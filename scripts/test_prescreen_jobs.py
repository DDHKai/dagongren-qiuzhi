import unittest
from prescreen_jobs import assess,run,validate

def job(body='',header='杭州 3-5年 大专',pay='20-30K',key='/gongsi/a.html'):
    return {'id':'https://www.zhipin.com/job_detail/a.html','companyKey':key,'source':{'title':'「示例岗位招聘」_示例公司','url':'https://www.zhipin.com/job_detail/a.html','text':f'导航\n示例岗位 {pay}\n{header}\n感兴趣\n职位描述\n{body}\n竞争力分析\n推荐岗位 双休 50-80K','capturedAt':'synthetic'}}

class PrescreenTests(unittest.TestCase):
    def test_posted_salary_is_not_fixed_pay(self):
        r=assess(job(),None,{'salaryMinK':18,'salaryBasis':'fixed'})
        self.assertEqual(r['dimensions']['salary']['status'],'unknown')
    def test_salary_range_minimum(self):
        p={'salaryMinK':18,'salaryBasis':'published-lower-bound'}
        self.assertEqual(assess(job(pay='15-30K'),None,p)['group'],'明确存在取舍')
        self.assertEqual(assess(job(pay='年薪20-30K'),None,p)['group'],'值得核实')
    def test_salary_upper_below_minimum_and_body_conflict(self):
        p={'salaryMinK':18,'salaryBasis':'fixed'}
        self.assertEqual(assess(job(pay='10-15K'),None,p)['group'],'明确存在取舍')
        self.assertEqual(assess(job(pay='20-30K',body='薪资：6k-15k'),None,p)['dimensions']['salary']['status'],'conflict')
    def test_fixed_and_performance_ambiguity(self):
        p={'salaryMinK':18,'salaryBasis':'fixed'}
        self.assertEqual(assess(job(body='固定月薪20K'),None,p)['group'],'披露条件满足')
        self.assertEqual(assess(job(body='固定月薪20K含绩效'),None,p)['group'],'值得核实')
    def test_recommendation_weekend_not_borrowed(self):
        self.assertEqual(assess(job(),None,{'weekend':'double'})['group'],'值得核实')
    def test_weekend_conflict(self):
        c={'id':'/gongsi/a.html','source':{'text':'工作时间及福利\n双休\n招聘Boss'}}
        self.assertEqual(assess(job(body='大小休'),c,{'weekend':'double'})['dimensions']['weekend']['status'],'conflict')
    def test_other_company_benefits_not_borrowed(self):
        c={'id':'/gongsi/b.html','source':{'text':'工作时间及福利\n双休\n招聘Boss'}}
        self.assertEqual(assess(job(),c,{'weekend':'double'})['group'],'值得核实')
    def test_negative_double_weekend(self):
        self.assertEqual(assess(job(body='不是双休'),None,{'weekend':'double'})['group'],'明确存在取舍')
    def test_customer_weekend_not_employee_benefit(self):
        self.assertEqual(assess(job(body='客户公司双休'),None,{'weekend':'double'})['group'],'值得核实')
    def test_education_tag_vs_explicit(self):
        p={'candidateEducation':'大专'}
        self.assertEqual(assess(job(header='杭州 3-5年 本科'),None,p)['group'],'值得核实')
        self.assertEqual(assess(job(header='杭州 3-5年 本科',body='要求本科及以上学历'),None,p)['group'],'明确存在取舍')
    def test_preferred_degree_not_hard_failure(self):
        self.assertNotEqual(assess(job(header='杭州 3-5年 本科',body='本科学历优先'),None,{'candidateEducation':'大专'})['group'],'明确存在取舍')
    def test_education_conflict(self):
        r=assess(job(header='杭州 3-5年 学历不限',body='要求本科及以上'),None,{'candidateEducation':'大专'})
        self.assertEqual(r['dimensions']['education']['status'],'conflict')
    def test_city_and_stationing(self):
        self.assertEqual(assess(job(),None,{'city':'杭州'})['group'],'披露条件满足')
        self.assertEqual(assess(job(body='前期义乌驻点'),None,{'city':'杭州'})['group'],'值得核实')
        self.assertEqual(assess(job(body='办公地址：福建-福州'),None,{'city':'杭州'})['dimensions']['city']['status'],'conflict')
    def test_all_evidence_is_exact_slice(self):
        j=job(body='固定月薪20K，双休，本科及以上学历');r=assess(j,None,{'salaryMinK':18,'salaryBasis':'fixed','weekend':'double','candidateEducation':'大专','city':'杭州'})
        for d in r['dimensions'].values():
            for e in d['evidence']:self.assertEqual(j['source']['text'][e['start']:e['end']],e['quote'])
    def test_unknown_company_and_multi_job_grouping(self):
        j=job();second=job();second['id']='https://www.zhipin.com/job_detail/b.html';second['source']['url']=second['id']
        unknown=job(key=None);unknown['id']='https://www.zhipin.com/job_detail/c.html';unknown['source']['url']=unknown['id']
        r=run({'jobs':[j,second,unknown],'companies':[]},{'weekend':'double'})
        self.assertEqual(len(r['companies']['/gongsi/a.html']),2)
        self.assertEqual(r['review'],'pending')
    def test_import_rejects_duplicate_and_wrong_subject(self):
        with self.assertRaises(ValueError):run({'jobs':[job(),job()],'companies':[]},{'weekend':'double'})
        with self.assertRaises(ValueError):run({'jobs':[],'companies':[{'id':'/gongsi/a.html','source':{'url':'https://www.zhipin.com/gongsi/b.html'}}]},{'weekend':'double'})
    def test_policy_requires_effective_explicit_criteria(self):
        for p in ({},{'salaryBasis':'fixed'},{'salaryMinK':18},{'city':'<script>'}):
            with self.assertRaises(ValueError):validate(p)

if __name__=='__main__':unittest.main()
