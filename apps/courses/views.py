from datetime import timedelta

import django_filters
from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from certificates.models import Certificate
from common.exports import export_rows
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from purchases.models import Purchase
from rest_framework import filters, generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Course, CourseCategory, CourseFeedback, CourseSubcategory
from .serializers import (
    CourseCategorySerializer,
    CourseFeedbackCreateSerializer,
    CourseFeedbackPublicSerializer,
    CourseFeedbackSerializer,
    CoursePublicSerializer,
    CourseSerializer,
    CourseSubcategorySerializer,
)

COURSE_FEEDBACK_SEARCH_FIELDS = ['user_name', 'email', 'message']


def _instructor_profile(user):
    return getattr(user, 'instructor_profile', None)


class IsCourseManager(HasDashboardPermission):
    def __init__(self):
        super().__init__('manage_courses')


def recompute_course_rating(course):
    """Keeps Course.average_rating/total_reviews in sync with its approved
    reviews — called whenever a review's approval state changes or it's
    deleted."""

    approved_reviews = course.feedback.filter(
        feedback_type='review', is_approved=True, rating__isnull=False
    )
    stats = approved_reviews.aggregate(avg=Avg('rating'))
    course.average_rating = round(stats['avg'] or 0, 2)
    course.total_reviews = approved_reviews.count()
    course.save(update_fields=['average_rating', 'total_reviews'])


class CourseFeedbackFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = CourseFeedback
        fields = ['course', 'feedback_type', 'is_resolved', 'is_approved', 'start_date', 'end_date']


# ---------------------------------------------------------------------------
# Public (marketing site)
# ---------------------------------------------------------------------------

class CoursePublicListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CoursePublicSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category__slug', 'level', 'is_free', 'is_featured']
    search_fields = ['title', 'short_description', 'tags']
    queryset = Course.objects.select_related('category', 'instructor__member').filter(
        status='published', visibility='public'
    )


class CoursePublicDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = CoursePublicSerializer
    lookup_field = 'slug'
    queryset = Course.objects.select_related('category', 'instructor__member').filter(
        status='published', visibility='public'
    )


class CourseCategoryPublicListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CourseCategorySerializer
    queryset = CourseCategory.objects.all()
    pagination_class = None


class CourseFeedbackPublicCreateView(generics.CreateAPIView):
    """A logged-in student leaves a review/complaint/suggestion on a course."""

    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = CourseFeedbackCreateSerializer

    def perform_create(self, serializer):
        student = self.request.user
        serializer.save(student=student, user_name=student.full_name, email=student.email)


class CourseFeedbackPublicListView(generics.ListAPIView):
    """Approved course reviews for the landing page — no auth required."""

    permission_classes = [AllowAny]
    serializer_class = CourseFeedbackPublicSerializer
    queryset = CourseFeedback.objects.select_related('course').filter(
        feedback_type='review', is_approved=True
    ).order_by('-created_at')


# ---------------------------------------------------------------------------
# Dashboard (RBAC) — admins see everything, instructors see only their own
# courses (manage_own_courses), matching the per-instructor scoping used
# throughout the dashboard.
# ---------------------------------------------------------------------------

class CourseCategoryListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsCourseManager]
    serializer_class = CourseCategorySerializer
    queryset = CourseCategory.objects.prefetch_related('subcategories')
    pagination_class = None


class CourseCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsCourseManager]
    serializer_class = CourseCategorySerializer
    queryset = CourseCategory.objects.prefetch_related('subcategories')


class CourseSubcategoryListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsCourseManager]
    serializer_class = CourseSubcategorySerializer
    pagination_class = None

    def get_queryset(self):
        queryset = CourseSubcategory.objects.select_related('category')
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset


class CourseSubcategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsCourseManager]
    serializer_class = CourseSubcategorySerializer
    queryset = CourseSubcategory.objects.select_related('category')


class CourseListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = CourseSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['instructor', 'category', 'status']

    def get_queryset(self):
        user = self.request.user
        base = Course.objects.select_related('category', 'instructor__member')
        if user.has_permission('manage_courses'):
            return base.all()
        if user.has_permission('manage_own_courses'):
            instructor = _instructor_profile(user)
            return base.filter(instructor=instructor) if instructor else base.none()
        raise PermissionDenied('You do not have permission to view courses.')

    def perform_create(self, serializer):
        user = self.request.user
        if user.has_permission('manage_courses'):
            serializer.save()
            return
        if user.has_permission('manage_own_courses'):
            instructor = _instructor_profile(user)
            if not instructor:
                raise PermissionDenied('No instructor profile linked to this account.')
            serializer.save(instructor=instructor)
            return
        raise PermissionDenied('You do not have permission to create courses.')


class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = CourseSerializer

    def get_queryset(self):
        user = self.request.user
        base = Course.objects.select_related('category', 'instructor__member')
        if user.has_permission('manage_courses'):
            return base.all()
        if user.has_permission('manage_own_courses'):
            instructor = _instructor_profile(user)
            return base.filter(instructor=instructor) if instructor else base.none()
        raise PermissionDenied('You do not have permission to view this course.')

    def perform_destroy(self, instance):
        if not self.request.user.has_permission('manage_courses'):
            raise PermissionDenied('Only an admin can delete a course.')
        instance.delete()


