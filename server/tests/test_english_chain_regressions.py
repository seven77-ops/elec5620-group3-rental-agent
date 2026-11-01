"""Regressions from the English-chain audit; all model outputs are synthetic."""
import unittest
from server.app.assistant.budget_evidence import stated_amount
from server.app.assistant.preferences_progress import guard_monthly
from server.app.english import untranslated_prose
from server.tests import test_assistant_api as assistant_fixture
from server.tests import test_english_generated_content as email_fixture
from server.tests import test_rag_answer_integrity as rag_fixture


class EnglishAmountTests(unittest.TestCase):
    def test_cardinal_money_amounts_are_literal_not_calculated_or_truncated(self):
        for text,amount in [('seven hundred',700),('seven hundred and fifty',750),
            ('and seven hundred dollars per week',700),
            ('one thousand two hundred',1200),('twelve hundred',1200),
            ('AUD seventy-five per week',75),('seven hundred point five zero dollars',700.5)]:
            with self.subTest(text=text):self.assertTrue(stated_amount(text,amount))
        for text,amount in [('seven hundred and fifty',700),('one thousand two hundred',1000),
            ('one two hundred',300),('seven hundred for two people',1400),('Weekly',3000)]:
            with self.subTest(text=text):self.assertFalse(stated_amount(text,amount))

    def test_monthly_guard_accepts_explicit_words_but_rejects_an_invented_amount(self):
        c={'rental_brief':{'budget_amount':3000,'budget_period':'month'}}
        text='My weekly budget is seven hundred dollars.'
        for kind in ('collect_preferences','search'):
            intent=({'intent':kind,'brief_patch':{'budget_amount':700,'budget_period':'week'}} if kind=='collect_preferences'
                    else {'intent':kind,'filters':{'max_weekly_rent':700}})
            self.assertEqual(guard_monthly(c,text,intent),intent)
        bad={'intent':'collect_preferences','brief_patch':{'budget_amount':3000,'budget_period':'week'}}
        self.assertEqual(guard_monthly(c,text,bad)['brief_patch'],{})


class EnglishLanguageTests(unittest.TestCase):
    def test_non_english_scripts_and_latin_languages_are_rejected(self):
        for value in ('Bonjour Alex, le robinet de la cuisine fuit. Pourriez-vous organiser une réparation ?',
            'Contactez votre propriétaire ou votre agent pour signaler la réparation.',
            'Hola, necesito una reparación para el grifo de la cocina.',
            'Bitte vereinbaren Sie eine Reparatur für den Wasserhahn in der Küche.',
            '안녕하세요. 주방 수도꼭지를 수리해 주세요.', 'こんにちは。キッチンの蛇口を修理してください。'):
            with self.subTest(value=value):self.assertTrue(untranslated_prose(value))

    def test_english_prose_names_and_source_quotations_are_preserved(self):
        for value,preserved in [('Contact your landlord or agent first.',[]),('No.',[]),('NSW Fair Trading',[]),
            ('Rental Bonds Online',[]),('AUD 700/week',[]),
            ('Dear 王先生, the kitchen sink is leaking. Could you please arrange a repair?',['王先生']),
            ('Please contact François Dupont about the repair.',['François Dupont']),
            ('The tenant name is 张三.',['Tenant name: 张三. Rent is AUD 700 per week.']),
            ('The contract says: "Bonjour, le robinet fuit." This is the supplied clause.',['Bonjour, le robinet fuit.'])]:
            with self.subTest(value=value):self.assertFalse(untranslated_prose(value,preserved))

    def test_english_greeting_does_not_hide_a_foreign_language_body(self):
        self.assertTrue(untranslated_prose('Repair request. Dear Alex, Bonjour, le robinet de la cuisine fuit. Pourriez-vous organiser une réparation ? Thank you.'))


class EnglishDraftRegressionTests(unittest.TestCase):
    setUp=email_fixture.EnglishGeneratedDraftTests.setUp
    def test_french_model_output_is_rejected_without_saving_a_repair(self):
        self.provider.output={'subject':'Demande de réparation','body':'Bonjour Alex, le robinet de la cuisine fuit. Pourriez-vous organiser une réparation ? Merci.'}
        r=self.client.post(self.path,json={**self.body,'draft':'The kitchen tap is leaking.'})
        self.assertEqual(r.status_code,502,r.text)
        self.assertEqual(r.json()['error']['code'],'ai_invalid_response')
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']+'/living-services').json()['repairs'],[])


class EnglishRagRegressionTests(unittest.TestCase):
    compose=rag_fixture.AnswerIntegrityTests.compose
    def test_french_claim_is_not_published_as_an_english_answer(self):
        answer=self.compose({'claims':[{'text':'Contactez votre propriétaire ou votre agent pour signaler la réparation.',
            'evidence_id':'source-a','quote_id':'p0'}],'unknowns':[]})
        self.assertEqual(answer['status'],'sources_only');self.assertFalse(answer['claims'])


class EnglishBudgetApiRegressionTests(unittest.TestCase):
    setUp=assistant_fixture.AssistantTests.setUp
    conversation=assistant_fixture.AssistantTests.conversation
    send=assistant_fixture.AssistantTests.send
    def test_monthly_budget_can_change_to_an_explicit_english_word_amount(self):
        c=self.conversation()
        self.provider.result={'intent':'collect_preferences','brief_patch':{'budget_amount':3000,'budget_period':'month','budget_scope':'whole_property'}}
        c=self.send(c,'monthly','My budget is AUD 3000 per month for the whole property.').json()
        self.provider.result={'intent':'collect_preferences','brief_patch':{'budget_amount':700,'budget_period':'week'}}
        r=self.send(c,'weekly','My weekly budget is seven hundred dollars.')
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['rental_brief']['budget_amount'],700)
        self.assertEqual(r.json()['rental_brief']['budget_period'],'week')


if __name__=='__main__':unittest.main()
