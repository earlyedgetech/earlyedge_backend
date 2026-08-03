from django.urls import path

from . import views

app_name = 'authentication'

urlpatterns = [
    # Student (website)
    path('student/register/', views.StudentRegisterView.as_view(), name='student-register'),
    path('student/login/', views.StudentLoginView.as_view(), name='student-login'),
    path('student/google/', views.StudentGoogleLoginView.as_view(), name='student-google-login'),
    path('student/forgot-password/', views.StudentForgotPasswordView.as_view(), name='student-forgot-password'),
    path('student/reset-password/', views.StudentResetPasswordView.as_view(), name='student-reset-password'),
    path('student/change-password/', views.StudentChangePasswordView.as_view(), name='student-change-password'),
    path('student/me/', views.StudentMeView.as_view(), name='student-me'),
    path('student/refresh/', views.StudentTokenRefreshView.as_view(), name='student-token-refresh'),

    # Dashboard member (RBAC)
    path('dashboard/register/', views.AdminMemberRegisterView.as_view(), name='dashboard-register'),
    path('dashboard/login/', views.AdminMemberLoginView.as_view(), name='dashboard-login'),
    path('dashboard/google/', views.AdminMemberGoogleLoginView.as_view(), name='dashboard-google-login'),
    path('dashboard/forgot-password/', views.AdminMemberForgotPasswordView.as_view(), name='dashboard-forgot-password'),
    path('dashboard/reset-password/', views.AdminMemberResetPasswordView.as_view(), name='dashboard-reset-password'),
    path('dashboard/change-password/', views.AdminMemberChangePasswordView.as_view(), name='dashboard-change-password'),
    path('dashboard/me/', views.AdminMemberMeView.as_view(), name='dashboard-me'),
    path('dashboard/refresh/', views.AdminMemberTokenRefreshView.as_view(), name='dashboard-token-refresh'),
]
