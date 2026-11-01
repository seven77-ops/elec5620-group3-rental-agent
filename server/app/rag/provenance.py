"""Bind registered public identities and PDF text to reviewed public originals."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from .sources import SOURCES,SOURCE_TYPES,PDF_DOWNLOADS,PDF_SHA256

_ROOT=Path(__file__).resolve().parents[3]
_ORIGINALS={'standard-lease':'standard-lease-2026-09-21.pdf',
            'tenant-information':'tenant-information-2026-10-08.pdf'}


@lru_cache(maxsize=4)
def _pdf_text(identifier,payload):
    from .capture import parse_pdf
    source=next(row for row in SOURCES if row[0]==identifier)
    return parse_pdf(source,payload,checked_at='2026-10-30')


def validate_registered_identity(doc):
    registered={row[0]:row for row in SOURCES}
    urls={row[2]:row[0] for row in SOURCES}
    identifier=doc['document_id'];kind=doc['source_type'];url=doc.get('source_url')
    if identifier in registered:
        if url!=registered[identifier][2] or kind!=SOURCE_TYPES[identifier]:
            raise ValueError('Registered source identity or role changed')
    elif kind in ('official_template','student_guidance'):
        raise ValueError('Unregistered template or university source')
    if url in urls and urls[url]!=identifier:
        raise ValueError('Registered source URL cannot be relabelled')
    if identifier in PDF_DOWNLOADS:
        payload=(_ROOT/'data/knowledge/en/files'/_ORIGINALS[identifier]).read_bytes()
        if sha256(payload).hexdigest()!=PDF_SHA256[identifier]:
            raise ValueError('Reviewed public PDF original changed')
        expected=_pdf_text(identifier,payload)
        for key in ('text','document_version','document_sha256','download_url','page_count','content_hash'):
            if doc.get(key)!=expected[key]:raise ValueError('Public PDF provenance mismatch: '+key)
    elif doc.get('download_url'):
        raise ValueError('Public PDF download is not registered')
