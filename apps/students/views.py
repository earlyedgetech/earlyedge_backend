from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from purchases.models import Purchase
from rest_framework import filters, generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Student
from .serializers import StudentCreateSerializer, StudentDetailSerializer, StudentSerializer


class StudentListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_students')]
    queryset = Student.objects.all().order_by('-created_at')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'is_verified', 'source']
    search_fields = ['full_name', 'email', 'phone']

    def get_serializer_class(self):
        return StudentCreateSerializer if self.request.method == 'POST' else StudentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.save()
        return Response(StudentSerializer(student).data, status=201)


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_students')]
    serializer_class = StudentDetailSerializer
    queryset = Student.objects.all().prefetch_related(
        'purchases__course', 'certificates__course', 'challenge_submissions__challenge',
    )


class StudentAnalyticsOverviewView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_students')]

    RANGE_DAYS = {'30d': 30, '90d': 90, '365d': 365}

    def get(self, request):
        from datetime import timedelta

        now = timezone.now()
        students = Student.objects.all()
        total_students = students.count()
        active_students = students.filter(is_active=True).count()
        verified_students = students.filter(is_verified=True).count()
        new_students_this_month = students.filter(
            created_at__year=now.year, created_at__month=now.month
        ).count()

        range_param = request.query_params.get('range', '30d')
        days = self.RANGE_DAYS.get(range_param, 30)
        since = now - timedelta(days=days)
        enrollment_trend = list(
            Purchase.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        progress_breakdown = list(
            Purchase.objects.values('enrollment_status').annotate(count=Count('id')).order_by('enrollment_status')
        )

        top_courses = list(
            Purchase.objects.values('course__title')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        top_courses = [{'course_title': row['course__title'], 'count': row['count']} for row in top_courses]

        region_breakdown = list(
            students.exclude(state='').values('state').annotate(count=Count('id')).order_by('-count')
        )

        return Response({
            'total_students': total_students,
            'active_students': active_students,
            'verified_students': verified_students,
            'new_students_this_month': new_students_this_month,
            'enrollment_trend': enrollment_trend,
            'progress_breakdown': progress_breakdown,
            'top_courses': top_courses,
            'region_breakdown': region_breakdown,
        })
