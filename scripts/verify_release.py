"""Run local release checks; does not publish or certify real-device support."""
import re
import shutil
import subprocess
import sys
from pathlib import Path
from check_public_files import PUBLIC, scan

def main():
    root=Path(__file__).resolve().parents[1]
    result=scan(root)
    if result['findings']:raise SystemExit(str(result))
    from check_release_layout import check_version
    check_version(root)
    for name in PUBLIC:
        if name.endswith('.md'):
            for target in re.findall(r'\]\(([^)]+)\)',(root/name).read_text(encoding='utf-8-sig')):
                if '://' not in target and not target.startswith('#'):
                    if not ((root/name).parent/target.split('#')[0]).exists():
                        raise SystemExit('Broken local link: '+name)
    for name in ['test_project_store.py','test_review_store.py','test_candidate_facts.py','test_desktop_launcher.py','test_audit_test_log.py','test_release_layout.py','test_resume_workspace.py','test_resume_document.py']:
        subprocess.run([sys.executable,str(root/'scripts'/name)],cwd=root,check=True)
    node=shutil.which('node')
    if node:subprocess.run([node,str(root/'scripts/test_experiment.mjs')],cwd=root,check=True)
    else:print('SKIP JavaScript tests: Node unavailable; not a full validation')
    print('PASS local checks. Real-device testing and manual privacy review remain required.')

if __name__=='__main__':main()
