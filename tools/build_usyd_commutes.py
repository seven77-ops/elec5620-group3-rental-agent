"""Explicit, resumable harvest of public listing addresses and USYD route observations.

No chat/case tables are opened. No keys or provider response bodies are logged.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import argparse, json,os,time,math
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
from datetime import datetime,timedelta
from local_ai_env import load_ai_env
from server.app.common import now,ApiError
from server.app.real_data.catalog import RealCatalog
from server.app.real_data.providers import DataProviders,TFNSW_DOC
from server.app.commute.locations import LocationResolver,listing_address,normalized,ADDRESS
from server.app.commute.usyd import DESTINATION,CAMPUS_FINGERPRINT,MODES
from server.app.commute.snapshot import distance_metres,observation
from server.app.commute.planner import arrival_for,timing_matches


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));temp.replace(path)


def blank(mode,reason='No checked route is available yet.'):
    return {'status':'unavailable','duration_minutes':None,'distance_m':None,
            'source_url':TFNSW_DOC if mode not in ('walk','bike','drive') else 'https://routing.openstreetmap.de/about.html',
            'reason':reason}



def observations_for(journeys,arrival,queried_at):
    """Keep distinct actual journeys and backwards-compatible includes-mode slots."""
    from server.app.commute.transit_options import planned_journeys,distinct
    options=planned_journeys(journeys,arrival.isoformat(),queried_at,limit=None)
    observations={}
    for mode in ('public_transport','train','metro','bus'):
        usable=[r for r in options if mode=='public_transport' or mode in r.get('transit_modes',[])]
        observations[mode]=(deepcopy(usable[0]) if usable else
            {**blank(mode,'No checked journey including this mode was returned for this query.'),
             'status':'no_observed_option','queried_at':queried_at})
    return observations,distinct(options)


def run(args):
    catalog=RealCatalog();rows=catalog.matching({});resolver=LocationResolver();resolver.provider.timeout=18
    output=Path(args.output)
    points={}
    if args.locations_seed and Path(args.locations_seed).is_file():
        seeded=json.loads(Path(args.locations_seed).read_text())
        if seeded.get('catalog_fingerprint')==catalog.fingerprint:points=seeded.get('points',{})
    location_file=output.with_name('locations.json')
    if location_file.is_file():
        d=json.loads(location_file.read_text())
        if d.get('catalog_fingerprint')==catalog.fingerprint:points.update(d.get('points',{}))
    missing=[r for r in rows if r['listing_id'] not in points]
    print('Exact address lookup',len(missing),'remaining',flush=True)
    if missing and not args.reuse_locations:
        result=resolver.prefetch(missing,batch_size=4);points.update(result['points'])
        print('Exact coordinates',len(points),'query errors',len(result['errors']),flush=True)
        save(location_file,{'catalog_fingerprint':catalog.fingerprint,'queried_at':now(),'points':points})
    # Individual recovery avoids dropping batches containing large apartment buildings.
    # Equal coordinate duplicates are still ambiguous in the live resolver; do not guess.
    missing=[] if args.reuse_locations else [r for r in rows if r['listing_id'] not in points]
    def resolve_one(row):
        own=LocationResolver();own.provider.timeout=15
        try:
            point=own.listing(row)
            if point:return row,{**point,'original_address':row['address'],'original_suburb':row['suburb']}
        except ApiError:pass
        return row,None
    with ThreadPoolExecutor(max_workers=3) as pool:
        for index,(row,point) in enumerate(pool.map(resolve_one,missing),1):
            if point:points[row['listing_id']]=point
            if index%25==0:
                save(location_file,{'catalog_fingerprint':catalog.fingerprint,'queried_at':now(),'points':points})
                print('Address recovery',index,'/',len(missing),'located',len(points),flush=True)
    save(location_file,{'catalog_fingerprint':catalog.fingerprint,'queried_at':now(),'points':points})
    arrival=arrival_for({'arrival_time':'09:00','travel_day':'weekday'})
    data={'schema_version':'1.0','catalog_fingerprint':catalog.fingerprint,'campus_fingerprint':CAMPUS_FINGERPRINT,
          'destination':DESTINATION,'generated_at':now(),'reference_arrival_at':arrival.isoformat(),'records':{},
          'limitations':['Fisher Library is the common campus reference. Indoor walking and travel to specific classrooms are additional.',
            'Road travel times are separate network estimates. Driving excludes live congestion, parking, tolls and walking after alighting.',
            'Public transport (any combination) uses sampled scheduled journeys arriving before 09:00 on the listed weekday, including walking, waiting and transfers; it does not cover all times.',
            'Legacy train, metro and bus slots mean a journey includes that mode, possibly with other transit and walking connections. Missing observations do not establish that no such route exists.']}
    if output.is_file():
        previous=json.loads(output.read_text())
        if previous.get('catalog_fingerprint')==catalog.fingerprint and previous.get('campus_fingerprint')==CAMPUS_FINGERPRINT:
            data['records']=previous.get('records',{})
            data['reference_arrival_at']=previous.get('reference_arrival_at',data['reference_arrival_at'])
            previous_arrival=datetime.fromisoformat(data['reference_arrival_at'])
            if previous_arrival>datetime.now(previous_arrival.tzinfo):arrival=previous_arrival
            else:data['reference_arrival_at']=arrival.isoformat()
    for row in rows:
        identifier=row['listing_id'];point=points.get(identifier)
        record=data['records'].setdefault(identifier,{'listing_id':identifier,'address':row['address'],'suburb':row['suburb'],
             'origin':point,'straight_line_distance_m':distance_metres(point) if point else None,
             'modes':{m:blank(m,'The full property address could not be uniquely located.' if not point else 'Not queried yet.') for m in MODES}})
        if record.get('origin')!=point:
            record['modes']={m:blank(m,'The location changed. Check routes again.') for m in MODES}
            record.pop('transit_options',None)
        record['origin']=point;record['straight_line_distance_m']=distance_metres(point) if point else None
    save(output,data)
    located=[r for r in rows if r['listing_id'] in points]
    provider=DataProviders(env=load_ai_env(ROOT/'.env',os.environ));provider.timeout=25
    for mode,backend in (('drive','car'),('bike','bike'),('walk','foot')):
        pending=[r for r in located if observation({'usyd_commute':data['records'][r['listing_id']]},mode) is None]
        for start in range(0,len(pending),40):
            batch=pending[start:start+40]
            coords=';'.join(f"{points[r['listing_id']]['longitude']:.7f},{points[r['listing_id']]['latitude']:.7f}" for r in batch)
            coords+=f";{DESTINATION['longitude']:.7f},{DESTINATION['latitude']:.7f}"
            url=f'https://routing.openstreetmap.de/routed-{backend}/table/v1/driving/'+coords
            try:
                response=provider.request('GET',url,{'User-Agent':'USYDRentalAssistant/1.0 (local student project)'},params={
                    'sources':';'.join(map(str,range(len(batch)))),'destinations':str(len(batch)),'annotations':'duration,distance'})
                if response.get('code')!='Ok' or len(response['durations'])!=len(batch) or len(response['distances'])!=len(batch):raise ValueError('matrix shape')
                for i,row in enumerate(batch):
                    seconds=response['durations'][i][0];distance=response['distances'][i][0]
                    if type(seconds) not in (int,float) or type(distance) not in (int,float) or not math.isfinite(seconds) or not math.isfinite(distance) or seconds<0 or distance<0:continue
                    origin=points[row['listing_id']];straight=distance_metres(origin)
                    if distance+100<straight:continue
                    data['records'][row['listing_id']]['modes'][mode]={'status':'routing_estimate','duration_minutes':round(seconds/60,2),
                        'distance_m':round(distance),'queried_at':now(),'source_url':f'https://routing.openstreetmap.de/routed-{backend}/',
                        'routing_profile':backend,'attribution':'© OpenStreetMap contributors · FOSSGIS OSRM',
                        'reason':'Independent '+backend+' road-network estimate; excludes live traffic and indoor travel.'}
            except (ApiError,ValueError,KeyError,TypeError,IndexError) as error:
                print('Road batch unavailable',mode,start,type(error).__name__,flush=True)
            data['generated_at']=now();save(output,data)
            print('Road',mode,min(start+40,len(pending)),'/',len(pending),flush=True)
            time.sleep(1.1)
    if not args.skip_transit and provider.public_config()['tfnsw']['configured']:
        pending=[r for r in located if observation({'usyd_commute':data['records'][r['listing_id']]},'public_transport') is None]
        def trip(row):
            origin=points[row['listing_id']]
            try:
                response=provider.trips({'origin':{k:origin[k] for k in ('latitude','longitude')},
                    'destination':{k:DESTINATION[k] for k in ('latitude','longitude')},'arrival_at':arrival.isoformat(),'allow_external':True})
                observations,options=observations_for(response['journeys'],arrival,now())
                return row['listing_id'],observations,options,None
            except ApiError as e:return row['listing_id'],{},[],e.code
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(trip,r) for r in pending]
            errors=0
            for count,f in enumerate(as_completed(futures),1):
                identifier,observations,options,error=f.result();data['records'][identifier]['modes'].update(observations)
                if not error:data['records'][identifier]['transit_options']=options
                if error:errors+=1
                if count%10==0 or count==len(pending):
                    data['generated_at']=now();save(output,data)
                    print('Transit',count,'/',len(pending),'request errors',errors,flush=True)
    data['generated_at']=now()
    data['coverage']={'total':len(rows),'located':len(points),'modes':{m:sum(r['modes'][m]['duration_minutes'] is not None for r in data['records'].values()) for m in MODES}}
    from server.app.commute.estimates import derive_estimates
    for record in data['records'].values():record.pop('estimates',None)
    estimates=derive_estimates(catalog._rows,data['records'])
    for identifier,modes in estimates.items():data['records'][identifier]['estimates']=modes
    data['coverage']['coarse_estimated']=len(estimates)
    save(output,data);print('COVERAGE',json.dumps(data['coverage']),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default=str(ROOT/'agent2/data/real/usyd-commutes.json'))
    p.add_argument('--locations-seed');p.add_argument('--reuse-locations',action='store_true');p.add_argument('--skip-transit',action='store_true');run(p.parse_args())
