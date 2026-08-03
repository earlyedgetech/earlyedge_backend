from datetime import datetime, time, timedelta

from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Batch, BatchRegistration, LiveClassSettings, LiveSession, SessionAttendance
from .serializers import (
    BatchRegistrationCreateSerializer,
    BatchRegistrationSerializer,
    BatchSerializer,
    LiveClassSettingsSerializer,
    LiveSessionSerializer,
    PublicBatchSerializer,
    SessionAttendanceSerializer,
)
from common.integrations.zoom_client import ZoomClient


def _instructor_profile(user):
    return getattr(user, 'instructor_profile', None)


def _scoped_queryset(user, base, own_filter):
    if user.has_permission('manage_live_classes'):
        return base
    if user.has_permission('manage_own_courses'):
        instructor = _instructor_profile(user)
        return own_filter(base, instructor) if instructor else base.none()
    raise PermissionDenied('You do not have permission to view live classes.')


class IsLiveClassManager(HasDashboardPermission):
    def __init__(self):
        super().__init__('manage_live_classes')


def _create_zoom_meeting_for_session(session):
    client = ZoomClient()
    meeting = client.create_meeting(
        topic=f'{session.batch.course.title} — {session.title}',
        start_time=session.scheduled_at,
        duration_minutes=session.duration_minutes,
    )
    session.meeting_url = meeting['join_url']
    session.zoom_meeting_id = meeting['id']
    session.save(update_fields=['meeting_url', 'zoom_meeting_id'])


# ---------------------------------------------------------------------------
# Student-facing
# ---------------------------------------------------------------------------

def _enrolled_course_ids(student):
    """Courses this student is actually enrolled in — a direct purchase OR
    an active AccessPlan covering the course (see purchases.access) — the
    gate for "only shown to the logged-in student who registered for that
    course", not just anyone with a batch registration row."""
    from purchases.access import enrolled_course_ids

    return enrolled_course_ids(student)


