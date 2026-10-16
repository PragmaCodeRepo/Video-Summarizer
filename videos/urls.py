from django.urls import path
from .auth_views import CurrentAccountView, LoginView, LogoutView, RegisterView
from .views import VideoDetailView, VideoListCreateView, analyze, health, reanalyze, upload_video

urlpatterns = [
    path('health/', health, name='health'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', CurrentAccountView.as_view(), name='auth-current-account'),
    path('analyze/', analyze, name='analyze'),
    path('videos/upload/', upload_video, name='video-upload'),
    path('videos/', VideoListCreateView.as_view(), name='video-list'),
    path('videos/<uuid:pk>/', VideoDetailView.as_view(), name='video-detail'),
    path('videos/<uuid:pk>/reanalyze/', reanalyze, name='video-reanalyze'),
]
