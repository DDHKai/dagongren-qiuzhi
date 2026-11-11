import unittest
from ability_review import generate,review,feedback

def fixture(status='candidate-confirmed'):
    job={'id':'https://www.zhipin.com/job_detail/sample.html','source':{'url':'https://www.zhipin.com/job_detail/sample.html','text':'示例岗位\n职位描述\n负责电商投放预算和数据分析\n熟悉RAG和Python落地工作流\n竞争力分析\n推荐岗位：算法'}}
    facts=[{'id':'f1','quote':'负责电商投放预算及AI工作流','status':status,'sourceHash':'synthetic','path':'experiences.0.responsibilitiesRaw'}]
    return generate(job,facts)

class AbilityTests(unittest.TestCase):
    def test_retrieval_never_autoconfirms(self):
        d=fixture();self.assertEqual(len(d['requirements']),2)
        self.assertTrue(all(r['decision']=='unreviewed' for r in d['requirements']))
        self.assertTrue(d['requirements'][0]['retrievalOnly']);self.assertIsNone(d['totalScore'])
    def test_exact_job_reference(self):
        d=fixture();text='示例岗位\n职位描述\n负责电商投放预算和数据分析\n熟悉RAG和Python落地工作流\n竞争力分析\n推荐岗位：算法'
        for r in d['requirements']:self.assertEqual(text[r['start']:r['end']],r['quote'])
    def item(self,d,i=0,decision='supported',facts=None):return {'requirementId':d['requirements'][i]['id'],'decision':decision,'factIds':['f1'] if facts is None else facts,'rationale':'人工核对了业务任务交集，其他技能仍需补证'}
    def test_positive_requires_confirmed_fact(self):
        d=fixture('candidate-unconfirmed')
        with self.assertRaises(ValueError):review(d,[self.item(d)],d['contextHash'],True)
    def test_ai_does_not_prove_python_or_rag(self):
        d=fixture()
        with self.assertRaises(ValueError):review(d,[self.item(d,1)],d['contextHash'],True)
        r=review(d,[self.item(d,1,'partial')],d['contextHash'],True)
        self.assertIn('Python',r['requirements'][1]['uncoveredProofTerms'])
    def test_stale_context_and_foreign_facts_rejected(self):
        d=fixture()
        with self.assertRaises(ValueError):review(d,[self.item(d)],'old-context',True)
        with self.assertRaises(ValueError):review(d,[self.item(d,facts=['foreign'])],d['contextHash'],True)
    def test_gap_not_inability_and_partial_review(self):
        d=fixture();r=review(d,[self.item(d,decision='evidence-gap',facts=[])],d['contextHash'],True)
        self.assertEqual(r['reviewStatus'],'partially-reviewed');self.assertEqual(r['requirements'][1]['decision'],'unreviewed')
    def test_explicit_reviewer_required(self):
        d=fixture()
        with self.assertRaises(ValueError):review(d,[self.item(d)],d['contextHash'],False)
    def test_complete_review_and_duplicate_rejected(self):
        d=fixture();items=[self.item(d),self.item(d,1,'unknown',[])]
        self.assertEqual(review(d,items,d['contextHash'],True)['reviewStatus'],'human-reviewed')
        with self.assertRaises(ValueError):review(d,[items[0],items[0]],d['contextHash'],True)
    def test_directions_require_confirmed_facts_and_feedback_is_local(self):
        self.assertFalse(fixture('candidate-unconfirmed')['directionHypotheses'])
        d=fixture();ident=d['directionHypotheses'][0]['id'];r=feedback(d,{ident:'not-want'})
        self.assertEqual(r['directionFeedback'][ident],'not-want')
        self.assertEqual(r['feedbackScope'],'current-report-only-not-long-term-profile')
        with self.assertRaises(ValueError):feedback(d,{'invented':'want'})

if __name__=='__main__':unittest.main()
