"""Bounded local user uploads, with case ownership and atomic durable receipts."""
import hashlib
from io import BytesIO
import os
import re
import tempfile
from urllib.parse import unquote, quote
import warnings

from fastapi import Request
from fastapi.responses import FileResponse
from ..common import ApiError, now, opaque_ref, request_id, require, uid

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_CASE_FILES = 50
MAX_CASE_BYTES = 100 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
MEDIA_TYPES = ('application/octet-stream', 'image/jpeg', 'image/png', 'application/pdf')


def safe_filename(encoded):
    require(isinstance(encoded, str) and len(encoded) <= 2160 and
            not re.search(r'%(?![0-9A-Fa-f]{2})', encoded), 422, 'invalid_filename', 'Provide a valid attachment filename.')
    try:
        filename = unquote(encoded, encoding='utf-8', errors='strict')
    except UnicodeError:
        raise ApiError(422, 'invalid_filename', 'The filename must be valid UTF-8.') from None
    require(0 < len(filename) <= 180 and filename.strip() == filename and filename not in ('.', '..')
            and not any(c in filename for c in ('/', '\\', ':'))
            and not any(ord(c) < 32 or ord(c) == 127 for c in filename),
            422, 'invalid_filename', 'Filenames cannot contain paths or control characters and must not exceed 180 characters.')
    return filename


def detected_media(content):
    if content.startswith(b'%PDF-'):
        return 'application/pdf'
    format_ = 'PNG' if content.startswith(b'\x89PNG\r\n\x1a\n') else 'JPEG' if content.startswith(b'\xff\xd8\xff') else None
    require(format_ is not None, 422, 'invalid_attachment', 'Attachments must be JPEG, PNG or PDF files.')
    try:
        from PIL import Image
    except ImportError:
        raise ApiError(503, 'image_validation_unavailable', 'Image validation is unavailable. Check backend dependencies.') from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                require(image.format == format_ and image.width * image.height <= MAX_IMAGE_PIXELS,
                        422, 'invalid_attachment', 'The image format is invalid or exceeds 30 million pixels.')
                image.verify()
            # JPEG verify() checks headers; decoding also catches a missing/truncated scan tail.
            with Image.open(BytesIO(content)) as image:
                image.load()
    except ApiError:
        raise
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ApiError(422, 'invalid_attachment', 'The image is damaged or failed format validation.') from None
    return 'image/png' if format_ == 'PNG' else 'image/jpeg'


class LivingAttachments:
    def __init__(self, ctx):
        self.ctx = ctx
        self.directory = self.ctx.repo.directory / 'living-files'

    def _authorize(self, db, case_id, repair_id=None):
        self.ctx.get(db, 'case', case_id)
        if repair_id is not None:
            opaque_ref(repair_id)
            living = self.ctx.repo.get(db, 'living_services', case_id) or {}
            require(any(r['repair_id'] == repair_id for r in living.get('repairs', [])),
                    404, 'not_found', 'Repair record not found for this case.')

    def _index(self, db, case_id):
        return self.ctx.repo.get(db, 'living_attachment_index', case_id) or {'ids': []}

    def list(self, case_id: str):
        with self.ctx.repo.transaction() as db:
            self._authorize(db, case_id)
            index = self._index(db, case_id)
            return {'items': [self.ctx.get(db, 'living_attachment', identifier)['metadata'] for identifier in index['ids']]}

    async def upload(self, case_id: str, request: Request, purpose: str = 'repair', repair_id: str | None = None):
        # Reject unknown cases/repair references before reading binary content.
        with self.ctx.repo.transaction() as db:
            self._authorize(db, case_id, repair_id)
        require(purpose in ('repair', 'receipt', 'moveout'), 422, 'invalid_input', 'Choose repair, receipt or move-out as the attachment purpose.')
        logical_id = request_id(request.headers.get('X-Request-Id', ''))
        filename = safe_filename(request.headers.get('X-Filename', ''))
        declared_media = request.headers.get('Content-Type', '').split(';')[0].strip().lower()
        require(declared_media in MEDIA_TYPES, 415, 'unsupported_media_type', 'Upload JPEG, PNG, PDF or binary content directly.')
        length = request.headers.get('Content-Length')
        if length is not None:
            require(length.isascii() and length.isdigit(), 422, 'invalid_input', 'Invalid attachment length.')
            require(int(length) <= MAX_FILE_BYTES, 413, 'attachment_too_large', 'Each attachment may be at most 10 MiB.')
        content = bytearray()
        async for chunk in request.stream():
            require(len(content) + len(chunk) <= MAX_FILE_BYTES, 413, 'attachment_too_large', 'Each attachment may be at most 10 MiB.')
            content.extend(chunk)
        content = bytes(content)
        identity = {'sha256': hashlib.sha256(content).hexdigest(), 'filename': filename,
                    'purpose': purpose, 'repair_id': repair_id}
        key = case_id + ':' + logical_id
        written = temporary = None
        try:
            with self.ctx.repo.transaction() as db:
                self._authorize(db, case_id, repair_id)
                old = self.ctx.receipt(db, 'living_attachment_receipt', key, identity)
                if old:
                    return old['result']
                media = detected_media(content)
                require(declared_media == 'application/octet-stream' or declared_media == media,
                        422, 'invalid_attachment', 'The attachment content does not match the declared format.')
                index = self._index(db, case_id)
                require(len(index['ids']) < MAX_CASE_FILES, 409, 'attachment_limit', 'Each case can contain at most 50 attachments.')
                total = sum(self.ctx.get(db, 'living_attachment', identifier)['metadata']['size_bytes'] for identifier in index['ids'])
                require(total + len(content) <= MAX_CASE_BYTES, 409, 'attachment_limit', 'Total attachments per case may be at most 100 MiB.')
                attachment_id = uid('attachment')
                file_ref = attachment_id + '.bin'
                metadata = {'attachment_id': attachment_id, 'case_id': case_id, 'filename': filename,
                            'mime_type': media, 'size_bytes': len(content), 'sha256': identity['sha256'],
                            'purpose': purpose, 'repair_id': repair_id, 'created_at': now(),
                            'download_url': '/api/v1/cases/' + quote(case_id, safe='') + '/living-services/attachments/' + attachment_id,
                            'verification_status': 'user_uploaded_unverified'}
                self.directory.mkdir(mode=0o700, exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix='.upload-', dir=self.directory, delete=False) as handle:
                    temporary = handle.name
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                written = self.directory / file_ref
                os.replace(temporary, written)
                temporary = None
                self.ctx.repo.put(db, 'living_attachment', attachment_id,
                                  {'case_id': case_id, 'file_ref': file_ref, 'metadata': metadata})
                index['ids'].append(attachment_id)
                self.ctx.repo.put(db, 'living_attachment_index', case_id, index)
                self.ctx.save_receipt(db, 'living_attachment_receipt', key, identity, metadata)
            return metadata
        except BaseException:
            if written is not None:
                written.unlink(missing_ok=True)
            if temporary is not None:
                from pathlib import Path
                Path(temporary).unlink(missing_ok=True)
            raise

    def download(self, case_id: str, attachment_id: str):
        with self.ctx.repo.transaction() as db:
            self._authorize(db, case_id)
            saved = self.ctx.get(db, 'living_attachment', attachment_id)
            require(saved['case_id'] == case_id, 404, 'not_found', 'Attachment not found for this case.')
            metadata = saved['metadata']
            path = self.directory / saved['file_ref']
            require(path.is_file(), 404, 'not_found', 'Attachment content is missing.')
        return FileResponse(path, media_type=metadata['mime_type'], filename=metadata['filename'],
                            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
