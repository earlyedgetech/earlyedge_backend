from django.urls import path

from . import views

app_name = 'admin_security'

urlpatterns = [
    # Activity / admin logs (audit trail)
    path('logs/', views.AdminLogListCreateView.as_view(), name='admin-log-list-create'),
    path('logs/export/', views.AdminLogExportView.as_view(), name='admin-log-export'),
    path('logs/mine/', views.MyAdminLogListView.as_view(), name='admin-log-mine'),

    # Security settings (singleton)
    path('settings/', views.SecuritySettingsView.as_view(), name='security-settings'),

    # Roles & permissions (RBAC)
    path('permissions/', views.PermissionListView.as_view(), name='permission-list'),
    path('roles/', views.RoleListCreateView.as_view(), name='role-list-create'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role-detail'),

    # Dashboard members (force logout)
    path('members/', views.AdminMemberListView.as_view(), name='member-list'),
    path('members/<int:pk>/force-logout/', views.AdminMemberForceLogoutView.as_view(), name='member-force-logout'),

    # In-app notifications (Navbar bell)
    path('notifications/', views.MyNotificationListView.as_view(), name='notification-list-mine'),
    path('notifications/unread-count/', views.MyNotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
]
