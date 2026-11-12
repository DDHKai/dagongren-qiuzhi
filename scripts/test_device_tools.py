import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from check_public_files import PUBLIC
from run_device_checks import redact,source_check
from package_device_feedback import pack

class DeviceToolsTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'data/test-tmp';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def fixture(self):
        source=self.root/'source';source.mkdir();manifest={}
        for name in PUBLIC:
            p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'')
        (source/'VERSION').write_text('0.2.0-experiment',encoding='utf-8');(source/'TEST_SNAPSHOT').write_text('v0.2.0-mvp-test1',encoding='utf-8')
        manifest={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in PUBLIC}
        (source/'MANIFEST.json').write_text(json.dumps(manifest),encoding='utf-8');archive=self.root/'source.zip'
        with ZipFile(archive,'w') as z:
            for name in list(PUBLIC)+['MANIFEST.json']:z.write(source/name,'dagongren-experiment/'+name)
        archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  source.zip',encoding='utf-8')
        return source,archive
    def test_archive_manifest_and_extracted_source_must_match(self):
        source,archive=self.fixture();self.assertTrue(source_check(source,archive)['passed'])
        (source/'README.md').write_text('changed',encoding='utf-8');self.assertFalse(source_check(source,archive)['passed'])
    def test_checksum_mismatch_not_passed(self):
        source,archive=self.fixture();archive.with_suffix('.zip.sha256').write_text('0'*64,encoding='utf-8');self.assertFalse(source_check(source,archive)['passed'])
    def test_home_and_project_paths_redacted(self):
        text=str(self.root)+' '+json.dumps(str(self.root))[1:-1]+' /Users/SYNTHETIC/file'
        cleaned=redact(text,self.root);self.assertNotIn(str(self.root),cleaned);self.assertNotIn('/Users/SYNTHETIC',cleaned)
    def test_raw_and_database_excluded(self):
        results=self.root/'results';results.mkdir();(results/'RAW-PRIVATE').mkdir();(results/'RAW-PRIVATE/secret.txt').write_text('do not share');(results/'workspace.sqlite3').write_bytes(b'private')
        (results/'device-summary.json').write_text('{"status":"synthetic"}',encoding='utf-8');target=self.root/'feedback.zip'
        pack(results,target,True)
        with ZipFile(target) as z:self.assertEqual(set(z.namelist()),{'device-results/device-summary.json','device-results/feedback-manifest.json'})
    def test_privacy_and_review_gate(self):
        results=self.root/'results';results.mkdir();(results/'manual-results.md').write_text('securityId=synthetic',encoding='utf-8')
        with self.assertRaises(ValueError):pack(results,self.root/'blocked.zip',False)
        with self.assertRaises(ValueError):pack(results,self.root/'blocked.zip',True)
        self.assertFalse((self.root/'blocked.zip').exists())
    def test_missing_report_is_not_certified_by_packer(self):
        results=self.root/'results';results.mkdir();(results/'manual-results.md').write_text('未测试，设备未就绪',encoding='utf-8')
        r=pack(results,self.root/'partial.zip',True);self.assertIn('device-summary.json',r['missingFiles']);self.assertFalse(r['uploaded'])

if __name__=='__main__':unittest.main()
