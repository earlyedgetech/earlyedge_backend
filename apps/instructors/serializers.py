import uuid

from admin_security.models import AdminMember, Role
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Instructor, InstructorPayout, InstructorReview


def generate_instructor_code():
    code = f'INS-{uuid.uuid4().hex[:8].upper()}'
    while Instructor.objects.filter(instructor_code=code).exists():
        code = f'INS-{uuid.uuid4().hex[:8].upper()}'
    return code


class InstructorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='member.full_name', read_only=True)
    email = serializers.EmailField(source='member.email', read_only=True)
    account_status_display = serializers.CharField(source='get_account_status_display', read_only=True)
    course_count = serializers.ReadOnlyField()
    enrolled_students = serializers.ReadOnlyField()

    class Meta:
        model = Instructor
        fields = [
            'id', 'instructor_code', 'full_name', 'email', 'bio', 'qualification',
            'specialization', 'experience_years', 'languages_spoken', 'phone',
            'profile_picture_url', 'gender', 'dob', 'address', 'city', 'state',
            'country', 'pincode', 'account_status', 'account_status_display',
            'admin_verified', 'rating_avg', 'total_ratings', 'course_count',
            'enrolled_students', 'portfolio_url', 'video_intro_url', 'payout_method',
            'payout_details', 'commission_rate', 'timezone', 'availability_schedule',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'rating_avg', 'total_ratings', 'created_at', 'updated_at']


class InstructorPublicSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='member.full_name', read_only=True)

    class Meta:
        model = Instructor
        fields = [
            'id', 'full_name', 'bio', 'qualification', 'specialization',
            'experience_years', 'profile_picture_url', 'rating_avg', 'total_ratings',
            'course_count', 'portfolio_url', 'video_intro_url',
        ]


class InstructorCreateSerializer(serializers.ModelSerializer):
    """Provisions the dashboard login (AdminMember, role=instructor) and the
    Instructor profile together — an admin fills out one form to onboard an
    instructor, there is no separate 'create login, then create profile' step."""

    full_name = serializers.CharField(write_only=True, max_length=255)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Instructor
        fields = [
            'full_name', 'email', 'password', 'instructor_code', 'bio', 'qualification',
            'specialization', 'experience_years', 'languages_spoken', 'phone',
            'profile_picture_url', 'gender', 'dob', 'address', 'city', 'state',
            'country', 'pincode', 'portfolio_url', 'video_intro_url', 'payout_method',
            'payout_details', 'commission_rate', 'timezone', 'availability_schedule',
        ]

    def validate_email(self, value):
        value = value.lower()
        if AdminMember.objects.filter(email=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_instructor_code(self, value):
        if Instructor.objects.filter(instructor_code=value).exists():
            raise serializers.ValidationError('This instructor code is already in use.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        full_name = validated_data.pop('full_name')
        email = validated_data.pop('email')
        password = validated_data.pop('password')

        role, _ = Role.objects.get_or_create(slug='instructor', defaults={'name': 'Instructor'})
        member = AdminMember.objects.create_user(
            email=email, password=password, full_name=full_name, role=role,
            must_reset_password=True,
        )
        return Instructor.objects.create(member=member, **validated_data)


class InstructorApplicationSerializer(serializers.ModelSerializer):
    """Public, self-serve counterpart to InstructorCreateSerializer — an
    applicant (not an admin) fills this in from the shareable application
    page. The resulting login is provisioned inactive/pending: they cannot
    sign in until an admin reviews and verifies the application (see
    InstructorDetailView.perform_update)."""

    full_name = serializers.CharField(write_only=True, max_length=255)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Instructor
        fields = [
            'full_name', 'email', 'password', 'bio', 'qualification',
            'specialization', 'experience_years', 'languages_spoken', 'phone',
            'profile_picture_url', 'gender', 'dob', 'address', 'city', 'state',
            'country', 'pincode', 'portfolio_url', 'video_intro_url', 'timezone',
            'availability_schedule',
        ]

    def validate_email(self, value):
        value = value.lower()
        if AdminMember.objects.filter(email=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        full_name = validated_data.pop('full_name')
        email = validated_data.pop('email')
        password = validated_data.pop('password')

        role, _ = Role.objects.get_or_create(slug='instructor', defaults={'name': 'Instructor'})
        member = AdminMember.objects.create_user(
            email=email, password=password, full_name=full_name, role=role,
            must_reset_password=False, is_active=False,
        )
        instructor = Instructor.objects.create(
            member=member, instructor_code=generate_instructor_code(),
            account_status='pending_verification', admin_verified=False,
            **validated_data,
        )

        from admin_security.notifications import notify_admins_with_permission
        from settings_app.notifications import send_notification

        send_notification('instructor_application_received', email=member.email, context={
            'full_name': member.full_name,
        })
        notify_admins_with_permission(
            'manage_instructors', f'New instructor application: {member.full_name}',
            link='/-/admin-dashboard/instructor_management/all_instructors',
        )

        return instructor


class InstructorReviewSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.member.full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True, default=None)

    class Meta:
        model = InstructorReview
        fields = [
            'id', 'instructor', 'instructor_name', 'student', 'course', 'course_title',
            'user_name', 'email', 'rating', 'comment', 'is_approved', 'created_at',
        ]
        read_only_fields = ['id', 'instructor_name', 'course_title', 'created_at']


class InstructorReviewCreateSerializer(serializers.ModelSerializer):
    """`instructor` comes from the URL (see InstructorReviewPublicCreateView),
    not the request body."""

    class Meta:
        model = InstructorReview
        fields = ['course', 'user_name', 'email', 'rating', 'comment']


class InstructorReviewPublicSerializer(serializers.ModelSerializer):
    """Approved instructor reviews shown on the public instructor profile
    page — no email/student id."""

    class Meta:
        model = InstructorReview
        fields = ['id', 'user_name', 'rating', 'comment', 'created_at']


class InstructorPayoutSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True, default=None)

    class Meta:
        model = InstructorPayout
        fields = ['id', 'instructor', 'amount', 'note', 'recorded_by', 'recorded_by_name', 'created_at']
        read_only_fields = ['id', 'instructor', 'recorded_by', 'recorded_by_name', 'created_at']
