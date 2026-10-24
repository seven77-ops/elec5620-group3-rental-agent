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
            for url in urls:
                if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() or ord(c) < 32 for c in url):
                    raise ValueError('Invalid photo URL')
                parsed = urlsplit(url)
                if (parsed.scheme != 'https' or parsed.netloc != 'rimh2.domainstatic.com.au'
                        or not parsed.path.startswith('/') or parsed.path == '/'
                        or parsed.query or parsed.fragment):
                    raise ValueError('Only observed HTTPS Domain CDN photos are accepted')
            result[identifier] = [{'url': url, 'source_url': entry['source_url'], 'captured_at': timestamp} for url in urls]
        return result
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Photo sidecar is malformed') from exc
