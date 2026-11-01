"""Capture only reviewed public sources; PDF originals never come from case uploads."""
import hashlib
import io
import re
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
from pypdf import PdfReader

from .sources import PDF_DOWNLOADS, PDF_SHA256, SOURCES, SOURCE_TYPES

MAX_READER_BYTES = 2_000_000
MAX_PDF_BYTES = 12_000_000
MAX_TEXT = 500_000
OFFICIAL_HOSTS = {'www.nsw.gov.au', 'www.sydney.edu.au'}
ERROR = re.compile(r'403 ERROR|404\s*[-:]?\s*Page not found|Request blocked|Access Denied|SecurityCompromiseError|ROBOTS_DENIED|^Title:\s*(?:Page not found|Error|Forbidden|Just a moment|Attention Required|Unauthorized|Internal Server Error)', re.I | re.M)
HTTP_FAILURE_LABEL = re.compile(
    r'(?:(?:HTTP(?:/\d(?:\.\d)?)?\s+|Error\s+)?[45]\d{2}[\s:–—-]+)?'
    r'(?:Bad Gateway|Service Unavailable|Gateway Time(?:out| Out)|Internal Server Error|'
    r'Bad Request|Not Found|Forbidden|Too Many Requests|Request Timeout|Unauthorized)'
    r'(?:\s*[-|]\s*[^\n]+)?[.!]?', re.I)


def _http_error_page(envelope, text):
    """Error labels belong in the Reader title or leading body line, not prose."""
    title = re.search(r'^Title:[ \t]*([^\n]*)', envelope, re.M)
    first_line = text.strip().splitlines()[0] if text.strip() else ''
    first_line = re.sub(r'^#{1,6}\s+', '', first_line).replace('**', '').strip()
    return bool((title and HTTP_FAILURE_LABEL.fullmatch(title[1].strip())) or
                HTTP_FAILURE_LABEL.fullmatch(first_line))


def _source(source):
    if not isinstance(source, (tuple, list)) or tuple(source) not in SOURCES:
        raise ValueError('Unreviewed public source')
    url = urlsplit(source[2])
    if url.scheme != 'https' or url.hostname not in OFFICIAL_HOSTS or url.username or url.password or url.fragment or url.query:
        raise ValueError('Unapproved source URL')
    return tuple(source)


def _metadata(source, text, checked_at):
    identifier, title, url = _source(source)
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return {'document_id': identifier, 'title': title, 'source_url': url,
            'source_type': SOURCE_TYPES[identifier], 'language': 'en', 'jurisdiction': 'NSW',
            'scope': 'public', 'checked_at': checked_at or datetime.now(ZoneInfo('Australia/Sydney')).date().isoformat(),
            'published_at': None, 'document_version': content_hash, 'content_hash': content_hash, 'text': text}


