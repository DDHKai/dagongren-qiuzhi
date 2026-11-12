from pathlib import Path
import tempfile
import unittest
from check_release_layout import check_version

class VersionTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'data/test-tmp'
        parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.root=Path(self.temp.name)
        for d in ('web','scripts','docs'):(self.root/d).mkdir()
        for name,text in {'VERSION':'0.1.1-experiment','web/index.html':"const VERSION='0.1.1-experiment'",'scripts/desktop_launcher.py':"ROOT/'VERSION'",'README.md':'0.1.1-experiment','docs/desktop-testing.md':'0.1.1-experiment'}.items():
            (self.root/name).write_text(text,encoding='utf-8')
    def tearDown(self):self.temp.cleanup()
    def test_mismatched_page_rejected(self):
        (self.root/'web/index.html').write_text("const VERSION='0.1.0-experiment'",encoding='utf-8')
        with self.assertRaises(ValueError):check_version(self.root)
    def test_mismatched_docs_rejected(self):
        (self.root/'README.md').write_text('old version',encoding='utf-8')
        with self.assertRaises(ValueError):check_version(self.root)
    def test_mismatched_snapshot_rejected(self):
        (self.root/'TEST_SNAPSHOT').write_text('v0.2.0-mvp-test1',encoding='utf-8')
        with self.assertRaises(ValueError):check_version(self.root)

if __name__=='__main__':unittest.main()
