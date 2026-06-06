"""
KHANDHARS CHAT - File Upload Utility
Handles uploads to Cloudinary or local storage
"""
import os
import uuid
import mimetypes
from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_TYPES = {
    'image': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
    'video': {'mp4', 'webm', 'mov', 'avi'},
    'audio': {'mp3', 'wav', 'ogg', 'm4a', 'aac'},
    'document': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'ppt', 'pptx'},
    'voice': {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'webm'},
}

MAX_SIZES = {
    'image': 10 * 1024 * 1024,     # 10MB
    'video': 50 * 1024 * 1024,     # 50MB
    'audio': 20 * 1024 * 1024,     # 20MB
    'document': 25 * 1024 * 1024,  # 25MB
    'voice': 10 * 1024 * 1024,     # 10MB
}


def get_extension(filename):
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def handle_file_upload(file, folder='uploads', allowed_types='image'):
    """
    Handle file upload to Cloudinary or local storage.
    Returns dict: {success, url, public_id, thumbnail_url, file_size, mime_type, error}
    """
    if not file or not file.filename:
        return {'success': False, 'error': 'No file provided'}

    filename = secure_filename(file.filename)
    ext = get_extension(filename)

    # Validate extension
    allowed_exts = ALLOWED_TYPES.get(allowed_types, set())
    if ext not in allowed_exts:
        return {'success': False, 'error': f'File type .{ext} not allowed'}

    # Read file content
    file_content = file.read()
    file_size = len(file_content)
    file.seek(0)

    # Check file size
    max_size = MAX_SIZES.get(allowed_types, 50 * 1024 * 1024)
    if file_size > max_size:
        from .helpers import format_file_size
        return {'success': False, 'error': f'File too large. Max size: {format_file_size(max_size)}'}

    mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    # Try Cloudinary first
    cloud_name = current_app.config.get('CLOUDINARY_CLOUD_NAME')
    if cloud_name:
        return _upload_to_cloudinary(file, filename, folder, allowed_types, mime_type, file_size)

    # Fallback to local storage
    return _upload_local(file, filename, folder, mime_type, file_size)


def _upload_to_cloudinary(file, filename, folder, resource_type_hint, mime_type, file_size):
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=current_app.config['CLOUDINARY_CLOUD_NAME'],
            api_key=current_app.config['CLOUDINARY_API_KEY'],
            api_secret=current_app.config['CLOUDINARY_API_SECRET'],
        )

        resource_type = 'image' if resource_type_hint == 'image' else \
                        'video' if resource_type_hint in ('video', 'audio', 'voice') else 'raw'

        public_id = f'{folder}/{uuid.uuid4().hex}'
        result = cloudinary.uploader.upload(
            file,
            public_id=public_id,
            resource_type=resource_type,
            folder='khandhars_chat',
            overwrite=False,
        )

        thumbnail_url = ''
        if resource_type == 'image':
            thumbnail_url = result.get('secure_url', '').replace('/upload/', '/upload/w_400,h_400,c_fill/')
        elif resource_type == 'video':
            thumbnail_url = result.get('secure_url', '').replace('/upload/', '/upload/so_0,w_400,h_300,c_fill/')

        return {
            'success': True,
            'url': result.get('secure_url', ''),
            'public_id': result.get('public_id', ''),
            'thumbnail_url': thumbnail_url,
            'file_size': file_size,
            'mime_type': mime_type,
            'filename': filename,
        }
    except Exception as e:
        current_app.logger.error(f'Cloudinary upload error: {e}')
        return {'success': False, 'error': 'Upload failed. Please try again.'}


def _upload_local(file, filename, folder, mime_type, file_size):
    """Fallback local file storage."""
    try:
        upload_dir = os.path.join(current_app.static_folder, 'uploads', folder)
        os.makedirs(upload_dir, exist_ok=True)

        unique_name = f'{uuid.uuid4().hex}_{filename}'
        file_path = os.path.join(upload_dir, unique_name)
        file.save(file_path)

        url = f'/static/uploads/{folder}/{unique_name}'
        return {
            'success': True,
            'url': url,
            'public_id': f'{folder}/{unique_name}',
            'thumbnail_url': url,
            'file_size': file_size,
            'mime_type': mime_type,
            'filename': unique_name,
        }
    except Exception as e:
        current_app.logger.error(f'Local upload error: {e}')
        return {'success': False, 'error': 'Upload failed.'}


def delete_file(public_id):
    """Delete file from Cloudinary."""
    if not public_id:
        return
    try:
        cloud_name = current_app.config.get('CLOUDINARY_CLOUD_NAME')
        if cloud_name:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=current_app.config['CLOUDINARY_API_KEY'],
                api_secret=current_app.config['CLOUDINARY_API_SECRET'],
            )
            cloudinary.uploader.destroy(public_id)
    except Exception as e:
        current_app.logger.error(f'Cloudinary delete error: {e}')
