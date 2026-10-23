import logging
import os
import subprocess
import time
import tempfile

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from openai import OpenAIError

from videos.models import SharePointImport, Video
from videos.services import analyze_transcript, transcribe_video
from videos.sharepoint import GraphClient, SharePointError, download_to_temp

logger = logging.getLogger(__name__)


def analyze_item(job, graph, item):
    name = str(item.get('name') or 'SharePoint video')[:300]
    source_url = str(item.get('webUrl') or '')
    existing = Video.objects.filter(owner=job.owner, source_url=source_url).first() if source_url else None
    if existing and existing.status == 'indexed':
        return 'skipped', None

    video = existing or Video.objects.create(
        owner=job.owner, title=os.path.splitext(name)[0][:300], source_url=source_url,
        source_type='sharepoint', status='processing', analysis_mode='ai',
    )
    video.status = 'processing'
    video.save(update_fields=['status', 'updated_at'])
    path = None
    try:
        size = int(item.get('size') or 0)
        if size > 500 * 1024 * 1024:
            raise SharePointError('Video exceeds the 500 MB processing limit.')
        path = download_to_temp(graph, item)
        with open(path, 'rb') as stream:
            uploaded = File(stream, name=os.path.basename(name))
            transcript = transcribe_video(uploaded)
        result = analyze_transcript(transcript, video.title)
        video.transcript = transcript
        video.summary = result['summary']
        video.categories = result['categories']
        video.key_topics = result['keyTopics']
        video.kb_score = result['kbScore']
        video.training_ready = result['trainingReady']
        video.analysis_mode = result['analysisMode']
        video.status = 'indexed'
        video.save()
        return 'imported', None
    except (SharePointError, OpenAIError, RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        video.status = 'failed'
        video.save(update_fields=['status', 'updated_at'])
        logger.warning('SharePoint video analysis failed for item id=%s error=%s', item.get('id', ''), type(error).__name__)
        message = str(error) if isinstance(error, (SharePointError, RuntimeError, ValueError)) else 'Video analysis failed. Check the backend OpenAI configuration and connectivity.'
        return 'failed', {'title': name, 'detail': message[:300]}
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def process_job(job_id):
    close_old_connections()
    try:
        with transaction.atomic():
            job = SharePointImport.objects.select_related('owner').get(pk=job_id)
            if job.status not in ('queued', 'processing'):
                return
            job.status = 'processing'
            job.save(update_fields=['status', 'updated_at'])

        graph = GraphClient()
        try:
            items = graph.list_videos()
            job.total = len(items)
            job.save(update_fields=['total', 'updated_at'])
            for item in items:
                outcome, error = analyze_item(job, graph, item)
                job.processed += 1
                if outcome == 'imported':
                    job.imported += 1
                elif outcome == 'failed':
                    job.failed += 1
                    if len(job.errors) < 50:
                        job.errors.append(error)
                job.save(update_fields=['processed', 'imported', 'failed', 'errors', 'updated_at'])
        finally:
            graph.close()

        job.status = 'completed_with_errors' if job.failed else 'completed'
        job.save(update_fields=['status', 'updated_at'])
    except SharePointError as error:
        SharePointImport.objects.filter(pk=job_id).update(status='failed', errors=[{'detail': str(error)[:300]}])
    except Exception as error:
        logger.exception('SharePoint import failed: job=%s error=%s', job_id, type(error).__name__)
        SharePointImport.objects.filter(pk=job_id).update(status='failed', errors=[{'detail': 'Import failed unexpectedly. Check the backend worker logs.'}])
    finally:
        close_old_connections()


class Command(BaseCommand):
    help = 'Process queued SharePoint video folder imports.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process at most one queued import and exit.')
        parser.add_argument('--poll-seconds', type=int, default=5, help='Seconds between queue checks.')

    def handle(self, *args, **options):
        poll_seconds = max(1, options['poll_seconds'])
        self.stdout.write('SharePoint import worker started.')
        while True:
            close_old_connections()
            job = SharePointImport.objects.filter(status='queued').order_by('created_at').first()
            if job:
                self.stdout.write(f'Processing SharePoint import {job.id}.')
                process_job(job.id)
                self.stdout.write(f'Finished SharePoint import {job.id}.')
                if options['once']:
                    return
            elif options['once']:
                self.stdout.write('No queued SharePoint imports.')
                return
            else:
                time.sleep(poll_seconds)
