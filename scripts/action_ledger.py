"""Local, scoped manual-handoff ledger. Never clicks, sends or uploads to a platform."""
from datetime import datetime,timezone
from contextlib import contextmanager
import json
import re
import secrets
import sqlite3
from urllib.parse import urlsplit
from ability_review import hash_json
from prescreen_jobs import run as prescreen

def stamp():return datetime.now(timezone.utc).timestamp()
def job_id(value):
    u=urlsplit(value)
    if u.scheme!='https' or u.netloc!='www.zhipin.com' or not re.fullmatch(r'/job_detail/[^/]+\.html',u.path) or u.query or u.fragment:raise ValueError('Canonical job required')
    return value

def favorite_state(observation):
    controls=observation.get('controls',{});state=controls.get('favorite','unknown')
    if state=='unknown':return state
    if controls.get('basis')=='favorite-control-v1':
        control=controls.get('control',{});label=control.get('label');kind=control.get('kind')
        if kind=='boss-interest' and label=='取消感兴趣' and control.get('active') is True:expected='collected'
        elif kind=='boss-interest' and label in ('感兴趣','已感兴趣'):expected='collected' if label=='已感兴趣' else 'unknown' if control.get('active') is True else 'not-collected'
        elif kind=='explicit-favorite' and label in ('收藏','已收藏'):expected='collected' if label=='已收藏' else 'not-collected'
        else:raise ValueError('Ambiguous favorite control')
        if expected!=state or label not in observation['job']['source']['text']:raise ValueError('Control evidence mismatch')
        return expected
    labels=controls.get('labels',[])
    if controls.get('basis')!='exact-label-in-job-header-only' or not isinstance(labels,list) or any(not isinstance(x,str) for x in labels):raise ValueError('Scoped control evidence required')
    expected='collected' if labels.count('已收藏')==1 and '收藏' not in labels else 'not-collected' if labels.count('收藏')==1 and '已收藏' not in labels else 'unknown'
    if state!=expected:raise ValueError('Ambiguous or contradictory control evidence')
    label='已收藏' if state=='collected' else '收藏'
    if label not in observation['job']['source']['text']:raise ValueError('Control label absent from observed page text')
    return state

