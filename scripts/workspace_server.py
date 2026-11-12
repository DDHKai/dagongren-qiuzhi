"""Private localhost intake UI. No model, telemetry or external actions."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs
from desktop_launcher import ROOT,Server
from resume_workspace import create as intake,confirm,save,validate_conditions
from resume_document import create as extract,apply_mapping
from prescreen_jobs import run as prescreen
from ability_review import generate as ability_generate,review as ability_review,feedback as ability_feedback,load_facts,hash_json
from company_research import capture as finance_capture,review as finance_review,sha as finance_sha,metadata as finance_metadata
from result_report import generate as result_generate,context as result_context,choose as result_choose,reorder as result_reorder,summary as result_summary,html_report
from action_ledger import Ledger

class Workspace:
    def __init__(self,path):
        self.root=Path(path);self.root.mkdir(parents=True,exist_ok=True);self.ledger=Ledger(self.root/'private-actions.sqlite3')
    def folder(self,ident):
        if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('invalid_id')
        p=self.root/ident
        if not p.is_dir():raise ValueError('unknown_id')
        return p
    def listing(self):return sorted(p.name for p in self.root.iterdir() if p.is_dir() and re.fullmatch('[a-f0-9]{32}',p.name))
    def upload(self,payload):
        validate_conditions(payload['conditions'])
        kind=payload['kind']
        if kind not in ('.pdf','.docx','.txt','.json'):raise ValueError('unsupported_file')
        raw=base64.b64decode(payload['data'],validate=True)
        if not raw or len(raw)>10_000_000:raise ValueError('file_size')
        ident=secrets.token_hex(16);p=self.root/ident;p.mkdir()
        source=p/('upload'+kind);source.write_bytes(raw)
        meta={'kind':kind,'versions':[],'status':'importing'};save(p/'case.json',meta)
        save(p/'conditions-initial.json',payload['conditions'])
        try:
            if kind in ('.pdf','.docx'):
                extract(source,p/'document');meta['status']='document-review-required'
            else:
                version=secrets.token_hex(16)
                intake(source,p/'conditions-initial.json',p/version)
                meta['versions'].append(version);meta['status']='facts-review-required'
        except Exception:
            meta['status']='import-failed';save(p/'case.json',meta);raise
        save(p/'case.json',meta);return self.state(ident)
    def state(self,ident):
        p=self.folder(ident);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        result={'id':ident,**meta}
        result['conditions']={'status':'user-review-required','groups':json.loads((p/'conditions-initial.json').read_text(encoding='utf-8'))}
        if (p/'document/extraction.json').exists():result['document']=json.loads((p/'document/extraction.json').read_text(encoding='utf-8'))
        if meta['versions']:
            v=meta['versions'][-1]
            result['facts']=json.loads((p/v/'facts.json').read_text(encoding='utf-8'))['facts']
            result['conditions']=json.loads((p/v/'conditions.json').read_text(encoding='utf-8'))
            result['resume']=json.loads((p/v/'resume.json').read_text(encoding='utf-8'))
        if meta.get('marketReports'):result['marketReport']=json.loads((p/meta['marketReports'][-1]/'report.json').read_text(encoding='utf-8'))
        if meta.get('abilityReports'):
            r=json.loads((p/meta['abilityReports'][-1]/'report.json').read_text(encoding='utf-8'))
            r['stale']=r['candidateVersion']!=meta['versions'][-1] or r['marketVersion']!=meta['marketReports'][-1] or r['context']['candidateFactsHash']!=hash_json(load_facts(p/meta['versions'][-1]))
            result['abilityReport']=r;result['abilityVersion']=meta['abilityReports'][-1]
        if meta.get('researchReports'):
            v=meta['researchReports'][-1];r=json.loads((p/v/'report.json').read_text(encoding='utf-8'))
            r['marketEvidenceChanged']=r.get('marketVersion')!=meta.get('marketReports',[])[-1]
            result['researchReport']=r;result['researchVersion']=v
            capture_version=r.get('captureVersion')
            if capture_version and (p/capture_version/'extraction.json').exists():result['researchDocument']=json.loads((p/capture_version/'extraction.json').read_text(encoding='utf-8'))
        if meta.get('resultReports'):
            v=meta['resultReports'][-1];r=json.loads((p/v/'report.json').read_text(encoding='utf-8'))
            try:r['stale']=r['contextHash']!=result_context(p)['hash']
            except Exception:r['stale']=True
            result.update(resultReport=r,resultVersion=v,resultSummary=result_summary(r))
        result['actionTasks']=self.ledger.list(ident)
        return result
    def authorize_actions(self,payload):
        report=self.checked_result(payload)
        self.ledger.authorize(payload['id'],report,payload['reportVersion'],payload['items'],payload.get('authorizationConfirmed'))
        return self.state(payload['id'])
    def begin_action(self,payload):
        if payload.get('observationReviewed') is not True:raise ValueError('Explicit refresh review required')
        report=self.checked_result(payload);p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        checkpoint=json.loads((p/meta['marketReports'][-1]/'checkpoint.json').read_text(encoding='utf-8'))
        try:self.ledger.begin(payload['id'],payload['taskId'],report,payload['reportVersion'],checkpoint,payload['observation'])
        except ValueError:
            self.ledger.refused(payload['id'],payload['taskId'],payload['observation']);raise
        return self.state(payload['id'])
    def observe_action(self,payload):
        self.folder(payload['id'])
        self.ledger.finish(payload['id'],payload['taskId'],payload['observation'],payload.get('observationReviewed'))
        return self.state(payload['id'])
    def cancel_action(self,payload):
        if payload.get('cancelConfirmed') is not True:raise ValueError('Explicit revocation required')
        self.folder(payload['id']);self.ledger.cancel(payload['id'],payload['taskId']);return self.state(payload['id'])
    def save_result(self,ident,report):
        p=self.folder(ident);meta=json.loads((p/'case.json').read_text(encoding='utf-8'));v='result-'+secrets.token_hex(16)
        (p/v).mkdir();save(p/v/'report.json',report);meta.setdefault('resultReports',[]).append(v);save(p/'case.json',meta)
        return self.state(ident)
    def generate_result(self,payload):return self.save_result(payload['id'],result_generate(self.folder(payload['id']),payload.get('priority','fit')))
    def checked_result(self,payload):
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        if payload['reportVersion']!=meta['resultReports'][-1]:raise ValueError('Stale result version')
        r=json.loads((p/meta['resultReports'][-1]/'report.json').read_text(encoding='utf-8'))
        if r['contextHash']!=result_context(p)['hash']:raise ValueError('Evidence changed; regenerate result, no implicit choice carryover')
        return r
    def choose_result(self,payload):
        r=self.checked_result(payload)
        return self.save_result(payload['id'],result_choose(r,payload['jobId'],payload['bucket'],payload['reason'],payload.get('reviewerConfirmed')))
    def reorder_result(self,payload):
        if payload.get('orderConfirmed') is not True:raise ValueError('Explicit ordering required')
        return self.save_result(payload['id'],result_reorder(self.checked_result(payload),payload['order']))
    def export_result(self,payload):
        if payload.get('privateExportConfirmed') is not True:raise ValueError('Private export requires explicit acknowledgement')
        r=self.checked_result(payload);r['summary']=result_summary(r)
        r['actionObservations']=[{k:t.get(k) for k in ('jobId','action','state','platformState','observedAt','systemExecuted','messageSent','attachmentSent','outcomeMeaning')} for t in self.ledger.list(payload['id']) if t['jobId'] in r['userOrder']]
        kind=payload['format']
        if kind not in ('json','html'):raise ValueError('Unsupported export')
        content=json.dumps(r,ensure_ascii=False,indent=2) if kind=='json' else html_report(r)
        return {'filename':'private-job-report.'+kind,'content':content,'contentType':'application/json' if kind=='json' else 'text/html','status':'export-prepared-not-save-confirmed'}
    def company_context(self,ident,company_id):
        p=self.folder(ident);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        market=meta['marketReports'][-1];data=json.loads((p/market/'checkpoint.json').read_text(encoding='utf-8'))
        found=[c for c in data['companies'] if c['id']==company_id]
        if len(found)!=1:raise ValueError('Company outside latest evidence')
        return {'company':found[0],'marketVersion':market}
    def capture_finance(self,payload):
        if payload.get('mode') not in ('unknown','official'):raise ValueError('Explicit research mode required')
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        context=self.company_context(payload['id'],payload['companyId'])
        version='research-'+secrets.token_hex(16);out=p/version
        if payload.get('mode')=='unknown':
            out.mkdir();report={'status':'unlisted-or-identity-unverified','companyGrowth':'unknown','riskAssessment':'unknown','automaticScore':None}
        else:
            if payload.get('downloadConfirmed') is not True:raise ValueError('Explicit official-site request permission required')
            m=finance_metadata(payload['metadata']);quote=payload['employerQuote'];source=context['company']['source']
            if not isinstance(quote,str) or not quote.strip() or quote not in source['text'] or m['employerLegalName'] not in quote:raise ValueError('Employer needs exact company evidence')
            try:report=finance_capture(m,out)
            except Exception:
                out.mkdir(exist_ok=True);report={'status':'official-source-unavailable-or-unverified','metadata':m,'companyGrowth':'unknown','riskAssessment':'unknown','automaticScore':None}
            report['captureVersion']=version;report['employerEvidence']={'quote':quote,'sourceUrl':source['url'],'sourceSha256':finance_sha(source['text'].encode())}
        report.update(companyId=payload['companyId'],companyName=context['company']['source'].get('title') or '公司名称待核实',marketVersion=context['marketVersion'])
        save(out/'report.json',report);meta.setdefault('researchReports',[]).append(version);save(p/'case.json',meta)
        return self.state(payload['id'])
    def review_finance(self,payload):
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        if payload['reportVersion']!=meta['researchReports'][-1]:raise ValueError('Stale financial review')
        old=json.loads((p/meta['researchReports'][-1]/'report.json').read_text(encoding='utf-8'))
        if old['marketVersion']!=meta['marketReports'][-1]:raise ValueError('Employer evidence changed; recheck relationship')
        capture_version=old['captureVersion'];version='research-'+secrets.token_hex(16);(p/version).mkdir()
        report=finance_review(p/capture_version,payload['review'],p/version/'report.json')
        report.update(captureVersion=capture_version,companyId=old['companyId'],companyName=old.get('companyName','公司名称待核实'),marketVersion=old['marketVersion'],employerEvidence=old['employerEvidence'])
        save(p/version/'report.json',report);meta['researchReports'].append(version);save(p/'case.json',meta)
        return self.state(payload['id'])
    def generate_ability(self,payload):
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        candidate=meta['versions'][-1];market=meta['marketReports'][-1]
        checkpoint=json.loads((p/market/'checkpoint.json').read_text(encoding='utf-8'))
        jobs=[j for j in checkpoint['jobs'] if j['id']==payload['jobId']]
        if len(jobs)!=1:raise ValueError('Job outside latest market evidence')
        report=ability_generate(jobs[0],load_facts(p/candidate));report.update(candidateVersion=candidate,marketVersion=market)
        version='ability-'+secrets.token_hex(16);(p/version).mkdir();save(p/version/'report.json',report)
        meta.setdefault('abilityReports',[]).append(version);save(p/'case.json',meta)
        return self.state(payload['id'])
    def review_ability(self,payload):
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        if payload['reportVersion']!=meta['abilityReports'][-1]:raise ValueError('Stale report')
        draft=json.loads((p/meta['abilityReports'][-1]/'report.json').read_text(encoding='utf-8'))
        if draft['candidateVersion']!=meta['versions'][-1] or draft['marketVersion']!=meta['marketReports'][-1] or draft['context']['candidateFactsHash']!=hash_json(load_facts(p/meta['versions'][-1])):raise ValueError('Regenerate after evidence or confirmation change')
        report=ability_review(draft,payload['items'],payload['contextHash'],payload.get('reviewerConfirmed'))
        version='ability-'+secrets.token_hex(16);(p/version).mkdir();save(p/version/'report.json',report)
        meta['abilityReports'].append(version);save(p/'case.json',meta)
        return self.state(payload['id'])
    def direction_feedback(self,payload):
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        if payload['reportVersion']!=meta['abilityReports'][-1]:raise ValueError('Stale report')
        draft=json.loads((p/meta['abilityReports'][-1]/'report.json').read_text(encoding='utf-8'))
        if draft['candidateVersion']!=meta['versions'][-1] or draft['marketVersion']!=meta['marketReports'][-1] or draft['context']['candidateFactsHash']!=hash_json(load_facts(p/meta['versions'][-1])):raise ValueError('Regenerate stale evidence')
        report=ability_feedback(draft,payload['choices']);version='ability-'+secrets.token_hex(16);(p/version).mkdir();save(p/version/'report.json',report)
        meta['abilityReports'].append(version);save(p/'case.json',meta);return self.state(payload['id'])
    def screen(self,payload):
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        if payload.get('policyConfirmed') is not True:raise ValueError('Explicit policy confirmation required')
        report=prescreen(payload['checkpoint'],payload['policy'])
        version='market-'+secrets.token_hex(16);folder=p/version;folder.mkdir()
        save(folder/'checkpoint.json',payload['checkpoint']);save(folder/'report.json',report)
        meta.setdefault('marketReports',[]).append(version);save(p/'case.json',meta)
        return self.state(payload['id'])
    def review(self,payload):
        validate_conditions(payload['conditions'])
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        if payload.get('reviewed') is not True:raise ValueError('explicit_review_required')
        version=secrets.token_hex(16);conditions=p/('conditions-'+version+'.json');save(conditions,payload['conditions'])
        if meta['kind'] in ('.pdf','.docx'):
            mapping=p/('mapping-'+version+'.json');save(mapping,payload['mapping'])
            source=p/('resume-'+version+'.json');apply_mapping(p/'document',mapping,source)
        else:source=p/('upload'+meta['kind'])
        intake(source,conditions,p/version)
        save(p/version/'conditions.json',{'status':'user-confirmed','groups':payload['conditions']})
        meta['versions'].append(version);meta['status']='facts-review-required';save(p/'case.json',meta)
        return self.state(payload['id'])
    def confirm(self,payload):
        p=self.folder(payload['id']);meta=json.loads((p/'case.json').read_text(encoding='utf-8'))
        confirm(p/meta['versions'][-1],payload['factIds'])
        return self.state(payload['id'])

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(20)
    def log_message(self,*args):pass
    def send(self,status,data,kind='application/json; charset=utf-8'):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers();self.wfile.write(data)
    def local(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_address[1])
    def authorized(self):return self.local() and secrets.compare_digest(self.headers.get('X-Workspace-Token',''),self.server.token) and self.headers.get('Origin',self.server.origin)==self.server.origin
    def do_GET(self):
        if not self.local():self.send(403,{'error':'invalid_host'});return
        route=urlsplit(self.path)
        if route.path=='/':
            page=(ROOT/'web/workspace.html').read_text(encoding='utf-8').replace('__WORKSPACE_TOKEN__',self.server.token)
            self.send(200,page.encode(),'text/html; charset=utf-8');return
        if route.path=='/favicon.ico':self.send(200,b'','image/x-icon');return
        if not self.authorized():self.send(403,{'error':'authorization_required'});return
        try:
            with self.server.lock:
                if route.path=='/api/list':data={'ids':self.server.workspace.listing()}
                elif route.path=='/api/state':data=self.server.workspace.state(parse_qs(route.query)['id'][0])
                elif route.path=='/api/company-context':data=self.server.workspace.company_context(parse_qs(route.query)['id'][0],parse_qs(route.query)['companyId'][0])
                else:self.send(404,{'error':'not_found'});return
            self.send(200,data)
        except Exception:self.send(400,{'error':'request_failed_check_local_input'})
    def do_POST(self):
        if not self.authorized():self.send(403,{'error':'authorization_required'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=14_000_000:raise ValueError('size')
            payload=json.loads(self.rfile.read(size))
            with self.server.lock:
                if self.path=='/api/upload':data=self.server.workspace.upload(payload)
                elif self.path=='/api/review':data=self.server.workspace.review(payload)
                elif self.path=='/api/confirm':data=self.server.workspace.confirm(payload)
                elif self.path=='/api/screen':data=self.server.workspace.screen(payload)
                elif self.path=='/api/ability-generate':data=self.server.workspace.generate_ability(payload)
                elif self.path=='/api/ability-review':data=self.server.workspace.review_ability(payload)
                elif self.path=='/api/direction-feedback':data=self.server.workspace.direction_feedback(payload)
                elif self.path=='/api/research-capture':data=self.server.workspace.capture_finance(payload)
                elif self.path=='/api/research-review':data=self.server.workspace.review_finance(payload)
                elif self.path=='/api/result-generate':data=self.server.workspace.generate_result(payload)
                elif self.path=='/api/result-choose':data=self.server.workspace.choose_result(payload)
                elif self.path=='/api/result-reorder':data=self.server.workspace.reorder_result(payload)
                elif self.path=='/api/result-export':data=self.server.workspace.export_result(payload)
                elif self.path=='/api/action-authorize':data=self.server.workspace.authorize_actions(payload)
                elif self.path=='/api/action-begin':data=self.server.workspace.begin_action(payload)
                elif self.path=='/api/action-observe':data=self.server.workspace.observe_action(payload)
                elif self.path=='/api/action-cancel':data=self.server.workspace.cancel_action(payload)
                else:self.send(404,{'error':'not_found'});return
            self.send(200,data)
        except ValueError as exc:
            if self.path.startswith('/api/action-'):
                reason=str(exc)
                code='duplicate-or-uncertain' if 'Existing action' in reason else 'job-changed' if 'Conditions changed' in reason or 'Job duties changed' in reason else 'authorization-stale' if 'Authorization expired' in reason or 'Stale result' in reason or 'Evidence changed' in reason else 'observation-invalid' if any(t in reason for t in ('Observation','observation','observed','Scoped control','Control label','Ambiguous')) else 'scope-or-confirmation'
                self.send(400,{'error':'action_step_rejected','reasonCode':code})
            else:self.send(400,{'error':'request_failed_check_format_dependency_evidence_or_confirmation'})
        except Exception:self.send(400,{'error':'request_failed_check_format_dependency_evidence_or_confirmation'})

def start(path,port=8875):
    for n in range(port,port+20):
        try:server=Server(('127.0.0.1',n),Handler);break
        except OSError:continue
    else:raise OSError('No free local port')
    server.workspace=Workspace(path);server.token=secrets.token_urlsafe(32);server.lock=threading.Lock();server.origin='http://127.0.0.1:'+str(server.server_address[1])
    return server

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=ROOT/'data/private-web');p.add_argument('--port',type=int,default=8875);p.add_argument('--no-browser',action='store_true');a=p.parse_args()
    if not 1024<=a.port<=65516:p.error('Invalid port')
    with start(a.data,a.port) as server:
        print('Private workspace: '+server.origin+'\nLocal files are stored under the selected data directory. Ctrl+C to stop.',flush=True)
        if not a.no_browser:webbrowser.open(server.origin)
        try:server.serve_forever()
        except KeyboardInterrupt:pass

if __name__=='__main__':main()
