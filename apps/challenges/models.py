from common.models import TimeStampedModel
from django.db import models


class Challenge(TimeStampedModel):
    DIFFICULTY_CHOICES = (
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    )

    title = models.CharField(max_length=255)
    description = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='easy')
    points = models.PositiveIntegerField(default=10)
    challenge_date = models.DateField()
    starter_code = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'daily_challenges'
        ordering = ['-challenge_date']

    def __str__(self):
        return f'{self.title} ({self.challenge_date})'


class ChallengeSubmission(TimeStampedModel):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    )

    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='challenge_submissions')
    code = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    score = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'daily_challenge_submissions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student} - {self.challenge} ({self.status})'
