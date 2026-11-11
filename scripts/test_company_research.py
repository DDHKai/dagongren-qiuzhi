import copy
import json
from pathlib import Path
import tempfile
import unittest
from company_research import capture,review,official_url,metadata,Redirect

def meta():return {'market':'CN','issuerLegalName':'示例上市公司','securityIdentifier':'600000','employerLegalName':'示例上市公司','relationship':'same-entity','documentType':'季度报告','periodStart':'2026-01-01','periodEnd':'2026-09-30','disclosureDate':'2026-10-28','latestCheckedAt':'2026-11-12','currency':'CNY','unit':'元','consolidationScope':'合并','auditStatus':'unaudited','officialDocumentUrl':'https://static.cninfo.com.cn/finalpage/synthetic.pdf'}
RAW='<html><body><p>示例上市公司 2026年第三季度 经营现金流100.00 可用现金200.00 短期有息债务100.00</p><script>untrusted()</script></body></html>'.encode()

class FinanceTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'data/test-tmp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.root=Path(self.temp.name);self.folder=self.root/'report'
        capture(meta(),self.folder,lambda m:(RAW,m['officialDocumentUrl']))
        self.unit=json.loads((self.folder/'extraction.json').read_text(encoding='utf-8'))['units'][0]['id']
    def tearDown(self):self.temp.cleanup()
    def payload(self):return {'reviewerConfirmed':True,'identityEvidence':{'unitId':self.unit,'quote':'示例上市公司'},'periodEvidence':{'unitId':self.unit,'quote':'2026年第三季度'},'metrics':[]}
    def metric(self,name,value,quote):return {'metric':name,'value':value,'currency':'CNY','unit':'元','consolidationScope':'合并','periodStart':None,'periodEnd':'2026-09-30','evidence':{'unitId':self.unit,'quote':quote}}
    def test_official_allowlist(self):
        for url in ['http://static.cninfo.com.cn/a.pdf','https://static.cninfo.com.cn.evil.invalid/a','https://user:pass@static.cninfo.com.cn/a','https://127.0.0.1/a']:
            with self.assertRaises(ValueError):official_url(url,'CN')
    def test_metadata_chronology_and_entity(self):
        m=meta();m['periodEnd']='2027-01-01'
        with self.assertRaises(ValueError):metadata(m)
        m=meta();m['employerLegalName']='另一主体'
        with self.assertRaises(ValueError):metadata(m)
    def test_no_score_or_automatic_growth(self):
        r=json.loads((self.folder/'report.json').read_text(encoding='utf-8'));self.assertIsNone(r['automaticScore']);self.assertEqual(r['companyGrowth'],'unknown')
        d=json.loads((self.folder/'extraction.json').read_text(encoding='utf-8'));self.assertNotIn('untrusted()',str(d))
    def test_unknown_on_source_failure_no_fallback(self):
        def fail(m):raise OSError('offline')
        out=self.root/'failed'
        with self.assertRaises(OSError):capture(meta(),out,fail)
        d=json.loads((out/'status.json').read_text(encoding='utf-8'));self.assertEqual(d['riskAssessment'],'unknown');self.assertFalse(d['fallbackUsed'])
    def test_explicit_review_and_quotation(self):
        p=self.payload();p['reviewerConfirmed']=False
        with self.assertRaises(ValueError):review(self.folder,p,self.root/'v1.json')
        p=self.payload();p['identityEvidence']['quote']='invented'
        with self.assertRaises(ValueError):review(self.folder,p,self.root/'v1.json')
    def test_units_must_match(self):
        p=self.payload();m=self.metric('availableCash','200.00','可用现金200.00');m['unit']='万元';p['metrics']=[m]
        with self.assertRaises(ValueError):review(self.folder,p,self.root/'v1.json')
    def test_ratio_only_from_explicit_available_cash_and_debt(self):
        p=self.payload();p['metrics']=[self.metric('availableCash','200.00','可用现金200.00'),self.metric('shortTermInterestDebt','100.00','短期有息债务100.00')]
        r=review(self.folder,p,self.root/'v1.json');self.assertEqual(r['shortDebtCoverage']['ratio'],'2');self.assertEqual(r['riskAssessment'],'unknown')
    def test_cannot_invent_numeric_value_or_overwrite(self):
        p=self.payload();p['metrics']=[self.metric('availableCash','900.00','可用现金200.00')]
        with self.assertRaises(ValueError):review(self.folder,p,self.root/'v1.json')
        p=self.payload();review(self.folder,p,self.root/'v1.json')
        with self.assertRaises(ValueError):review(self.folder,p,self.root/'v1.json')
    def test_tampered_document_rejected(self):
        (self.folder/'source.html').write_text('changed',encoding='utf-8')
        with self.assertRaises(ValueError):review(self.folder,self.payload(),self.root/'v1.json')
    def test_table_numeric_cells_are_not_merged(self):
        raw='<html><p>示例上市公司 2026年第三季度 营业收入 12.00 -6.87 14,728.97 -1.89</p></html>'.encode()
        folder=self.root/'table';capture(meta(),folder,lambda m:(raw,m['officialDocumentUrl']))
        p=self.payload();m=self.metric('revenue','14,728.97','营业收入 12.00 -6.87 14,728.97 -1.89');m['periodStart']='2026-01-01';p['metrics']=[m]
        r=review(folder,p,self.root/'table-review.json');self.assertEqual(r['metrics'][0]['value'],'14,728.97')
    def test_changed_metadata_rejected(self):
        path=self.folder/'report.json';r=json.loads(path.read_text(encoding='utf-8'));r['metadata']['unit']='万元';path.write_text(json.dumps(r),encoding='utf-8')
        with self.assertRaises(ValueError):review(self.folder,self.payload(),self.root/'changed.json')
    def test_negative_available_cash_requires_sign_review(self):
        raw='<html><p>示例上市公司 2026年第三季度 可用现金-200.00</p></html>'.encode();folder=self.root/'negative'
        capture(meta(),folder,lambda m:(raw,m['officialDocumentUrl']));p=self.payload();p['metrics']=[self.metric('availableCash','-200.00','可用现金-200.00')]
        with self.assertRaises(ValueError):review(folder,p,self.root/'negative-review.json')
    def test_cannot_drop_negative_sign(self):
        raw='<html><p>示例上市公司 2026年第三季度 经营现金流-100.00</p></html>'.encode();folder=self.root/'sign'
        capture(meta(),folder,lambda m:(raw,m['officialDocumentUrl']));p=self.payload()
        m=self.metric('operatingCashFlow','100.00','经营现金流-100.00');m['periodStart']='2026-01-01';p['metrics']=[m]
        with self.assertRaises(ValueError):review(folder,p,self.root/'sign-review.json')
    def test_parent_relationship_requires_citation(self):
        other=self.root/'parent';m=meta();m['relationship']='parent-subsidiary';m['employerLegalName']='示例子公司';capture(m,other,lambda v:(RAW,v['officialDocumentUrl']))
        with self.assertRaises(ValueError):review(other,self.payload(),self.root/'v1.json')

if __name__=='__main__':unittest.main()
