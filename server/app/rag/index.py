"""Small-corpus SQLite FTS and exact cosine store with atomic snapshot publication."""
import hashlib, json, math, re, sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from .provider import valid_vector

GOVERNMENT_HOSTS={'www.nsw.gov.au','www.service.nsw.gov.au','www.fairtrading.nsw.gov.au'}
PUBLIC_HOSTS=GOVERNMENT_HOSTS|{'www.sydney.edu.au'}
PUBLIC_TYPES={'official_guidance','official_template','student_guidance','product_guide'}
STOP=set('a an the is are i my do does how can what to of in on for and or with it this that as be me at get about should'.split())
BRIDGE={'押金':'bond refund','退租':'ending tenancy notice','报修':'repair maintenance','维修':'repair maintenance','合同':'tenancy agreement','清洁':'cleaning','房东':'landlord','中介':'agent','租金':'rent'}


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def terms(query):
    expanded=query+' '+' '.join(v for k,v in BRIDGE.items() if k in query)
    return list(dict.fromkeys(t for t in re.findall(r'[a-z0-9]+',expanded.casefold()) if t not in STOP and len(t)>1))[:30]


def chunks(document):
    section=document['title'];parents=[];parts=[];body=[]
    def flush():
        text='\n'.join(body).strip()
        if text:parts.append((section,[value for level,value in parents] or [section],text))
        body.clear()
    for line in document['text'].splitlines():
        heading=re.match(r'^(#{1,6})\s+(.+)',line)
        if heading:
            flush();level=len(heading[1]);section=heading[2].strip()
            while parents and parents[-1][0]>=level:parents.pop()
            parents.append((level,section))
        else:body.append(line)
    flush()
    for section,path,text in parts:
        groups=[];current=''
        for paragraph in text.split('\n\n'):
            if current and len(current)+len(paragraph)>6500:groups.append(current);current=''
            if len(paragraph)>16000:raise ValueError('Section needs manual paragraph review')
            current+=(('\n\n' if current else '')+paragraph)
        if current:groups.append(current)
        for number,group in enumerate(groups):
            context=' > '.join(path)
            embedding_text=document['title']+' > '+context+'\n'+group
            identifier=digest('section-context-v2\0'+document['document_id']+'\0'+context+'\0'+str(number)+'\0'+group)[:32]
            row={'chunk_id':identifier,**{k:v for k,v in document.items() if k!='text'},'section':section,
                'section_path':path,'embedding_input_version':'section-context-v2','embedding_text':embedding_text,'text':group,'content_hash':digest(embedding_text)}
            if document.get('download_url'):
                page=next((int(m[1]) for label in path if (m:=re.fullmatch(r'Page (\d+)',label))),None)
                if page and page<=document.get('page_count',0):
                    row.update(page=page,document_url=document['download_url']+'#page='+str(page))
            elif document.get('source_type')=='product_guide':
                row['document_url']=document['source_url']+'?version='+document['document_version']
            yield row


