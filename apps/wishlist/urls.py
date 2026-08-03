from django.urls import path

from . import views

app_name = 'wishlist'

urlpatterns = [
    path('', views.WishlistListCreateView.as_view(), name='wishlist-list-create'),
    path('<int:pk>/', views.WishlistDeleteView.as_view(), name='wishlist-delete'),
    path('dashboard/stats/', views.WishlistStatsView.as_view(), name='wishlist-stats'),
    path('dashboard/export/', views.WishlistItemExportView.as_view(), name='wishlist-export'),
    path('dashboard/items/', views.WishlistAdminListView.as_view(), name='wishlist-admin-list'),
]
