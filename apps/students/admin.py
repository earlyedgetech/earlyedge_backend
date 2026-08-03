from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'is_active', 'is_verified', 'auth_provider', 'created_at')
    search_fields = ('email', 'full_name')
    list_filter = ('is_active', 'is_verified', 'auth_provider')
