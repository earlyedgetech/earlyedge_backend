"""Automation rule execution.

Triggered synchronously from views.py for in-request events
(new_lead_created, stage_changed, follow_up_completed) and from tasks.py's
daily sweep for date-based triggers (demo_missed, retry_date_reached).
Simple, fast actions — deliberately not routed through Celery, matching how
small this codebase's other per-request side effects are.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import AutomationRule, LeadActivity, LeadFollowUp


def run_automations(trigger, lead):
    for rule in AutomationRule.objects.filter(trigger=trigger, is_active=True):
        _execute(rule, lead)

    if trigger == 'new_lead_created':
        apply_default_assignment(lead)


def _execute(rule, lead):
    action_fn = _ACTIONS.get(rule.action)
    if not action_fn:
        return
    try:
        action_fn(lead, rule.config or {})
        LeadActivity.objects.create(
            lead=lead, activity_type='automation',
            description=f'"{rule.name}" ran ({rule.get_action_display()}).',
        )
    except Exception as exc:
        LeadActivity.objects.create(
            lead=lead, activity_type='automation', description=f'"{rule.name}" failed: {exc}',
        )


def _round_robin_counsellor():
    """Least-loaded active counsellor — even distribution without needing
    persistent cursor state across workers."""
    from admin_security.models import AdminMember

    return (
        AdminMember.objects.filter(role__slug='leads-manager', is_active=True)
        .annotate(lead_count=Count('assigned_leads', filter=Q(assigned_leads__is_archived=False)))
        .order_by('lead_count', 'id')
        .first()
    )


def _notify_lead_assigned(lead, counsellor):
    from admin_security.notifications import notify_admin
    from settings_app.notifications import send_notification

    notify_admin(
        counsellor, f'New lead assigned to you: {lead.full_name}',
        link='/-/admin-dashboard/leads_management/all_leads',
    )

    if not counsellor.email:
        return
    send_notification('lead_assigned', email=counsellor.email, context={
        'counsellor_name': counsellor.full_name,
        'lead_name': lead.full_name,
        'lead_contact': lead.phone or lead.email,
    })


def _assign_counsellor(lead, config):
    if config.get('strategy') == 'specific' and config.get('counsellor_id'):
        lead.assigned_to_id = config['counsellor_id']
        lead.save(update_fields=['assigned_to'])
        if lead.assigned_to:
            _notify_lead_assigned(lead, lead.assigned_to)
        return

    counsellor = _round_robin_counsellor()
    if counsellor:
        lead.assigned_to = counsellor
        lead.save(update_fields=['assigned_to'])
        _notify_lead_assigned(lead, counsellor)


def resolve_strategy_assignee(lead, settings):
    """Who `lead` should go to under Lead Settings > Assignment strategy.
    Returns None for 'manual' (no auto-assignment) or when nothing resolves.
    Source/branch/course-wise fall back to round-robin when this particular
    lead's source/branch/course has no configured mapping, so a strategy
    choice always does *something* rather than silently leaving leads
    unassigned."""
    from admin_security.models import AdminMember

    strategy = settings.assignment_strategy
    if strategy == 'manual':
        return None

    if strategy == 'source_wise' and lead.source_id:
        assignee = getattr(lead.source, 'default_assignee', None)
        if assignee and assignee.is_active:
            return assignee

    elif strategy == 'branch_wise' and lead.branch:
        assignee_id = (settings.branch_assignment_map or {}).get(lead.branch)
        if assignee_id:
            member = AdminMember.objects.filter(pk=assignee_id, is_active=True).first()
            if member:
                return member

    elif strategy == 'course_wise' and lead.interested_course_id:
        assignee_id = (settings.course_assignment_map or {}).get(str(lead.interested_course_id))
        if assignee_id:
            member = AdminMember.objects.filter(pk=assignee_id, is_active=True).first()
            if member:
                return member

    return _round_robin_counsellor()


def apply_default_assignment(lead):
    """Falls back to LeadSettings.assignment_strategy when no AutomationRule
    already assigned the lead on this trigger — this is what makes the
    Assignment & Duplicates tab in Lead Settings actually affect real leads,
    instead of being a stored-but-unused preference."""
    from .models import LeadSettings

    lead.refresh_from_db(fields=['assigned_to'])
    if lead.assigned_to_id is not None:
        return

    settings = LeadSettings.get_solo()
    assignee = resolve_strategy_assignee(lead, settings)
    if not assignee:
        return

    lead.assigned_to = assignee
    lead.save(update_fields=['assigned_to'])
    LeadActivity.objects.create(
        lead=lead, activity_type='assigned',
        description=f'Auto-assigned to {assignee.full_name} ({settings.get_assignment_strategy_display()}).',
    )
    _notify_lead_assigned(lead, assignee)


def _send_welcome_email(lead, config):
    """Uses the "Lead Welcome Email" template from Settings > Message
    Automations by default; a rule-specific subject/message in config
    overrides the content but still requires the site-wide template to be
    active unless explicitly overridden."""

    from settings_app.models import NotificationTemplate
    from settings_app.notifications import render_template, send_branded_email

    if not lead.email:
        return

    override_subject, override_message = config.get('subject'), config.get('message')
    template = NotificationTemplate.objects.filter(key='lead_welcome', is_active=True).first()
    if not template and not (override_subject or override_message):
        return

    default_subject, default_body = render_template('lead_welcome', {'lead_name': lead.full_name})
    send_branded_email(lead.email, override_subject or default_subject, override_message or default_body)


def _send_whatsapp(lead, config):
    from common.integrations.whatsapp_client import WhatsAppClient

    if not lead.phone:
        return
    WhatsAppClient().send_template_message(
        lead.phone, lead.full_name, config.get('message', 'Thanks for your interest!'),
    )


def _schedule_follow_up(lead, config):
    days = int(config.get('days_from_now', 1))
    LeadFollowUp.objects.create(
        lead=lead,
        follow_up_type=config.get('follow_up_type', 'call'),
        note=config.get('note', 'Auto-scheduled follow-up.'),
        follow_up_date=timezone.now() + timedelta(days=days),
    )


def _notify_manager(lead, config):
    from admin_security.models import AdminMember
    from settings_app.models import NotificationTemplate
    from settings_app.notifications import render_template, send_branded_email

    recipient_list = list(
        AdminMember.objects.filter(role__slug='admin', is_active=True).exclude(email='').values_list('email', flat=True)
    )
    if not recipient_list:
        return

    override_message = config.get('message')
    template = NotificationTemplate.objects.filter(key='lead_manager_alert', is_active=True).first()
    if not template and not override_message:
        return

    default_subject, default_body = render_template('lead_manager_alert', {
        'lead_name': lead.full_name, 'lead_contact': lead.phone or lead.email,
    })
    body = override_message or default_body
    for recipient in recipient_list:
        send_branded_email(recipient, default_subject, body)


def _move_stage(lead, config):
    stage_id = config.get('stage_id')
    if not stage_id:
        return
    lead.stage_id = stage_id
    lead.save(update_fields=['stage'])


def _add_tag(lead, config):
    tag = config.get('tag')
    if not tag:
        return
    tags = lead.tags or []
    if tag not in tags:
        lead.tags = [*tags, tag]
        lead.save(update_fields=['tags'])


_ACTIONS = {
    'assign_counsellor': _assign_counsellor,
    'send_welcome_email': _send_welcome_email,
    'send_whatsapp': _send_whatsapp,
    'schedule_follow_up': _schedule_follow_up,
    'notify_manager': _notify_manager,
    'move_stage': _move_stage,
    'add_tag': _add_tag,
}
