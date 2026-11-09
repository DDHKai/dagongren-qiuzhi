"""Local candidate evidence IDs. Never publish the salt, facts, or source data."""
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from review_store import add_shared_source,setup,save_review

def extract_facts(resume,salt,source_hash):
    facts=[]
    for i,exp in enumerate(resume.get('experiences',[])):
        for field in ['responsibilitiesRaw','achievementsRaw']:
            for text in (exp.get(field) or '').splitlines():
                text=text.strip()
                if not text or text in {'内容：','业绩：'}:continue
                # Stable for identical evidence in the same experience; edits get new IDs.
                identity=json.dumps([i,field,text],ensure_ascii=False,separators=(',',':'))
                fact_id='fact_'+hmac.new(salt,identity.encode(),hashlib.sha256).hexdigest()[:24]
                facts.append({'id':fact_id,'sourceHash':source_hash,'path':f'experiences.{i}.{field}', 'quote':text,'status':'candidate-unconfirmed'})
    return facts

def migrate(db,root,run_id='round-2026-11-07'):
    root=Path(root);setup(db)
    salt_path=root/'data/private/fact-id-salt'
    salt_path.parent.mkdir(parents=True,exist_ok=True)
    if not salt_path.exists():
        with salt_path.open('xb') as file:file.write(secrets.token_bytes(32))
    resume=json.loads((root/'data/resume-trial/resume.structured.json').read_text(encoding='utf-8'))
    source=add_shared_source(db,run_id,resume,'candidate')
    facts=extract_facts(resume,salt_path.read_bytes(),source)
    by_id={f['id']:f for f in facts}
    rows=db.execute("SELECT payload FROM reviews WHERE run_id=? AND status='draft'",(run_id,)).fetchall()
    migrated=[]
    for row in rows:
        review=json.loads(row[0])
        if review.get('origin')!='legacy-manual-sample':continue
        claim=review['claims'][0]
        # Candidate retrieval suggestions only; not an automatic semantic verdict.
        themes=[t for t in ['AI','数据','团队','天猫','投放','服装'] if t in claim['text']]
        selected=[f for f in facts if any(t in f['quote'] for t in themes)][:4]
        claim['candidateFactIds']=[f['id'] for f in selected]
        claim['evidence'] += [{k:f[k] for k in ['sourceHash','path','quote']} for f in selected]
        claim['rationale']='候选人证据按主题检索挂接，尚需逐项确认因果与充分性；不能把工具使用视为专业项目经验。'
        review['origin']='candidate-linked-draft'
        review['candidateFacts']={f['id']:by_id[f['id']] for f in selected}
        saved=save_review(db,review)
        migrated.append({'reviewId':saved,'jobId':review['jobId'],'candidateFactIds':claim['candidateFactIds'],'status':'draft'})
    output={'facts':facts,'reviews':migrated,'semanticVerified':0}
    (root/'data/private/candidate-evidence.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'facts':len(facts),'linkedDrafts':len(migrated),'semanticVerified':0}

if __name__=='__main__':
    from project_store import ROOT,connect
    with connect(ROOT/'data/project.sqlite3') as db:print(json.dumps(migrate(db,ROOT)))
