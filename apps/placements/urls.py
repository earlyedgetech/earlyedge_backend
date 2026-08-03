from django.urls import path

from . import views

app_name = 'placements'

urlpatterns = [
    # Public / student-facing
    path('jobs/', views.OpenJobsListView.as_view(), name='open-jobs'),
    path('apply/', views.ApplyToJobView.as_view(), name='apply'),
    path('my-applications/', views.MyApplicationsListView.as_view(), name='my-applications'),

    # Dashboard (RBAC)
    path('dashboard/companies/', views.CompanyListCreateView.as_view(), name='company-list-create'),
    path('dashboard/jobs/', views.JobListCreateView.as_view(), name='job-list-create'),
    path('dashboard/jobs/<int:pk>/', views.JobDetailView.as_view(), name='job-detail'),
    path('dashboard/applications/', views.JobApplicationListView.as_view(), name='application-list'),
    path('dashboard/applications/<int:pk>/', views.JobApplicationDetailView.as_view(), name='application-detail'),
]
