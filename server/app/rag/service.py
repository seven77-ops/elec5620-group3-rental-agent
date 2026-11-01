"""Public evidence retrieval, optional cloud ranking and validated cited answers."""
import json,re
from copy import deepcopy
from datetime import date,datetime
from time import monotonic
from zoneinfo import ZoneInfo
from ..bootstrap import ROOT
from ..common import require,shape
from ..ai.provider import ProviderError
from .index import KnowledgeIndex
from .provider import RetrievalProvider,RetrievalError
from .passages import source_passages
from .scope import retrieval_source_types,retrieval_query,PRODUCT_TYPES

SNAPSHOT=ROOT/'data/knowledge/en/documents.json'
ANSWER_SCHEMA={'type':'object','additionalProperties':False,'required':['claims','unknowns'],'properties':{
    'claims':{'type':'array','maxItems':3,'items':{'type':'object','additionalProperties':False,'required':['text','evidence_id','quote_id'],
        'properties':{'text':{'type':'string','maxLength':1200},'evidence_id':{'type':'string'},'quote_id':{'type':'string'}}}},
    'unknowns':{'type':'array','maxItems':5,'items':{'type':'string','maxLength':400}}}}


def passages(row):
    return source_passages(row)


def scoped_answer_schema(evidence):
    schema=deepcopy(ANSWER_SCHEMA)
    schema['properties']['claims']['items']['allOf']=[{'oneOf':[
        {'properties':{'evidence_id':{'const':row['evidence_id']},
                       'quote_id':{'enum':[quote['quote_id'] for quote in row['passages']]}}}
        for row in evidence]}]
    return schema


