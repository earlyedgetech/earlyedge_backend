from django.contrib import admin

from .models import Refund


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['purchase', 'amount', 'status', 'processed_at']
    list_filter = ['status']