def parse_source(source, raw, *, checked_at=None):
    """Validate Jina's source envelope, trim site chrome, retain substantive body/tables."""
    source = _source(source)
    if not isinstance(raw, str) or len(raw.encode()) > MAX_READER_BYTES or 'Markdown Content:' not in raw:
        raise ValueError('Unexpected source response: ' + source[0])
    envelope, text = raw.split('Markdown Content:', 1)
    origin = re.search(r'^URL Source: (\S+)\s*$', envelope, re.M)
    if not origin or origin[1] != source[2] or ERROR.search(envelope) or ERROR.search(text[:2000]) or _http_error_page(envelope, text):
        raise ValueError('Unreadable or mismatched source: ' + source[0])
    text = text.strip()
    heading = re.search(r'^# [^\n]+', text, re.M)
    if heading:
        text = text[heading.start():]
    # Normalize heading link labels before detecting NSW footer headings.
    text = re.sub(r'^(#{1,6})\s+(.*)$', lambda m: m[1] + ' ' + re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', m[2]).replace('**', '').strip(), text, flags=re.M)
    footer = re.search(r'^#{2,3} (?:You might also be interested in|Popular|About this website|Related rules and guidance|Related information|Related links|Tagged in|Media)\s*$', text, re.M)
    if footer:
        text = text[:footer.start()].strip()
    if source[0] == 'student-off-campus':
        # University site-wide acknowledgement begins the footer after rental rights.
        text = text.split('\nWe recognise and pay respect to the Elders and communities', 1)[0].strip()
        text = re.sub(r'^\s*(?:h2|_self|cmp-[\w-]+)\s*$', '', text, flags=re.M)
        # The site renders duplicate card lists: discard only malformed duplicate rows.
        text = re.sub(r'^.*\)false[^\n]*\n?', '', text, flags=re.M)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if not 300 <= len(text) <= MAX_TEXT or ERROR.search(text[:2000]) or _http_error_page(envelope, text):
        raise ValueError('Unreadable source: ' + source[0])
    result = _metadata(source, text, checked_at)
    published = re.search(r'^Published Time: ([^\n]+)', envelope, re.M)
    result.update(published_at=published[1] if published else None, capture_method='Jina Reader of official public URL',
                  source_response_sha256=hashlib.sha256(raw.encode()).hexdigest())
    return result


def parse_pdf(source, payload, *, checked_at=None):
    """Extract every page of a verified official PDF and reject populated lease forms."""
    source = _source(source)
    if source[0] not in PDF_DOWNLOADS or not isinstance(payload, bytes) or not payload.startswith(b'%PDF-') or len(payload) > MAX_PDF_BYTES:
        raise ValueError('Invalid approved PDF')
    sha = hashlib.sha256(payload).hexdigest()
    if sha != PDF_SHA256[source[0]]:
        raise ValueError('Official PDF changed; review its public/blank original before capture')
    try:
        reader = PdfReader(io.BytesIO(payload))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
            raise ValueError('Encrypted or excessive PDF')
        if source[0] == 'standard-lease':
            for field in (reader.get_fields() or {}).values():
                if field.get('/V') not in (None, '', '/Off', '/No', False):
                    raise ValueError('Only blank official forms may be captured')
            for page in reader.pages:
                for ref in page.get('/Annots', []):
                    annotation = ref.get_object()
                    if annotation.get('/V') not in (None, '', '/Off', '/No', False):
                        raise ValueError('Only blank official forms may be captured')
        pages = [page.extract_text() or '' for page in reader.pages]
    except Exception as exc:
        raise ValueError('Unreadable or nonblank official PDF') from exc
    if any(len(page.strip()) < 30 for page in pages):
        raise ValueError('PDF contains unextractable pages; manual review required')
    text = '\n\n'.join('## Page ' + str(n) + '\n\n' + page.strip() for n, page in enumerate(pages, 1))
    if not 300 <= len(text) <= MAX_TEXT:
        raise ValueError('Unreadable PDF text')
    result = _metadata(source, text, checked_at)
    result.update(page_count=len(pages), download_url=PDF_DOWNLOADS[source[0]], document_sha256=sha,
                  document_version=sha, capture_method='Official public PDF; pypdf full page text')
    return result


def _fetch(client, url, limit):
    # The caller supplies only URLs derived from the fixed registry and PDF mapping.
    with client.stream('GET', url, follow_redirects=False, timeout=55) as response:
        if response.is_redirect:
            raise ValueError('Source redirects require review')
        response.raise_for_status()
        length = response.headers.get('content-length')
        if length and int(length) > limit:
            raise ValueError('Source response too large')
        result = bytearray()
        for part in response.iter_bytes():
            result.extend(part)
            if len(result) > limit:
                raise ValueError('Source response too large')
        return bytes(result), dict(response.headers)


def capture(source, *, client=None, checked_at=None):
    """Fetch a registered source only. Optional client enables fully offline tests."""
    source = _source(source)
    if client is None:
        with httpx.Client(trust_env=False) as owned_client:
            return capture(source, client=owned_client, checked_at=checked_at)
    raw, _ = _fetch(client, 'https://r.jina.ai/' + source[2], MAX_READER_BYTES)
    landing = parse_source(source, raw.decode('utf-8'), checked_at=checked_at)
    download = PDF_DOWNLOADS.get(source[0])
    if not download:
        return landing
    parsed = urlsplit(download)
    if parsed.scheme != 'https' or parsed.hostname != 'www.nsw.gov.au' or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError('Unapproved PDF host')
    if '](' + download + ')' not in landing['text']:
        raise ValueError('Official landing no longer links the approved PDF; review required')
    payload, headers = _fetch(client, download, MAX_PDF_BYTES)
    if 'application/pdf' not in headers.get('content-type', '').lower():
        raise ValueError('Official download did not return a PDF')
    result = parse_pdf(source, payload, checked_at=checked_at)
    version = re.search(r'File last updated on:\s*([^\n]+)', landing['text'])
    result.update(published_at=landing['published_at'], landing_content_hash=landing['content_hash'],
                  source_response_sha256=landing['source_response_sha256'],
                  official_version_label=version[1].strip() if version else None,
                  last_modified=headers.get('last-modified'))
    return result
