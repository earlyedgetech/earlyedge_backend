from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from common.models import TimeStampedModel


class StudentManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Students must have an email address')
        email = self.normalize_email(email)
        student = self.model(email=email, **extra_fields)
        if password:
            student.set_password(password)
        else:
            student.set_unusable_password()
        student.save(using=self._db)
        return student


class Student(AbstractBaseUser, TimeStampedModel):
    AUTH_PROVIDER_CHOICES = (
        ('email', 'Email'),
        ('google', 'Google'),
    )
    SOURCE_CHOICES = (
        ('website', 'Website'),
        ('lead', 'Converted from Lead'),
        ('manual', 'Manually Added'),
    )

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    auth_provider = models.CharField(max_length=10, choices=AUTH_PROVIDER_CHOICES, default='email')
    google_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    source = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default='website',
        help_text='Website = self-signed-up. Lead/Manual = created by an admin from the dashboard.',
    )
    converted_from_lead = models.OneToOneField(
        'leads.Lead', on_delete=models.SET_NULL, null=True, blank=True, related_name='converted_student',
    )

    objects = StudentManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table = 'students'

    def __str__(self):
        return self.email


class StudentDevice(TimeStampedModel):
    """One active login session — the "device" in the Hotstar-style
    concurrent-device cap (see settings_app.SiteSettings.max_concurrent_devices
    and StudentJWTAuthentication). A row is created on every successful
    student login/register (see utils.get_tokens_for_student) and deleted
    once the account's device count exceeds the configured cap (oldest
    first) — deleting a row immediately invalidates that device's tokens,
    since auth checks the row still exists on every request."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='devices')
    session_id = models.CharField(max_length=64, unique=True)
    device_label = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'student_devices'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.student} - {self.device_label or self.session_id[:8]}'
