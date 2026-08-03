"""WhatsApp messaging via Meta's WhatsApp Cloud API (official, documented).

IMPORTANT: Meta requires any message sent outside a 24-hour
customer-initiated window to use a pre-approved message *template* — a
free-form text message will simply fail to deliver. The template named in
`SiteSettings.whatsapp_template_name` must already exist and be approved in
Meta Business Manager; that approval step can't be automated from here.

Until `whatsapp_enabled` is on and credentials + a template name are filled
in (Settings -> Integrations), `send_template_message` runs in mock mode —
it logs what would have been sent and returns success, so any scheduled task
built on top of this is fully exercisable without a live WhatsApp Business
account.

Shared across any app that needs to send a WhatsApp message (live_classes
reminders, leads follow-up automations, ...).
"""

import logging

import requests
from django.conf import settings as django_settings

API_BASE_URL = 'https://graph.facebook.com/v19.0'
logger = logging.getLogger(__name__)


class WhatsAppError(Exception):
    pass


def _site_settings():
    from settings_app.models import SiteSettings
    return SiteSettings.get_solo()


def _mock_mode():
    return getattr(django_settings, 'WHATSAPP_FORCE_MOCK', False)


class WhatsAppClient:
    def __init__(self):
        self.settings = _site_settings()
        self.configured = bool(
            self.settings.whatsapp_enabled
            and self.settings.whatsapp_access_token
            and self.settings.whatsapp_phone_number_id
            and self.settings.whatsapp_template_name
        )
        self.mock = _mock_mode() or not self.configured

    def send_template_message(self, to_phone, *text_params):
        """`to_phone` should be in E.164 format (e.g. +15551234567).
        `text_params` fill the approved template's body placeholders in
        order (e.g. session title + join link, or a lead's name + message)."""

        if self.mock:
            logger.info(
                'WhatsApp mock send to %s: template params=%s',
                to_phone, text_params,
            )
            return {'mock': True}

        response = requests.post(
            f'{API_BASE_URL}/{self.settings.whatsapp_phone_number_id}/messages',
            headers={'Authorization': f'Bearer {self.settings.whatsapp_access_token}'},
            json={
                'messaging_product': 'whatsapp',
                'to': to_phone,
                'type': 'template',
                'template': {
                    'name': self.settings.whatsapp_template_name,
                    'language': {'code': 'en'},
                    'components': [
                        {
                            'type': 'body',
                            'parameters': [{'type': 'text', 'text': str(p)} for p in text_params],
                        },
                    ],
                },
            },
            timeout=15,
        )
        if response.status_code >= 400:
            raise WhatsAppError(f'WhatsApp send failed: {response.status_code} {response.text}')
        return response.json()
