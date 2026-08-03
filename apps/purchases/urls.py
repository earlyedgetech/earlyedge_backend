from django.urls import path

from . import views

app_name = 'purchases'

urlpatterns = [
    # Student-facing
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('my-purchases/', views.MyPurchasesListView.as_view(), name='my-purchases'),
    path('cart/', views.CartItemListCreateView.as_view(), name='cart-list-create'),
    path('cart/<int:pk>/', views.CartItemDeleteView.as_view(), name='cart-delete'),

    # Public + student-facing — Access Plans (pricing tiers)
    path('plans/', views.PublicAccessPlanListView.as_view(), name='plan-public-list'),
    path('plans/checkout/', views.PlanCheckoutView.as_view(), name='plan-checkout'),
    path('plans/my-plans/', views.MyPlanPurchasesListView.as_view(), name='my-plans'),

    # Dashboard — Access Plans
    path('dashboard/plans/', views.AccessPlanListCreateView.as_view(), name='plan-list-create'),
    path('dashboard/plans/<int:pk>/', views.AccessPlanDetailView.as_view(), name='plan-detail'),
    path('dashboard/plan-purchases/', views.PlanPurchaseListView.as_view(), name='plan-purchase-list'),

    # Dashboard (RBAC) — export/analytics/settings must come before the
    # <int:pk>/ detail route, otherwise it would swallow them first.
    path('dashboard/purchases/export/', views.PurchaseExportView.as_view(), name='purchase-export'),
    path('dashboard/purchases/analytics/', views.PurchaseAnalyticsView.as_view(), name='purchase-analytics'),
    path('dashboard/purchases/settings/', views.PurchaseSettingsView.as_view(), name='purchase-settings'),
    path('dashboard/purchases/', views.PurchaseListView.as_view(), name='purchase-list'),
    path('dashboard/purchases/<int:pk>/', views.PurchaseDetailView.as_view(), name='purchase-detail'),
    path('dashboard/purchases/<int:pk>/remind/', views.PurchaseReminderView.as_view(), name='purchase-remind'),
    path(
        'dashboard/purchases/<int:purchase_id>/installments/<int:installment_id>/pay/',
        views.PurchaseInstallmentPayView.as_view(),
        name='purchase-installment-pay',
    ),

    # Dashboard — Cart admin visibility
    path('dashboard/cart/export/', views.CartItemExportView.as_view(), name='cart-export'),
    path('dashboard/cart/', views.CartAdminListView.as_view(), name='cart-admin-list'),
    path('dashboard/cart/<int:pk>/notify/', views.CartItemNotifyView.as_view(), name='cart-notify'),
]
