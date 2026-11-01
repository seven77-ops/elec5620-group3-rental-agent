"""Local review inbox, derived from durable cases and decisions."""
import json
from datetime import datetime

from fastapi import Request

from ..settings import TENANT


class OperatorInbox:
    def __init__(self, ctx):
        self.ctx = ctx

    def read(self, request: Request):
        repo = self.ctx.repo
        items = []
        with repo.transaction() as db:
            cases = [json.loads(row[0]) for row in db.execute(
                'SELECT body FROM objects WHERE kind=? ORDER BY rowid DESC', ('case',))]
            for case in cases:
                for ref in case.get('reviews', []):
                    saved = repo.get(db, 'review', ref['review_id'])
                    if not saved:
                        continue
                    review = saved['review']
                    snapshots = [json.loads(row[0]) for row in db.execute(
                        'SELECT body FROM objects WHERE kind=? AND id LIKE ? ORDER BY rowid',
                        ('review_version', ref['review_id'] + ':%'))]
                    decisions = []
                    for snapshot in [*snapshots, review]:
                        decision = snapshot.get('human_review')
                        if decision and decision.get('status') in ('approved', 'returned') and decision not in decisions:
                            decisions.append(decision)
                    if review['status'] != 'Awaiting Human Review' and not decisions:
                        continue
                    address = (review.get('fields', {}).get('address') or {}).get('value')
                    items.append({'kind': 'contract', 'case_id': case['case_id'],
                        'review_id': review['review_id'], 'address': address or 'Address unverified',
                        'version': review['version'], 'status': 'open' if review['status'] == 'Awaiting Human Review' else 'closed',
                        'created_at': review['created_at'], 'reason': 'High-risk contract review',
                        'decisions': decisions, 'review': review})
            from .issue_reports import issue_view
            for row in db.execute('SELECT body FROM objects WHERE kind=? ORDER BY rowid DESC', ('issue_report',)):
                items.append(issue_view(self.ctx,db,json.loads(row[0])))
            for row in db.execute('SELECT body FROM objects WHERE kind=? ORDER BY id', ('review_demo',)):
                items.append(json.loads(row[0]))
        # Agent 4 owns a separate database. Do not hold the web writer while reading it.
        for case in cases:
            identifier = case.get('aftercare_case_id')
            if not identifier:
                continue
            record = self.ctx.aftercare.get(identifier, TENANT)
            for review in record.get('reviews', []):
                from .review_files import review_files
                refs = set(review['source_refs'])
                items.append({**review, 'kind': 'aftercare', 'case_id': case['case_id'],
                    'attachments': review_files(self.ctx, case['case_id'], review),
                    'aftercare_case_id': identifier, 'address': record['tenancy']['address'],
                    'version': record['version'],
                    'claims': [claim for claim in (record.get('bond') or {}).get('claims', [])
                               if 'claim:' + claim['claim_id'] in refs],
                    'history': [] if review.get('report') else (record.get('bond') or {}).get('history', [])[-3:],
                    'evidence': [entry for entry in record.get('evidence', [])
                                 if not review.get('report') or entry['evidence_id'] in refs]})
        # Contracts and issue reports retain different ISO timezone offsets.
        # Compare instants so a newer UTC report is not buried below older AEDT records.
        items.sort(key=lambda item: (item['status'] == 'open',
            datetime.fromisoformat(item['created_at'].replace('Z','+00:00')).timestamp(), item['case_id']), reverse=True)
        return {'items': items, 'pending_count': sum(item['status'] == 'open' for item in items)}
