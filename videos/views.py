import subprocess
import logging
from openai import OpenAIError
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
from .models import Video
from .serializers import VideoSerializer
from .services import analyze_transcript, transcribe_video

logger = logging.getLogger(__name__)

def openai_failure(error, stage):
    error_type = type(error).__name__
    code = getattr(error, 'status_code', None)
    logger.error('OpenAI %s failed: exception=%s status=%s', stage, error_type, code)
    if error_type == 'AuthenticationError' or code == 401:
        detail = 'OpenAI rejected the API key. Verify OPENAI_API_KEY in backend/.env, then restart Django.'
    elif error_type == 'PermissionDeniedError' or code == 403:
        detail = f'OpenAI denied access during {stage}. Check project access and model permissions.'
    elif error_type == 'RateLimitError' or code == 429:
        detail = f'OpenAI rate or usage limit reached during {stage}. Check project quota and billing.'
    elif code == 400:
        detail = f'OpenAI rejected the {stage} request. Check the media format, duration, and model settings.'
    elif code and code >= 500:
        detail = f'OpenAI had a temporary service error during {stage}. Try again shortly.'
    else:
        detail = f'OpenAI {stage} failed ({error_type}{f", HTTP {code}" if code else ""}). Check backend connectivity and configuration.'
    return Response({'detail': detail}, status=status.HTTP_502_BAD_GATEWAY)

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({'status': 'ok', 'service': 'video-intelligence-api', 'openaiConfigured': bool(settings.OPENAI_API_KEY)})

class VideoListCreateView(generics.ListCreateAPIView):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer

class VideoDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def analyze(request):
    title = str(request.data.get('title', '')).strip()
    transcript = str(request.data.get('transcript', '')).strip()
    if not title or not transcript:
        return Response({'detail': 'Both title and transcript are required.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(title) > 300:
        return Response({'detail': 'Title must be 300 characters or fewer.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        return Response(analyze_transcript(transcript, title))
    except RuntimeError as error:
        return Response({'detail': str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except OpenAIError as error:
        return openai_failure(error, 'transcript analysis')
    except (ValueError, TypeError) as error:
        return Response({'detail': str(error)}, status=status.HTTP_502_BAD_GATEWAY)

@api_view(['POST'])
@permission_classes([AllowAny])
def reanalyze(request, pk):
    try:
        video = Video.objects.get(pk=pk)
    except Video.DoesNotExist:
        return Response({'detail': 'Video not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not video.transcript:
        return Response({'detail': 'This video has no stored transcript to analyze.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = analyze_transcript(video.transcript, video.title)
        for key, field in [('summary', 'summary'), ('categories', 'categories'), ('keyTopics', 'key_topics'), ('kbScore', 'kb_score'), ('trainingReady', 'training_ready'), ('analysisMode', 'analysis_mode')]:
            setattr(video, field, result[key])
        video.status = 'indexed'
        video.save()
        from .serializers import VideoSerializer
        return Response(VideoSerializer(video).data)
    except RuntimeError as error:
        return Response({'detail': str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except OpenAIError as error:
        return openai_failure(error, 'transcript analysis')

@api_view(['POST'])
@permission_classes([AllowAny])
def upload_video(request):
    uploaded = request.FILES.get('file')
    title = str(request.data.get('title', '')).strip() or (uploaded.name.rsplit('.', 1)[0] if uploaded else '')
    if not uploaded:
        return Response({'detail': 'Choose a video file to upload.'}, status=status.HTTP_400_BAD_REQUEST)
    extension = uploaded.name.lower().rsplit('.', 1)[-1] if '.' in uploaded.name else ''
    if extension not in {'mp4', 'mov', 'webm'}:
        return Response({'detail': 'Supported video formats are MP4, MOV, and WEBM.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        transcript = transcribe_video(uploaded)
    except OpenAIError as error:
        return openai_failure(error, 'video transcription')
    except RuntimeError as error:
        return Response({'detail': str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        return Response({'detail': str(error) or 'Could not extract audio from this video.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = analyze_transcript(transcript, title)
    except OpenAIError as error:
        return openai_failure(error, 'video summarization')
    except RuntimeError as error:
        return Response({'detail': str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except (ValueError, TypeError) as error:
        return Response({'detail': str(error)}, status=status.HTTP_502_BAD_GATEWAY)
    try:
        video = Video.objects.create(title=title, source_url=str(request.data.get('sourceUrl', '')), source_type='upload', transcript=transcript,
            summary=result['summary'], categories=result['categories'], key_topics=result['keyTopics'],
            kb_score=result['kbScore'], training_ready=result['trainingReady'], status='indexed', analysis_mode=result['analysisMode'])
        from .serializers import VideoSerializer
        return Response(VideoSerializer(video).data, status=status.HTTP_201_CREATED)
    except RuntimeError as error:
        return Response({'detail': str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except (ValueError, TypeError, OSError, subprocess.TimeoutExpired) as error:
        return Response({'detail': str(error) or 'Video processing failed.'}, status=status.HTTP_400_BAD_REQUEST)
