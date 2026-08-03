import uuid

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework_simplejwt.tokens import RefreshToken

# Stateless and keyed off (pk, password hash, last_login, email), so a single
# generator instance is safe to reuse across Student and AdminMember — the
# uid is always resolved against a specific model by the endpoint it was
# issued for (see apps/authentication/views.py).
password_reset_token_generator = PasswordResetTokenGenerator()


def _register_student_device(student, session_id, request=None):
    """Creates the StudentDevice row backing this login's session_id, then
    evicts the oldest devices beyond SiteSettings.max_concurrent_devices —
    the Hotstar-style concurrent-login cap. Deleting a device row is what
    actually signs it out: StudentJWTAuthentication rejects any token whose
    session_id no longer has a matching row."""
    from settings_app.models import SiteSettings
    from students.models import StudentDevice

    device_label = ''
    if request is not None:
        device_label = request.META.get('HTTP_USER_AGENT', '')[:255]

    StudentDevice.objects.create(student=student, session_id=session_id, device_label=device_label)

    max_devices = SiteSettings.get_solo().max_concurrent_devices
    device_ids = list(
        StudentDevice.objects.filter(student=student).order_by('created_at').values_list('id', flat=True)
    )
    if len(device_ids) > max_devices:
        StudentDevice.objects.filter(id__in=device_ids[:len(device_ids) - max_devices]).delete()


def get_tokens_for_student(student, request=None):
    session_id = uuid.uuid4().hex
    refresh = RefreshToken.for_user(student)
    refresh['user_type'] = 'student'
    refresh['email'] = student.email
    refresh['session_id'] = session_id
    _register_student_device(student, session_id, request)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def get_tokens_for_admin_member(member):
    from django.utils import timezone

    refresh = RefreshToken.for_user(member)
    refresh['user_type'] = 'admin_member'
    refresh['email'] = member.email
    refresh['role'] = member.role.slug if member.role else None
    # Preserved verbatim across ROTATE_REFRESH_TOKENS rotations (rotation
    # only touches jti/exp/iat, never other payload claims) — lets the
    # refresh endpoint enforce Security Settings' session_timeout as the
    # *total* session length, independent of how often the access token
    # gets refreshed. See _TypedTokenRefreshSerializer.
    refresh['session_started_at'] = int(timezone.now().timestamp())
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def build_password_reset_link(user, frontend_path):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token_generator.make_token(user)
    return f'{settings.FRONTEND_URL}{frontend_path}?uid={uid}&token={token}'


def send_password_reset_email(user, frontend_path):
    from settings_app.notifications import send_notification

    link = build_password_reset_link(user, frontend_path)
    send_notification('password_reset', email=user.email, context={'link': link})


def verify_google_id_token(token):
    """Returns the decoded payload dict. Raises ValueError if the token is
    invalid, expired, or was not issued for our GOOGLE_OAUTH_CLIENT_ID."""
    return google_id_token.verify_oauth2_token(
        token, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID
    )
