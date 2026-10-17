"""SQLite aggregate + immutable command receipts under a single serial write transaction."""
from contextlib import closing
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
from .contracts import canonical, validate
from .errors import AftercareError, require
from .services import apply, new_case


class AftercareAgent:
    """Local coordinator. Actor IDs are demo identities, not production authentication."""
    def __init__(self, database, *, operator_ids=(), gateway=None):
        self.database = str(database)
        self.operator_ids = set(operator_ids)
        self.gateway = gateway
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS receipts (
                    actor_id TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    response TEXT NOT NULL, PRIMARY KEY(actor_id, request_id));
                CREATE TABLE IF NOT EXISTS m3_reviews (
                    review_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, upstream_case_id TEXT NOT NULL,
                    version INTEGER NOT NULL, fingerprint TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS m3_handoffs (
                    upstream_case_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                    tenancy_id TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL UNIQUE,
                    review_id TEXT NOT NULL UNIQUE, packet TEXT NOT NULL, response TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS m3_receipts (
                    actor_id TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    response TEXT NOT NULL, PRIMARY KEY(actor_id, request_id));
                CREATE TABLE IF NOT EXISTS m3_confirmations (
                    confirmation_id TEXT NOT NULL, version INTEGER NOT NULL, fingerprint TEXT NOT NULL,
                    tenant_id TEXT NOT NULL, upstream_case_id TEXT NOT NULL,
                    PRIMARY KEY(confirmation_id, version));
            ''')

    def connect(self):
        return sqlite3.connect(self.database, timeout=25, isolation_level=None)

    @contextmanager
    def transaction(self):
        with closing(self.connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                yield conn
                conn.commit()
            except sqlite3.Error as exc:
                conn.rollback()
                raise AftercareError('storage_error', 'Storage transaction failed; no success was recorded') from exc
            except Exception:
                conn.rollback()
                raise

    def receive(self, packet, *, actor_id, as_of):
        """Consume a coordinator-bound M3 packet; actor/time are not browser payload fields."""
        from .handoff import receive
        return receive(self, packet, actor_id=actor_id, as_of=as_of)

    def get_handoff(self, case_id, actor_id):
        self.get(case_id, actor_id)
        with closing(self.connect()) as conn:
            row = conn.execute('SELECT packet FROM m3_handoffs WHERE case_id=?', (case_id,)).fetchone()
        require(row is not None, 'not_found', 'No M3 handoff is linked to this case')
        return json.loads(row[0])

    def authorize(self, case, actor_id, role, operation=None):
        if role == 'operator':
            require(actor_id in self.operator_ids, 'access_denied', 'Operator is not in the locally configured allowlist')
            require(operation in {None, 'operator_decision'}, 'access_denied', 'Operators may only read cases or record review decisions')
        else:
            require(role == 'tenant' and case['tenant_id'] == actor_id, 'access_denied', 'Case is unavailable to this tenant')
            require(operation != 'operator_decision', 'access_denied', 'An authorised operator decision is required')

    def get(self, case_id, actor_id, role='tenant'):
        with closing(self.connect()) as conn:
            row = conn.execute('SELECT document FROM cases WHERE case_id=?', (case_id,)).fetchone()
        require(row is not None, 'not_found', 'Case not found')
        case = json.loads(row[0])
        self.authorize(case, actor_id, role)
        return case

    def submit(self, command):
        validate('command', command)
        with self.transaction() as conn:
            return self._submit(conn, command)

    def _submit(self, conn, command):
        """Caller owns the transaction, including any M3 mapping and receipt writes."""
        digest = sha256(canonical(command).encode()).hexdigest()
        row = conn.execute('SELECT document FROM cases WHERE case_id=?', (command['case_id'],)).fetchone()
        if row:
            case = json.loads(row[0])
            self.authorize(case, command['actor_id'], command['actor_role'], command['operation'])
        else:
            require(command['operation'] == 'create' and command['actor_role'] == 'tenant', 'not_found', 'Create the tenant case first')
            case = new_case(command)
            self.authorize(case, command['actor_id'], command['actor_role'], command['operation'])
        old = conn.execute('SELECT fingerprint,response FROM receipts WHERE actor_id=? AND request_id=?',
                           (command['actor_id'], command['request_id'])).fetchone()
        if old:
            require(old[0] == digest, 'request_conflict', 'A request ID was reused with different input')
            return json.loads(old[1])
        require(not row or command['operation'] != 'create', 'already_exists', 'Case already exists')
        require(case['version'] == command['expected_version'], 'version_conflict', 'Reload the case and use its current version')
        binding = conn.execute('SELECT packet FROM m3_handoffs WHERE case_id=?', (case['case_id'],)).fetchone()
        if binding and command['operation'] in {'create_plan', 'confirm_plan', 'revise_tenancy'}:
            from .handoff import fingerprint
            original = json.loads(binding[0])['review']
            latest = conn.execute('SELECT version,fingerprint FROM m3_reviews WHERE review_id=?', (original['review_id'],)).fetchone()
            require(latest == (original['version'], fingerprint(original)), 'handoff_review_stale',
                    'A newer M3 review is known; reconcile the lease before creating a plan or revising context')
        if binding and command['operation'] == 'create_plan':
            require(command['payload']['schedule_confirmed'] is True, 'move_out_confirmation_required',
                    'Confirm the move-out date separately before creating a plan')
        if binding and command['operation'] == 'revise_tenancy':
            incoming = command['payload']['tenancy']
            require(all(incoming[k] == case['tenancy'][k] for k in
                        ('address', 'jurisdiction', 'tenancy_type', 'source_ref', 'source_version')),
                    'handoff_source_immutable', 'Keep M3 confirmed facts and provenance; reconcile contract changes separately')
        result = apply(case, command, gateway=self.gateway, property_only=bool(binding))
        validate('aftercare-case', case)
        response = {'schema_version': '1.0', 'request_id': command['request_id'],
                    'case_id': case['case_id'], 'version': case['version'],
                    'result': result, 'case': case,
                    'task': {'task_id': command['request_id'], 'responsible_role': 'AftercareAgent',
                             'case_id': case['case_id'], 'input_version': command['expected_version'],
                             'output_version': case['version'], 'status': 'completed',
                             'output_refs': [f"case:{case['case_id']}@{case['version']}"]}}
        conn.execute('INSERT INTO cases(case_id,document) VALUES(?,?) ON CONFLICT(case_id) DO UPDATE SET document=excluded.document',
                     (case['case_id'], canonical(case)))
        conn.execute('INSERT INTO receipts VALUES(?,?,?,?)',
                     (command['actor_id'], command['request_id'], digest, canonical(response)))
        return response
