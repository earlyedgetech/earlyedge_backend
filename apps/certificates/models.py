import uuid

from common.models import TimeStampedModel
from django.db import models


class CertificateTemplate(TimeStampedModel):
    CATEGORY_CHOICES = (
        ('online_course', 'Online Course'),
        ('internship', 'Internship'),
        ('workshop', 'Workshop'),
        ('completion', 'Completion / General'),
    )

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default='online_course')
    background_image_url = models.URLField(blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = 'certificate_templates'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Certificate(TimeStampedModel):
    STATUS_CHOICES = (
        ('issued', 'Issued'),
        ('revoked', 'Revoked'),
    )
    ISSUE_TYPE_CHOICES = (
        ('manual', 'Manual'),
        ('auto', 'Automatic'),
    )

    certificate_code = models.CharField(max_length=40, unique=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='certificates')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='certificates')
    template = models.ForeignKey(
        CertificateTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='certificates'
    )
    certificate_type = models.CharField(
        max_length=15, choices=CertificateTemplate.CATEGORY_CHOICES, default='online_course'
    )
    issue_type = models.CharField(max_length=10, choices=ISSUE_TYPE_CHOICES, default='manual')
    issued_at = models.DateTimeField(auto_now_add=True)
    pdf_url = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='issued')

    class Meta:
        db_table = 'certificates'
        ordering = ['-issued_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'course'], name='unique_student_course_certificate')
        ]

    def __str__(self):
        return f'{self.certificate_code} - {self.student}'
