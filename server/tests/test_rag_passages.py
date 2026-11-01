"""Quoted groups retain original lead-ins and immediately adjacent exceptions."""
import importlib
import unittest


class SourcePassageTests(unittest.TestCase):
    def passages(self,text):
        try: module=importlib.import_module('server.app.rag.passages')
        except ModuleNotFoundError:self.fail('The source passage grouping module is not implemented')
        return module.source_passages({'text':text})

    def test_short_sections_are_kept_whole_through_inclusive_3200_limit(self):
        text='An original short source section.\n\n* First item\n\nHowever, an exception applies.'
        self.assertEqual(self.passages(text),{'p0':text})
        text='A'*3200
        self.assertEqual(self.passages(text),{'p0':text})

    def test_long_source_preserves_non_colon_should_lead_in_and_following_list(self):
        lead='The principal tenant acting for the shared rental should'
        items='* submit or respond to the bond refund claim.\n* distribute the refund to the other tenants.'
        text=('Background detail. '*185)+'\n\n'+lead+'\n\n'+items+'\n\nIndependent next rule applies.'
        values=list(self.passages(text).values())
        self.assertIn(lead+'\n\n'+items,values)
        self.assertNotIn(lead,values);self.assertNotIn(items,values)

    def test_colon_must_and_may_lead_ins_group_all_separated_bullets(self):
        for lead in ['The tenant must:','The landlord must','The tenant may']:
            group=lead+'\n\n* first applicable choice, or\n\n* second applicable choice.'
            text=('Background detail. '*185)+'\n\n'+group+'\n\nA separate unrelated rule.'
            self.assertIn(group,self.passages(text).values())

    def test_immediately_following_exception_and_list_attach_to_rule(self):
        rule='A departing co-tenant must be repaid within 14 days, less reasonable costs.'
        exception='This does not apply if:\n\n* debts exceed the bond share, or\n\n* a final apprehended violence order excludes them.'
        group=rule+'\n\n'+exception
        text=('Background detail. '*185)+'\n\n'+group+'\n\nA separate unrelated rule.'
        values=list(self.passages(text).values())
        self.assertIn(group,values);self.assertNotIn(rule,values);self.assertNotIn(exception,values)

    def test_however_unless_and_exception_paragraphs_remain_with_preceding_rule(self):
        rule='The ordinary rule applies to the tenancy.'
        for exception in ['However, the exception applies in special circumstances.',
                          'Unless the parties agree, that rule does not apply.',
                          'Exception: the rule does not apply to this category.']:
            group=rule+'\n\n'+exception
            text=('Background detail. '*185)+'\n\n'+group+'\n\nA separate unrelated rule.'
            self.assertIn(group,self.passages(text).values())

    def test_oversized_rule_with_exception_is_omitted_as_a_whole(self):
        rule='The tenant must repay the bond. '+('Important condition. '*145)
        exception='This does not apply if:\n\n* '+('A qualifying exception. '*35)
        group=rule+'\n\n'+exception
        self.assertGreater(len(group),3200);self.assertLess(len(rule),3200)
        tail='A separate complete rule is still usable.'
        values=list(self.passages(group+'\n\n'+tail).values())
        self.assertEqual(values,[tail])

    def test_dangling_lead_ins_are_not_exposed_as_quotes(self):
        for lead in ['The principal tenant should','A tenant must:','The landlord may']:
            text=('Background detail. '*185)+'\n\n'+lead
            self.assertNotIn(lead,self.passages(text).values())

    def test_exact_source_substrings_survive_unusual_blank_line_spacing(self):
        group='A rule applies.\n\n\nHowever, this does not apply if:\n\n  * an exception holds.'
        text=('Background detail. '*185)+'\n\n'+group+'\n\nA separate complete rule.'
        values=list(self.passages(text).values())
        self.assertIn(group,values)
        for value in values:self.assertIn(value,text)

    def test_bullets_with_wrapped_body_and_ordered_lists_stay_exact(self):
        group='The tenant must:\n\n1. notify the landlord\n   with written details\n\n2. keep the receipt.'
        text=('Background detail. '*185)+'\n\n'+group
        self.assertIn(group,self.passages(text).values())

    def test_empty_source_has_no_model_quote(self):
        self.assertEqual(self.passages(''),{})

    def test_verified_official_pdf_page_keeps_full_page_context(self):
        from server.app.rag.passages import source_passages
        text=('An official PDF page. '+('Complete source sentence. '*180)).strip()
        row={'text':text,'source_type':'official_template','download_url':'https://www.nsw.gov.au/test.pdf','page':3}
        self.assertEqual(source_passages(row),{'p0':text})
        self.assertEqual(source_passages({**row,'source_type':'user_contract'}),{})
        self.assertEqual(source_passages({**row,'text':'A'*8001}),{})
        self.assertEqual(source_passages({**row,'text':text+' and'}),{})

    def test_captured_accordion_subsection_keeps_procedure_and_deadline_together(self):
        label='A payment procedure keyboard_arrow_down'
        procedure='The office gives written notice that you made a claim.\n\nIf a party refuses to sign, you can still submit it. They have 14 days to dispute it.'
        group=label+'\n\n'+procedure
        next_group='Another procedure keyboard_arrow_down\n\nAn unrelated complete rule.'
        text=('Background facts. '*210)+'\n\n'+group+'\n\n'+next_group
        values=list(self.passages(text).values())
        self.assertIn(group,values);self.assertIn(next_group,values)
        self.assertFalse(any('written notice' in value and 'unrelated' in value for value in values))
        self.assertFalse(any(value=='The office gives written notice that you made a claim.' for value in values))
        for value in values:self.assertIn(value,text)

    def test_oversized_accordion_subsection_is_omitted_without_partial_procedure(self):
        text='A procedure keyboard_arrow_down\n\n'+('A necessary qualification. '*140)+'\n\nHowever, a further qualification applies.\n\n* * *\n\nAnother complete rule.'
        values=list(self.passages(text).values())
        self.assertFalse(any('necessary qualification' in value or 'further qualification' in value for value in values))
        self.assertIn('Another complete rule.',values)

    def test_captured_shared_tenancy_guidance_keeps_subject_with_actions_and_repayment_exceptions(self):
        import json
        from pathlib import Path
        from server.app.rag.index import chunks
        root=Path(__file__).resolve().parents[2]
        doc=next(d for d in json.loads((root/'data/knowledge/en/documents.json').read_text()) if d['document_id']=='bond-refund')
        row=next(c for c in chunks(doc) if c['section']=='What do you need to do?')
        values=list(self.passages(row['text']).values())
        principal=next(value for value in values if 'The principal tenant who acts on behalf' in value)
        self.assertIn('submit or respond to a claim',principal)
        self.assertIn('distribute the bond refund',principal)
        repayment=next(value for value in values if 'within 14 days of the request' in value)
        self.assertIn('This does not apply if:',repayment)
        self.assertIn('debts exceed the amount of bond money',repayment)
        self.assertIn('final apprehended violence order',repayment)
        for value in values:self.assertIn(value,row['text'])