class MyBatchesListView(generics.ListAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = BatchSerializer

    def get_queryset(self):
        return Batch.objects.select_related('course').filter(
            registrations__student=self.request.user,
            registrations__status='registered',
            course_id__in=_enrolled_course_ids(self.request.user),
        ).distinct()


class MyUpcomingSessionsListView(generics.ListAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = LiveSessionSerializer

    def get_queryset(self):
        return LiveSession.objects.select_related('batch__course').filter(
            batch__registrations__student=self.request.user,
            batch__registrations__status='registered',
            batch__course_id__in=_enrolled_course_ids(self.request.user),
        ).distinct().order_by('scheduled_at')


class BatchRegistrationCreateView(generics.CreateAPIView):
    """A logged-in student requests to join a public batch — this is what
    the website's "Request to Join" button calls. Lands as status='pending'
    (see serializer); an admin contacts and confirms from the dashboard."""

    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = BatchRegistrationCreateSerializer

    def perform_create(self, serializer):
        registration = serializer.save(student=self.request.user)

        from admin_security.notifications import notify_admins_with_permission
        from settings_app.notifications import send_notification

        send_notification('batch_join_requested', email=self.request.user.email, context={
            'student_name': self.request.user.full_name,
            'course_title': registration.batch.course.title,
            'batch_name': registration.batch.name,
        })
        notify_admins_with_permission(
            'manage_live_classes',
            f'{self.request.user.full_name} requested to join {registration.batch.name}',
            link='/-/admin-dashboard/live_classes/registrations_students',
        )


# ---------------------------------------------------------------------------
# Public (marketing site)
# ---------------------------------------------------------------------------

class PublicBatchListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicBatchSerializer
    queryset = Batch.objects.select_related('course', 'course__instructor__member').filter(is_public=True)


class PublicBatchDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicBatchSerializer
    queryset = Batch.objects.select_related('course', 'course__instructor__member').filter(is_public=True)


# ---------------------------------------------------------------------------
# Dashboard (RBAC) — admins see everything; instructors see only batches,
# sessions, registrations, and attendance for the courses they teach.
# ---------------------------------------------------------------------------

class BatchListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = BatchSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['course', 'status', 'is_public']

    def get_queryset(self):
        return _scoped_queryset(
            self.request.user,
            Batch.objects.select_related('course', 'course__instructor__member'),
            lambda base, instructor: base.filter(course__instructor=instructor),
        )

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.has_permission('manage_live_classes') or user.has_permission('manage_own_courses')):
            raise PermissionDenied('You do not have permission to create batches.')
        serializer.save()


class BatchDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = BatchSerializer

    def get_queryset(self):
        return _scoped_queryset(
            self.request.user,
            Batch.objects.select_related('course', 'course__instructor__member'),
            lambda base, instructor: base.filter(course__instructor=instructor),
        )


class BatchGenerateSessionsView(APIView):
    """Expands a Batch's recurring schedule into individual LiveSession rows
    — one per matching weekday between start_date/end_date — each getting a
    real (or mock) Zoom link. This is the "pick the instructor's slot, get
    the timings automatically" mechanism."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    def post(self, request, pk):
        batch = get_object_or_404(
            _scoped_queryset(
                request.user,
                Batch.objects.select_related('course'),
                lambda base, instructor: base.filter(course__instructor=instructor),
            ),
            pk=pk,
        )
        if not (request.user.has_permission('manage_live_classes') or request.user.has_permission('manage_own_courses')):
            raise PermissionDenied('You do not have permission to schedule sessions.')

        if not batch.start_date or not batch.end_date:
            raise ValidationError('Batch must have a start_date and end_date to generate sessions.')

        weekdays = request.data.get('weekdays', [])
        start_time_str = request.data.get('start_time')
        duration_minutes = int(request.data.get('duration_minutes', 60))
        if not weekdays or not start_time_str:
            raise ValidationError('weekdays and start_time are required.')

        hour, minute = (int(part) for part in start_time_str.split(':')[:2])
        slot_time = time(hour=hour, minute=minute)

        created = []
        current = batch.start_date
        while current <= batch.end_date:
            if current.weekday() in weekdays:
                naive_dt = datetime.combine(current, slot_time)
                scheduled_at = timezone.make_aware(naive_dt) if timezone.is_naive(naive_dt) else naive_dt
                session = LiveSession.objects.create(
                    batch=batch,
                    title=f'{batch.name} — {current.strftime("%b %d")}',
                    scheduled_at=scheduled_at,
                    duration_minutes=duration_minutes,
                )
                _create_zoom_meeting_for_session(session)
                created.append(session)
            current += timedelta(days=1)

        return Response(LiveSessionSerializer(created, many=True).data, status=201)


class LiveSessionListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = LiveSessionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['batch', 'status']

    def get_queryset(self):
        return _scoped_queryset(
            self.request.user,
            LiveSession.objects.select_related('batch__course'),
            lambda base, instructor: base.filter(batch__course__instructor=instructor),
        )

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.has_permission('manage_live_classes') or user.has_permission('manage_own_courses')):
            raise PermissionDenied('You do not have permission to schedule sessions.')
        session = serializer.save()
        _create_zoom_meeting_for_session(session)


class LiveSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = LiveSessionSerializer

    def get_queryset(self):
        return _scoped_queryset(
            self.request.user,
            LiveSession.objects.select_related('batch__course'),
            lambda base, instructor: base.filter(batch__course__instructor=instructor),
        )


class BatchRegistrationListView(generics.ListAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = BatchRegistrationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['batch', 'status']

    def get_queryset(self):
        return _scoped_queryset(
            self.request.user,
            BatchRegistration.objects.select_related('batch__course', 'student'),
            lambda base, instructor: base.filter(batch__course__instructor=instructor),
        )


class BatchRegistrationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Marking a registration `completed` (individually, or in bulk when its
    batch is marked completed — see certificates.signals) is what drives
    automatic certificate issuance for face-to-face classes. Destroy lets an
    admin cancel/remove a registration from the dashboard."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = BatchRegistrationSerializer

    def get_queryset(self):
        return _scoped_queryset(
            self.request.user,
            BatchRegistration.objects.select_related('batch__course', 'student'),
            lambda base, instructor: base.filter(batch__course__instructor=instructor),
        )

    def _check_manage_permission(self):
        user = self.request.user
        if not (user.has_permission('manage_live_classes') or user.has_permission('manage_own_courses')):
            raise PermissionDenied('You do not have permission to manage registrations.')

    def perform_update(self, serializer):
        self._check_manage_permission()
        was_pending = serializer.instance.status == 'pending'
        registration = serializer.save()

        if was_pending and registration.status == 'registered':
            from settings_app.notifications import send_notification

            send_notification('batch_registration_confirmed', email=registration.student.email, context={
                'student_name': registration.student.full_name,
                'course_title': registration.batch.course.title,
                'batch_name': registration.batch.name,
            })

    def perform_destroy(self, instance):
        self._check_manage_permission()
        instance.delete()


class SessionAttendanceListView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = SessionAttendanceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['session', 'status']

    def get_queryset(self):
        return _scoped_queryset(
            self.request.user,
            SessionAttendance.objects.select_related('session__batch__course', 'student'),
            lambda base, instructor: base.filter(session__batch__course__instructor=instructor),
        )

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.has_permission('manage_live_classes') or user.has_permission('manage_own_courses')):
            raise PermissionDenied('You do not have permission to mark attendance.')
        serializer.save()


class SessionAttendanceDetailView(generics.RetrieveUpdateAPIView):
    """Lets an already-marked attendance record be corrected (e.g.
    absent -> present) — previously only creation was supported."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = SessionAttendanceSerializer

    def get_queryset(self):
        return _scoped_queryset(
            self.request.user,
            SessionAttendance.objects.select_related('session__batch__course', 'student'),
            lambda base, instructor: base.filter(session__batch__course__instructor=instructor),
        )

    def perform_update(self, serializer):
        user = self.request.user
        if not (user.has_permission('manage_live_classes') or user.has_permission('manage_own_courses')):
            raise PermissionDenied('You do not have permission to mark attendance.')
        serializer.save()


class LiveClassSettingsView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, IsLiveClassManager]

    def get(self, request):
        return Response(LiveClassSettingsSerializer(LiveClassSettings.get_solo()).data)

    def patch(self, request):
        serializer = LiveClassSettingsSerializer(LiveClassSettings.get_solo(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class LiveClassAnalyticsOverviewView(APIView):
    """Real per-batch analytics — same RBAC scoping and shape convention as
    courses.views.CourseAnalyticsOverviewView."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    def get(self, request):
        batches = _scoped_queryset(
            request.user,
            Batch.objects.select_related('course'),
            lambda base, instructor: base.filter(course__instructor=instructor),
        )
        sessions = LiveSession.objects.filter(batch__in=batches)
        registrations = BatchRegistration.objects.filter(batch__in=batches)
        attendance = SessionAttendance.objects.filter(session__batch__in=batches)

        total_batches = batches.count()
        total_sessions = sessions.count()
        total_registrations = registrations.count()
        upcoming_sessions_count = sessions.filter(
            status__in=['scheduled', 'live'], scheduled_at__gte=timezone.now()
        ).count()

        attendance_counts = attendance.aggregate(
            total=Count('id'), present=Count('id', filter=Q(status='present'))
        )
        attendance_rate = (
            round((attendance_counts['present'] / attendance_counts['total']) * 100, 1)
            if attendance_counts['total'] else 0
        )

        batch_performance = []
        for batch in batches.order_by('-created_at')[:10]:
            batch_sessions = sessions.filter(batch=batch)
            batch_attendance = attendance.filter(session__batch=batch)
            batch_attendance_counts = batch_attendance.aggregate(
                total=Count('id'), present=Count('id', filter=Q(status='present'))
            )
            batch_performance.append({
                'id': batch.id,
                'name': batch.name,
                'course_title': batch.course.title,
                'registrations': registrations.filter(batch=batch).count(),
                'sessions_count': batch_sessions.count(),
                'attendance_rate': (
                    round((batch_attendance_counts['present'] / batch_attendance_counts['total']) * 100, 1)
                    if batch_attendance_counts['total'] else 0
                ),
            })

        return Response({
            'total_batches': total_batches,
            'total_sessions': total_sessions,
            'total_registrations': total_registrations,
            'upcoming_sessions_count': upcoming_sessions_count,
            'attendance_rate': attendance_rate,
            'batch_performance': batch_performance,
        })
