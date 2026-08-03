from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'support'

router = DefaultRouter()
router.register('tickets', views.SupportTicketViewSet, basename='ticket')
router.register('feedback', views.FeedbackViewSet, basename='feedback')
router.register('faq-categories', views.FAQCategoryViewSet, basename='faq-category')
router.register('faq-items', views.FAQItemViewSet, basename='faq-item')

urlpatterns = [
    # Must come before the router include, otherwise DefaultRouter's
    # feedback/<pk>/ and tickets/<pk>/ patterns would swallow these first.
    path('feedback/public/', views.PublicFeedbackListView.as_view(), name='feedback-public'),
    path('tickets/export/', views.TicketExportView.as_view(), name='ticket-export'),
    path('faq/public/', views.FAQPublicListView.as_view(), name='faq-public'),
    path('faq/ask/', views.FAQAskQuestionView.as_view(), name='faq-ask'),
    path('faq-items/export/', views.FAQItemExportView.as_view(), name='faq-item-export'),
    path('', include(router.urls)),
]
