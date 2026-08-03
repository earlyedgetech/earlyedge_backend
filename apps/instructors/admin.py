from django.contrib import admin

from .models import Instructor, InstructorPayout


@admin.register(Instructor)
class InstructorAdmin(admin.ModelAdmin):
    list_display = ['instructor_code', 'member', 'account_status', 'admin_verified', 'rating_avg']
    list_filter = ['account_status', 'admin_verified']
    search_fields = ['instructor_code', 'member__email', 'member__full_name']


@admin.register(InstructorPayout)
class InstructorPayoutAdmin(admin.ModelAdmin):
    list_display = ['instructor', 'amount', 'recorded_by', 'created_at']
