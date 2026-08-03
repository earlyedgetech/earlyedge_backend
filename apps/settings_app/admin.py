from django.contrib import admin

from .models import LegalPage, NotificationTemplate, SiteSettings

admin.site.register(SiteSettings)
admin.site.register(NotificationTemplate)
admin.site.register(LegalPage)
