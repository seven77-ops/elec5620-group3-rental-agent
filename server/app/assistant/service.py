"""Durable assistant turns, stale-input rejection and explicit Agent1 proposals."""
from contextlib import contextmanager
from copy import copy,deepcopy
import hashlib
from time import time
from ..common import ApiError,require,shape,integer,request_id,opaque_ref,uid,now
from ..repository import canonical
from ..ai.provider import ProviderError
from ..adapters.real_agent2 import RealProfilesAdapter
from .intents import validate_intent,merge_profile,response_schema
from .tools import execute,known_listings,CLARIFY,UNKNOWN,preference_summary,listing_context,history_context,search_answer
from .dialogue import BRIEF_SCHEMA,merge_brief,brief_summary,next_question,brief_filters,brief_profile_patch,profile_brief
from .living import read_snapshot, model_context, answer_living
from ..living.service import LivingService
from .repair_dialogue import repair_focus, focus_context


def signature(case):
    return hashlib.sha256(canonical(case).encode()).hexdigest()


def message(role,content,agent='assistant',**extra):
    return {'message_id':uid('message'),'role':role,'content':content,'agent':agent,
            'created_at':now(),'listings':[],'actions':[],**extra}


class BorrowedRepository:
    """Public adapters can compose atomically without opening nested SQLite writers."""
    def __init__(self,repo,db): self.repo,self.db=repo,db
    def __getattr__(self,key): return getattr(self.repo,key)
    @contextmanager
    def transaction(self): yield self.db


