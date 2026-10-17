"""Start the local-only API and Vite together. Ctrl+C stops both children."""
from pathlib import Path
import os
import secrets
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

def main():
    if not (ROOT / 'frontend/node_modules').is_dir():
        raise SystemExit('Install frontend dependencies first: cd frontend && npm ci')
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    environment = os.environ.copy()
    if not environment.get('RENTAL_OPERATOR_KEY'):
        key_path = runtime / 'operator-key.txt'
        if not key_path.exists():
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(secrets.token_urlsafe(32))
        environment['RENTAL_OPERATOR_KEY'] = key_path.read_text().strip()
        print(f'Local operator key file: {key_path}', flush=True)
    children = []
    def stop(*_):
        for child in children:
            if child.poll() is None:
                child.terminate()
    signal.signal(signal.SIGTERM, stop)
    try:
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server.app.main:app', '--host', '127.0.0.1', '--port', '8000'], cwd=ROOT, env=environment))
        children.append(subprocess.Popen(['npm', 'run', 'dev'], cwd=ROOT / 'frontend', env=environment))
        print('Open http://127.0.0.1:5173 · API http://127.0.0.1:8000/docs', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        return next((child.returncode for child in children if child.returncode), 0)
    except KeyboardInterrupt:
        return 0
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()

if __name__ == '__main__':
    raise SystemExit(main())
