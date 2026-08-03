from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import TimeStampedModel
from students.models import Student


class SupportTicket(TimeStampedModel):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CLOSED, 'Closed'),
    )
    SOURCE_DASHBOARD = 'dashboard'
    SOURCE_WEBSITE = 'website'
    SOURCE_CHOICES = (
        (SOURCE_DASHBOARD, 'Dashboard'),
        (SOURCE_WEBSITE, 'Website'),
    )

    subject = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    message = models.TextField()
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_WEBSITE)

    class Meta:
        db_table = 'support_tickets'

    def __str__(self):
        return f'{self.subject} ({self.email})'


class FAQCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'faq_categories'
        ordering = ['order', 'name']
        verbose_name_plural = 'FAQ categories'

    def __str__(self):
        return self.name


class FAQItem(TimeStampedModel):
    STATUS_PENDING = 'pending'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_PUBLISHED, 'Published'),
    )

    category = models.ForeignKey(
        FAQCategory, on_delete=models.CASCADE, related_name='items', null=True, blank=True
    )
    question = models.CharField(max_length=500)
    answer = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    asked_by_name = models.CharField(max_length=255, blank=True)
    asked_by_email = models.EmailField(blank=True)

    class Meta:
        db_table = 'faq_items'
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.question


class Feedback(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='feedbacks')
    name = models.CharField(max_length=255)
    email = models.EmailField()
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    profile_pic = models.ImageField(upload_to='feedback/profile_pics/', blank=True, null=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    visible = models.BooleanField(default=False)

    class Meta:
        db_table = 'feedbacks'

    def __str__(self):
        return f'{self.name} - {self.rating}★'
