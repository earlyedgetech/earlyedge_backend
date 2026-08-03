from django.urls import path

from . import views

app_name = 'students'

urlpatterns = [
    path('dashboard/students/analytics/', views.StudentAnalyticsOverviewView.as_view(), name='student-analytics'),
    path('dashboard/students/', views.StudentListCreateView.as_view(), name='student-list'),
    path('dashboard/students/<int:pk>/', views.StudentDetailView.as_view(), name='student-detail'),
]
