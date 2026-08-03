from admin_security.models import AdminMember
from admin_security.serializers import AdminMemberSerializer
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from students.models import Student
from students.serializers import StudentMeSerializer, StudentMeUpdateSerializer

from rest_framework_simplejwt.views import TokenViewBase

from .authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from .permissions import HasDashboardPermission, IsAdminMember, IsStudent
from .serializers import (
    AdminMemberChangePasswordSerializer,
    AdminMemberForgotPasswordSerializer,
    AdminMemberGoogleLoginSerializer,
    AdminMemberLoginSerializer,
    AdminMemberRegisterSerializer,
    AdminMemberResetPasswordSerializer,
    AdminMemberTokenRefreshSerializer,
    StudentChangePasswordSerializer,
    StudentForgotPasswordSerializer,
    StudentGoogleLoginSerializer,
    StudentLoginSerializer,
    StudentRegisterSerializer,
    StudentResetPasswordSerializer,
    StudentTokenRefreshSerializer,
)
from .utils import (
    get_tokens_for_admin_member,
    get_tokens_for_student,
    send_password_reset_email,
    verify_google_id_token,
)

GENERIC_RESET_MESSAGE = (
    'If an account exists with that email, a password reset link has been sent.'
)


# ---------------------------------------------------------------------------
# Student (website)
# ---------------------------------------------------------------------------

class StudentRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from settings_app.notifications import send_notification

        serializer = StudentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.save()
        send_notification('student_welcome', email=student.email, context={'student_name': student.full_name})
        tokens = get_tokens_for_student(student, request)
        return Response(tokens, status=status.HTTP_201_CREATED)


class StudentLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StudentLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = serializer.validated_data['student']
        student.last_login = timezone.now()
        student.save(update_fields=['last_login'])
        tokens = get_tokens_for_student(student, request)
        return Response(tokens, status=status.HTTP_200_OK)


class StudentGoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from settings_app.notifications import send_notification

        serializer = StudentGoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = verify_google_id_token(serializer.validated_data['id_token'])
        except ValueError:
            return Response({'detail': 'Invalid Google token.'}, status=status.HTTP_400_BAD_REQUEST)

        email = payload.get('email')
        if not email or not payload.get('email_verified'):
            return Response(
                {'detail': 'Google account email is not verified.'}, status=status.HTTP_400_BAD_REQUEST
            )

        student, created = Student.objects.get_or_create(
            email=email,
            defaults={
                'full_name': payload.get('name', ''),
                'auth_provider': 'google',
                'google_id': payload['sub'],
                'is_verified': True,
            },
        )
        if not created and student.google_id != payload['sub']:
            student.google_id = payload['sub']
            student.auth_provider = 'google'
            student.save(update_fields=['google_id', 'auth_provider'])

        if created:
            send_notification('student_welcome', email=student.email, context={'student_name': student.full_name})

        student.last_login = timezone.now()
        student.save(update_fields=['last_login'])
        tokens = get_tokens_for_student(student, request)
        return Response(tokens, status=status.HTTP_200_OK)


class StudentForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StudentForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student = Student.objects.filter(email=serializer.validated_data['email'].lower()).first()
        if student:
            send_password_reset_email(student, frontend_path='/reset-password')

        return Response({'detail': GENERIC_RESET_MESSAGE}, status=status.HTTP_200_OK)


class StudentResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StudentResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        student = serializer.validated_data['student']
        student.set_password(serializer.validated_data['new_password'])
        student.save(update_fields=['password'])
        return Response({'detail': 'Password has been reset.'}, status=status.HTTP_200_OK)


class StudentMeView(APIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]

    def get(self, request):
        return Response(StudentMeSerializer(request.user).data)

    def patch(self, request):
        serializer = StudentMeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(StudentMeSerializer(request.user).data)


