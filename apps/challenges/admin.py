from django.contrib import admin

from .models import Challenge, ChallengeSubmission


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'difficulty', 'points', 'challenge_date', 'is_active']
    list_filter = ['difficulty', 'is_active']


@admin.register(ChallengeSubmission)
class ChallengeSubmissionAdmin(admin.ModelAdmin):
    list_display = ['student', 'challenge', 'status', 'score']
    list_filter = ['status']
