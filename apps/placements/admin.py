from django.contrib import admin

from .models import Company, Job, JobApplication

admin.site.register(Company)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'job_type', 'status', 'created_at']
    list_filter = ['status', 'job_type']


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ['student', 'job', 'status', 'created_at']
    list_filter = ['status']
