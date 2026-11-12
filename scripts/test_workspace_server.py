import base64
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from io import BytesIO
from zipfile import ZipFile
from workspace_server import start

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'data/test-tmp';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.server=start(self.temp.name,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def request(self,path,body=None,headers=None,auth=True):
        h={'X-Workspace-Token':self.server.token} if auth else {}
        h.update(headers or {})
        c=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h)
        r=c.getresponse();status=r.status;data=r.read();c.close();return status,data
    def upload(self):
        return self.request('/api/upload',{'kind':'.txt','data':base64.b64encode('示例任务一\n示例任务二'.encode()).decode(),'conditions':{'must':['双休'],'prefer':[],'ignore':[]}})
    def test_import_review_confirm_and_reload(self):
        status,b=self.upload();self.assertEqual(status,200);d=json.loads(b);ident=d['id']
        self.assertEqual(len(d['facts']),2)
        status,b=self.request('/api/review',{'id':ident,'reviewed':True,'conditions':{'must':['双休'],'prefer':['示例方向'],'ignore':[]}})
        self.assertEqual(status,200);d=json.loads(b);self.assertEqual(len(d['versions']),2)
        self.assertEqual(d['conditions']['status'],'user-confirmed')
        status,b=self.request('/api/confirm',{'id':ident,'factIds':[d['facts'][0]['id']]})
        self.assertEqual(status,200)
        d=json.loads(self.request('/api/state?id='+ident)[1]);self.assertEqual(d['facts'][0]['status'],'candidate-confirmed')
        self.assertEqual(d['facts'][1]['status'],'candidate-unconfirmed')
    def test_api_requires_token(self):self.assertEqual(self.request('/api/list',auth=False)[0],403)
    def test_origin_and_host_rejected(self):
        self.assertEqual(self.request('/api/list',headers={'Origin':'https://example.invalid'})[0],403)
        self.assertEqual(self.request('/',headers={'Host':'example.invalid'})[0],403)
    def test_private_paths_not_served(self):
        self.assertEqual(self.request('/../README.md')[0],404)
        self.assertEqual(self.request('/api/state?id=../../private')[0],400)
    def test_no_implicit_review_or_confirmation(self):
        d=json.loads(self.upload()[1]);ident=d['id']
        self.assertEqual(self.request('/api/review',{'id':ident,'reviewed':False,'conditions':{'must':[],'prefer':[],'ignore':[]}})[0],400)
        self.assertEqual(self.request('/api/confirm',{'id':ident,'factIds':[]})[0],400)
    def test_failed_conditions_do_not_create_case(self):
        self.request('/api/upload',{'kind':'.txt','data':'YQ==','conditions':{}})
        self.assertEqual(json.loads(self.request('/api/list')[1])['ids'],[])
    def test_prescreen_is_explicit_versioned_and_reloaded(self):
        from test_prescreen_jobs import job
        d=json.loads(self.upload()[1]);ident=d['id']
        payload={'id':ident,'checkpoint':{'jobs':[job(body='双休')],'companies':[]},'policy':{'weekend':'double'}}
        self.assertEqual(self.request('/api/screen',payload)[0],400)
        payload['policyConfirmed']=True
        status,b=self.request('/api/screen',payload);self.assertEqual(status,200)
        report=json.loads(b)['marketReport'];self.assertEqual(report['counts']['披露条件满足'],1)
        d=json.loads(self.request('/api/state?id='+ident)[1]);self.assertEqual(d['marketReport']['review'],'pending')
        self.assertEqual(len(d['marketReports']),1)
    def test_ability_review_and_stale_candidate_confirmation(self):
        from test_prescreen_jobs import job
        d=json.loads(self.upload()[1]);ident=d['id'];fact=d['facts'][0]['id']
        j=job(body='负责示例任务与报表整理工作')
        self.request('/api/screen',{'id':ident,'policyConfirmed':True,'checkpoint':{'jobs':[j],'companies':[]},'policy':{'weekend':'double'}})
        status,b=self.request('/api/ability-generate',{'id':ident,'jobId':j['id']});self.assertEqual(status,200)
        draft=json.loads(b);r=draft['abilityReport'];self.assertFalse(r['stale'])
        self.request('/api/confirm',{'id':ident,'factIds':[fact]})
        stale=json.loads(self.request('/api/state?id='+ident)[1]);self.assertTrue(stale['abilityReport']['stale'])
        payload={'id':ident,'reportVersion':draft['abilityVersion'],'contextHash':r['contextHash'],'reviewerConfirmed':True,
            'items':[{'requirementId':r['requirements'][0]['id'],'decision':'supported','factIds':[fact],'rationale':'人工对照任务证据'}]}
        self.assertEqual(self.request('/api/ability-review',payload)[0],400)
        d=json.loads(self.request('/api/ability-generate',{'id':ident,'jobId':j['id']})[1]);r=d['abilityReport']
        payload.update(reportVersion=d['abilityVersion'],contextHash=r['contextHash'])
        status,b=self.request('/api/ability-review',payload);self.assertEqual(status,200)
        self.assertEqual(json.loads(b)['abilityReport']['reviewStatus'],'human-reviewed')
    def test_company_research_unknown_and_versioned_official_review(self):
        from unittest.mock import patch
        from test_prescreen_jobs import job
        from test_company_research import meta,RAW
        from company_research import capture
        ident=json.loads(self.upload()[1])['id'];j=job(body='示例职责');cid='/gongsi/synthetic.html';j['companyKey']=cid
        checkpoint={'jobs':[j],'companies':[{'id':cid,'source':{'url':'https://www.zhipin.com'+cid,'text':'工商信息：示例上市公司','title':'示例公司'}}]}
        screen={'id':ident,'policyConfirmed':True,'checkpoint':checkpoint,'policy':{'weekend':'double'}}
        self.assertEqual(self.request('/api/screen',screen)[0],200)
        self.assertEqual(self.request('/api/company-context?id='+ident+'&companyId='+cid)[0],200)
        payload={'id':ident,'companyId':cid,'mode':'unknown'}
        status,b=self.request('/api/research-capture',payload);self.assertEqual(status,200)
        self.assertEqual(json.loads(b)['researchReport']['companyGrowth'],'unknown')
        payload.update(mode='official',metadata=meta(),employerQuote='工商信息：示例上市公司')
        self.assertEqual(self.request('/api/research-capture',payload)[0],400)
        payload['downloadConfirmed']=True
        with patch('workspace_server.finance_capture',side_effect=lambda m,p:capture(m,p,lambda m:(RAW,m['officialDocumentUrl']))):
            status,b=self.request('/api/research-capture',payload)
        self.assertEqual(status,200);d=json.loads(b);unit=d['researchDocument']['units'][0]['id']
        review={'reviewerConfirmed':True,'identityEvidence':{'unitId':unit,'quote':'示例上市公司'},'periodEvidence':{'unitId':unit,'quote':'2026年第三季度'},'metrics':[]}
        rp={'id':ident,'reportVersion':d['researchVersion'],'review':review}
        status,b=self.request('/api/research-review',rp);self.assertEqual(status,200)
        d=json.loads(b);self.assertEqual(d['researchReport']['status'],'human-reviewed-evidence');self.assertEqual(len(d['researchReports']),3)
        self.assertEqual(self.request('/api/research-review',rp)[0],400)
        self.request('/api/screen',screen);d=json.loads(self.request('/api/state?id='+ident)[1])
        self.assertTrue(d['researchReport']['marketEvidenceChanged']);rp['reportVersion']=d['researchVersion']
        self.assertEqual(self.request('/api/research-review',rp)[0],400)
    def test_result_routes_explicit_choice_export_and_stale_guard(self):
        from test_prescreen_jobs import job
        ident=json.loads(self.upload()[1])['id'];j=job(body='负责示例任务与报表整理工作')
        screen={'id':ident,'policyConfirmed':True,'checkpoint':{'jobs':[j],'companies':[]},'policy':{'weekend':'double'}}
        self.request('/api/screen',screen)
        status,b=self.request('/api/result-generate',{'id':ident});self.assertEqual(status,200);d=json.loads(b)
        self.assertEqual(d['resultSummary']['counts']['preferred'],0)
        payload={'id':ident,'reportVersion':d['resultVersion'],'jobId':j['id'],'bucket':'excluded','reason':'本轮暂不探索此方向'}
        self.assertEqual(self.request('/api/result-choose',payload)[0],400)
        payload['reviewerConfirmed']=True;status,b=self.request('/api/result-choose',payload);self.assertEqual(status,200);d=json.loads(b)
        self.assertEqual(self.request('/api/result-choose',payload)[0],400)
        export={'id':ident,'reportVersion':d['resultVersion'],'format':'json'}
        self.assertEqual(self.request('/api/result-export',export)[0],400)
        export['privateExportConfirmed']=True;status,b=self.request('/api/result-export',export);self.assertEqual(status,200)
        self.assertEqual(json.loads(b)['status'],'export-prepared-not-save-confirmed')
        self.request('/api/screen',screen);self.assertEqual(self.request('/api/result-export',export)[0],400)
    def test_action_authorization_routes_never_execute_and_can_revoke(self):
        from test_prescreen_jobs import job
        d=json.loads(self.upload()[1]);ident=d['id'];fid=d['facts'][0]['id'];self.request('/api/confirm',{'id':ident,'factIds':[fid]})
        j=job(body='负责示例任务一与报表整理工作');cid=j['companyKey']
        self.request('/api/screen',{'id':ident,'policyConfirmed':True,'policy':{'salaryMinK':18,'salaryBasis':'published-lower-bound'},'checkpoint':{'jobs':[j],'companies':[{'id':cid,'source':{'url':'https://www.zhipin.com'+cid,'title':'合成公司','text':'公司简介'}}]}})
        d=json.loads(self.request('/api/ability-generate',{'id':ident,'jobId':j['id']})[1]);r=d['abilityReport']
        self.request('/api/ability-review',{'id':ident,'reportVersion':d['abilityVersion'],'contextHash':r['contextHash'],'reviewerConfirmed':True,'items':[{'requirementId':r['requirements'][0]['id'],'decision':'supported','factIds':[fid],'rationale':'合成用例任务原文对照'}]})
        d=json.loads(self.request('/api/result-generate',{'id':ident})[1])
        d=json.loads(self.request('/api/result-choose',{'id':ident,'reportVersion':d['resultVersion'],'jobId':j['id'],'bucket':'preferred','reason':'合成任务交集','reviewerConfirmed':True})[1])
        grant={'id':ident,'reportVersion':d['resultVersion'],'items':[{'jobId':j['id'],'action':'favorite-manual'}]}
        self.assertEqual(self.request('/api/action-authorize',grant)[0],400)
        grant['authorizationConfirmed']=True;status,b=self.request('/api/action-authorize',grant);self.assertEqual(status,200)
        task=json.loads(b)['actionTasks'][0];self.assertFalse(task['systemExecuted']);self.assertEqual(task['state'],'authorized')
        self.assertEqual(self.request('/api/action-authorize',grant)[0],400)
        status,b=self.request('/api/action-cancel',{'id':ident,'taskId':task['id'],'cancelConfirmed':True});self.assertEqual(status,200)
        self.assertEqual(json.loads(b)['actionTasks'][0]['state'],'cancelled')
    def test_docx_mapping_to_confirmable_facts(self):
        b=BytesIO()
        with ZipFile(b,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>整理合成报表</w:t></w:r></w:p></w:body></w:document>')
        status,raw=self.request('/api/upload',{'kind':'.docx','data':base64.b64encode(b.getvalue()).decode(),'conditions':{'must':['双休'],'prefer':[],'ignore':[]}})
        self.assertEqual(status,200);data=json.loads(raw)
        self.assertEqual(data['conditions']['groups']['must'],['双休'])
        self.assertFalse(data['versions'])
        status,raw=self.request('/api/review',{'id':data['id'],'reviewed':True,'conditions':data['conditions']['groups'],
            'mapping':{'reviewerConfirmed':True,'experiences':[{'responsibilitiesRaw':[{'unitId':'u1','quote':'整理合成报表'}]}],'education':[]}})
        self.assertEqual(status,200);data=json.loads(raw)
        self.assertEqual(data['facts'][0]['quote'],'整理合成报表')
        self.assertEqual(data['resume']['sourceMap'][0]['unitId'],'u1')

if __name__=='__main__':unittest.main()
