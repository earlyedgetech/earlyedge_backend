from datetime import timedelta

import django_filters
from common.exports import export_rows
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember

from .models import PromoCode, PromoCodeRedemption
from .serializers import PromoCodePublicSerializer, PromoCodeSerializer

PROMOCODES_PERMISSION = 'manage_promocodes'
PROMOCODE_SEARCH_FIELDS = ['code', 'description']


class PromoCodeFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = PromoCode
        fields = ['is_active', 'platform', 'start_date', 'end_date']


def get_filtered_promo_codes(request):
    """Same search/date-range filtering as the promo code list view, or a
    specific set of rows via `ids` (export-selected, ignores other filters)."""

    ids_param = request.query_params.get('ids')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return PromoCode.objects.filter(id__in=ids)

    queryset = PromoCodeFilter(request.query_params, queryset=PromoCode.objects.all()).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in PROMOCODE_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class PromoCodeViewSet(viewsets.ModelViewSet):
    """All Promo Codes — dashboard-only CRUD."""

    queryset = PromoCode.objects.all()
    serializer_class = PromoCodeSerializer
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(PROMOCODES_PERMISSION)]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PromoCodeFilter
    search_fields = PROMOCODE_SEARCH_FIELDS
    ordering_fields = ['created_at', 'start_date', 'end_date', 'code']


class PromoCodeExportView(APIView):
    """Exports promo codes matching the current search/date filters (or a
    specific selected set via `ids`) as CSV, Excel, or PDF."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(PROMOCODES_PERMISSION)]

    HEADERS = [
        'ID', 'Code', 'Description', 'Discount Type', 'Discount Value', 'Platform',
        'Active', 'Show In Cart', 'Total Uses', 'Start Date', 'End Date', 'Created At',
    ]
    FIELDS = [
        'id', 'code', 'description', 'discount_type', 'discount_value', 'platform',
        'is_active', 'show_in_cart', 'total_uses', 'start_date', 'end_date', 'created_at',
    ]

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_promo_codes(request).order_by('-created_at')
        rows = PromoCodeSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching promo codes to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'promo_codes')


class PromoCodePublicListView(generics.ListAPIView):
    """Codes a shopper should see suggested in their cart at checkout — no
    auth required. Only currently-active codes explicitly marked
    show_in_cart, and only while within their date window (if one is set)."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PromoCodePublicSerializer
    pagination_class = None

    def get_queryset(self):
        today = timezone.localdate()
        return PromoCode.objects.filter(
            is_active=True, show_in_cart=True,
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=today)
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).order_by('-created_at')


class PromoCodeAnalyticsView(APIView):
    """Stats + usage-over-time series for the Promo Code Analytics dashboard."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(PROMOCODES_PERMISSION)]

    RANGE_DAYS = {'30d': 30, '90d': 90}

    def get(self, request):
        redemptions = PromoCodeRedemption.objects.all()
        completed = redemptions.filter(status=PromoCodeRedemption.STATUS_COMPLETED)

        total_applied = redemptions.count()
        total_redemptions = completed.count()
        conversion_rate = round((total_redemptions / total_applied) * 100, 1) if total_applied else 0
        total_discounted = completed.aggregate(total=Sum('discount_amount'))['total'] or 0

        usage_qs = completed
        range_param = request.query_params.get('range', '90d')
        days = self.RANGE_DAYS.get(range_param)
        if days is not None:
            since = timezone.now() - timedelta(days=days)
            usage_qs = usage_qs.filter(completed_at__gte=since)

        usage_over_time = (
            usage_qs
            .annotate(date=TruncDate('completed_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        return Response({
            'total_codes_active': PromoCode.objects.filter(is_active=True).count(),
            'total_redemptions': total_redemptions,
            'conversion_rate': conversion_rate,
            'total_discounted': total_discounted,
            'usage_over_time': list(usage_over_time),
        })
