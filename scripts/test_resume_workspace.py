import json
from pathlib import Path
import tempfile
import unittest
from resume_workspace import create,confirm

class IntakeTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'data/test-tmp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.root=Path(self.temp.name)
        self.resume=self.root/'input.json';self.resume.write_text(json.dumps({'experiences':[{'responsibilitiesRaw':'示例任务一\n示例任务二'}]}),encoding='utf-8')
        self.conditions=self.root/'conditions.json';self.conditions.write_text(json.dumps({'must':['双休'],'prefer':[],'ignore':[]}),encoding='utf-8');self.output=self.root/'private intake'
    def tearDown(self):self.temp.cleanup()
    def test_intake_and_explicit_confirmation(self):
        r=create(self.resume,self.conditions,self.output);self.assertEqual(r['facts'],2)
        f=json.loads((self.output/'facts.json').read_text(encoding='utf-8'))['facts']
        self.assertTrue(all(x['status']=='candidate-unconfirmed' for x in f))
        self.assertEqual(confirm(self.output,[f[0]['id']])['confirmed'],1)
    def test_output_not_overwritten(self):
        create(self.resume,self.conditions,self.output)
        with self.assertRaises(ValueError):create(self.resume,self.conditions,self.output)
    def test_tampered_fact_rejected(self):
        create(self.resume,self.conditions,self.output)
        p=self.output/'facts.json';d=json.loads(p.read_text(encoding='utf-8'));d['facts'][0]['quote']='invented';p.write_text(json.dumps(d),encoding='utf-8')
        with self.assertRaises(ValueError):confirm(self.output,[d['facts'][0]['id']])
    def test_conflicting_conditions_rejected(self):
        self.conditions.write_text(json.dumps({'must':['双休'],'prefer':['双休'],'ignore':[]}),encoding='utf-8')
        with self.assertRaises(ValueError):create(self.resume,self.conditions,self.output)
    def test_txt_does_not_infer_company(self):
        p=self.root/'resume.txt';p.write_text('示例任务',encoding='utf-8');create(p,self.conditions,self.output)
        d=json.loads((self.output/'resume.json').read_text(encoding='utf-8'))
        self.assertNotIn('company',d['experiences'][0])

if __name__=='__main__':unittest.main()
