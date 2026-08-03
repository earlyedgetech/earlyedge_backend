from common.models import TimeStampedModel
from django.db import models
from django.utils.text import slugify


class CourseCategory(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)

    class Meta:
        db_table = 'course_categories'
        verbose_name_plural = 'course categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class CourseSubcategory(TimeStampedModel):
    category = models.ForeignKey(CourseCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, blank=True)

    class Meta:
        db_table = 'course_subcategories'
        verbose_name_plural = 'course subcategories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['category', 'name'], name='unique_category_subcategory_name'),
        ]

    def __str__(self):
        return f'{self.category.name} / {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Course(TimeStampedModel):
    LEVEL_CHOICES = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    )
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    VISIBILITY_CHOICES = (
        ('public', 'Public'),
        ('private', 'Private'),
        ('unlisted', 'Unlisted'),
    )
    COURSE_TYPE_CHOICES = (
        ('course', 'Online Course'),
        ('internship', 'Internship'),
        ('workshop', 'Workshop'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)

    thumbnail_url = models.URLField(blank=True)
    banner_url = models.URLField(blank=True)
    intro_video_url = models.URLField(blank=True)

    category = models.ForeignKey(
        CourseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses'
    )
    subcategory = models.ForeignKey(
        CourseSubcategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses'
    )
    instructor = models.ForeignKey(
        'instructors.Instructor', on_delete=models.SET_NULL, null=True, blank=True, related_name='courses'
    )

    language = models.CharField(max_length=50, default='English')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    duration = models.CharField(max_length=50, blank=True)
    course_type = models.CharField(max_length=15, choices=COURSE_TYPE_CHOICES, default='course')

    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='INR')
    is_free = models.BooleanField(default=False)

    tags = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    outcomes = models.JSONField(default=list, blank=True)
    what_you_learn = models.JSONField(default=list, blank=True)

    course_materials_url = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    is_verified = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)

    total_enrollments = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_reviews = models.PositiveIntegerField(default=0)

    publish_date = models.DateTimeField(null=True, blank=True)
    certificate_enabled = models.BooleanField(default=True)

    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)
    seo_keywords = models.CharField(max_length=500, blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public')

    class Meta:
        db_table = 'courses'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def discount_percent(self):
        if self.discount_price is None or not self.price:
            return 0
        return round((1 - (self.discount_price / self.price)) * 100)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Course.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                counter += 1
                slug = f'{base_slug}-{counter}'
            self.slug = slug
        super().save(*args, **kwargs)


class CourseFeedback(TimeStampedModel):
    TYPE_CHOICES = (
        ('suggestion', 'Suggestion'),
        ('complaint', 'Complaint'),
        ('bug', 'Bug'),
        ('review', 'Review'),
        ('other', 'Other'),
    )

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='feedback')
    student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='course_feedback'
    )
    user_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    message = models.TextField()
    feedback_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='review')
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = 'course_feedback'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.course.title} - {self.user_name or "anonymous"}'
