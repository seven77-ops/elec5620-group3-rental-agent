"""Explicitly refresh public AER observations; never fetch customer/account data.

Run from the project root with .venv/bin/python tools/refresh_utility_energy.py.
Internet/water observations keep their own dates and are not renewed by this job.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo
import httpx
from server.app.living.utility_normalize import energy_plan
from server.app.living.utility_catalog import valid_seed

NAMES={
 'agl':{'Residential Smart Saver','Residential Smart Saver - New To AGL','Residential Smart Saver - New to AGL','Residential Standing Offer','Residential Three for Free'},
 'origin':{'Origin Go Variable Ongoing','Origin Basic','Origin Weekday Shift','Origin Night Shift'},
 'energyaustralia':{'Flexi Plan','Rate Fix','Standing Offer (Home)'},
}
POSTCODES={'2000','2042','2134','2135','2138','2145'}


def get(url,version):
    for attempt in range(3):
        try:
            with httpx.Client(timeout=35,trust_env=False,follow_redirects=False) as client:
                response=client.get(url,headers={'x-v':str(version),'x-min-v':str(version),'Accept':'application/json'})
                response.raise_for_status();return response.json()
        except (httpx.TransportError,httpx.HTTPStatusError):
            if attempt==2:raise
            time.sleep(1+attempt)


def run(path):
    seed=valid_seed(json.loads(path.read_text()));selected=[];observed=datetime.now(ZoneInfo('Australia/Sydney')).isoformat()
    for brand,wanted in NAMES.items():
        page=1
        while True:
            data=get(f'https://cdr.energymadeeasy.gov.au/{brand}/cds-au/v1/energy/plans?page={page}&page-size=1000',1)
            for p in data['data']['plans']:
                if p['customerType']=='RESIDENTIAL' and p['displayName'] in wanted and set(p['geography'].get('includedPostcodes',[]))&POSTCODES:
                    selected.append((brand,p['planId']))
            if page>=data['meta']['totalPages']:break
            page+=1
            if page>20:raise ValueError('Unexpected AER pagination')
            time.sleep(.5)
    if any(not any(brand==b for brand,_ in selected) for b in NAMES):raise ValueError('AER selection incomplete; current snapshot retained')
    def detail(item):
        brand,identifier=item
        d=get(f'https://cdr.energymadeeasy.gov.au/{brand}/cds-au/v1/energy/plans/'+quote(identifier,safe=''),3)['data']
        if d['planId']!=identifier or d['brand']!=brand:raise ValueError('AER identity mismatch')
        time.sleep(1.1)
        return energy_plan(d,observed)
    with ThreadPoolExecutor(max_workers=2) as pool:energy=list(pool.map(detail,selected))
    result={**seed,'plans':[p for p in seed['plans'] if p['category'] not in ('electricity','gas')]+energy}
    result['energy_refreshed_at']=observed
    valid_seed(result)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');temp.replace(path)
    print(f'Updated {len(energy)} public energy observations; internet/water dates preserved. Restart the API to import this snapshot.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'server/app/living/data/utility-plans.json')
    args=parser.parse_args();run(args.output)
