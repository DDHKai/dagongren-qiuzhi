"""Fixed-source financial document capture and human evidence review, no company score."""
import argparse
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
import os
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlsplit,urlunsplit,quote
from project_store import ROOT
from resume_workspace import save

POLICY=ROOT/'config/financial-sources.json'
METRICS={'operatingCashFlow':'flow','revenue':'flow','netProfit':'flow','receivables':'balance',
    'cashAndCashEquivalents':'balance','restrictedCash':'balance','availableCash':'balance',
    'shortTermInterestDebt':'balance','interestBearingDebt':'balance'}

def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False).encode()
def policy():return json.loads(POLICY.read_text(encoding='utf-8'))

def official_url(url,market):
    entry=policy()['markets'].get(market)
    if not entry or not isinstance(url,str) or re.search(r'[\x00-\x20]',url):raise ValueError('Unsupported market or URL')
    u=urlsplit(url)
    if u.scheme!='https' or u.hostname not in entry['allowedHosts'] or u.username or u.password or u.port not in (None,443):raise ValueError('Official HTTPS host required')
    return urlunsplit(('https',u.netloc,quote(u.path,safe='/%:@-._~'),quote(u.query,safe='=&%/:@-._~'),''))

def metadata(meta):
    required={'market','issuerLegalName','securityIdentifier','employerLegalName','relationship','documentType','periodStart','periodEnd','disclosureDate','currency','unit','consolidationScope','auditStatus','officialDocumentUrl','latestCheckedAt'}
    if not isinstance(meta,dict) or not required<=set(meta):raise ValueError('Complete explicit metadata required')
    for k in required:
        if not isinstance(meta[k],str) or not meta[k].strip():raise ValueError('Metadata text required')
    official_url(meta['officialDocumentUrl'],meta['market'])
    pattern={'CN':r'\d{6}','HK':r'\d{5}','US':r'\d{10}'}[meta['market']]
    if not re.fullmatch(pattern,meta['securityIdentifier']):raise ValueError('Use stock code or ten-digit CIK')
    for k in ('periodStart','periodEnd','disclosureDate','latestCheckedAt'):date.fromisoformat(meta[k])
    if meta['periodStart']>meta['periodEnd'] or meta['periodEnd']>meta['disclosureDate'] or meta['disclosureDate']>meta['latestCheckedAt']:raise ValueError('Invalid report/check chronology')
    if meta['relationship'] not in ('same-entity','parent-subsidiary','unverified') or meta['auditStatus'] not in ('audited','unaudited','unknown'):raise ValueError('Explicit relation/audit status required')
    if meta['relationship']=='same-entity' and meta['issuerLegalName']!=meta['employerLegalName']:raise ValueError('Different legal names cannot claim same entity')
    return meta

class Redirect(urllib.request.HTTPRedirectHandler):
    def __init__(self,market):self.market=market;self.count=0
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        self.count+=1
        if self.count>3:raise ValueError('Redirect budget')
        newurl=official_url(newurl,self.market)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(meta):
    metadata(meta);url=official_url(meta['officialDocumentUrl'],meta['market'])
    ua='Dagongren-local-research/0.1'
    if meta['market']=='US':
        ua=os.environ.get('DAGONGREN_SEC_USER_AGENT','')
        if '@' not in ua or '\n' in ua or '\r' in ua:raise ValueError('SEC requires user-provided identifying contact User-Agent')
    opener=urllib.request.build_opener(Redirect(meta['market']))
    with opener.open(urllib.request.Request(url,headers={'User-Agent':ua}),timeout=30) as response:
        final=official_url(response.geturl(),meta['market']);chunks=[];total=0
        while block:=response.read(65536):
            total+=len(block)
            if total>25_000_000:raise ValueError('Document size limit')
            chunks.append(block)
    return b''.join(chunks),final