class Ledger:
    def __init__(self,path):
        self.path=path
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,job_id TEXT NOT NULL,action TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL,event TEXT NOT NULL,at REAL NOT NULL,payload TEXT NOT NULL);''')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db:yield db
        finally:db.close()
    def event(self,db,task,event,payload):db.execute('INSERT INTO events(task_id,event,at,payload) VALUES(?,?,?,?)',(task,event,stamp(),json.dumps(payload,ensure_ascii=False)))
    def list(self,case_id):
        with self.connect() as db:
            result=[json.loads(x[0]) for x in db.execute('SELECT payload FROM tasks WHERE case_id=? ORDER BY rowid DESC',(case_id,))]
        for r in result:r['expired']=r['expiresAt']<stamp()
        return result
    def get(self,db,ident,case_id):
        row=db.execute('SELECT payload FROM tasks WHERE id=? AND case_id=?',(ident,case_id)).fetchone()
        if not row:raise ValueError('Task outside case')
        return json.loads(row[0])
    def put(self,db,r):db.execute('UPDATE tasks SET state=?,payload=? WHERE id=?',(r['state'],json.dumps(r,ensure_ascii=False),r['id']))
    def authorize(self,case_id,report,report_version,items,confirmed,binding=None):
        if confirmed is not True or not isinstance(items,list) or not 1<=len(items)<=20:raise ValueError('Explicit batch of 1-20 required')
        rows={r['jobId']:r for r in report['jobs']};seen=set();created=[];now=stamp()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for item in items:
                if not isinstance(item,dict) or set(item)!={'jobId','action'}:raise ValueError('Message, attachment and implicit scope are not supported')
                jid=job_id(item['jobId']);action=item['action'];key=(jid,action)
                if action not in ('favorite-manual','favorite') or key in seen:raise ValueError('Only favorite supported; contact and resume are upgrade-only')
                if action=='favorite' and (not binding or binding['expiresAt']<now):raise ValueError('Current account binding required')
                seen.add(key);row=rows.get(jid)
                if row is None or not row['selection']['selected']:raise ValueError('Choose this job in current shortlist first')
                for old, in db.execute("SELECT payload FROM tasks WHERE job_id=? AND action IN ('favorite','favorite-manual')",(jid,)):
                    prior=json.loads(old)
                    if binding and prior.get('accountFingerprint') and prior['accountFingerprint']!=binding['account']['fingerprint']:continue
                    if prior['state'] in ('awaiting-user-action','ready-to-execute','executing','outcome-unknown','observed-favorite','confirmed-favorite') or prior['state']=='authorized' and prior['expiresAt']>now:raise ValueError('Existing action or uncertain outcome; reconcile first, no repeat')
                ident=secrets.token_hex(16);r={'id':ident,'caseId':case_id,'jobId':jid,'companyId':row['companyId'],'jobTitle':row['jobTitle'],'companyName':row['companyName'],
                    'action':action,'state':'authorized','authorizationMode':'manual-handoff-only','reportVersion':report_version,'contextHash':report['contextHash'],
                    'createdAt':now,'expiresAt':now+1800,'platformState':'not-observed','systemExecuted':False,'messageSent':'not-verified','attachmentSent':'not-authorized'}
                if action=='favorite':r.update(authorizationMode='favorite-only',bindingId=binding['id'],accountFingerprint=binding['account']['fingerprint'],browserFingerprint=binding['account']['browserFingerprint'])
                db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?)',(ident,case_id,jid,action,r['state'],json.dumps(r,ensure_ascii=False)));self.event(db,ident,'authorized',{'reportVersion':report_version,'action':action,'jobId':jid});created.append(r)
        return created
    def fresh(self,observation,task):
        if not isinstance(observation,dict) or observation.get('kind')!='read-only-job-observation' or observation.get('schemaVersion')!=1:raise ValueError('Read-only observation required')
        source=observation['job']['source']
        if observation['job']['id']!=task['jobId'] or source['url']!=task['jobId'] or job_id(source['url'])!=task['jobId']:raise ValueError('Wrong observed job')
        dt=datetime.fromisoformat(source['capturedAt'].replace('Z','+00:00'))
        if dt.tzinfo is None or not -30<=stamp()-dt.timestamp()<=300:raise ValueError('Observation too old or future-dated')
        text=source['text']
        if not isinstance(text,str) or not text.strip() or re.search('环境存在异常|安全验证|访问过于频繁|请完成验证|登录查看完整内容|请登录后查看|登录/注册',text):raise ValueError('Login, platform check or incomplete observation')
        if observation['job'].get('companyKey')!=task['companyId']:raise ValueError('Company relationship changed or unavailable')
        if task.get('accountFingerprint') and any(observation.get('account',{}).get(k)!=task[v] for k,v in [('fingerprint','accountFingerprint'),('browserFingerprint','browserFingerprint')]):raise ValueError('Account or browser changed')
        company=observation.get('company')
        if not company or company.get('id')!=task['companyId']:raise ValueError('Fresh company observation required')
        cu=urlsplit(company['source']['url']);ct=datetime.fromisoformat(company['source']['capturedAt'].replace('Z','+00:00'))
        if cu.scheme!='https' or cu.netloc!='www.zhipin.com' or cu.path!=task['companyId'] or ct.tzinfo is None or not -30<=stamp()-ct.timestamp()<=300:raise ValueError('Stale or wrong company observation')
        return dt.timestamp()
    def begin(self,case_id,ident,report,report_version,checkpoint,observation):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.get(db,ident,case_id)
            if r['state']!='authorized' or r['expiresAt']<stamp() or r['contextHash']!=report['contextHash'] or r['reportVersion']!=report_version:raise ValueError('Authorization expired, consumed or evidence changed')
            self.fresh(observation,r)
            favorite=favorite_state(observation)
            if r['action']=='favorite' and favorite=='unknown':raise ValueError('Favorite control unverified')
            if r['action'] not in ('favorite','favorite-manual'):raise ValueError('Contact is upgrade-only; no new handoff')
            refreshed=prescreen({'jobs':[observation['job']],'companies':[observation['company']] if observation.get('company') else []},report['policy'])['jobs'][0]
            old=next(x for x in report['jobs'] if x['jobId']==r['jobId'])
            if not old['selection']['selected']:raise ValueError('Job no longer selected')
            simple=lambda row:{k:{'status':v['status'],'quotes':[x['quote'] for x in v['evidence']]} for k,v in row['dimensions'].items()}
            if simple(old)!=simple(refreshed) or refreshed.get('jobTitle')!=old['jobTitle']:raise ValueError('Conditions changed; update evidence and choose again')
            prior=next(x for x in checkpoint['jobs'] if x['id']==r['jobId'])
            def jd(job):
                text=job['source']['text'];start=text.find('职位描述')
                if start<0:raise ValueError('No scoped description')
                end=min([p for marker in ('竞争力分析','BOSS 安全提示','更多职位','看过该职位的人还看了') if (p:=text.find(marker,start+1))>=0] or [len(text)])
                return re.sub(r'\s+',' ',text[start:end]).strip()
            if jd(prior)!=jd(observation['job']):raise ValueError('Job duties changed; review again')
            r.update(state='ready-to-execute' if r['action']=='favorite' else 'awaiting-user-action',startedAt=stamp(),beforeHash=hash_json(observation),beforeObservation=observation)
            if favorite=='collected':
                r.update(state='observed-favorite',platformState='favorite-observed',observedAt=self.fresh(observation,r),outcomeMeaning='开始前已观察到收藏，不重复操作；未由本系统点击。')
            self.put(db,r);self.event(db,ident,'manual-handoff-started',{'beforeHash':r['beforeHash']})
            return r
    def finish(self,case_id,ident,observation,reviewed):
        if reviewed is not True:raise ValueError('Explicit observed-evidence review required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.get(db,ident,case_id)
            if r['state'] not in ('awaiting-user-action','outcome-unknown','executing'):raise ValueError('No outstanding attempt to reconcile')
            when=self.fresh(observation,r)
            if when<=r['startedAt'] or hash_json(observation)==r['beforeHash']:raise ValueError('Need a new observation after handoff')
            favorite=favorite_state(observation)
            r.update(state='observed-favorite' if r['action'] in ('favorite','favorite-manual') and favorite=='collected' else 'outcome-unknown',
                platformState='favorite-observed' if favorite=='collected' else 'not-favorite-observed' if favorite=='not-collected' else 'unknown',
                observedAt=when,afterHash=hash_json(observation),afterObservation=observation,
                outcomeMeaning='仅观察到平台收藏状态，不证明由本系统执行，也不证明已发送消息；未知不自动重试。')
            self.put(db,r);self.event(db,ident,'observation-recorded',{'afterHash':r['afterHash'],'state':r['state']});return r
    def cancel(self,case_id,ident):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.get(db,ident,case_id)
            if r['state'] not in ('authorized','ready-to-execute'):raise ValueError('Cannot cancel an uncertain external outcome as if nothing happened')
            r['state']='cancelled';self.put(db,r);self.event(db,ident,'authorization-cancelled',{});return r
    def refused(self,case_id,ident,observation):
        with self.connect() as db:
            self.get(db,ident,case_id);self.event(db,ident,'preflight-rejected',{'observationHash':hash_json(observation),'systemExecuted':False})
    def task(self,case_id,ident):
        with self.connect() as db:return self.get(db,ident,case_id)
    def claim(self,case_id,ident):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.get(db,ident,case_id)
            if r['action']!='favorite' or r['state']!='ready-to-execute' or r['expiresAt']<stamp():raise ValueError('Favorite authorization unavailable')
            r.update(state='executing',attemptId=secrets.token_hex(16),executionStartedAt=stamp());self.put(db,r);self.event(db,ident,'favorite-attempt-claimed',{'attemptId':r['attemptId']});return r
    def complete(self,case_id,ident,result):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');r=self.get(db,ident,case_id)
            if r['state']!='executing':raise ValueError('Favorite attempt already consumed')
            status=result.get('status');observation=result.get('observation')
            if status in ('confirmed-favorite','already-favorite'):
                observation={**observation,'account':result['account']};when=self.fresh(observation,r)
                if favorite_state(observation)!='collected' or when<r['startedAt']:raise ValueError('Favorite outcome not proven')
                if status=='confirmed-favorite' and (result.get('reloadConfirmed') is not True or result.get('clicked') is not True or result.get('attemptId')!=r['attemptId'] or result.get('taskId')!=r['id']):raise ValueError('Missing matching execution and reload proof')
                r.update(state='confirmed-favorite' if status=='confirmed-favorite' else 'observed-favorite',systemExecuted=status=='confirmed-favorite',platformState='favorite-observed',observedAt=when,afterHash=hash_json(observation),afterObservation=observation,reloadConfirmed=result.get('reloadConfirmed',False))
            else:r.update(state='outcome-unknown' if result.get('clickMayHaveOccurred',True) else 'blocked-before-click',failureCode=result.get('code','UNVERIFIED_OUTCOME'))
            self.put(db,r);self.event(db,ident,'favorite-outcome',{'state':r['state'],'systemExecuted':r['systemExecuted']});return r
    def reconcile_reload(self,case_id,ident,result):
        if result.get('status')!='verified-existing-favorite' or result.get('clicked') is not False or result.get('reloadConfirmed') is not True:raise ValueError('Read-only reload proof required')
        observation={**result['observation'],'account':result['account']}
        self.finish(case_id,ident,observation,True)
        with self.connect() as db:
            r=self.get(db,ident,case_id);r.update(reconciliationReloadConfirmed=True,reconciliationProofHash=hash_json(result));self.put(db,r);self.event(db,ident,'favorite-readonly-reconciled',{'proofHash':r['reconciliationProofHash'],'systemExecuted':False});return r
