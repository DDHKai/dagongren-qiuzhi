import copy
from datetime import datetime,timezone,timedelta
import unittest
import test_result_report as fixtures

class FavoriteWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ResultTests();self.f.setUp();self.f.reviewed();self.w=self.f.w;self.ident=self.f.ident;self.jid=self.f.jid
        d=self.w.generate_result({'id':self.ident});self.d=self.w.choose_result({'id':self.ident,'reportVersion':d['resultVersion'],'jobId':self.jid,'bucket':'preferred','reason':'合成岗位，人工选择','reviewerConfirmed':True})
        self.account={'fingerprint':'a'*64,'browserFingerprint':'b'*64,'displayHint':'138****0000','method':'visible-masked-phone-and-nav-name-v1','capturedAt':datetime.now(timezone.utc).isoformat()}
        self.calls=[];self.mode='happy';self.w.favorite_worker=self.runner
    def tearDown(self):self.f.tearDown()
    def observation(self,collected=False):
        data=copy.deepcopy(self.f.screen['checkpoint']);j=data['jobs'][0];c=data['companies'][0]
        j['source']['capturedAt']=c['source']['capturedAt']=(datetime.now(timezone.utc)+timedelta(seconds=.1)).isoformat()
        if collected:j['source']['text']=j['source']['text'].replace('感兴趣','已感兴趣')
        label='已感兴趣' if collected else '感兴趣'
        return {'schemaVersion':1,'kind':'read-only-job-observation','job':j,'company':c,'controls':{'favorite':'collected' if collected else 'not-collected','basis':'favorite-control-v1','control':{'kind':'boss-interest','label':label},'labels':[label]}}
    def runner(self,spec):
        self.calls.append(spec['mode'])
        if spec['mode']=='probe':return {'status':'account-observed','account':self.account,'tabId':'synthetic-tab'}
        if spec['mode']=='prepare':return {'status':'prepared-not-clicked','account':{**self.account,'fingerprint':'c'*64} if self.mode=='switched' else self.account,'observation':self.observation(self.mode=='already'),'criticalHash':'synthetic-critical'}
        if self.mode=='unknown':return {'status':'stopped','code':'DISCONNECTED','clickMayHaveOccurred':True}
        if self.mode=='blocked':return {'status':'stopped','code':'SCOPE_CHANGED','clickMayHaveOccurred':False}
        return {'status':'confirmed-favorite','account':self.account,'observation':self.observation(True),'clicked':True,'reloadConfirmed':True,'taskId':spec['taskId'],'attemptId':spec['attemptId']}
    def bind(self):
        p=self.w.favorite_probe({})['favoriteProbe']
        return self.w.bind_favorite({'probeId':p['id'],'alias':'合成账号','bindingConfirmed':True})
    def authorize(self):
        self.bind();self.d=self.w.authorize_actions({'id':self.ident,'reportVersion':self.d['resultVersion'],'authorizationConfirmed':True,'items':[{'jobId':self.jid,'action':'favorite'}]});return self.d['actionTasks'][0]
    def execute(self,task):return self.w.execute_favorite({'id':self.ident,'reportVersion':self.d['resultVersion'],'taskId':task['id']})
    def test_probe_is_read_only_and_binding_explicit(self):
        p=self.w.favorite_probe({})['favoriteProbe'];self.assertEqual(self.calls,['probe']);self.assertFalse(self.w.ledger.list(self.ident))
        with self.assertRaises(ValueError):self.w.bind_favorite({'probeId':p['id'],'alias':'合成账号','bindingConfirmed':False})
    def test_favorite_success_requires_bound_account_and_single_claim(self):
        task=self.authorize();d=self.execute(task);t=d['actionTasks'][0]
        self.assertEqual(self.calls,['probe','prepare','execute']);self.assertEqual(t['state'],'confirmed-favorite');self.assertTrue(t['systemExecuted']);self.assertEqual(t['messageSent'],'not-verified')
        with self.assertRaises(ValueError):self.execute(task)
        self.assertEqual(self.calls.count('execute'),1)
    def test_account_switch_stops_before_click(self):
        task=self.authorize();self.mode='switched'
        with self.assertRaises(ValueError):self.execute(task)
        self.assertNotIn('execute',self.calls);self.assertEqual(self.w.ledger.list(self.ident)[0]['state'],'authorized')
    def test_already_favorite_never_clicks_again(self):
        task=self.authorize();self.mode='already';d=self.execute(task);self.assertNotIn('execute',self.calls);self.assertEqual(d['actionTasks'][0]['state'],'observed-favorite');self.assertFalse(d['actionTasks'][0]['systemExecuted'])
    def test_unknown_result_blocks_repeat_and_does_not_mark_success(self):
        task=self.authorize();self.mode='unknown';d=self.execute(task);self.assertEqual(d['actionTasks'][0]['state'],'outcome-unknown');self.assertFalse(d['actionTasks'][0]['systemExecuted'])
        with self.assertRaises(ValueError):self.execute(task)
    def test_before_click_stop_is_recorded_separately(self):
        task=self.authorize();self.mode='blocked';d=self.execute(task);self.assertEqual(d['actionTasks'][0]['state'],'blocked-before-click')
    def test_contact_and_resume_upgrade_actions_rejected(self):
        for action in ('contact-manual','send-resume','send-message','upload-attachment','auto-reply'):
            with self.assertRaises(ValueError):self.w.authorize_actions({'id':self.ident,'reportVersion':self.d['resultVersion'],'authorizationConfirmed':True,'items':[{'jobId':self.jid,'action':action}]})
        self.assertFalse(self.w.ledger.list(self.ident))

if __name__=='__main__':unittest.main()
