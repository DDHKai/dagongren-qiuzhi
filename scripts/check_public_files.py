"""Conservative allowlist scan; does not publish, copy, or modify files."""
import json
import re
from project_store import ROOT

PUBLIC=['.gitignore','README.md','docs/开源边界与事实证据.md','examples/synthetic-resume.json']+['scripts/'+x for x in ['project_store.py','review_store.py','candidate_facts.py','test_project_store.py','test_review_store.py','test_candidate_facts.py','check_public_files.py']]
PUBLIC += ['web/index.html','docs/跨设备实验测试.md','scripts/package_experiment.py','scripts/test_experiment.mjs']
PUBLIC += ['start-windows.bat','start-macos.command','scripts/desktop_launcher.py','scripts/test_desktop_launcher.py','docs/desktop-testing.md']
PUBLIC += ['LICENSE','CONTRIBUTING.md','SECURITY.md','docs/reference-structure.md','scripts/verify_release.py']

def scan(root=ROOT):
    findings=[]
    patterns={'user-home':r'[A-Za-z]:\\Users\\[^\\\s]+','credential':r'\bsk-[A-Za-z0-9_-]{16,}','phone':r'(?<!\d)1[3-9]\d{9}(?!\d)'}
    # Private identifiers are read locally; never included in scan output.
    private=root/'data/attachments/resume.merged.json'
    names=[]
    if private.exists():
        data=json.loads(private.read_text(encoding='utf-8'))
        name=data.get('personalInfo',{}).get('name',{}).get('value')
        if name:names.append(name)
    for path in PUBLIC:
        file=root/path
        if not file.is_file():findings.append({'file':path,'type':'missing'});continue
        text=file.read_text(encoding='utf-8')
        for label,pattern in patterns.items():
            if re.search(pattern,text):findings.append({'file':path,'type':label})
        if any(name in text for name in names):findings.append({'file':path,'type':'private-identifier'})
    return {'filesChecked':len(PUBLIC),'findings':findings,'scope':'allowlist only; not a guarantee against all identifying content'}

if __name__=='__main__':
    result=scan();print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(bool(result['findings']))
