import unittest
from copy import deepcopy
from types import SimpleNamespace
from server.app.real_data.catalog import RealCatalog
from server.app.common import ApiError

class TransitInfoTests(unittest.TestCase):
    def setUp(self):
        self.catalog=RealCatalog();self.home=self.catalog.get('domain:16095702');self.calls=[]
        def tool(name,args):
            self.calls.append((name,args))
            if name=='find_nearby':return {'locations':[{'id':'G20501','name':'undefined, undefined','type':'stop','distance':80,'properties':{'stopId':'2050123','STOP_NAME_WITH_PLACE':'Parramatta Road stop'}},
                {'name':'Park bench','kind':'Bench','distance':10}]}
            return {'alerts':[{'subtitle':'Route 412 service change','url':'https://transportnsw.info/alerts/test'},
                {'subtitle':'Unsafe link removed','url':'javascript:alert(1)'}]}
        self.ctx=SimpleNamespace(settings=SimpleNamespace(catalog=self.catalog),transit_provider=SimpleNamespace(tool=tool))
        self.case={'selection':None};self.chat={'messages':[{'listings':[self.home]}]}

    def test_nearby_returns_only_named_stops_from_public_house_coordinates(self):
        from server.app.assistant.transit_info import answer
        before=deepcopy((self.case,self.chat))
        result=answer(self.ctx,{'intent':'transit_info','transit_topic':'nearby'},self.case,self.chat,[],True)
        info=result['transit_information'];self.assertEqual(len(info['stops']),1)
        self.assertEqual(info['stops'][0]['distance_m'],80)
        self.assertEqual(self.calls[0][1]['latitude'],self.home['usyd_commute']['origin']['latitude'])
        self.assertEqual(self.calls[0][1]['type_1'],'STOP')
        self.assertFalse(self.calls[0][1]['concise'])
        self.assertEqual(info['stops'][0]['name'],'Parramatta Road stop')
        self.assertEqual((self.case,self.chat),before)

    def test_alerts_are_scoped_to_a_stop_and_have_safe_links(self):
        from server.app.assistant.transit_info import answer
        info=answer(self.ctx,{'intent':'transit_info','transit_topic':'alerts'},self.case,self.chat,[],True)['transit_information']
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.calls[1][1]['stop_id'],'2050123')
        self.assertEqual(info['stop_name'],'Parramatta Road stop')
        self.assertIsNone(info['alerts'][1]['url'])

    def test_ambiguous_no_consent_and_unlocated_never_make_external_calls(self):
        from server.app.assistant.transit_info import answer
        self.chat['messages'][0]['listings'].append(self.catalog.get('domain:18258009'))
        result=answer(self.ctx,{'intent':'transit_info','transit_topic':'nearby'},self.case,self.chat,[],True)
        self.assertIn('Which property',result['content']);self.assertEqual(self.calls,[])
        result=answer(self.ctx,{'intent':'transit_info','transit_topic':'nearby','listing_ids':[self.home['listing_id']]},self.case,self.chat,[],False)
        self.assertEqual(self.calls,[])
        unknown=next(r for r in self.catalog.matching({}) if not r['usyd_commute']['origin'])
        self.chat={'messages':[{'listings':[unknown]}]}
        result=answer(self.ctx,{'intent':'transit_info','transit_topic':'nearby'},self.case,self.chat,[],True)
        self.assertIn('location',result['content']);self.assertEqual(self.calls,[])

    def test_model_boundary_disallows_arbitrary_coordinates_and_unknown_property_ids(self):
        from server.app.assistant.intents import validate_intent,response_schema
        from jsonschema import Draft202012Validator
        value={'intent':'transit_info','transit_topic':'nearby','listing_ids':[self.home['listing_id']]}
        self.assertFalse(list(Draft202012Validator(response_schema()).iter_errors(value)))
        self.assertEqual(validate_intent(value,self.catalog,[self.home['listing_id']]),value)
        for changed in ({**value,'latitude':1},{**value,'listing_ids':['domain:invented']},{**value,'transit_topic':'shell'}):
            with self.assertRaises(ApiError):validate_intent(changed,self.catalog,[self.home['listing_id']])
