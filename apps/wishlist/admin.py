from django.contrib import admin

from .models import WishlistItem


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'created_at']
    search_fields = ['student__email', 'course__title']
