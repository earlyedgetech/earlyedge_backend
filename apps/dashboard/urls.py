from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('overview/', views.DashboardOverviewView.as_view(), name='overview'),
    path('module-stats/', views.DashboardModuleStatsView.as_view(), name='module-stats'),
    path('public-stats/', views.PublicPlatformStatsView.as_view(), name='public-stats'),
]
