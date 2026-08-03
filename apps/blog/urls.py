from django.urls import path

from . import views

app_name = 'blog'

urlpatterns = [
    path('public/posts/', views.PublicBlogPostListView.as_view(), name='public-post-list'),
    path('public/posts/<slug:slug>/', views.PublicBlogPostDetailView.as_view(), name='public-post-detail'),
    path('dashboard/posts/', views.BlogPostListCreateView.as_view(), name='post-list-create'),
    path('dashboard/posts/<int:pk>/', views.BlogPostDetailView.as_view(), name='post-detail'),
]
