from django.urls import path

from . import views

app_name = 'instructors'

urlpatterns = [
    # Public directory (marketing site)
    path('', views.InstructorPublicListView.as_view(), name='instructor-public-list'),
    path('apply/', views.InstructorApplyView.as_view(), name='instructor-apply'),
    path('reviews/public/', views.InstructorReviewPublicListView.as_view(), name='instructor-review-public-list'),
    path('<int:pk>/', views.InstructorPublicDetailView.as_view(), name='instructor-public-detail'),
    path('<int:pk>/reviews/', views.InstructorReviewPublicCreateView.as_view(), name='instructor-review-create'),

    # Dashboard (RBAC)
    path('dashboard/instructors/', views.InstructorListCreateView.as_view(), name='instructor-list-create'),
    path('dashboard/instructors/me/', views.InstructorMeView.as_view(), name='instructor-me'),
    path(
        'dashboard/instructors/analytics/overview/',
        views.InstructorAnalyticsOverviewView.as_view(),
        name='instructor-analytics-overview',
    ),
    path('dashboard/instructors/<int:pk>/', views.InstructorDetailView.as_view(), name='instructor-detail'),
    path(
        'dashboard/instructors/<int:pk>/earnings/',
        views.InstructorEarningsView.as_view(),
        name='instructor-earnings',
    ),
    path('dashboard/reviews/', views.InstructorReviewListView.as_view(), name='instructor-review-list'),
    path('dashboard/reviews/export/', views.InstructorReviewExportView.as_view(), name='instructor-review-export'),
    path('dashboard/reviews/<int:pk>/', views.InstructorReviewDetailView.as_view(), name='instructor-review-detail'),
]
