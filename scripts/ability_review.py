"""Evidence retrieval and explicit human ability review. No model or total score."""
import hashlib
import json
from pathlib import Path
import re
from candidate_facts import extract_facts
from resume_workspace import digest

TERMS=['投放','预算','复盘','数据分析','数据整理','自动化','工作流','培训','团队管理','客户','电商','服装','供应链','商品','直播','短视频','选品','增长','项目管理','用户运营','测试','销售','财务','设计']
SPECIAL=['RAG','Python','SQL','ComfyUI','机器学习','算法','全栈','深度学习']

def hash_json(d):return digest(json.dumps(d,sort_keys=True,ensure_ascii=False).encode())

def load_facts(folder):
    folder=Path(folder);manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    resume=json.loads((folder/'resume.json').read_text(encoding='utf-8'));data=json.loads((folder/'facts.json').read_text(encoding='utf-8'))
    if digest((folder/'source.bin').read_bytes())!=manifest['sourceSha256'] or hash_json(resume)!=manifest['resumeHash']:raise ValueError('Candidate source changed')
    expected=extract_facts(resume,(folder/'fact-id-salt').read_bytes(),manifest['resumeHash'])
    if len(data['facts'])!=len(expected):raise ValueError('Fact set changed')
    for f,e in zip(data['facts'],expected):
        if any(f.get(k)!=e[k] for k in ('id','quote','path','sourceHash')) or f.get('status') not in ('candidate-confirmed','candidate-unconfirmed'):raise ValueError('Candidate evidence changed')
    return data['facts']

def terms(text):
    return {t.lower() for t in TERMS if t in text}|{t.lower() for t in re.findall(r'[A-Za-z][A-Za-z0-9+#.]{1,}',text)}

def directions(facts):
    result=[]
    for label,keys in [('电商投放/增长运营',{'投放','预算'}),('运营分析/数据运营',{'数据分析','复盘','数据整理'}),('业务AI应用/运营提效',{'ai','自动化','工作流'}),('商品/供应链运营',{'供应链','商品','选品'}),('客户成功/业务实施顾问',{'客户','培训','项目管理'})]:
        refs=[f['id'] for f in facts if f['status']=='candidate-confirmed' and terms(f['quote'])&keys]
        if refs:result.append({'id':'direction_'+digest(label.encode())[:16],'label':label,'factIds':refs[:5],'status':'hypothesis','explanation':'仅从已确认任务检索的探索假设，未验证市场需求或本人意愿，不推定具备全部岗位技能。'})
    return result

def generate(job,facts):
    source=job['source'];text=source['text'];start=text.find('职位描述')
    if start<0:raise ValueError('Missing job description scope')
    start+=len('职位描述');end=min([p for marker in ('竞争力分析','BOSS 安全提示','更多职位','看过该职位的人还看了') if (p:=text.find(marker,start))>=0] or [len(text)])
    requirements=[]
    for m in re.finditer(r'[^\n]+',text[start:end]):
        quote=m.group().strip()
        if len(quote)<8:continue
        a=start+m.start()+len(m.group())-len(m.group().lstrip());b=a+len(quote)
        ident='req_'+hashlib.sha256((job['id']+str(a)+quote).encode()).hexdigest()[:20]
        related=[]
        for f in facts:
            shared=sorted(terms(quote)&terms(f['quote']))
            if shared:related.append({'factId':f['id'],'sharedTerms':shared,'status':f['status']})
        guards=[t for t in SPECIAL if t.lower() in quote.lower()]
        guards+=re.findall(r'\d+\s*年(?:以上)?',quote)
        requirements.append({'id':ident,'quote':quote,'start':a,'end':b,'sourceHash':digest(text.encode()),'sourceUrl':source.get('url'),
            'capturedAt':source.get('capturedAt'),'sourceOrder':len(requirements)+1,'retrievalOnly':related[:8],
            'proofTerms':guards,'decision':'unreviewed','selectedFactIds':[],'rationale':''})
        if len(requirements)>=60:break
    if not requirements:raise ValueError('No scoped requirement text')
    identity={'jobId':job['id'],'jobSourceHash':digest(text.encode()),'candidateFactsHash':hash_json(facts)}
    return {'schemaVersion':1,'context':identity,'contextHash':hash_json(identity),'facts':facts,'requirements':requirements,
        'reviewStatus':'draft','semanticVerification':'not-automated','totalScore':None,'directionHypotheses':directions(facts),'directionFeedback':{},
        'warnings':['原文按行切分可能是断行或标签，不保证完整要求；原文顺序不是重要性排序。','sharedTerms只用于检索，不证明能力；未检索到也不证明候选人不会。','需要逐项人工判断；本人确认不等于第三方核验。','最多保留60段，覆盖范围需人工核对，不把草稿当完整JD深评。']}

def review(draft,items,context_hash,reviewer_confirmed):
    if reviewer_confirmed is not True or context_hash!=draft['contextHash']:raise ValueError('Explicit review and matching context required')
    if not isinstance(items,list) or not items:raise ValueError('Review items required')
    known={r['id']:r for r in draft['requirements']};facts={f['id']:f for f in draft['facts']};seen=set();decisions={}
    for item in items:
        ident=item['requirementId'];decision=item['decision'];chosen=item.get('factIds',[]);reason=item.get('rationale','')
        if ident not in known or ident in seen or decision not in ('supported','partial','unknown','evidence-gap'):raise ValueError('Invalid decision identity')
        seen.add(ident)
        if not isinstance(reason,str) or not reason.strip() or len(reason)>3000 or not isinstance(chosen,list) or len(chosen)!=len(set(chosen)) or any(f not in facts for f in chosen):raise ValueError('Reason and scoped facts required')
        if decision in ('supported','partial') and (not chosen or any(facts[f]['status']!='candidate-confirmed' for f in chosen)):raise ValueError('Use explicitly confirmed facts for positive judgment')
        quoted='\n'.join(facts[f]['quote'] for f in chosen)
        missing=[t for t in known[ident]['proofTerms'] if t.lower() not in quoted.lower()]
        if decision=='supported' and missing:raise ValueError('Specialist or duration claim lacks direct evidence; use partial/unknown and explain')
        decisions[ident]={'decision':decision,'selectedFactIds':chosen,'rationale':reason,'uncoveredProofTerms':missing}
    result=json.loads(json.dumps(draft));result['previousReviewStatus']=draft['reviewStatus']
    for r in result['requirements']:
        if r['id'] in decisions:r.update(decisions[r['id']])
    result['reviewStatus']='human-reviewed' if all(r['decision']!='unreviewed' for r in result['requirements']) else 'partially-reviewed'
    result['meaning']='人工对照判断，不是模型或第三方验证；缺少证据不等于没有能力。'
    return result

def feedback(draft,choices):
    if not isinstance(choices,dict) or not choices:raise ValueError('Explicit choices required')
    known={d['id'] for d in draft['directionHypotheses']}
    if any(k not in known or v not in ('want','not-want','unsure') for k,v in choices.items()):raise ValueError('Unknown direction or preference')
    result=json.loads(json.dumps(draft));result['directionFeedback'].update(choices);result['feedbackScope']='current-report-only-not-long-term-profile'
    return result
