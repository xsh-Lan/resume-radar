#!/usr/bin/env python3
"""Local source ledger and mechanical validation; no model or capability inference."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit
from pathlib import Path

DATA_FILES=('run.json','sources.json','requirements.json','evidence.json','diagnosis.json','sentence_review.json')
SUPPORT={'direct','transferable','partial','unknown','missing','conflicting'}
GAPS={'expression','evidence_missing','experience_gap','depth_gap','transfer_gap','hard_constraint','source_conflict'}
DECISIONS={'keep','rewrite','merge','compress','drop','needs_input'}

def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write_json(path,data): Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def make_source(text,ident,kind):
    units=[]; offset=0; section=''
    for line_number,line in enumerate(text.splitlines(keepends=True),1):
        raw=line.rstrip('\r\n')
        if raw.strip() and not re.fullmatch(r'\s*(?:[-*_]\s*){3,}',raw):
            plain_heading=re.match(r'^(教育经历|教育背景|实习经历|工作经历|项目经历|个人其他信息|其他信息|荣誉与证书|技能清单)(?:\s*$|[（(])',raw.strip())
            is_heading=raw.lstrip().startswith('#') or bool(plain_heading)
            if is_heading: section=plain_heading.group(1) if plain_heading else raw.lstrip('# ').strip()
            for m in re.finditer(r'.+?(?:[。！？]+|[.!?]+(?=\s+[A-Z]|\s*$)|$)',raw):
                quote=m.group(0)
                if not quote.strip(): continue
                start=offset+m.start()
                units.append({'id':f'{ident}-U{len(units)+1:03d}','source_id':ident,'line':line_number,
                              'start':start,'end':start+len(quote),'text':quote,'section':section,
                              'kind':'heading' if is_heading else 'content'})
        offset+=len(line)
    return {'id':ident,'kind':kind,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'units':units}

def read_text(path):
    p=Path(path)
    if p.suffix.lower() not in {'.md','.txt'}: raise ValueError('Extract and inspect PDF/DOCX first; input must be UTF-8 .md/.txt')
    text=p.read_text(encoding='utf-8-sig')
    if not text.strip(): raise ValueError('Empty input')
    return text

def initialize(args):
    dest=Path(args.run_dir).resolve()
    if dest.exists(): raise ValueError('Run directory exists; use a new candidate/source version directory')
    sources=[make_source(read_text(args.resume),'RESUME','resume')]
    if args.jd: sources.append(make_source(read_text(args.jd),'JD','jd'))
    run={'schema_version':'2.1','candidate_key':args.candidate_key,
         'mode':'jd' if args.jd else ('direction' if args.target else 'explore'),
         'target':args.target or '','target_status':'user_specified' if args.target else 'unresolved',
         'stage':args.stage or 'unknown','status':'draft','assumptions':[],'role_options':[],
         'summary':'','actions':[],'final_text':'','display_mode':'focused',
         'market_search':{'status':'not_needed' if args.jd else 'pending','limitations':'','attempts':[]},
         'review':{'status':'pending','findings':[]}}
    dest.mkdir(parents=True)
    write_json(dest/'run.json',run); write_json(dest/'sources.json',{'sources':sources})
    for f in DATA_FILES[2:]: write_json(dest/f,[])
    return {'run_dir':str(dest),'mode':run['mode'],'resume_units':len(sources[0]['units']),
            'status':'draft','note':'Sources only; model analysis and review still required.'}

def add_source(args):
    root=Path(args.run_dir); data=read_json(root/'sources.json'); sources=data['sources']
    ident=args.kind.upper()+str(1+sum(s['kind']==args.kind for s in sources))
    sources.append(make_source(read_text(args.file),ident,args.kind))
    write_json(root/'sources.json',data)
    run=read_json(root/'run.json'); run['status']='draft'; run['review']={'status':'pending','findings':[]}
    write_json(root/'run.json',run)
    return {'source_id':ident,'units':len(sources[-1]['units']),'status':'draft','note':'Update affected evidence and repeat focused review.'}

def valid_url(value):
    if not isinstance(value,str): return False
    try:
        parsed=urlsplit(value)
        return parsed.scheme in {'http','https'} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError: return False

def valid_date(value):
    try: datetime.fromisoformat(value); return True
    except (ValueError,TypeError): return False

def add_jd(args):
    """Import inspected public JD text; fetching is performed by the host's browsing tools."""
    if not valid_url(args.url): raise ValueError('Public HTTP(S) source URL required')
    if not valid_date(args.retrieved_at): raise ValueError('retrieved-at must be an ISO date/time')
    root=Path(args.run_dir); data=read_json(root/'sources.json')
    if any(s.get('metadata',{}).get('url')==args.url for s in data['sources']):
        raise ValueError('Duplicate JD URL; reuse its source ID')
    ident='JOB'+str(1+sum(s['kind']=='jd_sample' for s in data['sources']))
    source=make_source(read_text(args.file),ident,'jd_sample')
    source['metadata']={k:getattr(args,k) for k in ('url','role','title','company','location','level','published_at','retrieved_at','availability')}
    data['sources'].append(source)
    write_json(root/'sources.json',data)
    run=read_json(root/'run.json'); run['status']='draft'; run['review']={'status':'pending','findings':[]}
    write_json(root/'run.json',run)
    return {'source_id':ident,'units':len(source['units']),'status':'draft','note':'Map requirements to exact JD units; update search coverage and repeat review.'}

