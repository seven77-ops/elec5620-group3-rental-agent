"""Transactional local persistence. Prototype identity is not authentication."""
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class ConflictError(ValueError):
    pass


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    case_id TEXT PRIMARY KEY, serial INTEGER NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profiles (
                    case_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (case_id, version));
                CREATE TRIGGER IF NOT EXISTS immutable_profile_update BEFORE UPDATE ON profiles
                    BEGIN SELECT RAISE(ABORT, 'confirmed profiles are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_profile_delete BEFORE DELETE ON profiles
                    BEGIN SELECT RAISE(ABORT, 'confirmed profiles are immutable'); END;
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, version INTEGER NOT NULL,
                    dataset_hash TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(case_id, version, dataset_hash));
            ''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=15, factory=ClosingConnection)

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, session):
        with self.transaction() as db:
            db.execute('INSERT INTO sessions VALUES (?, ?, ?)',
                       (session['case_id'], 0, dumps(session)))

    def load(self, case_id, db=None):
        if db is None:
            with self.connect() as conn:
                return self.load(case_id, conn)
        row = db.execute('SELECT serial, payload FROM sessions WHERE case_id=?', (case_id,)).fetchone()
        if row is None:
            raise ValueError('Case not found.')
        return json.loads(row[1]), row[0]

    def save(self, session, serial, db=None):
        if db is None:
            with self.transaction() as conn:
                return self.save(session, serial, conn)
        cur = db.execute('UPDATE sessions SET serial=?, payload=? WHERE case_id=? AND serial=?',
                         (serial + 1, dumps(session), session['case_id'], serial))
        if cur.rowcount != 1:
            raise ConflictError('Session changed. Reload and review the latest revision.')

    def profile(self, case_id, version, db=None):
        if db is None:
            with self.connect() as conn:
                return self.profile(case_id, version, conn)
        row = db.execute('SELECT payload FROM profiles WHERE case_id=? AND version=?', (case_id, version)).fetchone()
        if not row:
            raise ValueError('Saved confirmed profile not found.')
        return json.loads(row[0])

    def task(self, task_id, db=None):
        if db is None:
            with self.connect() as conn:
                return self.task(task_id, conn)
        row = db.execute('SELECT payload FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if row is None:
            raise ValueError('Task not found.')
        return json.loads(row[0])

    def save_task(self, task, db):
        db.execute('UPDATE tasks SET payload=? WHERE task_id=?', (dumps(task), task['task_id']))

    def tasks(self, case_id):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                'SELECT payload FROM tasks WHERE case_id=? ORDER BY version, task_id', (case_id,))]
