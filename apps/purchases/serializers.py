from decimal import ROUND_DOWN, Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from courses.models import Course
from promocodes.models import PromoCode, PromoCodeRedemption
from students.models import Student

from .models import AccessPlan, CartItem, PlanPurchase, Purchase, PurchaseInstallment, PurchaseSettings


class AccessPlanSerializer(serializers.ModelSerializer):
    course_titles = serializers.SerializerMethodField()

    class Meta:
        model = AccessPlan
        fields = [
            'id', 'name', 'description', 'duration_days', 'price', 'currency',
            'courses', 'course_titles', 'include_all_courses', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_course_titles(self, obj):
        if obj.include_all_courses:
            return ['All courses']
        return list(obj.courses.values_list('title', flat=True))


class PublicAccessPlanSerializer(serializers.ModelSerializer):
    course_titles = serializers.SerializerMethodField()

    class Meta:
        model = AccessPlan
        fields = ['id', 'name', 'description', 'duration_days', 'price', 'currency', 'course_titles', 'include_all_courses']

    def get_course_titles(self, obj):
        if obj.include_all_courses:
            return ['All courses']
        return list(obj.courses.values_list('title', flat=True))


class PlanPurchaseSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = PlanPurchase
        fields = [
            'id', 'student', 'student_name', 'plan', 'plan_name', 'amount_paid',
            'payment_method', 'transaction_id', 'expires_at', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'student', 'expires_at', 'created_at']


class PlanCheckoutSerializer(serializers.Serializer):
    """Student self-checkout for an AccessPlan — always the plan's fixed
    price paid in full, same "Pay Once" model as course checkout."""

    plan = serializers.PrimaryKeyRelatedField(queryset=AccessPlan.objects.filter(is_active=True))
    payment_method = serializers.ChoiceField(choices=Purchase.PAYMENT_METHOD_CHOICES, default='card')

    def create(self, validated_data):
        student = self.context['request'].user
        plan = validated_data['plan']
        expires_at = timezone.now() + timezone.timedelta(days=plan.duration_days)
        return PlanPurchase.objects.create(
            student=student, plan=plan, amount_paid=plan.price,
            payment_method=validated_data['payment_method'], expires_at=expires_at,
        )


class PurchaseInstallmentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True, default=None)

    class Meta:
        model = PurchaseInstallment
        fields = ['id', 'sequence', 'amount', 'due_date', 'is_paid', 'paid_date', 'note', 'recorded_by_name']
        read_only_fields = fields


class PurchaseSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    promo_code_display = serializers.CharField(source='promo_code.code', read_only=True, default=None)
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    installments = PurchaseInstallmentSerializer(many=True, read_only=True)

    class Meta:
        model = Purchase
        fields = [
            'id', 'student', 'student_name', 'student_email', 'course', 'course_title', 'course_slug',
            'original_price', 'discount_amount', 'total_amount', 'amount_paid', 'amount_due',
            'promo_code', 'promo_code_display', 'payment_method', 'payment_status', 'transaction_id',
            'enrollment_status', 'progress_percent', 'source', 'installments', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'source', 'original_price', 'discount_amount', 'total_amount', 'amount_paid',
            'created_at', 'updated_at',
        ]


