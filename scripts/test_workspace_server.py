import base64
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from io import BytesIO
from zipfile import ZipFile
from workspace_server import start

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'data/test-tmp';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.server=start(self.temp.name,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.temp.cleanup()
    def request(self,path,body=None,headers=None,auth=True):
        h={'X-Workspace-Token':self.server.token} if auth else {}
        h.update(headers or {})
        c=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h)
        r=c.getresponse();status=r.status;data=r.read();c.close();return status,data
    def upload(self):
        return self.request('/api/upload',{'kind':'.txt','data':base64.b64encode('示例任务一\n示例任务二'.encode()).decode(),'conditions':{'must':['双休'],'prefer':[],'ignore':[]}})
    def test_import_review_confirm_and_reload(self):
        status,b=self.upload();self.assertEqual(status,200);d=json.loads(b);ident=d['id']
        self.assertEqual(len(d['facts']),2)
        status,b=self.request('/api/review',{'id':ident,'reviewed':True,'conditions':{'must':['双休'],'prefer':['示例方向'],'ignore':[]}})
        self.assertEqual(status,200);d=json.loads(b);self.assertEqual(len(d['versions']),2)
        self.assertEqual(d['conditions']['status'],'user-confirmed')
        status,b=self.request('/api/confirm',{'id':ident,'factIds':[d['facts'][0]['id']]})
        self.assertEqual(status,200)
        d=json.loads(self.request('/api/state?id='+ident)[1]);self.assertEqual(d['facts'][0]['status'],'candidate-confirmed')
        self.assertEqual(d['facts'][1]['status'],'candidate-unconfirmed')
    def test_api_requires_token(self):self.assertEqual(self.request('/api/list',auth=False)[0],403)
    def test_origin_and_host_rejected(self):
        self.assertEqual(self.request('/api/list',headers={'Origin':'https://example.invalid'})[0],403)
        self.assertEqual(self.request('/',headers={'Host':'example.invalid'})[0],403)
    def test_private_paths_not_served(self):
        self.assertEqual(self.request('/../README.md')[0],404)
        self.assertEqual(self.request('/api/state?id=../../private')[0],400)
    def test_no_implicit_review_or_confirmation(self):
        d=json.loads(self.upload()[1]);ident=d['id']
        self.assertEqual(self.request('/api/review',{'id':ident,'reviewed':False,'conditions':{'must':[],'prefer':[],'ignore':[]}})[0],400)
        self.assertEqual(self.request('/api/confirm',{'id':ident,'factIds':[]})[0],400)
    def test_failed_conditions_do_not_create_case(self):
        self.request('/api/upload',{'kind':'.txt','data':'YQ==','conditions':{}})
        self.assertEqual(json.loads(self.request('/api/list')[1])['ids'],[])
    def test_docx_mapping_to_confirmable_facts(self):
        b=BytesIO()
        with ZipFile(b,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>整理合成报表</w:t></w:r></w:p></w:body></w:document>')
        status,raw=self.request('/api/upload',{'kind':'.docx','data':base64.b64encode(b.getvalue()).decode(),'conditions':{'must':['双休'],'prefer':[],'ignore':[]}})
        self.assertEqual(status,200);data=json.loads(raw)
        self.assertEqual(data['conditions']['groups']['must'],['双休'])
        self.assertFalse(data['versions'])
        status,raw=self.request('/api/review',{'id':data['id'],'reviewed':True,'conditions':data['conditions']['groups'],
            'mapping':{'reviewerConfirmed':True,'experiences':[{'responsibilitiesRaw':[{'unitId':'u1','quote':'整理合成报表'}]}],'education':[]}})
        self.assertEqual(status,200);data=json.loads(raw)
        self.assertEqual(data['facts'][0]['quote'],'整理合成报表')
        self.assertEqual(data['resume']['sourceMap'][0]['unitId'],'u1')

if __name__=='__main__':unittest.main()
