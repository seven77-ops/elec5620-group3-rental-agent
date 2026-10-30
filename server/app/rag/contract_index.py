"""Physically scoped private contract chunks with page/clause/extracted-line provenance."""
import hashlib,json,re,sqlite3
from contextlib import contextmanager
from ..common import ApiError,require
from .index import KnowledgeIndex,digest
from .provider import valid_vector


def contract_chunks(document,case_id,review_id,version,token,source_url):
    rows=[];page=1;section='Contract text';start=1;buffer=[];size=0
    def flush():
        nonlocal buffer,size
        if not buffer:return
        text='\n'.join(value for _,value in buffer).strip()
        if text:
            first,last=buffer[0][0],buffer[-1][0]
            identifier=digest(token+'\0'+str(page)+'\0'+str(first)+'\0'+text)[:32]
            rows.append({'chunk_id':identifier,'document_id':review_id,'case_id':case_id,'review_id':review_id,
                'review_version':version,'document_version':token,'document_hash':document['sha256'],
                'source_type':'user_contract','title':document['source_name'],'source_url':source_url+'/'+identifier,
                'document_url':source_url.rsplit('/sources',1)[0]+'/document?context_token='+token+'#page='+str(page),
                'section':section,'page':page,'line_start':first,'line_end':last,'language':'original',
                'text':text,'content_hash':digest(text),'checked_at':None})
        buffer=[];size=0
    for number,line in enumerate(document['text'].splitlines(),1):
        marker=re.fullmatch(r'\[page (\d+)\]',line)
        if marker:
            flush();page=int(marker[1]);section='Contract text';continue
        heading=re.match(r'^(?:\d+(?:\.\d+)*[.)]?\s+[A-Za-z][^.!?]{0,90}|[A-Z][A-Za-z /&-]{1,60}:)$',line.strip())
        if heading:flush();section=line.strip()
        # Keep exact source substrings; long lines are split only at whitespace.
        parts=[];remaining=line
        while len(remaining)>1400:
            end=remaining.rfind(' ',0,1400)
            if end<1:end=1400
            parts.append(remaining[:end]);remaining=remaining[end:]
        parts.append(remaining)
        for part in parts:
            if buffer and size+len(part)>1600:flush()
            buffer.append((number,part));size+=len(part)+1
    flush();return rows


class ContractIndex(KnowledgeIndex):
    def __init__(self,path,case_id,review_id,token,*,create=False):
        self.case_id,self.review_id,self.token=case_id,review_id,token
        self.read_only=not create
        if create:super().__init__(path)
        else:
            from pathlib import Path
            self.path=Path(path)
            require(self.path.is_file() and not self.path.is_symlink(),409,'contract_index_missing','The authorized private index is no longer available.')

    @contextmanager
    def connect(self):
        if not self.read_only:
            with super().connect() as db:yield db
            return
        try:db=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=15)
        except sqlite3.OperationalError:raise ApiError(409,'contract_index_missing','The authorized private index is no longer available.') from None
        try:yield db
        finally:db.close()

    def publish_rows(self,rows,vectors=None,model=None,dimensions=None):
        if (not rows or len({r['chunk_id'] for r in rows})!=len(rows) or any(r.get('case_id')!=self.case_id or
            r.get('review_id')!=self.review_id or r.get('document_version')!=self.token for r in rows)):
            raise ValueError('Private index scope mismatch')
        if vectors is not None and (len(vectors)!=len(rows) or not all(valid_vector(v,dimensions) for v in vectors)):
            raise ValueError('Invalid private vectors')
        with self.connect() as db:
            db.execute('DELETE FROM chunks');db.execute('DELETE FROM keywords');db.execute('DELETE FROM vectors')
            for row in rows:
                db.execute('INSERT INTO chunks VALUES (?,?)',(row['chunk_id'],json.dumps(row)))
                db.execute('INSERT INTO keywords VALUES (?,?)',(row['chunk_id'],row['section']+'\n'+row['text']))
            if vectors is not None:db.executemany('INSERT INTO vectors VALUES (?,?,?,?)',[(r['chunk_id'],model,dimensions,json.dumps(v)) for r,v in zip(rows,vectors)])
            db.execute('INSERT OR REPLACE INTO metadata VALUES ("index_version",?)',(self.token,))

    def status(self):
        with self.connect() as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM chunks')]
            vectors=db.execute('SELECT model,dimensions,count(*) FROM vectors GROUP BY model,dimensions').fetchall()
        if any(r.get('case_id')!=self.case_id or r.get('review_id')!=self.review_id or r.get('document_version')!=self.token for r in rows):
            raise ValueError('Private index scope mismatch')
        return {'chunk_count':len(rows),'page_count':len({r['page'] for r in rows}),
                'index_version':self.token,'vector_indexes':[{'model':m,'dimensions':d,'chunks':n} for m,d,n in vectors]}
