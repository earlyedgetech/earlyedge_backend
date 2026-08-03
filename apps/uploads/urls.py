from django.urls import path

from . import views

app_name = 'uploads'

urlpatterns = [
    path('sessions/', views.UploadSessionCreateView.as_view(), name='session-create'),
    path('sessions/<uuid:session_id>/chunk/<int:index>/', views.UploadSessionChunkView.as_view(), name='session-chunk'),
    path('sessions/<uuid:session_id>/complete/', views.UploadSessionCompleteView.as_view(), name='session-complete'),
]
