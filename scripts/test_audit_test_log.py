import copy
import unittest
from audit_test_log import audit,state

def fixture():
    c={'salary':18,'weekend':'required','sort':'fit'}
    s=state(c,set(),set(),[])
    return {'schemaVersion':2,'appVersion':'0.1.1-experiment','syntheticOnly':True,
        'capabilities':{'liveCollection':False,'externalActions':False,'automaticAIReview':False},
        'downloadStatus':'requested-not-confirmed','counts':{'selected':0,'dismissed':0},'finalState':s,
        'events':[{'sequence':i+1,'elapsedMs':i,'type':t,'state':copy.deepcopy(s)} for i,t in enumerate(['app_started','log_export_requested'])]}

class AuditTests(unittest.TestCase):
    def test_valid_minimal_not_full_test_certification(self):self.assertEqual(audit(fixture())['verdict'],'通过')
    def test_wrong_group(self):
        d=fixture();d['events'][0]['state']['groups'][0]['ids']=[]
        self.assertEqual(audit(d)['verdict'],'异常')
    def test_duplicate_sequence(self):
        d=fixture();d['events'][1]['sequence']=1
        self.assertEqual(audit(d)['verdict'],'异常')
    def test_unknown_version(self):
        d=fixture();d['schemaVersion']=1
        self.assertEqual(audit(d)['verdict'],'证据不足')
    def test_compatible_current_static_fixture(self):
        d=fixture();d['appVersion']='0.2.0-experiment';self.assertEqual(audit(d)['verdict'],'通过')
    def test_counts_and_hidden_state(self):
        d=fixture();d['counts']['selected']=1
        self.assertEqual(audit(d)['verdict'],'异常')
    def test_invalid_conditions(self):
        d=fixture();d['events'][0]['state']['conditions']['salary']=201
        self.assertEqual(audit(d)['verdict'],'异常')
    def test_missing_export(self):
        d=fixture();d['events'].pop()
        self.assertEqual(audit(d)['verdict'],'证据不足')
    def test_malformed_values(self):
        for bad in (None,[],{'syntheticOnly':False}):self.assertEqual(audit(bad)['verdict'],'异常')
    def test_nonmonotonic_time(self):
        d=fixture();d['events'][1]['elapsedMs']=-1
        self.assertEqual(audit(d)['verdict'],'异常')
    def test_selection_transition(self):
        d=fixture();d['events'][1].update(type='selection_changed',sampleId='S01')
        s=state(d['finalState']['conditions'],{'S01'},set(),[])
        d['events'][1]['state']=copy.deepcopy(s)
        d['events'].append({'sequence':3,'elapsedMs':2,'type':'log_export_requested','state':copy.deepcopy(s)})
        d['finalState']=s;d['counts']['selected']=1
        self.assertEqual(audit(d)['verdict'],'通过')

if __name__=='__main__':unittest.main()
