"""Portable local evidence store. Python 3.10+, standard library only."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
    INSERT OR IGNORE INTO schema_version VALUES(1);
    CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, target INTEGER NOT NULL, collection TEXT NOT NULL, review TEXT NOT NULL DEFAULT 'pending');
    CREATE TABLE IF NOT EXISTS sources(hash TEXT PRIMARY KEY, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id));
    CREATE TABLE IF NOT EXISTS observations(run_id TEXT REFERENCES runs(id), company_id TEXT REFERENCES companies(id), job_id TEXT REFERENCES jobs(id), source_hash TEXT REFERENCES sources(hash), PRIMARY KEY(run_id,company_id,job_id,source_hash));
    CREATE TABLE IF NOT EXISTS selections(run_id TEXT REFERENCES runs(id), job_id TEXT REFERENCES jobs(id), action TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'requested', PRIMARY KEY(run_id,job_id,action));
    ''')
    return db

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def import_checkpoint(db, run_id, payload, target=100):
    entries = payload['companies']
    if len({c['companyKey'] for c in entries}) != len(entries):
        raise ValueError('Duplicate company identities in checkpoint')
    with db:
        db.execute("INSERT OR IGNORE INTO runs(id,target,collection) VALUES(?,?,'pending')", (run_id,target))
        if db.execute('SELECT target FROM runs WHERE id=?',(run_id,)).fetchone()[0] != target:
            raise ValueError('Run target is immutable; use a new run ID')
        for c in entries:
            company_id = c['companyKey']
            job = c['job']
            job_id = job['url'].split('?',1)[0]
            if not company_id.startswith('/gongsi/') or '/job_detail/' not in job_id:
                raise ValueError('Invalid company/job identity')
            if '职位描述' not in job['text'] or '工商信息' not in c['company']['text']:
                raise ValueError('Incomplete page evidence')
            text = canonical(c)
            digest = hashlib.sha256(text.encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)',(digest,text))
            db.execute('INSERT OR IGNORE INTO companies VALUES(?)',(company_id,))
            previous = db.execute('SELECT company_id FROM jobs WHERE id=?',(job_id,)).fetchone()
            if previous and previous[0] != company_id:
                raise ValueError('Job/company identity conflict; manual review required')
            db.execute('INSERT OR IGNORE INTO jobs VALUES(?,?)',(job_id,company_id))
            db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?)',(run_id,company_id,job_id,digest))
        count = db.execute('SELECT COUNT(DISTINCT company_id) FROM observations WHERE run_id=?',(run_id,)).fetchone()[0]
        db.execute('UPDATE runs SET collection=? WHERE id=?',('complete' if count>=target else 'partial',run_id))
    return status(db,run_id)

def status(db,run_id):
    row=db.execute('SELECT target,collection,review FROM runs WHERE id=?',(run_id,)).fetchone()
    if not row: raise ValueError('Unknown run')
    count=db.execute('SELECT COUNT(DISTINCT company_id) FROM observations WHERE run_id=?',(run_id,)).fetchone()[0]
    return dict(runId=run_id,target=row[0],collectedCompanies=count,collection=row[1],review=row[2],overallComplete=row[1]=='complete' and row[2]=='complete')

def import_selections(db,run_id,items):
    allowed={'进一步核实','希望收藏','希望沟通'}
    with db:
        for item in items:
            url=item['jobUrl'].split('?',1)[0]
            action=item['requestedAction']
            if action not in allowed: raise ValueError('Unknown requested action')
            if not db.execute('SELECT 1 FROM observations WHERE run_id=? AND job_id=?',(run_id,url)).fetchone():
                raise ValueError('Selection is not part of this run')
            db.execute('INSERT OR IGNORE INTO selections(run_id,job_id,action) VALUES(?,?,?)',(run_id,url,action))
    return {'accepted':len(items),'externalActionsExecuted':0,'status':'requested only; revalidation and authorization required'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--db',type=Path,default=ROOT/'data/project.sqlite3')
    sub=p.add_subparsers(dest='command',required=True)
    for command in ['import','status','select']:
        q=sub.add_parser(command);q.add_argument('--run',required=True)
        if command!='status':q.add_argument('--input',type=Path,required=True)
    args=p.parse_args()
    with connect(args.db) as db:
        if args.command=='status':result=status(db,args.run)
        else:
            payload=json.loads(args.input.read_text(encoding='utf-8-sig'))
            result=import_checkpoint(db,args.run,payload) if args.command=='import' else import_selections(db,args.run,payload['selected'])
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
