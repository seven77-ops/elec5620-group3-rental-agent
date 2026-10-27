"""Read-only transit answers bound to an existing public house reference."""
import math
from urllib.parse import urlsplit
from ..common import ApiError,now,require
from ..real_data.providers import TFNSW_DOC
from ..commute.mcp_journeys import stop_id
from .tools import known_listings

TRANSIT_SCHEMA={'type':'object','required':['intent','transit_topic'],'additionalProperties':False,
    'properties':{'intent':{'const':'transit_info'},'transit_topic':{'enum':['nearby','alerts']},
                  'listing_ids':{'type':'array','minItems':1,'maxItems':1,'uniqueItems':True,'items':{'type':'string'}}}}

def nearby(provider,origin):
    payload=provider.tool('find_nearby',{'latitude':origin['latitude'],'longitude':origin['longitude'],
        'radius_m':500,'type_1':'STOP','max_results':50,'concise':False})
    rows=payload.get('locations')
    require(isinstance(rows,list) and len(rows)<=50,502,'mcp_invalid_stops','附近车站信息暂时无法核对。')
    result=[];seen=set()
    for row in rows:
        if not isinstance(row,dict):continue
        # The pinned summary drops STOP_NAME_WITH_PLACE/stopId and can emit
        # "undefined, undefined". Read actual named STOP fields, not G-prefixed IDs.
        properties=row.get('properties') if isinstance(row.get('properties'),dict) else {}
        ident=stop_id(properties.get('stopId'));distance=row.get('distance');name=properties.get('STOP_NAME_WITH_PLACE')
        if (row.get('type')!='stop' or not ident or ident in seen
                or not isinstance(name,str) or not name.strip() or type(distance) not in (int,float)
                or not math.isfinite(distance) or not 0<=distance<=500):continue
        seen.add(ident);result.append({'id':ident,'name':name[:180],'distance_m':round(distance)})
    return sorted(result,key=lambda r:(r['distance_m'],r['id']))[:10]

def safe_url(value):
    if not isinstance(value,str) or len(value)>1500:return None
    try:
        url=urlsplit(value)
        return value if (url.scheme=='https' and not url.username and not url.password and
            url.hostname in ('transportnsw.info','www.transportnsw.info','transport.nsw.gov.au','www.transport.nsw.gov.au','opendata.transport.nsw.gov.au')) else None
    except ValueError:return None

def answer(ctx,intent,case,chat,requested,allow_external):
    base={'intent':'transit_info','agent':'agent2','listings':[],'actions':[]}
    ids=requested or intent.get('listing_ids',[])
    known=known_listings(chat);selection=case.get('selection')
    if selection:known=list(dict.fromkeys([*known,selection['listing_id']]))
    require(set(ids)<=set(known),422,'invalid_reference','请选择当前对话中的一套房源。')
    if len(ids)>1:return {**base,'content':'你想查询哪一套房源？请先选中一套。'}
    if not ids and selection:ids=[selection['listing_id']]
    if not ids:
        latest=next((m['listings'] for m in reversed(chat['messages']) if m.get('listings')),[])
        if len(latest)==1:ids=[latest[0]['listing_id']]
    if len(ids)!=1:return {**base,'content':'你想查询哪一套房源？请选中一套，或告诉我房源编号。'}
    if not allow_external:return {**base,'content':'本次尚未启用交通查询，房源详情中可以直接打开地图。'}
    home=ctx.settings.catalog.get(ids[0]);origin=(home.get('usyd_commute') or {}).get('origin')
    if not origin:return {**base,'content':'这套房源的位置仍待确认，请先在房源详情中用地图核对地址。'}
    try:
        stops=nearby(ctx.transit_provider,origin)
        info={'topic':intent['transit_topic'],'listing_id':home['listing_id'],'address':home['address'],
              'queried_at':now(),'source_url':TFNSW_DOC,'stops':stops,'alerts':[],'stop_name':None}
        if intent['transit_topic']=='nearby':
            return {**base,'content':f"{home['address']} 周边500米的车站参考如下，最多展示10个。" if stops else '暂时没有查到这套房源500米内的可用车站信息。',
                    'transit_information':info}
        if not stops:return {**base,'content':'暂时没有找到可关联的附近车站，无法核对该站的运营提醒。','transit_information':info}
        stop=stops[0]
        payload=ctx.transit_provider.tool('get_alerts',{'stop_id':stop['id'],'current_only':True,'max_results':5,'concise':True})
        rows=payload.get('alerts')
        require(isinstance(rows,list) and len(rows)<=5,502,'mcp_invalid_alerts','线路提醒暂时无法核对。')
        info['stop_name']=stop['name']
        info['alerts']=[{'title':r['subtitle'][:500],'url':safe_url(r.get('url'))} for r in rows
                        if isinstance(r,dict) and isinstance(r.get('subtitle'),str) and r['subtitle'].strip()]
        return {**base,'content':f"已查询附近站点 {stop['name']} 的当前公开运营提醒。"+
                ('' if info['alerts'] else '暂未检索到相关提醒，出发前请再核对班次。'),'transit_information':info}
    except ApiError:
        return {**base,'content':'这次暂时没能查到交通信息，请稍后再试，或在房源详情里打开地图查看。'}
