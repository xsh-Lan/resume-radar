#!/usr/bin/env python3
"""Render a standalone resume diagnosis. Only the overall judgment starts visible."""
import argparse
import html
import json
import re
from collections import OrderedDict
from pathlib import Path
from workflow import read_json, validate_run
from sanitize_report import sanitize_text

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
}


def esc(value):
    return html.escape(str(value), quote=True)


def label(value):
    return LABELS.get(value, value)


def p(value, cls=''):
    return '<p' + (' class="' + cls + '"' if cls else '') + '>' + esc(value).replace('\n', '<br>') + '</p>'


def prose(value):
    return ''.join(p(v) for v in re.split(r'\n\s*\n', str(value)) if v.strip())


def field(title, value, kind=''):
    return '<div class="field' + (' field-' + kind if kind else '') + '"><h4>' + esc(title) + '</h4>' + prose(value) + '</div>'


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
    mode_note = '依据本次提供的 JD' if run['mode'] == 'jd' else '尚未提供具体 JD'
    body = ['<section class="overview" id="overall" aria-labelledby="overall-title"><div class="judgment">',
            '<div class="overview-label"><h2 id="overall-title">整体判断</h2><span class="mode">' + mode_note + '</span></div>']
    if display:
        body.extend(['<h3 class="overview-headline">' + esc(display['headline']).replace('\n', '<br>') + '</h3>',
                     '<div class="overview-intro">' + prose(display['introduction']) + '</div>',
                     '<div class="judgment-points"><div><h4>' + icon('check') + '已有经历依据</h4>' + prose(display['evidence_summary']) + '</div>',
                     '<div><h4>' + icon('search') + '关键证据缺口</h4>' + prose(display['gap_summary']) + '</div></div>'])
    else:
        body.append('<div class="overview-prose">' + prose(run['summary']) + '</div>')
    body.append('</div>')
    priorities = display['priorities'] if display else []
    if not display:
        priorities = [{'title': '', 'text': a['text']} for a in run.get('actions', []) if a['type'] == 'evidence'][:2]
    if priorities:
        body.append('<aside class="advice" aria-label="优先补充事项"><h3>优先补充事项</h3><div class="advice-items">')
        for item in priorities:
            body.append('<div class="advice-item">' + icon('arrow') + '<div>'
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
    diags = read_json(root / 'diagnosis.json')
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
             '</div>', overview(run, count),
             '<div class="report-intro"><div><h2>诊断明细</h2>' + p('展开栏目，查看分析依据与修订建议。') + '</div>',
             '<div class="report-controls" role="group" aria-label="控制报告详情的展开与收起"><button type="button" data-action="expand">展开全部详情</button><button type="button" data-action="collapse">收起全部详情</button></div></div>',
             '<div class="report-index">']

    basis = [field('当前分析方向', run.get('target') or '方向尚待确定')]
    if run.get('target_status') == 'provisional':
        basis.append(p('当前方向依据简历材料暂定，尚待用户确认。', 'boundary-note'))
    basis.append(field('分析范围', '经历与指标按所提供材料记录，未做外部事实核验。' +
                       ('未提供具体 JD，岗位要求为方向级参考，不代表特定公司的招聘门槛或录用概率。'
                        if run['mode'] != 'jd' else '岗位要求依据本次提供的 JD；解释性推断另行说明。')))
    if run.get('assumptions'):
        basis.append(field('假设与适用边界', '\n'.join(run['assumptions'])))
    if run.get('report_overview'):
        basis.append(field('整体判断详细说明', run['summary']))
    for n, option in enumerate(run.get('role_options', []), 1):
        basis.extend(['<article class="analysis-item"><h3>' + esc(option['role']) + '</h3>',
                      field('方向支持依据', option['rationale']), field('待确认信息', option['unknowns']),
                      support_fold(option['evidence_ids'], 'role-' + str(n)), '</article>'])
    basis.append('<h3 class="subsection-title">目标方向的岗位能力要求</h3>')
    for r in reqs:
        basis.extend(['<article class="analysis-item"><h3>' + esc(r['description']) + '</h3>',
                      p(label(r['support']) + '；' + ('JD 明示要求' if r['basis'] == 'jd' else label(r['basis'])), 'item-status'),
                      field('岗位任务', r['task']), field('责任范围与决策深度', r['responsibility'] + '；' + r['decision_depth'])])
        for uid in r.get('source_unit_ids', []):
            basis.append(field('JD 原文', units[uid]['text'], 'original'))
        if r.get('basis_note'):
            basis.append(field('标准依据与适用范围', r['basis_note']))
        basis.extend([support_fold(r.get('evidence_ids', []), 'req-' + r['id']), '</article>'])
    parts.append(fold('basis', '岗位方向与判断依据', '分析方向的适用范围、经历依据及岗位能力要求', ''.join(basis)))

    gaps = []
    if not diags:
        gaps.append(p('当前材料不足以支持额外差距判断，详见岗位要求与逐句审阅。'))
    for n, d in enumerate(diags, 1):
        gaps.extend(['<article class="analysis-item"><h3>' + esc(d.get('title') or label(d['gap_type'])) + '</h3>',
                     p(label(d['gap_type']), 'item-status')])
        if d.get('requirement_ids'):
            gaps.append(field('对应岗位要求', '；'.join(reqmap[i]['description'] for i in d['requirement_ids'])))
        gaps.extend([field('已有经历依据', d['demonstrates']), field('尚未充分支持的判断', d['does_not_demonstrate']),
                     field('对岗位匹配的影响', d['impact'])])
        if d.get('question'):
            gaps.append(field('待核实事项', d['question'], 'question'))
        gaps.extend([field('补充与修订建议', d['next_action']), support_fold(d['evidence_ids'], 'gap-source-' + str(n)), '</article>'])
    parts.append(fold('gaps', '关键差距与补齐建议', f'{len(diags)} 项诊断：现有依据、岗位影响与补充建议', ''.join(gaps)))

    order = {u['id']: i for i, u in enumerate(u for s in sources if s['kind'] == 'resume' for u in s['units'])}
    groups = OrderedDict()
    for v in sorted(reviews, key=lambda x: min(order[u] for u in x['unit_ids'])):
        section = units[v['unit_ids'][0]].get('section') or '基本信息'
        groups.setdefault(section, []).append(v)
    sentence_parts = [p(f'已审阅 {count["reviewed"]} 个单元，其中 {count["awaiting_input"]} 个单元待补充事实。保留原句属于有效处理；待确认项尚未定稿。', 'coverage-note')]
    for section, items in groups.items():
        sentence_parts.append('<h3 class="subsection-title">' + esc(section) + '</h3>')
        for v in items:
            original = '\n'.join(units[u]['text'] for u in v['unit_ids'])
            short = v.get('title') or re.sub(r'^\s*[#*\-]+\s*', '', original).strip()
            if len(short) > 62:
                short = short[:61] + '…'
            content = ['<div class="review-grid"><div class="review-pane">', field('简历原文', original, 'original'),
                       '</div><div class="review-pane">', field('已体现的岗位能力', v['capability']),
                       field('处理依据与证据判断', v['reason']), field('目标岗位相关性', v['role_relevance']), '</div></div>']
            if v.get('diagnosis_ids'):
                content.append(field('关联差距诊断', '；'.join(diagmap[i].get('title') or label(diagmap[i]['gap_type']) for i in v['diagnosis_ids'])))
            if v.get('text') and v['decision'] != 'keep':
                content.append('<div class="field field-rewrite"><div class="rewrite-heading"><h4>建议修订文本</h4>'
                               + ('<span>基于现有材料，待补充事实后定稿</span>' if v['decision'] == 'needs_input' else '')
                               + '</div>' + prose(v['text']) + '</div>')
            if v.get('question'):
                content.append(field('待核实事项', v['question'], 'question'))
            sentence_parts.append(fold('sentence-' + v['id'], short, label(v['decision']) + '；展开查看原文、岗位判断与修订依据',
                                       ''.join(content), 'sentence', v['decision']))
    parts.append(fold('sentences', '逐句审阅与修改建议', f'按简历顺序审阅全部 {count["resume_units"]} 个单元，保留待确认信息', ''.join(sentence_parts)))
    if run.get('final_text'):
        parts.append(fold('rewrite', '目标版本正文', '基于已提供事实整理的完整修订正文', prose(run['final_text'])))

    action_parts = []
    action_labels = {'edit': '可直接修订', 'evidence': '事实与材料补充', 'practice': '后续实践建议', 'decision': '求职方向选择'}
    for kind, title_a in action_labels.items():
        items = [a for a in run.get('actions', []) if a.get('type') == kind]
        if items:
            action_parts.append('<h3 class="subsection-title">' + title_a + '</h3><ol>')
            action_parts.extend('<li>' + prose(a['text']) + '</li>' for a in items)
            action_parts.append('</ol>')
    if not action_parts:
        action_parts.append(p('本次无额外行动项，具体修订意见见逐句审阅。'))
    parts.append(fold('actions', '修订与事实补充清单', '区分可直接修订、待补充事实、后续实践与方向选择', ''.join(action_parts)))
    source_parts = [p('本报告引用原文如下。位置对应提取文本的行号，不代表原 Word 的页码或排版。'), evidence_inline(list(evidence))]
    parts.append(fold('source-records', '原文依据核对', '核对报告所引用的全部简历原文与来源位置', ''.join(source_parts)))
    footer = ('本次为方向级分析。具体岗位匹配需结合实际 JD，进一步审阅能力要求与经历相关性。'
              if run['mode'] != 'jd' else '本报告依据所提供的简历与 JD 分析，待确认信息以补充材料为准。')
    parts.append('</div><footer class="report-footer">' + p(footer) + '</footer></main>')

    css = (Path(__file__).resolve().parent.parent / 'assets' / 'report.css').read_text(encoding='utf-8')
    js = """const folds=()=>[...document.querySelectorAll('details')];document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>folds().forEach(d=>d.open=b.dataset.action==='expand')));let printState=[];window.addEventListener('beforeprint',()=>{printState=folds().map(d=>d.open);folds().forEach(d=>d.open=true)});window.addEventListener('afterprint',()=>folds().forEach((d,i)=>d.open=!!printState[i]));"""
    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + esc(title) + '</title><style>' + css + '</style></head><body>' + ''.join(parts) + '<script>' + js + '</script></body></html>')
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'resume-review.html'
    target.write_text(sanitize_text(page), encoding='utf-8')
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
