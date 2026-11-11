"""Local resume intake and explicit fact confirmation. No model/network calls."""
import argparse
import hashlib
import json
import secrets
from pathlib import Path
from candidate_facts import extract_facts

def digest(data):return hashlib.sha256(data).hexdigest()
def save(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)

def create(source,conditions_path,output):
    source=Path(source);output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('Output directory must be empty')
    raw=source.read_bytes()
    if len(raw)>5_000_000:raise ValueError('Resume exceeds 5MB')
    text=raw.decode('utf-8-sig')
    if source.suffix.lower()=='.json':resume=json.loads(text)
    elif source.suffix.lower()=='.txt':
        resume={'experiences':[{'responsibilitiesRaw':text}], 'parseStatus':'raw-text-unstructured-no-inference'}
    else:raise ValueError('Only UTF-8 .json or .txt supported; PDF/DOCX not yet supported')
    if not isinstance(resume,dict) or not isinstance(resume.get('experiences'),list) or not resume['experiences']:raise ValueError('experiences must be a nonempty list')
    for exp in resume['experiences']:
        if not isinstance(exp,dict):raise ValueError('Invalid experience')
        for field in ('responsibilitiesRaw','achievementsRaw'):
            if exp.get(field) is not None and not isinstance(exp[field],str):raise ValueError('Evidence fields must be text')
    conditions=json.loads(Path(conditions_path).read_text(encoding='utf-8-sig'))
    if not isinstance(conditions,dict) or set(conditions)!={'must','prefer','ignore'}:raise ValueError('Conditions require must/prefer/ignore')
    seen=set()
    for group in conditions.values():
        if not isinstance(group,list):raise ValueError('Condition groups must be lists')
        for item in group:
            if not isinstance(item,str) or not item.strip() or item.strip() in seen:raise ValueError('Conditions must be nonempty, unique text')
            seen.add(item.strip())
    salt=secrets.token_bytes(32)
    h=digest(json.dumps(resume,ensure_ascii=False,sort_keys=True).encode())
    facts=extract_facts(resume,salt,h)
    if not facts:raise ValueError('No extractable responsibility/achievement lines')
    output.mkdir(parents=True,exist_ok=True)
    (output/'fact-id-salt').write_bytes(salt)
    (output/'source.bin').write_bytes(raw)
    save(output/'resume.json',resume)
    save(output/'facts.json',{'sourceHash':h,'facts':facts})
    save(output/'conditions.json',{'status':'user-review-required','groups':conditions})
    save(output/'manifest.json',{'schemaVersion':1,'sourceSha256':digest(raw),'resumeHash':h,
        'facts':len(facts),'networkCalls':0,'externalActions':0,'stage':'intake-awaiting-review'})
    return {'stage':'intake-awaiting-review','facts':len(facts),'networkCalls':0,'externalActions':0}

def confirm(output,ids):
    output=Path(output)
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    resume=json.loads((output/'resume.json').read_text(encoding='utf-8'))
    if digest((output/'source.bin').read_bytes())!=manifest['sourceSha256'] or digest(json.dumps(resume,ensure_ascii=False,sort_keys=True).encode())!=manifest['resumeHash']:
        raise ValueError('Source changed; create a new intake version')
    data=json.loads((output/'facts.json').read_text(encoding='utf-8'))
    expected=extract_facts(resume,(output/'fact-id-salt').read_bytes(),manifest['resumeHash'])
    if len(data['facts'])!=len(expected):raise ValueError('Fact set changed')
    for actual,original in zip(data['facts'],expected):
        if any(actual.get(k)!=original[k] for k in ('id','quote','path','sourceHash')):raise ValueError('Fact evidence changed')
    available={f['id'] for f in data['facts']}
    if not ids or not set(ids)<=available:raise ValueError('Explicit known fact IDs required')
    for f in data['facts']:
        if f['id'] in ids:f['status']='candidate-confirmed'
    save(output/'facts.json',data)
    return {'confirmed':sum(f['status']=='candidate-confirmed' for f in data['facts']),
        'meaning':'User-confirmed source statement; not independently verified employment evidence'}

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('create');q.add_argument('--resume',type=Path,required=True);q.add_argument('--conditions',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    q=sub.add_parser('confirm');q.add_argument('--output',type=Path,required=True);q.add_argument('--fact-id',action='append',required=True)
    a=p.parse_args()
    try:r=create(a.resume,a.conditions,a.output) if a.command=='create' else confirm(a.output,a.fact_id)
    except (ValueError,OSError,KeyError,TypeError):p.exit(1,'Intake failed: check input format, evidence integrity or output directory; raw personal content is not printed.\n')
    print(json.dumps(r,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
