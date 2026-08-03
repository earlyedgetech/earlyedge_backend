from rest_framework import serializers

from .models import Course, CourseCategory, CourseFeedback, CourseSubcategory


class CourseSubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseSubcategory
        fields = ['id', 'category', 'name', 'slug']
        read_only_fields = ['id', 'slug']


class CourseCategorySerializer(serializers.ModelSerializer):
    subcategories = CourseSubcategorySerializer(many=True, read_only=True)

    class Meta:
        model = CourseCategory
        fields = ['id', 'name', 'slug', 'subcategories']
        read_only_fields = ['id', 'slug']


class CourseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True, default=None)
    instructor_name = serializers.CharField(source='instructor.member.full_name', read_only=True, default=None)
    discount_percent = serializers.ReadOnlyField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'short_description', 'thumbnail_url',
            'banner_url', 'intro_video_url', 'category', 'category_name', 'subcategory',
            'subcategory_name', 'instructor', 'instructor_name', 'language', 'level', 'duration',
            'course_type', 'price', 'discount_price', 'discount_percent', 'currency', 'is_free', 'tags',
            'requirements', 'outcomes', 'what_you_learn', 'course_materials_url', 'status',
            'is_verified', 'is_featured', 'total_enrollments', 'average_rating',
            'total_reviews', 'publish_date', 'certificate_enabled', 'seo_title',
            'seo_description', 'seo_keywords', 'visibility', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'slug', 'total_enrollments', 'average_rating', 'total_reviews',
            'created_at', 'updated_at',
        ]


class CoursePublicSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True, default=None)
    instructor_id = serializers.IntegerField(source='instructor.id', read_only=True, default=None)
    instructor_name = serializers.CharField(source='instructor.member.full_name', read_only=True, default=None)
    discount_percent = serializers.ReadOnlyField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'short_description', 'thumbnail_url',
            'banner_url', 'intro_video_url', 'category_name', 'subcategory_name', 'instructor_id',
            'instructor_name', 'language', 'level', 'duration', 'course_type', 'price',
            'discount_price', 'discount_percent', 'currency', 'is_free', 'tags', 'requirements',
            'outcomes', 'what_you_learn', 'is_featured', 'total_enrollments', 'average_rating',
            'total_reviews', 'certificate_enabled',
        ]


class CourseFeedbackSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = CourseFeedback
        fields = [
            'id', 'course', 'course_title', 'student', 'user_name', 'email', 'message',
            'feedback_type', 'rating', 'is_resolved', 'is_approved', 'created_at',
        ]
        read_only_fields = ['id', 'course_title', 'created_at']


class CourseFeedbackCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseFeedback
        fields = ['course', 'user_name', 'email', 'message', 'feedback_type', 'rating']


class CourseFeedbackPublicSerializer(serializers.ModelSerializer):
    """Approved course reviews shown on the public landing page — no email."""

    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = CourseFeedback
        fields = ['id', 'course_title', 'user_name', 'rating', 'message', 'created_at']
