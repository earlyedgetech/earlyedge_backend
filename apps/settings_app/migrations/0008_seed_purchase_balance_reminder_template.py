from django.db import migrations

KEY = 'purchase_balance_reminder'


def seed_template(apps, schema_editor):
    NotificationTemplate = apps.get_model('settings_app', 'NotificationTemplate')
    NotificationTemplate.objects.get_or_create(
        key=KEY,
        defaults={
            'module': 'purchases',
            'label': 'Balance Payment Reminder',
            'channel': 'email',
            'subject': 'Payment reminder: {course_title}',
            'body': (
                'Hi {student_name},\n\n'
                'This is a reminder that you have a balance of {amount_due} remaining for "{course_title}". '
                'Please complete your payment by {due_date} to keep your enrollment active.\n\n'
                '— {site_name}'
            ),
            'is_active': True,
        },
    )


def unseed_template(apps, schema_editor):
    NotificationTemplate = apps.get_model('settings_app', 'NotificationTemplate')
    NotificationTemplate.objects.filter(key=KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0007_sitesettings_maintenance_end_at_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_template, unseed_template),
    ]
