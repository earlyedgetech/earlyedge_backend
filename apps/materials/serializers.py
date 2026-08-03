from rest_framework import serializers

from .models import MaterialCategory, MaterialFile, MaterialShare, MaterialSubcategory


class MaterialFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True, default=None)
    share_count = serializers.IntegerField(source='shares.count', read_only=True)

    class Meta:
        model = MaterialFile
        fields = [
            'id', 'subcategory', 'title', 'file_url', 'file_size', 'content_type',
            'uploaded_by', 'uploaded_by_name', 'share_count', 'created_at',
        ]
        read_only_fields = ['id', 'uploaded_by', 'created_at']


class MaterialSubcategorySerializer(serializers.ModelSerializer):
    files = MaterialFileSerializer(many=True, read_only=True)
    is_course_synced = serializers.SerializerMethodField()

    class Meta:
        model = MaterialSubcategory
        fields = ['id', 'category', 'name', 'slug', 'files', 'is_course_synced']
        read_only_fields = ['id', 'slug']

    def get_is_course_synced(self, obj):
        return obj.source_course_subcategory_id is not None


class MaterialCategorySerializer(serializers.ModelSerializer):
    subcategories = MaterialSubcategorySerializer(many=True, read_only=True)
    is_course_synced = serializers.SerializerMethodField()

    class Meta:
        model = MaterialCategory
        fields = ['id', 'name', 'slug', 'subcategories', 'is_course_synced']
        read_only_fields = ['id', 'slug']

    def get_is_course_synced(self, obj):
        return obj.source_course_category_id is not None


class MaterialShareSerializer(serializers.ModelSerializer):
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    course_title = serializers.CharField(source='batch.course.title', read_only=True)

    class Meta:
        model = MaterialShare
        fields = ['id', 'material_file', 'batch', 'batch_name', 'course_title', 'shared_by', 'created_at']
        read_only_fields = ['id', 'shared_by', 'created_at']


class MaterialStudentFileSerializer(serializers.ModelSerializer):
    """What a student sees for a file shared with (one of) their batches."""

    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    category_name = serializers.CharField(source='subcategory.category.name', read_only=True)

    class Meta:
        model = MaterialFile
        fields = ['id', 'title', 'file_url', 'file_size', 'content_type', 'category_name', 'subcategory_name', 'created_at']
