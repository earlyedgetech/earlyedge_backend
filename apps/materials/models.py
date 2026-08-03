from common.models import TimeStampedModel
from django.db import models
from django.utils.text import slugify


class MaterialCategory(TimeStampedModel):
    """Top-level folder for organizing materials/notes. Folders are usually
    kept in sync automatically with CourseCategory (see materials/signals.py)
    so the materials tree mirrors the course category hierarchy, but a
    folder can also exist standalone (e.g. "Recordings", "Assignments")
    when source_course_category is null."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    source_course_category = models.OneToOneField(
        'courses.CourseCategory', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='material_category',
        help_text='Set when this folder was auto-created from/synced to a course category.',
    )

    class Meta:
        db_table = 'material_categories'
        verbose_name_plural = 'material categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class MaterialSubcategory(TimeStampedModel):
    """A subfolder within a MaterialCategory."""

    category = models.ForeignKey(MaterialCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, blank=True)
    source_course_subcategory = models.OneToOneField(
        'courses.CourseSubcategory', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='material_subcategory',
        help_text='Set when this subfolder was auto-created from/synced to a course subcategory.',
    )

    class Meta:
        db_table = 'material_subcategories'
        verbose_name_plural = 'material subcategories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['category', 'name'], name='unique_material_category_subcategory_name'),
        ]

    def __str__(self):
        return f'{self.category.name} / {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class MaterialFile(TimeStampedModel):
    """One uploaded file (note/material) living inside a subfolder."""

    subcategory = models.ForeignKey(MaterialSubcategory, on_delete=models.CASCADE, related_name='files')
    title = models.CharField(max_length=255)
    file_url = models.URLField()
    file_size = models.BigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='uploaded_materials',
    )

    class Meta:
        db_table = 'material_files'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class MaterialShare(TimeStampedModel):
    """A material file shared to a live-class Batch — every student
    registered in that batch (live_classes.BatchRegistration) gets access."""

    material_file = models.ForeignKey(MaterialFile, on_delete=models.CASCADE, related_name='shares')
    batch = models.ForeignKey('live_classes.Batch', on_delete=models.CASCADE, related_name='shared_materials')
    shared_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='material_shares',
    )

    class Meta:
        db_table = 'material_shares'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['material_file', 'batch'], name='unique_material_file_batch_share'),
        ]

    def __str__(self):
        return f'{self.material_file.title} -> {self.batch.name}'
