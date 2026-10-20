#!/usr/bin/env python3
"""Render a standalone resume diagnosis. Only the overall judgment starts visible."""
import argparse
import html
import json
import re
from pathlib import Path
from workflow import read_json, validate_run

LABELS = {
    'jd': '具体 JD 分析', 'direction': '岗位方向分析', 'explore': '基于简历的方向分析',
    'keep': '保留', 'rewrite': '建议改写', 'merge': '建议合并', 'compress': '建议压缩',
    'drop': '建议删除', 'needs_input': '需要补充事实',
    'direct': '有直接材料支持', 'transferable': '有可迁移的经历', 'partial': '已有部分依据',
    'unknown': '现有材料不足以判断', 'missing': '已有依据确认缺口', 'conflicting': '材料有待核对',
    'expression': '表达与组织问题', 'evidence_missing': '关键信息尚未呈现',
    'experience_gap': '已确认的经历缺口', 'depth_gap': '已确认的责任范围差距',
    'transfer_gap': '场景迁移仍需说明', 'hard_constraint': '明确条件不符', 'source_conflict': '材料之间存在矛盾',
    'jd_basis': 'JD 明示要求', 'role_standard': '方向级参考标准', 'hypothesis': '本次分析的暂定假设',
    'self_reported': '简历中的自述', 'user_confirmed': '用户补充说明', 'artifact_supported': '所附材料支持',
    'unclear': '尚待澄清',
    'sample_jd': '检索 JD 样本要求',
}


def esc(value):
    return html.escape(str(value), quote=True)


def label(value):
    return LABELS.get(value, value)


def p(value, cls=''):
    return '<p' + (' class="' + cls + '"' if cls else '') + '>' + esc(value).replace('\n', '<br>') + '</p>'


def prose(value):
    return ''.join(p(v) for v in re.split(r'\n\s*\n', str(value)) if v.strip())


