from django.urls import path

from . import views

app_name = 'leads'

urlpatterns = [
    # Public (website enquiry form + generic webhook)
    path('public/enquire/', views.LeadPublicEnquiryView.as_view(), name='public-enquire'),
    path('public/webhook/<int:source_id>/', views.LeadWebhookView.as_view(), name='public-webhook'),

    # Dashboard — Counsellor options
    path('dashboard/counsellors/', views.CounsellorOptionsView.as_view(), name='counsellor-options'),

    # Dashboard — Pipeline Stages
    path('dashboard/pipeline-stages/', views.PipelineStageListCreateView.as_view(), name='stage-list-create'),
    path('dashboard/pipeline-stages/<int:pk>/', views.PipelineStageDetailView.as_view(), name='stage-detail'),

    # Dashboard — Lead Sources
    path('dashboard/sources/', views.LeadSourceListCreateView.as_view(), name='source-list-create'),
    path('dashboard/sources/<int:pk>/', views.LeadSourceDetailView.as_view(), name='source-detail'),

    # Dashboard — Leads
    path('dashboard/leads/', views.LeadListCreateView.as_view(), name='lead-list-create'),
    path('dashboard/leads/check-duplicate/', views.LeadDuplicateCheckView.as_view(), name='lead-check-duplicate'),
    path('dashboard/leads/export/', views.LeadExportView.as_view(), name='lead-export'),
    path('dashboard/leads/import/', views.LeadImportView.as_view(), name='lead-import'),
    path('dashboard/leads/bulk-action/', views.LeadBulkActionView.as_view(), name='lead-bulk-action'),
    path(
        'dashboard/leads/auto-assign-unassigned/',
        views.LeadAutoAssignUnassignedView.as_view(),
        name='lead-auto-assign-unassigned',
    ),
    path('dashboard/leads/<int:pk>/', views.LeadDetailView.as_view(), name='lead-detail'),
    path('dashboard/leads/<int:pk>/merge/', views.LeadMergeView.as_view(), name='lead-merge'),

    # Dashboard — Follow-ups
    path('dashboard/follow-ups/', views.LeadFollowUpListCreateView.as_view(), name='follow-up-list-create'),
    path('dashboard/follow-ups/<int:pk>/', views.LeadFollowUpDetailView.as_view(), name='follow-up-detail'),

    # Dashboard — Counselling
    path('dashboard/counselling-sessions/', views.CounsellingSessionListCreateView.as_view(), name='session-list-create'),
    path('dashboard/counselling-sessions/<int:pk>/', views.CounsellingSessionDetailView.as_view(), name='session-detail'),

    # Dashboard — Documents
    path('dashboard/documents/', views.LeadDocumentListCreateView.as_view(), name='document-list-create'),
    path('dashboard/documents/<int:pk>/', views.LeadDocumentDetailView.as_view(), name='document-detail'),

    # Dashboard — Automations
    path('dashboard/automations/', views.AutomationRuleListCreateView.as_view(), name='automation-list-create'),
    path('dashboard/automations/<int:pk>/', views.AutomationRuleDetailView.as_view(), name='automation-detail'),

    # Dashboard — Settings + Custom Fields
    path('dashboard/settings/', views.LeadSettingsView.as_view(), name='settings'),
    path(
        'dashboard/custom-fields/',
        views.LeadCustomFieldDefinitionListCreateView.as_view(),
        name='custom-field-list-create',
    ),
    path(
        'dashboard/custom-fields/<int:pk>/',
        views.LeadCustomFieldDefinitionDetailView.as_view(),
        name='custom-field-detail',
    ),

    # Dashboard — Analytics
    path('dashboard/analytics/overview/', views.LeadAnalyticsOverviewView.as_view(), name='analytics-overview'),
]