class TextHTML(HTMLParser):
    def __init__(self):super().__init__();self.skip=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag in ('p','div','tr','h1','h2','h3','br'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if tag in ('p','div','tr','h1','h2','h3'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data+' ')

def extract(raw):
    if raw.startswith(b'%PDF-'):
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(raw))
        if reader.is_encrypted or len(reader.pages)>400:raise ValueError('Encrypted or oversized report')
        units=[{'id':'p'+str(i+1),'location':{'page':i+1},'text':p.extract_text() or ''} for i,p in enumerate(reader.pages)]
        kind='pdf'
    elif re.search(br'<(?:!doctype\s+html|html)',raw[:1000],re.I):
        parser=TextHTML();parser.feed(raw.decode('utf-8-sig'));text=''.join(parser.parts)
        units=[{'id':'s'+str(i+1),'location':{'section':i+1},'text':s.strip()} for i,s in enumerate(re.split(r'\n\s*\n',text)) if s.strip()];kind='html'
    else:raise ValueError('Only original PDF or UTF-8 HTML financial documents supported')
    if sum(len(u['text']) for u in units)>4_000_000:raise ValueError('Extracted text limit')
    return {'kind':kind,'units':units,'warnings':['提取文字可能乱码、乱序或遗漏，数值必须对照原页；未自动核验发行人、期间、最新性或雇主关系。']}

def capture(meta,output,fetcher=fetch):
    metadata(meta);output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('Use empty new version directory')
    output.mkdir(parents=True,exist_ok=True)
    try:
        raw,final=fetcher(meta)
        if not raw or len(raw)>25_000_000:raise ValueError('Document size')
        official_url(final,meta['market']);doc=extract(raw)
        (output/('source.'+doc['kind'])).write_bytes(raw);save(output/'extraction.json',doc)
        report={'schemaVersion':1,'metadata':meta,'officialFinalUrl':final,'sourcePlatform':policy()['markets'][meta['market']]['name'],
            'retrievedAt':datetime.now(timezone.utc).isoformat(),'documentSha256':sha(raw),'extractionSha256':sha(canonical(doc)),'metadataSha256':sha(canonical(meta)),
            'status':'source-downloaded-review-required','relationshipStatus':'user-declared-not-independently-verified','latestStatus':'user-declared-check-not-automatically-verified',
            'metrics':[],'riskAssessment':'unknown','companyGrowth':'unknown','automaticScore':None}
        save(output/'report.json',report)
        return report
    except Exception:
        save(output/'status.json',{'status':'source-unavailable-or-unverified','companyGrowth':'unknown','riskAssessment':'unknown','fallbackUsed':False})
        raise

def number(value):
    if not isinstance(value,str):raise ValueError('Numeric original string required')
    value=value.strip().replace(',','').replace('，','').replace(' ','').replace('−','-')
    if value.startswith('(') and value.endswith(')'):value='-'+value[1:-1]
    n=Decimal(value)
    if not n.is_finite():raise ValueError('Finite financial figure required')
    return n

