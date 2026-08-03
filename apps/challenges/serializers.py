from rest_framework import serializers

from .models import Challenge, ChallengeSubmission


class ChallengeSerializer(serializers.ModelSerializer):
    submission_count = serializers.IntegerField(source='submissions.count', read_only=True)

    class Meta:
        model = Challenge
        fields = [
            'id', 'title', 'description', 'difficulty', 'points', 'challenge_date',
            'starter_code', 'is_active', 'submission_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ChallengeSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    challenge_title = serializers.CharField(source='challenge.title', read_only=True)

    class Meta:
        model = ChallengeSubmission
        fields = [
            'id', 'challenge', 'challenge_title', 'student', 'student_name',
            'code', 'status', 'score', 'created_at',
        ]
        read_only_fields = ['id', 'student', 'status', 'score', 'created_at']


class LeaderboardEntrySerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    total_score = serializers.IntegerField()
    challenges_completed = serializers.IntegerField()
