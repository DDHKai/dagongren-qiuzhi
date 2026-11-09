import copy
import unittest
import test_project_store
from review_store import setup,save_review

class ReviewTests(unittest.TestCase):
    def setUp(self):
        test_project_store.StoreTests.setUp(self)
        from project_store import import_checkpoint
        import_checkpoint(self.db,'r',{'companies':[self.record]})
        setup(self.db)
        key=self.db.execute('SELECT hash FROM sources').fetchone()[0]
        self.review={'schemaVersion':'1','runId':'r','jobId':self.record['job']['url'].split('?')[0],'claims':[{'id':'a','dimension':'job_fit','kind':'inference','text':'test','rationale':'test only','evidence':[{'sourceHash':key,'path':'job.text','quote':'职位描述'}]}]}
    def tearDown(self):
        test_project_store.StoreTests.tearDown(self)
    def test_fabricated_quote_rejected(self):
        r=copy.deepcopy(self.review);r['claims'][0]['evidence'][0]['quote']='不存在的证据'
        with self.assertRaises(ValueError):save_review(self.db,r)
    def test_cross_job_scope_rejected(self):
        r=copy.deepcopy(self.review);r['jobId']='https://www.zhipin.com/job_detail/b.html'
        with self.assertRaises(ValueError):save_review(self.db,r)
    def test_valid_draft_idempotent(self):
        save_review(self.db,self.review);save_review(self.db,self.review)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT status FROM reviews').fetchone()[0],'draft')
    def test_unknown_does_not_require_invented_evidence(self):
        r=copy.deepcopy(self.review);r['claims']=[{'id':'u','dimension':'company_growth','kind':'unknown','text':'未知','reason':'未取得公开数据','evidence':[]}]
        save_review(self.db,r)
    def test_dangling_fact_rejected(self):
        r=copy.deepcopy(self.review);r['claims'][0]['candidateFactIds']=['fact_missing']
        with self.assertRaises(ValueError):save_review(self.db,r)

if __name__=='__main__':
    import unittest
    unittest.main()