def numeric_tokens(text):
    return set(re.findall(r'(?<![A-Za-z])\d+(?:\.\d+)?(?:%|％|\+)?',unicodedata.normalize('NFKC',text)))

def validate_run(directory):
    root=Path(directory); errors=[]; warnings=[]
    def fail(code,detail): errors.append({'code':code,'detail':detail})
    try: data={f:read_json(root/f) for f in DATA_FILES}
    except (OSError,ValueError) as exc: return {'ok':False,'errors':[{'code':'load','detail':str(exc)}],'warnings':[],'counts':{}}
    run=data['run.json']
    if not isinstance(run,dict) or not isinstance(data['sources.json'],dict):
        return {'ok':False,'errors':[{'code':'schema','detail':'run/sources must be objects'}],'warnings':[],'counts':{}}
    def indexed(values,name):
        out={}
        if not isinstance(values,list) or any(not isinstance(v,dict) for v in values):
            fail('schema',name+': expected list of objects'); return out
        for v in values:
            i=v.get('id')
            if not isinstance(i,str) or not i or i in out: fail('id',f'{name}: missing/duplicate id {i!r}')
            else: out[i]=v
        return out
    def refs(value,mapping,name):
        if not isinstance(value,list) or any(not isinstance(v,str) or v not in mapping for v in value):
            fail('reference',name); return []
        return value
    def fields(item,names,label):
        for k in names:
            if not isinstance(item.get(k),str) or not item[k].strip(): fail('required',f'{label}.{k}')
    sources=indexed(data['sources.json'].get('sources'),'sources'); units={}; resume_units={}
    for sid,s in sources.items():
        text=s.get('text','')
        if not isinstance(text,str): fail('source',sid); continue
        if hashlib.sha256(text.encode()).hexdigest()!=s.get('sha256'): fail('source_hash',sid)
        if s.get('kind') not in {'resume','jd','jd_sample','followup','artifact'}: fail('source_kind',sid)
        if s.get('kind')=='jd_sample':
            meta=s.get('metadata',{})
            if not isinstance(meta,dict): fail('job_metadata',sid); meta={}
            fields(meta,['url','role','title','company','location','level','published_at','retrieved_at','availability'],sid+': metadata')
            if not valid_url(meta.get('url')): fail('job_url',sid)
            if not valid_date(meta.get('retrieved_at')): fail('job_date',sid)
            if meta.get('availability') not in {'open','closed','unknown'}: fail('job_availability',sid)
        expected=make_source(text,sid,s.get('kind'))['units']
        if s.get('units')!=expected: fail('source_units',sid+': units must match lossless extraction')
        for u in expected:
            if u['id'] in units: fail('id','duplicate unit '+u['id'])
            units[u['id']]=u
            if s.get('kind')=='resume': resume_units[u['id']]=u
    if not resume_units: fail('source','No resume units')
    mode=run.get('mode')
    if mode not in {'jd','direction','explore'}: fail('mode',str(mode))
    if mode=='jd' and not any(s.get('kind')=='jd' for s in sources.values()): fail('mode','JD source required')
    if mode=='direction' and not run.get('target'): fail('mode','Direction target required')
    if run.get('target_status') not in {'user_specified','user_selected','provisional','unresolved'}: fail('target','Invalid status')
    if run.get('target_status')=='provisional' and not run.get('assumptions'): fail('target','Provisional target requires assumptions')
    if not run.get('candidate_key'): fail('candidate','Candidate key required')
    fields(run,['summary'],'run')
    if run.get('status')!='reviewed': fail('status','Set reviewed only after analysis and focused review')
    if not isinstance(run.get('assumptions'),list) or any(not isinstance(a,str) for a in run.get('assumptions',[])): fail('schema','assumptions must be strings')
    if run.get('display_mode','focused') not in {'focused','full'}: fail('display_mode','focused/full required')
    search=run.get('market_search')
    if run.get('schema_version')=='2.1' or search is not None:
        if not isinstance(search,dict): fail('market_search','Search ledger required'); search={}
        state=search.get('status')
        if state not in {'complete','partial','failed','not_needed'}: fail('market_search','Search must be completed or explicitly limited')
        if mode!='jd' and state=='not_needed' and not search.get('limitations'): fail('market_search','Explain user opt-out or why search is unnecessary')
        if state in {'partial','failed'} and not search.get('limitations'): fail('market_search','Disclose shortfalls or failure')
        attempts=search.get('attempts')
        if not isinstance(attempts,list) or any(not isinstance(a,dict) for a in attempts):
            fail('market_search','attempts must be objects'); attempts=[]
        for a in attempts:
            fields(a,['role','query','searched_at','outcome'],'search attempt')
            if not valid_date(a.get('searched_at')): fail('market_search','Invalid search date')
        if state in {'complete','partial','failed'} and not attempts: fail('market_search','Actual search attempts required')
        jobs=[s for s in sources.values() if s.get('kind')=='jd_sample']
        if state in {'complete','partial'} and not jobs: fail('market_search','Retrieved JD sources required')
        urls=[s.get('metadata',{}).get('url') for s in jobs if isinstance(s.get('metadata',{}),dict)]
        if len(urls)!=len(set(urls)): fail('job_duplicate','Reuse duplicate JD sources')
    actions=run.get('actions',[])
    if not isinstance(actions,list) or any(not isinstance(a,dict) for a in actions):
        fail('schema','actions must be objects'); actions=[]
    for a in actions:
        if a.get('type') not in {'edit','evidence','practice','decision'}: fail('action','Invalid action type')
        fields(a,['text'],'action')
    review=run.get('review',{})
    if not isinstance(review,dict) or review.get('status')!='completed' or not isinstance(review.get('findings'),list) or any(not isinstance(x,str) for x in review.get('findings',[])): fail('review','Focused review not completed')
    evidence=indexed(data['evidence.json'],'evidence'); requirements=indexed(data['requirements.json'],'requirements')
    diagnoses=indexed(data['diagnosis.json'],'diagnosis'); reviews=indexed(data['sentence_review.json'],'sentence_review')
    if 'report_overview' in run:
        overview=run['report_overview']
        if not isinstance(overview,dict):
            fail('overview','report_overview must be an object')
        else:
            fields(overview,['headline','introduction','evidence_summary','gap_summary'],'report_overview')
            if 'assessment' in overview:
                fields(overview,['fit_scope','eligibility'],'overview fit')
                assessment=overview['assessment']
                if not isinstance(assessment,list) or not assessment or any(not isinstance(item,dict) for item in assessment):
                    fail('overview','assessment must be a nonempty list of objects')
                else:
                    for item in assessment:
                        fields(item,['dimension','judgment'],'overview assessment')
                        if item.get('status') not in {'met','partial','unknown','unmet'}:fail('overview','Invalid assessment status')
                        if not refs(item.get('requirement_ids'),requirements,'assessment requirements'):fail('overview','Assessment requires job requirements')
                        if not refs(item.get('evidence_ids'),evidence,'assessment evidence'):fail('overview','Assessment requires candidate evidence')
            priorities=overview.get('priorities')
            if not isinstance(priorities,list) or any(not isinstance(item,dict) for item in priorities):
                fail('overview','priorities must be a list of objects')
            else:
                for item in priorities:
                    fields(item,['title','text'],'overview priority')
                    if not refs(item.get('diagnosis_ids'),diagnoses,'overview priority diagnoses'):
                        fail('overview','Each priority must reference an existing diagnosis')
    for ident,e in evidence.items():
        uid=e.get('unit_id'); sid=e.get('source_id'); quote=e.get('quote')
        if uid not in units or not isinstance(quote,str) or not quote or quote not in units[uid]['text']: fail('quote',ident)
        if sid not in sources or (uid in units and sid!=units[uid]['source_id']): fail('reference',ident+': source')
        if sources.get(sid,{}).get('kind') in {'jd','jd_sample'}: fail('candidate_evidence',ident+': recruiting requirements are not candidate facts')
        if e.get('status') not in {'self_reported','user_confirmed','artifact_supported','unclear','conflicting'}: fail('evidence_status',ident)
        required_kind={'user_confirmed':'followup','artifact_supported':'artifact'}.get(e.get('status'))
        if required_kind and sources.get(sid,{}).get('kind')!=required_kind: fail('evidence_status',ident+': requires '+required_kind)
        if e.get('actor') not in {'individual','team','shared','unknown'}: fail('actor',ident)
        if e.get('completion') not in {'actual','expected','in_progress','unknown'}: fail('completion',ident)
        fields(e,['action'],ident)
    if not evidence: fail('evidence','Sourced evidence required')
    if not requirements: fail('requirements','At least one justified requirement required')
    for ident,r in requirements.items():
        fields(r,['role','description','task','responsibility','decision_depth'],ident)
        basis=r.get('basis'); ids=refs(r.get('source_unit_ids',[]),units,ident+': source units')
        if basis not in {'jd','sample_jd','role_standard','hypothesis'}: fail('basis',ident)
        if mode!='jd' and basis=='jd': fail('basis',ident+': no JD in this mode')
        if basis=='jd' and (not ids or any(sources[units[u]['source_id']]['kind']!='jd' for u in ids)): fail('basis',ident+': JD quotes required')
        if basis=='sample_jd' and (not ids or any(sources[units[u]['source_id']]['kind']!='jd_sample' for u in ids)): fail('basis',ident+': retrieved JD quotes required')
        if basis=='sample_jd' and any(sources[units[u]['source_id']].get('metadata',{}).get('role')!=r.get('role') for u in ids): fail('job_role',ident+': sample must belong to this role')
        if basis!='jd' and not r.get('basis_note'): fail('basis',ident+': standard/hypothesis needs rationale and limits')
        if r.get('importance') not in {'core','supporting','bonus','hard'}: fail('importance',ident)
        if r.get('importance')=='hard' and basis not in {'jd','sample_jd'}: fail('hard_requirement',ident)
        if r.get('support') not in SUPPORT: fail('support',ident)
        eids=refs(r.get('evidence_ids',[]),evidence,ident+': evidence')
        if r.get('support') in {'direct','transferable','partial'} and not eids: fail('support',ident+': positive support needs evidence')
        if r.get('support')=='missing' and not any(ident in d.get('requirement_ids',[]) and d.get('gap_type') in {'experience_gap','depth_gap','hard_constraint'} for d in diagnoses.values()): fail('missing_support',ident)
    issue_keys=set()
    for ident,d in diagnoses.items():
        key=d.get('issue_key')
        if run.get('schema_version')=='2.1' and (not isinstance(key,str) or not key.strip()): fail('issue_key',ident)
        if key:
            if key in issue_keys: fail('duplicate_diagnosis',ident+': reuse existing diagnosis ID')
            issue_keys.add(key)
        if d.get('priority','medium') not in {'high','medium','low'}: fail('priority',ident)
        if d.get('scope') not in {'role','document','fact'}: fail('scope',ident)
        if d.get('gap_type') not in GAPS: fail('gap_type',ident)
        rids=refs(d.get('requirement_ids',[]),requirements,ident+': requirements')
        eids=refs(d.get('evidence_ids',[]),evidence,ident+': evidence')
        fields(d,['demonstrates','does_not_demonstrate','impact','next_action'],ident)
        if not eids: fail('diagnosis',ident+': actual evidence required')
        if d.get('scope')=='role' and not rids: fail('diagnosis',ident+': role gap needs requirement')
        if d.get('gap_type') in {'experience_gap','depth_gap'}:
            cids=refs(d.get('confirmation_evidence_ids',[]),evidence,ident+': confirmations')
            if d.get('confirmed_by_user') is not True or not cids or any(evidence[i].get('status')!='user_confirmed' for i in cids): fail('unconfirmed_gap',ident)
        if d.get('gap_type')=='hard_constraint' and (not rids or any(requirements[i].get('importance')!='hard' or requirements[i].get('basis') not in {'jd','sample_jd'} for i in rids)): fail('hard_constraint',ident)
    options=run.get('role_options',[])
    if not isinstance(options,list) or any(not isinstance(o,dict) for o in options): fail('roles','Expected role options list'); options=[]
    if mode=='explore' and not options: fail('roles','Supported role options required')
    for o in options:
        fields(o,['role','rationale','unknowns'],'role_option')
        if not refs(o.get('evidence_ids',[]),evidence,'role_option evidence'): fail('roles','Actual evidence required')
        if run.get('schema_version')=='2.1':
            fields(o,['transfer_difficulty','next_action'],'role_option')
            sids=refs(o.get('jd_source_ids',[]),sources,'role_option JD sources')
            if any(sources[i].get('kind')!='jd_sample' or sources[i].get('metadata',{}).get('role')!=o.get('role') for i in sids): fail('job_role','Role option JD references')
            if not sids and not o.get('search_limitation'): fail('roles','Disclose missing JD coverage for '+o.get('role',''))
            if 'recommended_jd_source_ids' in o:
                picked=refs(o['recommended_jd_source_ids'],sources,'recommended JD sources')
                if any(i not in sids or sources[i].get('metadata',{}).get('availability')=='closed' for i in picked): fail('job_recommendation','Recommendations must use this role’s non-closed JD references')
    if isinstance(search,dict) and search.get('status')=='complete':
        expected_roles={o.get('role') for o in options} if mode=='explore' else {run.get('target')} if mode=='direction' else set()
        found_roles={s.get('metadata',{}).get('role') for s in sources.values() if s.get('kind')=='jd_sample' and isinstance(s.get('metadata'),dict)}
        if expected_roles-found_roles: fail('market_search','Complete search lacks samples for '+str(sorted(expected_roles-found_roles)))
    for a in actions: refs(a.get('diagnosis_ids',[]),diagnoses,'action diagnoses')
    def check_rewrite(text,eids,label):
        if not isinstance(text,str): fail('rewrite',label); return
        quotes='\n'.join(evidence[i].get('quote','') for i in eids)
        extra=numeric_tokens(text)-numeric_tokens(quotes)
        if extra: fail('new_numbers',label+': '+str(sorted(extra)))
        for term in ('主导','独立负责','独立完成','全权','领导'):
            if term in text and term not in quotes: fail('ownership_upgrade',label+': '+term)
        if eids and all(evidence[i].get('completion') in {'expected','in_progress','unknown'} for i in eids):
            if re.search('已上线|实现|提升|完成',text) and not re.search('未|待|预计|计划|原型|评审|进行中|拟',text): fail('completion_upgrade',label)
    covered=set(); pending=set()
    for ident,v in reviews.items():
        uids=refs(v.get('unit_ids',[]),resume_units,ident+': units')
        if not uids: fail('coverage',ident+': resume units required')
        if covered.intersection(uids): fail('coverage',ident+': duplicate review, use merge')
        covered.update(uids); decision=v.get('decision')
        if decision not in DECISIONS: fail('decision',ident)
        if decision=='needs_input':
            pending.update(uids)
            if not v.get('question'): fail('question',ident)
        fields(v,['reason','capability','role_relevance'],ident)
        refs(v.get('diagnosis_ids',[]),diagnoses,ident+': diagnoses')
        eids=refs(v.get('evidence_ids',[]),evidence,ident+': evidence')
        if decision in {'rewrite','merge','compress'} or (decision=='needs_input' and v.get('text')):
            if not eids or not v.get('text'): fail('rewrite',ident+': replacement/evidence required')
            check_rewrite(v.get('text',''),eids,ident)
        if decision=='keep' and v.get('text') and v['text']!='\n'.join(resume_units[u]['text'] for u in uids): fail('keep_changed',ident)
        if decision=='drop' and v.get('text'): fail('drop_text',ident+': drop is a recommendation, not replacement text')
    if set(resume_units)-covered: fail('coverage','Unreviewed: '+str(sorted(set(resume_units)-covered)))
    if run.get('final_text'):
        if run.get('target_status')=='unresolved': fail('target','Final version requires selected or disclosed provisional target')
        check_rewrite(run['final_text'],list(evidence),'final_text')
    if pending: warnings.append({'code':'needs_input','detail':f'{len(pending)}个单元待补事实；完成审阅不等于这些事实已确认。'})
    if mode!='jd': warnings.append({'code':'no_jd','detail':'这是方向级分析，不代表具体公司的匹配分或录用概率。'})
    return {'ok':not errors,'errors':errors,'warnings':warnings,
            'counts':{'resume_units':len(resume_units),'reviewed':len(covered),'awaiting_input':len(pending),'requirements':len(requirements),'diagnoses':len(diagnoses)},
            'boundary':'Mechanical source/coverage checks only; semantic judgments and external truth are not certified.'}

