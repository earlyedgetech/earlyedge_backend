from common.models import TimeStampedModel
from django.db import models


class Batch(TimeStampedModel):
    STATUS_CHOICES = (
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    MODE_CHOICES = (
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('hybrid', 'Hybrid'),
    )

    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='batches')
    name = models.CharField(max_length=150)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='online')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    max_students = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    is_public = models.BooleanField(
        default=False,
        help_text='Shows this batch as a card on the public website (landing page / live classes page).',
    )

    class Meta:
        db_table = 'live_class_batches'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.course.title} - {self.name}'

    @property
    def registered_count(self):
        """Seats considered occupied — pending requests hold a seat too (so
        the batch can't be over-requested past capacity), dropped ones
        don't."""
        return self.registrations.exclude(status='dropped').count()


class LiveSession(TimeStampedModel):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='sessions')
    title = models.CharField(max_length=255)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    meeting_url = models.URLField(blank=True)
    zoom_meeting_id = models.CharField(max_length=50, blank=True)
    recording_url = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='scheduled')
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'live_sessions'
        ordering = ['scheduled_at']

    def __str__(self):
        return f'{self.batch} - {self.title}'


class BatchRegistration(TimeStampedModel):
    STATUS_CHOICES = (
        ('pending', 'Pending Confirmation'),
        ('registered', 'Registered'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
    )

    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='registrations')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='batch_registrations')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='registered')

    class Meta:
        db_table = 'live_class_registrations'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['batch', 'student'], name='unique_batch_student_registration')
        ]

    def __str__(self):
        return f'{self.student} - {self.batch}'


class SessionAttendance(TimeStampedModel):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    )

    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='attendance')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='session_attendance')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='absent')
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'live_session_attendance'
        constraints = [
            models.UniqueConstraint(fields=['session', 'student'], name='unique_session_student_attendance')
        ]

    def __str__(self):
        return f'{self.student} - {self.session} ({self.status})'


class LiveClassSettings(TimeStampedModel):
    """Solo settings row for Live Class Settings' General + Permissions tabs
    — everything else (recording storage, notifications, integrations) now
    lives under the main Settings module (Integrations / Message Automation)."""

    waiting_room_enabled = models.BooleanField(default=False)
    chat_enabled = models.BooleanField(default=True)
    default_mic_on = models.BooleanField(default=False)
    default_cam_on = models.BooleanField(default=False)
    restricted_mode_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = 'live_class_settings'

    def __str__(self):
        return 'Live Class Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
