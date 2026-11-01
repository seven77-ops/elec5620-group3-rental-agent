"""English product copy must not change the numeric facts of its public data."""
import json,re,unittest
from pathlib import Path
from server.app.bootstrap import ROOT

class EnglishCatalogueTests(unittest.TestCase):
    def test_public_authored_catalogue_copy_is_english(self):
        files=('server/app/living/providers.json','server/app/living/data/utility-plans.json',
               'agent2/data/areas/sydney-evidence.json','agent2/data/demo/listings.json',
               'agent2/data/real/usyd-commutes.json','agent3/data/demo/corrections.json',
               'agent3/data/demo/selected-listing-evidence.json')
        def check(value,path=()):
            if isinstance(value,str):
                # Proper publication titles/publisher names remain original evidence.
                if len(path)>1 and path[-2]=='source' and path[-1] in ('title','publisher'):return
                self.assertIsNone(re.search('[\u4e00-\u9fff]',value),'.'.join(path)+': '+value)
            elif isinstance(value,dict):
                for key,item in value.items():check(item,path+(key,))
            elif isinstance(value,list):
                for n,item in enumerate(value):check(item,path+(str(n),))
        for file in files:
            with self.subTest(file=file):check(json.loads((ROOT/file).read_text()),(file,))
    def test_bundled_demo_contract_and_selection_use_current_english_fixtures(self):
        from rental_agent.engine import evaluate
        from rental_agent.handoff import build_selected_listing_evidence
        from contract_agent.handoff import validate_selection
        packet=json.loads((ROOT/'agent3/data/demo/selected-listing-evidence.json').read_text())
        dataset=json.loads((ROOT/'agent2/data/demo/listings.json').read_text())
        report=evaluate(packet['profile'],dataset,as_of=dataset['as_of'])
        current=build_selected_listing_evidence(report,dataset,packet['listing_id'],
            selected_at=packet['selected_at'],user_confirmed=True)
        self.assertEqual(packet,current,'Bundled handoff must be regenerated with the current English fixture and evidence fingerprints')
        validate_selection(packet)
        address=packet['listing_snapshot']['address']
        agreement=(ROOT/'agent3/data/demo/agreements/selection-demo.txt').read_text()
        self.assertIsNone(re.search('[\u4e00-\u9fff]',agreement))
        self.assertIn('Address: '+address,agreement)
        self.assertEqual(json.loads((ROOT/'agent3/data/demo/corrections.json').read_text())['address'],address)

    def test_english_display_labels_preserve_existing_commute_evidence_binding(self):
        from server.app.real_data.catalog import RealCatalog
        from server.app.commute.usyd import DESTINATION,CAMPUS_FINGERPRINT
        catalog=RealCatalog()
        snapshot=json.loads((ROOT/'agent2/data/real/usyd-commutes.json').read_text())
        self.assertEqual(catalog.fingerprint,snapshot['catalog_fingerprint'])
        self.assertEqual(CAMPUS_FINGERPRINT,snapshot['campus_fingerprint'])
        self.assertEqual(snapshot['destination'],DESTINATION)
        self.assertIsNotNone(catalog.commutes)
        self.assertTrue(catalog.matching({'usyd_mode':'public_transport','usyd_max_minutes':30}))

    def test_english_utility_snapshot_keeps_valid_structured_facts(self):
        from server.app.living.utility_catalog import valid_seed
        data=json.loads((ROOT/'server/app/living/data/utility-plans.json').read_text())
        self.assertEqual(valid_seed(data),data)
        self.assertEqual(len(data['plans']),165)
        self.assertTrue(all(plan['currency']=='AUD' for plan in data['plans']))

if __name__=='__main__':unittest.main()
