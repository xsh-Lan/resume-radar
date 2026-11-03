"""Build the local original-PDF review workbench from a validated analysis ledger."""
import hashlib
import json
import re
import shutil
import webbrowser
from pathlib import Path
from workflow import read_json, validate_run
from pdf_source import read_pdf, locate_units
from example_library import library
from source_semantics import presentation_reviews

ROOT = Path(__file__).resolve().parents[1]


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def product_scope(run):
    scope = run.get('example_library_scope')
    if scope is not None:
        if scope not in {'product_management', 'other'}: raise ValueError('example_library_scope 无效')
        return scope == 'product_management'
    return bool(re.search(r'产品|product\s*manage', run.get('target', ''), re.I))


def render_workbench(run_dir, output_dir, pdf_path=None, open_browser=False):
    root = Path(run_dir).resolve()
    validation = validate_run(root)
    if not validation['ok']: raise ValueError('分析数据尚未通过校验：' + safe_json(validation['errors']))
    origin_file = root / 'pdf-origin.json'
    origin = read_json(origin_file) if origin_file.exists() else {}
    pdf = Path(pdf_path).resolve() if pdf_path else root / 'original.pdf'
    if not pdf.is_file(): raise ValueError('缺少 PDF 原件，请以 PDF 初始化，或指定 --pdf。')
    if origin and hashlib.sha256(pdf.read_bytes()).hexdigest() != origin['sha256']:
        raise ValueError('PDF 与初始化时的原件不一致，请建立新的分析版本。')
    sources = read_json(root / 'sources.json')['sources']
    resume = next(s for s in sources if s['kind'] == 'resume')
    # Prepare and validate everything before replacing a previously generated report.
    document = read_pdf(pdf)
    locations = locate_units(document, resume['units'])
    run = read_json(root / 'run.json')
    reviews = read_json(root / 'sentence_review.json')
    visible_reviews, layout_ids = presentation_reviews(resume, reviews)
    references = library()
    links_file = root / 'example_links.json'
    links = read_json(links_file) if links_file.exists() else []
    if not isinstance(links, list): raise ValueError('example_links.json 必须为列表')
    review_ids = {r['id'] for r in reviews}
    applicable = product_scope(run)
    for link in links:
        if not isinstance(link, dict) or link.get('review_id') not in review_ids or link.get('case_id') not in references['cases']:
            raise ValueError('案例关联引用了不存在的审阅或案例')
        if not applicable: raise ValueError('当前目标不属于产品经理，不应关联产品经理案例。')
        if not link.get('reason') or not link.get('conditions'):
            raise ValueError('案例关联必须说明适用理由和条件')
    out = Path(output_dir).resolve()
    if out == root or out in pdf.parents or out in root.parents:
        raise ValueError('请使用独立的报告子目录，避免覆盖运行资料。')
    out.mkdir(parents=True, exist_ok=True)
    document = read_pdf(pdf, out / 'pages')
    original_copy = out / 'original.pdf'
    if pdf != original_copy: shutil.copyfile(pdf, original_copy)
    data = {'run': run, 'resume': resume, 'sources': sources,
            'reviews': visible_reviews, 'layoutUnitIds': layout_ids,
            'diagnoses': read_json(root / 'diagnosis.json'),
            'requirements': read_json(root / 'requirements.json'),
            'evidence': read_json(root / 'evidence.json'), 'pages': document['pages'],
            'locations': locations, 'links': links, 'libraryApplicable': applicable,
            'filename': origin.get('filename', pdf.name),
            'documentHash': document['sha256'], 'libraryCount': references['count'],
            'confirmation': read_json(root / 'confirmation.json') if (root / 'confirmation.json').exists() else {}}
    css = (ROOT / 'assets' / 'workbench.css').read_text(encoding='utf-8')
    js = (ROOT / 'assets' / 'workbench.js').read_text(encoding='utf-8')
    template = (ROOT / 'assets' / 'workbench.html').read_text(encoding='utf-8')
    page = template.replace('/* RADAR_CSS */', css).replace('/* RADAR_JS */', js).replace('/* RADAR_DATA */', 'const DATA=' + safe_json(data) + ';')
    (out / 'library.js').write_text('window.RADAR_LIBRARY=' + safe_json(references) + ';', encoding='utf-8')
    target = out / 'resume-review.html'
    target.write_text(page, encoding='utf-8')
    matched = sum(x['status'] == 'matched' for x in locations.values())
    validation['pdf_mapping'] = {'matched': matched, 'total': len(locations),
        'unresolved': [uid for uid, loc in locations.items() if loc['status'] != 'matched']}
    validation['presentation'] = {'layout_units': len(layout_ids),
        'content_units': len(resume['units']) - len(layout_ids), 'review_items': len(visible_reviews)}
    (out / 'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
    if open_browser: webbrowser.open(target.as_uri())
    return {'html': str(target), 'validation': validation, 'library_cases': references['count']}
