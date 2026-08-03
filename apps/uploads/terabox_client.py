"""Terabox upload client.

IMPORTANT — read before touching this file: Terabox has no publicly
published, stable developer API. Their "Open Platform" integration docs
(https://www.terabox.com/integrations/docs) describe the shape of the flow
(precreate -> chunked upload -> create/merge) but require contacting Terabox
directly to get `access_token`/`app_id` credentials, and community tooling
that talks to Terabox does so by mimicking their web client's internal API
(the same family as Baidu's PCS API) using a logged-in session's `ndus`
cookie / `jsToken` rather than a documented OAuth flow. The endpoint paths
and payload shapes below follow that community-documented convention as
closely as possible, but they are **not guaranteed correct** — verify them
against a real account (browser devtools network tab while uploading a file
on terabox.com, or Terabox support once Open Platform access is granted)
before relying on this in production.

Until real credentials are configured in Settings -> Integrations, every
call in this module returns through `_mock_result`, so the rest of the
upload pipeline (progress tracking, DB records, course/materials wiring) is
fully exercisable without a live Terabox account.
"""

import hashlib
import math

import requests
from django.conf import settings as django_settings

API_BASE_URL = 'https://www.terabox.com/api'
UPLOAD_BASE_URL = 'https://c-jp.terabox.com/rest/2.0/pcs/superfile2'
DEFAULT_APP_ID = '250528'


class TeraboxError(Exception):
    pass


class TeraboxNotConfigured(TeraboxError):
    """Raised when no access token has been set in Settings -> Integrations."""


def _site_settings():
    from settings_app.models import SiteSettings
    return SiteSettings.get_solo()


def _is_configured(site_settings):
    return bool(site_settings.terabox_enabled and site_settings.terabox_access_token)


def _mock_mode():
    return getattr(django_settings, 'TERABOX_FORCE_MOCK', False)


class TeraboxClient:
    """Thin wrapper around the precreate -> chunk upload -> create flow.

    Usage mirrors the three REST calls a real integration needs:
        client = TeraboxClient()
        precreate = client.precreate(path, size, block_md5_list)
        client.upload_chunk(path, precreate['uploadid'], index, chunk_bytes)
        result = client.create(path, size, precreate['uploadid'], block_md5_list)
    """

    def __init__(self):
        self.settings = _site_settings()
        self.configured = _is_configured(self.settings)
        self.mock = _mock_mode() or not self.configured

    def _auth_params(self):
        return {
            'access_token': self.settings.terabox_access_token,
            'app_id': self.settings.terabox_app_id or DEFAULT_APP_ID,
        }

    def _remote_path(self, filename):
        root = (self.settings.terabox_root_path or '/EarlyEdgeTech').rstrip('/')
        return f'{root}/{filename}'

    def precreate(self, filename, size, block_md5_list):
        path = self._remote_path(filename)
        if self.mock:
            return {'path': path, 'uploadid': f'mock-{hashlib.md5(path.encode()).hexdigest()}'}

        response = requests.post(
            f'{API_BASE_URL}/precreate',
            params=self._auth_params(),
            data={
                'path': path,
                'size': size,
                'isdir': 0,
                'autoinit': 1,
                'block_list': block_md5_list,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get('errno'):
            raise TeraboxError(f"Terabox precreate failed: {data}")
        return {'path': path, 'uploadid': data['uploadid']}

    def upload_chunk(self, path, uploadid, part_index, chunk_bytes):
        if self.mock:
            return {'md5': hashlib.md5(chunk_bytes).hexdigest()}

        response = requests.post(
            UPLOAD_BASE_URL,
            params={
                **self._auth_params(),
                'method': 'upload',
                'path': path,
                'uploadid': uploadid,
                'partseq': part_index,
            },
            files={'file': ('blob', chunk_bytes)},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        if data.get('error_code'):
            raise TeraboxError(f"Terabox chunk upload failed: {data}")
        return {'md5': data.get('md5', hashlib.md5(chunk_bytes).hexdigest())}

    def create(self, filename, path, size, uploadid, block_md5_list):
        if self.mock:
            return {
                'path': path,
                'fs_id': f'mock-fsid-{hashlib.md5(path.encode()).hexdigest()[:12]}',
                'url': f'https://mock.terabox.local/share/{hashlib.md5(path.encode()).hexdigest()}/{filename}',
            }

        response = requests.post(
            f'{API_BASE_URL}/create',
            params=self._auth_params(),
            data={
                'path': path,
                'size': size,
                'uploadid': uploadid,
                'block_list': block_md5_list,
                'isdir': 0,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get('errno'):
            raise TeraboxError(f"Terabox create failed: {data}")

        share_url = self._generate_share_link(data.get('fs_id'))
        return {'path': path, 'fs_id': data.get('fs_id'), 'url': share_url}

    def _generate_share_link(self, fs_id):
        response = requests.post(
            f'{API_BASE_URL}/share/set',
            params=self._auth_params(),
            data={'fid_list': f'[{fs_id}]', 'schannel': 4, 'channel_list': '[]'},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get('errno'):
            raise TeraboxError(f"Terabox share-link generation failed: {data}")
        return data.get('link', '')


def chunk_count(total_size, chunk_size):
    return max(1, math.ceil(total_size / chunk_size))
