from django.db import migrations

PERMISSION = ('manage_materials', 'Manage Materials & Notes')
ROLES_TO_GRANT = ['admin', 'instructor']


def seed_materials_permission(apps, schema_editor):
    Permission = apps.get_model('admin_security', 'Permission')
    Role = apps.get_model('admin_security', 'Role')

    codename, name = PERMISSION
    permission, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': name})

    for slug in ROLES_TO_GRANT:
        try:
            role = Role.objects.get(slug=slug)
        except Role.DoesNotExist:
            continue
        role.permissions.add(permission)


def unseed_materials_permission(apps, schema_editor):
    Permission = apps.get_model('admin_security', 'Permission')
    Permission.objects.filter(codename=PERMISSION[0]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('admin_security', '0004_adminmember_must_reset_password'),
    ]

    operations = [
        migrations.RunPython(seed_materials_permission, unseed_materials_permission),
    ]
