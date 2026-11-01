#!/usr/bin/env python3
"""Offline, backed-up cleanup of local test reports. Defaults to a read-only plan."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,shutil,sqlite3
from pathlib import Path
import sys
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parents[1]

@contextmanager
def connection(*args,**kwargs):
    db=sqlite3.connect(*args,**kwargs)
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:db.close()

def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False)
def signature(db,schema='main'):
    tables=[r[0] for r in db.execute(f"select name from {schema}.sqlite_master where type='table' order by name")]
    rows=[]
    for table in tables:
        quoted=table.replace('"','""')
        rows.append((table,db.execute(f'SELECT * FROM {schema}."{quoted}" ORDER BY rowid').fetchall()))
    return hashlib.sha256(encoded(rows).encode()).hexdigest()

def read_objects(db):return {(kind,key):json.loads(raw) for kind,key,raw in db.execute('select kind,id,body from objects')}
def safe_tree(path):
    if path.is_symlink() or path.exists() and any(p.is_symlink() for p in path.rglob('*')):
        raise ValueError('Refusing symlinked runtime content')
def private_redaction(value,removed):
    changed=False
    if not isinstance(value,dict):return False
    conversation=value if 'messages' in value else value.get('result',{})
    if not isinstance(conversation,dict):return False
    for entry in conversation.get('messages',[]):
        marker=entry.get('knowledge',{}).get('private_binding',{})
        if marker.get('review_id') in removed:
            entry['content']='The test contract review and its private evidence were cleared. Upload a contract and grant consent again to ask about it.'
            entry['knowledge']={**entry['knowledge'],'answer':entry['content'],'status':'sources_only','claims':[],'citations':[],
              'unknowns':[],'warnings':['The original test contract and its private index were cleared.']}
            changed=True
    if changed and 'revision' in conversation:conversation['revision']+=1
    return changed

def maintain(runtime,*,apply=False,backup_root=None):
    original=Path(runtime).absolute()
    if original.is_symlink():raise ValueError('Refusing symlinked runtime')
    for path in original.glob('*.sqlite3'):
        if path.is_symlink():raise ValueError('Refusing symlinked runtime database')
    runtime=original.resolve()
    if not (runtime/'web.sqlite3').is_file():raise ValueError('Choose an existing rental runtime with web.sqlite3')
    for folder in ('uploads','living-files','rag-private'):safe_tree(runtime/folder)
    with connection(f'file:{runtime/"web.sqlite3"}?mode=ro',uri=True) as db:
        objects=read_objects(db);expected={'main':signature(db)}
    reviews={key for kind,key in objects if kind=='review'}
    reports=[v for (kind,_),v in objects.items() if kind=='issue_report']
    protected='\n'.join(encoded(v) for (kind,_),v in objects.items() if kind in ('living_services','lease_draft'))
    legacy={};affected_aftercare=set()
    aftercare=runtime/'aftercare.sqlite3'
    if aftercare.exists():
        with connection(f'file:{aftercare}?mode=ro',uri=True) as db:
            expected['aftercare']=signature(db)
            for key,raw in db.execute('select case_id,document from cases'):
                value=json.loads(raw)
                if value.get('reviews'):
                    reports.extend(r for r in value['reviews'] if r.get('report'))
                    changed=json.loads(raw);changed['reviews']=[]
                    # Independent bond facts/outcomes and their evidence are not
                    # report caches. Keep them and all restrictions they imply.
                    protected+='\n'+encoded({k:v for k,v in changed.items() if k not in ('evidence','audit')})
                    changed['version']+=1
                    legacy[key]=changed;affected_aftercare.add(key)
                else:protected+='\n'+encoded(value)
    report_files=set()
    for record in reports:
        report_files.update((record.get('report')or{}).get('attachment_ids',[]))
        for update in record.get('updates',[]):report_files.update(update.get('attachment_ids',[]))
    attachments={key:v for (kind,key),v in objects.items() if kind=='living_attachment'}
    removed_files={key for key,v in attachments.items() if key not in protected and
                   (key in report_files or v.get('metadata',{}).get('purpose')=='moveout')}
    for value in legacy.values():
        keep=encoded({k:v for k,v in value.items() if k not in ('evidence','audit')})
        value['evidence']=[e for e in value.get('evidence',[]) if str(e.get('evidence_id','')) in keep]
        value['audit']=[e for e in value.get('audit',[]) if e.get('operation') not in ('report_issue','reply_review','operator_decision')]
    direct={'review','review_version','contract_receipt','consent','contract_rag_index','contract_rag_receipt',
            'issue_report','issue_report_receipt','issue_advice_receipt'}
    deletes=set();updates={}
    for identity,value in objects.items():
        kind,key=identity
        if kind in direct:deletes.add(identity)
        elif kind in ('ai_analysis','ai_receipt') and (value.get('kind')=='contract' or value.get('binding',{}).get('review_id') in reviews):deletes.add(identity)
        elif kind=='ai_latest' and key.startswith('contract:'):deletes.add(identity)
        elif kind=='case' and value.get('reviews'):
            value['reviews']=[];updates[identity]=value
        elif kind=='living_attachment' and key in removed_files:deletes.add(identity)
        elif kind=='living_attachment_index':
            value['ids']=[i for i in value['ids'] if i not in removed_files];updates[identity]=value
        elif kind=='living_attachment_receipt' and value.get('result',{}).get('attachment_id') in removed_files:deletes.add(identity)
        elif kind=='aftercare_receipt' and value.get('command',{}).get('case_id') in affected_aftercare:deletes.add(identity)
        elif kind in ('assistant_conversation','assistant_turn_receipt') and private_redaction(value,reviews):updates[identity]=value
    # All upload/private-index files belong to contract-check caches; public RAG is separate.
    files=[]
    for folder in ('uploads','rag-private'):
        if (runtime/folder).exists():files.extend(p for p in (runtime/folder).rglob('*') if p.is_file())
    for identifier in removed_files:
        name=attachments[identifier]['file_ref']
        if Path(name).name!=name:raise ValueError('Invalid attachment filename')
        path=runtime/'living-files'/name
        if path.exists():files.append(path)
    if (runtime/'intake.sqlite3').exists():
        with connection(f'file:{runtime/"intake.sqlite3"}?mode=ro',uri=True) as db:expected['intake']=signature(db)
    plan={'remove_objects':dict(Counter(kind for kind,_ in deletes)),
          'removed_upload_files':len(files),'removed_legacy_review_sets':len(legacy),'demo_examples':5,
          'preserved':['profiles','conversations','favorites','selected properties','saved unsigned drafts','repairs','bookings','public RAG','provider catalogue']}
    if not apply:return plan
    backup_root=Path(backup_root or runtime.parent/'.runtime-backups').absolute();safe_tree(backup_root)
    if backup_root.resolve()==runtime or runtime in backup_root.resolve().parents:raise ValueError('Backup must be outside active runtime')
    backup_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=backup_root/('review-cleanup-'+stamp);backup.mkdir(mode=0o700)
    for path in sorted(runtime.glob('*.sqlite3')):
        with connection(f'file:{path}?mode=ro',uri=True) as source,connection(backup/path.name) as target:source.backup(target)
    for folder in ('uploads','living-files','rag-private'):
        if (runtime/folder).exists():shutil.copytree(runtime/folder,backup/folder)
    (backup/'manifest.json').write_text(encoded({**plan,'state':'backed_up','removed_files':[str(p.relative_to(runtime)) for p in files]}))
    with connection(runtime/'web.sqlite3') as db:
        if aftercare.exists():db.execute('attach database ? as aftercare',(str(aftercare),))
        intake=runtime/'intake.sqlite3'
        if intake.exists():db.execute('attach database ? as intake',(str(intake),))
        db.execute('begin exclusive')
        for schema,wanted in expected.items():
            if signature(db,schema)!=wanted:raise RuntimeError('Runtime changed during planning. Stop local services and retry; no cleanup was committed.')
        for kind,key in deletes:db.execute('delete from objects where kind=? and id=?',(kind,key))
        for (kind,key),value in updates.items():db.execute('update objects set body=? where kind=? and id=?',(encoded(value),kind,key))
        for key,value in legacy.items():db.execute('update aftercare.cases set document=? where case_id=?',(encoded(value),key))
        if aftercare.exists():
            for actor,request,raw in db.execute('select actor_id,request_id,response from aftercare.receipts').fetchall():
                if json.loads(raw).get('case_id') in affected_aftercare:db.execute('delete from aftercare.receipts where actor_id=? and request_id=?',(actor,request))
        if intake.exists():db.execute('delete from intake.intake_requests')
        examples=json.loads((ROOT/'server/app/adapters/review_examples.json').read_text())
        db.execute("delete from objects where kind='review_demo'")
        for item in examples:db.execute('insert into objects values(?,?,?)',('review_demo',item['review_id'],encoded(item)))
        db.commit()
        if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise RuntimeError('Database integrity check failed; restore the saved backup')
    for path in files:path.unlink()
    result={**plan,'backup':str(backup),'applied':True}
    (backup/'manifest.json').write_text(encoded({**result,'state':'complete','removed_files':[str(p.relative_to(runtime)) for p in files]}))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--runtime-dir',required=True);parser.add_argument('--apply',action='store_true');parser.add_argument('--backup-root')
    args=parser.parse_args();print(json.dumps(maintain(args.runtime_dir,apply=args.apply,backup_root=args.backup_root),indent=2))
