import uuid

from common.models import TimeStampedModel
from django.db import models


class UploadSession(TimeStampedModel):
    """Tracks one chunked file upload from the dashboard to Terabox.

    A session is opened (precreate), fed chunks in order, then completed
    (create/merge on Terabox's side). `bytes_uploaded` lets any client poll
    progress, though in practice the frontend already knows its own progress
    from each chunk request's upload event — this field is for server-side
    visibility (admin panel, crash recovery) rather than being the primary
    progress source.
    """

    PURPOSE_CHOICES = (
        ('course_thumbnail', 'Course Thumbnail'),
        ('course_banner', 'Course Banner'),
        ('course_intro_video', 'Course Intro Video'),
        ('course_materials', 'Course Materials'),
        ('material_file', 'Material File'),
        ('live_session_recording', 'Live Session Recording'),
        ('lead_document', 'Lead Document'),
    )
    STATUS_CHOICES = (
        ('uploading', 'Uploading'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    total_size = models.BigIntegerField()
    chunk_size = models.BigIntegerField(default=4 * 1024 * 1024)
    bytes_uploaded = models.BigIntegerField(default=0)

    terabox_uploadid = models.CharField(max_length=255, blank=True)
    terabox_path = models.CharField(max_length=500, blank=True)
    block_md5_list = models.JSONField(default=list, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='uploading')
    error_message = models.CharField(max_length=500, blank=True)
    result_url = models.URLField(blank=True)

    created_by = models.ForeignKey(
        'admin_security.AdminMember', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='upload_sessions',
    )

    class Meta:
        db_table = 'upload_sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.filename} ({self.status})'

    @property
    def progress_percent(self):
        if not self.total_size:
            return 0
        return round((self.bytes_uploaded / self.total_size) * 100)