class StudentChangePasswordView(APIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]

    def post(self, request):
        serializer = StudentChangePasswordSerializer(
            data=request.data, context={'student': request.user}
        )
        serializer.is_valid(raise_exception=True)

        student = request.user
        student.set_password(serializer.validated_data['new_password'])
        student.save(update_fields=['password'])
        return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)


class StudentTokenRefreshView(TokenViewBase):
    permission_classes = [AllowAny]
    serializer_class = StudentTokenRefreshSerializer


# ---------------------------------------------------------------------------
# Admin / dashboard member (RBAC)
# ---------------------------------------------------------------------------

class AdminMemberRegisterView(APIView):
    """Dashboard members are provisioned by an existing admin with the
    'manage_members' permission — there is no public self-registration for
    the dashboard side."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_members')]

    def post(self, request):
        serializer = AdminMemberRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.save()
        tokens = get_tokens_for_admin_member(member)
        return Response(tokens, status=status.HTTP_201_CREATED)


class AdminMemberLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminMemberLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.validated_data['member']
        member.last_login = timezone.now()
        member.save(update_fields=['last_login'])
        tokens = get_tokens_for_admin_member(member)
        return Response(tokens, status=status.HTTP_200_OK)


class AdminMemberGoogleLoginView(APIView):
    """Logs in an *existing* dashboard member via Google — does not create
    new admin accounts, since dashboard access must be explicitly granted
    with a role."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminMemberGoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = verify_google_id_token(serializer.validated_data['id_token'])
        except ValueError:
            return Response({'detail': 'Invalid Google token.'}, status=status.HTTP_400_BAD_REQUEST)

        email = payload.get('email')
        if not email or not payload.get('email_verified'):
            return Response(
                {'detail': 'Google account email is not verified.'}, status=status.HTTP_400_BAD_REQUEST
            )

        member = AdminMember.objects.select_related('role').filter(email=email).first()
        if not member:
            return Response(
                {'detail': 'No dashboard account exists for this Google account.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not member.is_active:
            return Response({'detail': 'This account has been deactivated.'}, status=status.HTTP_403_FORBIDDEN)

        if member.google_id != payload['sub']:
            member.google_id = payload['sub']
            member.save(update_fields=['google_id'])

        member.last_login = timezone.now()
        member.save(update_fields=['last_login'])
        tokens = get_tokens_for_admin_member(member)
        return Response(tokens, status=status.HTTP_200_OK)


class AdminMemberForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminMemberForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member = AdminMember.objects.filter(email=serializer.validated_data['email'].lower()).first()
        if member:
            send_password_reset_email(member, frontend_path='/-/reset-password')

        return Response({'detail': GENERIC_RESET_MESSAGE}, status=status.HTTP_200_OK)


class AdminMemberResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminMemberResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member = serializer.validated_data['member']
        member.set_password(serializer.validated_data['new_password'])
        member.save(update_fields=['password'])
        return Response({'detail': 'Password has been reset.'}, status=status.HTTP_200_OK)


class AdminMemberChangePasswordView(APIView):
    """Authenticated password change — used for the mandatory first-login
    reset flow (member logged in with an admin-issued dummy password) as
    well as any voluntary password change from within the dashboard."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    def post(self, request):
        serializer = AdminMemberChangePasswordSerializer(
            data=request.data, context={'member': request.user}
        )
        serializer.is_valid(raise_exception=True)

        member = request.user
        member.set_password(serializer.validated_data['new_password'])
        member.must_reset_password = False
        member.save(update_fields=['password', 'must_reset_password'])
        return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)


class AdminMemberMeView(APIView):
    """Returns the logged-in dashboard member's profile, role, and resolved
    permission codenames — the frontend uses this to decide which dashboard
    sections/routes to render."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    def get(self, request):
        member = AdminMember.objects.select_related('role').get(pk=request.user.pk)
        return Response(AdminMemberSerializer(member).data)


class AdminMemberTokenRefreshView(TokenViewBase):
    permission_classes = [AllowAny]
    serializer_class = AdminMemberTokenRefreshSerializer
