from common.models import TimeStampedModel
from django.db import models


class Purchase(TimeStampedModel):
    PAYMENT_METHOD_CHOICES = (
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Wallet'),
        ('free', 'Free'),
    )
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    ENROLLMENT_STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    SOURCE_WEBSITE = 'website'
    SOURCE_DASHBOARD = 'dashboard'
    SOURCE_CHOICES = (
        (SOURCE_WEBSITE, 'Website'),
        (SOURCE_DASHBOARD, 'Dashboard'),
    )

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='purchases')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='purchases')

    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Total price owed for this enrollment — fixed at creation time, independent of '
                   'later course price changes. amount_paid tracks running total actually collected so far.',
    )
    promo_code = models.ForeignKey(
        'promocodes.PromoCode', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases'
    )

    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, default='free')
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=255, blank=True)

    enrollment_status = models.CharField(max_length=10, choices=ENROLLMENT_STATUS_CHOICES, default='active')
    progress_percent = models.PositiveSmallIntegerField(default=0)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_WEBSITE)

    class Meta:
        db_table = 'purchases'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'course'], name='unique_student_course_purchase')
        ]

    def __str__(self):
        return f'{self.student} - {self.course} ({self.payment_status})'

    @property
    def amount_due(self):
        return self.total_amount - self.amount_paid


class PurchaseInstallment(TimeStampedModel):
    """One planned/collected payment against a Purchase's total_amount. The
    first installment (sequence=1) represents whatever was paid at purchase
    time and is created already-paid; later ones are planned (due_date,
    unpaid) until an admin marks them collected."""

    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='installments')
    sequence = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        db_table = 'purchase_installments'
        ordering = ['sequence']
        constraints = [
            models.UniqueConstraint(fields=['purchase', 'sequence'], name='unique_purchase_installment_sequence'),
        ]

    def __str__(self):
        return f'{self.purchase} - installment {self.sequence}'


class AccessPlan(TimeStampedModel):
    """A time-boxed multi-course pass — e.g. "Starter Pass" (6 months,
    a curated set of courses) or "Advanced Pass" (1 year, everything).
    Still a one-time payment (see PlanPurchase), not a recurring
    subscription — no recurring-billing gateway integration exists in this
    project. Individual courses remain purchasable for lifetime access via
    the existing Purchase flow, untouched by this model."""

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    duration_days = models.PositiveIntegerField(help_text='e.g. 180 for a 6-month pass, 365 for a 1-year pass.')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    courses = models.ManyToManyField(
        'courses.Course', related_name='access_plans', blank=True,
        help_text='Which courses this plan grants access to. Ignored if "include all courses" is set.',
    )
    include_all_courses = models.BooleanField(
        default=False, help_text='Grants access to every course (current and future), e.g. for an "Advanced" tier.'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'access_plans'
        ordering = ['price']

    def __str__(self):
        return self.name

    def grants_access_to(self, course):
        return self.include_all_courses or self.courses.filter(pk=course.pk).exists()


class PlanPurchase(TimeStampedModel):
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='plan_purchases')
    plan = models.ForeignKey(AccessPlan, on_delete=models.PROTECT, related_name='purchases')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=15, choices=Purchase.PAYMENT_METHOD_CHOICES, default='free')
    transaction_id = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'plan_purchases'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student} - {self.plan}'

    @property
    def is_active(self):
        from django.utils import timezone

        return self.expires_at > timezone.now()


class CartItem(TimeStampedModel):
    """A course sitting in a student's cart, not yet purchased. `created_at`
    doubles as "added to cart at" for the abandonment-reminder task."""

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='cart_items')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='in_carts')
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cart_items'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'course'], name='unique_student_course_cart_item')
        ]

    def __str__(self):
        return f'{self.student} - {self.course}'


class PurchaseSettings(TimeStampedModel):
    CURRENCY_CHOICES = (
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('INR', 'Indian Rupee'),
        ('GBP', 'British Pound'),
        ('JPY', 'Japanese Yen'),
    )

    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    abandoned_cart_reminder_enabled = models.BooleanField(default=False)
    cart_reminder_days_threshold = models.PositiveIntegerField(default=15)

    class Meta:
        db_table = 'purchase_settings'

    def __str__(self):
        return 'Purchase Settings'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
