#!/usr/bin/env python3
"""Run the UI journey against disposable local servers and an isolated database."""
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    specs = sys.argv[1:] or ['full-rental-journey.spec.ts', 'commute-short-updates.spec.ts', 'single-selection.spec.ts']
    output = Path(tempfile.mkdtemp(prefix='rental-full-journey-'))
    children = []
    # Reserve distinct ports together. Vite strictPort and child exit checks catch
    # the small race after these reservations are released.
    reservations = [socket.socket(), socket.socket()]
    for connection in reservations:
        connection.bind(('127.0.0.1', 0))
    api_port, web_port = [connection.getsockname()[1] for connection in reservations]
    for connection in reservations:
        connection.close()
    python = ROOT / '.venv/bin/python'
    if not python.exists():
        raise SystemExit('请先安装项目 .venv 依赖。')
    env = {**os.environ, 'PYTHONPATH': str(ROOT),
           'RENTAL_ASSISTANT_TEST_RUNTIME': str(output / 'database'),
           'RENTAL_DEV_API_PORT': str(api_port),
           'WEB_TEST_BASE_URL': f'http://127.0.0.1:{web_port}',
           'FULL_JOURNEY_ISOLATED': '1',
           'FULL_JOURNEY_PYTHON': str(python),
           'PLAYWRIGHT_HTML_OUTPUT_DIR': str(output / 'report'),
           'PLAYWRIGHT_HTML_OPEN': 'never'}
    chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    if not env.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE') and chrome.exists():
        env['PLAYWRIGHT_CHROMIUM_EXECUTABLE'] = str(chrome)
    npm = shutil.which('npm')
    if not npm:
        raise SystemExit('找不到 npm，请先安装 Node.js。')
    print(f'测试报告、截图、PDF、临时数据库：{output}', flush=True)
    try:
        with (output / 'servers.log').open('w') as log:
            commands = [
                ([str(python), '-m', 'uvicorn', 'server.tests.assistant_demo_app:app',
                  '--host', '127.0.0.1', '--port', str(api_port)], ROOT),
                ([npm, 'run', 'dev', '--', '--port', str(web_port), '--strictPort'], ROOT / 'frontend'),
            ]
            for command, cwd in commands:
                children.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log,
                                                 start_new_session=True))
            for url in (f'http://127.0.0.1:{api_port}/api/v1/health', env['WEB_TEST_BASE_URL']):
                deadline = time.monotonic() + 30
                while True:
                    if any(child.poll() is not None for child in children):
                        raise RuntimeError(f'测试服务启动失败，见 {output / "servers.log"}')
                    try:
                        with urllib.request.urlopen(url, timeout=1) as response:
                            if response.status == 200:
                                break
                    except (OSError, urllib.error.URLError):
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f'测试服务启动超时，见 {output / "servers.log"}')
                    time.sleep(.2)
            return subprocess.run(
                [str(ROOT / 'frontend/node_modules/.bin/playwright'), 'test',
                 *specs, '--reporter=list,html',
                 '--output', str(output / 'artifacts'), '--trace=retain-on-failure'],
                cwd=ROOT / 'frontend', env=env, check=False,
            ).returncode
    finally:
        for child in children:
            try:
                # npm launches Vite as a descendant; stop our entire process group.
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        print(f'查看报告：{output / "report/index.html"}', flush=True)


if __name__ == '__main__':
    sys.exit(main())
