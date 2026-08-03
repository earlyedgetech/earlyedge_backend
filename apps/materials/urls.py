from django.urls import path

from . import views

app_name = 'materials'

urlpatterns = [
    # Student-facing
    path('student/shared/', views.MaterialsSharedListView.as_view(), name='student-shared-list'),

    # Dashboard (RBAC)
    path('dashboard/categories/', views.MaterialCategoryListCreateView.as_view(), name='category-list-create'),
    path('dashboard/categories/<int:pk>/', views.MaterialCategoryDetailView.as_view(), name='category-detail'),
    path(
        'dashboard/subcategories/',
        views.MaterialSubcategoryListCreateView.as_view(),
        name='subcategory-list-create',
    ),
    path(
        'dashboard/subcategories/<int:pk>/',
        views.MaterialSubcategoryDetailView.as_view(),
        name='subcategory-detail',
    ),
    path('dashboard/files/', views.MaterialFileListCreateView.as_view(), name='file-list-create'),
    path('dashboard/files/<int:pk>/', views.MaterialFileDetailView.as_view(), name='file-detail'),
    path('dashboard/files/<int:pk>/share/', views.MaterialFileShareView.as_view(), name='file-share'),
]
