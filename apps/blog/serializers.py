from rest_framework import serializers

from .models import BlogPost


class BlogPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content', 'cover_image_url', 'author_name',
            'category', 'is_published', 'published_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'published_at', 'created_at', 'updated_at']


class PublicBlogPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = ['id', 'title', 'slug', 'excerpt', 'content', 'cover_image_url', 'author_name', 'category', 'published_at']
