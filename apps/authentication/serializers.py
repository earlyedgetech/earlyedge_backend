from datetime import datetime, timezone as dt_timezone

from admin_security.models import AdminMember, Role
from django.contrib.auth.password_validation import validate_password
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from students.models import Student

from .utils import password_reset_token_generator


class _TypedTokenRefreshSerializer(serializers.Serializer):
    """Base for a refresh endpoint scoped to one user model/user_type claim.

    The default `TokenRefreshSerializer` looks the user up via
    `get_user_model()`, which resolves to Django's built-in `auth.User` —
    not `AdminMember` or `Student` — since this project has no
    `AUTH_USER_MODEL`. Subclasses here look the user up against the correct
    model instead, keyed off the `user_type` claim set at issuance (see
    `utils.get_tokens_for_admin_member` / `get_tokens_for_student`).
    """

    refresh = serializers.CharField()
    access = serializers.CharField(read_only=True)

    user_type = None
    user_model = None

    def validate(self, attrs):
        refresh = RefreshToken(attrs['refresh'])

        if refresh.payload.get('user_type') != self.user_type:
            raise AuthenticationFailed('Invalid token type for this endpoint.')

        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        try:
            user = self.user_model.objects.get(pk=user_id)
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed('Account not found.')
        if not user.is_active:
            raise AuthenticationFailed('This account has been deactivated.')

        if self.user_type == 'admin_member':
            self._enforce_admin_session_rules(refresh, user)
        elif self.user_type == 'student':
            self._enforce_student_device_rules(refresh, user)

        data = {'access': str(refresh.access_token)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            data['refresh'] = str(refresh)

        return data

    @staticmethod
    def _enforce_admin_session_rules(refresh, member):
        """Security Settings > Session Timeout, and force-logout — both only
        meaningful for dashboard admins, never students. `session_started_at`
        is set once at login and survives ROTATE_REFRESH_TOKENS rotations
        (see get_tokens_for_admin_member), so this bounds the *whole* login
        session's length, not just one access token's."""
        from admin_security.models import SecuritySettings
        from django.utils import timezone

        if member.force_logout_at:
            issued_at = datetime.fromtimestamp(refresh.payload['iat'], tz=dt_timezone.utc)
            if issued_at < member.force_logout_at:
                raise AuthenticationFailed('Your session was ended by an administrator. Please log in again.')

        session_started_at = refresh.payload.get('session_started_at')
        if session_started_at:
            timeout_seconds = {
                '15_min': 900, '30_min': 1800, '1_hour': 3600, '2_hour': 7200,
            }.get(SecuritySettings.get_solo().session_timeout, 1800)
            started_at = datetime.fromtimestamp(session_started_at, tz=dt_timezone.utc)
            if (timezone.now() - started_at).total_seconds() > timeout_seconds:
                raise AuthenticationFailed('Your session has expired. Please log in again.')

    @staticmethod
    def _enforce_student_device_rules(refresh, student):
        """Mirrors StudentJWTAuthentication's device-limit check so a
        refresh attempt from an evicted device fails immediately instead of
        issuing an access token that would just be rejected on next use."""
        session_id = refresh.payload.get('session_id')
        if session_id and not student.devices.filter(session_id=session_id).exists():
            raise AuthenticationFailed(
                "You've been signed out because you logged in on another device "
                "and reached this account's device limit."
            )


class AdminMemberTokenRefreshSerializer(_TypedTokenRefreshSerializer):
    user_type = 'admin_member'
    user_model = AdminMember


class StudentTokenRefreshSerializer(_TypedTokenRefreshSerializer):
    user_type = 'student'
    user_model = Student


# ---------------------------------------------------------------------------
# Student (website)
# ---------------------------------------------------------------------------

class StudentRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate_email(self, value):
        value = value.lower()
        if Student.objects.filter(email=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        validate_password(attrs['password'])
        return attrs

    def create(self, validated_data):
        return Student.objects.create_user(**validated_data)


class StudentLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower()
        try:
            student = Student.objects.get(email=email)
        except Student.DoesNotExist:
            raise serializers.ValidationError('Invalid email or password.')

        if not student.check_password(attrs['password']):
            raise serializers.ValidationError('Invalid email or password.')
        if not student.is_active:
            raise serializers.ValidationError('This account has been deactivated.')

        attrs['student'] = student
        return attrs


class StudentGoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True)


class StudentChangePasswordSerializer(serializers.Serializer):
    """Authenticated password change from the student's own settings —
    mirrors AdminMemberChangePasswordSerializer's re-confirm-current-password
    approach below."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        student = self.context['student']

        if not student.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': 'Current password is incorrect.'})

        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match.'})

        if attrs['new_password'] == attrs['current_password']:
            raise serializers.ValidationError(
                {'new_password': 'New password must be different from the current password.'}
            )

        validate_password(attrs['new_password'], user=student)
        return attrs


class StudentForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class StudentResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match.'})

        try:
            student_id = force_str(urlsafe_base64_decode(attrs['uid']))
            student = Student.objects.get(pk=student_id)
        except (Student.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError({'uid': 'Invalid reset link.'})

        if not password_reset_token_generator.check_token(student, attrs['token']):
            raise serializers.ValidationError({'token': 'This reset link is invalid or has expired.'})

        validate_password(attrs['new_password'], user=student)
        attrs['student'] = student
        return attrs


# ---------------------------------------------------------------------------
# Admin / dashboard member (RBAC)
# ---------------------------------------------------------------------------

class AdminMemberRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    role = serializers.SlugField(required=False, allow_null=True)

    def validate_email(self, value):
        value = value.lower()
        if AdminMember.objects.filter(email=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_role(self, value):
        try:
            return Role.objects.get(slug=value)
        except Role.DoesNotExist:
            raise serializers.ValidationError('Unknown role.')

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        validate_password(attrs['password'])
        return attrs

    def create(self, validated_data):
        return AdminMember.objects.create_user(must_reset_password=True, **validated_data)


class AdminMemberLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs['email'].lower()
        try:
            member = AdminMember.objects.select_related('role').get(email=email)
        except AdminMember.DoesNotExist:
            raise serializers.ValidationError('Invalid email or password.')

        if not member.check_password(attrs['password']):
            raise serializers.ValidationError('Invalid email or password.')
        if not member.is_active:
            raise serializers.ValidationError('This account has been deactivated.')

        attrs['member'] = member
        return attrs


class AdminMemberGoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True)


class AdminMemberForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class AdminMemberResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match.'})

        try:
            member_id = force_str(urlsafe_base64_decode(attrs['uid']))
            member = AdminMember.objects.get(pk=member_id)
        except (AdminMember.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError({'uid': 'Invalid reset link.'})

        if not password_reset_token_generator.check_token(member, attrs['token']):
            raise serializers.ValidationError({'token': 'This reset link is invalid or has expired.'})

        validate_password(attrs['new_password'], user=member)
        attrs['member'] = member
        return attrs


class AdminMemberChangePasswordSerializer(serializers.Serializer):
    """Used for the mandatory first-login password change — the member is
    already authenticated (JWT from the dummy-password login), so this just
    re-confirms the current password rather than requiring a fresh email
    reset link."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        member = self.context['member']

        if not member.check_password(attrs['current_password']):
            raise serializers.ValidationError({'current_password': 'Current password is incorrect.'})

        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match.'})

        if attrs['new_password'] == attrs['current_password']:
            raise serializers.ValidationError(
                {'new_password': 'New password must be different from the current password.'}
            )

        validate_password(attrs['new_password'], user=member)
        return attrs
