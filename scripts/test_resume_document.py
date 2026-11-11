import json
from pathlib import Path
import tempfile
import unittest
import importlib.util
from zipfile import ZipFile
from resume_document import create,extract,apply_mapping

class DocumentTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'data/test-tmp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.root=Path(self.temp.name);self.source=self.root/'sample.docx';self.folder=self.root/'parsed'
        with ZipFile(self.source,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>示例公司</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>整理示例报表</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
    def tearDown(self):self.temp.cleanup()
    def mapping(self,quote='整理示例报表'):
        p=self.root/'mapping.json';p.write_text(json.dumps({'reviewerConfirmed':True,'experiences':[{'company':[{'unitId':'u1','quote':'示例公司'}],'responsibilitiesRaw':[{'unitId':'u2','quote':quote}]}]}),encoding='utf-8');return p
    def test_docx_table_and_mapping(self):
        self.assertEqual(create(self.source,self.folder)['units'],2)
        out=self.root/'v1.json';r=apply_mapping(self.folder,self.mapping(),out)
        self.assertEqual(r['references'],2)
        self.assertEqual(json.loads(out.read_text(encoding='utf-8'))['experiences'][0]['company'],'示例公司')
        from resume_workspace import create as intake
        conditions=self.root/'conditions.json';conditions.write_text(json.dumps({'must':['双休'],'prefer':[],'ignore':[]}),encoding='utf-8')
        self.assertEqual(intake(out,conditions,self.root/'intake')['facts'],1)
    def test_invented_quote_rejected(self):
        create(self.source,self.folder)
        with self.assertRaises(ValueError):apply_mapping(self.folder,self.mapping('invented'),self.root/'v1.json')
    def test_changed_extraction_rejected(self):
        create(self.source,self.folder);p=self.folder/'extraction.json';p.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):apply_mapping(self.folder,self.mapping(),self.root/'v1.json')
    def test_review_version_not_overwritten(self):
        create(self.source,self.folder);out=self.root/'v1.json';apply_mapping(self.folder,self.mapping(),out)
        with self.assertRaises(ValueError):apply_mapping(self.folder,self.mapping(),out)
    def test_explicit_confirmation_required(self):
        create(self.source,self.folder);p=self.mapping();d=json.loads(p.read_text(encoding='utf-8'));d['reviewerConfirmed']=False;p.write_text(json.dumps(d),encoding='utf-8')
        with self.assertRaises(ValueError):apply_mapping(self.folder,p,self.root/'v1.json')
    def test_xml_entity_rejected(self):
        with ZipFile(self.source,'w') as z:z.writestr('word/document.xml','<!DOCTYPE a [<!ENTITY x "bad">]><a>&x;</a>')
        with self.assertRaises(ValueError):extract(self.source)
    @unittest.skipUnless(importlib.util.find_spec('pypdf'),'optional pypdf not installed')
    def test_blank_pdf_requires_review_not_successful_text(self):
        from pypdf import PdfWriter
        p=self.root/'blank.pdf';w=PdfWriter();w.add_blank_page(width=100,height=100)
        with p.open('wb') as f:w.write(f)
        result=create(p,self.folder)
        self.assertEqual(result['status'],'no-text-needs-ocr-or-manual-transcription')
    @unittest.skipUnless(importlib.util.find_spec('pypdf'),'optional pypdf not installed')
    def test_encrypted_pdf_rejected(self):
        from pypdf import PdfWriter
        p=self.root/'encrypted.pdf';w=PdfWriter();w.add_blank_page(width=100,height=100);w.encrypt('example')
        with p.open('wb') as f:w.write(f)
        with self.assertRaises(ValueError):extract(p)

if __name__=='__main__':unittest.main()
