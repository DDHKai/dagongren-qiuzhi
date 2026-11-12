import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest
from workspace_server import Workspace
from result_report import generate,choose,reorder,summary,html_report,size
from test_prescreen_jobs import job

class ResultTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'data/test-tmp';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.w=Workspace(Path(self.temp.name));self.c=self.w.upload({'kind':'.txt','data':base64.b64encode('负责示例报表整理及复盘'.encode()).decode(),'conditions':{'must':[],'prefer':[],'ignore':[]}})
        self.ident=self.c['id'];self.folder=self.w.folder(self.ident);self.w.confirm({'id':self.ident,'factIds':[self.c['facts'][0]['id']]})
        j=job(body='负责示例报表整理及复盘');self.jid=j['id'];self.cid=j['companyKey']
        company={'id':self.cid,'source':{'url':'https://www.zhipin.com'+self.cid,'title':'合成示例公司','text':'合成示例公司\n未融资 · 20-99人 · 软件\n公司简介\n推荐公司 10000人以上'}}
        self.screen={'id':self.ident,'policyConfirmed':True,'checkpoint':{'jobs':[j],'companies':[company]},'policy':{'salaryMinK':18,'salaryBasis':'published-lower-bound'}}
        self.w.screen(self.screen)
    def tearDown(self):self.temp.cleanup()
    def reviewed(self):
        d=self.w.generate_ability({'id':self.ident,'jobId':self.jid});r=d['abilityReport']
        return self.w.review_ability({'id':self.ident,'reportVersion':d['abilityVersion'],'contextHash':r['contextHash'],'reviewerConfirmed':True,
            'items':[{'requirementId':r['requirements'][0]['id'],'decision':'supported','factIds':[self.c['facts'][0]['id']],'rationale':'人工对照了相同报表任务'}]})
    def test_no_automatic_shortlist_or_score(self):
        r=generate(self.folder);self.assertIsNone(r['totalScore']);self.assertEqual(summary(r)['shortfall']['preferred'],10)
        self.assertEqual(r['coverage']['actualCompanies'],1);self.assertFalse(r['coverage']['complete']);self.assertEqual(r['jobs'][0]['abilityStatus'],'not-reviewed')
    def test_company_size_uses_header_only(self):
        r=generate(self.folder);self.assertEqual(r['jobs'][0]['companySize']['value'],'20-99人')
        self.assertEqual(len(r['jobs'][0]['companySize']['evidence']),1)
    def test_cannot_promote_unreviewed_or_unknown_conditions(self):
        r=generate(self.folder)
        with self.assertRaises(ValueError):choose(r,self.jid,'preferred','本人想选',True)
        self.reviewed();r=generate(self.folder);r['jobs'][0]['group']='值得核实'
        with self.assertRaises(ValueError):choose(r,self.jid,'preferred','先核实',True)
        self.assertEqual(choose(r,self.jid,'reserve','需确认固定待遇',True)['jobs'][0]['selection']['bucket'],'reserve')
    def test_hard_mismatch_cannot_be_compensated(self):
        self.reviewed();r=generate(self.folder);r['jobs'][0]['group']='明确存在取舍'
        with self.assertRaises(ValueError):choose(r,self.jid,'reserve','公司前景好',True)
        self.assertEqual(choose(r,self.jid,'tradeoff','需本人另行调整条件，不自动放宽',True)['jobs'][0]['selection']['bucket'],'tradeoff')
    def test_choice_order_and_private_export(self):
        self.reviewed();d=self.w.generate_result({'id':self.ident});r=d['resultReport']
        d=self.w.choose_result({'id':self.ident,'reportVersion':d['resultVersion'],'jobId':self.jid,'bucket':'preferred','reason':'任务直接相交，明确条件披露符合','reviewerConfirmed':True})
        self.assertEqual(d['resultSummary']['counts']['preferred'],1);self.assertEqual(d['resultReport']['systemOrder'],r['systemOrder'])
        p={'id':self.ident,'reportVersion':d['resultVersion'],'format':'html'}
        with self.assertRaises(ValueError):self.w.export_result(p)
        p['privateExportConfirmed']=True;e=self.w.export_result(p);self.assertIn('负责示例报表',e['content']);self.assertEqual(e['status'],'export-prepared-not-save-confirmed')
    def test_latest_ability_and_changed_market_make_result_stale(self):
        self.reviewed();d=self.w.generate_result({'id':self.ident});self.w.generate_ability({'id':self.ident,'jobId':self.jid})
        self.assertTrue(self.w.state(self.ident)['resultReport']['stale'])
        with self.assertRaises(ValueError):self.w.export_result({'id':self.ident,'reportVersion':d['resultVersion'],'format':'json','privateExportConfirmed':True})
        r=generate(self.folder);self.assertEqual(r['jobs'][0]['abilityStatus'],'draft')
        self.w.screen(self.screen);r=generate(self.folder);self.assertEqual(r['jobs'][0]['abilityStatus'],'stale');self.assertFalse(r['jobs'][0]['advice']['emphasize'])
    def test_same_company_not_counted_twice_and_bucket_capacity(self):
        self.reviewed();r=generate(self.folder);base=copy.deepcopy(r['jobs'][0]);r['jobs'].append({**copy.deepcopy(base),'jobId':'second'})
        r=choose(r,self.jid,'preferred','选择此岗位',True);r=choose(r,'second','reserve','同公司改选',True)
        self.assertEqual(summary(r)['counts']['preferred'],0);self.assertEqual(summary(r)['counts']['reserve'],1)
        r['jobs']=[{**copy.deepcopy(base),'jobId':str(i),'companyId':str(i)} for i in range(11)]
        for i in range(10):r=choose(r,str(i),'preferred','人工确认',True)
        with self.assertRaises(ValueError):choose(r,'10','preferred','不能自动替换',True)
    def test_order_exact_and_export_escapes_source(self):
        r=generate(self.folder)
        with self.assertRaises(ValueError):reorder(r,[])
        r['jobs'][0]['companyName']='<script>alert(1)</script>';r['jobs'][0]['sourceUrl']='javascript:alert(2)'
        html=html_report(r);self.assertNotIn('<script>',html);self.assertNotIn('href="javascript:',html);self.assertIn('&lt;script&gt;',html)
    def test_emphasis_only_from_confirmed_reviewed_facts(self):
        self.reviewed();r=generate(self.folder);a=r['jobs'][0]['advice'];self.assertEqual(a['emphasize'][0]['quote'],'负责示例报表整理及复盘');self.assertTrue(a['verify'])
    def test_full_coverage_counts_unique_related_companies(self):
        data=copy.deepcopy(self.screen);data['checkpoint']['jobs']=[];data['checkpoint']['companies']=[]
        for i in range(100):
            j=job(body='负责示例报表整理及复盘',key='/gongsi/s'+str(i)+'.html');j['id']=j['source']['url']='https://www.zhipin.com/job_detail/s'+str(i)+'.html';data['checkpoint']['jobs'].append(j)
            data['checkpoint']['companies'].append({'id':j['companyKey'],'source':{'url':'https://www.zhipin.com'+j['companyKey'],'title':'合成公司'+str(i),'text':'规模未披露'}})
        self.w.screen(data);r=generate(self.folder);self.assertTrue(r['coverage']['complete']);self.assertEqual(r['coverage']['actualCompanies'],100)
        self.assertEqual(summary(r)['counts']['preferred'],0)
    def test_relaxation_is_separate_and_unknown_not_treated_as_match(self):
        r=generate(self.folder);row=r['jobs'][0];row['group']='明确存在取舍';row['dimensions']['salary']['status']='disclosed-mismatch'
        row['dimensions']['weekend']={'status':'unknown','reason':'待确认','evidence':[]}
        self.assertFalse(summary(r)['relaxationOptions'])
        row['dimensions']['weekend']['status']='disclosed-match'
        options=summary(r)['relaxationOptions'];self.assertEqual(options[0]['additionalConditionEligibleCompanies'],1)
        self.assertEqual(r['policy']['salaryMinK'],18);self.assertEqual(row['group'],'明确存在取舍')
    def test_missing_job_title_keeps_unknown_instead_of_crashing(self):
        data=copy.deepcopy(self.screen);data['checkpoint']['jobs'][0]['source']['title']='未定位标题';self.w.screen(data)
        r=generate(self.folder);self.assertEqual(r['jobs'][0]['jobTitle'],'岗位标题待核实');self.assertEqual(r['jobs'][0]['group'],'值得核实')

if __name__=='__main__':unittest.main()
