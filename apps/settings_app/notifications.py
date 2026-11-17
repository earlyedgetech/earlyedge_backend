"""Shared notification rendering + sending — the "template used for
branding" system. One NotificationTemplate row per real code call-site;
`send_notification()` is the single place that knows how to dispatch a
rendered template by channel (email vs. whatsapp)."""

from django.conf import settings as django_settings
from django.core.mail import EmailMultiAlternatives

from .models import NotificationTemplate, SiteSettings
from django.conf import settings
# Fallback content used only if a template row is somehow missing (the seed
# migration always creates all 8 — this is defensive, not the normal path).
_FALLBACK_SUBJECTS = {
    'password_reset': 'Reset your password',
}
_FALLBACK_BODY = 'Hi {name},\n\nThanks for being part of {site_name}.\n\n— {site_name}'


def render_template(key, context):
    """Returns (subject, body) with {variable} placeholders filled from
    context. Missing variables in context are left as literal text rather
    than raising, so a template referencing an unavailable variable degrades
    gracefully instead of crashing the send."""

    template = NotificationTemplate.objects.filter(key=key).first()
    site_settings = SiteSettings.get_solo()
    safe_context = {'site_name': site_settings.site_name, **context}

    if not template:
        subject = _FALLBACK_SUBJECTS.get(key, site_settings.site_name)
        body = _FALLBACK_BODY
    else:
        subject, body = template.subject, template.body

    subject = _safe_format(subject, safe_context)
    body = _safe_format(body, safe_context)
    return subject, body


def _safe_format(text, context):
    class _DefaultDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'

    return text.format_map(_DefaultDict(context))


def send_branded_email(to_email, subject, body_text):
    """Wraps body_text in a simple branded HTML shell (logo/name/primary
    color/contact email from SiteSettings) and sends plain-text + HTML."""

    site_settings = SiteSettings.get_solo()
    color = site_settings.primary_color or '#004030'
    logo_html = (
        f'<img src="{site_settings.site_logo_url}" alt="{site_settings.site_name}" '
        f'style="height:36px;margin-bottom:12px;" />'
        if site_settings.site_logo_url else ''
    )
    body_html = body_text.replace('\n', '<br/>')
    html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:{color};padding:20px 24px;border-radius:8px 8px 0 0;">
        {logo_html}
        <span style="color:#fff;font-size:18px;font-weight:bold;">{site_settings.site_name}</span>
      </div>
      <div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;color:#1f2937;font-size:14px;line-height:1.6;">
        {body_html}
      </div>
      <p style="color:#9ca3af;font-size:11px;margin-top:16px;">
        {site_settings.site_name}{' · ' + site_settings.contact_email if site_settings.contact_email else ''}
      </p>
    </div>
    """

    from_email = (
        f'{site_settings.email_from_name} <{site_settings.email_from_address}>'
        if site_settings.email_from_name and site_settings.email_from_address
        else django_settings.DEFAULT_FROM_EMAIL
    )

    email = EmailMultiAlternatives(subject=subject, body=body_text, from_email=from_email, to=[to_email])
    email.attach_alternative(html, 'text/html')

    print("EMAIL_BACKEND:", settings.EMAIL_BACKEND)
    print("EMAIL_HOST:", settings.EMAIL_HOST)
    print("EMAIL_PORT:", settings.EMAIL_PORT)
    print("EMAIL_HOST_USER:", settings.EMAIL_HOST_USER)
    print("EMAIL_USE_TLS:", settings.EMAIL_USE_TLS)
    print("FROM_EMAIL:", from_email)
    email.send()


def send_notification(key, *, email=None, phone=None, context=None):
    """Looks up the active template for `key` and dispatches by its channel.
    No-ops quietly if the template is inactive/missing or the required
    recipient field for its channel wasn't supplied — callers don't need to
    branch on configuration, just pass what they have."""

    context = context or {}
    template = NotificationTemplate.objects.filter(key=key, is_active=True).first()
    if not template:
        return False

    subject, body = render_template(key, context)

    if template.channel == 'email':
        if not email:
            return False
        send_branded_email(email, subject, body)
        return True

    if template.channel == 'whatsapp':
        if not phone:
            return False
        from common.integrations.whatsapp_client import WhatsAppClient

        text_params = [line for line in body.split('\n') if line.strip()]
        WhatsAppClient().send_template_message(phone, *text_params)
        return True

    return False
