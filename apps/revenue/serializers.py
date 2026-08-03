from purchases.models import Purchase
from rest_framework import serializers

from .models import Refund


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Purchase
        fields = [
            'id', 'student', 'student_name', 'course', 'course_title', 'amount_paid',
            'payment_method', 'payment_status', 'transaction_id', 'created_at',
        ]


class RefundSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='purchase.student.full_name', read_only=True)
    course_title = serializers.CharField(source='purchase.course.title', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.full_name', read_only=True, default=None)

    class Meta:
        model = Refund
        fields = [
            'id', 'purchase', 'student_name', 'course_title', 'amount', 'reason', 'status',
            'processed_by', 'processed_by_name', 'processed_at', 'created_at',
        ]
        read_only_fields = ['id', 'processed_by', 'processed_at', 'created_at']
