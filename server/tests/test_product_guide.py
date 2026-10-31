"""Public product documentation must remain local, reviewed and source-bound."""
import hashlib
import json
import importlib
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / 'data' / 'knowledge' / 'en' / 'product-guide.md'


class ParsedHtml(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attributes = []
        self.content = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)

    def handle_data(self, data):
        self.content.append(data)


class ProductGuideTests(unittest.TestCase):
    def setUp(self):
        # Import here so absence of the feature is an explicit assertion failure.
        try:
            self.guide = importlib.import_module('server.app.rag.product_guide')
        except ModuleNotFoundError as exc:
            self.fail(f'Trusted product guide module is required: {exc}')

    def test_document_is_exact_reviewed_file_with_deterministic_metadata(self):
        document = self.guide.product_document()
        text = GUIDE.read_text(encoding='utf-8')
        self.assertEqual(document, {
            'document_id': 'product-guide',
            'title': 'Rental assistant user guide',
            'source_url': '/api/v1/rag/product-guide',
            'source_type': 'product_guide',
            'language': 'en',
            'jurisdiction': 'PRODUCT',
            'scope': 'public',
            'checked_at': '2026-10-31',
            'published_at': None,
            'document_version': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'capture_method': 'Local reviewed product documentation',
            'text': text,
        })
        document['text'] = 'Caller mutation'
        self.assertEqual(self.guide.product_document(), self.guide.product_document())
        self.assertEqual(self.guide.product_document()['text'], text)
        self.assertIsNone(self.guide.validate_product_document(self.guide.product_document()))

    def test_changed_body_is_rejected_even_with_matching_recomputed_hash(self):
        document = self.guide.product_document()
        changed = document['text'] + '\nUser contract: confidential text.'
        for version in (document['document_version'], hashlib.sha256(changed.encode()).hexdigest()):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.guide.validate_product_document({**document, 'text': changed, 'document_version': version})

    def test_every_trusted_metadata_field_and_version_are_bound_to_release(self):
        document = self.guide.product_document()
        for key in document:
            if key == 'text':
                continue
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.guide.validate_product_document({**document, key: 'forged'})
        for invalid in (None, [], 'product-guide', {}, {key: value for key, value in document.items() if key != 'scope'}):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaises(ValueError):
                self.guide.validate_product_document(invalid)

    def test_user_contract_private_scope_and_arbitrary_paths_cannot_impersonate_product(self):
        document = self.guide.product_document()
        for extra in ({'case_id': 'synthetic-case'}, {'case_id': None}, {'scope': 'private'},
                      {'source_type': 'user_contract'}, {'source_url': 'https://fake.example/api/v1/rag/product-guide'},
                      {'source_url': 'file:///private/contract.txt'}, {'path': '/private/contract.txt'},
                      {'contract_text': 'Synthetic private contract'}, {'scope': 'public', 'text': 'Synthetic private contract'}):
            with self.subTest(fields=list(extra)), self.assertRaises(ValueError):
                self.guide.validate_product_document({**document, **extra})
            with self.subTest(renderer=list(extra)), self.assertRaises(ValueError):
                self.guide.product_guide_html({**document, **extra})

    def test_html_is_readable_english_and_bound_to_actual_guide(self):
        document = self.guide.product_document()
        rendered = self.guide.product_guide_html(document)
        parsed = ParsedHtml()
        parsed.feed(rendered)
        self.assertIn(('lang', 'en'), parsed.attributes)
        self.assertIn('h1', parsed.tags)
        self.assertIn('h2', parsed.tags)
        self.assertIn('p', parsed.tags)
        self.assertIn('li', parsed.tags)
        self.assertIn(document['title'], rendered)
        self.assertIn('2026-10-31', rendered)
        self.assertNotIn('script', parsed.tags)
        self.assertNotIn('iframe', parsed.tags)
        self.assertNotIn('a', parsed.tags)
        self.assertFalse(any(key.startswith('on') or key in ('href', 'src') for key, _ in parsed.attributes))

    def test_even_trusted_authored_html_and_scripted_markdown_links_are_plain_text(self):
        authored = '# Guide <img src=x onerror=alert(1)>\n\n## Help & support\n\n<script>alert("test")</script>\n\n- [click](javascript:alert(1))\n- <a href="data:text/html,bad">unsafe</a>\n'
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / 'guide.md'
            fixture.write_text(authored, encoding='utf-8')
            with patch.object(self.guide, '_GUIDE_PATH', fixture):
                rendered = self.guide.product_guide_html(self.guide.product_document())
        parsed = ParsedHtml()
        parsed.feed(rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('&lt;img', rendered)
        self.assertIn('Help &amp; support', rendered)
        self.assertIn(authored.splitlines()[4], ''.join(parsed.content))
        for tag in ('script', 'img', 'a', 'iframe', 'object'):
            self.assertNotIn(tag, parsed.tags)
        self.assertFalse(any(key.startswith('on') or key in ('href', 'src') for key, _ in parsed.attributes))

    def test_documented_help_topics_have_implemented_ui_controls(self):
        text = self.guide.product_document()['text']
        # These are public source-code reads, not cases, runtime data or uploads.
        topics = (
            ('Start a case and chat', 'frontend/src/app/App.tsx', 'New case'),
            ('Edit rental requirements and see all matches', 'frontend/src/features/assistant/RentalNeeds.tsx', 'My rental needs'),
            ('Commute estimates', 'frontend/src/features/real-data/UsydCommute.tsx', 'Google Maps'),
            ('Lifestyle preferences and sources', 'frontend/src/features/assistant/AreaAdvice.tsx', 'Find an area that fits your lifestyle'),
            ('Favorites, comparison and direct selection', 'frontend/src/features/favorites/ListingActions.tsx', 'Select and follow up'),
            ('Confirm selection and prepare an inspection', 'frontend/src/features/candidate/CandidateFollowup.tsx', 'Contact property agent'),
            ('Lease draft form, AI assistance and PDF preview', 'frontend/src/features/contracts/LeaseDraft.tsx', 'Confirm and save unsigned draft'),
            ('Upload a contract for review', 'frontend/src/features/ContractUpload.tsx', 'Upload and review'),
            ('Private contract search and separate consent', 'frontend/src/features/knowledge/ContractKnowledgePanel.tsx', 'Turn off contract search'),
            ('Repair emails and follow-up records', 'frontend/src/features/living/RepairComposer.tsx', 'Polish email with AI'),
            ('Utilities, moving and cleaning providers', 'frontend/src/features/living/Services.tsx', 'view provider details'),
            ('Move-out plans and bond follow-up', 'frontend/src/features/AftercareBond.tsx', 'Prepare factual draft'),
        )
        for heading, source, control in topics:
            with self.subTest(topic=heading):
                self.assertIn('## ' + heading, text)
                self.assertIn(control, (ROOT / source).read_text(encoding='utf-8'))
        for capability in ('no fixed arrival time', 'all matching properties', 'manual signatures',
                           'does not send the email', 'does not submit a booking', 'not a legal-validity guarantee'):
            with self.subTest(capability=capability):
                self.assertIn(capability, text.casefold())

    def test_current_commute_help_matches_ui_and_canonical_snapshot(self):
        document = self.guide.product_document()
        for removed_control in ('Public transport route details', 'View journey details', '“Route details”'):
            with self.subTest(control=removed_control):
                self.assertNotIn(removed_control, document['text'])
        snapshot = json.loads((GUIDE.parent / 'documents.json').read_text(encoding='utf-8'))
        self.assertEqual([row for row in snapshot if row.get('document_id') == 'product-guide'], [document])


if __name__ == '__main__':
    unittest.main()
