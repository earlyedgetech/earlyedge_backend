from common.models import TimeStampedModel
from django.db import models
from django.utils.text import slugify


class BlogPost(TimeStampedModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    excerpt = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    cover_image_url = models.URLField(blank=True)
    author_name = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=100, blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'blog_posts'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            suffix = 1
            while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix += 1
                slug = f'{base_slug}-{suffix}'
            self.slug = slug
        super().save(*args, **kwargs)
