from django.db import migrations
from django.utils.text import slugify

STAGES = [
    # (name, order, color, is_won, is_lost)
    ('New Lead', 0, '#3b82f6', False, False),
    ('Contacted', 1, '#6366f1', False, False),
    ('Interested', 2, '#8b5cf6', False, False),
    ('Demo Scheduled', 3, '#f59e0b', False, False),
    ('Enrolled', 4, '#10b981', True, False),
    ('Not Interested', 5, '#9ca3af', False, False),
    ('Retry', 6, '#f97316', False, False),
    ('Lost', 7, '#ef4444', False, True),
]


def seed_pipeline_stages(apps, schema_editor):
    PipelineStage = apps.get_model('leads', 'PipelineStage')
    for name, order, color, is_won, is_lost in STAGES:
        PipelineStage.objects.get_or_create(
            name=name,
            defaults={
                'slug': slugify(name),
                'order': order,
                'color': color,
                'is_won': is_won,
                'is_lost': is_lost,
            },
        )


def unseed_pipeline_stages(apps, schema_editor):
    PipelineStage = apps.get_model('leads', 'PipelineStage')
    PipelineStage.objects.filter(name__in=[name for name, *_ in STAGES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0002_automationrule_leadcustomfielddefinition_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_pipeline_stages, unseed_pipeline_stages),
    ]
