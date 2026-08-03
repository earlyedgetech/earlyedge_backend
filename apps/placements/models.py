from common.models import TimeStampedModel
from django.db import models


class Company(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    website = models.URLField(blank=True)
    logo_url = models.URLField(blank=True)

    class Meta:
        db_table = 'placement_companies'
        verbose_name_plural = 'companies'
        ordering = ['name']

    def __str__(self):
        return self.name


class Job(TimeStampedModel):
    JOB_TYPE_CHOICES = (
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('internship', 'Internship'),
        ('contract', 'Contract'),
    )
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='jobs')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=150, blank=True)
    job_type = models.CharField(max_length=15, choices=JOB_TYPE_CHOICES, default='full_time')
    min_experience_years = models.PositiveIntegerField(default=0)
    skills = models.JSONField(default=list, blank=True)
    salary_range = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')

    class Meta:
        db_table = 'placement_jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} @ {self.company}'


class JobApplication(TimeStampedModel):
    STATUS_CHOICES = (
        ('applied', 'Applied'),
        ('shortlisted', 'Shortlisted'),
        ('interview', 'Interview Scheduled'),
        ('offered', 'Offered'),
        ('rejected', 'Rejected'),
    )

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='job_applications')
    resume_url = models.URLField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='applied')
    interview_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'placement_applications'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['job', 'student'], name='unique_job_student_application')
        ]

    def __str__(self):
        return f'{self.student} -> {self.job} ({self.status})'
