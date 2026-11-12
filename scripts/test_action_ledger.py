import copy
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest
from action_ledger import Ledger
from test_prescreen_jobs import job
from prescreen_jobs import run

def observation(collected=False,delta=0):
    j=job(body='负责示例报表整理及复盘');j['source']['capturedAt']=(datetime.now(timezone.utc)+timedelta(seconds=delta)).isoformat()
    j['source']['text']=j['source']['text'].replace('感兴趣',('已收藏' if collected else '收藏')+'\n感兴趣')
    c={'id':j['companyKey'],'source':{'url':'https://www.zhipin.com'+j['companyKey'],'title':'合成公司','text':'公司简介','capturedAt':j['source']['capturedAt']}}
    return {'schemaVersion':1,'kind':'read-only-job-observation','job':j,'company':c,'controls':{'favorite':'collected' if collected else 'not-collected','basis':'exact-label-in-job-header-only','labels':['已收藏' if collected else '收藏']}}

class ActionTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'data/test-tmp';parent.mkdir(parents=True,exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.store=Ledger(Path(self.temp.name)/'ledger.sqlite3');self.obs=observation();self.jid=self.obs['job']['id'];self.cid=self.obs['job']['companyKey']
        self.checkpoint={'jobs':[self.obs['job']],'companies':[self.obs['company']]};self.report=run(self.checkpoint,{'salaryMinK':18,'salaryBasis':'published-lower-bound'})
        self.report['contextHash']='synthetic-context';self.report['jobs'][0].update(selection={'selected':True},companyName='合成公司')
        self.items=[{'jobId':self.jid,'action':'favorite-manual'}]
    def tearDown(self):self.temp.cleanup()
    def authorize(self,items=None):return self.store.authorize('case',self.report,'v1',items or self.items,True)[0]
    def begin(self,task,obs=None):return self.store.begin('case',task['id'],self.report,'v1',self.checkpoint,obs or observation())
    def test_explicit_scope_no_wildcard_or_implicit_send(self):
        for items in [[{'jobId':'*','action':'favorite-manual'}],[{'jobId':self.jid,'action':'send-message'}],[self.items[0],self.items[0]]]:
            with self.assertRaises(ValueError):self.authorize(items)
        with self.assertRaises(ValueError):self.store.authorize('case',self.report,'v1',self.items,False)
        self.assertFalse(self.store.list('case'))
    def test_authorization_alone_does_nothing_and_deduplicates_across_cases(self):
        t=self.authorize();self.assertFalse(t['systemExecuted']);self.assertEqual(t['messageSent'],'not-verified')
        with self.assertRaises(ValueError):self.store.authorize('other-case',self.report,'v1',self.items,True)
    def test_fresh_after_observation_not_click_claim(self):
        t=self.authorize();self.begin(t);r=self.store.finish('case',t['id'],observation(True),True)
        self.assertEqual(r['state'],'observed-favorite');self.assertFalse(r['systemExecuted']);self.assertEqual(r['messageSent'],'not-verified')
        with self.assertRaises(ValueError):self.authorize()
    def test_old_wrong_company_and_platform_wall_stop(self):
        t=self.authorize()
        bad=[observation(delta=-301),observation(delta=60),observation(),observation()]
        bad[2]['job']['companyKey']='/gongsi/wrong.html';bad[3]['job']['source']['text']='安全验证'
        for obs in bad:
            with self.assertRaises(ValueError):self.begin(t,obs)
        self.assertEqual(self.store.list('case')[0]['state'],'authorized')
    def test_changed_salary_or_duties_requires_new_review(self):
        t=self.authorize();obs=observation();obs['job']['source']['text']=obs['job']['source']['text'].replace('20-30K','22-30K')
        with self.assertRaises(ValueError):self.begin(t,obs)
        obs=observation();obs['job']['source']['text']=obs['job']['source']['text'].replace('示例报表','销售招商')
        with self.assertRaises(ValueError):self.begin(t,obs)
    def test_unknown_outcome_blocks_repetition_but_can_reconcile(self):
        t=self.authorize();self.begin(t);r=self.store.finish('case',t['id'],observation(),True)
        self.assertEqual(r['state'],'outcome-unknown')
        with self.assertRaises(ValueError):self.authorize()
        r=self.store.finish('case',t['id'],observation(True),True);self.assertEqual(r['state'],'observed-favorite')
    def test_contact_entry_never_proves_message_sent(self):
        t=self.authorize([{'jobId':self.jid,'action':'contact-manual'}]);self.begin(t);r=self.store.finish('case',t['id'],observation(True),True)
        self.assertEqual(r['state'],'outcome-unknown');self.assertEqual(r['messageSent'],'not-verified')
    def test_prior_favorite_observation_does_not_repeat(self):
        t=self.authorize();r=self.begin(t,observation(True));self.assertEqual(r['state'],'observed-favorite');self.assertFalse(r['systemExecuted'])
    def test_cancel_and_report_binding(self):
        t=self.authorize()
        with self.assertRaises(ValueError):self.store.begin('case',t['id'],self.report,'v2',self.checkpoint,observation())
        self.store.cancel('case',t['id']);self.assertEqual(self.store.list('case')[0]['state'],'cancelled');self.authorize()
    def test_new_after_snapshot_and_review_required(self):
        t=self.authorize();obs=observation();self.begin(t,obs)
        with self.assertRaises(ValueError):self.store.finish('case',t['id'],obs,True)
        with self.assertRaises(ValueError):self.store.finish('case',t['id'],observation(True),False)
    def test_contradictory_label_cannot_mark_favorite(self):
        t=self.authorize();self.begin(t);obs=observation(True);obs['controls']['labels']=['收藏']
        with self.assertRaises(ValueError):self.store.finish('case',t['id'],obs,True)
    def test_batch_is_atomic(self):
        self.report['jobs'].append(copy.deepcopy(self.report['jobs'][0]));self.report['jobs'][-1]['jobId']='https://www.zhipin.com/job_detail/b.html'
        with self.assertRaises(ValueError):self.authorize(self.items+[{'jobId':'https://www.zhipin.com/job_detail/missing.html','action':'favorite-manual'}])
        self.assertFalse(self.store.list('case'))
    def test_expired_authorization_cannot_begin(self):
        from unittest.mock import patch
        t=self.authorize()
        with patch('action_ledger.stamp',return_value=t['expiresAt']+1):
            with self.assertRaises(ValueError):self.begin(t)
        self.assertFalse(self.store.list('case')[0]['systemExecuted'])
    def test_withdrawn_selection_cannot_begin(self):
        t=self.authorize();self.report['jobs'][0]['selection']['selected']=False
        with self.assertRaises(ValueError):self.begin(t)

if __name__=='__main__':unittest.main()
