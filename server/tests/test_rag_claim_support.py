"""Conservative source preservation is a guard, never an entailment proof."""
import importlib
import unittest


class ClaimSupportTests(unittest.TestCase):
    def test_chinese_statute_year_is_not_a_duration_and_must_exist_in_source(self):
        self.guard('可依据《2010年住宅租赁法》提出投诉。','The Residential Tenancies Act 2010 applies.',
                   'Complaints','如何投诉？','zh')
        with self.assertRaises(ValueError):
            self.guard('可依据《2020年住宅租赁法》提出投诉。','The Residential Tenancies Act 2010 applies.',
                       'Complaints','如何投诉？','zh')

    def guard(self, *args, **kwargs):
        try:
            api=importlib.import_module('server.app.rag.claim_support')
        except ModuleNotFoundError:
            self.fail('The conservative source-preservation guard is not implemented')
        return api.preserve_claim(*args, **kwargs)

    def test_benign_simple_repair_paraphrase_can_remain(self):
        text='Contact your landlord or agent about the repair.'
        result=self.guard(text,'Tell your landlord or agent about repairs as soon as possible.','Requesting repairs','Who do I contact?')
        self.assertEqual(result,{'text':text,'adjusted':False})

    def test_or_alternatives_are_preserved_as_one_original_quote(self):
        quote='You can only claim early if:\n\n* you have written agreement from your landlord, or\n* you direct the full bond to the landlord.'
        result=self.guard('You can only claim early if you have written agreement.',quote,['Bond refunds','Before the tenancy ends'],'When can I claim early?')
        self.assertTrue(result['adjusted']);self.assertIn(quote,result['text'])
        self.assertTrue(result['text'].startswith('Source context: Bond refunds > Before the tenancy ends'))

    def test_omitted_notice_prerequisite_is_replaced_with_full_source(self):
        quote='Tenants can end an agreement of 2 years or more early if given a rent increase notice. They must give 21 days’ written notice before the increase starts.'
        result=self.guard('Tenants can end an agreement of 2 years or more early if given a rent increase notice.',quote,'Other situations where break fees do not apply','Can I end the lease?')
        self.assertTrue(result['adjusted']);self.assertIn('21 days’ written notice before',result['text'])
        self.assertIn(quote,result['text'])

    def test_colon_only_lead_in_cannot_support_omitted_list(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            self.guard('You may not be reimbursed if you caused the damage.','Your landlord may not have to reimburse you if:','Urgent repairs','What if I caused damage?')

    def test_dangling_or_cannot_support_missing_alternative(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            self.guard('You need written agreement.','You have written agreement, or','Early bond claims','When can I claim?')

    def test_written_duration_not_in_fragment_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'duration'):
            self.guard('The three-month period starts when you became aware.','From the day the applicant became aware of the breach.','Either landlord or tenant','When does the three-month period start?')

    def test_arabic_duration_not_in_quote_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'duration'):
            self.guard('Give 21 days notice.','Give written notice before the rent increase.','Ending tenancy','What notice applies?')

    def test_number_word_and_hyphen_duration_normalize_without_rejecting_supported_value(self):
        result=self.guard('The three-month period starts on awareness.','The 3 month period starts on awareness.','Tribunal periods','When does it start?')
        self.assertFalse(result['adjusted'])
        result=self.guard('Give 21 days notice.','Give twenty-one days notice.','Notice','What notice applies?')
        self.assertFalse(result['adjusted'])

    def test_working_days_and_calendar_days_are_not_interchangeable(self):
        with self.assertRaisesRegex(ValueError,'duration'):
            self.guard('Wait 7 calendar days.','Allow 7 working days for delivery.','Posted notices','How long?')

    def test_usually_and_most_qualifications_preserve_exact_deadline_trigger(self):
        quote='For most disputes you must apply within 28 days. This starts from the day you become entitled to apply, which will usually be when the issue first happens.'
        result=self.guard('Generally apply within 28 days from the day the issue first happens.',quote,
                          'When to apply','What can I do about a dispute?')
        self.assertTrue(result['adjusted'])
        self.assertIn('become entitled to apply',result['text'])
        self.assertIn(quote,result['text'])

    def test_unsupported_amount_is_rejected_even_without_duration(self):
        with self.assertRaisesRegex(ValueError,'number'):
            self.guard('The cap is $2,000.','The cap is $1,000.','Repairs','What cap applies?')

    def test_markdown_emphasis_does_not_hide_a_supported_act_year(self):
        for quote in ['The statement explains the _Residential Tenancies Act 2010_(the Act).',
                      'The statement explains the **Residential Tenancies Act 2010**.',
                      'The statement explains the `Residential Tenancies Act 2010`.']:
            result=self.guard('The statement explains the Residential Tenancies Act 2010.',quote,
                              'Termination information statement','What is the statement about?')
            self.assertIn('2010',result['text'])
        with self.assertRaises(ValueError):
            self.guard('The statement explains the Act 2020.','The statement explains the _Act 2010_.',
                       'Statement','What Act?')

    def test_leaf_fee_list_carries_hierarchical_date_context(self):
        quote="* 4 weeks' rent before 25 per cent has expired\n* 3 weeks' rent from 25 to under 50 per cent"
        context=['When break fees apply','Tenant breaking a fixed-term agreement signed after 23 March 2020','For agreements of 3 years or less']
        result=self.guard("The fee is 4 weeks' rent before 25 per cent has expired.",quote,context,'What tier applies to a qualifying lease?')
        self.assertTrue(result['adjusted']);self.assertIn('signed after 23 March 2020',result['text']);self.assertIn(quote,result['text'])

    def test_explicit_before_after_date_regime_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'regime'):
            self.guard('An optional fee may apply.','The optional clause applies unless deleted.',
                       ['Break fees','Agreements signed before 23 March 2020'],'My lease was signed after 23 March 2020; what applies?')
        with self.assertRaisesRegex(ValueError,'regime'):
            self.guard('A mandatory fee may apply.','The mandatory fee applies if eligible.',
                       'Agreements signed after 23 March 2020','My lease was signed before 23 March 2020; what applies?')

    def test_pre_post_year_scope_is_checked_without_case_ids(self):
        with self.assertRaisesRegex(ValueError,'regime'):
            self.guard('An optional fee may apply.','The optional clause applies unless deleted.',
                       'Agreements signed before 23 March 2020','For post-2020 leases, what applies?')

    def test_comparison_explicitly_asking_both_regimes_can_show_each_labeled_quote(self):
        result=self.guard('An optional fee may apply.','The optional clause applies unless deleted.',
                          'Agreements signed before 23 March 2020','Compare rules before and after 23 March 2020.')
        self.assertTrue(result['adjusted']);self.assertIn('before 23 March 2020',result['text'])

    def test_chinese_numeric_checks_then_preserves_exact_english_source(self):
        quote='They should pay you back within 14 days.'
        result=self.guard('应在十四天内退款。',quote,'Non-urgent repairs','多久还钱？',language='zh')
        self.assertTrue(result['adjusted']);self.assertIn(quote,result['text'])
        with self.assertRaisesRegex(ValueError,'duration'):
            self.guard('应在三天内退款。',quote,'Repairs','多久？',language='zh')

    def test_exception_and_table_passages_are_preserved(self):
        for quote in ['A ground is required unless a tenant ends a periodic tenancy.',
                      '| Reason | Deadline |\n| Breach | 3 months |']:
            result=self.guard('A ground is required.',quote,'Notice rules','What is required?')
            self.assertTrue(result['adjusted']);self.assertIn(quote,result['text'])

    def test_empty_or_unusable_inputs_rejected(self):
        for text,quote,context in [('', 'Original text.', []),('Claim','',[]),('Claim','Source',{'unexpected':'mapping'})]:
            with self.assertRaises(ValueError):self.guard(text,quote,context,'Question')


    def test_explicit_scope_in_quote_is_checked_when_heading_has_no_date(self):
        with self.assertRaisesRegex(ValueError,'regime'):
            self.guard('An optional fee may apply.','For agreements signed before 23 March 2020, the optional clause applies unless deleted.',
                       'Break fees','For agreements signed after 23 March 2020, what applies?')

    def test_scope_dates_and_term_durations_in_trusted_context_support_claim(self):
        context=['Agreements signed after 23 March 2020','For agreements of 3 years or less']
        quote="If the mandatory fee applies, the fee is 4 weeks' rent."
        result=self.guard("For an agreement of three years signed after 23 March 2020, the fee is 4 weeks' rent.",quote,context,
                          'What applies after 23 March 2020?')
        self.assertTrue(result['adjusted']);self.assertIn('Agreements signed after 23 March 2020',result['text'])
        self.assertIn(quote,result['text'])
        result=self.guard("For pre-2020 agreements, the fee is 6 weeks' rent.","The optional fee is 6 weeks' rent.",
                          'Agreements signed before 23 March 2020','What applies before 23 March 2020?')
        self.assertTrue(result['adjusted']);self.assertIn('before 23 March 2020',result['text'])

    def test_context_number_without_duration_unit_cannot_support_a_duration(self):
        with self.assertRaisesRegex(ValueError,'duration'):
            self.guard('The fee is six weeks rent.','The optional fee is stated in the agreement.',
                       'Clause 6','What fee applies?')

    def test_context_urls_do_not_support_dates_or_durations(self):
        for context in ['https://example.test/2020/23/three-years',
                        '[Fee guidance](https://example.test/2020/23/three-years)']:
            with self.assertRaises(ValueError):
                self.guard('For three years after 23 March 2020 the fee applies.',
                           'The fee is stated in the agreement.',context,'What fee applies?')

    def test_context_derived_numeric_claim_is_always_replaced_with_source_and_label(self):
        result=self.guard('The agreement of three years must end immediately.',
                          'The agreement continues until its end date.','Agreements of 3 years','What happens?')
        self.assertTrue(result['adjusted'])
        self.assertNotIn('must end immediately',result['text'])
        self.assertIn('Agreements of 3 years',result['text'])

    def test_url_only_regime_is_not_treated_as_actual_section_scope(self):
        result=self.guard('Contact your agent about repairs.','Contact your agent about repairs.',
                          'https://example.test/pre-2020','Who do I contact after 23 March 2020?')
        self.assertEqual(result['text'],'Contact your agent about repairs.')
