from datetime import timedelta

from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from purchases.models import Purchase
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Refund
from .serializers import PaymentSerializer, RefundSerializer

REVENUE_PERMISSION = 'manage_revenue'


class PaymentListView(generics.ListAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(REVENUE_PERMISSION)]
    serializer_class = PaymentSerializer
    queryset = Purchase.objects.select_related('student', 'course')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student', 'payment_status', 'payment_method', 'course']


class RefundListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(REVENUE_PERMISSION)]
    serializer_class = RefundSerializer
    queryset = Refund.objects.select_related('purchase__student', 'purchase__course', 'processed_by')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']


class RefundDetailView(generics.RetrieveUpdateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(REVENUE_PERMISSION)]
    serializer_class = RefundSerializer
    queryset = Refund.objects.select_related('purchase__student', 'purchase__course', 'processed_by')

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.status in ('approved', 'completed') and not instance.processed_at:
            instance.processed_by = self.request.user
            instance.processed_at = timezone.now()
            instance.save(update_fields=['processed_by', 'processed_at'])
            if instance.status == 'completed':
                Purchase.objects.filter(pk=instance.purchase_id).update(payment_status='refunded')


class RevenueAnalyticsView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(REVENUE_PERMISSION)]

    RANGE_DAYS = {'30d': 30, '90d': 90}

    def get(self, request):
        completed = Purchase.objects.filter(payment_status='completed')

        range_param = request.query_params.get('range', '30d')
        days = self.RANGE_DAYS.get(range_param)
        qs = completed
        if days is not None:
            since = timezone.now() - timedelta(days=days)
            qs = qs.filter(created_at__gte=since)

        revenue_over_time = (
            qs.annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(total=Sum('amount_paid'), count=Count('id'))
            .order_by('date')
        )

        return Response({
            'total_revenue': completed.aggregate(total=Sum('amount_paid'))['total'] or 0,
            'total_transactions': completed.count(),
            'total_refunded': Refund.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0,
            'pending_refunds': Refund.objects.filter(status='pending').count(),
            'revenue_over_time': list(revenue_over_time),
        })
