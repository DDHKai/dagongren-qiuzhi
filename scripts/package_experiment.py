"""Build a clean test ZIP from the reviewed public allowlist, never the workspace."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from check_public_files import PUBLIC, scan

def main():
    root=Path(__file__).resolve().parents[1]
    result=scan(root)
    if result['findings']:
        raise SystemExit(json.dumps(result,ensure_ascii=False))
    out=root/'dist'
    out.mkdir(exist_ok=True)
    target=out/'dagongren-0.1.0-experiment.zip'
    manifest={}
    with ZipFile(target,'w',ZIP_DEFLATED) as archive:
        for name in PUBLIC:
            data=(root/name).read_bytes()
            archive.writestr('dagongren-experiment/'+name,data)
            manifest[name]=hashlib.sha256(data).hexdigest()
        archive.writestr('dagongren-experiment/MANIFEST.json',json.dumps(manifest,indent=2))
    checksum=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(checksum+'  '+target.name+'\n',encoding='utf-8')
    print(json.dumps({'archive':str(target),'files':len(manifest),'sha256':checksum},ensure_ascii=False))

if __name__=='__main__':main()
