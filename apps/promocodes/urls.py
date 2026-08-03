from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'promocodes'

router = DefaultRouter()
router.register('codes', views.PromoCodeViewSet, basename='promo-code')

urlpatterns = [
    path('analytics/', views.PromoCodeAnalyticsView.as_view(), name='analytics'),
    path('public/', views.PromoCodePublicListView.as_view(), name='promo-code-public-list'),
    # Must come before the router include, otherwise DefaultRouter's
    # codes/<pk>/ pattern would swallow this path first.
    path('codes/export/', views.PromoCodeExportView.as_view(), name='promo-code-export'),
    path('', include(router.urls)),
]
