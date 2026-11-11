import http.client
from pathlib import Path
import tempfile
import threading
import unittest
from desktop_launcher import bind_server, ROOT

class LauncherTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'data/test-tmp').mkdir(parents=True,exist_ok=True)
    def test_actual_bind_retry_and_static_root(self):
        first=bind_server(ROOT/'web',0,1)
        port=first.server_address[1]
        second=None
        thread=None
        try:
            second=bind_server(ROOT/'web',port,20)
            self.assertNotEqual(port,second.server_address[1])
            self.assertEqual(second.server_address[0],'127.0.0.1')
            thread=threading.Thread(target=second.serve_forever,daemon=True)
            thread.start()
            c=http.client.HTTPConnection(*second.server_address,timeout=3)
            c.request('GET','/');r=c.getresponse()
            self.assertEqual(r.status,200)
            self.assertIn(b'0.1.1-experiment',r.read())
            c.request('GET','/README.md');r=c.getresponse()
            self.assertEqual(r.status,404);r.read()
            c.request('GET','/favicon.ico');r=c.getresponse()
            self.assertEqual(r.status,204);r.read();c.close()
        finally:
            first.server_close()
            if second:
                if thread and thread.is_alive():second.shutdown()
                second.server_close()
    def test_missing_web_fails(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data/test-tmp') as d:
            with self.assertRaises(FileNotFoundError):bind_server(Path(d),0,1)
    def test_all_requested_ports_occupied(self):
        first=bind_server(ROOT/'web',0,1)
        try:
            with self.assertRaises(OSError):bind_server(ROOT/'web',first.server_address[1],1)
        finally:first.server_close()

if __name__=='__main__':unittest.main()
