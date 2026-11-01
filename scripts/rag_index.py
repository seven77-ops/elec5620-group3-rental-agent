"""Refresh reviewed English public snapshots and atomically publish a local RAG index."""
import argparse, hashlib, json, os, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server.app.rag.index import KnowledgeIndex
from server.app.rag.provider import RetrievalProvider
from server.app.rag.sources import SOURCES
from scripts.local_ai_env import load_ai_env

SNAPSHOT=ROOT/'data/knowledge/en/documents.json'


from server.app.rag.capture import capture,parse_source
from server.app.rag.product_guide import product_document


def build(index,documents,provider,embed=False):
    rows=index.prepare(documents)
    if not embed:index.publish(documents);return
    if not provider.status()['embedding_configured']:raise ValueError('Configure a shared chat key (or RENTAL_RAG_API_KEY override) and RENTAL_RAG_EMBEDDING_URL first')
    vectors=[];missing=[];cached={}
    for row in rows:
        with index.connect() as db:
            hit=db.execute('SELECT body FROM vectors WHERE id=? AND model=? AND dimensions=?',(row['chunk_id'],provider.model,provider.dimensions)).fetchone()
        if hit:cached[row['chunk_id']]=json.loads(hit[0])
        else:missing.append(row)
    # All external work completes before replacing the live snapshot.
    for start in range(0,len(missing),10):
        batch=missing[start:start+10]
        print(f'Embedding public chunks {start+1}–{start+len(batch)} of {len(missing)}',flush=True)
        for row,vector in zip(batch,provider.embed([r.get('embedding_text',r['text']) for r in batch],timeout=30)):cached[row['chunk_id']]=vector
    vectors=[cached[row['chunk_id']] for row in rows]
    index.publish(documents,vectors,provider.model,provider.dimensions)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true',help='Capture the fixed reviewed public sources; no private files are uploaded')
    parser.add_argument('--embed',action='store_true',help='Send public source chunks to the configured embedding endpoint')
    parser.add_argument('--runtime',type=Path,default=ROOT/'.runtime')
    args=parser.parse_args()
    documents=list(ThreadPoolExecutor(max_workers=3).map(capture,SOURCES)) if args.refresh else json.loads(SNAPSHOT.read_text())
    documents=[d for d in documents if d.get('source_type')!='product_guide']+[product_document()]
    env=load_ai_env(ROOT/'.env',os.environ);provider=RetrievalProvider(env)
    index=KnowledgeIndex(args.runtime/'rag.sqlite3');build(index,documents,provider,args.embed)
    if args.refresh:
        SNAPSHOT.parent.mkdir(parents=True,exist_ok=True);temp=SNAPSHOT.with_suffix('.tmp');temp.write_text(json.dumps(documents,ensure_ascii=False,indent=2));temp.replace(SNAPSHOT)
    print(json.dumps({**index.status(),**provider.status()},ensure_ascii=False))

if __name__=='__main__':main()
