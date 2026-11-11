"""Validate version markers and optionally rehearse in a clean extracted directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from zipfile import ZipFile
from check_public_files import PUBLIC

ROOT=Path(__file__).resolve().parents[1]

def check_version(root):
    version=(root/'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+-experiment',version):raise ValueError('invalid_version')
    html=(root/'web/index.html').read_text(encoding='utf-8')
    if re.search(r"const VERSION='([^']+)'",html).group(1)!=version:raise ValueError('page_version_mismatch')
    for name in ('README.md','docs/desktop-testing.md'):
        if version not in '\n'.join((root/name).read_text(encoding='utf-8-sig').splitlines()[:5]):
            raise ValueError('current_document_version_mismatch:'+name)
    if (root/'scripts/desktop_launcher.py').read_text(encoding='utf-8').count("ROOT/'VERSION'")!=1:
        raise ValueError('launcher_not_using_version')
    return version

def clean_rehearsal(root):
    version=check_version(root)
    subprocess.run([sys.executable,str(root/'scripts/package_experiment.py')],cwd=root,check=True)
    package=root/'dist'/('dagongren-'+version+'.zip')
    expected=package.with_suffix('.zip.sha256').read_text().split()[0]
    if hashlib.sha256(package.read_bytes()).hexdigest()!=expected:raise ValueError('archive_checksum')
    temp_root=root/'data/clean-tests';temp_root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='clean space ',dir=temp_root) as d:
        dest=Path(d)
        with ZipFile(package) as z:
            expected_names={'dagongren-experiment/'+n for n in PUBLIC}|{'dagongren-experiment/MANIFEST.json'}
            if set(z.namelist())!=expected_names or len(z.namelist())!=len(expected_names):raise ValueError('archive_allowlist')
            z.extractall(dest)
        clean=dest/'dagongren-experiment'
        manifest=json.loads((clean/'MANIFEST.json').read_text())
        if set(manifest)!=set(PUBLIC):raise ValueError('manifest_allowlist')
        for name,digest in manifest.items():
            if hashlib.sha256((clean/name).read_bytes()).hexdigest()!=digest:raise ValueError('manifest_hash')
        if (clean/'data').exists() or (clean/'.git').exists():raise ValueError('private_directory_in_package')
        check_version(clean)
        env=dict(os.environ);env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1'
        subprocess.run([sys.executable,str(clean/'scripts/verify_release.py')],cwd=dest,env=env,check=True,timeout=120)
        print(json.dumps({'cleanRehearsal':'passed','spaceInPath':True,'manifestFiles':len(manifest),
            'runtime':'existing interpreter; not bundled or independently installed',
            'limitations':'same host only; not macOS or clean-machine proof'},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser();p.add_argument('--clean',action='store_true');a=p.parse_args()
    print('Version markers OK: '+check_version(ROOT))
    if a.clean:clean_rehearsal(ROOT)

if __name__=='__main__':main()