def review(folder,payload,output):
    folder=Path(folder);output=Path(output)
    if output.exists():raise ValueError('Preserve prior review versions')
    report=json.loads((folder/'report.json').read_text(encoding='utf-8'));meta=report['metadata']
    metadata(meta)
    if sha(canonical(meta))!=report['metadataSha256']:raise ValueError('Changed financial metadata')
    doc=json.loads((folder/'extraction.json').read_text(encoding='utf-8'))
    if sha((folder/('source.'+doc['kind'])).read_bytes())!=report['documentSha256'] or sha(canonical(doc))!=report['extractionSha256']:raise ValueError('Changed financial source')
    if payload.get('reviewerConfirmed') is not True:raise ValueError('Explicit original-page review required')
    units={u['id']:u for u in doc['units']}
    def citation(ref):
        if not isinstance(ref,dict) or not isinstance(ref.get('quote'),str) or not ref['quote'].strip() or ref.get('unitId') not in units or ref['quote'] not in units[ref['unitId']]['text']:raise ValueError('Financial citation not in source')
        return {**ref,'location':units[ref['unitId']]['location'],'documentSha256':report['documentSha256']}
    identity=citation(payload['identityEvidence']);period=citation(payload['periodEvidence'])
    if meta['issuerLegalName'] not in identity['quote']:raise ValueError('Issuer name must appear in identity evidence')
    relation=payload.get('relationshipEvidence');relation=citation(relation) if relation else None
    if meta['relationship']=='parent-subsidiary' and relation is None:raise ValueError('Group relationship evidence required; otherwise leave unverified')
    metrics=[];seen=set()
    for m in payload.get('metrics',[]):
        name=m['metric']
        if name not in METRICS or name in seen:raise ValueError('Unsupported/duplicate metric')
        seen.add(name);ref=citation(m['evidence']);n=number(m['value'])
        if name in ('availableCash','restrictedCash','shortTermInterestDebt','interestBearingDebt') and n<0:raise ValueError('Nonnegative cash/debt balance required; verify sign convention')
        # Preserve whitespace between table cells; removing it merges adjacent numbers.
        normalized=re.sub(r'[,，]','',ref['quote']).replace('−','-')
        lexeme=m['value'].strip().replace(',','').replace('，','').replace(' ','').replace('−','-')
        if not re.search(r'(?<![\d.+(\-])'+re.escape(lexeme)+r'(?![\d.)])',normalized):raise ValueError('Value is not a direct original numeric token; no implicit unit conversion')
        if any(m.get(k)!=meta[k] for k in ('currency','unit','consolidationScope','periodEnd')):raise ValueError('Metric scope/unit/date mismatch')
        if METRICS[name]=='flow' and m.get('periodStart')!=meta['periodStart']:raise ValueError('Flow period mismatch')
        if METRICS[name]=='balance' and m.get('periodStart') not in (None,''):raise ValueError('Balance is as-of date, not cumulative flow')
        metrics.append({**m,'evidence':ref,'verification':'human-reviewed-not-automatically-semantic'})
    result={**report,'status':'human-reviewed-evidence','identityEvidence':identity,'periodEvidence':period,'relationshipEvidence':relation,
        'relationshipStatus':'human-attested' if meta['relationship']!='unverified' else 'unverified','metrics':metrics,'riskAssessment':'unknown'}
    finding=payload.get('finding')
    if finding:
        if finding.get('category') not in ('ordinary-fluctuation','attention-needed','major-risk') or not isinstance(finding.get('reason'),str) or not finding['reason'].strip() or not finding.get('evidence'):raise ValueError('Risk finding needs explicit category, reason and citations')
        result['finding']={**finding,'evidence':[citation(r) for r in finding['evidence']],'classification':'human-opinion-not-automatically-verified'}
        result['riskAssessment']=finding['category']
    by_name={m['metric']:m for m in metrics}
    if 'availableCash' in by_name and 'shortTermInterestDebt' in by_name and number(by_name['shortTermInterestDebt']['value'])>0:
        result['shortDebtCoverage']={'ratio':str(number(by_name['availableCash']['value'])/number(by_name['shortTermInterestDebt']['value'])),
            'formula':'explicit availableCash / explicit shortTermInterestDebt, same scope/unit/as-of date','automaticRiskThreshold':None}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    return result

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('capture');q.add_argument('--metadata',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    q=sub.add_parser('review');q.add_argument('--folder',type=Path,required=True);q.add_argument('--review',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:r=capture(json.loads(a.metadata.read_text(encoding='utf-8-sig')),a.output) if a.command=='capture' else review(a.folder,json.loads(a.review.read_text(encoding='utf-8-sig')),a.output)
    except Exception:p.exit(1,'Financial step failed. Check fixed official source, optional PDF dependency, required metadata, quotation and review scope. Unknown is not a company risk.\n')
    print(json.dumps({'status':r['status'],'riskAssessment':r['riskAssessment'],'companyGrowth':r['companyGrowth'],'automaticScore':None},ensure_ascii=False))

if __name__=='__main__':main()
