from django.contrib import admin

from .models import UploadSession


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    list_display = ['filename', 'purpose', 'status', 'progress_percent', 'created_by', 'created_at']
    list_filter = ['purpose', 'status']
    search_fields = ['filename']
