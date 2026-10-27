"""Optional, sourced advertisement photos; never fetched by the API server."""
from datetime import datetime
import json
from urllib.parse import urlsplit


def load_photos(path, listings):
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text())
        if document['schema_version'] != 1 or not isinstance(document['listings'], list):
            raise ValueError('Invalid photo sidecar')
        result = {}
        for entry in document['listings']:
            identifier = entry['listing_id']
            if identifier in result or identifier not in listings or entry['source_url'] != listings[identifier]['source_url']:
                raise ValueError('Photo source must match one known advertisement')
            timestamp = entry['captured_at']
            if not isinstance(timestamp, str) or datetime.fromisoformat(timestamp).tzinfo is None:
                raise ValueError('Photo observation requires an aware ISO timestamp')
            urls = entry['image_urls']
            if not isinstance(urls, list) or not 1 <= len(urls) <= 12 or len(set(urls)) != len(urls):
                raise ValueError('Expected one to twelve unique property photos')
            provenance = {}
            source_host = 'www.domain.com.au'
            if 'photo_source_url' in entry or 'photo_source_kind' in entry:
                page_url = entry['photo_source_url']
                kind = entry['photo_source_kind']
                if (not isinstance(page_url, str) or len(page_url) > 2048
                        or any(c.isspace() or ord(c) < 32 for c in page_url)):
                    raise ValueError('Invalid photo source page')
                page = urlsplit(page_url)
                if (page.scheme != 'https' or page.netloc not in
                        ('www.domain.com.au', 'www.property.com.au', 'www.realestate.com.au')
                        or page.path in ('', '/') or page.query or page.fragment
                        or kind not in ('same_property_advertisement', 'same_property_reference', 'same_property_history')):
                    raise ValueError('Photo reference must name an observed property page')
                source_host = page.netloc
                provenance = {'photo_source_url': page_url, 'photo_source_kind': kind}
            image_host = ('rimh2.domainstatic.com.au' if source_host == 'www.domain.com.au'
                          else 'i2.au.reastatic.net')
            for url in urls:
                if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() or ord(c) < 32 for c in url):
                    raise ValueError('Invalid photo URL')
                parsed = urlsplit(url)
                if (parsed.scheme != 'https' or parsed.netloc != image_host
                        or not parsed.path.startswith('/') or parsed.path == '/'
                        or parsed.query or parsed.fragment):
                    raise ValueError('Photo CDN must match its observed property source')
            result[identifier] = [{'url': url, 'source_url': entry['source_url'], 'captured_at': timestamp,
                                   **provenance} for url in urls]
        return result
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Photo sidecar is malformed') from exc
