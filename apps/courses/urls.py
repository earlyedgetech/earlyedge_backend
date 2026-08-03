from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    # Public (marketing site) — reviews/public/ and categories/ must come
    # before <slug:slug>/, otherwise that catch-all would swallow them first.
    path('', views.CoursePublicListView.as_view(), name='course-public-list'),
    path('categories/', views.CourseCategoryPublicListView.as_view(), name='category-public-list'),
    path('reviews/public/', views.CourseFeedbackPublicListView.as_view(), name='course-feedback-public-list'),
    path('<slug:slug>/', views.CoursePublicDetailView.as_view(), name='course-public-detail'),
    path('<slug:slug>/feedback/', views.CourseFeedbackPublicCreateView.as_view(), name='course-feedback-create'),

    # Dashboard (RBAC)
    path('dashboard/categories/', views.CourseCategoryListCreateView.as_view(), name='category-list-create'),
    path('dashboard/categories/<int:pk>/', views.CourseCategoryDetailView.as_view(), name='category-detail'),
    path('dashboard/subcategories/', views.CourseSubcategoryListCreateView.as_view(), name='subcategory-list-create'),
    path(
        'dashboard/subcategories/<int:pk>/',
        views.CourseSubcategoryDetailView.as_view(),
        name='subcategory-detail',
    ),
    path('dashboard/courses/', views.CourseListCreateView.as_view(), name='course-list-create'),
    path('dashboard/courses/<int:pk>/', views.CourseDetailView.as_view(), name='course-detail'),
    path(
        'dashboard/analytics/overview/',
        views.CourseAnalyticsOverviewView.as_view(),
        name='analytics-overview',
    ),
    path('dashboard/feedback/', views.CourseFeedbackListView.as_view(), name='feedback-list'),
    path('dashboard/feedback/export/', views.CourseFeedbackExportView.as_view(), name='feedback-export'),
    path('dashboard/feedback/<int:pk>/', views.CourseFeedbackDetailView.as_view(), name='feedback-detail'),
]
