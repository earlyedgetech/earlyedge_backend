from rest_framework import serializers

from .models import WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    course_thumbnail = serializers.CharField(source='course.thumbnail_url', read_only=True)
    course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = WishlistItem
        fields = ['id', 'course', 'course_title', 'course_slug', 'course_thumbnail', 'course_price', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_course(self, value):
        student = self.context['request'].user
        if WishlistItem.objects.filter(student=student, course=value).exists():
            raise serializers.ValidationError('This course is already in your wishlist.')
        return value


class WishlistItemAdminSerializer(serializers.ModelSerializer):
    """Dashboard-facing shape — one row per student's wishlist item, for the
    Cart & Wishlist admin page's per-item table + total-value calculation."""

    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_email = serializers.CharField(source='student.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = WishlistItem
        fields = [
            'id', 'student', 'student_name', 'student_email', 'course', 'course_title',
            'course_price', 'created_at',
        ]
        read_only_fields = fields
