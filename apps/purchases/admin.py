from django.contrib import admin

from .models import Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'amount_paid', 'payment_status', 'enrollment_status', 'created_at']
    list_filter = ['payment_status', 'enrollment_status', 'payment_method']
    search_fields = ['student__email', 'student__full_name', 'course__title', 'transaction_id']
