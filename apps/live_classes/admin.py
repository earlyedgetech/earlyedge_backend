from django.contrib import admin

from .models import Batch, BatchRegistration, LiveClassSettings, LiveSession, SessionAttendance


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'status', 'is_public', 'start_date', 'end_date']
    list_filter = ['status', 'is_public']


@admin.register(LiveClassSettings)
class LiveClassSettingsAdmin(admin.ModelAdmin):
    list_display = ['waiting_room_enabled', 'chat_enabled', 'default_mic_on', 'default_cam_on']


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'batch', 'scheduled_at', 'status']
    list_filter = ['status']


admin.site.register(BatchRegistration)
admin.site.register(SessionAttendance)
