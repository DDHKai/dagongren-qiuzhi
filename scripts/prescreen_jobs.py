"""Conservative evidence-based prescreen. No AI, network or employment guarantees."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

LEVEL={'初中':0,'高中':1,'中专':1,'大专':2,'本科':3,'硕士':4,'博士':5}

def validate(policy):
    if not isinstance(policy,dict) or not policy or not set(policy)<={'city','salaryMinK','salaryBasis','weekend','candidateEducation'}:raise ValueError('Explicit supported policy required')
    if not set(policy)&{'city','salaryMinK','weekend','candidateEducation'} or ('salaryBasis' in policy and 'salaryMinK' not in policy):raise ValueError('No effective criteria')
    if 'salaryMinK' in policy:
        if type(policy['salaryMinK']) not in (float,int) or not 0<=policy['salaryMinK']<=200 or policy.get('salaryBasis') not in ('fixed','published-lower-bound'):raise ValueError('salary requires min and explicit basis')
    if policy.get('weekend','double')!='double':raise ValueError('Only hard double-weekend constraint supported')
    if 'candidateEducation' in policy and policy['candidateEducation'] not in LEVEL:raise ValueError('Unknown candidate education')
    if 'city' in policy and (not isinstance(policy['city'],str) or not re.fullmatch('[\u4e00-\u9fff]{2,10}',policy['city'])):raise ValueError('Explicit Chinese city required')
    return policy

def evidence(source,field,start,end):
    text=source.get('text','')
    return {'field':field,'quote':text[start:end],'start':start,'end':end,
        'sourceSha256':hashlib.sha256(text.encode()).hexdigest(),'sourceUrl':source.get('url'), 'capturedAt':source.get('capturedAt')}

def segment(source,begin,end,field):
    text=source.get('text','');return text[begin:end],lambda a,b:evidence(source,field,begin+a,begin+b)

def assess(job,company,policy):
    validate(policy);source=job['source'];text=source.get('text','')
    title=re.search(r'^「(.+?)招聘」',source.get('title',''))
    title=title.group(1) if title else source.get('jobTitle','')
    start=text.find(title) if title else -1
    if start<0:
        return {'jobId':job['id'],'companyId':job.get('companyKey'),'group':'值得核实','dimensions':{'sourceScope':{'status':'unknown','reason':'未定位本岗位标题，不从推荐岗位或正文猜测头部字段','evidence':[]}},'review':'pending'}
    header_end=min([p for marker in ('感兴趣','立即沟通','职位描述') if (p:=text.find(marker,start))>=0] or [len(text)])
    header,href=segment(source,start,header_end,'job.header')
    jd_start=text.find('职位描述',header_end)
    if jd_start<0:jd_start=header_end
    jd_end=min([p for marker in ('竞争力分析','BOSS 安全提示','更多职位','看过该职位的人还看了') if (p:=text.find(marker,jd_start+1))>=0] or [len(text)])
    jd,jref=segment(source,jd_start,jd_end,'job.description')
    dims={};notes=[]
    def result(status,reason,refs):return {'status':status,'reason':reason,'evidence':refs}
    if 'salaryMinK' in policy:
        range_pattern=r'(\d+(?:\.\d+)?)\s*[Kk]?\s*[-–—~至]\s*(\d+(?:\.\d+)?)\s*[Kk]'
        ranges=list(re.finditer(range_pattern,header))
        body_ranges=list(re.finditer(r'(?:薪资|月薪|月收入)[^\n]{0,12}?'+range_pattern,jd))
        fixed=list(re.finditer(r'(?:无责)?底薪\s*[:：]?\s*(\d+(?:\.\d+)?)\s*([Kk千]|元)|固定月薪\s*[:：]?\s*(\d+(?:\.\d+)?)\s*([Kk千]|元)',jd))
        refs=[href(m.start(),m.end()) for m in ranges]+[jref(m.start(),m.end()) for m in fixed+body_ranges]
        fixed_values=[float(m.group(1) or m.group(3))/(1000 if (m.group(2) or m.group(4))=='元' else 1) for m in fixed]
        minimum=policy['salaryMinK']
        ambiguous_fixed=any(re.search('含绩效|含提成|不保证|非固定|不承诺|试用|转正',jd[max(0,m.start()-10):m.end()+16]) for m in fixed)
        if policy['salaryBasis']=='fixed':
            if not fixed_values and len(ranges)==1 and float(ranges[0].group(2))<minimum:dims['salary']=result('disclosed-mismatch','披露薪资上限低于底线，固定构成仍未核实；不等于已获报价',refs)
            elif not fixed_values:dims['salary']=result('unknown','仅有发布区间或薪资构成未披露，不能确认固定底薪',refs)
            elif ambiguous_fixed:dims['salary']=result('unknown','固定薪资附近有绩效/试用阶段/否定限定，须确认构成和适用阶段',refs)
            elif len(set(fixed_values))>1:dims['salary']=result('conflict','出现不同固定薪资，须核实适用阶段与绩效条件',refs)
            else:dims['salary']=result('disclosed-match' if fixed_values[0]>=minimum else 'disclosed-mismatch','按明确底薪/固定月薪原文比较，尚非针对求职者报价',refs)
        elif len(ranges)!=1:dims['salary']=result('unknown' if not ranges else 'conflict','发布区间缺失或不唯一；不以年薪/日薪换算月薪',refs)
        else:dims['salary']=result('disclosed-match' if float(ranges[0].group(1))>=minimum else 'disclosed-mismatch','比较发布区间下限；不等于固定薪资或实际报价',refs)
        if ranges and body_ranges and {(float(m.group(1)),float(m.group(2))) for m in ranges}!={(float(m.group(1)),float(m.group(2))) for m in body_ranges}:
            dims['salary']=result('conflict','头部与正文薪资范围不同，需核实组成与适用范围',refs)
        if re.search(r'年薪|日薪|时薪|[Kk]\s*[/／]\s*(?:年|天|时)',header):
            dims['salary']=result('unknown','非明确月薪口径，不能自动换算',refs)
    if 'weekend' in policy:
        refs=[];positive=False;negative=False
        scopes=[(header,href),(jd,jref)]
        if company and job.get('companyKey')==company.get('id'):
            cs=company['source'];ct=cs.get('text','');a=ct.find('工作时间及福利')
            if a>=0:
                b=min([p for marker in ('招聘Boss','企业服务热线','查看所有职位') if (p:=ct.find(marker,a+1))>=0] or [len(ct)])
                scopes.append(segment(cs,a,b,'company.workBenefits'))
        for s,ref in scopes:
            # Negative words consume their embedded 双休 so they cannot become positive.
            for m in re.finditer(r'不(?:提供|是)?双休|非双休|无双休|单双休|大小休|排班轮休|单休|每周休息一天|周休[一1]天|双休',s):
                refs.append(ref(m.start(),m.end()))
                if re.search('客户|其他岗位|不接受|不要求',s[max(0,m.start()-10):m.start()]):continue
                if m.group()=='双休':positive=True
                else:negative=True
        dims['weekend']=result('conflict' if positive and negative else 'disclosed-match' if positive else 'disclosed-mismatch' if negative else 'unknown','双休正反证据并存需核实' if positive and negative else '仅比较本岗位及同主体工时福利；不加班不等于双休',refs)
    if 'candidateEducation' in policy:
        tags=list(re.finditer('学历不限|初中|高中|中专|大专|本科|硕士|博士',header));refs=[href(m.start(),m.end()) for m in tags]
        strict=[];unlimited=[];preferred=[]
        for m in re.finditer(r'(?:统招|全日制)?(初中|高中|中专|大专|本科|硕士|博士)(?:及以上|以上|学历|毕业)|学历不限|不限学历',jd):
            quote=jd[max(0,m.start()-10):min(len(jd),m.end()+12)]
            refs.append(jref(m.start(),m.end()))
            if m.group() in ('学历不限','不限学历'):unlimited.append(m)
            elif any(k in quote for k in ('优先','不限','无需','不要求')):preferred.append(m)
            else:strict.append(LEVEL[m.group(1)])
        rank=LEVEL[policy['candidateEducation']]
        tagranks=[LEVEL[m.group()] for m in tags if m.group() in LEVEL]
        if strict and (unlimited or any(m.group()=='学历不限' for m in tags)):
            dims['education']=result('conflict','正文学历门槛与不限标签冲突',refs)
        elif strict:dims['education']=result('disclosed-match' if rank>=max(strict) else 'disclosed-mismatch','正文明确门槛与本人提供学历比较；不核验学历真实性',refs)
        elif unlimited or any(m.group()=='学历不限' for m in tags):dims['education']=result('disclosed-match','披露不限学历，不代表其他条件合格',refs)
        elif tagranks and rank>=max(tagranks):dims['education']=result('disclosed-match','仅标签符合，正文未额外证实',refs)
        else:dims['education']=result('unknown','标签高于本人学历或未明确，需问等效经验/是否硬门槛；优先不等于必须',refs)
    if 'city' in policy:
        city=policy['city'].removesuffix('市');matches=list(re.finditer(r'(?:^|\n)\s*([\u4e00-\u9fff]{2,10})\s+(?:\d+(?:-\d+)?年|经验|学历|在校)',header))
        refs=[href(m.start(),m.end()) for m in matches]
        cities={m.group(1).removesuffix('市') for m in matches}
        address=list(re.finditer(r'(?:实际)?(?:办公地址|工作地点|工作地址)\s*[:：]?\s*([^\n]{1,100})',jd))
        known=['北京','上海','广州','深圳','杭州','福州','义乌','宁波','南京','成都','武汉','重庆','苏州','嘉兴','温州','丽水']
        for m in address:
            refs.append(jref(m.start(),m.end()))
            cities.update(c for c in known if c in m.group(1))
            if city in m.group(1):cities.add(city)
        mobility=list(re.finditer('驻点|驻场|出差|往返|多地办公',jd));refs += [jref(m.start(),m.end()) for m in mobility]
        dims['city']=result('conflict' if len(cities)>1 else 'unknown' if not cities or mobility else 'disclosed-match' if city in cities else 'disclosed-mismatch','岗位地点披露对比；多地/驻点需核实，未借用公司注册地址',refs)
    if re.search('合伙人|联合创始|招商|销售',title):notes.append('标题涉及销售/招商/合伙模式，需确认劳动关系与固定报酬；尚未评判能力匹配')
    states=[d['status'] for d in dims.values()]
    group='明确存在取舍' if 'disclosed-mismatch' in states else '值得核实' if any(s in ('unknown','conflict') for s in states) else '披露条件满足'
    return {'jobId':job['id'],'jobTitle':title,'companyId':job.get('companyKey'),'group':group,'dimensions':dims,'notes':notes,'review':'pending','qualification':'仅本轮明确条件的披露预筛；不是录用或固定报价确认'}

def run(data,policy):
    validate(policy)
    if not isinstance(data,dict) or not isinstance(data.get('jobs'),list) or not isinstance(data.get('companies'),list):raise ValueError('Collector schema required')
    if len(data['jobs'])>5000 or len(data['companies'])>1000:raise ValueError('Evidence budget exceeded')
    if len({j['id'] for j in data['jobs']})!=len(data['jobs']) or len({c['id'] for c in data['companies']})!=len(data['companies']):raise ValueError('Duplicate identities')
    for c in data['companies']:
        u=urlsplit(c['source']['url'])
        if u.scheme!='https' or u.hostname!='www.zhipin.com' or u.path!=c['id'] or not re.fullmatch(r'/gongsi/[^/]+\.html',u.path):raise ValueError('Company identity/source mismatch')
    for j in data['jobs']:
        u=urlsplit(j['source']['url'])
        if u.scheme!='https' or u.hostname!='www.zhipin.com' or j['id']!='https://www.zhipin.com'+u.path or not re.fullmatch(r'/job_detail/[^/]+\.html',u.path) or not isinstance(j['source']['text'],str):raise ValueError('Job identity/source mismatch')
    companies={c['id']:c for c in data['companies']}
    rows=[assess(j,companies.get(j.get('companyKey')),policy) for j in data['jobs']]
    grouped={}
    for r in rows:grouped.setdefault(r['companyId'] or 'unknown:'+r['jobId'],[]).append(r['jobId'])
    reasons={}
    for row in rows:
        for name,d in row['dimensions'].items():
            if d['status']!='disclosed-match':
                key=name+':'+d['status'];reasons[key]=reasons.get(key,0)+1
    return {'schemaVersion':1,'policy':policy,'jobs':rows,'companies':grouped,'counts':{g:sum(r['group']==g for r in rows) for g in ('披露条件满足','值得核实','明确存在取舍')},'reasonCounts':reasons,'review':'pending','coverage':{'jobs':len(rows),'platformCompanies':len({j.get('companyKey') for j in data['jobs'] if j.get('companyKey') in companies}),'targetCompanies':data.get('targetCompanies'),'collectionStatus':data.get('status')}}

def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--policy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Use a new output file to preserve earlier results')
    try:result=run(json.loads(a.checkpoint.read_text(encoding='utf-8-sig')),json.loads(a.policy.read_text(encoding='utf-8-sig')))
    except (ValueError,KeyError,TypeError,OSError):p.exit(1,'Prescreen failed: check checkpoint and explicit policy. Raw personal content is not printed.\n')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'counts':result['counts'],'review':'pending'},ensure_ascii=False))

if __name__=='__main__':main()