def _scoped_courses(user):
    base = Course.objects.select_related('category', 'instructor__member')
    if user.has_permission('manage_courses'):
        return base.all()
    if user.has_permission('manage_own_courses'):
        instructor = _instructor_profile(user)
        return base.filter(instructor=instructor) if instructor else base.none()
    raise PermissionDenied('You do not have permission to view course analytics.')


class CourseAnalyticsOverviewView(APIView):
    """Real per-course analytics for the dashboard's Course Analytics page —
    admins see platform-wide numbers, instructors see only their own
    courses, mirroring the scoping already used by CourseListCreateView.

    "Completion" is derived from issued Certificates rather than
    Purchase.progress_percent/enrollment_status — nothing in the app
    currently updates those two fields, so they'd always read 0; a Certificate
    row is a real, actively-used signal (see live_classes.views —
    BatchRegistrationDetailView's docstring) that a student finished a course.
    """

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    RANGE_DAYS = {'30d': 30, '90d': 90, '365d': 365}

    def get(self, request):
        courses = _scoped_courses(request.user)
        purchases = Purchase.objects.filter(course__in=courses)
        completed_purchases = purchases.filter(payment_status='completed')
        certificates = Certificate.objects.filter(course__in=courses, status='issued')

        total_courses = courses.count()
        total_enrollments = completed_purchases.count()
        total_revenue = completed_purchases.aggregate(total=Sum('amount_paid'))['total'] or 0
        avg_rating = courses.aggregate(avg=Avg('average_rating'))['avg'] or 0

        completion_rate = (
            round((certificates.count() / total_enrollments) * 100, 1) if total_enrollments else 0
        )

        range_param = request.query_params.get('range', '90d')
        days = self.RANGE_DAYS.get(range_param)
        trend_qs = completed_purchases
        if days is not None:
            since = timezone.now() - timedelta(days=days)
            trend_qs = trend_qs.filter(created_at__gte=since)

        enrollments_over_time = list(
            trend_qs
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        popular_courses = [
            {
                'id': course.id,
                'title': course.title,
                'enrollments': course.total_enrollments,
                'average_rating': course.average_rating,
            }
            for course in courses.order_by('-total_enrollments')[:8]
        ]

        top_instructors_qs = (
            completed_purchases
            .exclude(course__instructor__isnull=True)
            .values('course__instructor', 'course__instructor__member__full_name')
            .annotate(enrollments=Count('id'), revenue=Sum('amount_paid'))
            .order_by('-enrollments')[:8]
        )
        top_instructors = [
            {
                'id': row['course__instructor'],
                'name': row['course__instructor__member__full_name'],
                'enrollments': row['enrollments'],
                'revenue': row['revenue'] or 0,
            }
            for row in top_instructors_qs
        ]

        return Response({
            'total_courses': total_courses,
            'total_enrollments': total_enrollments,
            'total_revenue': total_revenue,
            'avg_rating': round(avg_rating, 2),
            'completion_rate': completion_rate,
            'enrollments_over_time': enrollments_over_time,
            'popular_courses': popular_courses,
            'top_instructors': top_instructors,
        })


def _scoped_course_feedback(user):
    base = CourseFeedback.objects.select_related('course')
    if user.has_permission('manage_courses'):
        return base.all()
    if user.has_permission('manage_own_courses'):
        instructor = _instructor_profile(user)
        return base.filter(course__instructor=instructor) if instructor else base.none()
    raise PermissionDenied('You do not have permission to view course feedback.')


def get_filtered_course_feedback(request):
    """Same scoping + search/date-range filtering as the feedback list view,
    or a specific set of rows via `ids` (export-selected, ignores filters)."""

    user = request.user
    ids_param = request.query_params.get('ids')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return _scoped_course_feedback(user).filter(id__in=ids)

    queryset = CourseFeedbackFilter(request.query_params, queryset=_scoped_course_feedback(user)).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in COURSE_FEEDBACK_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class CourseFeedbackListView(generics.ListAPIView):
    """Admins see all feedback; instructors see feedback only for their own
    courses — the same scoping as the course list itself."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = CourseFeedbackSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = CourseFeedbackFilter
    search_fields = COURSE_FEEDBACK_SEARCH_FIELDS

    def get_queryset(self):
        return _scoped_course_feedback(self.request.user)


class CourseFeedbackExportView(APIView):
    """Exports course feedback matching the current search/date/scope
    filters (or a specific selected set via `ids`) as CSV, Excel, or PDF."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    HEADERS = ['ID', 'Course', 'User', 'Email', 'Type', 'Rating', 'Resolved', 'Approved', 'Message', 'Created At']
    FIELDS = [
        'id', 'course_title', 'user_name', 'email', 'feedback_type', 'rating',
        'is_resolved', 'is_approved', 'message', 'created_at',
    ]

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_course_feedback(request).order_by('-created_at')
        rows = CourseFeedbackSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching feedback to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'course_feedback')


class CourseFeedbackDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Only `is_resolved`/`is_approved` are meaningfully editable here — the
    review content itself belongs to the student who wrote it. Approving
    or unapproving a review (or deleting one) recomputes the parent
    course's average_rating/total_reviews."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsCourseManager]
    serializer_class = CourseFeedbackSerializer
    queryset = CourseFeedback.objects.select_related('course')

    def perform_update(self, serializer):
        feedback = serializer.save()
        recompute_course_rating(feedback.course)

    def perform_destroy(self, instance):
        course = instance.course
        instance.delete()
        recompute_course_rating(course)