def subnumber(value):
    digits='零一二三四五六七八九'
    if value < 10: return '（'+digits[value]+'）'
    if value < 100:
        return '（'+(digits[value//10] if value>=20 else '')+'十'+(digits[value%10] if value%10 else '')+'）'
    return '（'+str(value)+'）'


def text_points(value):
    return numbered_points([v.strip() for v in re.split(r'(?<=[。！？])\s*|\n+',str(value)) if v.strip()])


def numbered_points(values):
    return '<ol class="review-points">' + ''.join('<li>' + prose(v) + '</li>' for v in values if v) + '</ol>'


def field(title, value, kind=''):
    return '<div class="field' + (' field-' + kind if kind else '') + '"><h4>' + esc(title) + '</h4>' + text_points(value) + '</div>'


def icon(name):
    paths = {
        'check': 'm5 12 4 4L19 6',
        'search': 'M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm5-2 6 6',
        'arrow': 'M4 12h16m-6-6 6 6-6 6',
        'chevron': 'm6 9 6 6 6-6',
    }
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + paths[name] + '"/></svg>'


def fold(ident, title, purpose, body, cls='report-section', decision=''):
    state = ' data-decision="' + esc(decision) + '"' if decision else ''
    return (f'<details class="{cls}" id="{esc(ident)}"{state}><summary>'
            f'<span class="summary-text"><span class="fold-title">{esc(title)}</span>'
            f'<span class="fold-purpose">{esc(purpose)}</span></span>'
            f'<span class="fold-state" aria-hidden="true">{icon("chevron")}</span></summary>'
            f'<div class="fold-content">{body}</div></details>')


def overview(run, count):
    display = run.get('report_overview')
    mode_note = '具体岗位定制' if run['mode'] == 'jd' else '岗位方向探索'
    body = ['<section class="overview" id="overall" aria-labelledby="overall-title"><div class="judgment">',
            '<div class="overview-label"><h2 id="overall-title">一、整体判断</h2><span class="mode">' + mode_note + '</span></div>']
    if display:
        body.extend(['<h3 class="overview-headline">' + esc(display['headline']).replace('\n', '<br>') + '</h3>',
                     '<div class="overview-intro">' + prose(display['introduction']) + '</div>'])
        if display.get('assessment'):
            body.append('<dl class="fit-assessment" aria-label="岗位要求对照">')
            for n,item in enumerate(display['assessment'],1):
                body.append('<div class="fit-row"><dt>'+esc(subnumber(n)+item['dimension'])+'<span class="fit-state fit-'+esc(item['status'])+'">'+esc({'met':'基本达标','partial':'部分达标','unknown':'尚不能判断','unmet':'不符合'}[item['status']])+'</span></dt><dd>'+esc(item['judgment'])+'</dd></div>')
            body.append('</dl>')
            body.append(p(display['fit_scope'],'fit-boundary'))
            body.append(p(display['eligibility'],'fit-eligibility'))
        else:
            body.extend(['<div class="judgment-points"><div><h4>' + icon('check') + '（一）已有经历依据</h4>' + text_points(display['evidence_summary']) + '</div>',
                         '<div><h4>' + icon('search') + '（二）关键证据缺口</h4>' + text_points(display['gap_summary']) + '</div></div>'])
    else:
        body.append('<div class="overview-prose">' + text_points(run['summary']) + '</div>')
    body.append('</div>')
    priorities = display['priorities'] if display else []
    if not display:
        priorities = [{'title': '', 'text': a['text']} for a in run.get('actions', []) if a['type'] == 'evidence'][:2]
    if priorities:
        body.append('<aside class="advice" aria-label="优先补充事项"><h3>优先补充事项</h3><div class="advice-items">')
        for n,item in enumerate(priorities,1):
            body.append('<div class="advice-item">' + '<span class="priority-number">'+str(n)+'.</span><div>'
                        + ('<h4>' + esc(item['title']) + '</h4>' if item['title'] else '') + prose(item['text']) + '</div></div>')
        body.append('</div>' + p('材料未呈现的部分仍需核实，不能据此认定候选人缺乏相应能力。', 'kind-note') + '</aside>')
    body.append('</section>')
    return ''.join(body)


def render(directory, output_dir):
    root = Path(directory)
    result = validate_run(root)
    if not result['ok']:
        raise ValueError(json.dumps(result, ensure_ascii=False))
    run = read_json(root / 'run.json')
    sources = read_json(root / 'sources.json')['sources']
    units = {u['id']: u for s in sources for u in s['units']}
    reqs = read_json(root / 'requirements.json')
    reqmap = {r['id']: r for r in reqs}
    evidence = {e['id']: e for e in read_json(root / 'evidence.json')}
    diags = sorted(read_json(root / 'diagnosis.json'), key=lambda d: {'high':0,'medium':1,'low':2}[d.get('priority','medium')])
    diagmap = {d['id']: d for d in diags}
    reviews = read_json(root / 'sentence_review.json')
    count = result['counts']

    def evidence_inline(ids):
        body = []
        for ident in dict.fromkeys(ids):
            e = evidence[ident]
            u = units[e['unit_id']]
            location = (u.get('section') or '简历信息') + '，提取文本第 ' + str(u['line']) + ' 行；' + label(e['status'])
            body.extend(['<div class="source-excerpt">', p(location, 'source-location'),
                         '<blockquote>' + esc(e['quote']) + '</blockquote></div>'])
        return ''.join(body)

    def support_fold(ids, ident):
        if not ids:
            return ''
        return fold(ident, '原文依据', f'在当前内容中展开 {len(set(ids))} 条引用原文', evidence_inline(ids), 'inline-evidence')

    title = run.get('report_title') or ((run.get('target') + ' ' if run.get('target') else '') + '简历诊断报告')
    mode = label(run['mode'])
    stage = run.get('stage')
    subtitle = mode + ('，目标阶段：' + stage if stage and stage != 'unknown' else '') + '。'
    brand = '<div class="brand"><svg viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="5" y="3" width="22" height="26" rx="6"/><path d="M11 11h10M11 16h7M11 21h4"/><circle cx="24" cy="24" r="6" fill="#fff"/><path d="m21 24 2 2 4-4"/></svg><span>简历雷达（resume radar）</span></div>'
    parts = ['<header class="topbar"><div class="topbar-inner">', brand,
             '<span class="report-category">岗位分析与逐句审阅</span></div></header><main class="page">',
             '<div class="page-heading"><div><h1>' + esc(title) + '</h1>' + p(subtitle) + '</div>',
             p('报告日期　' + str(run['analysis_date']), 'date') if run.get('analysis_date') else '',
             p('报告修订　' + str(run['report_revision']), 'date') if run.get('report_revision') else '',
             '</div>', overview(run, count),
             '<div class="report-intro"><div><h2>诊断明细</h2>' + p('从原文出发，直接看哪里需要调整。') + '</div>',
             '<div class="report-controls" role="group" aria-label="控制报告详情的展开与收起"><button type="button" data-action="expand">展开全部详情</button><button type="button" data-action="collapse">收起全部详情</button></div></div>',
             '<div class="report-index">']

    source_map={source['id']:source for source in sources}
    jobs=[source for source in sources if source['kind']=='jd_sample']
    options=run.get('role_options') or [{'role':run.get('target') or '方向待确定','rationale':'依据本次提供的简历与岗位要求进行评估。','jd_source_ids':[source['id'] for source in jobs if source['metadata']['role']==run.get('target')]}]
    basis=[]
    for n,option in enumerate(options,1):
        basis.append('<article class="direction-recommendation"><h3>'+esc(subnumber(n)+option['role'])+'</h3>'+p(option['rationale'],'direction-reason'))
        candidates=option.get('recommended_jd_source_ids',option.get('jd_source_ids',[]))
        candidates=[source_map[i] for i in candidates if i in source_map and source_map[i].get('kind')=='jd_sample' and source_map[i]['metadata']['availability']!='closed'][:2]
        if candidates:
            basis.append('<div class="recommended-jobs"><span>岗位推荐</span><ul>')
            for source in candidates:
                meta=source['metadata']
                state='页面显示开放' if meta['availability']=='open' else '状态待核实'
                basis.append('<li><a href="'+esc(meta['url'])+'" target="_blank" rel="noopener noreferrer">'+esc(meta['title'])+'</a><span class="job-note">'+esc(meta['location']+' · '+state)+'</span></li>')
            basis.append('</ul></div>')
        else:
            basis.append(p('岗位推荐：暂无已核实可投递的岗位。','job-note'))
        basis.append('</article>')
    if any(source['metadata']['availability']=='unknown' for source in jobs):
        basis.append(p('岗位链接仅供核对；状态未确认的岗位，投递前请查看原页面。','direction-boundary'))
    parts.append('<section class="report-section direction-section" id="basis"><header class="plain-section-heading"><h2>二、方向建议</h2></header><div class="fold-content">'+''.join(basis)+'</div></section>')

    order={u['id']:i for i,u in enumerate(u for source in sources if source['kind']=='resume' for u in source['units'])}
    ordered=sorted(reviews,key=lambda v:min(order[u] for u in v['unit_ids']))
    main=[p(f'共 {count["reviewed"]} 处原文，{count["awaiting_input"]} 处待确认。每条展开后依次查看原文、改后、原因与建议。','coverage-note')]
    anchored=set()
    for n,v in enumerate(ordered,1):
        original='\n'.join(units[u]['text'] for u in v['unit_ids'])
        short=v.get('title') or re.sub(r'^\s*[#*\-]+\s*','',original).strip()
        if len(short)>55: short=short[:54]+'…'
        content=['<div class="sentence-comparison"><div class="sentence-field original-column"><h4>原文</h4><blockquote>'+esc(original)+'</blockquote></div>']
        if v['decision']=='keep':
            after=p('保留原文。','unchanged-copy')
        elif v['decision']=='drop':
            after=p('建议从目标版本删除。原文保留在来源记录中。')
        elif v.get('text'):
            after=prose(v['text'])
            # A short factual lead remains part of the validated rewrite text.
            lead=re.match(r'^【([^【】\n]{1,32})】',v['text'])
            if lead:
                after='<p class="rewrite-lead"><strong>'+esc(lead.group(1))+'</strong></p>'+prose(v['text'][lead.end():].lstrip())
            if v['decision']=='needs_input':after+=p('保守表达，关键事实确认后再定稿。','pending-copy')
        else:
            after=p('暂不定稿，先确认下方问题。','pending-copy')
        content.append('<div class="sentence-field revised-column"><h4>改后</h4>'+after+'</div></div>')
        # Global diagnosis records are never pasted into a sentence: the local reason and
        # question must be written against this exact original text by the reviewing module.
        notes=[part.strip() for part in v['reason'].split('\n') if part.strip()]
        if v.get('question'):notes.append('需要确认：'+v['question'])
        anchors=[]
        for did in v.get('diagnosis_ids',[]):
            if did not in anchored:
                anchors.append('<span id="diagnosis-'+esc(did)+'" class="diagnosis-anchor"></span>');anchored.add(did)
        content.append('<div class="sentence-field sentence-reasons">'+''.join(anchors)+'<h4>原因与建议</h4>'+numbered_points(list(dict.fromkeys(notes)))+'</div>')
        locations=[]
        for uid in v['unit_ids']:
            u=units[uid];locations.append((u.get('section') or '原文')+' · 第'+str(u['line'])+'行')
        content.append(p('来源：'+'；'.join(locations),'source-location'))
        main.append(fold('sentence-'+v['id'],subnumber(n)+short,label(v['decision']),''.join(content),'sentence',v['decision']))
    if run.get('final_text'):
        main.append('<div class="final-copy"><h3>完整修改稿</h3>'+prose(run['final_text'])+'</div>')
    parts.append('<section class="report-section review-section" id="gaps"><header class="plain-section-heading"><h2>三、逐句审阅</h2></header><div class="fold-content">'+''.join(main)+'</div></section>')
    footer = ('本次为方向级分析。具体岗位匹配需结合实际 JD，进一步审阅能力要求与经历相关性。'
              if run['mode'] != 'jd' else '本报告依据所提供的简历与 JD 分析，待确认信息以补充材料为准。')
    scope_notes='；'.join(run.get('report_scope_notes',[]))
    if scope_notes: footer+=' '+scope_notes
    parts.append('</div><footer class="report-footer">' + p(footer) + '</footer></main>')

    css = (Path(__file__).resolve().parent.parent / 'assets' / 'report.css').read_text(encoding='utf-8')
    js = """const folds=()=>[...document.querySelectorAll('details.sentence')];document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>folds().forEach(d=>d.open=b.dataset.action==='expand')));function revealHash(){const target=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(!target)return;let parent=target.parentElement;while(parent){if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement}requestAnimationFrame(()=>target.scrollIntoView({block:'center'}))}window.addEventListener('hashchange',revealHash);if(location.hash)revealHash();let printState=[];window.addEventListener('beforeprint',()=>{printState=folds().map(d=>d.open);folds().forEach(d=>d.open=true)});window.addEventListener('afterprint',()=>folds().forEach((d,i)=>d.open=!!printState[i]));"""
    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + esc(title) + '</title><style>' + css + '</style></head><body>' + ''.join(parts) + '<script>' + js + '</script></body></html>')
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'resume-review.html'
    target.write_text(page, encoding='utf-8')
    (out / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'html': str(target.resolve()), 'validation': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    try:
        result = render(args.run_dir, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
