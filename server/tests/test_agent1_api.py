"""Browser API must use the member's actual Agent1 state and task lifecycle."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient


class Agent1ApiTests(unittest.TestCase):
    def setUp(self):
        from server.app.main import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = create_app(runtime_dir=self.tmp.name)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.case = self.client.post('/api/v1/cases', json={}).json()
        self.cid = self.case['case_id']

    def post(self, action, body):
        return self.client.post(f'/api/v1/cases/{self.cid}/{action}', json=body)

    def ready(self):
        self.assertIn('agent1', self.case, 'New browser cases must be backed by actual Agent1')
        from preference_agent.store import Store
        return Store(Path(self.tmp.name) / 'web.sqlite3')

    def confirmation(self):
        return {'draft_revision': self.case['draft']['revision'],
                'fingerprint': self.case['draft']['fingerprint'],
                'review_token': self.case['agent1']['review_token']}

    def confirm(self):
        self.ready()
        response = self.post('profile-confirmations', self.confirmation())
        self.assertEqual(response.status_code, 200, response.text)
        self.case = response.json()
        return self.case['confirmations'][-1]['version']

    def evaluate(self, request='evaluation'):
        return self.post('evaluations', {'request_id': request,
                          'confirmation_version': self.case['confirmations'][-1]['version']})

    def revise(self, weights=None):
        profile = copy.deepcopy(self.case['draft']['profile'])
        profile['weights'] = weights or {'commute': .15, 'cost': .6, 'housing': .15, 'amenities': .1}
        response = self.post('profile-drafts', {'expected_revision': self.case['draft']['revision'], 'profile': profile})
        self.assertEqual(response.status_code, 200, response.text)
        self.case = response.json()

    def test_new_case_uses_actual_agent1_and_confirmed_version_survives_restart(self):
        store = self.ready()
        self.assertEqual(self.client.get('/api/v1/demo-config').json()['capabilities']['agent1'], 'local_service')
        session, _ = store.load(self.case['agent1']['case_id'])
        self.assertEqual(session['search_id'], self.case['search_id'])
        self.assertEqual(session['state'], 'AwaitingConfirmation')
        self.confirm()
        record = store.profile(session['case_id'], 1)
        self.assertEqual(record['profile'], self.case['confirmations'][0]['profile'])
        self.assertEqual(record['confirmationMethod'], 'explicit_local_ui_action')
        from server.app.main import create_app
        restarted = TestClient(create_app(runtime_dir=self.tmp.name))
        saved = restarted.get(f'/api/v1/cases/{self.cid}').json()
        self.assertEqual(saved, self.case)
        self.assertEqual(saved['agent1']['state'], 'Confirmed')

    def test_exact_review_token_required_and_confirmation_retry_is_idempotent(self):
        self.ready()
        body = self.confirmation()
        self.assertEqual(self.post('profile-confirmations', {**body, 'review_token': 'wrong'}).status_code, 409)
        self.assertEqual(self.post('profile-confirmations', {k:v for k,v in body.items() if k!='review_token'}).status_code, 422)
        self.confirm()
        self.assertEqual(self.post('profile-confirmations', body).json(), self.case)
        self.assertEqual(self.post('profile-confirmations', {**body, 'review_token': 'wrong'}).status_code, 409)

    def test_revision_requires_new_token_and_retains_original_profile(self):
        store = self.ready()
        old = self.confirmation()
        self.confirm()
        original = store.profile(self.case['agent1']['case_id'], 1)
        self.revise()
        self.assertEqual(self.case['draft']['revision'], 2)
        self.assertNotEqual(self.case['agent1']['review_token'], old['review_token'])
        self.assertEqual(self.post('profile-confirmations', old).status_code, 409)
        self.assertEqual(self.evaluate().status_code, 409)
        self.confirm()
        self.assertEqual(self.case['confirmations'][-1]['version'], 2)
        self.assertEqual(store.profile(self.case['agent1']['case_id'], 1), original)

    def test_actual_task_replay_and_verified_comparison(self):
        store = self.ready()
        self.confirm()
        first = self.evaluate()
        self.assertEqual(first.status_code, 200, first.text)
        first = first.json()
        task = store.task(first['agent1_task_id'])
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['report'], first['report'])
        self.assertEqual(self.evaluate().json(), first)
        self.assertEqual(self.evaluate('different-http-request').json(), first)
        self.assertEqual(store.task(task['task_id'])['attempts'], 1)
        self.revise()
        self.confirm()
        second = self.evaluate('second-version').json()
        self.assertEqual(second['report']['recommendations'][0]['listing_id'], 'DEMO-012')
        self.assertEqual(second['comparison_source'], 'agent1_verified_versions')
        changed = next(r for r in second['comparison']['rows'] if r['listing_id']=='DEMO-002')
        self.assertEqual((changed['before_rank'], changed['after_rank']), (9,3))
        self.assertEqual(self.client.get('/api/v1/evaluations/'+first['run_id']).json(), first)

    def test_response_loss_reconciles_real_completed_task(self):
        store = self.ready()
        self.confirm()
        from preference_agent.handover import LocalSupervisor
        route = LocalSupervisor.routeTask
        def lost(receiver, task_id):
            route(receiver, task_id)
            raise RuntimeError('simulated reply lost after completion')
        with patch.object(LocalSupervisor, 'routeTask', lost):
            first = self.evaluate()
        # Agent1 reconciles its persisted completion before returning to the API.
        self.assertEqual(first.status_code, 200, first.text)
        task = store.task(first.json()['agent1_task_id'])
        self.assertEqual(task['attempts'], 1)
        self.assertEqual(self.evaluate().json(), first.json())

    def test_failed_adapter_confirmation_rolls_back_core_version(self):
        store = self.ready()
        from server.app.repository import Repository
        put = Repository.put
        def fail(repo, db, kind, key, value):
            if kind=='case' and value.get('confirmations'):
                raise RuntimeError('simulated adapter failure')
            return put(repo, db, kind, key, value)
        with patch.object(Repository, 'put', fail):
            response = self.post('profile-confirmations', self.confirmation())
        self.assertEqual(response.status_code, 500)
        with self.assertRaises(ValueError):
            store.profile(self.case['agent1']['case_id'], 1)
        self.assertEqual(self.client.get(f'/api/v1/cases/{self.cid}').json(), self.case)
        self.confirm()

    def test_concurrent_same_confirmation_creates_one_core_version(self):
        store = self.ready()
        body = self.confirmation()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.post('profile-confirmations', body), range(2)))
        self.assertEqual([r.status_code for r in responses], [200,200])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(store.load(self.case['agent1']['case_id'])[0]['latest_version'], 1)

    def test_late_old_response_cannot_publish_over_current_version(self):
        store = self.ready()
        self.confirm()
        entered, release = Event(), Event()
        from preference_agent.handover import LocalSupervisor
        route = LocalSupervisor.routeTask
        def delayed(receiver, task_id):
            result = route(receiver, task_id)
            if result['version']==1:
                entered.set()
                if not release.wait(10):
                    raise RuntimeError('review test release timeout')
            return result
        with patch.object(LocalSupervisor, 'routeTask', delayed), ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.evaluate, 'delayed-v1')
            try:
                self.assertTrue(entered.wait(5))
                self.revise()
                self.confirm()
                latest = self.evaluate('current-v2')
                self.assertEqual(latest.status_code, 200, latest.text)
            finally:
                release.set()
            old = pending.result(timeout=5)
        self.assertEqual(old.status_code, 409, old.text)
        saved = self.client.get(f'/api/v1/cases/{self.cid}').json()
        self.assertEqual(saved['evaluations'][-1]['run_id'], latest.json()['run_id'])
        self.assertEqual(store.load(self.case['agent1']['case_id'])[0]['latest_version'], 2)

    def test_legacy_cases_keep_history_without_fabricating_agent1_confirmation(self):
        self.ready()
        repo = self.app.state.repository
        legacy = copy.deepcopy(self.case)
        legacy.pop('agent1',None)
        legacy.pop('agent1_case_id',None)
        with repo.transaction() as db:
            repo.put(db,'case',self.cid,legacy)
        self.assertEqual(self.client.get(f'/api/v1/cases/{self.cid}').status_code,200)
        attempted = self.post('profile-confirmations', {'draft_revision':1,'fingerprint':legacy['draft']['fingerprint'],'review_token':'legacy'})
        self.assertEqual(attempted.status_code,409)
        self.assertEqual(attempted.json()['error']['code'],'agent1_upgrade_required')


if __name__=='__main__':
    unittest.main()
