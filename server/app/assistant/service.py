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
from ..real_data.profile import supplied_profile
from .tools import execute,known_listings,CLARIFY,preference_summary,listing_context,history_context,search_answer
from .dialogue import BRIEF_SCHEMA,merge_brief,brief_summary,next_question,brief_filters,brief_profile_patch,profile_brief
from .living import read_snapshot, model_context, answer_living
from ..living.service import LivingService
from .repair_dialogue import repair_focus, focus_context
from .lease_bridge import LeaseChatBridge
from . import commute
from . import areas
from . import progress
from .preferences_progress import guard_monthly
from .soft_preferences import merge_explicit_priorities,rank_answer
from ..rag.scope import is_product_question


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
        require(self.ctx.settings.catalog is not None,503,'real_catalog_unavailable','The live listing catalogue is unavailable.')
        return self.ctx.settings.catalog

    def get(self,db,case_id,conversation_id):
        self.ctx.get(db,'case',case_id)
        value=self.ctx.get(db,'assistant_conversation',conversation_id)
        require(value['case_id']==case_id,404,'not_found','Conversation not found.')
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
            require(len(index)<100,409,'conversation_limit','This case can contain at most 100 conversations.')
            c={'conversation_id':uid('chat'),'case_id':case_id,'title':'New conversation','revision':0,'messages':[]}
            self.save(db,c); return c

    def read(self,case_id: str,conversation_id: str):
        with self.ctx.repo.transaction() as db:
            return self.living_status(db,self.get(db,case_id,conversation_id))

    def living_status(self,db,conversation):
        result=deepcopy(conversation)
        for entry in result['messages']:
            self.ctx.contract_knowledge.decorate_entry(db,entry)
            for action in entry.get('actions',[]):
                if action.get('type')=='apply_living_services':
                    proposal=self.ctx.repo.get(db,'living_proposal',action.get('proposal_id',''))
                    if proposal and proposal['case_id']==result['case_id']:
                        if proposal['status']=='applied':action['applied']=True
                        elif proposal['status']=='superseded':action['superseded']=True
        return LeaseChatBridge(self.ctx).hydrate(db,result)

    def send(self,case_id: str,conversation_id: str,body: dict):
        shape(body,('request_id','expected_revision','message','allow_external_ai'),('listing_ids','allow_external_data'))
        request_id(body['request_id'])
        require(body['allow_external_ai'] is True,422,'ai_consent_required','Explicit consent is required to use external AI for this request.')
        require(type(body.get('allow_external_data',False)) is bool,422,'invalid_input','Location and transit lookup consent must be a boolean.')
        require(integer(body['expected_revision']),422,'invalid_input','Provide the current conversation version.')
        require(isinstance(body['message'],str) and 0<len(body['message'].strip())<=3000,422,'invalid_input','Messages must contain 1 to 3000 characters.')
        requested=body.get('listing_ids',[])
        require(isinstance(requested,list) and len(requested)<=5 and all(isinstance(i,str) for i in requested) and len(requested)==len(set(requested)),422,'invalid_reference','Select at most 5 displayed listings.')
        catalog=self.catalog(); key=case_id+':'+body['request_id']; identity={'conversation_id':conversation_id,**body}
        token=uid('attempt')
        with self.ctx.repo.transaction() as db:
            c=self.get(db,case_id,conversation_id); case=self.ctx.get(db,'case',case_id)
            old=self.ctx.receipt(db,'assistant_turn_receipt',key,identity)
            if old and 'result' in old: return self.living_status(db,old['result'])
            require(not old or old.get('status')!='pending' or time()-old['started_at']>60,409,'request_in_progress','This message is being processed. Please retry shortly.')
            require(c['revision']==body['expected_revision'],409,'conversation_conflict','The conversation changed. Refresh and retry.')
            require(len(c['messages'])<200,409,'message_limit','This conversation is full. Start a new conversation.')
            known=known_listings(c)
            require(set(requested)<=set(known),422,'invalid_reference','Only listings displayed in this conversation can be referenced.')
            preview=known_listings(c,preview=True)
            cards_context=listing_context(catalog,[i for i in preview if i not in requested]+requested)
            ids=[row['listing_id'] for row in cards_context]
            require(set(requested)<=set(ids),422,'invalid_reference','Only listings displayed in this conversation can be referenced.')
            public_snapshot=self.living_status(db,c)
            latest_proposal=next((entry.get('lease_proposal') for entry in reversed(public_snapshot['messages']) if entry.get('lease_proposal')),None)
            lease_pending_summary=({'missing_fields':[q['field'] for q in latest_proposal['questions']]} if latest_proposal and latest_proposal['status']=='pending' else None)
            snapshot=signature(case)
            living_snapshot=read_snapshot(self.ctx,db,case_id)
            self.ctx.repo.put(db,'assistant_turn_receipt',key,{'input':identity,'token':token,'started_at':time(),'status':'pending'})
        # The complete external call runs with no SQLite transaction held.
        living_focus=repair_focus(self.ctx,case_id,c,living_snapshot)
        context={'task':'assistant_intent','response_schema':response_schema(),'message':body['message'],
            'history':history_context(public_snapshot,ids),
            'draft_profile':supplied_profile(case['draft']['profile'],case.get('requirements_contract')!='supplied-only-v1'),
            'confirmed_profile':supplied_profile(case['confirmations'][-1]['profile'],case.get('requirements_contract')!='supplied-only-v1') if (case['confirmations'] and case['confirmations'][-1]['draft_revision']==case['draft']['revision'] and case['confirmations'][-1]['fingerprint']==case['draft']['fingerprint'] and case['agent1']['state']=='Confirmed') else None,
            'displayed_listing_ids':ids,'displayed_listings':cards_context,'selected_listing_ids':requested,
            'rental_brief':c.get('rental_brief',{}),'dialogue_mode':c.get('dialogue_mode'),
            'commute':commute.brief_context(c),
            'pending_question':progress.pending_question(c),
            'area_knowledge':areas.model_context(),
            'compared_areas':c.get('area_names',[]),
            'saved_candidate':({'listing_id':case['selection']['listing_id'],
                'address':case['selection']['listing_snapshot'].get('address'),
                'profile_version':case['selection']['profile_version']} if case.get('selection') else None),
            'brief_reconstruction_required':'rental_brief' not in c and bool(c['messages']),
            'last_search_filters':c.get('last_search_filters',{}),
            'catalog':{'suburbs':catalog.suburbs,'fingerprint':catalog.fingerprint},
            'lease_draft':None,
            'living_services':model_context(living_snapshot,LivingService(self.ctx).directory(),focus_context(living_focus)),
            'unknowns':['rent_scope','bills','availability','actual_door_to_class_duration','move_in_date']}
        try:
            context['lease_draft']=LeaseChatBridge(self.ctx).context(case_id)
            if lease_pending_summary: context['lease_draft']['pending_proposal']=lease_pending_summary
            calls=[]
            explicit={'intent':'knowledge'} if is_product_question(body['message']) else progress.explicit_transition(c,body['message'])
            with self.ctx.repo.transaction() as db:
                routing_snapshot=self.living_status(db,c)
            routing=self.ctx.decision_router.prepare(body['message'],routing_snapshot,token,explicit=explicit,
                pending=progress.pending_question(c),lease_pending=bool(lease_pending_summary),
                repair_active=bool(living_focus.get('repair_id') or living_focus.get('pending')))
            full_context=context
            if routing['allowed_intents']:
                context={**context,'routing_domain':routing['route'],'response_schema':{
                    'oneOf':[variant for variant in context['response_schema']['oneOf']
                             if variant['properties']['intent']['const'] in routing['allowed_intents']]}}
            uncertain_region=None
            if routing['direct_intent'] is not None:
                intent=validate_intent(routing['direct_intent'],catalog,ids)
            for attempt in range(0 if routing['direct_intent'] is not None else 2):
                try:
                    with self.ctx.repo.transaction() as db:
                        context['history']=history_context(self.living_status(db,c),ids)
                        full_context['history']=context['history']
                    output,call=self.ctx.ai_provider.call(context)
                    calls.append(call)
                    uncertain_region,output=progress.partial_region(body['message'],output,catalog) if not explicit else (None,explicit)
                    intent=validate_intent(output,catalog,ids)
                    require(not routing['allowed_intents'] or intent['intent'] in routing['allowed_intents'],
                            502,'ai_invalid_response','The extracted fields do not match the routing decision. Reassess the complete intent.')
                    break
                except (ApiError,ProviderError) as error:
                    if isinstance(error,ProviderError):calls.append(error.call)
                    if error.code!='ai_invalid_response' or attempt:raise
                    if routing['allowed_intents']:
                        routing.update(source='ali',reason='extraction_disagreed',allowed_intents=None)
                    context={**full_context,'validation_feedback':'The previous response did not match response_schema. Reconsider the request using the full schema. Return one strict JSON object using only the exact fields and enum values of its chosen intent. No markdown, prose, or extra fields.'}
            intent,recovery_calls=progress.repair_route(self.ctx,c,body['message'],intent,catalog) if not uncertain_region and not is_product_question(body['message']) else (intent,[])
            calls.extend(recovery_calls)
            intent=guard_monthly(c,body['message'],intent)
            self.ctx.decision_router.observe(routing['audit_id'],intent,routing)
            if intent['intent']=='collect_preferences' and c.get('dialogue_mode')=='recommend_areas':
                intent['intent']='recommend_areas'
            proposal=None
            lease_pending=None
            commute_options=None
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
                require(recovered['intent']=='collect_preferences',502,'ai_invalid_response','Previous requirements could not be extracted. Please retry.')
                memory={**c,'rental_brief':recovered.get('brief_patch',{})}
            brief=merge_explicit_priorities(merge_brief(memory,intent),body['message'])
            if intent['intent']=='collect_preferences' and (brief.get('commute_mode') or brief.get('commute_max_minutes')):
                intent['intent']='recommend_areas'
            question=next_question(brief) if intent['intent']=='collect_preferences' else None
            if uncertain_region:
                answer={'intent':'collect_preferences','agent':'agent1','listings':[],'actions':[],
                        'content':f'Which suburb does {uncertain_region} refer to? Please provide its full English name. Your budget and property requirements are retained until you clarify the suburb.'}
            elif intent['intent']=='contract':
                answer=self.ctx.contract_knowledge.chat_answer(case_id,body['message'])
            elif intent['intent']=='knowledge':
                report=self.ctx.knowledge.answer(body['message'],True,'en')
                answer={'intent':'knowledge','agent':'assistant','content':report['answer'],'knowledge':report,'listings':[],'actions':[]}
            elif intent['intent']=='area_advice':
                names=intent.get('areas')
                if names is None and 'suburb' not in intent.get('brief_patch',{}):names=c.get('area_names')
                answer=areas.answer_areas(catalog,brief,names,intent.get('focus','balanced'))
            elif intent['intent']=='recommend_areas':
                answer,commute_options=commute.prepare(self.ctx,c,brief,intent.get('brief_patch',{}),body['message'],body.get('allow_external_data',False),
                    refresh=intent.get('refresh_recommendations',False))
            elif intent['intent']=='collect_preferences' and question:
                summary=brief_summary(brief)
                answer={'intent':'collect_preferences','agent':'agent1',
                    'content':('Noted: '+summary+'.\n' if summary else '')+question,'listings':[],'actions':[]}
            elif intent['intent'] in ('update_preferences','collect_preferences'):
                patch=brief_profile_patch(brief) if intent['intent']=='collect_preferences' else intent.get('preference_patch',{})
                try:
                    require(bool(patch),422,'empty_patch','Please add your preferences.')
                    profile=merge_profile(case['draft']['profile'],patch,legacy=case.get('requirements_contract')!='supplied-only-v1')
                    housing=profile.get('housing_preferences',{})
                    catalog.filters({k:v for k,v in housing.items() if k!='budget_match_mode'})
                except (ApiError,ValueError):
                    answer={'intent':'clarify','agent':'agent1','content':CLARIFY,'listings':[],'actions':[]}
                else:
                    proposal={'proposal_id':uid('proposal'),'case_id':case_id,'conversation_id':conversation_id,
                        'case_signature':snapshot,'conversation_revision':c['revision']+1,'profile':profile,'status':'proposed',
                        'requirements_contract':'supplied-only-v1'}
                    answer={'intent':'update_preferences','agent':'agent1',
                        'content':'Your updated rental requirements are ready. Review the summary below, then confirm to save preferences and generate candidates.',
                        'listings':[],'actions':[{'type':'apply_preferences','label':'Confirm preferences and generate candidates','proposal_id':proposal['proposal_id'],'summary':preference_summary(profile)}]}
                    if intent['intent']=='collect_preferences':
                        preview=search_answer(catalog,brief_filters(brief),ctx=self.ctx,case_id=case_id)
                        preview['actions'].extend(answer['actions'])
                        answer={**preview,'intent':'collect_preferences','agent':'agent1',
                            'content':'Requirements noted: '+brief_summary(brief)+'.\n'+preview['content']+'\nConfirm the requirements below to save your rental preferences.'}
            elif intent['intent']=='draft_contract':
                prepared=LeaseChatBridge(self.ctx).prepare(case_id,c,body['message'])
                answer=prepared['answer']; lease_pending=prepared['pending']
                if prepared.get('call'): calls.append(prepared['call'])
            elif intent['intent']=='living_services':
                answer=answer_living(self.ctx,intent,case_id,c,body['message'],living_snapshot['version'],living_focus)
            elif intent['intent']=='transit_info':
                from .transit_info import answer as transit_answer
                answer=transit_answer(self.ctx,intent,case,c,requested,body.get('allow_external_data',False))
            else: answer=execute(intent,case,c,catalog,requested,ctx=self.ctx)
            answer=rank_answer(answer,brief,catalog)
            search_filters=answer.pop('_search_filters',None)
            repair_call=answer.pop('_repair_call',None)
            if repair_call:calls.append(repair_call)
            area_names=answer.pop('_area_names',None)
            next_living_focus=answer.pop('_living_focus',None)
            superseded=answer.pop('_supersede_living_proposal',None)
            if answer['intent']=='clarify' and intent.get('clarification_reason')!='multiple_tasks' and (intent.get('clarification_reason')=='unknown_fact' or any(word in body['message'].casefold() for word in ('安静','噪音','噪声','隔音','noise','quiet','soundproof','通勤','commute','账单','bills','在租','available'))):
                from .comparison import verification_checklist
                answer['content']='Verified noise, soundproofing, commute, bills and availability data are currently unavailable. The checklist provides questions for the agent and inspection; you can also compare known bedrooms, bathrooms, parking and weekly rent.'
                answer['verification_checklist']=verification_checklist()
            if answer['intent'] in ('other','clarify') and intent.get('clarification_reason')!='multiple_tasks' and any(word in body['message'].casefold() for word in ('不满意','都不行','不喜欢','都不好','not satisfied','don\'t like')):
                answer['content']='What makes these listings unsuitable: advertised weekly rent, location, bedrooms and bathrooms, or living conditions that need checking? Choose a suggestion below to continue previewing.'
                answer['actions']=[{'type':'suggestion','label':'Preview cheaper listings','message':'Preview listings with lower advertised weekly rent using the previous suburb and bedroom and bathroom requirements. Keep saved preferences unchanged.'},
                    {'type':'suggestion','label':'Check noise and bills','message':'Prepare questions to verify noise, soundproofing and bills for these listings.'}]
            safe_calls=[{k:v for k,v in entry.items() if k in {'task','provider','model','status','attempted','duration_ms','started_at','usage','error_code','simulated'}} for entry in calls]
            with self.ctx.repo.transaction() as db:
                current=self.get(db,case_id,conversation_id); current_case=self.ctx.get(db,'case',case_id)
                receipt=self.ctx.repo.get(db,'assistant_turn_receipt',key)
                require(receipt.get('token')==token and current['revision']==c['revision'] and signature(current_case)==snapshot,
                    409,'stale_assistant_input','Preferences or the conversation changed. Refresh and resend.')
                if intent['intent']=='living_services':
                    require(read_snapshot(self.ctx,db,case_id)['version']==living_snapshot['version'],
                        409,'living_context_changed','Aftercare details changed while processing. Reload the latest details and retry.')
                if superseded:
                    previous=self.ctx.repo.get(db,'living_proposal',superseded)
                    if previous and previous['case_id']==case_id and previous['status']=='pending':
                        previous['status']='superseded'
                        self.ctx.repo.put(db,'living_proposal',superseded,previous)
                if next_living_focus:current['living_focus']=next_living_focus
                if proposal: self.ctx.repo.put(db,'assistant_proposal',proposal['proposal_id'],proposal)
                LeaseChatBridge(self.ctx).persist(db,lease_pending)
                if intent['intent']=='area_advice':
                    current['rental_brief']=brief
                    current['area_names']=area_names
                    current['dialogue_mode']='recommend_areas' if brief.get('recommend_areas') else 'area_advice'
                    self.ctx.repo.put(db,'assistant_commute_activity',case_id,{'conversation_id':conversation_id,'brief':brief})
                elif intent['intent']=='recommend_areas':
                    current['rental_brief']=brief
                    current['dialogue_mode']='recommend_areas'
                    current['commute_destination_options']=commute_options or []
                    self.ctx.repo.put(db,'assistant_commute_activity',case_id,{'conversation_id':conversation_id,'brief':brief})
                elif intent['intent']=='collect_preferences' or proposal:
                    if proposal and intent['intent']=='update_preferences' and current.get('rental_brief',{}).get('recommend_areas'):
                        # A pending explicit saved-field edit must not discard
                        # the independent commute brief or replace its other
                        # user values with the sample/saved profile defaults.
                        changed=intent.get('preference_patch',{})
                        kept=deepcopy(current['rental_brief'])
                        budget=changed.get('budget',{})
                        if 'maximum' in budget:kept['budget_amount']=budget['maximum'];kept['budget_period']='week'
                        if 'scope' in budget:kept['budget_scope']=budget['scope']
                        for field in ('occupants','rental_mode'):
                            if field in changed:kept[field]=changed[field]
                        kept.update({k:v for k,v in changed.get('housing_preferences',{}).items() if k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces')})
                        if changed.get('student_commute'):
                            student=profile['student_commute']
                            kept.update(commute_mode=student['mode'],commute_max_minutes=student['maximum_minutes'],commute_hard_limit=True)
                        current['rental_brief']=kept
                        current['dialogue_mode']='recommend_areas'
                    else:
                        current['rental_brief']=({**{k:v for k,v in brief.items() if k=='lifestyle_priorities'},**profile_brief(profile)}
                                                if proposal and intent['intent']=='update_preferences' else brief)
                        current['dialogue_mode']='collect_preferences'
                elif intent['intent']=='search':
                    current['dialogue_mode']='search'
                    if brief: current['rental_brief']=brief
                if search_filters is not None:
                    current['last_search_filters']=search_filters
                    if intent['intent']=='workflow': current['dialogue_mode']='search'
                if current.get('rental_brief')!=c.get('rental_brief'):
                    # Intake, preview edits and area questions share one active
                    # requirement context, including across conversations.
                    self.ctx.repo.put(db,'assistant_commute_activity',case_id,{
                        'conversation_id':conversation_id,'brief':current.get('rental_brief',{})})
                route_summary={key:routing[key] for key in ('mode','source','route','reason')}
                outgoing=message('assistant',calls=safe_calls,routing=route_summary,**answer)
                self.ctx.contract_knowledge.decorate_entry(db,outgoing)
                current['messages'].extend([message('user',body['message']),outgoing])
                current['revision']+=1
                if answer.get('commute_recommendation'):
                    self.ctx.repo.put(db,'assistant_commute_report',case_id,{
                        'conversation_id':conversation_id,'conversation_revision':current['revision'],
                        'case_signature':snapshot,'catalog_fingerprint':catalog.fingerprint,'brief':brief,
                        'created_at':now(),'message':current['messages'][-1]})
                if answer.get('area_advice'):
                    self.ctx.repo.put(db,'assistant_area_report',case_id,{
                        'conversation_id':conversation_id,'brief':brief,'case_signature':snapshot,
                        'catalog_fingerprint':catalog.fingerprint,'area_knowledge_fingerprint':answer['area_advice']['fingerprint'],
                        'created_at':now(),'message':current['messages'][-1]})
                if current['title']=='New conversation': current['title']=body['message'].strip()[:28]
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
                raise ApiError(503,exc.code,'AI is temporarily unavailable. Please retry; your saved conversation is retained.') from None
            raise

    def apply(self,case_id: str,proposal_id: str,body: dict):
        shape(body,('request_id','confirmed')); request_id(body['request_id']); opaque_ref(proposal_id)
        require(body['confirmed'] is True,422,'confirmation_required','Explicitly confirm applying these preferences.')
        self.catalog(); key=case_id+':'+body['request_id']; identity={'proposal_id':proposal_id,**body}
        with self.ctx.repo.transaction() as db,self.ctx.preferences.store.join(db):
            self.ctx.get(db,'case',case_id)
            p=self.ctx.get(db,'assistant_proposal',proposal_id)
            require(p['case_id']==case_id,404,'not_found','Preference proposal not found.')
            old=self.ctx.receipt(db,'assistant_apply_receipt',key,identity)
            if old: return old['result']
            c=self.get(db,case_id,p['conversation_id']); case=self.ctx.get(db,'case',case_id)
            require(p['status']=='proposed',409,'proposal_applied','This preference proposal has already been applied.')
            require(p.get('requirements_contract')=='supplied-only-v1',409,'stale_proposal',
                    'This older summary contains demo defaults. Review and sync it again in My rental requirements.')
            require(signature(case)==p['case_signature'] and c['revision']==p['conversation_revision'],409,'stale_proposal','Preferences or the conversation changed. Submit the changes again.')
            joined=copy(self.ctx); joined.repo=BorrowedRepository(self.ctx.repo,db)
            adapter=RealProfilesAdapter(joined)
            case=adapter.draft(case_id,{'expected_revision':case['draft']['revision'],'profile':p['profile']})
            case=adapter.confirm(case_id,{'draft_revision':case['draft']['revision'],'fingerprint':case['draft']['fingerprint'],'review_token':case['agent1']['review_token']})
            run=adapter.evaluation(case_id,{'request_id':'assistant-'+p['proposal_id'],'confirmation_version':case['confirmations'][-1]['version']})
            case=self.ctx.get(db,'case',case_id)
            cards=deepcopy(run['report']['pending_confirmation'])
            previous = next((m for m in reversed(c['messages']) if m.get('listings') or m.get('commute_recommendation')), None)
            from .recommendation_options import filters_for
            previous_filters = previous.get('recommendation_filters') if previous else None
            if previous and previous.get('commute_recommendation'):
                previous_filters = filters_for(previous['commute_recommendation']['criteria'])
            if previous_filters is None: previous_filters = c.get('last_search_filters', {})
            def effective(filters): return {k:v for k,v in filters.items() if k != 'sort' and v is not None}
            fields = ('listing_id', 'address', 'weekly_rent', 'bedrooms', 'bathrooms', 'car_spaces', 'captured_at')
            def facts(rows): return {r['listing_id']: tuple(r.get(k) for k in fields) for r in rows}
            if previous is None or effective(previous_filters) != effective(run['report']['filters']) or facts(previous['listings']) != facts(cards):
                c['messages'].append(message('assistant',f"Rental requirements saved; found {len(cards)} matching listings.",
                    'agent2',intent='search',listings=cards))
            for item in c['messages']:
                for action in item['actions']:
                    if action['type'] == 'apply_preferences': action['applied'] = True
            c['last_search_filters']=run['report']['filters']
            if c.get('rental_brief',{}).get('recommend_areas'):
                c['rental_brief']={**c['rental_brief'],**profile_brief(p['profile'])}
                c['dialogue_mode']='recommend_areas'
            else:
                c['rental_brief']={**{k:v for k,v in c.get('rental_brief',{}).items() if k=='lifestyle_priorities'},**profile_brief(p['profile'])}
                c['dialogue_mode']='search'
            c['revision']+=1; self.save(db,c)
            p['status']='applied'; self.ctx.repo.put(db,'assistant_proposal',proposal_id,p)
            result={'case':case,'conversation':c}
            self.ctx.save_receipt(db,'assistant_apply_receipt',key,identity,result)
            return result
