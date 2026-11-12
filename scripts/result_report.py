"""Local decision report: separate evidence dimensions, explicit choices, no total score."""
import copy
import hashlib
from datetime import datetime,timezone
from html import escape
import json
import re
from urllib.parse import urlsplit
from ability_review import hash_json,load_facts,generate as ability_generate,review as ability_review
from prescreen_jobs import run as prescreen

def read(path):return json.loads(path.read_text(encoding='utf-8'))

def context(folder):
    meta=read(folder/'case.json');candidate=meta['versions'][-1];market=meta['marketReports'][-1]
    facts=load_facts(folder/candidate);checkpoint=read(folder/market/'checkpoint.json');screen=read(folder/market/'report.json')
    if hash_json(prescreen(checkpoint,screen['policy']))!=hash_json(screen):raise ValueError('Prescreen/source changed')
    abilities={};research={};hashes={}
    for category,target,key in [('abilityReports',abilities,None),('researchReports',research,'companyId')]:
        for version in meta.get(category,[]):
            r=read(folder/version/'report.json');ident=r.get(key) if key else r['context']['jobId']
            target[ident]=r;hashes[version]=hash_json(r)
    evidence={'candidateVersion':candidate,'marketVersion':market,'factsHash':hash_json(facts),
        'checkpointHash':hash_json(checkpoint),'screenHash':hash_json(screen),'reviewHashes':hashes}
    return {'meta':meta,'facts':facts,'checkpoint':checkpoint,'screen':screen,'abilities':abilities,'research':research,
        'evidence':evidence,'hash':hash_json(evidence)}

def size(company):
    if not company:return {'status':'unknown','value':'未披露','evidence':[]}
    source=company['source'];text=source['text'];end=min([p for marker in ('公司简介','公司介绍','热招职位','看过该公司') if (p:=text.find(marker))>=0] or [min(len(text),2500)])
    header=text[:end];matches=list(re.finditer(r'(?<!\d)(?:\d[\d,]*\s*[-—至]\s*\d[\d,]*人|\d[\d,]*人(?:以上|以下))',header))
    values={m.group() for m in matches}
    return {'status':'disclosed' if len(values)==1 else 'conflict' if values else 'unknown','value':next(iter(values)) if len(values)==1 else '规模冲突' if values else '未披露',
        'evidence':[{'quote':m.group(),'start':m.start(),'end':m.end(),'sourceUrl':source['url'],'sourceHash':hash_json(text),'capturedAt':source.get('capturedAt')} for m in matches]}

def ability_for(job,c):
    r=c['abilities'].get(job['id'])
    if not r:return None,'not-reviewed'
    if r['candidateVersion']!=c['evidence']['candidateVersion'] or r['marketVersion']!=c['evidence']['marketVersion'] or r['context']['candidateFactsHash']!=c['evidence']['factsHash'] or r['context']['jobSourceHash']!=hashlib.sha256(job['source']['text'].encode()).hexdigest():return None,'stale'
    # Rebuild source fragments and revalidate all positive claims before using cached review.
    draft=ability_generate(job,c['facts'])
    if hash_json(r['facts'])!=c['evidence']['factsHash'] or r['contextHash']!=draft['contextHash']:raise ValueError('Changed ability facts/context')
    if [(x['id'],x['quote']) for x in r['requirements']]!=[(x['id'],x['quote']) for x in draft['requirements']]:raise ValueError('Changed requirement quotations')
    items=[{'requirementId':x['id'],'decision':x['decision'],'factIds':x['selectedFactIds'],'rationale':x['rationale']} for x in r['requirements'] if x['decision']!='unreviewed']
    validated=ability_review(draft,items,draft['contextHash'],True) if items else draft
    if validated['reviewStatus']!=r['reviewStatus']:raise ValueError('Changed review coverage')
    return r,r['reviewStatus']

