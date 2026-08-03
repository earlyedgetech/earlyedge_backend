from datetime import datetime, timezone as dt_timezone

from admin_security.models import AdminMember
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings
from students.models import Student


class StudentJWTAuthentication(JWTAuthentication):
    """Only accepts tokens issued to a Student (see utils.get_tokens_for_student).
    Keeping this separate from AdminMemberJWTAuthentication means a student's
    token can never be used to access dashboard/RBAC endpoints and vice versa.
    """

    def get_user(self, validated_token):
        if validated_token.get('user_type') != 'student':
            raise AuthenticationFailed('Invalid token type for this endpoint.')

        user_id = validated_token[api_settings.USER_ID_CLAIM]
        try:
            student = Student.objects.get(id=user_id)
        except Student.DoesNotExist:
            raise AuthenticationFailed('Student not found.')

        if not student.is_active:
            raise AuthenticationFailed('Student account is inactive.')

        # session_id is absent on tokens issued before the device-limit
        # feature shipped — treat those as still valid rather than mass
        # logging out everyone already signed in.
        session_id = validated_token.get('session_id')
        if session_id and not student.devices.filter(session_id=session_id).exists():
            raise AuthenticationFailed(
                "You've been signed out because you logged in on another device "
                "and reached this account's device limit."
            )

        return student


class AdminMemberJWTAuthentication(JWTAuthentication):
    """Only accepts tokens issued to an AdminMember (see utils.get_tokens_for_admin_member)."""

    def get_user(self, validated_token):
        if validated_token.get('user_type') != 'admin_member':
            raise AuthenticationFailed('Invalid token type for this endpoint.')

        user_id = validated_token[api_settings.USER_ID_CLAIM]
        try:
            member = AdminMember.objects.select_related('role').get(id=user_id)
        except AdminMember.DoesNotExist:
            raise AuthenticationFailed('Admin member not found.')

        if not member.is_active:
            raise AuthenticationFailed('Admin member account is inactive.')

        if member.force_logout_at:
            issued_at = datetime.fromtimestamp(validated_token['iat'], tz=dt_timezone.utc)
            if issued_at < member.force_logout_at:
                raise AuthenticationFailed('Your session was ended by an administrator. Please log in again.')

        return member
