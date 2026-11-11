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

class Workspace:
    def __init__(self,path):self.root=Path(path);self.root.mkdir(parents=True,exist_ok=True)
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
        return result
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
                else:self.send(404,{'error':'not_found'});return
            self.send(200,data)
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
