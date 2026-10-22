"""Offline provider directory with source metadata; never contacts a supplier."""
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlsplit

CATEGORIES = {'electricity', 'gas', 'internet', 'water', 'cleaner', 'removalist'}


class ProviderCatalog:
    def __init__(self, value=None):
        value = json.loads(Path(__file__).with_name('providers.json').read_text()) if value is None else value
        if not isinstance(value, dict) or not isinstance(value.get('providers'), list) or not isinstance(value.get('checked_on'), str):
            raise ValueError('Invalid living-provider directory')
        seen = set()
        for provider in value['providers']:
            if (not isinstance(provider, dict) or not isinstance(provider.get('id'), str)
                    or not provider['id'] or provider['id'] in seen
                    or not isinstance(provider.get('categories'), list)
                    or not provider['categories'] or any(c not in CATEGORIES for c in provider['categories'])):
                raise ValueError('Invalid or duplicate living provider')
            for field in ('website', 'contact_url', 'source_url'):
                url = urlsplit(provider[field])
                if url.scheme != 'https' or not url.hostname or url.username or url.password:
                    raise ValueError('Provider links must use public HTTPS URLs')
            seen.add(provider['id'])
        self._directory = deepcopy(value)
        self.providers = {p['id']: deepcopy(p) for p in value['providers']}

    def directory(self):
        return deepcopy(self._directory)
