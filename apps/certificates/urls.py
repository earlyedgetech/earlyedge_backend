from django.urls import path

from . import views

app_name = 'certificates'

urlpatterns = [
    # Public
    path('verify/<str:certificate_code>/', views.CertificateVerifyView.as_view(), name='certificate-verify'),

    # Student-facing
    path('my-certificates/', views.MyCertificatesListView.as_view(), name='my-certificates'),

    # Dashboard (RBAC) — Templates
    path('dashboard/templates/', views.CertificateTemplateListCreateView.as_view(), name='template-list-create'),
    path('dashboard/templates/<int:pk>/', views.CertificateTemplateDetailView.as_view(), name='template-detail'),

    # Dashboard (RBAC) — Certificates
    path('dashboard/certificates/', views.CertificateListCreateView.as_view(), name='certificate-list-create'),
    path('dashboard/certificates/export/', views.CertificateExportView.as_view(), name='certificate-export'),
    path('dashboard/certificates/<int:pk>/', views.CertificateDetailView.as_view(), name='certificate-detail'),

    # Dashboard (RBAC) — manual generation helpers
    path('dashboard/courses/', views.CertificateCourseListView.as_view(), name='certificate-course-list'),
    path('dashboard/eligible-students/', views.EligibleStudentsView.as_view(), name='eligible-students'),

    # Dashboard (RBAC) — Analytics
    path('dashboard/analytics/', views.CertificateAnalyticsView.as_view(), name='certificate-analytics'),
]
