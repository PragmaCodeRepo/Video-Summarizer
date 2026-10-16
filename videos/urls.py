from django.urls import path
from .views import VideoDetailView, VideoListCreateView, analyze, health, reanalyze, upload_video

urlpatterns = [
    path('health/', health, name='health'),
    path('analyze/', analyze, name='analyze'),
    path('videos/upload/', upload_video, name='video-upload'),
    path('videos/', VideoListCreateView.as_view(), name='video-list'),
    path('videos/<uuid:pk>/', VideoDetailView.as_view(), name='video-detail'),
    path('videos/<uuid:pk>/reanalyze/', reanalyze, name='video-reanalyze'),
]
