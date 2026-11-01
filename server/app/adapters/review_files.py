"""Case-scoped file references for local human review; uploaded bytes stay local."""
from ..common import require


def validate_review_files(ctx, db, case_id, identifiers):
    require(isinstance(identifiers,list) and len(identifiers)<=10 and
            all(isinstance(identifier,str) for identifier in identifiers) and
            len(set(identifiers))==len(identifiers),422,'invalid_input','Choose up to 10 evidence files.')
    for identifier in identifiers:
        saved=ctx.get(db,'living_attachment',identifier)
        require(saved['case_id']==case_id,404,'not_found','Evidence file not found for this case.')


def review_files(ctx, case_id, review):
    identifiers=list(dict.fromkeys((review.get('report') or {}).get('attachment_ids',[])+
                    [identifier for update in review.get('updates',[]) for identifier in update.get('attachment_ids',[])]))
    with ctx.repo.transaction() as db:
        files=[]
        for identifier in identifiers:
            saved=ctx.repo.get(db,'living_attachment',identifier)
            if saved and saved['case_id']==case_id:files.append(saved['metadata'])
    return files
