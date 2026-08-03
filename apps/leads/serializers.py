from rest_framework import serializers

from .models import (
    AutomationRule,
    CounsellingSession,
    Lead,
    LeadActivity,
    LeadCustomFieldDefinition,
    LeadDocument,
    LeadFollowUp,
    LeadSettings,
    LeadSource,
    LeadStageHistory,
    PipelineStage,
)


class PipelineStageSerializer(serializers.ModelSerializer):
    lead_count = serializers.IntegerField(source='leads.count', read_only=True)

    class Meta:
        model = PipelineStage
        fields = ['id', 'name', 'slug', 'order', 'color', 'is_won', 'is_lost', 'lead_count']
        read_only_fields = ['id', 'slug', 'lead_count']


class LeadSourceSerializer(serializers.ModelSerializer):
    lead_count = serializers.IntegerField(source='leads.count', read_only=True)
    default_assignee_name = serializers.CharField(source='default_assignee.full_name', read_only=True, default=None)

    class Meta:
        model = LeadSource
        fields = [
            'id', 'name', 'campaign_cost', 'webhook_secret', 'default_assignee', 'default_assignee_name',
            'lead_count',
        ]
        read_only_fields = ['id', 'lead_count']


class LeadFollowUpSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    lead_name = serializers.CharField(source='lead.full_name', read_only=True)

    class Meta:
        model = LeadFollowUp
        fields = [
            'id', 'lead', 'lead_name', 'follow_up_type', 'note', 'follow_up_date', 'priority',
            'is_completed', 'outcome', 'next_follow_up_date', 'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']


class CounsellingSessionSerializer(serializers.ModelSerializer):
    lead_name = serializers.CharField(source='lead.full_name', read_only=True)
    counsellor_name = serializers.CharField(source='counsellor.full_name', read_only=True, default=None)
    course_discussed_title = serializers.CharField(source='course_discussed.title', read_only=True, default=None)

    class Meta:
        model = CounsellingSession
        fields = [
            'id', 'lead', 'lead_name', 'counsellor', 'counsellor_name', 'scheduled_at', 'mode',
            'meeting_url', 'classroom', 'course_discussed', 'course_discussed_title', 'parent_attendance',
            'notes', 'scholarship_discussed', 'placement_discussed', 'outcome', 'feedback', 'created_at',
        ]
        read_only_fields = ['id', 'meeting_url', 'created_at']


class LeadDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True, default=None)

    class Meta:
        model = LeadDocument
        fields = ['id', 'lead', 'title', 'file_url', 'file_size', 'uploaded_by', 'uploaded_by_name', 'created_at']
        read_only_fields = ['id', 'uploaded_by', 'created_at']


class LeadActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True, default=None)

    class Meta:
        model = LeadActivity
        fields = ['id', 'lead', 'actor', 'actor_name', 'activity_type', 'description', 'created_at']
        read_only_fields = ['id', 'lead', 'actor', 'actor_name', 'activity_type', 'description', 'created_at']


class LeadStageHistorySerializer(serializers.ModelSerializer):
    from_stage_name = serializers.CharField(source='from_stage.name', read_only=True, default=None)
    to_stage_name = serializers.CharField(source='to_stage.name', read_only=True, default=None)
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True, default=None)

    class Meta:
        model = LeadStageHistory
        fields = [
            'id', 'lead', 'from_stage', 'from_stage_name', 'to_stage', 'to_stage_name',
            'changed_by', 'changed_by_name', 'created_at',
        ]
        read_only_fields = fields


class LeadSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True, default=None)
    interested_course_title = serializers.CharField(source='interested_course.title', read_only=True, default=None)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True, default=None)
    stage_name = serializers.CharField(source='stage.name', read_only=True, default=None)
    stage_color = serializers.CharField(source='stage.color', read_only=True, default=None)

    class Meta:
        model = Lead
        fields = [
            'id', 'full_name', 'email', 'phone', 'parent_name', 'parent_contact', 'city', 'state',
            'country', 'branch', 'source', 'source_name', 'interested_course', 'interested_course_title',
            'stage', 'stage_name', 'stage_color', 'priority', 'tags', 'custom_fields', 'is_archived',
            'assigned_to', 'assigned_to_name', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LeadDetailSerializer(LeadSerializer):
    """Adds nested related data — used for the Lead Profile page. The plain
    list view intentionally stays flat (no nested prefetch cost) — see
    LeadSerializer."""

    follow_ups = LeadFollowUpSerializer(many=True, read_only=True)
    counselling_sessions = CounsellingSessionSerializer(many=True, read_only=True)
    documents = LeadDocumentSerializer(many=True, read_only=True)
    activities = LeadActivitySerializer(many=True, read_only=True)
    stage_history = LeadStageHistorySerializer(many=True, read_only=True)

    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + [
            'follow_ups', 'counselling_sessions', 'documents', 'activities', 'stage_history',
        ]


class LeadPublicCreateSerializer(serializers.ModelSerializer):
    """Public lead-capture (webhook + website enquiry form) — minimal
    surface, no stage/assignment fields exposed to an anonymous caller."""

    class Meta:
        model = Lead
        fields = ['id', 'full_name', 'email', 'phone', 'interested_course', 'notes']
        read_only_fields = ['id']

    def validate(self, attrs):
        if not attrs.get('email') and not attrs.get('phone'):
            raise serializers.ValidationError('An email or phone number is required.')
        return attrs


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = ['id', 'name', 'trigger', 'action', 'config', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class LeadCustomFieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadCustomFieldDefinition
        fields = ['id', 'label', 'key', 'field_type', 'options', 'is_active']
        read_only_fields = ['id', 'key']


class LeadSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadSettings
        fields = [
            'lead_number_format', 'default_country', 'working_hours_start', 'working_hours_end',
            'default_pipeline_stage', 'duplicate_detection_field', 'assignment_strategy',
            'branch_assignment_map', 'course_assignment_map', 'retry_interval_days',
            'facebook_leads_enabled', 'facebook_leads_access_token', 'facebook_leads_page_id',
            'google_sheets_enabled', 'google_sheets_service_account_json', 'google_sheets_spreadsheet_id',
            'calendly_enabled', 'calendly_api_token',
            'email_sync_enabled', 'email_sync_provider', 'email_sync_credentials',
            'updated_at',
        ]
        read_only_fields = ['updated_at']
