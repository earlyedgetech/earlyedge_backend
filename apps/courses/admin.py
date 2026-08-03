from django.contrib import admin

from .models import Course, CourseCategory, CourseFeedback, CourseSubcategory


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']


@admin.register(CourseSubcategory)
class CourseSubcategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'slug']
    list_filter = ['category']
    search_fields = ['name']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'category', 'status', 'price', 'total_enrollments']
    list_filter = ['status', 'level', 'is_featured', 'category']
    search_fields = ['title', 'slug']


@admin.register(CourseFeedback)
class CourseFeedbackAdmin(admin.ModelAdmin):
    list_display = ['course', 'user_name', 'feedback_type', 'rating', 'is_resolved']
    list_filter = ['feedback_type', 'is_resolved']
