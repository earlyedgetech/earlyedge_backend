import django_filters
from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from common.exports import export_rows
from courses.models import Course
from django.db.models import Avg, Count, Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from purchases.models import Purchase
from rest_framework import filters, generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Instructor, InstructorPayout, InstructorReview
from .serializers import (
    InstructorApplicationSerializer,
    InstructorCreateSerializer,
    InstructorPayoutSerializer,
    InstructorPublicSerializer,
    InstructorReviewCreateSerializer,
    InstructorReviewPublicSerializer,
    InstructorReviewSerializer,
    InstructorSerializer,
)

INSTRUCTOR_REVIEW_SEARCH_FIELDS = ['user_name', 'email', 'comment']


class IsInstructorManager(HasDashboardPermission):
    def __init__(self):
        super().__init__('manage_instructors')


def _instructor_earnings(instructor):
    total_revenue = Purchase.objects.filter(
        course__instructor=instructor, payment_status='completed'
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    gross_earnings = round(total_revenue * instructor.commission_rate / 100, 2)
    total_paid_out = instructor.payouts.aggregate(total=Sum('amount'))['total'] or 0
    return {
        'total_revenue': total_revenue,
        'commission_rate': instructor.commission_rate,
        'gross_earnings': gross_earnings,
        'total_paid_out': total_paid_out,
        'pending_balance': round(gross_earnings - total_paid_out, 2),
    }


def recompute_instructor_rating(instructor):
    """Keeps Instructor.rating_avg/total_ratings in sync with its approved
    reviews — called whenever a review's approval state changes or it's
    deleted."""

    approved_reviews = instructor.reviews.filter(is_approved=True)
    stats = approved_reviews.aggregate(avg=Avg('rating'))
    instructor.rating_avg = round(stats['avg'] or 0, 2)
    instructor.total_ratings = approved_reviews.count()
    instructor.save(update_fields=['rating_avg', 'total_ratings'])


class InstructorReviewFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = InstructorReview
        fields = ['instructor', 'is_approved', 'start_date', 'end_date']


def get_filtered_instructor_reviews(request):
    """Same search/date-range filtering as the instructor review list view,
    or a specific set of rows via `ids` (export-selected, ignores filters)."""

    ids_param = request.query_params.get('ids')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return InstructorReview.objects.filter(id__in=ids)

    queryset = InstructorReviewFilter(
        request.query_params, queryset=InstructorReview.objects.select_related('instructor__member', 'course')
    ).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in INSTRUCTOR_REVIEW_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class InstructorListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_instructors')]
    queryset = Instructor.objects.select_related('member').all()

    def get_serializer_class(self):
        return InstructorCreateSerializer if self.request.method == 'POST' else InstructorSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instructor = serializer.save()
        return Response(InstructorSerializer(instructor).data, status=201)


class InstructorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admins (manage_instructors) can view/edit any instructor. An
    instructor without that permission may only view/edit their own profile
    — never another instructor's, and never delete."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = InstructorSerializer

    def get_queryset(self):
        user = self.request.user
        if user.has_permission('manage_instructors'):
            return Instructor.objects.select_related('member').all()
        return Instructor.objects.select_related('member').filter(member=user)

    def perform_update(self, serializer):
        was_verified = serializer.instance.admin_verified
        instructor = serializer.save()

        if instructor.admin_verified and not was_verified:
            instructor.account_status = 'active'
            instructor.save(update_fields=['account_status'])

            from settings_app.notifications import send_notification

            send_notification('instructor_verified', email=instructor.member.email, context={
                'full_name': instructor.member.full_name,
            })

        member_should_be_active = instructor.account_status == 'active'
        if instructor.member.is_active != member_should_be_active:
            instructor.member.is_active = member_should_be_active
            instructor.member.save(update_fields=['is_active'])

    def perform_destroy(self, instance):
        if not self.request.user.has_permission('manage_instructors'):
            raise NotFound()
        instance.delete()


class InstructorApplyView(generics.CreateAPIView):
    """Public 'become an instructor' application form — the link an admin
    shares with a prospective instructor. Creates a pending, inactive login
    that an admin must verify (see InstructorDetailView.perform_update)
    before the instructor can sign in."""

    permission_classes = [AllowAny]
    serializer_class = InstructorApplicationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Application submitted. An admin will review and verify your account shortly.'},
            status=201,
        )


class InstructorMeView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    def get(self, request):
        try:
            instructor = Instructor.objects.select_related('member').get(member=request.user)
        except Instructor.DoesNotExist:
            raise NotFound('No instructor profile linked to this account.')
        return Response(InstructorSerializer(instructor).data)


class InstructorPublicListView(generics.ListAPIView):
    """Public instructor directory for the marketing site."""

    permission_classes = [AllowAny]
    serializer_class = InstructorPublicSerializer
    queryset = Instructor.objects.select_related('member').filter(admin_verified=True)


class InstructorPublicDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = InstructorPublicSerializer
    queryset = Instructor.objects.select_related('member').filter(admin_verified=True)


class InstructorReviewPublicCreateView(generics.CreateAPIView):
    """A logged-in student leaves a review on the instructor identified by
    the URL's <pk> — mirrors CourseFeedbackPublicCreateView in the courses
    app."""

    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = InstructorReviewCreateSerializer

    def perform_create(self, serializer):
        student = self.request.user
        serializer.save(
            instructor_id=self.kwargs['pk'],
            student=student,
            user_name=student.full_name,
            email=student.email,
        )


