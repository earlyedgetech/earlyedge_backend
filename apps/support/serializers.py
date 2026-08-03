from rest_framework import serializers

from .models import FAQCategory, FAQItem, Feedback, SupportTicket


class FAQItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQItem
        fields = [
            'id', 'category', 'question', 'answer', 'order', 'status',
            'asked_by_name', 'asked_by_email', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'asked_by_name', 'asked_by_email', 'created_at', 'updated_at']


class FAQCategorySerializer(serializers.ModelSerializer):
    items = FAQItemSerializer(many=True, read_only=True)

    class Meta:
        model = FAQCategory
        fields = ['id', 'name', 'order', 'items']
        read_only_fields = ['id']


class FAQItemPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQItem
        fields = ['id', 'question', 'answer']


class FAQCategoryPublicSerializer(serializers.ModelSerializer):
    """Home/FAQ page shape — only published questions, never a pending one
    a student just submitted."""

    items = serializers.SerializerMethodField()

    class Meta:
        model = FAQCategory
        fields = ['id', 'name', 'items']

    def get_items(self, category):
        published = category.items.filter(status=FAQItem.STATUS_PUBLISHED)
        return FAQItemPublicSerializer(published, many=True).data


class FAQAskQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQItem
        fields = ['question', 'asked_by_name', 'asked_by_email']


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = [
            'id', 'subject', 'name', 'email', 'phone', 'status', 'message',
            'source', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'source', 'created_at', 'updated_at']


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = [
            'id', 'student', 'name', 'email', 'rating', 'profile_pic',
            'description', 'visible', 'created_at',
        ]
        read_only_fields = ['id', 'student', 'name', 'email', 'visible', 'created_at']


class FeedbackPublicSerializer(serializers.ModelSerializer):
    """Read-only shape exposed to the home page — no email/student id."""

    class Meta:
        model = Feedback
        fields = ['id', 'name', 'rating', 'profile_pic', 'description', 'created_at']
