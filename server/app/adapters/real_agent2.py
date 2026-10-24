"""Agent2 provisional real-advertisement evaluation and immutable candidate selection."""
from copy import deepcopy
import hashlib
from fastapi.responses import Response
from ..common import ApiError
from ..real_data.preferences import preference_context, POLICY
from .profiles import ProfilesAdapter
from ..common import now, require, shape, integer, opaque_ref, request_id
from ..repository import canonical


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class RealProfilesAdapter(ProfilesAdapter):
    def recommendation_context(self, case_id: str):
        with self.ctx.repo.transaction() as db:
            case = self.ctx.get(db, 'case', case_id)
            try:
                confirmed = self.ctx.current(case)
            except ApiError as exc:
                if exc.code != 'unconfirmed_profile':
                    raise
                return {'profile_version':None, 'filters':{'sort':'rent_asc'},
                        'unverified_preferences':[], 'mapping_policy':POLICY}
            return {**preference_context(confirmed['profile'],self.ctx.settings.catalog),
                    'profile_version':confirmed['version'], 'profile_fingerprint':confirmed['fingerprint']}

    def draft(self, case_id: str, body: dict):
        # Reject unsupported suburbs before Agent1 persists a confirmed-search condition.
        if isinstance(body.get('profile'),dict):
            housing = body['profile'].get('housing_preferences')
            if isinstance(housing,dict):
                self.ctx.settings.catalog.filters({k:v for k,v in housing.items() if k != 'budget_match_mode'})
        return super().draft(case_id,body)

    def evaluation(self, case_id: str, body: dict):
        shape(body, ('request_id', 'confirmation_version'), ('filters',))
        require(integer(body['confirmation_version']) and body['confirmation_version'] > 0, 422, 'invalid_input', '请提供当前确认版本。')
        key = case_id + ':' + request_id(body['request_id'])
        catalog = self.ctx.settings.catalog
        with self.ctx.repo.transaction() as db:
            case = self.ctx.get(db, 'case', case_id)
            confirmed = self.ctx.current(case, body['confirmation_version'])
            old = self.ctx.receipt(db, 'real_evaluation_receipt', key, body)
            if old: return old['result']
            profile = deepcopy(confirmed['profile'])
            context = preference_context(profile,catalog)
            filters = catalog.filters(body['filters']) if 'filters' in body else context['filters']
            filter_source = 'manual' if 'filters' in body else 'confirmed_profile'
            listings = catalog.matching(filters)
            pending = []
            for item in listings:
                pending.append({**item, 'status':'pending', 'rank':None, 'score':None, 'weekly_cost':None,
                    'score_breakdown':{'cost':None,'commute':None,'housing':None,'amenities':None},
                    'issues':['是否仍在租、租金计价对象、账单、起租窗口与租期尚待核实。'],
                    'reasons':[f"广告标价 AUD {item['weekly_rent']:g}/周；{item['bedroom_label']}卧 {item['bathrooms']:g}卫 {item['car_spaces']:g}车位。"],
                    'hard_checks':{'availability':{'status':'unknown','reason':'公开广告未经房东确认仍在租。'}},
                    'evidence_refs':{field:{'source_ref':item['source_url'],
                        'observed_at':item['captured_at'], 'source_name':'Domain 公开广告索引'}
                        for field in ('bedrooms','bathrooms','car_spaces','weekly_rent')}})
                if item['bedroom_count_basis'] == 'open_plan_as_one':
                    pending[-1]['evidence_refs']['bedrooms'].update(source_value=item['advertised_bedrooms'],
                        interpreted_value=1, interpretation='项目口径：0卧开放式房源按1个起居睡眠空间计算，非独立卧室。')
            run_id = 'real-' + digest({'profile':profile,'dataset':catalog.fingerprint,'filters':filters,'mapping_policy':POLICY,'filter_source':filter_source})
            report = {'schema_version':'real-1.0','scoring_version':'real-facts-1.0','data_mode':'real_listings',
                'recommendation_run_id':run_id,'search_id':case['search_id'],'profile':profile,
                'profile_version':confirmed['version'],'profile_fingerprint':confirmed['fingerprint'],
                'dataset_fingerprint':catalog.fingerprint,'as_of':catalog.as_of, 'evaluated_at':now(),
                'report_status':'provisional','filters':filters,'catalog':catalog.metadata(),
                'mapping_policy':POLICY,'filter_source':filter_source,'profile_filters':context['filters'],
                'unverified_preferences':context['unverified_preferences'],
                'counts':{'input':len(listings),'eligible':0,'pending':len(listings),'excluded':0,'duplicates':0},
                'recommendations':pending[:5],'eligible':[],'pending_confirmation':pending,'excluded':[],
                'duplicates':[],'effective_weights':{},'clarification_requests':['房源为待核实候选，广告标价不等于可比总费用。'],
                'data_limitations':['使用采集的真实公开广告快照，未连接实时在租数据。',
                    '卧室、浴室、车位和广告周租有来源；通勤、设施距离、计价对象等未知信息没有补造。',
                    '筛选与排序仅依据广告字段；未执行完整资格认定或四维总分。']}
            report['data_limitations'].append('原广告0卧的开放式房源按项目口径计为1个睡眠空间；保留原始卧室数，不表示独立卧室。')
            result = {'run_id':run_id,'report':report,'comparison':None,'comparison_source':'real_catalog'}
            # Reusing a deterministic run preserves its original immutable evaluation time.
            saved = self.ctx.repo.get(db,'evaluation',run_id)
            if saved:
                require(saved['case_id']==case_id,409,'evaluation_conflict','报告标识冲突。')
                result = saved['response']
            else:
                self.ctx.repo.put(db,'evaluation',run_id,{'case_id':case_id,'response':result,
                    'dataset':{'data_mode':'real_listings','as_of':catalog.as_of,'listings':listings},'profile':profile})
            if not case['evaluations'] or case['evaluations'][-1]['run_id'] != run_id:
                case['evaluations'].append({'run_id':run_id,'profile_version':confirmed['version'],'created_at':now(),'data_mode':'real_listings'})
            self.ctx.repo.put(db,'case',case_id,case)
            self.ctx.save_receipt(db,'real_evaluation_receipt',key,body,result)
            return result

    def select(self, case_id: str, body: dict):
        shape(body, ('request_id','run_id','listing_id','confirmed'))
        opaque_ref(body['run_id']); opaque_ref(body['listing_id'])
        key = case_id + ':' + request_id(body['request_id'])
        with self.ctx.repo.transaction() as db:
            case = self.ctx.get(db,'case',case_id)
            confirmed = self.ctx.current(case)
            run = self.ctx.get(db,'evaluation',body['run_id'])
            require(run['case_id']==case_id and run['profile']==confirmed['profile'],409,'stale_evaluation','请按当前确认偏好重新生成候选。')
            require(run['response']['report'].get('data_mode')=='real_listings',409,'legacy_evaluation','模拟报告仅供历史查看，请重新评估真实房源。')
            require(run['response']['report']['dataset_fingerprint']==self.ctx.settings.catalog.fingerprint,
                    409,'stale_catalog','房源库已更新，请重新生成真实候选。')
            require(run['response']['report'].get('mapping_policy')==POLICY,409,'stale_evaluation','推荐规则已更新，请按当前偏好重新生成候选。')
            require(body['confirmed'] is True,422,'selection_confirmation_required','请明确确认保存此候选。')
            old = self.ctx.receipt(db,'real_selection_receipt',key,body)
            if old: return old['result']
            listing = next((r for r in run['dataset']['listings'] if r['listing_id']==body['listing_id']),None)
            require(listing is not None,409,'listing_not_in_run','只能选择本次真实筛选结果内的房源。')
            selection = {'schema_version':'real-1.0','data_mode':'real_listings','listing_id':body['listing_id'],
                'profile_version':confirmed['version'],'profile_fingerprint':confirmed['fingerprint'],
                'selected_at':now(),'recommendation_run_id':body['run_id'],
                'dataset_fingerprint':run['response']['report']['dataset_fingerprint'],
                'listing_snapshot':deepcopy(listing),'requires_verification':True,'contract_ready':False,
                'selection_status':'candidate_selected','user_confirmed':True}
            case['selection'] = selection
            self.ctx.repo.put(db,'case',case_id,case)
            self.ctx.save_receipt(db,'real_selection_receipt',key,body,selection)
            return selection

    def export_evaluation(self, run_id: str, format: str = 'json'):
        report = self.read_evaluation(run_id)['report']
        if report.get('data_mode') != 'real_listings': return super().export_evaluation(run_id, format)
        require(format in ('json','markdown'),422,'invalid_format','请选择 json 或 markdown。')
        if format == 'json': return self.ctx.download(report,'real-evaluation')
        lines = ['# 真实房源候选报告', '', f"采集快照：{report['as_of']}", '', *report['data_limitations'], '',
                 '| 地址 | 卧室 | 浴室 | 车位 | 广告周租 AUD | 来源 |','|---|---:|---:|---:|---:|---|']
        for r in report['pending_confirmation']:
            address = r['address'].replace('|','\\|').replace('\n',' ')
            lines.append(f"| {address} | {r['bedroom_label']} | {r['bathrooms']} | {r['car_spaces']} | {r['weekly_rent']} | {r['source_url']} |")
        return Response('\n'.join(lines),media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="real-evaluation.md"'})