def advice(row,ability):
    emphasize=[];gaps=[]
    if ability:
        facts={f['id']:f for f in ability['facts']}
        for r in ability['requirements']:
            if r['decision'] in ('supported','partial'):
                for fid in r['selectedFactIds']:
                    f=facts[fid]
                    if f['status']=='candidate-confirmed' and fid not in {e['factId'] for e in emphasize}:
                        emphasize.append({'factId':fid,'quote':f['quote'],'sourceHash':f['sourceHash'],'jobQuote':r['quote'],'decision':r['decision'],'reason':r['rationale']})
            if r['decision'] in ('partial','unknown','evidence-gap'):
                gaps.append({'jobQuote':r['quote'],'reason':r['rationale'],'meaning':'仍需核实或补证，不等于没有能力'})
    questions=[{'dimension':k,'question':{'salary':'针对本人，这个岗位的固定月薪、绩效占比及试用期口径分别是什么？','weekend':'针对这个岗位，是否固定双休？大促或值班如何安排？','education':'学历要求是否为该岗位硬性门槛，是否接受本人已说明的学历？','city':'本人实际工作地点、驻场及出差要求是什么？'}.get(k,'该来源范围和条件适用于这个岗位吗？'),'evidence':v['evidence']}
        for k,v in row['dimensions'].items() if v['status'] in ('unknown','conflict')]
    for k,v in row['dimensions'].items():
        if v['status']=='disclosed-mismatch':gaps.append({'dimension':k,'reason':v['reason'],'evidence':v['evidence'],'meaning':'当前明确条件存在取舍；未自动放宽'})
    if not ability:questions.append({'dimension':'ability','question':'请先复核岗位核心任务与本人经历的直接交集，尚不能认定能力匹配。','evidence':[]})
    questions.append({'dimension':'employer','question':'招聘主体、劳动合同主体与实际用工主体是否一致？','evidence':[]})
    return {'emphasize':emphasize,'verify':questions,'possibleMismatch':gaps,'scope':'从已确认事实与人工对照生成的沟通提纲，不自动发送，不包装未证明能力'}

def generate(folder,priority='fit'):
    if priority not in ('fit','treatment','prospect'):raise ValueError('Unknown priority')
    c=context(folder);companies={x['id']:x for x in c['checkpoint']['companies']};jobs={x['id']:x for x in c['checkpoint']['jobs']};rows=[]
    for screened in c['screen']['jobs']:
        j=jobs[screened['jobId']];cid=screened['companyId'];company=companies.get(cid);a,status=ability_for(j,c)
        financial=c['research'].get(cid);financial=financial if financial and financial['marketVersion']==c['evidence']['marketVersion'] else None
        row={**screened,'jobTitle':screened.get('jobTitle') or '岗位标题待核实','companyName':(company['source'].get('title') or '公司名称待核实') if company else '主体未定位','companyIdentified':bool(company),
            'companySize':size(company),'abilityStatus':status,'abilityRequirements':a['requirements'] if a else [],'abilityWarnings':a['warnings'] if a else [],
            'companyResearch':financial or {'riskAssessment':'unknown','companyGrowth':'unknown','status':'not-researched'},
            'sourceUrl':j['id'],'capturedAt':j['source'].get('capturedAt'),
            'sourceTextHash':hash_json(j['source']['text']),'actions':'收藏执行以动作台账及刷新证据为准；沟通、简历投递由本人在平台完成。'}
        row['advice']=advice(row,a);row['selection']={'bucket':'unreviewed','reason':'','selected':False}
        rows.append(row)
    def tier(r):
        hard={'披露条件满足':0,'值得核实':1,'明确存在取舍':2}[r['group']]
        reviewed=0 if r['abilityStatus']=='human-reviewed' else 1
        risk=1 if r['companyResearch']['riskAssessment']=='major-risk' else 0
        if priority=='treatment':return (hard,sum(v['status'] in ('unknown','conflict') for k,v in r['dimensions'].items() if k in ('salary','weekend')),reviewed)
        if priority=='prospect':return (hard,risk,reviewed)
        return (hard,reviewed,risk)
    ordered=sorted(rows,key=lambda r:(tier(r),r['jobId']))
    for row in rows:row['systemTier']=list(tier(row))
    actual={r['companyId'] for r in rows if r['companyId'] in companies}
    return {'schemaVersion':1,'createdAt':datetime.now(timezone.utc).isoformat(),'context':c['evidence'],'contextHash':c['hash'],
        'policy':c['screen']['policy'],
        'priority':priority,'sortingBasis':{'fit':'先看已披露硬条件，再看是否完成能力人工复核，明确重大风险提示后置','treatment':'先看已披露硬条件，再看待遇条件中待确认项数量，最后看能力是否复核','prospect':'先看已披露硬条件，再提示已知重大风险；未实现成长排序，不能视为前景排名'}[priority],
        'tiePolicy':'同档不强排；内部稳定ID仅用于复现展示，不代表精确优劣','systemOrder':[r['jobId'] for r in ordered],
        'userOrder':[r['jobId'] for r in ordered],'preferenceScope':'current-report-only','jobs':rows,
        'coverage':{'targetCompanies':100,'actualCompanies':len(actual),'anonymousJobs':sum(r['companyId'] not in companies for r in rows),'jobs':len(rows),'complete':len(actual)>=100},
        'targets':{'preferred':10,'reserve':10},'reasonCounts':c['screen']['reasonCounts'],'totalScore':None,
        'limitations':['条件满足仅指配置范围内的披露，不是本人报价确认。','能力复核覆盖原文片段，不保证完整JD已被正确拆解。','公司成长未自动判断，财报未知不淘汰。','本报告含私人经历引用，不是匿名开源数据。']}

