"""Local-only, secret-free optional child of the website development runner."""
from pathlib import Path
import json,os,socket,subprocess,time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
def start(environment):
    if environment.get('RENTAL_TFNSW_MCP_ENABLED','1').lower() not in ('1','true'):return None
    python=ROOT/'.runtime/tfnsw-mcp/.venv/bin/python'
    if not python.is_file() or not environment.get('TFNSW_API_KEY'):return None
    port=int(environment.get('RENTAL_TFNSW_MCP_PORT','6401'))
    if not 1<=port<=65535:raise ValueError('Invalid transit MCP port')
    url=f'http://127.0.0.1:{port}'
    try:
        with socket.socket() as probe:probe.bind(('127.0.0.1',port))
    except OSError:
        print('Transit MCP port is occupied; direct TfNSW fallback remains enabled.',flush=True)
        return None
    # No API/model key is inherited by the tool server. Its HTTP requests carry
    # credentials per call, supplied only by our backend MCP client.
    child_env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SYSTEMROOT')}
    child_env.update(HOST='127.0.0.1',PORT=str(port),PYTHONUNBUFFERED='1')
    directory=ROOT/'.runtime/tfnsw-mcp';directory.mkdir(parents=True,exist_ok=True)
    with (directory/'server.log').open('a') as log:
        child=subprocess.Popen([str(python),'-m','tfnsw_trip_planner_mcp'],cwd=ROOT/'integrations/tfnsw_mcp/upstream',env=child_env,stdout=log,stderr=log)
    deadline=time.monotonic()+8
    while time.monotonic()<deadline and child.poll() is None:
        try:
            with urlopen(url+'/health',timeout=.4) as response:
                if json.load(response).get('status')=='ok':
                    environment['RENTAL_TFNSW_MCP_URL']=url+'/mcp'
                    print(f'Transit MCP ready at {url}/mcp',flush=True);return child
        except (OSError,ValueError):pass
        time.sleep(.1)
    if child.poll() is None:
        child.terminate()
        try:child.wait(timeout=3)
        except subprocess.TimeoutExpired:child.kill();child.wait()
    print('Transit MCP unavailable; direct TfNSW fallback remains enabled.',flush=True)
    return None
