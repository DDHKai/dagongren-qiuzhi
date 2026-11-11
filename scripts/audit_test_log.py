"""Audit synthetic desktop logs offline; never executes content or uploads data."""
import argparse
import json
import math
from pathlib import Path

IDS=['S01','S02','S03','S04','S05','S06']
# Fixed fixture for 0.1.1-experiment only: fixed pay, rest, fit, growth evidence.
FIXTURE=[(20,'double',3,1),(None,'unknown',3,2),(16,'double',3,1),
         (22,'single',2,1),(23,'double',0,1),(19,'double',2,0)]
LABELS=['披露条件满足','值得核实','明确存在取舍']
TYPES={'app_started','conditions_applied','selection_changed','manual_rank_changed',
       'dismissed','round_reset','validation_rejected','runtime_error',
       'unhandled_rejection','log_export_requested'}

def number(x):
    return type(x) in (int,float) and math.isfinite(x)

def valid_conditions(c):
    return isinstance(c,dict) and set(c)=={'salary','weekend','sort'} and number(c['salary']) and 0<=c['salary']<=200 and c['weekend'] in ('required','preferred','ignore') and c['sort'] in ('fit','pay','growth')

def state(c,selected,hidden,manual):
    groups=[[] for _ in LABELS]
    for ident,(pay,rest,fit,growth) in zip(IDS,FIXTURE):
        if ident in hidden:continue
        bad=(pay is not None and pay<c['salary']) or not fit or (c['weekend']=='required' and rest=='single')
        unknown=pay is None or (c['weekend']=='required' and rest=='unknown')
        groups[2 if bad else 1 if unknown else 0].append(ident)
    def key(ident):
        pay,rest,fit,growth=FIXTURE[IDS.index(ident)]
        pay=pay if pay is not None else -1
        base={'fit':(-fit,-pay),'pay':(-pay,-fit),'growth':(-growth,-fit)}[c['sort']]
        return (0,manual.index(ident)) if ident in manual else (1,*base)
    return {'conditions':dict(c),'selected':sorted(selected),'dismissed':sorted(hidden),
        'manualOrder':list(manual),'groups':[{'label':label,'ids':sorted(items,key=key)} for label,items in zip(LABELS,groups)]}

def audit(data):
    errors=[];missing=[];coverage=[]
    def result():
        return {'auditVersion':1,'verdict':'异常' if errors else '证据不足' if missing else '通过',
            'scope':'仅核验已知版本合成日志的一致性，不认证实机、下载完成、T01–T10全覆盖或人工体验',
            'errors':errors,'insufficientEvidence':missing,'observedEventTypes':sorted(set(coverage))}
    if not isinstance(data,dict):errors.append('root_not_object');return result()
    if data.get('syntheticOnly') is not True:errors.append('not_declared_synthetic');return result()
    if data.get('capabilities')!={'liveCollection':False,'externalActions':False,'automaticAIReview':False}:
        errors.append('unexpected_capabilities');return result()
    if data.get('schemaVersion')!=2 or data.get('appVersion')!='0.1.1-experiment':
        missing.append('unsupported_schema_or_version_no_replay');return result()
    events=data.get('events')
    if not isinstance(events,list) or not events or len(events)>10000:
        errors.append('invalid_event_list');return result()
    c={'salary':18,'weekend':'required','sort':'fit'};selected=set();hidden=set();manual=[];last=-1
    for i,e in enumerate(events):
        prefix='event_'+str(i+1)+':'
        if not isinstance(e,dict):errors.append(prefix+'not_object');break
        t=e.get('type');ident=e.get('sampleId');elapsed=e.get('elapsedMs')
        if type(e.get('sequence')) is not int or e['sequence']!=i+1:errors.append(prefix+'sequence')
        if not number(elapsed) or elapsed<last:errors.append(prefix+'elapsed');break
        last=elapsed
        if not isinstance(t,str) or t not in TYPES:errors.append(prefix+'unknown_type');break
        coverage.append(t)
        if (i==0 and t!='app_started') or (i>0 and t=='app_started'):errors.append(prefix+'startup_position')
        s=e.get('state')
        if not isinstance(s,dict) or not valid_conditions(s.get('conditions')):errors.append(prefix+'invalid_state');break
        if t=='conditions_applied':c=s['conditions'];manual=[]
        elif t in ('selection_changed','manual_rank_changed','dismissed'):
            if ident not in IDS or ident in hidden:errors.append(prefix+'invalid_target');break
            if t=='selection_changed':selected.symmetric_difference_update({ident})
            elif t=='manual_rank_changed':manual=[ident]+[x for x in manual if x!=ident]
            else:hidden.add(ident)
        elif t=='round_reset':selected.clear();hidden.clear();manual=[]
        elif t=='validation_rejected':
            detail=e.get('detail')
            if not isinstance(detail,dict) or detail.get('field')!='salary' or detail.get('reason') not in ('empty','out_of_range'):
                errors.append(prefix+'invalid_rejection')
        elif t in ('runtime_error','unhandled_rejection'):errors.append(prefix+'runtime_failure')
        if s!=state(c,selected,hidden,manual):errors.append(prefix+'state_mismatch')
    if data.get('finalState')!=state(c,selected,hidden,manual):errors.append('final_state_mismatch')
    counts=data.get('counts')
    if not isinstance(counts,dict) or any(type(counts.get(k)) is not int for k in ('selected','dismissed')) or counts!={'selected':len(selected),'dismissed':len(hidden)}:errors.append('counts_mismatch')
    if not isinstance(events[-1],dict) or events[-1].get('type')!='log_export_requested':missing.append('no_final_export_request')
    if data.get('downloadStatus')!='requested-not-confirmed':errors.append('unsupported_download_claim')
    return result()

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        if a.input.stat().st_size>10_000_000:raise ValueError()
        report=audit(json.loads(a.input.read_text(encoding='utf-8-sig')))
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        report={'auditVersion':1,'verdict':'异常','errors':['unreadable_or_malformed_log']}
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if a.output:
        if a.output.resolve()==a.input.resolve():p.error('Output must not overwrite input')
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text+'\n',encoding='utf-8')
    print(text)
    return {'通过':0,'异常':1,'证据不足':2}[report['verdict']]

if __name__=='__main__':raise SystemExit(main())
