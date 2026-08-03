from rest_framework import serializers

from .models import Company, Job, JobApplication


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'website', 'logo_url']


class JobSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    applicant_count = serializers.IntegerField(source='applications.count', read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'company', 'company_name', 'title', 'description', 'location', 'job_type',
            'min_experience_years', 'skills', 'salary_range', 'status', 'applicant_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class JobApplicationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    company_name = serializers.CharField(source='job.company.name', read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 'job', 'job_title', 'company_name', 'student', 'student_name', 'student_email',
            'resume_url', 'status', 'interview_at', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'student', 'created_at']


class JobApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobApplication
        fields = ['job', 'resume_url']

    def validate_job(self, value):
        student = self.context['request'].user
        if JobApplication.objects.filter(job=value, student=student).exists():
            raise serializers.ValidationError('You have already applied to this job.')
        if value.status != 'open':
            raise serializers.ValidationError('This job is no longer accepting applications.')
        return value
