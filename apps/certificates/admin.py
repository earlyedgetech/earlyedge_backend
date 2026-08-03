from django.contrib import admin

from .models import Certificate, CertificateTemplate


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_default']
    list_filter = ['category', 'is_default']


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_code', 'student', 'course', 'certificate_type', 'issue_type', 'status', 'issued_at']
    list_filter = ['status', 'certificate_type', 'issue_type']
    search_fields = ['certificate_code', 'student__email', 'course__title']
