from django.utils import timezone
from rest_framework import serializers

from .models import Batch, BatchRegistration, LiveClassSettings, LiveSession, SessionAttendance


class BatchSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    instructor_name = serializers.CharField(
        source='course.instructor.member.full_name', read_only=True, default=None
    )
    registered_count = serializers.ReadOnlyField()

    class Meta:
        model = Batch
        fields = [
            'id', 'course', 'course_title', 'instructor_name', 'name', 'mode', 'start_date', 'end_date',
            'max_students', 'status', 'is_public', 'registered_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class LiveSessionSerializer(serializers.ModelSerializer):
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    course_title = serializers.CharField(source='batch.course.title', read_only=True)

    class Meta:
        model = LiveSession
        fields = [
            'id', 'batch', 'batch_name', 'course_title', 'title', 'scheduled_at',
            'duration_minutes', 'meeting_url', 'zoom_meeting_id', 'recording_url', 'status', 'created_at',
        ]
        read_only_fields = ['id', 'meeting_url', 'zoom_meeting_id', 'created_at']


class BatchRegistrationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True)

    class Meta:
        model = BatchRegistration
        fields = [
            'id', 'batch', 'batch_name', 'student', 'student_name', 'student_email',
            'status', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class BatchRegistrationCreateSerializer(serializers.ModelSerializer):
    """Student self-request from the public website — NOT immediate access.
    Lands as status='pending'; an admin contacts the student to confirm
    interest/payment and only then flips it to 'registered' from the
    dashboard (BatchRegistrationDetailView), which is what actually grants
    access to the batch's live sessions (see MyBatchesListView)."""

    class Meta:
        model = BatchRegistration
        fields = ['id', 'batch', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def validate_batch(self, batch):
        if not batch.is_public:
            raise serializers.ValidationError('This batch is not open for registration.')
        if batch.max_students and batch.registered_count >= batch.max_students:
            raise serializers.ValidationError('This batch is full.')
        return batch

    def validate(self, attrs):
        student = self.context['request'].user
        if BatchRegistration.objects.filter(student=student, batch=attrs['batch']).exists():
            raise serializers.ValidationError('You have already requested to join this batch.')
        return attrs

    def create(self, validated_data):
        validated_data['status'] = 'pending'
        return super().create(validated_data)


class SessionAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    session_title = serializers.CharField(source='session.title', read_only=True)

    class Meta:
        model = SessionAttendance
        fields = ['id', 'session', 'session_title', 'student', 'student_name', 'status', 'joined_at']
        read_only_fields = ['id']


class PublicBatchSerializer(serializers.ModelSerializer):
    """What the public website (landing page cards, live classes page)
    fetches — only ever `is_public=True` batches (enforced by the view)."""

    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    thumbnail_url = serializers.CharField(source='course.thumbnail_url', read_only=True)
    short_description = serializers.CharField(source='course.short_description', read_only=True)
    instructor_name = serializers.CharField(
        source='course.instructor.member.full_name', read_only=True, default=None
    )
    registered_count = serializers.ReadOnlyField()
    seats_left = serializers.SerializerMethodField()
    next_session_at = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = [
            'id', 'course_title', 'course_slug', 'thumbnail_url', 'short_description',
            'instructor_name', 'name', 'mode', 'start_date', 'end_date', 'max_students',
            'registered_count', 'seats_left', 'next_session_at',
        ]

    def get_seats_left(self, obj):
        if not obj.max_students:
            return None
        return max(0, obj.max_students - obj.registered_count)

    def get_next_session_at(self, obj):
        upcoming = obj.sessions.filter(
            scheduled_at__gte=timezone.now(), status__in=['scheduled', 'live'],
        ).order_by('scheduled_at').first()
        return upcoming.scheduled_at if upcoming else None


class LiveClassSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiveClassSettings
        fields = [
            'waiting_room_enabled', 'chat_enabled', 'default_mic_on', 'default_cam_on',
            'restricted_mode_enabled', 'updated_at',
        ]
        read_only_fields = ['updated_at']
