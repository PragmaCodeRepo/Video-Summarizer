import uuid
from django.db import models

class Video(models.Model):
    CATEGORIES = [('Design', 'Design'), ('Content', 'Content'), ('Marketing', 'Marketing')]
    STATUSES = [('pending', 'Pending'), ('processing', 'Processing'), ('indexed', 'Indexed'), ('failed', 'Failed')]
    MODES = [('ai', 'AI'), ('manual', 'Manual')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    source_url = models.URLField(blank=True)
    source_type = models.CharField(max_length=20, default='transcript')
    summary = models.TextField(blank=True)
    transcript = models.TextField(blank=True)
    categories = models.JSONField(default=list)
    key_topics = models.JSONField(default=list)
    duration = models.CharField(max_length=30, blank=True)
    language = models.CharField(max_length=30, blank=True)
    kb_score = models.PositiveSmallIntegerField(default=0)
    training_ready = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUSES, default='pending')
    analysis_mode = models.CharField(max_length=20, choices=MODES, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

