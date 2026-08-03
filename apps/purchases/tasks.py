from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import CartItem, PurchaseSettings


def send_cart_reminder_email(cart_item):
    """Plain function (not a task) so both the scheduled sweep below and the
    admin's manual "Notify" button (see views.CartItemNotifyView) can reuse
    the exact same email. Content + the template's own is_active come from
    the "Abandoned Cart Reminder" row in Settings > Message Automations;
    the scheduled sweep is additionally gated by
    PurchaseSettings.abandoned_cart_reminder_enabled below (the age-based
    automation on/off), which is separate from whether the template itself
    is enabled."""

    from settings_app.notifications import send_notification

    send_notification('cart_abandoned', email=cart_item.student.email, context={
        'student_name': cart_item.student.full_name,
        'course_title': cart_item.course.title,
    })


@shared_task
def send_cart_abandonment_reminders():
    """Daily sweep (see CELERY_BEAT_SCHEDULE): emails students whose cart
    items have crossed the configured age threshold and haven't already
    been reminded. Returns the number of reminders sent (useful for both
    tests and Celery's task-result inspection)."""

    settings_obj = PurchaseSettings.get_solo()
    if not settings_obj.abandoned_cart_reminder_enabled:
        return 0

    cutoff = timezone.now() - timedelta(days=settings_obj.cart_reminder_days_threshold)
    stale_items = CartItem.objects.select_related('student', 'course').filter(
        created_at__lte=cutoff, reminder_sent_at__isnull=True,
    )

    sent = 0
    for item in stale_items:
        send_cart_reminder_email(item)
        item.reminder_sent_at = timezone.now()
        item.save(update_fields=['reminder_sent_at'])
        sent += 1

    return sent
