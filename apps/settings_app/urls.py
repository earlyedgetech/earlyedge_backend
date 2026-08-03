from django.urls import path

from . import views

app_name = 'settings_app'

urlpatterns = [
    path('public/', views.PublicSiteSettingsView.as_view(), name='public-settings'),
    path('dashboard/', views.SiteSettingsView.as_view(), name='dashboard-settings'),
    path('dashboard/backup/', views.TriggerBackupView.as_view(), name='trigger-backup'),
    path(
        'dashboard/notification-templates/',
        views.NotificationTemplateListView.as_view(), name='notification-template-list',
    ),
    path(
        'dashboard/notification-templates/<int:pk>/',
        views.NotificationTemplateDetailView.as_view(), name='notification-template-detail',
    ),
    path(
        'dashboard/notification-templates/<int:pk>/test-send/',
        views.NotificationTemplateTestSendView.as_view(), name='notification-template-test-send',
    ),
    path('public/legal-pages/<str:page_type>/', views.PublicLegalPageView.as_view(), name='public-legal-page'),
    path('dashboard/legal-pages/<str:page_type>/', views.LegalPageView.as_view(), name='legal-page'),
    path('public/announcements/active/', views.PublicActiveAnnouncementView.as_view(), name='public-announcement-active'),
    path('dashboard/announcements/', views.AnnouncementListCreateView.as_view(), name='announcement-list-create'),
    path('dashboard/announcements/<int:pk>/', views.AnnouncementDetailView.as_view(), name='announcement-detail'),
]
