from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import LiveSession


@shared_task
def send_live_class_reminders():
    """Runs every few minutes (see CELERY_BEAT_SCHEDULE) — notifies every
    registered student on a session starting in about an hour, once, same
    reminder_sent_at-guarded pattern as
    apps.purchases.tasks.send_cart_abandonment_reminders. Delivery channel
    (email vs. WhatsApp) and on/off both come from the single
    "Live Class Reminder" template in Settings > Message Automations —
    replaces the old two separate email/WhatsApp booleans."""

    from settings_app.notifications import send_notification

    now = timezone.now()
    window_start = now + timedelta(minutes=55)
    window_end = now + timedelta(minutes=65)

    due_sessions = LiveSession.objects.select_related('batch__course').filter(
        scheduled_at__gte=window_start, scheduled_at__lte=window_end,
        reminder_sent_at__isnull=True, status__in=['scheduled', 'live'],
    )

    sent = 0

    for session in due_sessions:
        registrations = session.batch.registrations.select_related('student').filter(status='registered')
        for registration in registrations:
            student = registration.student
            sent_ok = send_notification('live_class_reminder', email=student.email, phone=student.phone, context={
                'student_name': student.full_name,
                'session_title': session.title,
                'course_title': session.batch.course.title,
                'meeting_url': session.meeting_url,
            })
            if sent_ok:
                sent += 1

        session.reminder_sent_at = now
        session.save(update_fields=['reminder_sent_at'])

    return sent
