import django_filters
from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from common.exports import export_rows
from courses.models import Course
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Certificate, CertificateTemplate
from .serializers import (
    CertificateCourseSerializer,
    CertificateSerializer,
    CertificateTemplateSerializer,
    CertificateVerifySerializer,
    EligibleStudentSerializer,
)
from .services import default_certificate_type_for_course, eligible_students_for_course

CERTIFICATE_SEARCH_FIELDS = ['student__full_name', 'student__email', 'course__title', 'certificate_code']


def _instructor_profile(user):
    return getattr(user, 'instructor_profile', None)


# ---------------------------------------------------------------------------
# Public verification panel
# ---------------------------------------------------------------------------

class CertificateVerifyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, certificate_code):
        try:
            certificate = Certificate.objects.select_related('student', 'course', 'template').get(
                certificate_code=certificate_code
            )
        except Certificate.DoesNotExist:
            return Response({'valid': False, 'detail': 'No certificate found with this code.'}, status=404)

        data = CertificateVerifySerializer(certificate).data
        data['valid'] = certificate.status == 'issued'
        return Response(data)


# ---------------------------------------------------------------------------
# Student-facing
# ---------------------------------------------------------------------------

class MyCertificatesListView(generics.ListAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = CertificateSerializer
    pagination_class = None

    def get_queryset(self):
        return Certificate.objects.select_related('course', 'template').filter(student=self.request.user)


# ---------------------------------------------------------------------------
# Dashboard (RBAC) — Templates
# ---------------------------------------------------------------------------

class CertificateTemplateListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_certificates')]
    serializer_class = CertificateTemplateSerializer
    queryset = CertificateTemplate.objects.all()
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category']


class CertificateTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_certificates')]
    serializer_class = CertificateTemplateSerializer
    queryset = CertificateTemplate.objects.all()


# ---------------------------------------------------------------------------
# Dashboard (RBAC) — Certificates
# ---------------------------------------------------------------------------

class CertificateFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='issued_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='issued_at', lookup_expr='date__lte')

    class Meta:
        model = Certificate
        fields = ['course', 'status', 'certificate_type', 'issue_type', 'start_date', 'end_date']


def _scoped_certificates(user):
    base = Certificate.objects.select_related('student', 'course', 'template')
    if user.has_permission('manage_certificates'):
        return base.all()
    if user.has_permission('manage_own_courses'):
        instructor = _instructor_profile(user)
        return base.filter(course__instructor=instructor) if instructor else base.none()
    raise PermissionDenied('You do not have permission to view certificates.')


class CertificateListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = CertificateSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = CertificateFilter
    search_fields = CERTIFICATE_SEARCH_FIELDS

    def get_queryset(self):
        return _scoped_certificates(self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.has_permission('manage_certificates') or user.has_permission('manage_own_courses')):
            raise PermissionDenied('You do not have permission to issue certificates.')
        course = serializer.validated_data['course']
        certificate_type = serializer.validated_data.get('certificate_type') or default_certificate_type_for_course(course)
        serializer.save(issue_type='manual', certificate_type=certificate_type)


class CertificateDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_certificates')]
    serializer_class = CertificateSerializer
    queryset = Certificate.objects.select_related('student', 'course', 'template')


class CertificateExportView(APIView):
    """Exports certificates matching the current search/date/status filters
    (or a specific selected set via `ids`) as CSV, Excel, or PDF."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_certificates')]

    HEADERS = [
        'Certificate Code', 'Student', 'Email', 'Course', 'Type', 'Issue Type', 'Status', 'Issued At',
    ]
    FIELDS = [
        'certificate_code', 'student_name', 'student_email', 'course_title',
        'certificate_type', 'issue_type', 'status', 'issued_at',
    ]

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()

        ids_param = request.query_params.get('ids')
        if ids_param:
            ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
            queryset = _scoped_certificates(request.user).filter(id__in=ids)
        else:
            queryset = CertificateFilter(request.query_params, queryset=_scoped_certificates(request.user)).qs
            search = request.query_params.get('search')
            if search:
                query = Q()
                for field in CERTIFICATE_SEARCH_FIELDS:
                    query |= Q(**{f'{field}__icontains': search})
                queryset = queryset.filter(query)

        rows = CertificateSerializer(queryset.order_by('-issued_at'), many=True).data
        if not rows:
            return Response({'detail': 'No matching certificates to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'certificates')


# ---------------------------------------------------------------------------
# Dashboard (RBAC) — manual generation helpers (course/student pickers)
# ---------------------------------------------------------------------------

class CertificateCourseListView(generics.ListAPIView):
    """Certificate-enabled courses, for the "Generate Certificate" modal's
    course picker — scoped to `manage_certificates` rather than requiring
    the (separate) course-management permission."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_certificates')]
    serializer_class = CertificateCourseSerializer
    pagination_class = None
    queryset = Course.objects.filter(certificate_enabled=True).order_by('title')


class EligibleStudentsView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_certificates')]

    def get(self, request):
        course_id = request.query_params.get('course')
        if not course_id:
            return Response({'detail': 'A course id is required.'}, status=400)
        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found.'}, status=404)

        students = eligible_students_for_course(course)
        return Response(EligibleStudentSerializer(students, many=True).data)


# ---------------------------------------------------------------------------
# Dashboard (RBAC) — Analytics
# ---------------------------------------------------------------------------

class CertificateAnalyticsView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_certificates')]

    def get(self, request):
        from datetime import timedelta

        queryset = Certificate.objects.all()
        total = queryset.count()

        by_type = dict(
            queryset.values_list('certificate_type').annotate(count=Count('id')).order_by()
        )
        by_issue_type = dict(
            queryset.values_list('issue_type').annotate(count=Count('id')).order_by()
        )
        by_status = dict(
            queryset.values_list('status').annotate(count=Count('id')).order_by()
        )

        since = timezone.now() - timedelta(days=180)
        issued_over_time = (
            queryset.filter(issued_at__gte=since)
            .annotate(month=TruncMonth('issued_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        top_courses = (
            queryset.values('course__title')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        return Response({
            'total': total,
            'by_type': {
                'online_course': by_type.get('online_course', 0),
                'internship': by_type.get('internship', 0),
                'workshop': by_type.get('workshop', 0),
                'completion': by_type.get('completion', 0),
            },
            'by_issue_type': {
                'manual': by_issue_type.get('manual', 0),
                'auto': by_issue_type.get('auto', 0),
            },
            'by_status': {
                'issued': by_status.get('issued', 0),
                'revoked': by_status.get('revoked', 0),
            },
            'issued_over_time': [
                {'month': row['month'].strftime('%b %Y'), 'count': row['count']}
                for row in issued_over_time
            ],
            'top_courses': [
                {'course_title': row['course__title'], 'count': row['count']}
                for row in top_courses
            ],
        })
