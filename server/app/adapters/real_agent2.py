"""Agent2 provisional real-advertisement evaluation and immutable candidate selection."""
from copy import deepcopy
import hashlib
from fastapi.responses import Response
from ..common import ApiError
from ..real_data.preferences import preference_context, POLICY
from ..real_data.profile import validate_real_profile, supplied_profile
from .profiles import ProfilesAdapter
from ..common import now, require, shape, integer, opaque_ref, request_id
from ..repository import canonical


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def commute_evidence(rows,filters):
    if 'usyd_max_minutes' not in filters:return None
    mode=filters.get('usyd_mode','public_transport')
    return digest([{'listing_id':row['listing_id'],
                    'origin':(row.get('usyd_commute') or {}).get('origin'),
                    'route':(row.get('usyd_commute') or {}).get('modes',{}).get(mode),
                    'estimate':(row.get('usyd_commute') or {}).get('estimates',{}).get(mode)} for row in rows])


def require_matching_listing(catalog, listing_id, filters, rows):
    if any(row['listing_id']==listing_id for row in rows):return
    row=catalog.get(listing_id)
    from ..commute.matching import FILTER_KEYS
    base={k:v for k,v in filters.items() if k not in FILTER_KEYS}
    require(any(item['listing_id']==listing_id for item in catalog.matching(base)),
            409,'listing_outside_requirements','This listing does not meet current budget, suburb or property requirements. Save it as a favourite, or update your requirements before selecting it.')
    if 'usyd_max_minutes' in filters:
        from ..commute.snapshot import observation
        from ..commute.estimates import estimate_for
        from ..commute.usyd import MODE_LABELS
        mode=filters.get('usyd_mode','public_transport');maximum=filters['usyd_max_minutes']
        route=observation(row,mode);estimate=estimate_for(row,mode) if not route else None
        label=MODE_LABELS.get(mode,'commute')
        if route and route['duration_minutes']>maximum:
            raise ApiError(409,'listing_outside_requirements',
                f"This listing has an indicative {label} trip to USYD of about {route['duration_minutes']:g} minutes, exceeding your {maximum}-minute limit. Save it as a favourite or update your commute limit before selecting it.",
                {'constraint':'commute','minutes':route['duration_minutes'],'maximum_minutes':maximum})
        if estimate and estimate['upper_minutes']>maximum:
            raise ApiError(409,'listing_outside_requirements',
                f"This listing has an indicative {label} trip to USYD of {estimate['lower_minutes']:g}–{estimate['upper_minutes']:g} minutes. The upper estimate exceeds your {maximum}-minute limit. Save it as a favourite or update your limit before selecting it.",
                {'constraint':'commute','lower_minutes':estimate['lower_minutes'],'upper_minutes':estimate['upper_minutes'],'maximum_minutes':maximum})
        transfers=filters.get('usyd_max_transfers')
        if route and transfers is not None and type(route.get('transfers')) is int and route['transfers']>transfers:
            raise ApiError(409,'listing_outside_requirements',
                f"The indicative {label} route needs {route['transfers']} transfers, exceeding your limit of {transfers}. Save it as a favourite or update your transfer requirement before selecting it.")
        raise ApiError(409,'listing_outside_requirements',
            f"No indicative commute for this listing meets the {label} {maximum}-minute requirement. Save it as a favourite or choose a listing with suitable commute evidence.")
    raise ApiError(409,'listing_outside_requirements','This listing is outside the current results. Review your requirements before selecting it.')


