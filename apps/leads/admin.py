from django.contrib import admin

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

admin.site.register(LeadSource)
admin.site.register(LeadFollowUp)
admin.site.register(LeadActivity)
admin.site.register(LeadDocument)
admin.site.register(LeadStageHistory)
admin.site.register(CounsellingSession)
admin.site.register(AutomationRule)
admin.site.register(LeadCustomFieldDefinition)
admin.site.register(LeadSettings)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'stage', 'source', 'assigned_to', 'is_archived']
    list_filter = ['stage', 'source', 'priority', 'is_archived']
    search_fields = ['full_name', 'email', 'phone']


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'is_won', 'is_lost']
