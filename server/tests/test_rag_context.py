import tempfile,unittest
from pathlib import Path
from server.app.rag.index import KnowledgeIndex
from server.app.rag.service import passages
from server.tests.test_rag import document

class ContextTests(unittest.TestCase):
    def test_nested_applicability_survives_parent_heading_without_body(self):
        with tempfile.TemporaryDirectory() as folder:
            index=KnowledgeIndex(Path(folder)/'rag.sqlite3')
            d=document(text='Text')
            d['text']='## Agreements signed before 23 March 2020\n\n### Included optional break fee\nThe first half fee is six weeks rent.'
            index.publish([d]);row=index.search('break fee')[0]
            self.assertEqual(row['section_path'],['Agreements signed before 23 March 2020','Included optional break fee'])
            self.assertIn('before 23 March 2020',row['embedding_text'])

    def test_conditional_intro_and_following_list_form_one_exact_quote(self):
        raw='You may claim only if:\n\n* you have receipts\n* the issue was not your fault\n\nOther information is separate.'
        quotes=list(passages({'text':raw}).values())
        self.assertTrue(any('You may claim only if:\n\n* you have receipts\n* the issue was not your fault' in quote for quote in quotes))
        self.assertNotIn('You may claim only if:',quotes)
        self.assertTrue(all(quote in raw for quote in quotes))

    def test_parent_change_invalidates_chunk_identity_and_cached_vectors(self):
        with tempfile.TemporaryDirectory() as folder:
            index=KnowledgeIndex(Path(folder)/'rag.sqlite3');d=document();d['text']='## Old date scope\n### Rent\nRent is paid weekly.'
            index.publish([d]);old=index.search('rent')[0];index.save_vectors([old['chunk_id']],[[1.,0.]],'test',2)
            d['text']=d['text'].replace('Old date scope','New date scope');index.publish([d]);new=index.search('rent')[0]
            self.assertNotEqual(new['chunk_id'],old['chunk_id']);self.assertEqual(index.vector_search([1.,0.],'test',2),[])
