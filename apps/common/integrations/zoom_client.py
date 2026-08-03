"""Zoom meeting-link generation.

Uses Zoom's official Server-to-Server OAuth app flow (documented, stable
API — unlike Terabox): exchange Account ID + Client ID/Secret for an access
token, then create a scheduled meeting. Credentials live in
SiteSettings (Settings -> Integrations). Until `zoom_enabled` is on and
credentials are filled in, `create_meeting` returns a mock join_url so the
rest of the scheduling pipeline (sessions, reminders) is fully exercisable
without a live Zoom account.

Shared across any app that needs a real meeting link (live_classes sessions,
leads counselling sessions, ...).
"""

import base64
import uuid

import requests
from django.conf import settings as django_settings

OAUTH_TOKEN_URL = 'https://zoom.us/oauth/token'
API_BASE_URL = 'https://api.zoom.us/v2'


class ZoomError(Exception):
    pass


def _site_settings():
    from settings_app.models import SiteSettings
    return SiteSettings.get_solo()


def _mock_mode():
    return getattr(django_settings, 'ZOOM_FORCE_MOCK', False)


class ZoomClient:
    def __init__(self):
        self.settings = _site_settings()
        self.configured = bool(
            self.settings.zoom_enabled
            and self.settings.zoom_account_id
            and self.settings.zoom_client_id
            and self.settings.zoom_client_secret
        )
        self.mock = _mock_mode() or not self.configured

    def _get_access_token(self):
        basic = base64.b64encode(
            f'{self.settings.zoom_client_id}:{self.settings.zoom_client_secret}'.encode()
        ).decode()
        response = requests.post(
            OAUTH_TOKEN_URL,
            params={'grant_type': 'account_credentials', 'account_id': self.settings.zoom_account_id},
            headers={'Authorization': f'Basic {basic}'},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()['access_token']

    def create_meeting(self, topic, start_time, duration_minutes):
        """`start_time` must be a timezone-aware datetime. Returns
        {id, join_url}."""

        if self.mock:
            fake_id = uuid.uuid4().hex[:11]
            return {'id': fake_id, 'join_url': f'https://mock.zoom.local/j/{fake_id}'}

        token = self._get_access_token()
        response = requests.post(
            f'{API_BASE_URL}/users/me/meetings',
            headers={'Authorization': f'Bearer {token}'},
            json={
                'topic': topic,
                'type': 2,
                'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'duration': duration_minutes,
                'timezone': 'UTC',
                'settings': {'join_before_host': True, 'waiting_room': False},
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise ZoomError(f'Zoom meeting creation failed: {response.status_code} {response.text}')
        data = response.json()
        return {'id': str(data['id']), 'join_url': data['join_url']}
