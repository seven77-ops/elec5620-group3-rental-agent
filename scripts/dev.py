"""Start the local-only API and Vite together. Ctrl+C stops both children."""
from pathlib import Path
import os
import shutil
import argparse
import secrets
import signal
import subprocess
import sys
import time
from local_ai_env import load_ai_env
from transit_sidecar import start as start_transit

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description='Run the local rental UI and API')
    parser.add_argument('--web-port', type=int, default=5173)
    parser.add_argument('--api-port', type=int, default=8000)
    ports = parser.parse_args()
    if not all(1 <= port <= 65535 for port in (ports.web_port, ports.api_port)):
        parser.error('Ports must be between 1 and 65535')
    if not (ROOT / 'frontend/node_modules').is_dir():
        raise SystemExit('Install frontend dependencies first: cd frontend && npm ci')
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    environment = load_ai_env(ROOT / '.env', os.environ)
    environment['RENTAL_DEV_API_PORT'] = str(ports.api_port)
    # Windows defaults to a locale code page (e.g. GBK); data files are UTF-8.
    environment.setdefault('PYTHONUTF8', '1')
    if not environment.get('RENTAL_OPERATOR_KEY'):
        key_path = runtime / 'operator-key.txt'
        if not key_path.exists():
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(secrets.token_urlsafe(32))
        environment['RENTAL_OPERATOR_KEY'] = key_path.read_text(encoding='utf-8').strip()
        print(f'Local operator key file: {key_path}', flush=True)
    children = []
    def stop(*_):
        for child in children:
            if child.poll() is None:
                child.terminate()
    signal.signal(signal.SIGTERM, stop)
    try:
        transit=start_transit(environment)
        if transit:children.append(transit)
        required=[]
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server.app.main:app', '--host', '127.0.0.1', '--port', str(ports.api_port)], cwd=ROOT, env=environment))
        required.append(children[-1])
        # On Windows npm is npm.cmd, which CreateProcess cannot find by bare name.
        npm = shutil.which('npm', path=environment.get('PATH')) or 'npm'
        children.append(subprocess.Popen([npm, 'run', 'dev', '--', '--port', str(ports.web_port)], cwd=ROOT / 'frontend', env=environment))
        required.append(children[-1])
        print(f'Open http://127.0.0.1:{ports.web_port} · API http://127.0.0.1:{ports.api_port}/docs', flush=True)
        while all(child.poll() is None for child in required):
            time.sleep(0.5)
        return next((child.returncode for child in required if child.returncode), 0)
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