class KnowledgeIndex:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS keywords USING fts5(id UNINDEXED,text,tokenize="porter unicode61")')
            db.execute('CREATE TABLE IF NOT EXISTS vectors(id TEXT,model TEXT,dimensions INTEGER,body TEXT, PRIMARY KEY(id,model,dimensions))')
            db.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15)
        try:
            with db:yield db
        finally:db.close()

    def prepare(self,documents):
        result=[];seen=set()
        for d in documents:
            if not isinstance(d,dict) or d.get('case_id') is not None or d.get('scope','public')!='public':raise ValueError('Only public knowledge can be indexed')
            if (not isinstance(d.get('document_id'),str) or d['document_id'] in seen or d.get('language')!='en'
                or not isinstance(d.get('text'),str) or not d['text'].strip() or len(d['text'])>500000):raise ValueError('Invalid public document')
            kind=d.get('source_type')
            if kind=='product_guide':
                from .product_guide import validate_product_document
                validate_product_document(d)
            else:
                if kind not in PUBLIC_TYPES-{'product_guide'} or d.get('jurisdiction')!='NSW':raise ValueError('Invalid public document role')
                from .provenance import validate_registered_identity
                validate_registered_identity(d)
                def approved_url(value):
                    if not isinstance(value,str):raise ValueError('Missing source URL')
                    url=urlsplit(value)
                    hosts={'www.sydney.edu.au'} if kind=='student_guidance' else GOVERNMENT_HOSTS
                    if url.scheme!='https' or url.hostname not in hosts or url.username or url.password or url.fragment:raise ValueError('Unapproved source URL')
                approved_url(d.get('source_url'))
                if 'document_url' in d:raise ValueError('Document links are derived from validated provenance')
                if d.get('download_url'):
                    approved_url(d['download_url'])
                    if type(d.get('page_count')) is not int or not 1<=d['page_count']<=100:raise ValueError('Invalid PDF page count')
            date.fromisoformat(d['checked_at']);seen.add(d['document_id'])
            result.extend(chunks(d))
        return result

    def publish(self,documents,vectors=None,model=None,dimensions=None):
        rows=self.prepare(documents);version=digest(json.dumps(rows,sort_keys=True))
        if vectors is not None and (len(vectors)!=len(rows) or not all(valid_vector(v,dimensions) for v in vectors)):raise ValueError('Invalid vectors')
        with self.connect() as db:
            if db.execute('SELECT value FROM metadata WHERE key="index_version"').fetchone()==(version,) and vectors is None:return
            db.execute('DELETE FROM chunks');db.execute('DELETE FROM keywords')
            for row in rows:
                db.execute('INSERT INTO chunks VALUES (?,?)',(row['chunk_id'],json.dumps(row)))
                db.execute('INSERT INTO keywords VALUES (?,?)',(row['chunk_id'],' > '.join(row.get('section_path',[row['section']]))+'\n'+row['text']))
            db.execute('DELETE FROM vectors WHERE id NOT IN (SELECT id FROM chunks)')
            if vectors is not None:
                db.executemany('INSERT OR REPLACE INTO vectors VALUES (?,?,?,?)',[(r['chunk_id'],model,dimensions,json.dumps(v)) for r,v in zip(rows,vectors)])
            db.execute('INSERT OR REPLACE INTO metadata VALUES ("index_version",?)',(version,))

    def status(self):
        with self.connect() as db:
            version=db.execute('SELECT value FROM metadata WHERE key="index_version"').fetchone()
            rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM chunks')]
            vectors=db.execute('SELECT model,dimensions,count(*) FROM vectors GROUP BY model,dimensions').fetchall()
        return {'knowledge_language':'en','scope':'public','jurisdiction':'NSW','document_count':len({r['document_id'] for r in rows}),
                'chunk_count':len(rows),'index_version':version[0] if version else None,
                'jurisdictions':sorted({r['jurisdiction'] for r in rows}),
                'source_breakdown':[{'source_type':kind,'documents':len({r['document_id'] for r in rows if r['source_type']==kind}),'chunks':count}
                    for kind,count in sorted(Counter(r['source_type'] for r in rows).items())],
                'vector_indexes':[{'model':m,'dimensions':d,'chunks':n} for m,d,n in vectors]}

    def search(self,query,limit=20,*,source_types=None):
        tokens=terms(query)
        if not tokens or source_types==():return []
        expression=' OR '.join('"'+t+'"' for t in tokens)
        clause='';parameters=[expression]
        if source_types is not None:
            if not source_types:return []
            clause=' AND json_extract(c.body, \'$.source_type\') IN ('+','.join('?' for _ in source_types)+')'
            parameters.extend(source_types)
        parameters.append(limit)
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT c.body FROM keywords k JOIN chunks c ON c.id=k.id WHERE keywords MATCH ?'+clause+' ORDER BY bm25(keywords) LIMIT ?',parameters)]

    def source(self,identifier):
        with self.connect() as db:
            row=db.execute('SELECT body FROM chunks WHERE id=?',(identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_vectors(self,ids,vectors,model,dimensions):
        if len(ids)!=len(vectors) or not all(valid_vector(v,dimensions) for v in vectors):raise ValueError('Invalid vectors')
        with self.connect() as db:
            if any(not db.execute('SELECT 1 FROM chunks WHERE id=?',(i,)).fetchone() for i in ids):raise ValueError('Stale chunk')
            db.executemany('INSERT OR REPLACE INTO vectors VALUES (?,?,?,?)',[(i,model,dimensions,json.dumps(v)) for i,v in zip(ids,vectors)])

    def vector_search(self,query,model,dimensions,limit=20,*,source_types=None):
        if not valid_vector(query,dimensions):raise ValueError('Invalid query vector')
        norm=math.sqrt(sum(x*x for x in query));scored=[]
        with self.connect() as db:
            for body,raw in db.execute('SELECT c.body,v.body FROM chunks c JOIN vectors v ON v.id=c.id WHERE v.model=? AND v.dimensions=?',(model,dimensions)):
                row=json.loads(body)
                if source_types is not None and row.get('source_type') not in source_types:continue
                vector=json.loads(raw)
                score=sum(x*y for x,y in zip(query,vector))/(norm*math.sqrt(sum(x*x for x in vector)))
                if score>.3:scored.append((score,row))
        return [r for score,r in sorted(scored,key=lambda pair:pair[0],reverse=True)[:limit]]