def choose(report,job_id,bucket,reason,confirmed):
    if confirmed is not True or bucket not in ('unreviewed','preferred','reserve','tradeoff','excluded'):raise ValueError('Explicit scoped choice required')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValueError('Choice reason required')
    out=copy.deepcopy(report);row=next((r for r in out['jobs'] if r['jobId']==job_id),None)
    if row is None:raise ValueError('Job outside report')
    if bucket in ('preferred','reserve'):
        if not row['companyIdentified']:raise ValueError('Company identity required')
        if row['group']=='明确存在取舍':raise ValueError('Hard mismatch cannot enter shortlist; retain tradeoff')
        if row['abilityStatus']!='human-reviewed' or not row['advice']['emphasize']:raise ValueError('Complete human ability review and confirmed positive evidence required')
        if bucket=='preferred' and row['group']!='披露条件满足':raise ValueError('Unknown hard condition stays reserve')
        for other in out['jobs']:
            if other['jobId']!=job_id and other['companyId']==row['companyId'] and other['selection']['bucket'] in ('preferred','reserve'):other['selection']={'bucket':'unreviewed','reason':'同公司本轮改选其他岗位；原选择见历史版本','selected':False}
        if sum(r['selection']['bucket']==bucket and r['jobId']!=job_id for r in out['jobs'])>=10:raise ValueError('Ten-company bucket capacity; no silent replacement')
    row['selection']={'bucket':bucket,'reason':reason,'selected':bucket in ('preferred','reserve'),'confirmedAt':datetime.now(timezone.utc).isoformat()}
    return out

def reorder(report,order):
    if not isinstance(order,list) or len(order)!=len(set(order)) or set(order)!=set(report['userOrder']):raise ValueError('Exact report job order required')
    out=copy.deepcopy(report);out['userOrder']=order;return out

def summary(report):
    counts={b:sum(r['selection']['bucket']==b for r in report['jobs']) for b in ('preferred','reserve','tradeoff','excluded','unreviewed')}
    baseline={r['companyId'] for r in report['jobs'] if r['companyIdentified'] and r['group']=='披露条件满足'}
    relaxation=[]
    for dimension in ('salary','weekend','education','city'):
        eligible=[r for r in report['jobs'] if r['dimensions'].get(dimension,{}).get('status')=='disclosed-mismatch' and all(v['status']=='disclosed-match' for k,v in r['dimensions'].items() if k!=dimension)]
        if eligible:relaxation.append({'dimension':dimension,'jobIds':[r['jobId'] for r in eligible],
            'additionalConditionEligibleCompanies':len({r['companyId'] for r in eligible if r['companyIdentified']}-baseline),
            'meaning':'仅假设不检查这一项，其他已配置条件均有披露符合；不等于能力匹配、用户愿意或应当放宽。本轮条件未改变。'})
    return {'counts':counts,'shortfall':{'preferred':10-counts['preferred'],'reserve':10-counts['reserve']},
        'relaxationOptions':relaxation,
        'exclusionReasons':[{'jobId':r['jobId'],'companyId':r['companyId'],'reason':r['selection']['reason']} for r in report['jobs'] if r['selection']['bucket']=='excluded'],
        'conditionReasonCounts':report['reasonCounts'],'meaning':'条件原因按岗位计数，不冒称公司淘汰原因；未知与明确不符分开。人工排除理由单列，不自动语义聚类。'}

