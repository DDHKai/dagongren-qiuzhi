"""Launch user-selected Chrome with a dedicated local profile, never copy a daily profile."""
import argparse
from pathlib import Path
import subprocess
from project_store import ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--chrome',type=Path,required=True)
    p.add_argument('--profile',type=Path,default=ROOT/'data/chrome-collector');p.add_argument('--port',type=int,default=9333);a=p.parse_args()
    if not a.chrome.is_file() or not 1024<=a.port<=65535:p.error('Select installed Chrome executable and valid local port')
    a.profile.mkdir(parents=True,exist_ok=True)
    subprocess.Popen([str(a.chrome.resolve()),'--user-data-dir='+str(a.profile.resolve()),'--remote-debugging-port='+str(a.port),
        '--remote-debugging-address=127.0.0.1','--no-first-run','--no-default-browser-check','--new-window','https://www.zhipin.com/web/geek/jobs'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('Dedicated Chrome launch requested. Complete login/verification yourself. Do not send passwords or codes. Keep CDP local. Login is not automatically verified.')

if __name__=='__main__':main()
