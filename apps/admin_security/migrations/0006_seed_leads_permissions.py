from django.db import migrations

PERMISSIONS = [
    ('view_leads', 'View Leads'),
    ('create_leads', 'Create Leads'),
    ('edit_leads', 'Edit Leads'),
    ('delete_leads', 'Delete Leads'),
    ('export_leads', 'Export Leads'),
    ('import_leads', 'Import Leads'),
    ('assign_leads', 'Assign Leads'),
    ('view_lead_analytics', 'View Lead Analytics'),
]
ROLES_TO_GRANT = ['admin', 'leads-manager']


def seed_leads_permissions(apps, schema_editor):
    Permission = apps.get_model('admin_security', 'Permission')
    Role = apps.get_model('admin_security', 'Role')

    permission_objs = []
    for codename, name in PERMISSIONS:
        obj, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': name})
        permission_objs.append(obj)

    for slug in ROLES_TO_GRANT:
        try:
            role = Role.objects.get(slug=slug)
        except Role.DoesNotExist:
            continue
        for permission in permission_objs:
            role.permissions.add(permission)


def unseed_leads_permissions(apps, schema_editor):
    Permission = apps.get_model('admin_security', 'Permission')
    Permission.objects.filter(codename__in=[codename for codename, _ in PERMISSIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('admin_security', '0005_seed_materials_permission'),
    ]

    operations = [
        migrations.RunPython(seed_leads_permissions, unseed_leads_permissions),
    ]