def html_report(report):
    e=lambda x:escape(str(x),quote=True)
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;"><title>本地求职决策报告</title><style>body{max-width:1000px;margin:30px auto;padding:20px;font:16px/1.7 system-ui;color:#183949}article{padding:22px;border:1px solid #ccdce2;margin:20px 0}h2{font-size:24px}h3{font-size:18px}pre{white-space:pre-wrap;overflow-wrap:anywhere}.warn{background:#fff1cf;padding:12px}</style><h1>本地求职决策报告</h1><p class="warn">私人材料，分享前逐项脱敏。不是匿名报告。本文件不会触发平台操作；收藏状态见台账，沟通与投递请本人完成。岗位当前状态须重新确认。</p>']
    sums=summary(report);labels={'preferred':'人工优选','reserve':'人工候选','tradeoff':'存在取舍','excluded':'本轮不考虑','unreviewed':'尚未选定'}
    parts.append('<h2>优选 '+str(sums['counts']['preferred'])+'/10 · 候选 '+str(sums['counts']['reserve'])+'/10</h2>')
    parts.append('<p>覆盖 '+e(report['coverage']['actualCompanies'])+'/100家公司；优选与候选均由本轮人工指定，不凑数。</p><p>'+e(report['sortingBasis'])+'。'+e(report['tiePolicy'])+'</p>')
    parts.append('<h3>条件差异共性（岗位计数，未知与明确不符分开）</h3>')
    for key,count in report['reasonCounts'].items():
        dim,state=key.split(':');parts.append('<p>'+e({'salary':'薪资','weekend':'休息制度','education':'学历','city':'地点','sourceScope':'来源范围'}.get(dim,dim))+' · '+e({'unknown':'待核实','conflict':'来源冲突','disclosed-mismatch':'披露不符'}.get(state,state))+'：'+str(count)+'</p>')
    for entry in sums['exclusionReasons']:parts.append('<p>本人本轮排除理由：'+e(entry['reason'])+'</p>')
    for option in sums['relaxationOptions']:parts.append('<p>若单独不检查'+e({'salary':'薪资','weekend':'双休','education':'学历','city':'地点'}[option['dimension']])+'条件，其余配置条件披露符合的新增公司：'+str(option['additionalConditionEligibleCompanies'])+'。本轮未改变条件，不代表能力匹配。</p>')
    rows={r['jobId']:r for r in report['jobs']}
    for ident in report['userOrder']:
        r=rows[ident];parts.append('<article><h2>'+e(r['companyName'])+'</h2><h3>'+e(r['jobTitle'])+'</h3><p>规模：'+e(r['companySize']['value'])+' · '+e(r['group'])+' · '+e(labels[r['selection']['bucket']])+'</p>')
        salary=list(dict.fromkeys(ref['quote'] for ref in r['dimensions'].get('salary',{}).get('evidence',[])))
        parts.append('<p><strong>薪资披露：'+e('；'.join(salary[:2]) if salary else '本轮未配置判断或未定位原文')+'</strong>（不是针对本人的报价）</p>')
        if r['companyResearch']['riskAssessment']=='major-risk':parts.append('<p class="warn">人工重大风险提示：'+e(r['companyResearch'].get('finding',{}).get('reason','请核对原财报依据'))+'</p>')
        for task in report.get('actionObservations',[]):
            if task['jobId']==ident:parts.append('<p>收藏记录：'+e({'confirmed-favorite':'系统已收藏，页面刷新后核实','observed-favorite':'已核实平台收藏状态，仅作观察确认','executing':'执行结果待核实，禁止重复','blocked-before-click':'点击前停止','ready-to-execute':'已核对，尚未点击','authorized':'仅授权，未操作','awaiting-user-action':'历史人工接管，待观察','outcome-unknown':'结果尚未核实','cancelled':'授权撤销'}.get(task['state'],task['state']))+'；沟通和简历投递由本人完成。最后观察时间：'+e(datetime.fromtimestamp(task['observedAt'],timezone.utc).isoformat() if task.get('observedAt') else '无')+'，不是当前状态保证。</p>')
        u=urlsplit(r['sourceUrl'])
        if u.scheme=='https' and u.hostname=='www.zhipin.com' and re.fullmatch(r'/job_detail/[^/]+\.html',u.path):parts.append('<a rel="noreferrer" href="'+e(r['sourceUrl'])+'">原岗位（打开后仍须刷新核实）</a>')
        for key,label in [('emphasize','该强调的真实经历'),('verify','最需要核实的问题'),('possibleMismatch','双方可能不匹配之处')]:
            parts.append('<h3>'+label+'</h3>')
            if not r['advice'][key]:parts.append('<p>暂无证据支持的内容，不自动补写</p>')
            for item in r['advice'][key]:parts.append('<p>'+e(item.get('quote') or item.get('question') or (item.get('jobQuote','')+' '+item.get('reason','')))+'</p>')
        parts.append('<details><summary>条件、公司研究及来源</summary><pre>'+e(json.dumps({'dimensions':r['dimensions'],'companySize':r['companySize'],'companyResearch':r['companyResearch'],'capturedAt':r['capturedAt'],'selection':r['selection']},ensure_ascii=False,indent=2))+'</pre></details></article>')
    return ''.join(parts)+'</html>'
