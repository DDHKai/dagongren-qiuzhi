import copy
import tempfile
import unittest
from pathlib import Path
from project_store import connect, import_checkpoint, import_selections, status

class StoreTests(unittest.TestCase):
    def setUp(self):
        test_root=Path(__file__).resolve().parents[1]/'data/test-tmp'
        test_root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=test_root)
        self.db=connect(Path(self.temp.name)/'test.sqlite3')
        self.record={'companyKey':'/gongsi/a.html','job':{'url':'https://www.zhipin.com/job_detail/a.html?x=1','text':'职位描述'},'company':{'text':'工商信息'}}
    def tearDown(self):
        self.db.close();self.temp.cleanup()
    def test_repeat_import_and_review_gate(self):
        data={'companies':[self.record]}
        import_checkpoint(self.db,'r',data,target=1)
        s=import_checkpoint(self.db,'r',data,target=1)
        self.assertEqual(s['collectedCompanies'],1)
        self.assertFalse(s['overallComplete'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM sources').fetchone()[0],1)
    def test_conflict_rolls_back(self):
        import_checkpoint(self.db,'r',{'companies':[self.record]})
        other=copy.deepcopy(self.record);other['companyKey']='/gongsi/b.html'
        with self.assertRaises(ValueError):import_checkpoint(self.db,'r',{'companies':[other]})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM companies').fetchone()[0],1)
    def test_selection_membership_and_no_execution(self):
        import_checkpoint(self.db,'r',{'companies':[self.record]})
        item={'jobUrl':self.record['job']['url'],'requestedAction':'希望沟通'}
        self.assertEqual(import_selections(self.db,'r',[item])['externalActionsExecuted'],0)
        item['jobUrl']='https://www.zhipin.com/job_detail/other.html'
        with self.assertRaises(ValueError):import_selections(self.db,'r',[item])

if __name__=='__main__':unittest.main()
