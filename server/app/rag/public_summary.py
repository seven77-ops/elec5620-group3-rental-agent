"""Bounded public-source presentation review; never used by private contract compose."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import re
from time import monotonic
from jsonschema import Draft202012Validator
from ..ai.provider import ProviderError
from .claim_support import preserve_claim
from .passages import source_passages
from ..english import untranslated_prose

PUBLIC_TYPES={'official_guidance','official_template','student_guidance','product_guide'}
REPAIRABLE={'invalid_response','invalid_citation','unsupported_claim'}
_CERTAINTY=re.compile(r'guarantee(?:d|s)?|always|unconditionally|一定|保证|無條件|无条件|必然',re.I)
_STATUS_CODE=re.compile(r'(?:状态\s*(?:为|是)?|status\s*(?:is|of|=|:)?)\s*[\"\'“‘「]*([A-Z][A-Z_]{2,})')


def check_text(text,quote,context,question,language):
    if untranslated_prose(text,[quote]):
        raise ValueError('The generated public summary must be in English')
    preserve_claim(text,quote,context,question,language)
    if _CERTAINTY.search(text) and not _CERTAINTY.search(quote):raise ValueError('Unsupported certainty')
    if any(code not in quote for code in _STATUS_CODE.findall(text)):raise ValueError('Uncited status code')
    # Translation must not turn a response window into compulsory acceptance,
    # or change the party submitting a claim into its recipient.
    if re.search(r'has up to .{0,20} to accept',quote,re.I) and re.search(r'(?:必须|须|需在)[^。；;]{0,18}接受',text):
        raise ValueError('Acceptance period mistranslated as obligation')
    if 'submitted by either' in quote.lower() and re.search(r'向[^。；;]{0,18}(?:房东|中介)[^。；;]{0,10}提交',text):
        raise ValueError('Submitting party mistranslated as recipient')


def review_public_summary(provider,question,language,evidence,result,*,timeout=15):
    language='en'
    deadline=monotonic()+timeout
    if result.get('scope') not in ('public','product') or result.get('private_binding'):
        return result
    if not evidence or any(row.get('source_type') not in PUBLIC_TYPES for row in evidence):
        return result
    if not (result.get('source_preserving') or result.get('generation_outcome') in REPAIRABLE):
        return result
    supplied=[{'evidence_id':r['chunk_id'],'section':r.get('section_path',r['section']),
               'source_type':r['source_type'],'passages':[{'quote_id':key,'text':value}
                 for key,value in source_passages(r).items()]} for r in evidence]
    supplied=[r for r in supplied if r['passages']]
    if not supplied or timeout<1:return result
    from .service import ANSWER_SCHEMA
    schema=deepcopy(ANSWER_SCHEMA)
    item=schema['properties']['claims']['items']
    item['required'].remove('quote_id');del item['properties']['quote_id']
    item['required'].append('quote_ids')
    item['properties']['quote_ids']={'type':'array','minItems':1,'maxItems':3,'uniqueItems':True,'items':{'type':'string'}}
    item['allOf']=[{'oneOf':[{'properties':{'evidence_id':{'const':row['evidence_id']},
        'quote_ids':{'items':{'enum':[p['quote_id'] for p in row['passages']]}}}} for row in supplied]}]
    item['required']+=['grounded','conditions_preserved']
    item['properties'].update(grounded={'const':True},conditions_preserved={'const':True})
    try:
        # Isolate synthesis by source item. A single global prompt encouraged the
        # model to borrow a condition from source B but cite source A. Neither
        # neighboring sources nor earlier (possibly rejected) model text is sent.
        chosen_ids=list(dict.fromkeys(c['evidence_id'] for c in result['claims']))[:3]
        selected=[r for r in supplied if r['evidence_id'] in chosen_ids] if chosen_ids else supplied[:3]
        def summarize(row):
            one_schema=deepcopy(schema)
            one_schema['properties']['claims']['maxItems']=1
            one_schema['properties']['claims']['items']['allOf'][0]['oneOf']=[branch for branch in
                item['allOf'][0]['oneOf'] if branch['properties']['evidence_id']['const']==row['evidence_id']]
            response,call=provider.call({'task':'rag_grounded_summary','question':question,'language':language,
                'response_schema':one_schema,'evidence':[row],'transport_timeout_seconds':min(15,max(1,timeout-8))})
            if list(Draft202012Validator(one_schema).iter_errors(response)):raise ValueError('Invalid per-source summary')
            return response,call
        with ThreadPoolExecutor(max_workers=3,thread_name_prefix='public-summary') as pool:
            outputs=list(pool.map(summarize,selected))
        raw={'claims':[],'unknowns':[]}
        for response,call in outputs:
            # Each source worker must obey its own single-source schema as well.
            if len(response.get('claims',[]))>1:raise ValueError('Too many per-source claims')
            if list(Draft202012Validator(schema).iter_errors(response)):raise ValueError('Invalid source summary')
            raw['claims']+=response['claims'];raw['unknowns']+=response['unknowns']
        raw['unknowns']=list(dict.fromkeys(raw['unknowns']))[:5]
        if list(Draft202012Validator(schema).iter_errors(raw)):raise ValueError('Invalid reviewed summary')
        if any(untranslated_prose(value) for value in raw['unknowns']):
            raise ValueError('Generated follow-up information must be in English')
        by_id={r['chunk_id']:r for r in evidence};accepted=[];citations=[];seen=set()
        for candidate in raw['claims']:
            row=by_id[candidate['evidence_id']]
            available=source_passages(row)
            quote='\n\n'.join(available[key] for key in candidate['quote_ids'])
            text=candidate['text'].strip()
            if not text:raise ValueError('Empty reviewed claim')
            # This remains an AI source review, not human or legal certification.
            # Deterministic source checks still reject invented numbers, units and regimes.
            # Check numeric/citation safety before independent language review.
            check_text(text,quote,row.get('section_path',row['section']),question,language)
            if any(code not in quote for code in _STATUS_CODE.findall(text)):
                raise ValueError('Uncited status code')
            if _CERTAINTY.search(text) and not _CERTAINTY.search(quote):raise ValueError('Unsupported certainty')
            key=(row['chunk_id'],tuple(sorted(candidate['quote_ids'])))
            if key in seen:raise ValueError('Duplicate source claim')
            seen.add(key)
            accepted.append({'text':text,'evidence_id':row['chunk_id'],'quote':quote,'source_preserving':False})
            citations.append({'evidence_id':row['chunk_id'],'document_id':row['document_id'],'title':row['title'],
                'section':row['section'],'source_url':row.get('document_url',row['source_url']),
                'checked_at':row['checked_at'],'document_version':row.get('document_version',row['content_hash']),
                'quote':quote,**{k:row[k] for k in ('source_type','page','line_start','line_end') if k in row}})
        if accepted:
            # Independently check the proposed text against ONLY its cited quotation.
            # The generating pass sees all sources; it must not borrow another source's
            # fact while retaining the wrong citation. No retrieval pool or draft here.
            remaining=min(8,deadline-monotonic())
            if remaining<1:raise ValueError('Public summary deadline exhausted')
            check_schema={'type':'object','additionalProperties':False,'required':['supported'],
                          'properties':{'supported':{'type':'array','minItems':len(accepted),'maxItems':len(accepted),
                              'items':{'type':'boolean'}},'texts':{'type':'array','minItems':len(accepted),
                              'maxItems':len(accepted),'items':{'type':'string','minLength':1,'maxLength':1200}}}}
            check_schema['required'].append('texts')
            check_schema['required'].append('original_supported')
            check_schema['properties']['original_supported']={'type':'array','minItems':len(accepted),
                'maxItems':len(accepted),'items':{'type':'boolean'}}
            checked,check_meta=provider.call({'task':'rag_summary_check','language':language,
                'response_schema':check_schema,'transport_timeout_seconds':remaining,
                'checks':[{'claim':c['text'],'quote':c['quote'],
                           'source_context':by_id[c['evidence_id']].get('section_path',by_id[c['evidence_id']]['section'])}
                          for c in accepted]})
            if list(Draft202012Validator(check_schema).iter_errors(checked)) or not all(checked['supported']):
                raise ValueError('Independent source review rejected a claim')
            for claim,text in zip(accepted,checked['texts']):
                row=by_id[claim['evidence_id']]
                check_text(text,claim['quote'],row.get('section_path',row['section']),question,language)
                claim['text']=text.strip()
        updated=deepcopy(result)
        updated.update(claims=accepted,unknowns=(result.get('unknowns',[]) if accepted else raw['unknowns']),source_preserving=False,answer_language=language,
                       summary_method='source_reviewed_summary',summary_review={'model_accepted':True,'human_reviewed':False},
                       summary_calls=[{k:v for k,v in call.items() if k in ('task','model','status','duration_ms','usage','simulated')}
                                      for _,call in outputs])
        if accepted:
            updated['summary_check_call']={k:v for k,v in check_meta.items() if k in ('task','model','status','duration_ms','usage','simulated')}
        updated['warnings']=[w for w in updated['warnings'] if not (w.startswith('The AI summary') or '未提供经核验的中文译文' in w)]
        if accepted:
            updated.update(status='answered',generation_outcome='answered',citations=citations,
                           answer='\n\n'.join(c['text']+' ['+str(i+1)+']' for i,c in enumerate(accepted)))
        else:
            updated.update(status='insufficient_evidence',generation_outcome='model_abstained',
                answer='The available sources do not establish an answer to this question.')
        return updated
    except (ProviderError,ValueError,TypeError,KeyError):
        # Atomic failure: never publish a partially checked summary.
        fallback=deepcopy(result)
        fallback['unknowns']=[value for value in fallback.get('unknowns',[]) if not untranslated_prose(value)]
        fallback.update(status='sources_only',generation_outcome='summary_review_failed',claims=[],source_preserving=False,
            answer='Sources were found, but the concise summary could not be source-checked. Retry or read the excerpts.')
        fallback['warnings'].append('The concise summary could not be source-checked. Retry or review the excerpts.')
        return fallback
