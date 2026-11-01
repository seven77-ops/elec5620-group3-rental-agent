"""Independent, version-bound contract knowledge consent and revocable private indexes."""
from copy import deepcopy
import hashlib,json,re,shutil
from pathlib import Path
from time import time
from ..common import ApiError,require,shape,request_id,integer,now,uid
from ..ai.service import AiService,digest
from ..adapters.contracts import ContractsAdapter
from .contract_index import ContractIndex,contract_chunks
from .provider import RetrievalError


class ContractKnowledge:
    def __init__(self,ctx):self.ctx=ctx

    def _owned(self,db,case_id,review_id):
        self.ctx.get(db,'case',case_id);saved=self.ctx.get(db,'review',review_id)
        require(saved['case_id']==case_id,404,'not_found','The contract was not found in this case.')
        return saved

    def _binding(self,db,case_id,review_id):
        saved=self._owned(db,case_id,review_id)
        binding,_=AiService(self.ctx,ContractsAdapter(self.ctx)).contract_source(db,review_id)
        directory=(self.ctx.repo.directory/'uploads').resolve();path=(directory/saved['file_ref']).resolve()
        require(path.parent==directory and path.is_file(),404,'document_missing','The uploaded contract is unavailable.')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==binding['document_sha256'],409,'document_changed','The contract file changed. Upload it again before searching.')
        return binding,saved,path

    def _directory(self,case_id,review_id):
        base=self.ctx.repo.directory/'rag-private';name=hashlib.sha256((case_id+'\0'+review_id).encode()).hexdigest()
        path=base/name
        require(not path.is_symlink() and path.resolve().parent==base.resolve(),409,'invalid_private_store','The private store is unavailable.')
        return path

    def _path(self,case_id,review_id,grant):
        filename=grant.get('index_file','')
        require(re.fullmatch(r'index-[A-Za-z0-9-]+\.sqlite3',filename) is not None,409,'contract_index_missing','Enable contract search again.')
        return self._directory(case_id,review_id)/filename

    def _grant(self,db,case_id,review_id,token=None):
        binding,saved,path=self._binding(db,case_id,review_id);current=digest(binding)
        require(token is None or token==current,409,'contract_context_changed','The selected contract version changed. Reload contract search.')
        grant=self.ctx.repo.get(db,'contract_rag_index',review_id)
        require(grant and grant.get('active'),403,'contract_rag_consent_required','Enable private contract search for this document first.')
        require(grant['binding']==binding,409,'contract_context_changed','The contract review changed. Enable search again for this version.')
        require(grant['status']=='ready',409,'contract_index_not_ready','Contract indexing has not completed.')
        index_path=self._path(case_id,review_id,grant)
        require(index_path.is_file(),409,'contract_index_missing','The private index is missing. Enable search again.')
        return binding,saved,grant,index_path

    def status(self,case_id: str,review_id: str):
        with self.ctx.repo.transaction() as db:
            binding,saved,path=self._binding(db,case_id,review_id)
            grant=self.ctx.repo.get(db,'contract_rag_index',review_id)
        status='not_enabled'
        if grant:
            status=('revoked' if not grant.get('active') else 'needs_reindex' if grant['binding']!=binding else grant['status'])
            if status=='ready' and not self._path(case_id,review_id,grant).is_file():status='needs_reindex'
        return {'status':status,'context_token':digest(binding),'review_id':review_id,'review_version':binding['review_version'],
                'source_name':saved['review']['document']['source_name'],'document_hash':binding['document_sha256'],
                'page_count':saved['review']['document']['page_count'],'allow_external_ai':bool(grant and grant.get('active') and grant.get('allow_external_ai')),
                'grant_id':grant.get('grant_id') if grant else None,'warnings':grant.get('warnings',[]) if grant else []}

    def index(self,case_id: str,review_id: str,body: dict):
        shape(body,('request_id','context_token','expected_version','confirmed','allow_external_ai'))
        request_id(body['request_id']);require(body['confirmed'] is True,403,'contract_rag_consent_required','Confirm independent consent to index this contract.')
        require(type(body['allow_external_ai']) is bool and integer(body['expected_version']),422,'invalid_input','Choose the external-processing scope and current review version.')
        key=case_id+':'+review_id+':'+body['request_id'];attempt=uid('index')
        with self.ctx.repo.transaction() as db:
            binding,saved,path=self._binding(db,case_id,review_id)
            require(body['context_token']==digest(binding) and body['expected_version']==binding['review_version'],409,'contract_context_changed','Reload the current contract version.')
            old=self.ctx.receipt(db,'contract_rag_receipt',key,body)
            grant=self.ctx.repo.get(db,'contract_rag_index',review_id)
            if old and old.get('result'):
                require(grant and grant.get('active') and grant.get('grant_id')==old['result']['grant_id'] and grant['binding']==binding,409,'contract_index_superseded','This index consent was revoked or superseded.')
                return old['result']
            require(not old or old.get('status')!='pending' or time()-old.get('started_at',0)>900,409,'request_in_progress','Contract indexing is already running.')
            grant={'case_id':case_id,'review_id':review_id,'binding':binding,'grant_id':attempt,'active':True,'status':'indexing',
                'allow_external_ai':body['allow_external_ai'],'created_at':now(),'index_file':attempt+'.sqlite3','warnings':[]}
            self.ctx.repo.put(db,'contract_rag_index',review_id,grant)
            self.ctx.repo.put(db,'contract_rag_receipt',key,{'input':body,'status':'pending','grant_id':attempt,'started_at':time()})
        try:
            from contract_agent.document import load_document
            document=load_document(path,consent=True,max_pdf_pages=30 if saved.get('real_context') else 10)
            require(document['sha256']==binding['document_sha256'],409,'document_changed','The uploaded contract changed during indexing.')
            document['source_name']=saved['review']['document']['source_name']
            rows=contract_chunks(document,case_id,review_id,binding['review_version'],digest(binding),
                '/api/v1/cases/'+case_id+'/rag/contracts/'+review_id+'/sources')
            require(bool(rows),422,'unreadable_contract','No readable contract clauses were found.')
            vectors=None;provider=self.ctx.knowledge.provider
            if body['allow_external_ai']:
                if provider.status()['embedding_configured']:
                    try:
                        vectors=[]
                        for start in range(0,len(rows),10):
                            with self.ctx.repo.transaction() as db:self._pending(db,case_id,review_id,binding,attempt)
                            vectors.extend(provider.embed([r['text'] for r in rows[start:start+10]],timeout=30))
                    except RetrievalError:
                        vectors=None;grant['warnings'].append('Contract semantic indexing is unavailable; local text search is ready.')
                else:grant['warnings'].append('Embedding is not configured; contract search uses local text.')
            with self.ctx.repo.transaction() as db:
                self._pending(db,case_id,review_id,binding,attempt)
                directory=self._directory(case_id,review_id);directory.mkdir(parents=True,exist_ok=True)
                target=self._path(case_id,review_id,grant)
                private=ContractIndex(target,case_id,review_id,digest(binding),create=True)
                private.publish_rows(rows,vectors,provider.model,provider.dimensions)
                grant['status']='ready';grant['chunk_count']=len(rows);self.ctx.repo.put(db,'contract_rag_index',review_id,grant)
                result={'status':'ready','context_token':digest(binding),'review_id':review_id,'review_version':binding['review_version'],
                    'grant_id':attempt,'chunk_count':len(rows),'vector_chunks':len(rows) if vectors is not None else 0,
                    'allow_external_ai':body['allow_external_ai'],'warnings':grant['warnings']}
                self.ctx.save_receipt(db,'contract_rag_receipt',key,body,result)
                for previous in directory.glob('*.sqlite3'):
                    if previous!=target:previous.unlink(missing_ok=True)
            return result
        except BaseException:
            cleanup=False
            with self.ctx.repo.transaction() as db:
                current=self.ctx.repo.get(db,'contract_rag_index',review_id)
                if current and current.get('grant_id')==attempt:
                    current.update(active=False,status='failed');self.ctx.repo.put(db,'contract_rag_index',review_id,current)
                    cleanup=True
                receipt=self.ctx.repo.get(db,'contract_rag_receipt',key)
                if receipt and receipt.get('grant_id')==attempt:receipt['status']='failed';self.ctx.repo.put(db,'contract_rag_receipt',key,receipt)
            if cleanup:self._cleanup(case_id,[review_id])
            raise

    def _pending(self,db,case_id,review_id,binding,attempt):
        current,_,_=self._binding(db,case_id,review_id);grant=self.ctx.repo.get(db,'contract_rag_index',review_id)
        require(current==binding and grant and grant.get('active') and grant.get('grant_id')==attempt,409,'contract_context_changed','Contract permission or version changed during indexing.')

    def _purge_files(self,case_id,review_id):
        path=self._directory(case_id,review_id)
        if path.exists():shutil.rmtree(path)

    def _redact(self,entry):
        entry['content']='Contract search consent or the source version changed. Enable search again for the current contract before asking further questions.'
        entry['knowledge']={**entry['knowledge'],'answer':entry['content'],'status':'sources_only','claims':[],'citations':[],
            'unknowns':[],'warnings':['Historical private evidence is no longer available under the current permission.']}
        return entry

    def decorate_entry(self,db,entry):
        marker=entry.get('knowledge',{}).get('private_binding')
        if not marker:return entry
        try:
            binding,_,grant,_=self._grant(db,marker['case_id'],marker['review_id'],marker['context_token'])
            require(grant['grant_id']==marker['grant_id'],409,'contract_index_superseded','Private source was superseded.')
        except (ApiError,KeyError):self._redact(entry)
        return entry

    def _revoke_records(self,db,case_id,review_ids):
        for review_id in review_ids:
            grant=self.ctx.repo.get(db,'contract_rag_index',review_id)
            if grant:grant.update(active=False,status='revoked',allow_external_ai=False);self.ctx.repo.put(db,'contract_rag_index',review_id,grant)
        # Remove private quote copies from derived chat/cache results while retaining user messages.
        for kind in ('assistant_conversation','assistant_turn_receipt'):
            for identifier,raw in db.execute('SELECT id,body FROM objects WHERE kind=?',(kind,)).fetchall():
                value=json.loads(raw);conversation=value if kind=='assistant_conversation' else value.get('result')
                if not isinstance(conversation,dict) or conversation.get('case_id')!=case_id:continue
                changed=False
                for entry in conversation.get('messages',[]):
                    marker=entry.get('knowledge',{}).get('private_binding',{})
                    if marker.get('review_id') in review_ids:self._redact(entry);changed=True
                if changed:
                    if kind=='assistant_conversation':conversation['revision']+=1
                    self.ctx.repo.put(db,kind,identifier,value)

    def revoke(self,case_id: str,review_id: str,body: dict):
        shape(body,())
        with self.ctx.repo.transaction() as db:
            self._owned(db,case_id,review_id);self._revoke_records(db,case_id,[review_id])
        warnings=self._cleanup(case_id,[review_id])
        return {'status':'revoked','review_id':review_id,'warnings':warnings}

    def _cleanup(self,case_id,review_ids):
        warnings=[]
        for review_id in review_ids:
            # The revocation transaction already committed. A concurrent new grant
            # must not have its new files deleted by this old cleanup operation.
            with self.ctx.repo.transaction() as db:
                grant=self.ctx.repo.get(db,'contract_rag_index',review_id)
                if not grant or grant.get('active'):continue
                failed=False
                try:self._purge_files(case_id,review_id)
                except OSError:
                    failed=True;warnings.append('Access was revoked. Derived file cleanup needs a retry.')
                grant['cleanup_pending']=failed
                grant['warnings']=['Access was revoked. Derived file cleanup needs a retry.'] if failed else []
                self.ctx.repo.put(db,'contract_rag_index',review_id,grant)
        return warnings

    def revoke_original(self,case_id,consent_id):
        with self.ctx.repo.transaction() as db:
            ids=[identifier for identifier,raw in db.execute('SELECT id,body FROM objects WHERE kind="contract_rag_index"').fetchall()
                 if (value:=json.loads(raw)).get('case_id')==case_id and value.get('binding',{}).get('consent_id')==consent_id]
            self._revoke_records(db,case_id,ids)
        self._cleanup(case_id,ids)

    def _query(self,case_id,review_id,body):
        with self.ctx.repo.transaction() as db:self._binding(db,case_id,review_id)
        shape(body,('question','allow_external_ai','context_token'),('language',))
        require(isinstance(body['context_token'],str) and bool(re.fullmatch(r'[a-f0-9]{64}',body['context_token'])) and isinstance(body['question'],str) and 0<len(body['question'].strip())<=2000 and type(body['allow_external_ai']) is bool and body.get('language','en') in ('en','zh'),422,'invalid_input','Enter a supported question and processing scope.')
        with self.ctx.repo.transaction() as db:binding,saved,grant,path=self._grant(db,case_id,review_id,body['context_token'])
        require(not body['allow_external_ai'] or grant['allow_external_ai'],403,'contract_external_consent_required','Enable cloud processing for this contract before sending excerpts to AI.')
        return binding,saved,grant,path

    def _check(self,case_id,review_id,binding,grant):
        with self.ctx.repo.transaction() as db:
            current,_,active,_=self._grant(db,case_id,review_id,digest(binding))
            require(current==binding and active['grant_id']==grant['grant_id'],409,'contract_context_changed','Contract permission or source changed during the request.')

    def _retrieve(self,case_id,review_id,body,binding,grant,path):
        index=ContractIndex(path,case_id,review_id,digest(binding));status=index.status();query=body['question']
        query=re.sub(r'\bdeposit\b','bond',query,flags=re.I)
        # Remove document-label bridges before the shared Chinese topic expansion.
        query=re.sub(r'合同|租约|协议',' ',query)
        query=re.sub(r'\b(?:contract|agreement|clause|document|say|says|stated|uploaded|terms)\b',' ',query,flags=re.I)
        rankings=[index.search(query)];methods=['contract_keywords'];warnings=[];provider=self.ctx.knowledge.provider
        if body['allow_external_ai'] and provider.status()['embedding_configured'] and any(v['model']==provider.model and v['dimensions']==provider.dimensions for v in status['vector_indexes']):
            self._check(case_id,review_id,binding,grant)
            try:rankings.append(index.vector_search(provider.embed([body['question']])[0],provider.model,provider.dimensions));methods.append('contract_vectors')
            except RetrievalError:warnings.append('Contract semantic search is unavailable; local results are retained.')
        rows={};scores={}
        for ranking in rankings:
            for rank,row in enumerate(ranking):rows[row['chunk_id']]=row;scores[row['chunk_id']]=scores.get(row['chunk_id'],0)+1/(61+rank)
        ordered=[rows[i] for i in sorted(rows,key=lambda i:scores[i],reverse=True)[:20]]
        if body['allow_external_ai'] and ordered and provider.status()['rerank_configured']:
            self._check(case_id,review_id,binding,grant)
            try:ordered=[ordered[i] for i in provider.rerank(body['question'],[r['text'] for r in ordered])];methods.append('contract_rerank')
            except RetrievalError:warnings.append('Contract reranking is unavailable; local order is retained.')
        self._check(case_id,review_id,binding,grant)
        return {'evidence':ordered[:6],'index_version':digest(binding),'retrieval_methods':methods,'warnings':warnings}

    def search(self,case_id: str,review_id: str,body: dict):
        binding,saved,grant,path=self._query(case_id,review_id,body)
        return self._retrieve(case_id,review_id,body,binding,grant,path)

    def answers(self,case_id: str,review_id: str,body: dict):
        binding,saved,grant,path=self._query(case_id,review_id,body)
        report=self._retrieve(case_id,review_id,body,binding,grant,path);private=report.pop('evidence')
        from .scope import REFERENCE_TYPES
        public=self.ctx.knowledge.retrieve(body['question'],body['allow_external_ai'],source_types=REFERENCE_TYPES);official=public.pop('evidence')
        report['retrieval_methods']+=['public_'+m for m in public['retrieval_methods']];report['warnings']+=public['warnings']
        self._check(case_id,review_id,binding,grant)
        result=self.ctx.knowledge.compose(body['question'],report,private[:4]+official[:2],body['allow_external_ai'] and bool(private),'en')
        if not private:
            result.update(status='insufficient_evidence',answer='No matching clause was found in this authorized contract. Any general guidance below does not establish a term of your contract.',
                claims=[],unknowns=['The selected contract does not provide a matching clause.'])
        result['scope']='contract';result['knowledge_language']='original'
        result['private_binding']={'case_id':case_id,'review_id':review_id,'context_token':digest(binding),'grant_id':grant['grant_id']}
        self._check(case_id,review_id,binding,grant)
        require(self.ctx.knowledge.index.status()['index_version']==public['index_version'],409,'knowledge_changed','Public guidance changed during answering.')
        return result

    def document(self,case_id: str,review_id: str,context_token: str):
        from fastapi.responses import Response
        from urllib.parse import quote
        with self.ctx.repo.transaction() as db:
            binding,saved,grant,index_path=self._grant(db,case_id,review_id,context_token)
            _,_,path=self._binding(db,case_id,review_id)
        content=path.read_bytes()
        require(hashlib.sha256(content).hexdigest()==binding['document_sha256'],409,'document_changed','The source document changed.')
        self._check(case_id,review_id,binding,grant)
        kind=saved['review']['document']['format']
        media={'pdf':'application/pdf','txt':'text/plain','docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}[kind]
        name=quote(saved['review']['document']['source_name'],safe='')
        return Response(content,media_type=media,headers={'Cache-Control':'no-store, private','X-Content-Type-Options':'nosniff',
            'Content-Disposition':"inline; filename*=UTF-8''"+name})

    def source(self,case_id: str,review_id: str,source_id: str):
        with self.ctx.repo.transaction() as db:binding,saved,grant,path=self._grant(db,case_id,review_id)
        row=ContractIndex(path,case_id,review_id,digest(binding)).source(source_id)
        require(row and row['case_id']==case_id and row['review_id']==review_id and row['document_version']==digest(binding),404,'not_found','The clause is not in the currently authorized contract.')
        self._check(case_id,review_id,binding,grant);return row

    def chat_answer(self,case_id,question):
        with self.ctx.repo.transaction() as db:
            case=self.ctx.get(db,'case',case_id);latest=case['reviews'][-1]['review_id'] if case['reviews'] else None
        if latest:
            try:
                status=self.status(case_id,latest)
                if status['status']=='ready':
                    result=self.answers(case_id,latest,{'question':question,'allow_external_ai':status['allow_external_ai'],'context_token':status['context_token'],
                        'language':'en'})
                    return {'intent':'contract','agent':'agent3','content':result['answer'],'knowledge':result,'listings':[],'actions':[]}
            except ApiError as error:
                if error.status not in (403,409):raise
        return {'intent':'contract','agent':'agent3','content':'Upload a PDF, DOCX or TXT agreement here. You can start before selecting a property. Consent to contract processing to extract key terms and items to check. For questions about the original text, separately enable contract search and choose whether AI may process relevant excerpts.',
                'listings':[],'actions':[{'type':'navigate','label':'View contract review','page':'contract?mode=review'}]}


def register_contract_rag_routes(app,ctx):
    service=ctx.contract_knowledge;base='/api/v1/cases/{case_id}/rag/contracts/{review_id}'
    app.get(base+'/status')(service.status);app.get(base+'/document')(service.document);app.post(base+'/index')(service.index)
    app.post(base+'/revoke')(service.revoke);app.post(base+'/search')(service.search)
    app.post(base+'/answers')(service.answers);app.get(base+'/sources/{source_id}')(service.source)
