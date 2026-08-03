from django.db import migrations

# (key, module, label, channel, subject, body)
TEMPLATES = [
    (
        'instructor_application_received', 'instructors', 'Instructor Application Received', 'email',
        'We received your application',
        'Hi {full_name},\n\n'
        'Thanks for applying to teach at {site_name}. Our team will review your application and verify '
        'your account shortly — you\'ll be able to log in once approved.\n\n'
        '— {site_name}',
    ),
    (
        'instructor_verified', 'instructors', 'Instructor Verified', 'email',
        "You're verified — welcome to {site_name}!",
        'Hi {full_name},\n\n'
        "Great news — your instructor account has been verified. You can now log in to the dashboard "
        'and start managing your courses.\n\n'
        '— {site_name}',
    ),
    (
        'batch_join_requested', 'live_classes', 'Batch Join Request Received', 'email',
        'We received your request to join {course_title}',
        'Hi {student_name},\n\n'
        'Thanks for your interest in "{course_title}" ({batch_name}). Our team will contact you shortly '
        'to confirm your seat.\n\n'
        '— {site_name}',
    ),
    (
        'batch_registration_confirmed', 'live_classes', 'Batch Registration Confirmed', 'email',
        "You're confirmed for {course_title}!",
        'Hi {student_name},\n\n'
        'Your seat in "{course_title}" ({batch_name}) is confirmed. We\'ll notify you as sessions are scheduled.\n\n'
        '— {site_name}',
    ),
    (
        'lead_assigned', 'leads', 'Lead Assigned to You', 'email',
        'New lead assigned: {lead_name}',
        'Hi {counsellor_name},\n\n'
        'A new lead, "{lead_name}" ({lead_contact}), has been assigned to you. Please follow up soon.\n\n'
        '— {site_name}',
    ),
]


def seed_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model('settings_app', 'NotificationTemplate')
    for key, module, label, channel, subject, body in TEMPLATES:
        NotificationTemplate.objects.get_or_create(
            key=key,
            defaults={
                'module': module, 'label': label, 'channel': channel,
                'subject': subject, 'body': body, 'is_active': True,
            },
        )


def unseed_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model('settings_app', 'NotificationTemplate')
    NotificationTemplate.objects.filter(key__in=[key for key, *_ in TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0009_alter_notificationtemplate_module'),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
