import django_filters
from authentication.authentication import AdminMemberJWTAuthentication, StudentJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember, IsStudent
from common.exports import export_rows
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AccessPlan, CartItem, PlanPurchase, Purchase, PurchaseInstallment, PurchaseSettings
from .serializers import (
    AccessPlanSerializer,
    CartItemAdminSerializer,
    CartItemSerializer,
    CheckoutSerializer,
    DashboardPurchaseCreateSerializer,
    PlanCheckoutSerializer,
    PlanPurchaseSerializer,
    PublicAccessPlanSerializer,
    PurchaseSerializer,
    PurchaseSettingsSerializer,
)
from .tasks import send_cart_reminder_email

PURCHASE_SEARCH_FIELDS = ['student__full_name', 'student__email', 'course__title']


def _instructor_profile(user):
    return getattr(user, 'instructor_profile', None)


# ---------------------------------------------------------------------------
# Student-facing (checkout / my purchases / cart)
# ---------------------------------------------------------------------------

class CheckoutView(generics.CreateAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = CheckoutSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = serializer.save()
        return Response(PurchaseSerializer(purchase).data, status=201)


class MyPurchasesListView(generics.ListAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = PurchaseSerializer

    def get_queryset(self):
        return Purchase.objects.select_related('course', 'promo_code').filter(student=self.request.user)


class PublicAccessPlanListView(generics.ListAPIView):
    """Powers the Pricing page's plan tiers, alongside individual course
    pricing (which stays exactly as-is — buying one course directly is
    still always available and unaffected by plans)."""

    permission_classes = [AllowAny]
    serializer_class = PublicAccessPlanSerializer
    queryset = AccessPlan.objects.filter(is_active=True).prefetch_related('courses')
    pagination_class = None


class PlanCheckoutView(generics.CreateAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = PlanCheckoutSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_purchase = serializer.save()
        return Response(PlanPurchaseSerializer(plan_purchase).data, status=201)


class MyPlanPurchasesListView(generics.ListAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = PlanPurchaseSerializer
    pagination_class = None

    def get_queryset(self):
        return PlanPurchase.objects.select_related('plan').filter(student=self.request.user)


class CartItemListCreateView(generics.ListCreateAPIView):
    """A student's own cart — mirrors wishlist.WishlistListCreateView."""

    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]
    serializer_class = CartItemSerializer
    pagination_class = None

    def get_queryset(self):
        return CartItem.objects.select_related('course').filter(student=self.request.user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


class CartItemDeleteView(generics.DestroyAPIView):
    authentication_classes = [StudentJWTAuthentication]
    permission_classes = [IsStudent]

    def get_queryset(self):
        return CartItem.objects.filter(student=self.request.user)


# ---------------------------------------------------------------------------
# Dashboard (RBAC) — admins see all purchases; instructors see purchases only
# for the courses they teach, i.e. their own enrolled students.
# ---------------------------------------------------------------------------

class PurchaseFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Purchase
        fields = ['student', 'course', 'payment_status', 'enrollment_status', 'source', 'start_date', 'end_date']


def _scoped_purchases(user):
    base = Purchase.objects.select_related('student', 'course', 'promo_code')
    if user.has_permission('manage_purchases') or user.has_permission('manage_students'):
        return base.all()
    if user.has_permission('manage_own_courses'):
        instructor = _instructor_profile(user)
        return base.filter(course__instructor=instructor) if instructor else base.none()
    raise PermissionDenied('You do not have permission to view purchases.')


def get_filtered_purchases(request):
    """Same scoping + search/date-range filtering as the purchase list view,
    or a specific set of rows via `ids` (export-selected, ignores filters)."""

    user = request.user
    ids_param = request.query_params.get('ids')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return _scoped_purchases(user).filter(id__in=ids)

    queryset = PurchaseFilter(request.query_params, queryset=_scoped_purchases(user)).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in PURCHASE_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class PurchaseListView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = PurchaseFilter
    search_fields = PURCHASE_SEARCH_FIELDS

    def get_serializer_class(self):
        return DashboardPurchaseCreateSerializer if self.request.method == 'POST' else PurchaseSerializer

    def get_queryset(self):
        return _scoped_purchases(self.request.user)

    def create(self, request, *args, **kwargs):
        if not request.user.has_permission('manage_purchases'):
            raise PermissionDenied('Only an admin can manually record a purchase.')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = serializer.save()
        return Response(PurchaseSerializer(purchase).data, status=201)


class PurchaseExportView(APIView):
    """Exports purchases matching the current search/date/scope filters (or
    a specific selected set via `ids`) as CSV, Excel, or PDF."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]

    HEADERS = [
        'ID', 'Student', 'Email', 'Course', 'Amount Paid', 'Payment Method',
        'Payment Status', 'Enrollment Status', 'Source', 'Created At',
    ]
    FIELDS = [
        'id', 'student_name', 'student_email', 'course_title', 'amount_paid', 'payment_method',
        'payment_status', 'enrollment_status', 'source', 'created_at',
    ]

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_purchases(request).order_by('-created_at')
        rows = PurchaseSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching purchases to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'purchases')


class PurchaseDetailView(generics.RetrieveUpdateAPIView):
    """Update is intentionally narrow — enrollment_status/progress only,
    handled implicitly since payment fields are read-only on the serializer."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember]
    serializer_class = PurchaseSerializer

    def get_queryset(self):
        return _scoped_purchases(self.request.user)

    def perform_update(self, serializer):
        was_completed = serializer.instance.enrollment_status == 'completed'
        purchase = serializer.save()
        if not was_completed and purchase.enrollment_status == 'completed':
            from settings_app.notifications import send_notification

            send_notification('course_completion', email=purchase.student.email, context={
                'student_name': purchase.student.full_name,
                'course_title': purchase.course.title,
            })


class PurchaseInstallmentPayView(APIView):
    """Marks one planned installment as collected — increments the parent
    Purchase's amount_paid and flips payment_status to 'completed' once the
    total is covered."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]

    def post(self, request, purchase_id, installment_id):
        try:
            installment = PurchaseInstallment.objects.select_related('purchase').get(
                pk=installment_id, purchase_id=purchase_id,
            )
        except PurchaseInstallment.DoesNotExist:
            raise NotFound('Installment not found.')

        if not installment.is_paid:
            installment.is_paid = True
            installment.paid_date = timezone.now().date()
            installment.recorded_by = request.user
            installment.save(update_fields=['is_paid', 'paid_date', 'recorded_by'])

            purchase = installment.purchase
            purchase.amount_paid = purchase.amount_paid + installment.amount
            if purchase.amount_paid >= purchase.total_amount:
                purchase.payment_status = 'completed'
            purchase.save(update_fields=['amount_paid', 'payment_status'])

        return Response(PurchaseSerializer(installment.purchase).data)


class PurchaseReminderView(APIView):
    """Admin-triggered "send balance reminder now" — uses the
    'purchase_balance_reminder' template from Settings > Message
    Automations, same pattern as CartItemNotifyView's abandoned-cart nudge."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]

    def post(self, request, pk):
        try:
            purchase = Purchase.objects.select_related('student', 'course').get(pk=pk)
        except Purchase.DoesNotExist:
            raise NotFound('Purchase not found.')

        amount_due = purchase.amount_due
        if amount_due <= 0:
            return Response({'detail': 'This purchase has no balance due.'}, status=400)

        from settings_app.notifications import send_notification

        next_installment = purchase.installments.filter(is_paid=False).order_by('sequence').first()
        sent = send_notification('purchase_balance_reminder', email=purchase.student.email, context={
            'student_name': purchase.student.full_name,
            'course_title': purchase.course.title,
            'amount_due': str(amount_due),
            'due_date': next_installment.due_date.isoformat() if next_installment and next_installment.due_date else 'as soon as possible',
        })
        if not sent:
            return Response(
                {'detail': 'Balance reminder template is inactive — enable it in Settings > Message Automations.'},
                status=400,
            )
        return Response({'detail': f'Reminder sent to {purchase.student.email}.'})


class PurchaseAnalyticsView(APIView):
    """Stats + revenue-over-time series for the Purchase Analytics dashboard."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]

    RANGE_DAYS = {'30d': 30, '90d': 90}

    def get(self, request):
        from datetime import timedelta

        completed = Purchase.objects.filter(payment_status='completed')

        total_purchases = completed.count()
        total_revenue = completed.aggregate(total=Sum('amount_paid'))['total'] or 0
        active_enrollments = completed.filter(enrollment_status='active').count()

        top_course_row = (
            completed.values('course__title')
            .annotate(purchases=Count('id'), revenue=Sum('amount_paid'))
            .order_by('-purchases')
            .first()
        )
        top_course = (
            {'title': top_course_row['course__title'], 'purchases': top_course_row['purchases']}
            if top_course_row else None
        )

        revenue_qs = completed
        range_param = request.query_params.get('range', '90d')
        days = self.RANGE_DAYS.get(range_param)
        if days is not None:
            since = timezone.now() - timedelta(days=days)
            revenue_qs = revenue_qs.filter(created_at__gte=since)

        revenue_over_time = (
            revenue_qs
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(revenue=Sum('amount_paid'), count=Count('id'))
            .order_by('date')
        )

        revenue_by_course = (
            completed.values('course__title')
            .annotate(revenue=Sum('amount_paid'), purchases=Count('id'))
            .order_by('-revenue')[:8]
        )
        revenue_by_course = [
            {'course_title': row['course__title'], 'revenue': row['revenue'], 'purchases': row['purchases']}
            for row in revenue_by_course
        ]

        return Response({
            'total_purchases': total_purchases,
            'total_revenue': total_revenue,
            'active_enrollments': active_enrollments,
            'top_course': top_course,
            'revenue_over_time': list(revenue_over_time),
            'revenue_by_course': list(revenue_by_course),
        })


class PurchaseSettingsView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]

    def get(self, request):
        return Response(PurchaseSettingsSerializer(PurchaseSettings.get_solo()).data)

    def patch(self, request):
        serializer = PurchaseSettingsSerializer(PurchaseSettings.get_solo(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Dashboard — Access Plans (pricing tiers) + Plan Purchases
# ---------------------------------------------------------------------------

class AccessPlanListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]
    serializer_class = AccessPlanSerializer
    queryset = AccessPlan.objects.prefetch_related('courses').all()
    pagination_class = None


class AccessPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]
    serializer_class = AccessPlanSerializer
    queryset = AccessPlan.objects.prefetch_related('courses').all()


class PlanPurchaseListView(generics.ListAPIView):
    """Dashboard visibility into who bought which plan — mirrors
    PurchaseListView's read side, no manual-create counterpart since plans
    are always self-checkout (an admin enrolling someone by hand uses a
    regular per-course Purchase instead)."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]
    serializer_class = PlanPurchaseSerializer
    queryset = PlanPurchase.objects.select_related('student', 'plan')


# ---------------------------------------------------------------------------
# Dashboard — Cart (admin visibility + abandonment-reminder controls)
# ---------------------------------------------------------------------------

CART_SEARCH_FIELDS = ['student__full_name', 'student__email', 'course__title']


class CartItemFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = CartItem
        fields = ['start_date', 'end_date']


def get_filtered_cart_items(request):
    ids_param = request.query_params.get('ids')
    base = CartItem.objects.select_related('student', 'course')
    if ids_param:
        ids = [int(pk) for pk in ids_param.split(',') if pk.strip().isdigit()]
        return base.filter(id__in=ids)

    queryset = CartItemFilter(request.query_params, queryset=base).qs

    search = request.query_params.get('search')
    if search:
        query = Q()
        for field in CART_SEARCH_FIELDS:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    return queryset


class CartAdminListView(generics.ListAPIView):
    """Every student's cart contents, for the dashboard's Cart & Wishlist
    page — total cart value and "days in cart" are computed client-side
    from this full list."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]
    serializer_class = CartItemAdminSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = CartItemFilter
    search_fields = CART_SEARCH_FIELDS
    queryset = CartItem.objects.select_related('student', 'course').order_by('-created_at')


class CartItemExportView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]

    HEADERS = ['ID', 'Student', 'Email', 'Course', 'Price', 'Reminder Sent At', 'Added At']
    FIELDS = ['id', 'student_name', 'student_email', 'course_title', 'course_price', 'reminder_sent_at', 'created_at']

    def get(self, request):
        export_format = request.query_params.get('export_format', 'csv').lower()
        queryset = get_filtered_cart_items(request).order_by('-created_at')
        rows = CartItemAdminSerializer(queryset, many=True).data

        if not rows:
            return Response({'detail': 'No matching cart items to export.'}, status=400)

        return export_rows(export_format, self.HEADERS, self.FIELDS, rows, 'cart_items')


class CartItemNotifyView(APIView):
    """Admin-triggered "send reminder now" for one cart item — independent
    of the automatic scheduled sweep (apps/purchases/tasks.py), so an admin
    can nudge a student any time, not just once the item crosses the
    configured age threshold."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission('manage_purchases')]

    def post(self, request, pk):
        try:
            item = CartItem.objects.select_related('student', 'course').get(pk=pk)
        except CartItem.DoesNotExist:
            raise NotFound('Cart item not found.')

        send_cart_reminder_email(item)
        item.reminder_sent_at = timezone.now()
        item.save(update_fields=['reminder_sent_at'])
        return Response(CartItemAdminSerializer(item).data)
