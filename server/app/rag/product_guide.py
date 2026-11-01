"""Reviewed public product help, bound to a fixed local Markdown source.

This module never accepts a filesystem path or host URL from a document. Its
review date is release metadata, not an automatically refreshed freshness claim.
"""
from hashlib import sha256
from html import escape
from pathlib import Path
import re


_GUIDE_PATH = Path(__file__).resolve().parents[3] / 'data' / 'knowledge' / 'en' / 'product-guide.md'
_CHECKED_AT = '2026-10-31'


def product_document() -> dict:
    """Return a fresh canonical record for the exact reviewed UTF-8 source."""
    text = _GUIDE_PATH.read_text(encoding='utf-8')
    return {
        'document_id': 'product-guide',
        'title': 'Rental assistant user guide',
        'source_url': '/api/v1/rag/product-guide',
        'source_type': 'product_guide',
        'language': 'en',
        'jurisdiction': 'PRODUCT',
        'scope': 'public',
        'checked_at': _CHECKED_AT,
        'published_at': None,
        'document_version': sha256(text.encode('utf-8')).hexdigest(),
        'capture_method': 'Local reviewed product documentation',
        'text': text,
    }


def validate_product_document(doc: dict) -> None:
    """Reject any record other than the complete local reviewed document.

    Comparing all fields also rejects extra case, upload, path or private data;
    a caller cannot bless changed content by recomputing its hash.
    """
    if not isinstance(doc, dict) or doc != product_document():
        raise ValueError('Product guide must match the reviewed local document')


def product_guide_html(doc: dict) -> str:
    """Render only trusted content as escaped text, headings and simple lists.

    Raw HTML, Markdown links and images are never interpreted. There are no
    scripts, user-selected resources, external assets or executable URLs.
    """
    validate_product_document(doc)
    blocks = []
    paragraph = []
    in_list = False

    def flush_paragraph():
        if paragraph:
            blocks.append('<p>' + escape(' '.join(paragraph)) + '</p>')
            paragraph.clear()

    def close_list():
        nonlocal in_list
        if in_list:
            blocks.append('</ul>')
            in_list = False

    for line in doc['text'].splitlines():
        heading = re.fullmatch(r'(#{1,6})\s+(.+)', line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading[1])
            blocks.append(f'<h{level}>' + escape(heading[2]) + f'</h{level}>')
        elif line.startswith('- '):
            flush_paragraph()
            if not in_list:
                blocks.append('<ul>')
                in_list = True
            blocks.append('<li>' + escape(line[2:]) + '</li>')
        elif not line.strip():
            flush_paragraph()
            close_list()
        else:
            close_list()
            paragraph.append(line.strip())
    flush_paragraph()
    close_list()
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>' + escape(doc['title']) + '</title>'
        '<style>body{margin:0;background:#f7f8fa;color:#172331;font:18px/1.65 system-ui,sans-serif}'
        'main{max-width:850px;margin:auto;padding:32px 24px 72px;background:white;overflow-wrap:anywhere}'
        'h1,h2,h3,h4,h5,h6{line-height:1.25}h2{margin-top:2em}li{margin:.5em 0}'
        'footer{margin-top:3em;font-size:.85em;color:#4b5563}</style></head><body><main>'
        + '\n'.join(blocks)
        + '<footer>Reviewed release: ' + escape(doc['checked_at'])
        + ' · Document version: ' + escape(doc['document_version'])
        + '</footer></main></body></html>'
    )
