from django.contrib import admin

from .models import MaterialCategory, MaterialFile, MaterialShare, MaterialSubcategory


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']


@admin.register(MaterialSubcategory)
class MaterialSubcategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'slug']
    list_filter = ['category']
    search_fields = ['name']


@admin.register(MaterialFile)
class MaterialFileAdmin(admin.ModelAdmin):
    list_display = ['title', 'subcategory', 'uploaded_by', 'created_at']
    list_filter = ['subcategory__category']
    search_fields = ['title']


@admin.register(MaterialShare)
class MaterialShareAdmin(admin.ModelAdmin):
    list_display = ['material_file', 'batch', 'shared_by', 'created_at']
