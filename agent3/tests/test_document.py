from pathlib import Path
import zipfile
import sys
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_agent.document import load_document
from contract_agent.errors import ResubmissionRequired
from contract_agent.review import review_agreement


class DocumentTests(unittest.TestCase):
    def test_docx_text_and_source_are_extracted(self):
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               '<w:body><w:p><w:r><w:t>Landlord: Example</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Tenant: Alex</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Address: 1 Example St</w:t></w:r></w:p>'
               '</w:body></w:document>')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "agreement.docx"
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("word/document.xml", xml)
            result = load_document(target, consent=True)
            self.assertIn("Tenant: Alex", result["text"])
            self.assertEqual(result["page_count"], 1)

    def blank_pdf(self, directory):
        target = Path(directory) / "scan.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=400, height=600)
        with target.open("wb") as stream:
            writer.write(stream)
        return target

    def test_text_pdf_is_read_with_page_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "typed-agreement.pdf"
            writer = PdfWriter()
            page = writer.add_blank_page(width=400, height=600)
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                     NameObject("/Subtype"): NameObject("/Type1"),
                                     NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(b"BT /F1 12 Tf 40 500 Td (Landlord: Example) Tj 0 -20 Td (Tenant: Alex) Tj ET")
            page[NameObject("/Contents")] = writer._add_object(stream)
            with target.open("wb") as output:
                writer.write(output)
            result = load_document(target, consent=True)
            self.assertEqual(result["extraction_mode"], "text")
            self.assertEqual(result["page_count"], 1)
            self.assertIn("Tenant: Alex", result["text"])

    def test_image_only_pdf_requests_ocr_or_resubmission(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self.blank_pdf(directory)
            with patch("contract_agent.document._ocr_pdf", side_effect=ResubmissionRequired("OCR unavailable")):
                with self.assertRaises(ResubmissionRequired):
                    load_document(target, consent=True)

    def test_ocr_text_is_marked_lower_confidence(self):
        text = ("Landlord: Example\nTenant: Alex\nAddress: Example Street 1\n"
                "Weekly rent: $500 per person\nBond: $2000\nStart date: 2027-02-01\nEnd date: 2028-01-01")
        with tempfile.TemporaryDirectory() as directory:
            target = self.blank_pdf(directory)
            with patch("contract_agent.document._ocr_pdf", return_value=[text]):
                document = load_document(target, consent=True)
            self.assertEqual(document["extraction_mode"], "ocr")
            review = review_agreement(document, consent=True, as_of="2026-10-15")
            self.assertEqual(review["fields"]["tenant"]["confidence"], 0.65)
