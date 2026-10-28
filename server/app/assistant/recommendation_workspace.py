"""Explicit, versioned edits to working search conditions, without AI or profile writes."""
from copy import deepcopy
from jsonschema import Draft202012Validator

from ..common import require, shape, integer, request_id, now
from ..commute.usyd import student_brief, DESTINATION
from .dialogue import BRIEF_SCHEMA
from .recommendation_options import FIELD_MAP, alternatives, filters_for, criteria_for, metadata
from .service import AssistantService, signature, message

PATCH_SCHEMA={'type':'object','minProperties':1,'additionalProperties':False,
              'properties':{k:BRIEF_SCHEMA['properties'][k] for k in FIELD_MAP}}
LABELS={'budget_amount':'周租上限','suburb':'区域','min_bedrooms':'卧室要求','min_bathrooms':'浴室要求',
        'min_car_spaces':'车位要求','commute_mode':'交通方式','commute_max_minutes':'通勤上限','max_transfers':'换乘上限'}


class RecommendationWorkspace:
    def __init__(self,ctx):self.ctx=ctx;self.assistant=AssistantService(ctx)

    filters=staticmethod(filters_for)

    def preview(self,case_id: str,body: dict):
        shape(body,('filters',))
        with self.ctx.repo.transaction() as db:self.ctx.get(db,'case',case_id)
        catalog=self.assistant.catalog();filters=catalog.filters(body['filters'])
        total=len(catalog.matching(filters))
        return {'filters':filters,'total':total,'alternatives':alternatives(catalog,filters,total),
                'catalog_fingerprint':catalog.fingerprint}

    def context(self,c):
        brief=deepcopy(c.get('rental_brief',{}))
        if c.get('dialogue_mode')=='search' and 'last_search_filters' in c:
            filters=self.assistant.catalog().filters(c['last_search_filters'])
            brief=criteria_for(filters,brief)
        else:filters=self.assistant.catalog().filters(filters_for(brief))
        return brief,filters

    def read(self,case_id: str,conversation_id: str):
        with self.ctx.repo.transaction() as db:
            c=self.assistant.get(db,case_id,conversation_id)
            if c.get('dialogue_mode') not in ('recommend_areas','search'):return None
            brief,filters=self.context(c);catalog=self.assistant.catalog()
            total=len(catalog.matching(filters))
            return {'criteria':criteria_for(filters,brief),'filters':filters,'total':total,
                    'alternatives':alternatives(catalog,filters,total),'catalog_fingerprint':catalog.fingerprint,
                    'revision':c['revision'],'suburbs':catalog.suburbs}

    def adjust(self,case_id: str,conversation_id: str,body: dict):
        shape(body,('request_id','expected_revision','expected_profile_fingerprint','catalog_fingerprint','confirmed','patch'))
        receipt_key=case_id+':'+request_id(body['request_id']);identity={'conversation_id':conversation_id,**body}
        require(body['confirmed'] is True,422,'confirmation_required','请明确应用此次筛选修改。')
        require(not list(Draft202012Validator(PATCH_SCHEMA).iter_errors(body['patch'])),422,'invalid_input','请核对本次预算、区域、房型或通勤修改。')
        catalog=self.assistant.catalog()
        with self.ctx.repo.transaction() as db:
            c=self.assistant.get(db,case_id,conversation_id);case=self.ctx.get(db,'case',case_id)
            old=self.ctx.receipt(db,'recommendation_adjust_receipt',receipt_key,identity)
            if old:return old['result']
            require(integer(body['expected_revision']) and body['expected_revision']==c['revision'],409,'conversation_conflict','找房条件已变化，请读取最新会话再修改。')
            require(body['expected_profile_fingerprint']==case['draft']['fingerprint'],409,'stale_profile','租房需求已更新，请读取最新会话再修改。')
            require(body['catalog_fingerprint']==catalog.fingerprint,409,'stale_catalog','房源目录已更新，请读取最新筛选结果。')
            require(len(c['messages'])<199,409,'message_limit','这个对话已满，请新建会话。')
            require(c.get('dialogue_mode') in ('search','recommend_areas'),409,'requirements_not_ready','请先提供找房条件并生成一次推荐。')
            before,filters=self.context(c);previous_count=len(catalog.matching(filters))
            patch=body['patch'];brief={**before,**deepcopy(patch)}
            for key,value in patch.items():
                # Personal/room budgets are not silently multiplied or treated as whole-ad rent.
                if key=='budget_amount' and 'max_weekly_rent' not in filters and not (brief.get('budget_scope')=='whole_property' and brief.get('budget_period')=='week'):continue
                if value is None:filters.pop(FIELD_MAP[key],None)
                else:filters[FIELD_MAP[key]]=value
            filters=catalog.filters(filters)
            require(not ('usyd_max_minutes' in filters) or filters.get('usyd_mode'),422,'invalid_input','请同时选择交通方式和通勤上限。')
            if filters.get('usyd_max_minutes'):
                from ..commute.cached_plan import reference_answer
                from .recommendation_order import arrange
                brief=student_brief({**criteria_for(filters,brief),'recommend_areas':True})
                answer=arrange(reference_answer(catalog,brief,DESTINATION),c,brief)
                c['dialogue_mode']='recommend_areas'
            else:
                from .tools import search_answer
                answer=search_answer(catalog,filters);answer.pop('_search_filters',None)
                c['dialogue_mode']='search'
            changes=[{'field':key,'label':LABELS[key],'before':before.get(key),'after':brief.get(key)}
                     for key in patch if before.get(key)!=brief.get(key)]
            require(changes,422,'no_change','这些条件尚未变化。')
            answer.update(metadata(catalog,filters,brief,len(answer['listings'])))
            answer['recommendation_change']={'before_count':previous_count,'after_count':len(answer['listings']),'changes':changes}
            labels='、'.join(item['label'] for item in changes)
            answer['content']=f'已调整{labels}，其他条件保持不变。符合条件的房源从 {previous_count} 套变为 {len(answer["listings"])} 套。'
            c['rental_brief']=brief;c['last_search_filters']=filters
            c['messages'].extend([message('user',f'调整本次找房条件：{labels}。'),message('assistant',**answer)])
            c['revision']+=1
            self.ctx.repo.put(db,'assistant_commute_activity',case_id,{'conversation_id':conversation_id,'brief':brief})
            if answer.get('commute_recommendation'):
                self.ctx.repo.put(db,'assistant_commute_report',case_id,{'conversation_id':conversation_id,
                    'conversation_revision':c['revision'],'case_signature':signature(case),'catalog_fingerprint':catalog.fingerprint,
                    'brief':brief,'created_at':now(),'message':c['messages'][-1]})
            self.assistant.save(db,c)
            result=self.assistant.living_status(db,c)
            self.ctx.save_receipt(db,'recommendation_adjust_receipt',receipt_key,identity,result)
            return result
