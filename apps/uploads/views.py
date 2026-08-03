import hashlib

from authentication.authentication import AdminMemberJWTAuthentication
from authentication.permissions import IsAdminMember
from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UploadSession
from .terabox_client import TeraboxClient, TeraboxError, chunk_count

# Any dashboard permission that already gates the feature doing the
# uploading is accepted here — courses and materials both funnel through
# this same session pipeline.
UPLOAD_PERMISSIONS = ('manage_courses', 'manage_own_courses', 'manage_materials')


class CanUpload(BasePermission):
    def has_permission(self, request, view):
        return any(request.user.has_permission(codename) for codename in UPLOAD_PERMISSIONS)


class UploadSessionCreateView(APIView):
    """Starts a chunked upload. Returns the chunk size the client should
    slice the file into, and a session id to address subsequent calls."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, CanUpload]

    def post(self, request):
        filename = request.data.get('filename')
        size = int(request.data.get('size') or 0)
        content_type = request.data.get('content_type', '')
        purpose = request.data.get('purpose')

        if not filename or not size or purpose not in dict(UploadSession.PURPOSE_CHOICES):
            return Response({'detail': 'filename, size, and a valid purpose are required.'}, status=400)

        session = UploadSession.objects.create(
            purpose=purpose,
            filename=filename,
            content_type=content_type,
            total_size=size,
            created_by=request.user,
        )

        client = TeraboxClient()
        try:
            precreate = client.precreate(filename, size, block_md5_list=[])
        except TeraboxError as exc:
            session.status = 'failed'
            session.error_message = str(exc)
            session.save(update_fields=['status', 'error_message'])
            return Response({'detail': str(exc)}, status=502)

        session.terabox_uploadid = precreate['uploadid']
        session.terabox_path = precreate['path']
        session.save(update_fields=['terabox_uploadid', 'terabox_path'])

        return Response({
            'session_id': session.id,
            'chunk_size': session.chunk_size,
            'chunk_count': chunk_count(size, session.chunk_size),
            'terabox_configured': client.configured,
        }, status=201)


class UploadSessionChunkView(APIView):
    """Relays one chunk straight through to Terabox and records progress."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, CanUpload]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def put(self, request, session_id, index):
        session = get_object_or_404(UploadSession, id=session_id, created_by=request.user)
        if session.status != 'uploading':
            return Response({'detail': f'Session is {session.status}, cannot accept chunks.'}, status=409)

        chunk_file = request.data.get('chunk')
        if chunk_file is None:
            return Response({'detail': 'chunk file field is required.'}, status=400)
        chunk_bytes = chunk_file.read()

        client = TeraboxClient()
        try:
            result = client.upload_chunk(session.terabox_path, session.terabox_uploadid, index, chunk_bytes)
        except TeraboxError as exc:
            session.status = 'failed'
            session.error_message = str(exc)
            session.save(update_fields=['status', 'error_message'])
            return Response({'detail': str(exc)}, status=502)

        block_md5_list = session.block_md5_list or []
        # Chunks may arrive out of order in theory; keep the list positional.
        while len(block_md5_list) <= index:
            block_md5_list.append(None)
        block_md5_list[index] = result['md5'] or hashlib.md5(chunk_bytes).hexdigest()

        session.block_md5_list = block_md5_list
        session.bytes_uploaded = min(session.total_size, session.bytes_uploaded + len(chunk_bytes))
        session.save(update_fields=['block_md5_list', 'bytes_uploaded'])

        return Response({
            'bytes_uploaded': session.bytes_uploaded,
            'progress_percent': session.progress_percent,
        })


class UploadSessionCompleteView(APIView):
    """Finalizes the upload on Terabox's side and returns the shareable URL
    to store on the owning record (Course media field, MaterialFile, ...)."""

    authentication_classes = [AdminMemberJWTAuthentication]
    permission_classes = [IsAdminMember, CanUpload]

    def post(self, request, session_id):
        session = get_object_or_404(UploadSession, id=session_id, created_by=request.user)
        if session.status == 'completed':
            return Response({'url': session.result_url, 'size': session.total_size})
        if session.status != 'uploading':
            return Response({'detail': f'Session is {session.status}, cannot complete.'}, status=409)

        client = TeraboxClient()
        try:
            result = client.create(
                session.filename, session.terabox_path, session.total_size,
                session.terabox_uploadid, session.block_md5_list,
            )
        except TeraboxError as exc:
            session.status = 'failed'
            session.error_message = str(exc)
            session.save(update_fields=['status', 'error_message'])
            return Response({'detail': str(exc)}, status=502)

        session.status = 'completed'
        session.result_url = result['url']
        session.save(update_fields=['status', 'result_url'])

        return Response({'url': session.result_url, 'size': session.total_size})