class AssistantService:
    def __init__(self,ctx): self.ctx=ctx

    def catalog(self):
        require(self.ctx.settings.catalog is not None,503,'real_catalog_unavailable','真实房源库未加载。')
        return self.ctx.settings.catalog

    def get(self,db,case_id,conversation_id):
        self.ctx.get(db,'case',case_id)
        value=self.ctx.get(db,'assistant_conversation',conversation_id)
        require(value['case_id']==case_id,404,'not_found','未找到这个对话。')
        return value

    def list(self,case_id: str):
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db,'case',case_id)
            index=self.ctx.repo.get(db,'assistant_index',case_id) or []
            return {'items':sorted(index,key=lambda i:i['updated_at'],reverse=True)}

    def save(self,db,c):
        self.ctx.repo.put(db,'assistant_conversation',c['conversation_id'],c)
        index=self.ctx.repo.get(db,'assistant_index',c['case_id']) or []
        index=[i for i in index if i['conversation_id']!=c['conversation_id']]
        index.append({'conversation_id':c['conversation_id'],'title':c['title'],'updated_at':now(),'message_count':len(c['messages'])})
        self.ctx.repo.put(db,'assistant_index',c['case_id'],index)

    def create(self,case_id: str,body: dict):
        shape(body,())
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db,'case',case_id)
            index=self.ctx.repo.get(db,'assistant_index',case_id) or []
            require(len(index)<100,409,'conversation_limit','当前案例最多保存100个对话。')
            c={'conversation_id':uid('chat'),'case_id':case_id,'title':'新对话','revision':0,'messages':[]}
            self.save(db,c); return c

    def read(self,case_id: str,conversation_id: str):
        with self.ctx.repo.transaction() as db:
            return self.living_status(db,self.get(db,case_id,conversation_id))

    def living_status(self,db,conversation):
        result=deepcopy(conversation)
        for entry in result['messages']:
            for action in entry.get('actions',[]):
                if action.get('type')=='apply_living_services':
                    proposal=self.ctx.repo.get(db,'living_proposal',action.get('proposal_id',''))
                    if proposal and proposal['case_id']==result['case_id']:
                        if proposal['status']=='applied':action['applied']=True
                        elif proposal['status']=='superseded':action['superseded']=True
        return result

    def send(self,case_id: str,conversation_id: str,body: dict):
        shape(body,('request_id','expected_revision','message','allow_external_ai'),('listing_ids',))
        request_id(body['request_id'])
        require(body['allow_external_ai'] is True,422,'ai_consent_required','请明确同意本次使用外部 AI。')
        require(integer(body['expected_revision']),422,'invalid_input','请提供当前对话版本。')
        require(isinstance(body['message'],str) and 0<len(body['message'].strip())<=3000,422,'invalid_input','消息须为1至3000字。')
        requested=body.get('listing_ids',[])
        require(isinstance(requested,list) and len(requested)<=5 and all(isinstance(i,str) for i in requested) and len(requested)==len(set(requested)),422,'invalid_reference','最多选择5套已展示房源。')
        catalog=self.catalog(); key=case_id+':'+body['request_id']; identity={'conversation_id':conversation_id,**body}
        token=uid('attempt')
        with self.ctx.repo.transaction() as db:
            c=self.get(db,case_id,conversation_id); case=self.ctx.get(db,'case',case_id)
            old=self.ctx.receipt(db,'assistant_turn_receipt',key,identity)
            if old and 'result' in old: return old['result']
            require(not old or old.get('status')!='pending' or time()-old['started_at']>60,409,'request_in_progress','本次消息正在处理，请稍后重试。')
            require(c['revision']==body['expected_revision'],409,'conversation_conflict','对话已更新，请刷新后重试。')
            require(len(c['messages'])<200,409,'message_limit','这个对话已满，请新建对话。')
            cards_context=listing_context(catalog,known_listings(c))
            ids=[row['listing_id'] for row in cards_context]
            require(set(requested)<=set(ids),422,'invalid_reference','只能引用当前对话已展示的房源。')
            snapshot=signature(case)
            living_snapshot=read_snapshot(self.ctx,db,case_id)
            self.ctx.repo.put(db,'assistant_turn_receipt',key,{'input':identity,'token':token,'started_at':time(),'status':'pending'})
        # The complete external call runs with no SQLite transaction held.
        living_focus=repair_focus(self.ctx,case_id,c,living_snapshot)
        context={'task':'assistant_intent','response_schema':response_schema(),'message':body['message'],
            'history':history_context(c,ids),
            'draft_profile':case['draft']['profile'],
            'confirmed_profile':case['confirmations'][-1]['profile'] if (case['confirmations'] and case['confirmations'][-1]['draft_revision']==case['draft']['revision'] and case['confirmations'][-1]['fingerprint']==case['draft']['fingerprint'] and case['agent1']['state']=='Confirmed') else None,
            'displayed_listing_ids':ids,'displayed_listings':cards_context,'selected_listing_ids':requested,
            'rental_brief':c.get('rental_brief',{}),'dialogue_mode':c.get('dialogue_mode'),
            'saved_candidate':({'listing_id':case['selection']['listing_id'],
                'address':case['selection']['listing_snapshot'].get('address'),
                'profile_version':case['selection']['profile_version']} if case.get('selection') else None),
            'brief_reconstruction_required':'rental_brief' not in c and bool(c['messages']),
            'last_search_filters':c.get('last_search_filters',{}),
            'catalog':{'suburbs':catalog.suburbs,'fingerprint':catalog.fingerprint},
            'living_services':model_context(living_snapshot,LivingService(self.ctx).directory(),focus_context(living_focus)),
            'unknowns':['rent_scope','bills','availability','commute_minutes','move_in_date']}
        try:
            output,call=self.ctx.ai_provider.call(context)
            calls=[call]
            intent=validate_intent(output,catalog,ids)
            proposal=None
            memory=c
            if intent['intent']=='collect_preferences' and context['brief_reconstruction_required']:
                # Legacy transcripts lack structured slots. Recover only explicit user
                # requirements in a small extraction task; latest-turn values win.
                recovered,recovery_call=self.ctx.ai_provider.call({'task':'assistant_brief',
                    'user_messages':[m['content'][:3000] for m in c['messages'][-20:] if m['role']=='user'],
                    'suburbs':catalog.suburbs,
                    'response_schema':{'type':'object','required':['intent','brief_patch'],'additionalProperties':False,
                        'properties':{'intent':{'const':'collect_preferences'},'brief_patch':BRIEF_SCHEMA}}})
                calls.append(recovery_call)
                recovered=validate_intent(recovered,catalog,[])
                require(recovered['intent']=='collect_preferences',502,'ai_invalid_response','历史需求提取失败，请重试。')
                memory={**c,'rental_brief':recovered.get('brief_patch',{})}
            brief=merge_brief(memory,intent)
            question=next_question(brief) if intent['intent']=='collect_preferences' else None
            if intent['intent']=='collect_preferences' and question:
                summary=brief_summary(brief)
                answer={'intent':'collect_preferences','agent':'agent1',
                    'content':('记下了：'+summary+'。\n' if summary else '')+question,'listings':[],'actions':[]}
            elif intent['intent'] in ('update_preferences','collect_preferences'):
                patch=brief_profile_patch(brief) if intent['intent']=='collect_preferences' else intent.get('preference_patch',{})
                try:
                    require(bool(patch),422,'empty_patch','请补充偏好。')
                    profile=merge_profile(case['draft']['profile'],patch)
                    housing=profile.get('housing_preferences',{})
                    catalog.filters({k:v for k,v in housing.items() if k!='budget_match_mode'})
                except (ApiError,ValueError):
                    answer={'intent':'clarify','agent':'agent1','content':CLARIFY,'listings':[],'actions':[]}
                else:
                    proposal={'proposal_id':uid('proposal'),'case_id':case_id,'conversation_id':conversation_id,
                        'case_signature':snapshot,'conversation_revision':c['revision']+1,'profile':profile,'status':'proposed'}
                    answer={'intent':'update_preferences','agent':'agent1',
                        'content':'已整理新的租房条件。请核对下方摘要；确认后保存偏好并生成候选。',
                        'listings':[],'actions':[{'type':'apply_preferences','label':'确认偏好并生成候选','proposal_id':proposal['proposal_id'],'summary':preference_summary(profile)}]}
                    if intent['intent']=='collect_preferences':
                        preview=search_answer(catalog,brief_filters(brief))
                        preview['actions'].extend(answer['actions'])
                        answer={**preview,'intent':'collect_preferences','agent':'agent1',
                            'content':'条件记下了：'+brief_summary(brief)+'。\n'+preview['content']+'\n确认下方条件后，我再保存为你的租房偏好。'}
            elif intent['intent']=='living_services':
                answer=answer_living(self.ctx,intent,case_id,c,body['message'],living_snapshot['version'],living_focus)
            else: answer=execute(intent,case,c,catalog,requested)
            search_filters=answer.pop('_search_filters',None)
            next_living_focus=answer.pop('_living_focus',None)
            superseded=answer.pop('_supersede_living_proposal',None)
            if answer['intent']=='clarify' and any(word in body['message'].casefold() for word in ('噪音','噪声','隔音','noise','soundproof','通勤','commute','账单','bills','在租','available')):
                answer['content']='目前没有已核实的噪音、隔音、通勤、账单和在租数据。请先核实这些事实；我可以比较广告卧卫、车位和周租。'
            safe_calls=[{k:v for k,v in entry.items() if k in {'task','provider','model','status','attempted','duration_ms','started_at','usage','error_code','simulated'}} for entry in calls]
            with self.ctx.repo.transaction() as db:
                current=self.get(db,case_id,conversation_id); current_case=self.ctx.get(db,'case',case_id)
                receipt=self.ctx.repo.get(db,'assistant_turn_receipt',key)
                require(receipt.get('token')==token and current['revision']==c['revision'] and signature(current_case)==snapshot,
                    409,'stale_assistant_input','偏好或对话已更新，请刷新后重新发送。')
                if intent['intent']=='living_services':
                    require(read_snapshot(self.ctx,db,case_id)['version']==living_snapshot['version'],
                        409,'living_context_changed','租后资料在处理期间已变化，请读取最新资料后重试。')
                if superseded:
                    previous=self.ctx.repo.get(db,'living_proposal',superseded)
                    if previous and previous['case_id']==case_id and previous['status']=='pending':
                        previous['status']='superseded'
                        self.ctx.repo.put(db,'living_proposal',superseded,previous)
                if next_living_focus:current['living_focus']=next_living_focus
                if proposal: self.ctx.repo.put(db,'assistant_proposal',proposal['proposal_id'],proposal)
                if intent['intent']=='collect_preferences' or proposal:
                    current['rental_brief']=profile_brief(profile) if proposal and intent['intent']=='update_preferences' else brief
                    current['dialogue_mode']='collect_preferences'
                elif intent['intent']=='search':
                    current['dialogue_mode']='search'
                    if brief: current['rental_brief']=brief
                if search_filters is not None: current['last_search_filters']=search_filters
                current['messages'].extend([message('user',body['message']),message('assistant',calls=safe_calls,**answer)])
                current['revision']+=1
                if current['title']=='新对话': current['title']=body['message'].strip()[:28]
                self.save(db,current)
                public=self.living_status(db,current)
                self.ctx.save_receipt(db,'assistant_turn_receipt',key,identity,public)
                return public
        except (ProviderError,ApiError) as exc:
            with self.ctx.repo.transaction() as db:
                receipt=self.ctx.repo.get(db,'assistant_turn_receipt',key)
                if receipt and receipt.get('token')==token:
                    receipt['status']='failed'; self.ctx.repo.put(db,'assistant_turn_receipt',key,receipt)
            if isinstance(exc,ProviderError):
                raise ApiError(503,exc.code,'AI 服务暂时不可用，请重试；已保存的对话保留。') from None
            raise

    def apply(self,case_id: str,proposal_id: str,body: dict):
        shape(body,('request_id','confirmed')); request_id(body['request_id']); opaque_ref(proposal_id)
        require(body['confirmed'] is True,422,'confirmation_required','请明确确认应用这项偏好。')
        self.catalog(); key=case_id+':'+body['request_id']; identity={'proposal_id':proposal_id,**body}
        with self.ctx.repo.transaction() as db,self.ctx.preferences.store.join(db):
            self.ctx.get(db,'case',case_id)
            p=self.ctx.get(db,'assistant_proposal',proposal_id)
            require(p['case_id']==case_id,404,'not_found','未找到这个偏好提案。')
            old=self.ctx.receipt(db,'assistant_apply_receipt',key,identity)
            if old: return old['result']
            c=self.get(db,case_id,p['conversation_id']); case=self.ctx.get(db,'case',case_id)
            require(p['status']=='proposed',409,'proposal_applied','此偏好提案已应用。')
            require(signature(case)==p['case_signature'] and c['revision']==p['conversation_revision'],409,'stale_proposal','偏好或对话已更新，请重新提出修改。')
            joined=copy(self.ctx); joined.repo=BorrowedRepository(self.ctx.repo,db)
            adapter=RealProfilesAdapter(joined)
            case=adapter.draft(case_id,{'expected_revision':case['draft']['revision'],'profile':p['profile']})
            case=adapter.confirm(case_id,{'draft_revision':case['draft']['revision'],'fingerprint':case['draft']['fingerprint'],'review_token':case['agent1']['review_token']})
            run=adapter.evaluation(case_id,{'request_id':'assistant-'+p['proposal_id'],'confirmation_version':case['confirmations'][-1]['version']})
            case=self.ctx.get(db,'case',case_id)
            cards=[self.catalog().get(r['listing_id']) for r in run['report']['recommendations']]
            c['messages'].append(message('assistant',f"Agent1 已确认偏好版本 {case['confirmations'][-1]['version']}，Agent2 找到 {run['report']['counts']['input']} 条广告候选。"+UNKNOWN,
                'agent2',intent='search',listings=cards,actions=[{'type':'navigate','label':'查看候选报告','page':'recommendations','run_id':run['run_id']}]))
            c['last_search_filters']=run['report']['filters']
            c['rental_brief']=profile_brief(p['profile'])
            c['dialogue_mode']='search'
            c['revision']+=1; self.save(db,c)
            p['status']='applied'; self.ctx.repo.put(db,'assistant_proposal',proposal_id,p)
            result={'case':case,'conversation':c}
            self.ctx.save_receipt(db,'assistant_apply_receipt',key,identity,result)
            return result
