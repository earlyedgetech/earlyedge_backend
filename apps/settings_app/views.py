from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import HasDashboardPermission, IsAdminMember
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Announcement, LegalPage, NotificationTemplate, SiteSettings
from .notifications import render_template, send_branded_email
from .serializers import (
    AnnouncementSerializer,
    LegalPageSerializer,
    NotificationTemplateSerializer,
    PublicAnnouncementSerializer,
    PublicSiteSettingsSerializer,
    SiteSettingsSerializer,
)

SETTINGS_PERMISSION = 'manage_settings'


def _get_legal_page(page_type):
    if page_type not in dict(LegalPage.PAGE_TYPE_CHOICES):
        return None
    page, _ = LegalPage.objects.get_or_create(
        page_type=page_type, defaults={'title': dict(LegalPage.PAGE_TYPE_CHOICES)[page_type]},
    )
    return page


class PublicSiteSettingsView(APIView):
    """Read-only settings the public website needs (branding, SEO, socials)."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(PublicSiteSettingsSerializer(SiteSettings.get_solo()).data)


class SiteSettingsView(APIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SETTINGS_PERMISSION)]

    def get(self, request):
        return Response(SiteSettingsSerializer(SiteSettings.get_solo()).data)

    def patch(self, request):
        serializer = SiteSettingsSerializer(SiteSettings.get_solo(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NotificationTemplateListView(generics.ListAPIView):
    """Read-only list — rows are seeded via migration (one per real code
    call-site), not admin-creatable. Powers both the Email & Branding
    template gallery and the Message Automations trigger list."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SETTINGS_PERMISSION)]
    serializer_class = NotificationTemplateSerializer
    queryset = NotificationTemplate.objects.all()
    pagination_class = None


class NotificationTemplateDetailView(generics.RetrieveUpdateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SETTINGS_PERMISSION)]
    serializer_class = NotificationTemplateSerializer
    queryset = NotificationTemplate.objects.all()


class NotificationTemplateTestSendView(APIView):
    """Sends the template's current (possibly unsaved-draft) content to an
    admin-supplied test recipient — email address for email-channel
    templates, phone number for WhatsApp. Missing template variables are
    left as literal {placeholders} in the test message rather than raising,
    same as a normal send with incomplete context."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SETTINGS_PERMISSION)]

    def post(self, request, pk):
        try:
            template = NotificationTemplate.objects.get(pk=pk)
        except NotificationTemplate.DoesNotExist:
            return Response({'detail': 'Template not found.'}, status=404)

        recipient = request.data.get('recipient', '').strip()
        if not recipient:
            raise ValidationError({'recipient': 'A test recipient is required.'})

        subject, body = render_template(template.key, {})
        subject = f'[TEST] {subject}' if subject else '[TEST]'

        if template.channel == 'email':
            send_branded_email(recipient, subject, body)
        else:
            from common.integrations.whatsapp_client import WhatsAppClient

            text_params = [line for line in body.split('\n') if line.strip()]
            WhatsAppClient().send_template_message(recipient, *text_params)

        return Response({'detail': f'Test {template.channel} sent to {recipient}.'})


class LegalPageView(APIView):
    """Privacy Policy / Terms of Use / Cookies Policy — GET auto-creates an
    empty row the first time (no meaningful "doesn't exist yet" state for a
    legal document type), PATCH edits it. Not multi-row CRUD — see
    LegalPage's docstring."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SETTINGS_PERMISSION)]

    def get(self, request, page_type):
        page = _get_legal_page(page_type)
        if page is None:
            return Response({'detail': 'Unknown page type.'}, status=404)
        return Response(LegalPageSerializer(page).data)

    def patch(self, request, page_type):
        page = _get_legal_page(page_type)
        if page is None:
            return Response({'detail': 'Unknown page type.'}, status=404)
        serializer = LegalPageSerializer(page, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PublicLegalPageView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, page_type):
        page = _get_legal_page(page_type)
        if page is None:
            return Response({'detail': 'Unknown page type.'}, status=404)
        return Response(LegalPageSerializer(page).data)


class PublicActiveAnnouncementView(APIView):
    """What the website's AnnouncementBar fetches — the single currently
    active/in-window announcement, or null."""

    permission_classes = [AllowAny]

    def get(self, request):
        announcement = Announcement.get_active()
        if not announcement:
            return Response(None)
        return Response(PublicAnnouncementSerializer(announcement).data)


class AnnouncementListCreateView(generics.ListCreateAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SETTINGS_PERMISSION)]
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.select_related('course').all()
    pagination_class = None


class AnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SETTINGS_PERMISSION)]
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.select_related('course').all()


class TriggerBackupView(APIView):
    """Stub for the Maintenance & Backup page — records that a backup was
    requested. Wiring this to an actual backup job (DB dump, storage
    upload) is a deploy-time concern outside this API layer."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, HasDashboardPermission(SETTINGS_PERMISSION)]

    def post(self, request):
        settings_obj = SiteSettings.get_solo()
        settings_obj.last_backup_at = timezone.now()
        settings_obj.save(update_fields=['last_backup_at'])
        return Response({'last_backup_at': settings_obj.last_backup_at})