class InstructorReviewPublicListView(generics.ListAPIView):
    """Approved reviews for one instructor's public profile page — no auth
    required. Filter with ?instructor=<id>."""

    permission_classes = [AllowAny]
    serializer_class = InstructorReviewPublicSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['instructor']
    queryset = InstructorReview.objects.filter(is_approved=True).order_by('-created_at')


class InstructorReviewListView(generics.ListAPIView):
    """Dashboard list — admins (manage_instructors) only."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_instructors')]
    serializer_class = InstructorReviewSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = InstructorReviewFilter
    search_fields = INSTRUCTOR_REVIEW_SEARCH_FIELDS
    queryset = InstructorReview.objects.select_related('instructor__member', 'course')


class InstructorReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Only `is_approved` is meaningfully editable here — the review content
    belongs to the student who wrote it. Approving/unapproving or deleting a
    review recomputes the parent instructor's rating_avg/total_ratings."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_instructors')]
    serializer_class = InstructorReviewSerializer
    queryset = InstructorReview.objects.select_related('instructor__member', 'course')

    def perform_update(self, serializer):
        review = serializer.save()
        recompute_instructor_rating(review.instructor)

    def perform_destroy(self, instance):
        instructor = instance.instructor
        instance.delete()
        recompute_instructor_rating(instructor)


class InstructorReviewExportView(APIView):
    """Exports instructor reviews matching the current search/date filters
    (or a specific selected set via `ids`) as CSV, Excel, or PDF."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_instructors')]

    HEADERS = ['ID', 'Instructor', 'Course', 'User', 'Email', 'Rating', 'Approved', 'Comment', 'Created At']
    FIELDS = [
        'id', 'instructor_name', 'course_title', 'user_name', 'email', 'rating',
        'is_approved', 'comment', 'created_at',
    ]

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_instructor_reviews(request).order_by('-created_at')
        rows = InstructorReviewSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching reviews to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'instructor_reviews')


class InstructorEarningsView(APIView):
    """Computed earnings for one instructor (revenue from their courses'
    completed purchases × commission_rate) plus their payout history. POST
    records a new payout — an admin has already paid the instructor
    externally (via payout_method/payout_details) and is logging it here so
    pending_balance drops."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsInstructorManager]

    def get_instructor(self, pk):
        try:
            return Instructor.objects.get(pk=pk)
        except Instructor.DoesNotExist:
            raise NotFound('Instructor not found.')

    def _response_data(self, instructor):
        data = _instructor_earnings(instructor)
        payouts = instructor.payouts.select_related('recorded_by').all()
        data['payouts'] = InstructorPayoutSerializer(payouts, many=True).data
        return data

    def get(self, request, pk):
        instructor = self.get_instructor(pk)
        return Response(self._response_data(instructor))

    def post(self, request, pk):
        instructor = self.get_instructor(pk)
        serializer = InstructorPayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(instructor=instructor, recorded_by=request.user)
        return Response(self._response_data(instructor), status=201)


class InstructorAnalyticsOverviewView(APIView):
    """Real instructor analytics — same shape/pattern as
    courses.views.CourseAnalyticsOverviewView and
    live_classes.views.LiveClassAnalyticsOverviewView."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsInstructorManager]

    RANK_LIMIT = 8

    def get(self, request):
        base = Instructor.objects.select_related('member')
        total_instructors = base.count()
        active_instructors = base.filter(account_status='active').count()
        avg_rating = base.aggregate(avg=Avg('rating_avg'))['avg'] or 0
        avg_courses_per_instructor = (
            round(Course.objects.filter(instructor__isnull=False).count() / total_instructors, 1)
            if total_instructors else 0
        )

        revenue_by_instructor = dict(
            Purchase.objects.filter(payment_status='completed', course__instructor__isnull=False)
            .values_list('course__instructor')
            .annotate(revenue=Sum('amount_paid'))
        )
        total_commission_payable = round(
            sum(
                (revenue_by_instructor.get(i.id, 0) or 0) * i.commission_rate / 100
                for i in base
            ),
            2,
        )

        annotated = base.annotate(
            course_count_annotated=Count('courses', distinct=True),
            enrolled_students_annotated=Sum('courses__total_enrollments'),
        )

        def _row(i, **extra):
            return {'id': i.id, 'name': i.member.full_name, **extra}

        courses_per_instructor = [
            _row(i, course_count=i.course_count_annotated)
            for i in annotated.order_by('-course_count_annotated')[:self.RANK_LIMIT]
        ]
        top_rated = [
            _row(i, rating_avg=i.rating_avg, total_ratings=i.total_ratings)
            for i in base.order_by('-rating_avg')[:self.RANK_LIMIT]
        ]
        top_by_students = [
            _row(i, enrolled_students=i.enrolled_students_annotated or 0)
            for i in annotated.order_by('-enrolled_students_annotated')[:self.RANK_LIMIT]
        ]

        return Response({
            'total_instructors': total_instructors,
            'active_instructors': active_instructors,
            'avg_rating': round(avg_rating, 2),
            'avg_courses_per_instructor': avg_courses_per_instructor,
            'total_commission_payable': total_commission_payable,
            'courses_per_instructor': courses_per_instructor,
            'top_rated': top_rated,
            'top_by_students': top_by_students,
        })
