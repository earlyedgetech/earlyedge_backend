import django_filters
from common.exports import export_rows
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember
from rest_framework import filters, generics
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdminLog, AdminMember, AdminNotification, Permission, Role, SecuritySettings
from .serializers import (
    AdminMemberSerializer,
    AdminNotificationSerializer,
    PermissionSerializer,
    RoleSerializer,
    AdminLogSerializer,
    SecuritySettingsSerializer,
)


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


ADMIN_LOG_SEARCH_FIELDS = ['action', 'user_name', 'user_type', 'ip_address', 'status']


def derive_log_module(action):
    """Best-effort module name from an action string like 'GET
    /leads/dashboard/leads/' — the first path segment lines up with the
    URL-prefix each app is mounted under in config/urls.py."""
    try:
        _, path = action.split(' ', 1)
    except ValueError:
        return ''
    segment = path.strip('/').split('/', 1)[0]
    return segment.replace('-', '_')[:30]


class AdminLogFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = AdminLog
        fields = ['start_date', 'end_date', 'user_name', 'status', 'module']


def get_filtered_admin_logs(request):
    """Applies the same search/date-range filtering used by the log list
    view, or narrows to a specific set of rows when `ids` is given (used by
    the "export selected" action, which should ignore any active filters)."""

    ids_param = request.query_params.get('ids')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return AdminLog.objects.filter(id__in=ids)

    queryset = AdminLogFilter(request.query_params, queryset=AdminLog.objects.all()).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in ADMIN_LOG_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class AdminLogListCreateView(generics.ListCreateAPIView):
    """Audit trail endpoint. IP address is taken from the request,
    never trusted from the client payload."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_admin_logs')]
    serializer_class = AdminLogSerializer
    queryset = AdminLog.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = AdminLogFilter
    search_fields = ADMIN_LOG_SEARCH_FIELDS

    def perform_create(self, serializer):
        serializer.save(
            ip_address=get_client_ip(self.request),
            module=derive_log_module(serializer.validated_data.get('action', '')),
        )


class MyAdminLogListView(generics.ListAPIView):
    """Read-only — a dashboard user's own activity trail. Available to any
    authenticated admin member (no manage_admin_logs permission required),
    unlike the full audit log which is admin-only and lets you view/moderate
    everyone's activity."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = AdminLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = AdminLogFilter
    search_fields = ADMIN_LOG_SEARCH_FIELDS

    def get_queryset(self):
        return AdminLog.objects.filter(user_name=self.request.user.full_name)


class AdminLogExportView(APIView):
    """Exports admin logs matching the current search/date filters (or a
    specific selected set via `ids`) as CSV, Excel, or PDF."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_admin_logs')]

    HEADERS = ['ID', 'Action', 'User', 'User Type', 'Timestamp', 'IP Address', 'Status']
    FIELDS = ['id', 'action', 'user_name', 'user_type', 'timestamp', 'ip_address', 'status']

    def get(self, request):
        # Note: cannot be named `format` — DRF reserves that query param for
        # its own content-negotiation (URL_FORMAT_OVERRIDE) and 404s on it.
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_admin_logs(request).order_by('-created_at')
        rows = AdminLogSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching logs to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'admin_logs')


class SecuritySettingsView(APIView):
    """Singleton resource — only GET/PATCH make sense since exactly one
    settings row always exists (see SecuritySettings.get_solo)."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_security_settings')]

    def get(self, request):
        serializer = SecuritySettingsSerializer(SecuritySettings.get_solo())
        return Response(serializer.data)

    def patch(self, request):
        serializer = SecuritySettingsSerializer(
            SecuritySettings.get_solo(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PermissionListView(generics.ListAPIView):
    """Read-only list of assignable permissions, used to populate role forms."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_roles')]
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    pagination_class = None


class RoleListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_roles')]
    queryset = Role.objects.prefetch_related('permissions').all()
    serializer_class = RoleSerializer


class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_roles')]
    queryset = Role.objects.prefetch_related('permissions').all()
    serializer_class = RoleSerializer


class AdminMemberListView(generics.ListAPIView):
    """Dashboard user directory — who's provisioned, their role, and
    whether they're active. Feeds the Force Logout control in Security
    Settings (there's no separate "team members" page)."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_members')]
    queryset = AdminMember.objects.select_related('role').order_by('full_name')
    serializer_class = AdminMemberSerializer
    pagination_class = None


class AdminMemberForceLogoutView(APIView):
    """Immediately ends every active session (access + refresh tokens
    already issued) for one dashboard admin — see AdminMemberJWTAuthentication
    and _TypedTokenRefreshSerializer, both of which reject any token issued
    before `force_logout_at`. Scoped to AdminMember only; students have no
    equivalent control here."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_members')]

    def post(self, request, pk):
        try:
            member = AdminMember.objects.get(pk=pk)
        except AdminMember.DoesNotExist:
            raise NotFound('Admin member not found.')

        member.force_logout_at = timezone.now()
        member.save(update_fields=['force_logout_at'])
        return Response(AdminMemberSerializer(member).data)


class MyNotificationListView(generics.ListAPIView):
    """Dashboard Navbar bell feed — polled periodically for near-real-time
    updates (no websocket infra in this project). Capped at the 50 most
    recent so the poll stays cheap."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = AdminNotificationSerializer
    pagination_class = None

    def get_queryset(self):
        return AdminNotification.objects.filter(recipient=self.request.user)[:50]


class MyNotificationUnreadCountView(APIView):
    """Cheap, frequent-poll-friendly endpoint — just the badge count."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    def get(self, request):
        count = AdminNotification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_count': count})


class NotificationMarkReadView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    def post(self, request, pk):
        try:
            notification = AdminNotification.objects.get(pk=pk, recipient=request.user)
        except AdminNotification.DoesNotExist:
            raise NotFound('Notification not found.')
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return Response(AdminNotificationSerializer(notification).data)


class NotificationMarkAllReadView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    def post(self, request):
        AdminNotification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'detail': 'All notifications marked as read.'})
