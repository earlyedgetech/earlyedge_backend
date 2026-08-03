import django_filters
from common.exports import export_rows
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from rest_framework.exceptions import AuthenticationFailed

from .models import FAQCategory, FAQItem, Feedback, SupportTicket
from .serializers import (
    FAQAskQuestionSerializer,
    FAQCategoryPublicSerializer,
    FAQCategorySerializer,
    FAQItemSerializer,
    FeedbackPublicSerializer,
    FeedbackSerializer,
    SupportTicketSerializer,
)

FAQ_PERMISSION = 'manage_support'
SUPPORT_PERMISSION = 'manage_support'
TICKET_SEARCH_FIELDS = ['subject', 'name', 'email', 'message']
FAQ_ITEM_SEARCH_FIELDS = ['question', 'answer', 'asked_by_name', 'asked_by_email']


class FAQItemFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = FAQItem
        fields = ['status', 'category', 'start_date', 'end_date']


def get_filtered_faq_items(request):
    """Same search/date-range filtering as the FAQ item list view, or a
    specific set of rows via `ids` (export-selected, ignores other filters)."""

    ids_param = request.query_params.get('ids')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return FAQItem.objects.filter(id__in=ids)

    queryset = FAQItemFilter(request.query_params, queryset=FAQItem.objects.all()).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in FAQ_ITEM_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class TicketFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = SupportTicket
        fields = ['status', 'source', 'start_date', 'end_date']


def get_filtered_tickets(request):
    """Same search/date-range filtering as the ticket list view, or a
    specific set of rows via `ids` (export-selected, ignores other filters)."""

    ids_param = request.query_params.get('ids')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return SupportTicket.objects.filter(id__in=ids)

    queryset = TicketFilter(request.query_params, queryset=SupportTicket.objects.all()).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in TICKET_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class FAQCategoryViewSet(viewsets.ModelViewSet):
    """Dashboard CRUD for FAQ categories, each with its nested questions."""

    queryset = FAQCategory.objects.all().prefetch_related('items')
    serializer_class = FAQCategorySerializer
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(FAQ_PERMISSION)]


class FAQItemViewSet(viewsets.ModelViewSet):
    """Dashboard CRUD for individual FAQ questions within a category —
    covers both already-published items and pending student-asked ones
    (filter with ?status=pending to list just the latter)."""

    queryset = FAQItem.objects.all().select_related('category')
    serializer_class = FAQItemSerializer
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(FAQ_PERMISSION)]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = FAQItemFilter
    search_fields = FAQ_ITEM_SEARCH_FIELDS


class FAQItemExportView(APIView):
    """Exports FAQ items (typically the pending/student-asked ones) matching
    the current search/date filters, or a specific selected set via `ids`."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(FAQ_PERMISSION)]

    HEADERS = ['ID', 'Question', 'Answer', 'Status', 'Asked By', 'Asked By Email', 'Created At']
    FIELDS = ['id', 'question', 'answer', 'status', 'asked_by_name', 'asked_by_email', 'created_at']

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_faq_items(request).order_by('-created_at')
        rows = FAQItemSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching FAQ items to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'faq_items')


class FAQAskQuestionView(generics.CreateAPIView):
    """Public "Ask a Question" submission — no login required. Lands as a
    pending item with no category/answer until an admin publishes it."""

    serializer_class = FAQAskQuestionSerializer
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        serializer.save(status=FAQItem.STATUS_PENDING, category=None, answer='')


class FAQPublicListView(generics.ListAPIView):
    """Public FAQ page — categories with only their published questions."""

    queryset = FAQCategory.objects.all().prefetch_related('items')
    serializer_class = FAQCategoryPublicSerializer
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class _OptionalAdminMemberJWTAuthentication(AdminMemberJWTAuthentication):
    """Same as AdminMemberJWTAuthentication, except a token that simply isn't
    an admin's (e.g. a logged-in student submitting the contact form) is
    treated as "no credentials" rather than a hard failure. Needed because
    DRF runs authentication before permissions — without this, a non-admin
    Bearer token on SupportTicketViewSet.create would 401 with "Invalid
    token type for this endpoint." even though create is AllowAny."""

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None


class SupportTicketViewSet(viewsets.ModelViewSet):
    """Contact/support form. `create` is open to anonymous website visitors
    (no auth token required, and any non-admin token present is ignored
    rather than rejected — see _OptionalAdminMemberJWTAuthentication); every
    other action — list/retrieve/update/delete — is dashboard-admin only.
    `source` is tagged server-side from whether a valid admin JWT was
    presented, never trusted from the client.
    """

    queryset = SupportTicket.objects.all().order_by('-created_at')
    serializer_class = SupportTicketSerializer
    authentication_classes = [AdminMemberJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = TicketFilter
    search_fields = TICKET_SEARCH_FIELDS

    def initialize_request(self, request, *args, **kwargs):
        # `self.action` isn't set yet at this point (ViewSetMixin sets it
        # *after* calling get_authenticators() via this same method's
        # super() call) — POST on this viewset's collection URL is
        # exclusively `create`, so the raw method is a safe stand-in.
        self._is_create_request = request.method == 'POST'
        return super().initialize_request(request, *args, **kwargs)

    def get_authenticators(self):
        if getattr(self, '_is_create_request', False):
            return [_OptionalAdminMemberJWTAuthentication()]
        return super().get_authenticators()

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [IsAdminMember(), HasDashboardPermission(SUPPORT_PERMISSION)]

    def perform_create(self, serializer):
        user = self.request.user
        is_admin_authored = getattr(user, 'is_authenticated', False)
        source = SupportTicket.SOURCE_DASHBOARD if is_admin_authored else SupportTicket.SOURCE_WEBSITE
        ticket = serializer.save(source=source)

        if not is_admin_authored:
            from admin_security.notifications import notify_admins_with_permission

            notify_admins_with_permission(
                SUPPORT_PERMISSION, f'New support ticket: {ticket.subject}',
                link='/-/admin-dashboard/support_feedback/support_tickets',
            )


class TicketExportView(APIView):
    """Exports support tickets matching the current search/date filters (or
    a specific selected set via `ids`) as CSV, Excel, or PDF."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SUPPORT_PERMISSION)]

    HEADERS = ['ID', 'Subject', 'Name', 'Email', 'Phone', 'Status', 'Source', 'Message', 'Created At']
    FIELDS = ['id', 'subject', 'name', 'email', 'phone', 'status', 'source', 'message', 'created_at']

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_tickets(request).order_by('-created_at')
        rows = SupportTicketSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching tickets to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'support_tickets')


class FeedbackViewSet(viewsets.ModelViewSet):
    """Testimonials submitted by a logged-in student about themselves.
    Students only ever see/manage their own feedback here — the home page
    uses PublicFeedbackListView instead."""

    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = FeedbackSerializer

    def get_queryset(self):
        return Feedback.objects.filter(student=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        student = self.request.user
        serializer.save(student=student, name=student.full_name, email=student.email)


class PublicFeedbackListView(generics.ListAPIView):
    """Home page widget — only feedback an admin has marked visible."""

    queryset = Feedback.objects.filter(visible=True).order_by('-created_at')
    serializer_class = FeedbackPublicSerializer
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
