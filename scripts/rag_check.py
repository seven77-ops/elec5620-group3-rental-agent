"""Show safe retrieval configuration; --probe sends synthetic English strings only."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.local_ai_env import load_ai_env
from server.app.rag.provider import RetrievalProvider,RetrievalError

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--probe',action='store_true');args=parser.parse_args()
    provider=RetrievalProvider(load_ai_env(ROOT/'.env',os.environ));result=provider.status()
    if args.probe:
        for kind,task in (
            ('embedding',lambda:len(provider.embed(['A synthetic rental repair request.'])[0])),
            ('rerank',lambda:provider.rerank('rental repair',['A synthetic repair request.','A synthetic cooking recipe.']))):
            try:result[kind+'_probe']={'status':'succeeded','result':task()}
            except RetrievalError as e:result[kind+'_probe']={'status':'unavailable','code':str(e),'http_status':e.http_status}
    print(json.dumps(result,indent=2))
    return 1 if args.probe and any(result[k+'_probe']['status']!='succeeded' for k in ('embedding','rerank')) else 0

if __name__=='__main__':raise SystemExit(main())
