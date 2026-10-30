"""Bailian retrieval HTTP adapters with shared-key fallback and explicit endpoints."""
import asyncio, json, math, os
from urllib.parse import urlsplit
import httpx
from ..ai.provider import run_transport, strict_json


class RetrievalError(Exception):
    def __init__(self,code,http_status=None):
        self.http_status=http_status
        super().__init__(code)


def valid_vector(vector, dimensions):
    return (isinstance(vector,list) and len(vector)==dimensions and all(
        type(x) in (int,float) and math.isfinite(x) for x in vector) and any(x!=0 for x in vector))


class RetrievalProvider:
    def __init__(self, env=None, transport=None):
        env=os.environ if env is None else env
        generic=any(env.get(k) for k in ('RENTAL_AI_URL','RENTAL_AI_MODEL','RENTAL_AI_API_KEY'))
        chat_key=env.get('RENTAL_AI_API_KEY' if generic else 'AGENT3_MODEL_API_KEY','').strip()
        self.key=env.get('RENTAL_RAG_API_KEY','').strip() or chat_key
        self.embedding_url=env.get('RENTAL_RAG_EMBEDDING_URL','').strip()
        self.rerank_url=env.get('RENTAL_RAG_RERANK_URL','').strip()
        self.model=env.get('RENTAL_RAG_EMBEDDING_MODEL','text-embedding-v4')
        self.rerank_model=env.get('RENTAL_RAG_RERANK_MODEL','qwen3-rerank')
        try:self.dimensions=int(env.get('RENTAL_RAG_DIMENSIONS','1024'))
        except ValueError:self.dimensions=1024
        if self.dimensions not in (64,128,256,512,768,1024,1536,2048):self.dimensions=1024
        self.timeout=6.;self.rerank_timeout=10.;self.transport=transport

    def configured(self,url):
        try:
            parsed=urlsplit(url)
            return bool(self.key and parsed.scheme=='https' and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment)
        except ValueError:return False

    def status(self):
        return {'embedding_configured':self.configured(self.embedding_url),'rerank_configured':self.configured(self.rerank_url),
                'embedding_model':self.model,'rerank_model':self.rerank_model,'dimensions':self.dimensions}

    def request(self,url,payload,timeout=None):
        try:
            value=self.timeout if timeout is None else float(timeout)
            deadline=min(60.,max(1.,value)) if math.isfinite(value) else self.timeout
        except (ValueError,TypeError):deadline=self.timeout
        if not self.configured(url):raise RetrievalError('not_configured')
        async def fetch():
            async with asyncio.timeout(deadline):
                async with httpx.AsyncClient(transport=self.transport,timeout=deadline,follow_redirects=False,trust_env=False) as client:
                    async with client.stream('POST',url,json=payload,headers={'Authorization':'Bearer '+self.key}) as response:
                        if response.status_code!=200:raise RetrievalError('http_error',response.status_code)
                        raw=bytearray()
                        async for part in response.aiter_bytes():
                            if len(raw)+len(part)>2_000_000:raise RetrievalError('response_too_large')
                            raw.extend(part)
                        return strict_json(raw.decode())
        try:return run_transport(fetch(),deadline)
        except RetrievalError:raise
        except (TimeoutError,httpx.TimeoutException):raise RetrievalError('timeout') from None
        except (httpx.HTTPError,ValueError,KeyError,TypeError):raise RetrievalError('invalid_or_unavailable') from None

    def embed(self,texts,*,timeout=None):
        if not isinstance(texts,list) or not 1<=len(texts)<=10 or any(not isinstance(t,str) or not 0<len(t)<=16000 for t in texts):
            raise RetrievalError('invalid_input')
        raw=self.request(self.embedding_url,{'model':self.model,'input':texts,'dimensions':self.dimensions,'encoding_format':'float'},timeout=timeout)
        try:
            rows=raw['data'];indexes=[r['index'] for r in rows]
            if any(type(i) is not int for i in indexes) or sorted(indexes)!=list(range(len(texts))):raise ValueError()
            vectors=[r['embedding'] for r in sorted(rows,key=lambda r:r['index'])]
            if not all(valid_vector(v,self.dimensions) for v in vectors):raise ValueError()
            return vectors
        except (ValueError,TypeError,KeyError):raise RetrievalError('invalid_embedding') from None

    def rerank(self,query,documents):
        if not documents or len(documents)>30:raise RetrievalError('invalid_input')
        raw=self.request(self.rerank_url,{'model':self.rerank_model,'input':{'query':query,'documents':documents},
                    'parameters':{'top_n':len(documents),'return_documents':False}},timeout=self.rerank_timeout)
        try:
            rows=raw['output']['results'];indexes=[r['index'] for r in rows]
            if len(rows)!=len(documents) or sorted(indexes)!=list(range(len(documents))) or any(type(i) is not int for i in indexes):raise ValueError()
            if any(type(r['relevance_score']) not in (int,float) or not math.isfinite(r['relevance_score']) or not 0<=r['relevance_score']<=1 for r in rows):raise ValueError()
            return indexes
        except (ValueError,KeyError,TypeError):raise RetrievalError('invalid_rerank') from None
