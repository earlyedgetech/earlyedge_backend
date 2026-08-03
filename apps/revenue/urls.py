from django.urls import path

from . import views

app_name = 'revenue'

urlpatterns = [
    path('dashboard/payments/', views.PaymentListView.as_view(), name='payment-list'),
    path('dashboard/refunds/', views.RefundListCreateView.as_view(), name='refund-list-create'),
    path('dashboard/refunds/<int:pk>/', views.RefundDetailView.as_view(), name='refund-detail'),
    path('dashboard/analytics/', views.RevenueAnalyticsView.as_view(), name='analytics'),
]
