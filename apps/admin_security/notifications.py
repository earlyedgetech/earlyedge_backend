"""In-app admin notification helpers — creates the AdminNotification rows
the dashboard Navbar bell polls for. Separate from settings_app.notifications
(email/WhatsApp templates); this is purely the in-app inbox feed."""

from .models import AdminMember, AdminNotification


def notify_admin(member, message, link=''):
    if not member:
        return
    AdminNotification.objects.create(recipient=member, message=message, link=link)


def notify_admins_with_permission(codename, message, link=''):
    recipients = [
        member for member in AdminMember.objects.filter(is_active=True).select_related('role')
        if member.has_permission(codename)
    ]
    AdminNotification.objects.bulk_create([
        AdminNotification(recipient=member, message=message, link=link) for member in recipients
    ])
