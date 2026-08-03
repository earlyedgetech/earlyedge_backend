from courses.models import Course
from rest_framework import serializers

from .models import Certificate, CertificateTemplate


class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = ['id', 'name', 'category', 'background_image_url', 'is_default', 'created_at']
        read_only_fields = ['id', 'created_at']


class CertificateSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True, default=None)

    class Meta:
        model = Certificate
        fields = [
            'id', 'certificate_code', 'student', 'student_name', 'student_email', 'course', 'course_title',
            'template', 'template_name', 'certificate_type', 'issue_type', 'issued_at', 'pdf_url', 'status',
        ]
        read_only_fields = ['id', 'certificate_code', 'issued_at', 'issue_type']

    def validate(self, attrs):
        student = attrs.get('student') or getattr(self.instance, 'student', None)
        course = attrs.get('course') or getattr(self.instance, 'course', None)
        if student and course:
            existing = Certificate.objects.filter(student=student, course=course)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError('This student already has a certificate for this course.')
        return attrs


class CertificateVerifySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True, default=None)

    class Meta:
        model = Certificate
        fields = [
            'certificate_code', 'student_name', 'course_title', 'template_name',
            'certificate_type', 'issued_at', 'status',
        ]


class CertificateCourseSerializer(serializers.ModelSerializer):
    """Lightweight course list for the certificates dashboard's course
    picker — kept self-contained under `manage_certificates` rather than
    reusing the courses app's (differently-scoped) dashboard endpoint."""

    class Meta:
        model = Course
        fields = ['id', 'title', 'course_type', 'certificate_enabled']


class EligibleStudentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    reason = serializers.CharField()
