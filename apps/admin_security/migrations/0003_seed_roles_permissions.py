from django.db import migrations

PERMISSIONS = [
    ('view_dashboard', 'View Dashboard Overview'),
    ('manage_courses', 'Manage All Courses'),
    ('manage_own_courses', 'Manage Own Courses (Instructor)'),
    ('manage_live_classes', 'Manage Live Classes & Batches'),
    ('manage_instructors', 'Manage Instructors'),
    ('manage_leads', 'Manage Leads'),
    ('manage_students', 'Manage Students'),
    ('manage_placements', 'Manage Placement Assistant'),
    ('manage_certificates', 'Manage Certificates'),
    ('manage_challenges', 'Manage Daily Challenges'),
    ('manage_promocodes', 'Manage Promo Codes'),
    ('manage_purchases', 'Manage Purchases & Enrollments'),
    ('manage_revenue', 'Manage Revenue & Payments'),
    ('manage_settings', 'Manage Site Settings'),
    ('manage_support', 'Manage Support & Feedback'),
    ('manage_members', 'Manage Dashboard Members'),
    ('manage_roles', 'Manage Roles & Permissions'),
    ('manage_admin_logs', 'View Admin Logs'),
    ('manage_security_settings', 'Manage Security Settings'),
]

ROLES = {
    'admin': ('Administrator', [codename for codename, _ in PERMISSIONS]),
    'instructor': ('Instructor', ['view_dashboard', 'manage_own_courses', 'manage_live_classes']),
    'finance': ('Finance Manager', ['view_dashboard', 'manage_revenue', 'manage_purchases', 'manage_promocodes']),
    'leads-manager': ('Leads Manager', ['view_dashboard', 'manage_leads']),
    'support': ('Support Agent', ['view_dashboard', 'manage_support']),
}


def seed_roles_and_permissions(apps, schema_editor):
    Permission = apps.get_model('admin_security', 'Permission')
    Role = apps.get_model('admin_security', 'Role')

    permission_objs = {}
    for codename, name in PERMISSIONS:
        obj, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': name})
        permission_objs[codename] = obj

    for slug, (name, codenames) in ROLES.items():
        role, _ = Role.objects.get_or_create(slug=slug, defaults={'name': name})
        role.permissions.set([permission_objs[codename] for codename in codenames])


def unseed_roles_and_permissions(apps, schema_editor):
    Role = apps.get_model('admin_security', 'Role')
    Permission = apps.get_model('admin_security', 'Permission')
    Role.objects.filter(slug__in=ROLES.keys()).delete()
    Permission.objects.filter(codename__in=[codename for codename, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('admin_security', '0002_adminlog_securitysettings'),
    ]

    operations = [
        migrations.RunPython(seed_roles_and_permissions, unseed_roles_and_permissions),
    ]
