"""Explicit cross-page actions from chat, composed with the existing business adapters."""
from copy import copy,deepcopy
from hashlib import sha256
from jsonschema import Draft202012Validator
from ..common import require,shape,integer,request_id,uid
from ..adapters.real_agent2 import RealProfilesAdapter
from .service import AssistantService,BorrowedRepository,signature,message
from .dialogue import BRIEF_SCHEMA,next_question,brief_profile_patch
from .intents import merge_profile
from .tools import preference_summary,known_listings


class AssistantWorkspace:
    def __init__(self,ctx):
        self.ctx=ctx
        self.assistant=AssistantService(ctx)

    def context(self,db,case_id,conversation_id,body):
        c=self.assistant.get(db,case_id,conversation_id)
        case=self.ctx.get(db,'case',case_id)
        require(len(c['messages'])<200,409,'message_limit','这个对话已满，请新建会话后继续。')
        require(integer(body['expected_revision']) and c['revision']==body['expected_revision'],
            409,'conversation_conflict','对话已更新，请重新读取需求后再同步。')
        require(isinstance(body['expected_profile_fingerprint'],str) and
            body['expected_profile_fingerprint']==case['draft']['fingerprint'],
            409,'stale_profile','租房需求已更新，请重新读取后再操作。')
        return c,case

    def prepare(self,case_id: str,conversation_id: str,body: dict):
        shape(body,('request_id','expected_revision','expected_profile_fingerprint','brief'))
        key=case_id+':'+request_id(body['request_id'])
        catalog=self.assistant.catalog()
        brief=body['brief']
        require(isinstance(brief,dict) and not list(Draft202012Validator(BRIEF_SCHEMA).iter_errors(brief)),
            422,'invalid_input','请核对区域、预算、人数和卧卫车位条件。')
        require(brief.get('suburb') is None or brief['suburb'] in catalog.suburbs,
            422,'invalid_input','请选择当前房源库中的区域。')
        question=next_question(brief)
        require(question is None,422,'incomplete_requirements',question or '请补全租房需求。')
        require('rental_mode' in brief,422,'incomplete_requirements','请选择整租、单间等租住方式。')
        with self.ctx.repo.transaction() as db:
            self.assistant.get(db,case_id,conversation_id)
            old=self.ctx.receipt(db,'assistant_prepare_receipt',key,{'conversation_id':conversation_id,**body})
            if old: return old['result']
            c,case=self.context(db,case_id,conversation_id,body)
            base_profile=case['draft']['profile']
            legacy=case.get('requirements_contract')!='supplied-only-v1'
            pending=next((a for a in c['messages'][-1]['actions'] if a['type']=='apply_preferences'),None) if c['messages'] else None
            if pending:
                previous=self.ctx.get(db,'assistant_proposal',pending['proposal_id'])
                require(previous['case_id']==case_id and previous['conversation_id']==conversation_id and
                    previous['status']=='proposed' and previous['conversation_revision']==c['revision'] and
                    previous['case_signature']==signature(case),409,'stale_proposal','对话中的需求已过期，请重新整理并确认。')
                base_profile=previous['profile']
                legacy=previous.get('requirements_contract')!='supplied-only-v1'
            patch=brief_profile_patch(brief)
            profile=merge_profile(base_profile,patch,legacy=legacy)
            if 'student_commute' in patch:profile['student_commute']=deepcopy(patch['student_commute'])
            else:profile.pop('student_commute',None)
            catalog.filters({k:v for k,v in profile.get('housing_preferences',{}).items() if k!='budget_match_mode'})
            p={'proposal_id':uid('proposal'),'case_id':case_id,'conversation_id':conversation_id,
                'case_signature':signature(case),'conversation_revision':c['revision']+1,
                'profile':profile,'status':'proposed','requirements_contract':'supplied-only-v1'}
            summary=preference_summary(profile)
            c['rental_brief']=deepcopy(brief)
            self.ctx.repo.put(db,'assistant_commute_activity',case_id,{'conversation_id':conversation_id,'brief':brief})
            c['dialogue_mode']='recommend_areas' if brief.get('recommend_areas') else 'collect_preferences'
            c['messages'].append(message('assistant','租房需求已整理好。核对并确认后，将同步到房源推荐。','agent1',
                intent='collect_preferences',actions=[{'type':'apply_preferences','label':'确认并同步需求',
                    'proposal_id':p['proposal_id'],'summary':summary}]))
            c['revision']+=1
            self.ctx.repo.put(db,'assistant_proposal',p['proposal_id'],p)
            self.assistant.save(db,c)
            result={'proposal_id':p['proposal_id'],'summary':summary,'conversation':c}
            self.ctx.save_receipt(db,'assistant_prepare_receipt',key,{'conversation_id':conversation_id,**body},result)
            return result

    def select(self,case_id: str,conversation_id: str,body: dict):
        shape(body,('request_id','expected_revision','expected_profile_fingerprint','listing_id','confirmed'),('allow_external_data',))
        key=case_id+':'+request_id(body['request_id'])
        require(body['confirmed'] is True,422,'selection_confirmation_required','请明确确认保存此候选。')
        require(isinstance(body['listing_id'],str),422,'invalid_reference','请选择已展示的房源。')
        self.assistant.catalog()
        if 'allow_external_data' in body:
            require(type(body['allow_external_data']) is bool,422,'invalid_input','外部路线查询选项无效。')
        with self.ctx.repo.transaction() as db, self.ctx.preferences.store.join(db):
            self.assistant.get(db,case_id,conversation_id)
            old=self.ctx.receipt(db,'assistant_select_receipt',key,{'conversation_id':conversation_id,**body})
            if old: return old['result']
            c,case=self.context(db,case_id,conversation_id,body)
            require(body['listing_id'] in known_listings(c),422,'invalid_reference','只能保存当前会话已展示的房源。')
            displayed=next(row for m in reversed(c['messages']) for row in m['listings'] if row['listing_id']==body['listing_id'])
            row=self.assistant.catalog().get(body['listing_id'])
            require(all(displayed.get(key)==row.get(key) for key in ('address','suburb','bedrooms','bathrooms','car_spaces','weekly_rent','source_url','captured_at')),
                409,'stale_listing','房源广告已更新，请重新查询后再确认保存。')
            confirmed=self.ctx.current(case)
            joined=copy(self.ctx); joined.repo=BorrowedRepository(self.ctx.repo,db)
            adapter=RealProfilesAdapter(joined)
            operation_id='chat-select-'+sha256(body['request_id'].encode()).hexdigest()
            run=adapter.evaluation(case_id,{'request_id':operation_id,
                'confirmation_version':confirmed['version']})
            adapter.select(case_id,{'request_id':operation_id,'run_id':run['run_id'],
                'listing_id':body['listing_id'],'confirmed':True})
            case=self.ctx.get(db,'case',case_id)
            row=self.assistant.catalog().get(body['listing_id'])
            c['messages'].append(message('assistant','已选定 '+row['address']+' 为当前跟进房源，可准备看房或进入合同流程。',
                'agent2',intent='select',actions=[{'type':'navigate','label':'查看当前跟进房源','page':'recommendations'}]))
            c['revision']+=1
            self.assistant.save(db,c)
            result={'case':case,'conversation':c}
            self.ctx.save_receipt(db,'assistant_select_receipt',key,{'conversation_id':conversation_id,**body},result)
            return result
