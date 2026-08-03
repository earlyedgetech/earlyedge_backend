from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from common.models import TimeStampedModel
from students.models import Student


class PromoCode(TimeStampedModel):
    DISCOUNT_PERCENTAGE = 'percentage'
    DISCOUNT_FIXED = 'fixed'
    DISCOUNT_TYPE_CHOICES = (
        (DISCOUNT_PERCENTAGE, 'Percentage'),
        (DISCOUNT_FIXED, 'Fixed Amount'),
    )

    PLATFORM_ALL = 'all'
    PLATFORM_MOBILE = 'mobile'
    PLATFORM_WEB = 'web'
    PLATFORM_CHOICES = (
        (PLATFORM_ALL, 'All Platforms'),
        (PLATFORM_MOBILE, 'Mobile Only'),
        (PLATFORM_WEB, 'Web Only'),
    )

    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)

    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default=DISCOUNT_PERCENTAGE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])

    # null = unlimited / no minimum, matching the "Unlimited" / "No minimum" placeholders in the UI.
    max_total_uses = models.PositiveIntegerField(null=True, blank=True)
    limit_per_user = models.PositiveIntegerField(null=True, blank=True)
    minimum_purchase = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default=PLATFORM_ALL)
    is_active = models.BooleanField(default=False)
    first_time_purchase_only = models.BooleanField(default=False)
    auto_apply_at_checkout = models.BooleanField(default=False)
    show_in_cart = models.BooleanField(
        default=False,
        help_text='Surface this code as a suggested/available coupon in the checkout cart, '
                  'rather than requiring the customer to already know it.',
    )

    class Meta:
        db_table = 'promo_codes'
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)

    @property
    def total_uses(self):
        return self.redemptions.filter(status=PromoCodeRedemption.STATUS_COMPLETED).count()


class PromoCodeRedemption(models.Model):
    """One row per code application at checkout. `status` moves from
    'applied' (code entered) to 'completed' (order finished) or 'cancelled'
    so the analytics view can derive a conversion rate without depending on
    the purchases app, which doesn't exist yet."""

    STATUS_APPLIED = 'applied'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_APPLIED, 'Applied'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='redemptions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='promo_redemptions')
    order_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_APPLIED)
    applied_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'promo_code_redemptions'
        ordering = ['-applied_at']

    def __str__(self):
        return f'{self.promo_code.code} - {self.student_id} ({self.status})'
