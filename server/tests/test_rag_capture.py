"""Offline capture boundary tests; never fetch case files or the internet."""
import io
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from pypdf import PdfWriter

from server.app.rag.sources import SOURCES


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCES[0]

    def reader(self, body, source=None):
        return 'Title: Official page\nURL Source: ' + (source or self.source)[2] + '\nPublished Time: 2026-09-01\nMarkdown Content:\n' + body

    def test_reader_removes_chrome_preserving_qualifications_and_tables(self):
        from server.app.rag.capture import parse_source
        body = 'Navigation\n[Home](https://www.nsw.gov.au/)\n# Official rental guidance\n\n' + ('The tenant must give written notice, except in an emergency.\n\n' * 6) + '| Reason | Notice |\n| --- | --- |\n| Inspection | 7 days |\n\n## You might also be interested in\nFooter'
        result = parse_source(self.source, self.reader(body), checked_at='2026-10-30')
        self.assertTrue(result['text'].startswith('# Official rental guidance'))
        self.assertIn('| Inspection | 7 days |', result['text'])
        self.assertNotIn('Footer', result['text'])
        self.assertEqual(result['checked_at'], '2026-10-30')
        self.assertEqual(result['scope'], 'public')
        self.assertEqual(len(result['content_hash']), 64)

    def test_rejects_wrong_source_and_error_responses(self):
        from server.app.rag.capture import parse_source
        for raw in ('Access denied', self.reader('# 404 - Page not found\n' + 'x' * 500), self.reader('# Request blocked\n' + 'x' * 500), self.reader('# Official\n' + 'x' * 500).replace('Title: Official page', 'Title: Just a moment...'), self.reader('# Official\n' + 'x' * 500).replace(self.source[2], 'https://evil.example/private')):
            with self.assertRaises(ValueError):
                parse_source(self.source, raw)

    def test_http_200_reader_error_titles_and_leading_error_pages_are_rejected(self):
        from server.app.rag.capture import capture, parse_source
        for title in ('503 Service Unavailable', '502 Bad Gateway', '504 Gateway Timeout', '500 Internal Server Error'):
            raw = self.reader('# ' + title + '\n\n' + 'Please try the request again later. ' * 12).replace('Title: Official page', 'Title: ' + title)
            with self.subTest(title=title), self.assertRaises(ValueError):
                parse_source(self.source, raw)
            with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=raw))) as client:
                with self.subTest(capture_title=title), self.assertRaises(ValueError):
                    capture(self.source, client=client)
        for prefix in ('# 503 Service Unavailable', '502 Bad Gateway', 'Navigation\n\n# 503 Service Unavailable'):
            with self.subTest(body=prefix), self.assertRaises(ValueError):
                parse_source(self.source, self.reader(prefix + '\n\n' + 'Please try the request again later. ' * 12))

    def test_normal_guidance_may_discuss_http_failures_without_being_an_error_page(self):
        from server.app.rag.capture import parse_source
        for introduction in ('# Official rental guidance\n\nA 503 Service Unavailable response or 502 Bad Gateway message can appear when an online service is busy.', '503 Service Unavailable can appear when an online service is busy; it does not cancel a submitted notice.'):
            body = introduction + '\n\n' + 'Keep a copy of your notice and contact the relevant service for assistance. ' * 7
            with self.subTest(introduction=introduction):
                result = parse_source(self.source, self.reader(body))
                self.assertEqual(result['text'], body.strip())

    def test_arbitrary_private_or_modified_source_is_rejected_before_request(self):
        from server.app.rag.capture import capture
        for source in (('private', 'Private', 'http://127.0.0.1/secrets'), (self.source[0], self.source[1], self.source[2] + '?case_id=private'), ('unknown', 'Unknown', 'https://www.nsw.gov.au/unreviewed')):
            with patch('server.app.rag.capture.httpx.Client') as client:
                with self.assertRaises(ValueError):
                    capture(source)
                client.assert_not_called()

    def test_fetch_rejects_redirects_error_status_and_oversized_payloads(self):
        from server.app.rag.capture import capture
        for status, headers, content in ((302, {'location': 'http://127.0.0.1/'}, b''), (403, {}, b'Forbidden'), (200, {'content-length': '99999999'}, b'bad')):
            transport = httpx.MockTransport(lambda request: httpx.Response(status, headers=headers, content=content))
            with httpx.Client(transport=transport) as client:
                with self.assertRaises((ValueError, httpx.HTTPStatusError)):
                    capture(self.source, client=client)

    def test_source_types_distinguish_university_and_blank_template(self):
        from server.app.rag.sources import SOURCE_TYPES
        self.assertEqual(SOURCE_TYPES['student-off-campus'], 'student_guidance')
        self.assertEqual(SOURCE_TYPES['standard-lease'], 'official_template')

    def test_pdf_capture_requires_current_landing_link_and_pdf_media_type(self):
        from server.app.rag.capture import capture
        from server.app.rag.sources import PDF_DOWNLOADS
        source = next(s for s in SOURCES if s[0] == 'standard-lease')
        download = PDF_DOWNLOADS[source[0]]
        for link, content_type in ((download.replace('www.nsw.gov.au', 'evil.example'), 'application/pdf'), (download, 'text/html')):
            visited = []
            def respond(request):
                visited.append(str(request.url))
                if str(request.url).startswith('https://r.jina.ai/'):
                    text = self.reader('# Official blank form\n\n' + ('Public instructions. ' * 30) + '\n[PDF](' + link + ')', source)
                    return httpx.Response(200, text=text)
                return httpx.Response(200, headers={'content-type': content_type}, content=b'<html>Denied</html>')
            with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                with self.assertRaises(ValueError):
                    capture(source, client=client)
            self.assertFalse(any('evil.example' in url for url in visited))

    def test_pdf_requires_signature_valid_pdf_and_extractable_complete_pages(self):
        from server.app.rag.capture import parse_pdf
        source = next(s for s in SOURCES if s[0] == 'standard-lease')
        with self.assertRaises(ValueError):
            parse_pdf(source, b'<html>Access denied</html>')
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
        out = io.BytesIO(); writer.write(out)
        with self.assertRaises(ValueError):
            parse_pdf(source, out.getvalue())
        with patch('server.app.rag.capture.PdfReader') as reader:
            payload = (Path(__file__).resolve().parents[2] / 'agent3/data/templates/nsw-residential-tenancy-2026-09-21.pdf').read_bytes()
            reader.return_value.is_encrypted = False
            reader.return_value.get_fields.return_value = {}
            reader.return_value.pages = [type('Page', (dict,), {'extract_text': lambda self: 'Official blank rental agreement. ' * 15})(), type('Page', (dict,), {'extract_text': lambda self: 'Additional tenancy terms. ' * 15})()]
            result = parse_pdf(source, payload, checked_at='2026-10-30')
            self.assertEqual(result['page_count'], 2)
            self.assertIn('## Page 1', result['text']); self.assertIn('## Page 2', result['text'])
            reader.return_value.get_fields.return_value = {'tenant': {'/V': 'A real person'}}
            with self.assertRaises(ValueError):
                parse_pdf(source, payload)
            reader.return_value.get_fields.return_value = {}
            reader.return_value.pages = [type('Page', (dict,), {'extract_text': lambda self: ''})()]
            with self.assertRaises(ValueError):
                parse_pdf(source, payload)


if __name__ == '__main__':
    unittest.main()
