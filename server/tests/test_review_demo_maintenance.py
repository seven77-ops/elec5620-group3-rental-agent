"""Offline local cleanup preserves unrelated data and installs explicit examples."""
import json,tempfile,unittest
from pathlib import Path
from scripts.review_demo_maintenance import connection
from fastapi.testclient import TestClient
from server.app.main import create_app

class ReviewDemoMaintenanceTests(unittest.TestCase):
    def test_dry_run_backup_cleanup_seed_and_idempotency(self):
        from scripts.review_demo_maintenance import maintain
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);runtime=base/'active';client=TestClient(create_app(runtime_dir=runtime))
            case=client.post('/api/v1/cases',json={}).json();cid=case['case_id'];repo=client.app.state.repository
            report=client.post(f'/api/v1/cases/{cid}/issue-reports',json={'request_id':'old-test','category':'furniture','description':'Old test report','attachment_ids':[]})
            self.assertEqual(report.status_code,200)
            with repo.transaction() as db:
                repo.put(db,'review','old-review',{'case_id':cid,'file_ref':'old-contract.txt','review':{'review_id':'old-review'}})
                repo.put(db,'review_version','old-review:1',{'review_id':'old-review'})
                current=repo.get(db,'case',cid);current['reviews']=[{'review_id':'old-review'}];repo.put(db,'case',cid,current)
                repo.put(db,'lease_draft','keep-draft',{'case_id':cid,'fields':{'tenant_names':'Original tenant'}})
                repo.put(db,'favorites',cid,{'case_id':cid,'items':['keep-listing']})
                repo.put(db,'living_services',cid,{'case_id':cid,'version':1,'profile':{'agent_name':'Original contact'},'bookings':[{'provider_id':'keep-provider'}],'repairs':[{'repair_id':'keep-repair','attachment_ids':['keep-file']}]})
                for identifier,purpose in [('old-file','moveout'),('keep-file','repair')]:
                    repo.put(db,'living_attachment',identifier,{'case_id':cid,'file_ref':identifier+'.bin','metadata':{'attachment_id':identifier,'purpose':purpose,'repair_id':'keep-repair' if purpose=='repair' else None}})
                repo.put(db,'living_attachment_index',cid,{'ids':['old-file','keep-file']})
            (runtime/'uploads').mkdir(exist_ok=True);(runtime/'uploads/old-contract.txt').write_text('Fictional old contract')
            (runtime/'living-files').mkdir();(runtime/'living-files/old-file.bin').write_bytes(b'old');(runtime/'living-files/keep-file.bin').write_bytes(b'keep')
            before=client.get(f'/api/v1/cases/{cid}').json()
            preview=maintain(runtime,apply=False,backup_root=base/'backups')
            self.assertGreater(preview['remove_objects'].get('review',0),0)
            self.assertEqual(client.get(f'/api/v1/cases/{cid}').json(),before)
            result=maintain(runtime,apply=True,backup_root=base/'backups')
            self.assertTrue((Path(result['backup'])/'web.sqlite3').is_file())
            self.assertTrue((Path(result['backup'])/'uploads/old-contract.txt').is_file())
            self.assertFalse((runtime/'uploads/old-contract.txt').exists())
            self.assertFalse((runtime/'living-files/old-file.bin').exists());self.assertTrue((runtime/'living-files/keep-file.bin').exists())
            with repo.transaction() as db:
                self.assertIsNone(repo.get(db,'review','old-review'));self.assertEqual(repo.get(db,'case',cid)['reviews'],[])
                self.assertIsNotNone(repo.get(db,'lease_draft','keep-draft'));self.assertEqual(repo.get(db,'favorites',cid)['items'],['keep-listing'])
                self.assertEqual(repo.get(db,'living_services',cid)['bookings'],[{'provider_id':'keep-provider'}])
                self.assertEqual(repo.get(db,'living_attachment_index',cid)['ids'],['keep-file'])
            items=client.get('/api/v1/operator/reviews').json()['items']
            self.assertEqual(len(items),5);self.assertTrue(all(i['is_demo'] and i['status']!='open' for i in items))
            self.assertEqual(len({i['reason'] for i in items}),5)
            self.assertEqual(client.get('/api/v1/issue-reports').json()['items'],[])
            maintain(runtime,apply=True,backup_root=base/'backups')
            self.assertEqual(client.get('/api/v1/operator/reviews').json()['items'],items)

    def test_legacy_review_receipts_and_private_chat_copies_do_not_resurrect(self):
        from scripts.review_demo_maintenance import maintain
        from server.tests.legacy_app import create_app as legacy_app
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'active';client=TestClient(legacy_app(runtime_dir=runtime))
            config=client.get('/api/v1/demo-config').json();cid=client.post('/api/v1/cases',json={}).json()['case_id']
            tenancy={**config['tenancy_template'],'confirmed':True,'baseline_evidence_refs':[]}
            created=client.post('/api/v1/aftercare/commands',json={'case_id':cid,'request_id':'legacy-create','expected_version':0,'operation':'create','payload':{'tenancy':tenancy,'evidence':[]}})
            self.assertEqual(created.status_code,200,created.text)
            legacy_id=created.json()['case_id']
            opened=client.post('/api/v1/aftercare/commands',json={'case_id':cid,'request_id':'keep-bond','expected_version':created.json()['version'],'operation':'open_bond','payload':{'bond_reference':'KEEP-INDEPENDENT-BOND','deposit_evidence_ref':None}})
            self.assertEqual(opened.status_code,200,opened.text)
            retained_bond=opened.json()['case']['bond'];retained_time=opened.json()['case']['updated_at']
            with connection(runtime/'aftercare.sqlite3') as db:
                value=json.loads(db.execute('select document from cases where case_id=?',(legacy_id,)).fetchone()[0])
                value['reviews']=[{'review_id':'old-legacy','source_refs':[],'report':{'attachment_ids':[]},'status':'open'}]
                db.execute('update cases set document=? where case_id=?',(json.dumps(value),legacy_id))
            repo=client.app.state.repository
            with repo.transaction() as db:
                repo.put(db,'review','private-review',{'case_id':cid,'file_ref':'private.txt','review':{'review_id':'private-review'}})
                repo.put(db,'assistant_conversation','keep-chat',{'case_id':cid,'revision':1,'messages':[
                    {'role':'user','content':'Original user words'},
                    {'role':'assistant','content':'Private cached quotation','knowledge':{'private_binding':{'review_id':'private-review'},'citations':[{'quote':'Private cached quotation'}]}}]})
            maintain(runtime,apply=True,backup_root=Path(folder)/'backups')
            self.assertEqual(len(client.get('/api/v1/operator/reviews').json()['items']),5)
            with connection(runtime/'aftercare.sqlite3') as db:
                value=json.loads(db.execute('select document from cases where case_id=?',(legacy_id,)).fetchone()[0])
                self.assertEqual(value['reviews'],[]);self.assertEqual(value['bond'],retained_bond)
                self.assertEqual(value['updated_at'],retained_time)
                self.assertEqual(db.execute('select count(*) from receipts').fetchone()[0],0)
            with repo.transaction() as db:
                chat=repo.get(db,'assistant_conversation','keep-chat')
                self.assertEqual(chat['messages'][0]['content'],'Original user words')
                self.assertEqual(chat['messages'][1]['knowledge']['citations'],[])
                self.assertNotIn('Private cached quotation',json.dumps(chat))
            example=client.get('/api/v1/operator/reviews').json()['items'][0]
            denied=client.post('/api/v1/issue-reports/'+example['review_id']+'/advice',json={'request_id':'no-demo-write','expected_version':1,'note':'Do not change examples'})
            self.assertEqual(denied.status_code,404)