def snapshot(directory):
    root=Path(directory); versions=root/'versions'; versions.mkdir(exist_ok=True); n=1
    while (versions/f'{n:04d}').exists(): n+=1
    out=versions/f'{n:04d}'; out.mkdir()
    for name in DATA_FILES: shutil.copy2(root/name,out/name)
    return {'snapshot':str(out)}

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init'); init.add_argument('--resume',required=True); init.add_argument('--jd'); init.add_argument('--target'); init.add_argument('--stage'); init.add_argument('--candidate-key',required=True); init.add_argument('--run-dir',required=True)
    add=sub.add_parser('add-source'); add.add_argument('--run-dir',required=True); add.add_argument('--kind',choices=['followup','artifact'],required=True); add.add_argument('--file',required=True)
    job=sub.add_parser('add-jd',help='Import inspected public JD text and provenance; does not fetch the web')
    for name in ('run-dir','file','url','role','title','company','retrieved-at'): job.add_argument('--'+name,required=True)
    for name in ('location','level','published-at'): job.add_argument('--'+name,default='unknown')
    job.add_argument('--availability',choices=['open','closed','unknown'],default='unknown')
    for cmd in ('validate','snapshot'): sub.add_parser(cmd).add_argument('--run-dir',required=True)
    args=p.parse_args()
    try:
        result=initialize(args) if args.command=='init' else add_source(args) if args.command=='add-source' else add_jd(args) if args.command=='add-jd' else snapshot(args.run_dir) if args.command=='snapshot' else validate_run(args.run_dir)
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result.get('ok',True) else 1
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False),file=sys.stderr); return 1

if __name__=='__main__': raise SystemExit(main())
