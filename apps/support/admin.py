from django.contrib import admin

from .models import FAQCategory, FAQItem, Feedback, SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'phone', 'status', 'created_at')
    list_filter = ('status',)
    list_editable = ('status',)
    search_fields = ('subject', 'name', 'email', 'phone')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'student', 'rating', 'visible', 'created_at')
    list_filter = ('visible', 'rating')
    list_editable = ('visible',)
    search_fields = ('name', 'email')


@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    search_fields = ('name',)


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'order', 'created_at')
    list_filter = ('category',)
    search_fields = ('question', 'answer')
