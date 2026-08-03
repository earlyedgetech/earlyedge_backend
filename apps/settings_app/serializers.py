from rest_framework import serializers

from .models import Announcement, LegalPage, NotificationTemplate, SiteSettings


class AnnouncementSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True, default=None)

    class Meta:
        model = Announcement
        fields = [
            'id', 'message', 'announcement_type', 'course', 'course_title', 'cta_label', 'cta_link',
            'countdown_at', 'is_active', 'starts_at', 'ends_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PublicAnnouncementSerializer(serializers.ModelSerializer):
    cta_link = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'message', 'announcement_type', 'cta_label', 'cta_link', 'countdown_at']

    def get_cta_link(self, obj):
        if obj.cta_link:
            return obj.cta_link
        if obj.course:
            return f'/courses/{obj.course.slug}'
        return '/courses'


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = [
            'site_name', 'site_logo_url', 'favicon_url', 'contact_email', 'contact_phone', 'address',
            'office_hours', 'max_concurrent_devices',
            'legal_name', 'registration_number', 'gst_number', 'established_year', 'company_address',
            'email_from_name', 'email_from_address', 'primary_color',
            'seo_title', 'seo_description', 'seo_keywords',
            'social_links', 'home_page_banner_url', 'about_page_content',
            'google_analytics_id', 'facebook_pixel_id', 'razorpay_key_id', 'razorpay_key_secret',
            'terabox_enabled', 'terabox_access_token', 'terabox_app_id', 'terabox_root_path',
            'zoom_enabled', 'zoom_account_id', 'zoom_client_id', 'zoom_client_secret',
            'whatsapp_enabled', 'whatsapp_access_token', 'whatsapp_waba_id', 'whatsapp_phone_number_id',
            'whatsapp_template_name',
            'maintenance_mode', 'maintenance_scope', 'maintenance_message',
            'maintenance_start_at', 'maintenance_end_at',
            'last_backup_at', 'updated_at',
        ]
        read_only_fields = ['last_backup_at', 'updated_at']


class PublicSiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = [
            'site_name', 'site_logo_url', 'favicon_url', 'contact_email', 'contact_phone', 'address',
            'office_hours', 'legal_name', 'registration_number', 'gst_number', 'established_year', 'company_address',
            'seo_title', 'seo_description', 'seo_keywords', 'social_links',
            'home_page_banner_url', 'about_page_content',
            'maintenance_mode', 'maintenance_scope', 'maintenance_message',
            'maintenance_start_at', 'maintenance_end_at',
        ]


class LegalPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalPage
        fields = ['page_type', 'title', 'content', 'updated_at']
        read_only_fields = ['page_type', 'updated_at']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    module_display = serializers.CharField(source='get_module_display', read_only=True)

    class Meta:
        model = NotificationTemplate
        fields = ['id', 'key', 'module', 'module_display', 'label', 'channel', 'subject', 'body', 'is_active']
        read_only_fields = ['id', 'key', 'module', 'module_display', 'label']
