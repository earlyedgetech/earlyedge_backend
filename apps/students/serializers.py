from certificates.models import Certificate
from challenges.models import ChallengeSubmission
from django.db import transaction
from leads.models import Lead, LeadActivity, PipelineStage
from purchases.serializers import PurchaseSerializer
from rest_framework import serializers

from .models import Student


class StudentMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            'id', 'email', 'full_name', 'phone', 'city', 'state', 'country',
            'is_verified', 'auth_provider', 'created_at',
        ]


class StudentMeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['full_name', 'phone', 'city', 'state', 'country']


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            'id', 'email', 'full_name', 'phone', 'city', 'state', 'country', 'is_active', 'is_verified',
            'auth_provider', 'source', 'converted_from_lead', 'last_login', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'auth_provider', 'source', 'converted_from_lead', 'last_login', 'created_at', 'updated_at',
        ]


class StudentCreateSerializer(serializers.ModelSerializer):
    """Dashboard-only counterpart to student self-signup — an admin adds a
    student record directly, either freehand ('manual') or by converting an
    existing Lead ('lead', via lead_id). Website signups never go through
    this path; they stay source='website' from Student's model default."""

    lead_id = serializers.PrimaryKeyRelatedField(
        source='converted_from_lead', queryset=Lead.objects.all(), required=False, allow_null=True,
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Student
        fields = [
            'id', 'full_name', 'email', 'phone', 'city', 'state', 'country',
            'source', 'lead_id', 'password', 'is_verified',
        ]
        read_only_fields = ['id']

    def validate_email(self, value):
        value = value.lower()
        if Student.objects.filter(email=value).exists():
            raise serializers.ValidationError('A student with this email already exists.')
        return value

    def validate(self, attrs):
        if attrs.get('source') == 'lead' and not attrs.get('converted_from_lead'):
            raise serializers.ValidationError({'lead_id': 'Required when source is "lead".'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lead = validated_data.pop('converted_from_lead', None)
        password = validated_data.pop('password', None) or None
        email = validated_data.pop('email')
        if lead:
            validated_data['source'] = 'lead'

        student = Student.objects.create_user(email=email, password=password, **validated_data)

        if lead:
            student.converted_from_lead = lead
            student.save(update_fields=['converted_from_lead'])

            won_stage = PipelineStage.objects.filter(is_won=True).order_by('order').first()
            if won_stage and lead.stage_id != won_stage.id:
                lead.stage = won_stage
                lead.save(update_fields=['stage'])
            LeadActivity.objects.create(
                lead=lead, activity_type='automation',
                description=f'Converted to student ({student.email}).',
            )

        return student


class StudentCertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Certificate
        fields = ['id', 'course_title', 'certificate_code', 'status', 'pdf_url', 'issued_at']
        read_only_fields = fields


class StudentChallengeSubmissionSerializer(serializers.ModelSerializer):
    challenge_title = serializers.CharField(source='challenge.title', read_only=True)

    class Meta:
        model = ChallengeSubmission
        fields = ['id', 'challenge_title', 'score', 'status', 'created_at']
        read_only_fields = fields


class StudentDetailSerializer(StudentSerializer):
    """Adds nested related data for the Single Student Page — the plain list
    view intentionally stays flat (no nested prefetch cost), see
    StudentSerializer."""

    purchases = PurchaseSerializer(many=True, read_only=True)
    certificates = StudentCertificateSerializer(many=True, read_only=True)
    challenge_submissions = StudentChallengeSubmissionSerializer(many=True, read_only=True)

    class Meta(StudentSerializer.Meta):
        fields = StudentSerializer.Meta.fields + ['purchases', 'certificates', 'challenge_submissions']
