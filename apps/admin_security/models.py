from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from common.models import TimeStampedModel


class Permission(TimeStampedModel):
    MODULE_CHOICES = (
        ('dashboard', 'Dashboard'),
        ('courses', 'Course Management'),
        ('materials', 'Materials'),
        ('instructors', 'Instructor Management'),
        ('leads', 'Leads Management'),
        ('students', 'Student Management'),
        ('live_classes', 'Live Classes'),
        ('placements', 'Placement Assistant'),
        ('certificates', 'Certificates'),
        ('challenges', 'Daily Challenges'),
        ('promocodes', 'Promo Codes'),
        ('purchases', 'Purchases & Enrollment'),
        ('revenue', 'Revenue & Payments'),
        ('settings', 'Settings'),
        ('support', 'Support & Feedback'),
        ('admin_security', 'Admin & Security'),
    )

    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES, default='dashboard')

    class Meta:
        db_table = 'dashboard_permissions'

    def __str__(self):
        return self.codename


class Role(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')

    class Meta:
        db_table = 'dashboard_roles'

    def __str__(self):
        return self.name

    def has_permission(self, codename):
        return self.permissions.filter(codename=codename).exists()


class AdminMemberManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, role=None, must_reset_password=False, **extra_fields):
        if not email:
            raise ValueError('Admin members must have an email address')
        email = self.normalize_email(email)
        member = self.model(
            email=email, role=role, must_reset_password=must_reset_password, **extra_fields
        )
        if password:
            member.set_password(password)
        else:
            member.set_unusable_password()
        member.save(using=self._db)
        return member

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class AdminMember(AbstractBaseUser, TimeStampedModel):
    AUTH_PROVIDER_CHOICES = (
        ('email', 'Email'),
        ('google', 'Google'),
    )

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, related_name='members', null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    auth_provider = models.CharField(max_length=10, choices=AUTH_PROVIDER_CHOICES, default='email')
    google_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    must_reset_password = models.BooleanField(
        default=False,
        help_text='Forces a mandatory password change on next login — set when an admin '
                   'provisions this account with a temporary/dummy password.',
    )
    force_logout_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Any access/refresh token issued before this moment is rejected — set this to now() to '
                   'immediately end every active session for this member (see AdminMemberJWTAuthentication).',
    )

    objects = AdminMemberManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table = 'dashboard_members'

    def __str__(self):
        return self.email

    def has_permission(self, codename):
        if self.is_superuser:
            return True
        return self.role is not None and self.role.has_permission(codename)


class AdminLog(TimeStampedModel):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin User'),
        ('user', 'User'),
    )
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
    )

    action = models.CharField(max_length=255)
    user_name = models.CharField(max_length=255)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    ip_address = models.GenericIPAddressField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    module = models.CharField(
        max_length=30, blank=True,
        help_text="Best-effort, parsed from the API path at write time (e.g. 'leads' from '/api/leads/...').",
    )

    class Meta:
        db_table = 'dashboard_admin_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} - {self.user_name}'


class AdminNotification(TimeStampedModel):
    """A per-admin inbox item — 'lead assigned to you', 'new instructor
    application', etc. Distinct from NotificationTemplate (that's an email/
    WhatsApp template an admin edits; this is the actual in-app bell-icon
    feed). The dashboard Navbar polls MyNotificationListView for these."""

    recipient = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.CASCADE, related_name='notifications'
    )
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True, help_text='Dashboard route to navigate to on click.')
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = 'dashboard_notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient} - {self.message}'


class SecuritySettings(TimeStampedModel):
    SESSION_TIMEOUT_CHOICES = (
        ('15_min', '15 Minutes'),
        ('30_min', '30 Minutes'),
        ('1_hour', '1 Hour'),
        ('2_hour', '2 Hours'),
    )

    two_factor_authentication = models.BooleanField(default=False)
    session_timeout = models.CharField(max_length=10, choices=SESSION_TIMEOUT_CHOICES, default='30_min')
    login_alerts = models.BooleanField(default=True)

    class Meta:
        db_table = 'dashboard_security_settings'

    def __str__(self):
        return 'Security Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
