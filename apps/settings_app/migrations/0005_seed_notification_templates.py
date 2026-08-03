from django.db import migrations

# (key, module, label, channel, subject, body)
TEMPLATES = [
    (
        'password_reset', 'account', 'Password Reset', 'email',
        'Reset your password',
        'Click the link below to reset your password:\n\n'
        '{link}\n\n'
        'If you did not request this, you can safely ignore this email.',
    ),
    (
        'student_welcome', 'students', 'Student Welcome', 'email',
        'Welcome to {site_name}!',
        'Hi {student_name},\n\n'
        'Welcome to {site_name}! Your account is ready — browse our courses and start learning today.\n\n'
        '— {site_name}',
    ),
    (
        'lead_welcome', 'leads', 'Lead Welcome Email', 'email',
        "Thanks for your interest — we'll be in touch",
        'Hi {lead_name},\n\n'
        'Thanks for reaching out to {site_name}. One of our counsellors will contact you shortly.\n\n'
        '— {site_name}',
    ),
    (
        'lead_manager_alert', 'leads', 'Lead Manager Alert', 'email',
        'Lead needs attention: {lead_name}',
        'Lead "{lead_name}" ({lead_contact}) needs review.',
    ),
    (
        'lead_follow_up_digest', 'leads', 'Follow-up Digest', 'email',
        'You have follow-up(s) due',
        'Hi {counsellor_name},\n\n'
        'Your due/overdue follow-ups:\n\n'
        '{follow_up_list}\n\n'
        '— {site_name}',
    ),
    (
        'cart_abandoned', 'purchases', 'Abandoned Cart Reminder', 'email',
        'You left "{course_title}" in your cart',
        'Hi {student_name},\n\n'
        'You added "{course_title}" to your cart but haven\'t completed checkout yet. '
        'Complete your purchase today before you miss out!\n\n'
        '— {site_name}',
    ),
    (
        'course_completion', 'purchases', 'Course Completion', 'email',
        "Congratulations on completing {course_title}!",
        'Hi {student_name},\n\n'
        'Congratulations on completing "{course_title}"! Your certificate will be available shortly.\n\n'
        '— {site_name}',
    ),
    (
        'live_class_reminder', 'live_classes', 'Live Class Reminder', 'email',
        '"{session_title}" starts in about an hour',
        'Hi {student_name},\n\n'
        'Your live class "{session_title}" ({course_title}) starts soon.\n\n'
        'Join here: {meeting_url}\n\n'
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
        ('settings_app', '0004_notificationtemplate_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
