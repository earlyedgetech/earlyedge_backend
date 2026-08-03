from common.models import TimeStampedModel
from django.db import models
from django.utils.text import slugify


class PipelineStage(TimeStampedModel):
    """Admin-configurable pipeline column (New Lead, Contacted, ...,
    Enrolled / Not Interested -> Retry or Lost). Seeded via a data
    migration; editable from Lead Settings."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=20, blank=True, default='#6b7280')
    is_won = models.BooleanField(default=False, help_text='Marks this stage as a successful admission (e.g. "Enrolled").')
    is_lost = models.BooleanField(default=False, help_text='Marks this stage as a closed-lost outcome.')

    class Meta:
        db_table = 'lead_pipeline_stages'
        ordering = ['order']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class LeadSource(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    campaign_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    webhook_secret = models.CharField(
        max_length=100, blank=True,
        help_text='Shared secret required on inbound webhook posts tagged to this source.',
    )
    default_assignee = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='default_assigned_sources',
        help_text='Who leads from this source go to when Lead Settings > Assignment strategy is "Source-wise" '
                   '(e.g. Website leads to one counsellor, other sources to another).',
    )

    class Meta:
        db_table = 'lead_sources'
        ordering = ['name']

    def __str__(self):
        return self.name


class Lead(TimeStampedModel):
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    )

    full_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    parent_name = models.CharField(max_length=255, blank=True)
    parent_contact = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    branch = models.CharField(max_length=100, blank=True)

    source = models.ForeignKey(LeadSource, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads')
    interested_course = models.ForeignKey(
        'courses.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='interested_leads'
    )
    stage = models.ForeignKey(
        PipelineStage, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads'
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    tags = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False)

    assigned_to = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_leads'
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'leads'
        ordering = ['-created_at']

    def __str__(self):
        return self.full_name


class LeadStageHistory(TimeStampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='stage_history')
    from_stage = models.ForeignKey(PipelineStage, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    to_stage = models.ForeignKey(PipelineStage, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    changed_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        db_table = 'lead_stage_history'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.lead} -> {self.to_stage}'


class LeadActivity(TimeStampedModel):
    """Auto-recorded timeline entry — covers Timeline + Activity Log + a
    call/WhatsApp/email trail as those channels get used, instead of
    several near-duplicate history models."""

    ACTIVITY_TYPE_CHOICES = (
        ('created', 'Created'),
        ('stage_changed', 'Stage Changed'),
        ('assigned', 'Assigned'),
        ('note_added', 'Note Added'),
        ('follow_up', 'Follow-up'),
        ('document_added', 'Document Added'),
        ('merged', 'Merged'),
        ('archived', 'Archived'),
        ('automation', 'Automation'),
    )

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='activities')
    actor = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    description = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'lead_activities'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.lead} - {self.activity_type}'


class LeadDocument(TimeStampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file_url = models.URLField()
    file_size = models.BigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        db_table = 'lead_documents'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class LeadFollowUp(TimeStampedModel):
    TYPE_CHOICES = (
        ('call', 'Phone Call'),
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('zoom', 'Zoom Meeting'),
        ('campus_visit', 'Campus Visit'),
    )

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='follow_ups')
    follow_up_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='call')
    note = models.TextField()
    follow_up_date = models.DateTimeField()
    priority = models.CharField(max_length=10, choices=Lead.PRIORITY_CHOICES, default='medium')
    is_completed = models.BooleanField(default=False)
    outcome = models.TextField(blank=True)
    next_follow_up_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_follow_ups',
    )

    class Meta:
        db_table = 'lead_follow_ups'
        ordering = ['follow_up_date']

    def __str__(self):
        return f'{self.lead.full_name} - {self.follow_up_date}'


class CounsellingSession(TimeStampedModel):
    MODE_CHOICES = (
        ('online', 'Online'),
        ('offline', 'Offline'),
    )
    OUTCOME_CHOICES = (
        ('', 'Pending'),
        ('interested', 'Interested'),
        ('demo_required', 'Demo Required'),
        ('admission_ready', 'Admission Ready'),
        ('retry', 'Retry'),
        ('lost', 'Lost'),
    )

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='counselling_sessions')
    counsellor = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='counselling_sessions',
    )
    scheduled_at = models.DateTimeField()
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='online')
    meeting_url = models.URLField(blank=True)
    classroom = models.CharField(max_length=100, blank=True)
    course_discussed = models.ForeignKey(
        'courses.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    parent_attendance = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    scholarship_discussed = models.BooleanField(default=False)
    placement_discussed = models.BooleanField(default=False)
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True, default='')
    feedback = models.TextField(blank=True)

    class Meta:
        db_table = 'lead_counselling_sessions'
        ordering = ['-scheduled_at']

    def __str__(self):
        return f'{self.lead} - {self.scheduled_at}'


class AutomationRule(TimeStampedModel):
    TRIGGER_CHOICES = (
        ('new_lead_created', 'New Lead Created'),
        ('stage_changed', 'Pipeline Stage Changed'),
        ('follow_up_completed', 'Follow-up Completed'),
        ('demo_missed', 'Demo Missed'),
        ('retry_date_reached', 'Retry Date Reached'),
    )
    ACTION_CHOICES = (
        ('assign_counsellor', 'Assign Counsellor'),
        ('send_welcome_email', 'Send Welcome Email'),
        ('send_whatsapp', 'Send WhatsApp Message'),
        ('schedule_follow_up', 'Schedule Follow-up'),
        ('notify_manager', 'Notify Manager'),
        ('move_stage', 'Move Pipeline Stage'),
        ('add_tag', 'Add Tag'),
    )

    name = models.CharField(max_length=150)
    trigger = models.CharField(max_length=25, choices=TRIGGER_CHOICES)
    action = models.CharField(max_length=25, choices=ACTION_CHOICES)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'lead_automation_rules'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class LeadCustomFieldDefinition(TimeStampedModel):
    FIELD_TYPE_CHOICES = (
        ('text', 'Text'),
        ('number', 'Number'),
        ('dropdown', 'Dropdown'),
        ('date', 'Date'),
    )

    label = models.CharField(max_length=150)
    key = models.SlugField(max_length=150, blank=True)
    field_type = models.CharField(max_length=10, choices=FIELD_TYPE_CHOICES, default='text')
    options = models.JSONField(default=list, blank=True, help_text='Choices for dropdown-type fields.')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'lead_custom_field_definitions'
        ordering = ['label']

    def __str__(self):
        return self.label

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = slugify(self.label).replace('-', '_')
        super().save(*args, **kwargs)


class LeadSettings(TimeStampedModel):
    lead_number_format = models.CharField(max_length=50, blank=True, default='LEAD-{id}')
    default_country = models.CharField(max_length=100, blank=True)
    working_hours_start = models.TimeField(null=True, blank=True)
    working_hours_end = models.TimeField(null=True, blank=True)
    default_pipeline_stage = models.ForeignKey(
        PipelineStage, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    duplicate_detection_field = models.CharField(
        max_length=15,
        choices=(('phone', 'Phone Number'), ('email', 'Email Address'), ('name_phone', 'Name + Phone')),
        default='phone',
    )
    assignment_strategy = models.CharField(
        max_length=15,
        choices=(
            ('manual', 'Manual'), ('round_robin', 'Round Robin'),
            ('branch_wise', 'Branch-wise'), ('course_wise', 'Course-wise'),
            ('source_wise', 'Source-wise'),
        ),
        default='manual',
    )
    branch_assignment_map = models.JSONField(
        default=dict, blank=True,
        help_text='{"<branch name>": <AdminMember id>} — who branch_wise-strategy leads for that branch go to.',
    )
    course_assignment_map = models.JSONField(
        default=dict, blank=True,
        help_text='{"<Course id>": <AdminMember id>} — who course_wise-strategy leads for that course go to.',
    )
    retry_interval_days = models.PositiveIntegerField(default=7)

    # Deferred vendor integrations — disabled placeholders (see Terabox in
    # settings_app.SiteSettings for the pattern this follows). None of these
    # are called by any code yet; they exist so credentials have somewhere
    # to live once/if these get built out for real.
    facebook_leads_enabled = models.BooleanField(default=False)
    facebook_leads_access_token = models.CharField(max_length=500, blank=True)
    facebook_leads_page_id = models.CharField(max_length=100, blank=True)

    google_sheets_enabled = models.BooleanField(default=False)
    google_sheets_service_account_json = models.TextField(blank=True)
    google_sheets_spreadsheet_id = models.CharField(max_length=150, blank=True)

    calendly_enabled = models.BooleanField(default=False)
    calendly_api_token = models.CharField(max_length=255, blank=True)

    email_sync_enabled = models.BooleanField(default=False)
    email_sync_provider = models.CharField(
        max_length=10, choices=(('gmail', 'Gmail'), ('outlook', 'Outlook')), blank=True
    )
    email_sync_credentials = models.TextField(blank=True)

    class Meta:
        db_table = 'lead_settings'

    def __str__(self):
        return 'Lead Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
