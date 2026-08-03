from django.urls import path

from . import views

app_name = 'live_classes'

urlpatterns = [
    # Student-facing
    path('my-batches/', views.MyBatchesListView.as_view(), name='my-batches'),
    path('my-sessions/', views.MyUpcomingSessionsListView.as_view(), name='my-sessions'),
    path('register/', views.BatchRegistrationCreateView.as_view(), name='register'),

    # Public (marketing site)
    path('public/', views.PublicBatchListView.as_view(), name='public-batch-list'),
    path('public/<int:pk>/', views.PublicBatchDetailView.as_view(), name='public-batch-detail'),

    # Dashboard (RBAC)
    path('dashboard/batches/', views.BatchListCreateView.as_view(), name='batch-list-create'),
    path('dashboard/batches/<int:pk>/', views.BatchDetailView.as_view(), name='batch-detail'),
    path(
        'dashboard/batches/<int:pk>/generate-sessions/',
        views.BatchGenerateSessionsView.as_view(),
        name='batch-generate-sessions',
    ),
    path('dashboard/sessions/', views.LiveSessionListCreateView.as_view(), name='session-list-create'),
    path('dashboard/sessions/<int:pk>/', views.LiveSessionDetailView.as_view(), name='session-detail'),
    path('dashboard/registrations/', views.BatchRegistrationListView.as_view(), name='registration-list'),
    path(
        'dashboard/registrations/<int:pk>/',
        views.BatchRegistrationDetailView.as_view(),
        name='registration-detail',
    ),
    path('dashboard/attendance/', views.SessionAttendanceListView.as_view(), name='attendance-list'),
    path(
        'dashboard/attendance/<int:pk>/',
        views.SessionAttendanceDetailView.as_view(),
        name='attendance-detail',
    ),
    path('dashboard/settings/', views.LiveClassSettingsView.as_view(), name='settings'),
    path('dashboard/analytics/overview/', views.LiveClassAnalyticsOverviewView.as_view(), name='analytics-overview'),
]
