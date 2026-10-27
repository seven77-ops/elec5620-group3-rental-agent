"""Install the pinned transit sidecar into its own ignored environment."""
import os,shutil,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    uv=shutil.which('uv')
    if not uv:raise SystemExit('Install uv first: https://docs.astral.sh/uv/getting-started/installation/')
    environment={**os.environ,'UV_PROJECT_ENVIRONMENT':str(ROOT/'.runtime/tfnsw-mcp/.venv')}
    subprocess.run([uv,'sync','--locked','--no-dev','--project',str(ROOT/'integrations/tfnsw_mcp/upstream')],env=environment,check=True)
    print('Transit MCP installed in .runtime/tfnsw-mcp/.venv; website dependencies unchanged.')

if __name__=='__main__':main()