class RealProfilesAdapter(ProfilesAdapter):
    validate_profile = staticmethod(validate_real_profile)

    def read_case(self, case_id: str):
        case = super().read_case(case_id)
        if case.get('requirements_contract') != 'supplied-only-v1':
            case['requirements_profile'] = supplied_profile(case['draft']['profile'])
        return case

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
            return {**preference_context(confirmed['profile'],self.ctx.settings.catalog,
                        legacy=case.get('requirements_contract')!='supplied-only-v1'),
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
        require(integer(body['confirmation_version']) and body['confirmation_version'] > 0, 422, 'invalid_input', 'Provide the current confirmation version.')
        key = case_id + ':' + request_id(body['request_id'])
        catalog = self.ctx.settings.catalog
        with self.ctx.repo.transaction() as db:
            case = self.ctx.get(db, 'case', case_id)
            confirmed = self.ctx.current(case, body['confirmation_version'])
            old = self.ctx.receipt(db, 'real_evaluation_receipt', key, body)
            if old: return old['result']
            profile = deepcopy(confirmed['profile'])
            context = preference_context(profile,catalog,legacy=case.get('requirements_contract')!='supplied-only-v1')
            filters = catalog.filters(body['filters']) if 'filters' in body else context['filters']
            filter_source = 'manual' if 'filters' in body else 'confirmed_profile'
            from ..commute.matching import matching_for_case
            listings = matching_for_case(self.ctx,case_id,filters,db=db)
            commute_version=commute_evidence(listings,filters)
            pending = []
            for item in listings:
                pending.append({**item, 'status':'pending', 'rank':None, 'score':None, 'weekly_cost':None,
                    'score_breakdown':{'cost':None,'commute':None,'housing':None,'amenities':None},
                    'issues':['Availability, rent scope, bills, start window and lease term remain unverified.'],
                    'reasons':[f"Advertised rent AUD {item['weekly_rent']:g}/week; {item['bedroom_label']} bedrooms, {item['bathrooms']:g} bathrooms, {item['car_spaces']:g} parking spaces."],
                    'hard_checks':{'availability':{'status':'unknown','reason':'The landlord has not confirmed that the public advertisement is still available.'}},
                    'evidence_refs':{field:{'source_ref':item['source_url'],
                        'observed_at':item['captured_at'], 'source_name':'Domain public advertisement index'}
                        for field in ('bedrooms','bathrooms','car_spaces','weekly_rent')}})
                if item['bedroom_count_basis'] == 'open_plan_as_one':
                    pending[-1]['evidence_refs']['bedrooms'].update(source_value=item['advertised_bedrooms'],
                        interpreted_value=1, interpretation='Project convention: a zero-bedroom open-plan listing counts as one living/sleeping space, not a private bedroom.')
            run_id = 'real-' + digest({'profile':profile,'dataset':catalog.fingerprint,'filters':filters,'mapping_policy':POLICY,'filter_source':filter_source,'commute_evidence':commute_version})
            report = {'schema_version':'real-1.0','scoring_version':'real-facts-1.0','data_mode':'real_listings',
                'recommendation_run_id':run_id,'search_id':case['search_id'],'profile':profile,
                'profile_version':confirmed['version'],'profile_fingerprint':confirmed['fingerprint'],
                'dataset_fingerprint':catalog.fingerprint,'as_of':catalog.as_of, 'evaluated_at':now(),
                'report_status':'provisional','filters':filters,'catalog':catalog.metadata(),
                'mapping_policy':POLICY,'filter_source':filter_source,'profile_filters':context['filters'],
                'commute_evidence_fingerprint':commute_version,
                'unverified_preferences':context['unverified_preferences'],
                'counts':{'input':len(listings),'eligible':0,'pending':len(listings),'excluded':0,'duplicates':0},
                'recommendations':pending[:5],'eligible':[],'pending_confirmation':pending,'excluded':[],
                'duplicates':[],'effective_weights':{},'clarification_requests':['Listings are unverified candidates. Advertised rent does not establish comparable total costs.'],
                'data_limitations':['Uses captured public advertisement snapshots, without live availability data.',
                    'Bedrooms, bathrooms, parking and advertised weekly rent have sources. Unknown commute, facility distances and rent scope have not been invented.',
                    'Filtering and ranking use advertisement fields only. Full eligibility checks and a four-dimension total score have not been applied.']}
            report['data_limitations'].append('Open-plan listings advertised as zero bedrooms count as one sleeping space under the project convention. The original bedroom count is retained; this does not establish a private bedroom.')
            result = {'run_id':run_id,'report':report,'comparison':None,'comparison_source':'real_catalog'}
            # Reusing a deterministic run preserves its original immutable evaluation time.
            saved = self.ctx.repo.get(db,'evaluation',run_id)
            if saved:
                require(saved['case_id']==case_id,409,'evaluation_conflict','Report identifier conflict.')
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
            require(run['case_id']==case_id and run['profile']==confirmed['profile'],409,'stale_evaluation','Generate candidates again using current confirmed preferences.')
            require(run['response']['report'].get('data_mode')=='real_listings',409,'legacy_evaluation','Simulated reports are historical records only. Re-evaluate live listings.')
            require(run['response']['report']['dataset_fingerprint']==self.ctx.settings.catalog.fingerprint,
                    409,'stale_catalog','The listing catalogue changed. Generate live listing candidates again.')
            require(run['response']['report'].get('mapping_policy')==POLICY,409,'stale_evaluation','Recommendation rules changed. Generate candidates again using current preferences.')
            require(body['confirmed'] is True,422,'selection_confirmation_required','Explicitly confirm saving this candidate.')
            old = self.ctx.receipt(db,'real_selection_receipt',key,body)
            if old: return old['result']
            filters=run['response']['report']['filters']
            if 'usyd_max_minutes' in filters:
                from ..commute.matching import matching_for_case
                current_rows=matching_for_case(self.ctx,case_id,filters,db=db)
                require(commute_evidence(current_rows,filters)==run['response']['report'].get('commute_evidence_fingerprint'),
                    409,'stale_evaluation','Campus routes changed or expired. Generate candidates again using current commute requirements.')
                require_matching_listing(self.ctx.settings.catalog,body['listing_id'],filters,current_rows)
            listing = next((r for r in run['dataset']['listings'] if r['listing_id']==body['listing_id']),None)
            require(listing is not None,409,'listing_not_in_run','Only listings in these live search results can be selected.')
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
        require(format in ('json','markdown'),422,'invalid_format','Choose json or markdown.')
        if format == 'json': return self.ctx.download(report,'real-evaluation')
        lines = ['# Live listing candidate report', '', f"Captured snapshot: {report['as_of']}", '', *report['data_limitations'], '',
                 '| Address | Bedrooms | Bathrooms | Parking | Advertised weekly rent AUD | Source |','|---|---:|---:|---:|---:|---|']
        for r in report['pending_confirmation']:
            address = r['address'].replace('|','\\|').replace('\n',' ')
            lines.append(f"| {address} | {r['bedroom_label']} | {r['bathrooms']} | {r['car_spaces']} | {r['weekly_rent']} | {r['source_url']} |")
        return Response('\n'.join(lines),media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="real-evaluation.md"'})
