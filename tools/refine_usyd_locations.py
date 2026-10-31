"""Explicit second-source harvest for unresolved public catalogue building addresses."""
import argparse,json,os,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from local_ai_env import load_ai_env
from server.app.real_data.catalog import RealCatalog
from server.app.real_data.providers import DataProviders
from server.app.commute.locations import listing_address
from server.app.commute.tfnsw_addresses import resolve
from server.app.common import now,ApiError

def run(output):
    catalog=RealCatalog();provider=DataProviders(env=load_ai_env(ROOT/'.env',os.environ));provider.timeout=12
    if not provider.tfnsw_key:raise SystemExit('TFNSW_API_KEY is not configured')
    groups={}
    for row in catalog.matching({}):
        if not (row.get('usyd_commute') or {}).get('origin') and listing_address(row):
            groups.setdefault(listing_address(row),[]).append(row)
    points={};errors=0
    def fetch(rows):
        try:return rows,resolve(rows[0],provider),None
        except ApiError as error:return rows,None,error.code
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending=[pool.submit(fetch,rows) for rows in groups.values()]
        for n,future in enumerate(as_completed(pending),1):
            rows,point,error=future.result();errors+=bool(error)
            if point:
                for row in rows:
                    # Build and validate source metadata against each unit's original identity.
                    from server.app.commute.tfnsw_addresses import address_point
                    own=address_point(row,{'locations':[point['matched_address']]},queried_at=point['queried_at'])
                    if own:points[row['listing_id']]=own
            if n%20==0 or n==len(pending):
                path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
                temp=path.with_suffix('.tmp')
                temp.write_text(json.dumps({'catalog_fingerprint':catalog.fingerprint,'queried_at':now(),
                    'points':points,'queried_buildings':n,'errors':errors},ensure_ascii=False,indent=2))
                temp.replace(path)
                print('Buildings checked',n,'/',len(pending),'homes located',len(points),'request errors',errors,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    run(parser.parse_args().output)