class KnowledgeService:
    def __init__(self,ctx):
        self.ctx=ctx;self.index=KnowledgeIndex(ctx.repo.directory/'rag.sqlite3');self.provider=RetrievalProvider()
        if SNAPSHOT.exists() and not self.index.status()['index_version']:self.index.publish(json.loads(SNAPSHOT.read_text()))

    def authorize(self,case_id):
        with self.ctx.repo.transaction() as db:self.ctx.get(db,'case',case_id)

    def status(self,case_id: str):
        self.authorize(case_id)
        return {**self.index.status(),**self.provider.status(),'generation_configured':self.ctx.ai_provider.public_config()['configured'],
                'private_documents_indexed':False}

    def source(self,case_id: str,source_id: str):
        self.authorize(case_id);item=self.index.source(source_id)
        require(item is not None,404,'not_found','The source is not present in the active public index.')
        return item

    def user_guide(self,version: str|None=None):
        from fastapi.responses import HTMLResponse
        from .product_guide import product_document,product_guide_html
        doc=product_document()
        require(version is None or version==doc['document_version'],409,'knowledge_changed','This product guide version changed. Reload the current guide.')
        return HTMLResponse(product_guide_html(doc),headers={'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff',
            'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"})

    def validate(self,case_id,body):
        self.authorize(case_id)
        shape(body,('question','allow_external_ai'),('language',))
        require(isinstance(body['question'],str) and 0<len(body['question'].strip())<=2000,422,'invalid_input','Enter a question of 1–2000 characters.')
        require(type(body['allow_external_ai']) is bool and body.get('language','en') in ('en','zh'),422,'invalid_input','Choose a supported answer language and explicit AI consent.')

    def retrieve(self,question,external,*,source_types=None):
        index_status=self.index.status();version=index_status['index_version'];warnings=[]
        source_types=retrieval_source_types(question) if source_types is None else source_types
        keyword=self.index.search(retrieval_query(question),source_types=source_types);rankings=[keyword];methods=['keywords']
        provider_status=self.provider.status()
        if external and provider_status['embedding_configured']:
            compatible=any(item['model']==self.provider.model and item['dimensions']==self.provider.dimensions and item['chunks']>0 for item in index_status['vector_indexes'])
            if not compatible:warnings.append('No compatible semantic index is available. Run the indexing command with --embed.')
            else:
                try:
                    vector=self.provider.embed([question])[0]
                    semantic=self.index.vector_search(vector,self.provider.model,self.provider.dimensions,source_types=source_types)
                    rankings.append(semantic);methods.append('vectors')
                except RetrievalError:warnings.append('Semantic retrieval is unavailable; keyword results are retained.')
        elif external:warnings.append('Embedding is not configured; this search uses local keywords.')
        scores={};rows={}
        today=datetime.now(ZoneInfo('Australia/Sydney')).date()
        for ranking in rankings:
            for rank,row in enumerate(ranking):
                # Checked freshness is a retrieval policy, not a guarantee that a rule is unchanged.
                if not 0<=(today-date.fromisoformat(row['checked_at'])).days<=90:continue
                key=row['chunk_id'];rows[key]=row;scores[key]=scores.get(key,0)+1/(60+rank+1)
        ordered=[rows[i] for i in sorted(rows,key=lambda i:scores[i],reverse=True)[:30]]
        if external and ordered and provider_status['rerank_configured']:
            try:
                order=self.provider.rerank(question,[r.get('embedding_text',r['text']) for r in ordered]);ordered=[ordered[i] for i in order];methods.append('rerank')
            except RetrievalError:warnings.append('Reranking is unavailable; fused retrieval order is retained.')
        elif external and ordered:warnings.append('Reranking is not configured.')
        require(self.index.status()['index_version']==version,409,'knowledge_changed','Knowledge sources changed. Please search again.')
        return {'evidence':ordered[:6],'index_version':version,'retrieval_methods':methods,'warnings':warnings,
                'scope':'product' if tuple(source_types)==PRODUCT_TYPES else 'public'}

    def search(self,case_id: str,body: dict):
        self.validate(case_id,body)
        return self.retrieve(body['question'],body['allow_external_ai'])

    def answers(self,case_id: str,body: dict):
        self.validate(case_id,body)
        return self.answer(body['question'],body['allow_external_ai'],body.get('language','en'))

    def answer(self,question,external=True,language='en'):
        language='en'
        report=self.retrieve(question,external);evidence=report.pop('evidence')
        deadline=monotonic()+36
        result=self.compose(question,report,evidence,external,language,model_timeout=18)
        if external:
            from .public_summary import review_public_summary
            result=review_public_summary(self.ctx.ai_provider,question,language,evidence,result,timeout=deadline-monotonic())
        result['question']=question
        require(self.index.status()['index_version']==report['index_version'],409,'knowledge_changed','Knowledge sources changed during answering. Please ask again.')
        return result

    def compose(self,question,report,evidence,external=True,language='en',*,model_timeout=None):
        language='en'
        by_id={r['chunk_id']:r for r in evidence}
        result={**report,'knowledge_language':'en','language':language,'claims':[],'citations':[],
                'unknowns':[],'generation_outcome':'no_evidence','answer_language':language,'status':'insufficient_evidence','answer':'No sufficiently relevant current source was found. Please clarify your NSW rental question.'}
        if not evidence:return result
        result.update(status='sources_only',answer='English source excerpts are available below. No AI summary has been applied.')
        cited=evidence
        result['generation_outcome']='local_only'
        if external:
            supplied=[{'evidence_id':r['chunk_id'],'section':r.get('section_path',r['section']),
                'source_type':r.get('source_type','official_guidance'),'jurisdiction':r.get('jurisdiction'),'page':r.get('page'),
                'passages':[{'quote_id':key,'text':value} for key,value in passages(r).items()]} for r in evidence]
            supplied=[r for r in supplied if r['passages']]
            outcome='invalid_response'
            try:
                if not supplied:
                    outcome='no_complete_passages'
                    raise ValueError('No complete quotation is available')
                schema=scoped_answer_schema(supplied)
                raw,meta=self.ctx.ai_provider.call({'task':'rag_answer','question':question,'language':language,
                    'response_schema':schema,'evidence':supplied,
                    **({'transport_timeout_seconds':model_timeout} if model_timeout else {})})
                from jsonschema import Draft202012Validator
                if list(Draft202012Validator(ANSWER_SCHEMA).iter_errors(raw)):raise ValueError('Invalid answer shape')
                from ..english import untranslated_prose
                if any(untranslated_prose(value) for value in raw['unknowns']):
                    raise ValueError('Generated follow-up information must be in English')
                if not raw['claims']:
                    result.update(status='insufficient_evidence',generation_outcome='model_abstained',unknowns=raw['unknowns'],
                        answer='The available sources do not establish an answer to this question.')
                else:
                    accepted=[];seen=set()
                    for candidate in raw['claims']:
                        claim=dict(candidate);outcome='invalid_citation'
                        row=by_id.get(claim['evidence_id'])
                        quote=passages(row).get(claim['quote_id']) if row else None
                        if quote is None or not claim['text'].strip():raise ValueError('Unsupported citation')
                        claim['quote']=quote
                        del claim['quote_id']
                        from .claim_support import preserve_claim
                        outcome='unsupported_claim'
                        supported=preserve_claim(claim['text'],quote,row.get('section_path',row['section']),question,language)
                        if not supported['adjusted'] and untranslated_prose(supported['text'],[quote]):
                            outcome='invalid_response'
                            raise ValueError('The generated answer must be in English')
                        claim['text']=supported['text'];claim['source_preserving']=supported['adjusted']
                        key=(claim['evidence_id'],quote,claim['text'])
                        if key not in seen:accepted.append(claim);seen.add(key)
                    result.update(status='answered',generation_outcome='answered',
                        answer='\n\n'.join(c['text']+' ['+str(i+1)+']' for i,c in enumerate(accepted)),
                        claims=accepted,unknowns=raw['unknowns'])
                    cited=[by_id[c['evidence_id']] for c in accepted]
                    result['source_preserving']=any(c['source_preserving'] for c in accepted)
                    if all(c['source_preserving'] for c in accepted):
                        result['answer_language']='en' if all(r.get('language')=='en' for r in cited) else 'original'
                result['call']={k:v for k,v in meta.items() if k in ('task','model','status','duration_ms','usage','simulated')}
            except ProviderError:
                result['generation_outcome']='provider_error'
                result['warnings'].append('The AI summary is unavailable. Review the source excerpts instead.')
            except (ValueError,TypeError,KeyError):
                result['generation_outcome']=outcome
                result['warnings'].append('The AI summary was unavailable or failed citation checks. Review the source excerpts instead.')
        for i,row in enumerate(cited):
            quote=result['claims'][i]['quote'] if result['claims'] else row['text'][:800]
            result['citations'].append({'evidence_id':row['chunk_id'],'document_id':row['document_id'],'title':row['title'],
                'section':row['section'],'source_url':row.get('document_url',row['source_url']),'checked_at':row['checked_at'],
                'document_version':row.get('document_version',row['content_hash']),'quote':quote,
                **{k:row[k] for k in ('source_type','page','line_start','line_end','review_id','review_version') if k in row}})
        return result


def register_rag_routes(app,ctx):
    from .contracts import register_contract_rag_routes
    register_contract_rag_routes(app,ctx)
    service=ctx.knowledge
    app.get('/api/v1/rag/product-guide')(service.user_guide)
    base='/api/v1/cases/{case_id}/rag'
    app.get(base+'/status')(service.status)
    app.post(base+'/search')(service.search)
    app.post(base+'/answers')(service.answers)
    app.get(base+'/sources/{source_id}')(service.source)
