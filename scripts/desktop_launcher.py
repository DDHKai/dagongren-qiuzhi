"""Local-only static launcher. Python 3.10+, no third-party packages."""
import argparse
import functools
import http.server
import json
from pathlib import Path
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parents[1]

class Server(http.server.ThreadingHTTPServer):
    # Avoid Windows allowing duplicate bindings to an already occupied port.
    allow_reuse_address = False

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not retain client addresses or paths.
    def do_GET(self):
        if self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

def bind_server(web, start=8765, attempts=20):
    web = Path(web)
    if not (web/'index.html').is_file():
        raise FileNotFoundError('web/index.html missing')
    handler = functools.partial(Handler, directory=str(web))
    last = None
    for port in range(start, min(start+attempts, 65536)):
        try:
            return Server(('127.0.0.1', port), handler)
        except OSError as exc:
            last = exc
    raise OSError('No available local port in requested range') from last

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--no-browser', action='store_true')
    p.add_argument('--diagnostics', action='store_true')
    p.add_argument('--workspace', action='store_true', help='Enable private real-resume intake UI')
    p.add_argument('--data', type=Path, default=ROOT/'data/private-web')
    a = p.parse_args()
    if a.diagnostics:
        # Explicit opt-in: output may contain personal directory names.
        print(json.dumps({'python':sys.version.split()[0], 'executable':sys.executable,
            'prefix':sys.prefix,'basePrefix':sys.base_prefix}, indent=2))
        return
    if sys.version_info < (3,10):
        p.error('Python 3.10+ required')
    if not 1024 <= a.port <= 65516:
        p.error('Port must be between 1024 and 65516')
    if a.workspace:
        from workspace_server import start
        server=start(a.data,a.port)
    else:server=bind_server(ROOT/'web', a.port)
    with server:
        url = 'http://127.0.0.1:'+str(server.server_address[1])+'/'
        version=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
        print('Dagongren '+version+'\n'+url+'\nLocal only. Ctrl+C to stop.',flush=True)
        if a.workspace:print('Private resume workspace enabled; files persist locally. No model or external action.',flush=True)
        if not a.no_browser:
            timer = threading.Timer(0.3, lambda:webbrowser.open(url))
            timer.daemon = True
            timer.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nStopped.')

if __name__ == '__main__':
    try:
        main()
    except (OSError, FileNotFoundError) as exc:
        print('Startup failed: '+str(exc), file=sys.stderr)
        sys.exit(1)
