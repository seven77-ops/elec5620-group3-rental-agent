import unittest
from server.app.lease_drafts.ai import grounded_patch, duration_grounded
from server.app.common import ApiError

class EnglishEvidenceTests(unittest.TestCase):
    def test_demonstration_wording_is_grounded(self):
        entries=[
          ('rental_mode','whole_property','This is a standard NSW whole-property residential tenancy.'),
          ('lease_term_months',12,'Lease term: 12 calendar months.'),
          ('bond',3600,'Proposed bond: AUD 3600.'),
          ('max_occupants',2,'Maximum occupants: 2.'),
        ]
        for field,value,quote in entries:
            with self.subTest(field=field):
                self.assertEqual(grounded_patch({'fields':[{'field':field,'value':value,'quote':quote}]},quote)[field],value)

    def test_punctuation_does_not_allow_decimal_prefixes_or_wrong_amounts(self):
        for value,quote in [(3600,'Bond: AUD 3600.50.'),(360,'Bond: AUD 3600.'),(3600,'Bond: AUD 13600.')]:
            with self.subTest(value=value,quote=quote), self.assertRaises(ApiError):
                grounded_patch({'fields':[{'field':'bond','value':value,'quote':quote}]},quote)
        quote='Bond: AUD 3,600.50.'
        self.assertEqual(grounded_patch({'fields':[{'field':'bond','value':3600.5,'quote':quote}]},quote)['bond'],3600.5)

    def test_calendar_compounds_are_not_shortened(self):
        message='Lease term: 1 year and 6 calendar months.'
        for months,quote in [(12,message),(6,message),(12,'1 year'),(6,'6 calendar months')]:
            self.assertFalse(duration_grounded(months,quote,message),(months,quote))
