"""Celery tasks for Leads Management: a daily follow-up digest email per
counsellor, and a daily sweep firing the two date-based automation triggers
(demo_missed, retry_date_reached) that can't be caught synchronously from a
request."""

from collections import defaultdict
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .automations import run_automations
from .models import CounsellingSession, Lead, LeadFollowUp, LeadSettings


@shared_task
def send_followup_digest():
    """Daily — emails each counsellor their due-today + overdue follow-ups,
    using the "Follow-up Digest" template from Settings > Message
    Automations (greeting/signoff templated, the list itself is generated
    here and interpolated in)."""

    from settings_app.notifications import send_notification

    now = timezone.now()
    due = LeadFollowUp.objects.select_related('lead', 'lead__assigned_to').filter(
        is_completed=False, follow_up_date__lte=now + timedelta(hours=24),
    )

    by_counsellor = defaultdict(list)
    for follow_up in due:
        counsellor = follow_up.lead.assigned_to
        if counsellor and counsellor.email:
            by_counsellor[counsellor].append(follow_up)

    sent = 0
    for counsellor, follow_ups in by_counsellor.items():
        lines = [
            f'- {f.lead.full_name}: {f.get_follow_up_type_display()} due {f.follow_up_date.strftime("%d %b %Y %H:%M")}'
            for f in follow_ups
        ]
        sent_ok = send_notification('lead_follow_up_digest', email=counsellor.email, context={
            'counsellor_name': counsellor.full_name,
            'follow_up_list': '\n'.join(lines),
        })
        if sent_ok:
            sent += 1

    return sent


@shared_task
def run_scheduled_automations():
    """Daily — fires demo_missed (a CounsellingSession scheduled in the
    past with no outcome recorded) and retry_date_reached (a lead sitting in
    the "Retry" stage past the configured retry interval). Guards against
    re-firing daily by checking for a prior matching LeadActivity rather
    than adding a dedicated "handled" flag to either model."""

    now = timezone.now()
    handled = 0

    missed_sessions = CounsellingSession.objects.select_related('lead').filter(scheduled_at__lt=now, outcome='')
    for session in missed_sessions:
        marker = f'session #{session.id} demo_missed'
        if session.lead.activities.filter(activity_type='automation', description__icontains=marker).exists():
            continue
        run_automations('demo_missed', session.lead)
        session.lead.activities.create(activity_type='automation', description=f'{marker} trigger fired.')
        handled += 1

    lead_settings = LeadSettings.get_solo()
    retry_cutoff = now - timedelta(days=lead_settings.retry_interval_days)
    retry_leads = Lead.objects.filter(stage__name='Retry', updated_at__lte=retry_cutoff, is_archived=False)
    for lead in retry_leads:
        if lead.activities.filter(
            activity_type='automation', description__icontains='retry_date_reached', created_at__gte=retry_cutoff,
        ).exists():
            continue
        run_automations('retry_date_reached', lead)
        lead.activities.create(activity_type='automation', description='retry_date_reached trigger fired.')
        handled += 1

    return handled
