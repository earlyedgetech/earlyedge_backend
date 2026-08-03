from django.contrib import admin

from .models import PromoCode, PromoCodeRedemption


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'discount_type', 'discount_value', 'platform',
        'is_active', 'start_date', 'end_date', 'total_uses',
    )
    list_filter = ('is_active', 'discount_type', 'platform')
    list_editable = ('is_active',)
    search_fields = ('code', 'description')


@admin.register(PromoCodeRedemption)
class PromoCodeRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        'promo_code', 'student', 'status', 'order_amount',
        'discount_amount', 'applied_at', 'completed_at',
    )
    list_filter = ('status',)
    search_fields = ('promo_code__code', 'student__email')
