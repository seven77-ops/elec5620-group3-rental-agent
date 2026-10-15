"""SQLite aggregate + immutable command receipts under a single serial write transaction."""
from contextlib import closing
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
            ''')

    def connect(self):
        return sqlite3.connect(self.database, timeout=25, isolation_level=None)

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
        digest = sha256(canonical(command).encode()).hexdigest()
        with closing(self.connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
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
                    conn.rollback()
                    return json.loads(old[1])
                require(not row or command['operation'] != 'create', 'already_exists', 'Case already exists')
                require(case['version'] == command['expected_version'], 'version_conflict', 'Reload the case and use its current version')
                result = apply(case, command, gateway=self.gateway)
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
                conn.commit()
                return response
            except sqlite3.Error as exc:
                conn.rollback()
                raise AftercareError('storage_error', 'Storage transaction failed; no success was recorded') from exc
            except Exception:
                conn.rollback()
                raise
