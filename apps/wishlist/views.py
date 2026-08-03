import django_filters
from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from common.exports import export_rows
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WishlistItem
from .serializers import WishlistItemAdminSerializer, WishlistItemSerializer

WISHLIST_SEARCH_FIELDS = ['student__full_name', 'student__email', 'course__title']


class WishlistListCreateView(generics.ListCreateAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = WishlistItemSerializer
    pagination_class = None

    def get_queryset(self):
        return WishlistItem.objects.select_related('course').filter(student=self.request.user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


class WishlistDeleteView(generics.DestroyAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]

    def get_queryset(self):
        return WishlistItem.objects.filter(student=self.request.user)


class WishlistStatsView(APIView):
    """Most-wishlisted courses — a signal of purchase intent for the admin
    dashboard's Cart & Wishlist page."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]

    def get(self, request):
        rows = (
            WishlistItem.objects.values('course_id', 'course__title', 'course__price')
            .annotate(wishlist_count=Count('id'))
            .order_by('-wishlist_count')[:50]
        )
        return Response([
            {
                'course_id': row['course_id'],
                'course_title': row['course__title'],
                'course_price': row['course__price'],
                'wishlist_count': row['wishlist_count'],
            }
            for row in rows
        ])


class WishlistItemFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = WishlistItem
        fields = ['start_date', 'end_date']


def get_filtered_wishlist_items(request):
    ids_param = request.query_params.get('ids')
    base = WishlistItem.objects.select_related('student', 'course')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return base.filter(id__in=ids)

    queryset = WishlistItemFilter(request.query_params, queryset=base).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in WISHLIST_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class WishlistAdminListView(generics.ListAPIView):
    """Every student's wishlist contents — the per-item counterpart to
    WishlistStatsView's aggregate report, for the Cart & Wishlist admin
    page's per-item table + total-value calculation."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]
    serializer_class = WishlistItemAdminSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = WishlistItemFilter
    search_fields = WISHLIST_SEARCH_FIELDS
    queryset = WishlistItem.objects.select_related('student', 'course').order_by('-created_at')


class WishlistItemExportView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]

    HEADERS = ['ID', 'Student', 'Email', 'Course', 'Price', 'Added At']
    FIELDS = ['id', 'student_name', 'student_email', 'course_title', 'course_price', 'created_at']

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_wishlist_items(request).order_by('-created_at')
        rows = WishlistItemAdminSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching wishlist items to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'wishlist_items')
