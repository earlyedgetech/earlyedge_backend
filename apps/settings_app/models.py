from common.models import TimeStampedModel
from django.db import models


class SiteSettings(TimeStampedModel):
    # General
    site_name = models.CharField(max_length=150, default='Early Edge Tech')
    site_logo_url = models.URLField(blank=True)
    favicon_url = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    office_hours = models.CharField(max_length=150, blank=True)
    max_concurrent_devices = models.PositiveSmallIntegerField(
        default=2,
        help_text='Hotstar-style cap — logging in on a new device beyond this limit signs the '
                   "student's oldest active device out immediately.",
    )

    # Company Details
    legal_name = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    gst_number = models.CharField(max_length=50, blank=True)
    established_year = models.PositiveIntegerField(null=True, blank=True)
    company_address = models.CharField(max_length=255, blank=True)

    # Email & Branding
    email_from_name = models.CharField(max_length=150, blank=True)
    email_from_address = models.EmailField(blank=True)
    primary_color = models.CharField(max_length=20, blank=True, default='#004030')

    # SEO
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)
    seo_keywords = models.CharField(max_length=500, blank=True)

    # Website
    social_links = models.JSONField(default=dict, blank=True)
    home_page_banner_url = models.URLField(blank=True)
    about_page_content = models.TextField(blank=True)

    # Integrations
    google_analytics_id = models.CharField(max_length=50, blank=True)
    facebook_pixel_id = models.CharField(max_length=50, blank=True)
    razorpay_key_id = models.CharField(max_length=100, blank=True)
    razorpay_key_secret = models.CharField(max_length=100, blank=True)

    # Terabox (course/material file storage) — see apps/uploads/terabox_client.py
    terabox_enabled = models.BooleanField(default=False)
    terabox_access_token = models.CharField(max_length=255, blank=True)
    terabox_app_id = models.CharField(max_length=50, blank=True, default='250528')
    terabox_root_path = models.CharField(max_length=255, blank=True, default='/EarlyEdgeTech')

    # Zoom (live class meeting links) — see apps/live_classes/zoom_client.py
    zoom_enabled = models.BooleanField(default=False)
    zoom_account_id = models.CharField(max_length=255, blank=True)
    zoom_client_id = models.CharField(max_length=255, blank=True)
    zoom_client_secret = models.CharField(max_length=255, blank=True)

    # WhatsApp (Meta Cloud API — live class reminders) — see apps/live_classes/whatsapp_client.py
    whatsapp_enabled = models.BooleanField(default=False)
    whatsapp_access_token = models.CharField(max_length=500, blank=True)
    whatsapp_waba_id = models.CharField(max_length=100, blank=True)
    whatsapp_phone_number_id = models.CharField(max_length=100, blank=True)
    whatsapp_template_name = models.CharField(max_length=100, blank=True)

    # Maintenance
    MAINTENANCE_SCOPE_CHOICES = (
        ('website', 'Website Only'),
        ('dashboard', 'Dashboard Only'),
        ('both', 'Website & Dashboard'),
    )
    maintenance_mode = models.BooleanField(default=False)
    maintenance_scope = models.CharField(
        max_length=10, choices=MAINTENANCE_SCOPE_CHOICES, default='website',
        help_text='Which side goes into maintenance mode. "Dashboard" and "Both" still let superusers into the '
                   'dashboard so someone can turn it back off.',
    )
    maintenance_message = models.TextField(blank=True, help_text='Purpose shown to visitors while the site is down.')
    maintenance_start_at = models.DateTimeField(null=True, blank=True)
    maintenance_end_at = models.DateTimeField(null=True, blank=True)
    last_backup_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'site_settings'

    def __str__(self):
        return 'Site Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class NotificationTemplate(TimeStampedModel):
    """One row per real, code-driven notification trigger — powers both the
    Email & Branding template editor and the Message Automations page (same
    data, two views). Rows are seeded via migration, not admin-creatable:
    each key corresponds to an actual call site that fires it."""

    MODULE_CHOICES = (
        ('account', 'Account'),
        ('students', 'Student Management'),
        ('leads', 'Leads Management'),
        ('purchases', 'Purchases & Enrollment'),
        ('live_classes', 'Live Classes'),
        ('instructors', 'Instructor Management'),
    )
    CHANNEL_CHOICES = (
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    )

    key = models.SlugField(max_length=100, unique=True)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    label = models.CharField(max_length=150)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='email')
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'notification_templates'
        ordering = ['module', 'label']

    def __str__(self):
        return self.label


class Announcement(TimeStampedModel):
    """Admin-configurable website announcement bar — general messages, a
    specific course's access promo, a new-course launch, or a countdown to
    a launch/deadline. Only ever one is "live" on the site at a time; see
    Announcement.get_active()."""

    TYPE_CHOICES = (
        ('general', 'General'),
        ('course_access', 'Course Access'),
        ('new_course', 'New Course Launch'),
        ('countdown', 'Launch Countdown'),
    )

    message = models.CharField(max_length=255)
    announcement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='general')
    course = models.ForeignKey(
        'courses.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='announcements',
        help_text='For Course Access / New Course Launch — links the CTA to this course.',
    )
    cta_label = models.CharField(max_length=50, blank=True, default='Browse Courses')
    cta_link = models.CharField(
        max_length=255, blank=True,
        help_text='Overrides the auto-derived course link. Leave blank to link to the course above (if set).',
    )
    countdown_at = models.DateTimeField(
        null=True, blank=True, help_text='For Launch Countdown — when the launch/deadline happens.'
    )
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True, help_text='Leave blank to start immediately.')
    ends_at = models.DateTimeField(null=True, blank=True, help_text='Leave blank to run indefinitely.')

    class Meta:
        db_table = 'announcements'
        ordering = ['-created_at']

    def __str__(self):
        return self.message

    @classmethod
    def get_active(cls):
        from django.utils import timezone

        now = timezone.now()
        return (
            cls.objects.filter(is_active=True)
            .exclude(starts_at__gt=now)
            .exclude(ends_at__lt=now)
            .order_by('-created_at')
            .first()
        )


class LegalPage(TimeStampedModel):
    """Privacy Policy / Terms of Use / Cookies Policy — one row per fixed
    page_type, auto-created on first GET (see LegalPageView), not a
    multi-row resource (see Blog for that)."""

    PAGE_TYPE_CHOICES = (
        ('privacy_policy', 'Privacy Policy'),
        ('terms_of_use', 'Terms of Use'),
        ('cookies_policy', 'Cookies Policy'),
    )

    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, unique=True)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField(blank=True)

    class Meta:
        db_table = 'legal_pages'

    def __str__(self):
        return self.get_page_type_display()
