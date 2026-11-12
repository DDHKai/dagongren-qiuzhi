"""Local cross-device checks, synthetic browser only. Never logs into BOSS or favorites jobs."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from zipfile import ZipFile,BadZipFile
from check_public_files import PUBLIC
from project_store import ROOT

def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def redact(text,root=ROOT):
    for value,label in [(str(root.resolve()),'<PROJECT>'),(str(Path.home()),'<HOME>')]:
        for form in (value,value.replace('\\','/'),json.dumps(value,ensure_ascii=True)[1:-1]):text=text.replace(form,label)
    text=re.sub(r'[A-Za-z]:[\\/]Users[\\/][^\\/\s"\']+', '<WINDOWS-HOME>',text,flags=re.I)
    return re.sub(r'/Users/[^/\s"\']+', '<MAC-HOME>',text)

def source_check(root,archive):
    manifest_path=root/'MANIFEST.json'
    result={'version':(root/'VERSION').read_text(encoding='utf-8').strip(),'snapshot':(root/'TEST_SNAPSHOT').read_text(encoding='utf-8').strip(),'manifestPresent':manifest_path.is_file(),'fileMismatches':[],'archiveSha256':None,'archiveChecksumMatch':False,'archiveLayoutMatches':False}
    manifest={}
    if manifest_path.is_file():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if set(manifest)!=set(PUBLIC):result['fileMismatches'].append('manifest-allowlist')
        for name in PUBLIC:
            p=root/name
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=manifest.get(name):result['fileMismatches'].append(name)
    if archive and archive.is_file() and archive.stat().st_size<=25_000_000:
        actual=hashlib.sha256(archive.read_bytes()).hexdigest();result['archiveSha256']=actual
        checksum=archive.with_suffix(archive.suffix+'.sha256')
        if checksum.is_file():
            fields=checksum.read_text(encoding='utf-8-sig').split();expected=fields[0] if fields else ''
            result['archiveChecksumMatch']=bool(re.fullmatch('[a-fA-F0-9]{64}',expected)) and actual.lower()==expected.lower()
        try:
            with ZipFile(archive) as z:
                expected_names={'dagongren-experiment/'+n for n in PUBLIC}|{'dagongren-experiment/MANIFEST.json'}
                safe=set(z.namelist())==expected_names and len(z.namelist())==len(expected_names) and sum(i.file_size for i in z.infolist())<=20_000_000
                if safe and json.loads(z.read('dagongren-experiment/MANIFEST.json'))==manifest:
                    result['archiveLayoutMatches']=all(hashlib.sha256(z.read('dagongren-experiment/'+name)).hexdigest()==manifest.get(name) for name in PUBLIC)
        except (BadZipFile,KeyError,ValueError):pass
    result['passed']=result['manifestPresent'] and not result['fileMismatches'] and result['archiveChecksumMatch'] and result['archiveLayoutMatches'] and result['version']=='0.2.0-experiment' and result['snapshot']=='v0.2.0-mvp-test1'
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--chrome',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--python-source',default='unspecified-needs-owner-declaration');a=p.parse_args()
    out=a.output.resolve()
    if out.exists() and any(out.iterdir()):p.error('Use a new empty output directory; preserve previous failures')
    out.mkdir(parents=True,exist_ok=True);raw=out/'RAW-PRIVATE';raw.mkdir()
    source=source_check(ROOT,a.archive.resolve());write(out/'source-check.json',source)
    env=dict(os.environ);env.update(PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
    node=shutil.which('node');node_version=None;node_ok=False
    if node:
        try:
            node_version=subprocess.run([node,'--version'],capture_output=True,text=True,timeout=10).stdout.strip();node_ok=int(node_version.lstrip('v').split('.')[0])>=22
        except Exception:pass
    paths={'executable':sys.executable,'prefix':sys.prefix,'basePrefix':sys.base_prefix,'stdlibJson':json.__file__,'stdlibOs':os.__file__}
    environment={'system':platform.system(),'systemRelease':platform.release(),'architecture':platform.machine(),'pythonVersion':platform.python_version(),
        'pythonSourceDeclared':a.python_source,'pythonRuntimePaths':{k:redact(str(v)) for k,v in paths.items()},
        'runtimeDriveLetters':{k:Path(str(v)).drive for k,v in paths.items()},'runtimeMayBeToolManaged':any(t in str(paths).lower() for t in ('workbuddy','codexprimaryruntime')),
        'nodeVersion':node_version,'nodeRequired22Plus':node_ok,'chromeSelected':bool(a.chrome and a.chrome.is_file()),
        'pypdfInstalled':bool(importlib.util.find_spec('pypdf')),'projectPathContainsSpace':' ' in str(ROOT),'testMode':'synthetic-only-favorite-worker-double','hostNameCollected':False}
    write(out/'environment.json',environment);steps=[]
    def run(name,cmd,timeout):
        print('Running '+name,flush=True)
        try:
            r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,timeout=timeout);code=r.returncode;stdout=r.stdout;stderr=r.stderr
        except subprocess.TimeoutExpired as exc:
            code=-1;stdout=exc.stdout or b'';stderr=(exc.stderr or b'')+b'\nTIMEOUT: not passed'
        (raw/(name+'.stdout.bin')).write_bytes(stdout);(raw/(name+'.stderr.bin')).write_bytes(stderr)
        combined=stdout+b'\n[STDERR]\n'+stderr;(raw/(name+'.raw.txt')).write_bytes(combined)
        log=combined.decode('utf-8',errors='replace').replace('\r\n','\n').replace('\r','\n')
        (out/(name+'.txt')).write_text(redact(log),encoding='utf-8',newline='\n')
        steps.append({'step':name,'exitCode':code,'passed':code==0});write(out/'steps.json',steps);print(name+': exit '+str(code),flush=True);return code,log
    if not source['passed']:
        summary={'schemaVersion':1,'version':source['version'],'snapshot':source['snapshot'],'syntheticCorePassed':False,'status':'wrong-or-unverified-source','realPlatform':'not-run','manualExperience':'not-run'}
        write(out/'device-summary.json',summary);print('Source integrity/version check failed; preserve package and checksum.');return 2
    checks,_=run('checks',[sys.executable,str(ROOT/'scripts/verify_release.py')],360)
    clean,_=run('clean-check',[sys.executable,str(ROOT/'scripts/check_release_layout.py'),'--clean'],420)
    browser=None;browser_proof=False
    if node_ok and a.chrome and a.chrome.is_file():
        env.update(DAGONGREN_TEST_PYTHON=sys.executable,DAGONGREN_TEST_CHROME=str(a.chrome.resolve()))
        browser,log=run('browser-check',[node,str(ROOT/'scripts/test_workspace_browser.mjs')],180)
        matches=re.findall(r'Synthetic test artifacts: (.+)',log)
        if matches:
            folder=Path(matches[-1].strip()).resolve()
            if folder.is_relative_to((ROOT/'data/test-tmp').resolve()):
                for filename in ('workspace.png','company-research.png','action-ledger.png','result-workspace.png','result-export.png'):
                    if (folder/filename).is_file():
                        (out/'screenshots').mkdir(exist_ok=True);shutil.copyfile(folder/filename,out/'screenshots'/filename)
                if (folder/'browser-summary.json').is_file():
                    info=json.loads((folder/'browser-summary.json').read_text(encoding='utf-8'));browser_proof=info.get('status')=='passed' and info.get('syntheticOnly') is True and info.get('favoriteWorkerDouble') is True and info.get('realBossTouched') is False
                    shutil.copyfile(folder/'browser-summary.json',out/'browser-summary.json')
                for old,new in [('private-job-report.json','synthetic-result.json'),('private-job-report.html','synthetic-result.html')]:
                    if (folder/'downloads'/old).is_file():shutil.copyfile(folder/'downloads'/old,out/new)
    passed=checks==0 and clean==0 and browser==0 and node_ok and browser_proof
    summary={'schemaVersion':1,'version':source['version'],'snapshot':source['snapshot'],'generatedAtUTC':datetime.now(timezone.utc).isoformat(),
        'syntheticCorePassed':passed,'status':'synthetic-core-passed' if passed else 'failed-or-incomplete','steps':steps,'browserEvidencePresent':browser_proof,
        'realPlatform':'not-run-by-this-tool','manualExperience':'not-run-by-this-tool','pdfCoverage':'optional-parser-installed' if environment['pypdfInstalled'] else 'not-installed-not-fully-tested',
        'returnPolicy':'RAW-PRIVATE, browser profiles, workspace databases, real resumes and real BOSS observations must not be returned'}
    write(out/'device-summary.json',summary)
    template=(ROOT/'docs/device-feedback-template.md').read_text(encoding='utf-8');(out/'manual-results.md').write_text(template,encoding='utf-8')
    print('Synthetic core passed: '+str(passed)+'. Fill manual-results.md; inspect all share files. Do not return RAW-PRIVATE.')
    return 0 if passed else 1 if any(s['exitCode'] not in (0,) for s in steps) else 2

if __name__=='__main__':raise SystemExit(main())
