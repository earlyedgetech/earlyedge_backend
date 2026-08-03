from django.urls import path

from . import views

app_name = 'challenges'

urlpatterns = [
    # Public / student-facing
    path('active/', views.ActiveChallengesListView.as_view(), name='active-list'),
    path('submit/', views.SubmitChallengeView.as_view(), name='submit'),
    path('my-submissions/', views.MySubmissionsListView.as_view(), name='my-submissions'),
    path('leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),

    # Dashboard (RBAC)
    path('dashboard/challenges/', views.ChallengeListCreateView.as_view(), name='challenge-list-create'),
    path('dashboard/challenges/<int:pk>/', views.ChallengeDetailView.as_view(), name='challenge-detail'),
    path('dashboard/submissions/', views.SubmissionListView.as_view(), name='submission-list'),
    path('dashboard/submissions/<int:pk>/', views.SubmissionDetailView.as_view(), name='submission-detail'),
]
