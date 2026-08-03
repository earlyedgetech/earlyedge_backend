from courses.models import CourseCategory, CourseSubcategory
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import MaterialCategory, MaterialSubcategory


def sync_material_category(course_category):
    """Return the MaterialCategory folder mirroring this CourseCategory,
    creating or renaming it as needed. Links to an existing same-named
    manual folder rather than raising on the unique name constraint."""
    try:
        material_category = MaterialCategory.objects.get(source_course_category=course_category)
    except MaterialCategory.DoesNotExist:
        material_category, created = MaterialCategory.objects.get_or_create(
            name=course_category.name,
            defaults={'source_course_category': course_category},
        )
        if not created and material_category.source_course_category_id is None:
            material_category.source_course_category = course_category
            material_category.save(update_fields=['source_course_category'])
        return material_category

    if material_category.name != course_category.name:
        material_category.name = course_category.name
        material_category.slug = slugify(course_category.name)
        material_category.save(update_fields=['name', 'slug'])
    return material_category


@receiver(post_save, sender=CourseCategory)
def on_course_category_saved(sender, instance, **kwargs):
    sync_material_category(instance)


@receiver(post_save, sender=CourseSubcategory)
def on_course_subcategory_saved(sender, instance, **kwargs):
    material_category = sync_material_category(instance.category)

    try:
        material_subcategory = MaterialSubcategory.objects.get(source_course_subcategory=instance)
    except MaterialSubcategory.DoesNotExist:
        material_subcategory, created = MaterialSubcategory.objects.get_or_create(
            category=material_category, name=instance.name,
            defaults={'source_course_subcategory': instance},
        )
        if not created and material_subcategory.source_course_subcategory_id is None:
            material_subcategory.source_course_subcategory = instance
            material_subcategory.save(update_fields=['source_course_subcategory'])
        return

    changed_fields = []
    if material_subcategory.category_id != material_category.id:
        material_subcategory.category = material_category
        changed_fields.append('category')
    if material_subcategory.name != instance.name:
        material_subcategory.name = instance.name
        material_subcategory.slug = slugify(instance.name)
        changed_fields += ['name', 'slug']
    if changed_fields:
        material_subcategory.save(update_fields=changed_fields)
