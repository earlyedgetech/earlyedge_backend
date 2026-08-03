from rest_framework import serializers

from .models import AdminLog, AdminMember, AdminNotification, Permission, Role, SecuritySettings


class AdminNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminNotification
        fields = ['id', 'message', 'link', 'is_read', 'created_at']
        read_only_fields = fields


class AdminMemberSerializer(serializers.ModelSerializer):
    role = serializers.SlugField(source='role.slug', read_only=True, allow_null=True)
    role_name = serializers.CharField(source='role.name', read_only=True, default=None)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = AdminMember
        fields = [
            'id', 'email', 'full_name', 'role', 'role_name',
            'permissions', 'is_superuser', 'is_active', 'auth_provider',
            'must_reset_password', 'last_login', 'force_logout_at',
        ]

    def get_permissions(self, obj):
        if obj.is_superuser:
            return list(Permission.objects.values_list('codename', flat=True))
        if not obj.role_id:
            return []
        return list(obj.role.permissions.values_list('codename', flat=True))


class AdminLogSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = AdminLog
        fields = ['id', 'action', 'user_name', 'user_type', 'timestamp', 'ip_address', 'status', 'module']
        read_only_fields = ['id', 'timestamp', 'ip_address', 'module']


class SecuritySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecuritySettings
        fields = ['two_factor_authentication', 'session_timeout', 'login_alerts', 'updated_at']
        read_only_fields = ['updated_at']


class PermissionSerializer(serializers.ModelSerializer):
    module_display = serializers.CharField(source='get_module_display', read_only=True)

    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'module', 'module_display']


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        slug_field='codename', queryset=Permission.objects.all(), many=True, required=False
    )

    class Meta:
        model = Role
        fields = ['id', 'name', 'slug', 'permissions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
