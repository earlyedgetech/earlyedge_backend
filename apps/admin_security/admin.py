from django.contrib import admin

from .models import AdminLog, AdminMember, Permission, Role, SecuritySettings


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('codename', 'name')
    search_fields = ('codename', 'name')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    filter_horizontal = ('permissions',)


@admin.register(AdminMember)
class AdminMemberAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'full_name', 'role', 'is_active', 'is_superuser',
        'auth_provider', 'must_reset_password', 'created_at',
    )
    search_fields = ('email', 'full_name')
    list_filter = ('is_active', 'is_superuser', 'auth_provider', 'role', 'must_reset_password')


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user_name', 'user_type', 'status', 'ip_address', 'created_at')
    search_fields = ('action', 'user_name', 'ip_address')
    list_filter = ('user_type', 'status')


@admin.register(SecuritySettings)
class SecuritySettingsAdmin(admin.ModelAdmin):
    list_display = ('two_factor_authentication', 'session_timeout', 'login_alerts', 'updated_at')