class DashboardPurchaseCreateSerializer(serializers.ModelSerializer):
    """Lets an admin manually record a purchase (e.g. an offline/manual
    enrollment, or enrolling a student converted from a Lead) — always
    tagged source='dashboard' server-side, never from the client. Unlike the
    student checkout flow (always full price, paid in full immediately),
    this supports a partial payment split into up to 2 further installments
    (3 total, counting what's paid now)."""

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    payment_plan = serializers.ChoiceField(choices=[('full', 'Full'), ('partial', 'Partial')], default='full')
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    installment_due_dates = serializers.ListField(
        child=serializers.DateField(), required=False, default=list,
        help_text='Due dates for the remaining balance after amount_paid — up to 2 (3 installments total).',
    )

    class Meta:
        model = Purchase
        fields = [
            'id', 'student', 'course', 'amount_paid', 'total_amount', 'payment_method',
            'enrollment_status', 'payment_plan', 'installment_due_dates', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        student = attrs['student']
        course = attrs['course']
        if Purchase.objects.filter(student=student, course=course).exists():
            raise serializers.ValidationError('This student already has a purchase record for this course.')

        total_amount = attrs.get('total_amount') or attrs['amount_paid']
        if attrs['amount_paid'] > total_amount:
            raise serializers.ValidationError({'amount_paid': 'Cannot exceed the total amount.'})

        if attrs.get('payment_plan') == 'partial':
            due_dates = attrs.get('installment_due_dates') or []
            if attrs['amount_paid'] >= total_amount:
                raise serializers.ValidationError(
                    {'payment_plan': 'Amount paid already covers the total — use "Full" instead.'}
                )
            if not due_dates:
                raise serializers.ValidationError(
                    {'installment_due_dates': 'Provide at least one due date for the remaining balance.'}
                )
            if len(due_dates) > 2:
                raise serializers.ValidationError(
                    {'installment_due_dates': 'A maximum of 3 installments total (1 paid now + 2 more) is supported.'}
                )

        attrs['total_amount'] = total_amount
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        due_dates = validated_data.pop('installment_due_dates', [])
        plan = validated_data.pop('payment_plan', 'full')
        total_amount = validated_data.pop('total_amount')
        amount_paid = validated_data['amount_paid']
        is_fully_paid = amount_paid >= total_amount

        purchase = Purchase.objects.create(
            student=validated_data['student'],
            course=validated_data['course'],
            original_price=total_amount,
            total_amount=total_amount,
            amount_paid=amount_paid,
            payment_method=validated_data['payment_method'],
            payment_status='completed' if is_fully_paid else 'partial',
            enrollment_status=validated_data.get('enrollment_status', 'active'),
            source=Purchase.SOURCE_DASHBOARD,
        )
        Course.objects.filter(pk=purchase.course_id).update(
            total_enrollments=purchase.course.total_enrollments + 1
        )

        if plan == 'partial' and not is_fully_paid:
            today = timezone.now().date()
            PurchaseInstallment.objects.create(
                purchase=purchase, sequence=1, amount=amount_paid,
                due_date=today, is_paid=True, paid_date=today, note='Paid at enrollment.',
            )
            remaining = total_amount - amount_paid
            count = len(due_dates)
            share = (remaining / count).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            amounts = [share] * (count - 1) + [remaining - share * (count - 1)]
            for seq, (due_date, amount) in enumerate(zip(due_dates, amounts), start=2):
                PurchaseInstallment.objects.create(
                    purchase=purchase, sequence=seq, amount=amount, due_date=due_date,
                )

        return purchase


class CheckoutSerializer(serializers.Serializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.filter(status='published'))
    promo_code = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=Purchase.PAYMENT_METHOD_CHOICES, default='free')

    def validate(self, attrs):
        student = self.context['request'].user
        course = attrs['course']

        if Purchase.objects.filter(student=student, course=course, payment_status='completed').exists():
            raise serializers.ValidationError('You are already enrolled in this course.')

        price = course.price if not course.is_free else Decimal('0')
        discount = Decimal('0')
        promo = None

        code = attrs.get('promo_code', '').strip().upper()
        if code:
            try:
                promo = PromoCode.objects.get(code=code, is_active=True)
            except PromoCode.DoesNotExist:
                raise serializers.ValidationError({'promo_code': 'Invalid or inactive promo code.'})
            if promo.minimum_purchase and price < promo.minimum_purchase:
                raise serializers.ValidationError({'promo_code': 'Order does not meet the minimum purchase amount.'})
            if promo.discount_type == PromoCode.DISCOUNT_PERCENTAGE:
                discount = (price * promo.discount_value / Decimal('100')).quantize(Decimal('0.01'))
            else:
                discount = min(promo.discount_value, price)

        attrs['original_price'] = price
        attrs['discount_amount'] = discount
        attrs['amount_paid'] = max(price - discount, Decimal('0'))
        attrs['promo_code_obj'] = promo
        return attrs

    def create(self, validated_data):
        student = self.context['request'].user
        course = validated_data['course']
        promo = validated_data.pop('promo_code_obj', None)

        purchase = Purchase.objects.create(
            student=student,
            course=course,
            original_price=validated_data['original_price'],
            discount_amount=validated_data['discount_amount'],
            amount_paid=validated_data['amount_paid'],
            total_amount=validated_data['amount_paid'],
            promo_code=promo,
            payment_method=validated_data['payment_method'],
            payment_status='completed',
            source=Purchase.SOURCE_WEBSITE,
        )

        Course.objects.filter(pk=course.pk).update(total_enrollments=course.total_enrollments + 1)

        if promo:
            PromoCodeRedemption.objects.create(
                promo_code=promo,
                student=student,
                order_amount=purchase.original_price,
                discount_amount=purchase.discount_amount,
                status=PromoCodeRedemption.STATUS_COMPLETED,
                completed_at=timezone.now(),
            )

        return purchase


class CartItemSerializer(serializers.ModelSerializer):
    """Student-facing shape — mirrors WishlistItemSerializer."""

    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    course_thumbnail = serializers.CharField(source='course.thumbnail_url', read_only=True)
    course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'course', 'course_title', 'course_slug', 'course_thumbnail', 'course_price', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_course(self, value):
        student = self.context['request'].user
        if CartItem.objects.filter(student=student, course=value).exists():
            raise serializers.ValidationError('This course is already in your cart.')
        return value


class CartItemAdminSerializer(serializers.ModelSerializer):
    """Dashboard-facing shape — one row per student's cart item, with enough
    to compute "days in cart" and total cart value client-side."""

    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id', 'student', 'student_name', 'student_email', 'course', 'course_title',
            'course_price', 'reminder_sent_at', 'created_at',
        ]
        read_only_fields = fields


class PurchaseSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseSettings
        fields = [
            'tax_rate', 'currency', 'abandoned_cart_reminder_enabled',
            'cart_reminder_days_threshold', 'updated_at',
        ]
        read_only_fields = ['updated_at']
