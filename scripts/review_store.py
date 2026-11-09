"""Evidence contracts; reference validation is not semantic verification."""
import hashlib
import json
from project_store import canonical

DIMENSIONS={'job_fit','salary','weekend','education','company_growth','industry_outlook'}

def setup(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS shared_evidence(run_id TEXT REFERENCES runs(id), source_hash TEXT REFERENCES sources(hash), role TEXT NOT NULL, PRIMARY KEY(run_id,source_hash));
    CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), job_id TEXT NOT NULL REFERENCES jobs(id), payload TEXT NOT NULL, status TEXT NOT NULL);
    INSERT OR IGNORE INTO schema_version VALUES(2);
    ''')

def add_shared_source(db,run_id,payload,role):
    if role not in {'candidate','public'}:raise ValueError('Invalid source role')
    text=canonical(payload);key=hashlib.sha256(text.encode()).hexdigest()
    with db:
        db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)',(key,text))
        db.execute('INSERT OR IGNORE INTO shared_evidence VALUES(?,?,?)',(run_id,key,role))
    return key

def validate(db,review):
    if review.get('schemaVersion')!='1':raise ValueError('Unknown review schema')
    run,job=review['runId'],review['jobId']
    if not db.execute('SELECT 1 FROM observations WHERE run_id=? AND job_id=?',(run,job)).fetchone():raise ValueError('Job outside run')
    claims=review['claims']
    if not isinstance(claims,list) or not claims:raise ValueError('Empty claims')
    seen=set()
    for claim in claims:
        if not claim.get('id') or claim['id'] in seen:raise ValueError('Duplicate/missing claim ID')
        seen.add(claim['id'])
        if claim.get('dimension') not in DIMENSIONS:raise ValueError('Unknown dimension')
        kind=claim.get('kind')
        if kind not in {'fact','inference','unknown'}:raise ValueError('Unknown claim kind')
        if not isinstance(claim.get('text'),str) or not claim['text'].strip():raise ValueError('Empty claim text')
        refs=claim.get('evidence',[])
        if not isinstance(refs,list):raise ValueError('Invalid evidence list')
        if kind!='unknown' and not refs:raise ValueError('Evidence required')
        if kind=='inference' and not claim.get('rationale'):raise ValueError('Inference rationale required')
        for ref in refs:
            key=ref['sourceHash']
            scoped=db.execute('SELECT 1 FROM observations WHERE run_id=? AND job_id=? AND source_hash=?',(run,job,key)).fetchone()
            shared=db.execute('SELECT role FROM shared_evidence WHERE run_id=? AND source_hash=?',(run,key)).fetchone()
            if not scoped and not shared:raise ValueError('Evidence outside job/run scope')
            row=db.execute('SELECT payload FROM sources WHERE hash=?',(key,)).fetchone()
            value=json.loads(row[0])
            for part in ref['path'].split('.'):
                if isinstance(value,list) and part.isdigit() and int(part)<len(value):
                    value=value[int(part)]
                    continue
                if not isinstance(value,dict) or part not in value:raise ValueError('Invalid evidence path')
                value=value[part]
            quote=ref.get('quote')
            if not isinstance(value,str) or not isinstance(quote,str) or not quote.strip() or quote not in value:raise ValueError('Evidence quote does not match source')
        if kind=='unknown' and not claim.get('reason'):raise ValueError('Unknown reason required')
        for fact_id in claim.get('candidateFactIds',[]):
            fact=review.get('candidateFacts',{}).get(fact_id)
            if not fact or fact.get('id')!=fact_id:raise ValueError('Unresolved candidate fact ID')
            shared=db.execute('SELECT role FROM shared_evidence WHERE run_id=? AND source_hash=?',(run,fact['sourceHash'])).fetchone()
            if not shared or shared[0]!='candidate':raise ValueError('Fact must use candidate source')
            if not any(all(ref.get(k)==fact.get(k) for k in ['sourceHash','path','quote']) for ref in refs):raise ValueError('Fact must have matching validated citation')
    return True

def save_review(db,review):
    validate(db,review)
    # Import and structural validation never certify the meaning of a judgment.
    text=canonical(review);key=hashlib.sha256(text.encode()).hexdigest()
    with db:
        db.execute('INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?)',(key,review['runId'],review['jobId'],text,'draft'))
    return key

def import_legacy(db,run_id,report):
    setup(db);count=0
    for r in report['preferred']+report['reserve']:
        job=r['jobUrl'].split('?',1)[0]
        source=db.execute('SELECT source_hash FROM observations WHERE run_id=? AND job_id=? ORDER BY source_hash LIMIT 1',(run_id,job)).fetchone()
        if not source:raise ValueError('Legacy job outside run')
        payload=json.loads(db.execute('SELECT payload FROM sources WHERE hash=?',source).fetchone()[0])
        text=payload['job']['text'];start=text.index('职位描述');quote=text[start:start+500]
        review={'schemaVersion':'1','runId':run_id,'jobId':job,'origin':'legacy-manual-sample','claims':[{'id':'fit','dimension':'job_fit','kind':'inference','text':r['fitEvidence'],'rationale':'历史人工样本迁移；仅挂接职责上下文，候选人事实逐条引用和语义复核尚未完成','evidence':[{'sourceHash':source[0],'path':'job.text','quote':quote}]}]+[{'id':d,'dimension':d,'kind':'unknown','text':'待结构化证据核对','reason':'旧报告内容已保留，但不能自动将样本结论转为已验证事实','evidence':[]} for d in sorted(DIMENSIONS-{'job_fit'})], 'legacyDecision':{'tier':r['tier'],'gap':r['gap'],'advice':r['communicationAdvice']}}
        save_review(db,review);count+=1
    return {'importedDrafts':count,'semanticVerified':0,'runReviewStatus':'pending'}
