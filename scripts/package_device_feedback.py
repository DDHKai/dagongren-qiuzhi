"""Pack reviewed test feedback only. Never uploads; excludes raw/private files by allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile,ZIP_DEFLATED

FILES=('device-summary.json','source-check.json','environment.json','steps.json','checks.txt','clean-check.txt','browser-check.txt','browser-summary.json','synthetic-result.json','synthetic-result.html','manual-results.md')
def pack(root,output,reviewed):
    root=Path(root).resolve();output=Path(output)
    if reviewed is not True:raise ValueError('Review every text and image before packing')
    if output.exists():raise ValueError('Use a new output filename')
    chosen=[root/name for name in FILES if (root/name).is_file()]
    chosen += sorted((root/'screenshots').glob('*.png')) if (root/'screenshots').is_dir() else []
    if not chosen:raise ValueError('No allowlisted feedback files')
    for file in chosen:
        if file.is_symlink() or not file.resolve().is_relative_to(root) or file.stat().st_size>15_000_000:raise ValueError('Unsafe or oversized feedback file')
        if file.suffix!='.png':
            text=file.read_text(encoding='utf-8-sig')
            for pattern in (r'[A-Za-z]:[\\/]Users[\\/][^\\/\s]+',r'/Users/[^/\s]+',r'(?<!\d)1[3-9]\d{9}(?!\d)',r'\b(?:gh[pousr]_|sk-)[A-Za-z0-9_-]{16,}',r'securityId='):
                if re.search(pattern,text):raise ValueError('Possible private content: '+file.name+'; review locally, never print matching content')
    manifest={'schemaVersion':1,'snapshot':'v0.2.0-mvp-test1','humanReviewAcknowledged':True,'files':{str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in chosen},'missingFiles':[n for n in FILES if not (root/n).exists()],'limitations':'Allowlist/regex cannot certify anonymity; human review remains required. Missing files do not imply PASS.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,'x',ZIP_DEFLATED) as z:
        for file in chosen:z.write(file,'device-results/'+file.relative_to(root).as_posix())
        z.writestr('device-results/feedback-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    digest=hashlib.sha256(output.read_bytes()).hexdigest();output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n',encoding='utf-8')
    return {'files':len(chosen),'missingFiles':manifest['missingFiles'],'sha256':digest,'uploaded':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--reviewed',action='store_true');a=p.parse_args()
    try:print(json.dumps(pack(a.results,a.output,a.reviewed),ensure_ascii=False))
    except (ValueError,OSError) as exc:p.exit(1,str(exc)+'\n')
if __name__=='__main__':main()
