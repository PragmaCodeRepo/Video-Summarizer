from rest_framework import serializers
from .models import Video

class VideoSerializer(serializers.ModelSerializer):
    sourceUrl = serializers.URLField(source='source_url', required=False, allow_blank=True)
    sourceType = serializers.CharField(source='source_type', required=False)
    keyTopics = serializers.ListField(source='key_topics', child=serializers.CharField(), required=False)
    kbScore = serializers.IntegerField(source='kb_score', required=False, min_value=0, max_value=100)
    trainingReady = serializers.BooleanField(source='training_ready', required=False)
    analysisMode = serializers.CharField(source='analysis_mode', required=False)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    transcript = serializers.CharField(write_only=True, required=False, allow_blank=True)
    class Meta:
        model = Video
        fields = ['id', 'title', 'sourceUrl', 'sourceType', 'summary', 'transcript', 'categories', 'keyTopics', 'duration', 'language', 'kbScore', 'trainingReady', 'status', 'analysisMode', 'createdAt', 'updatedAt']
