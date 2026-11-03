"""Record confirmations from Codex replies; legacy web input is optional."""
import argparse
import hashlib
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from workflow import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUTS = {'sentence_review': True, 'optimized_resume': True,
                   'modification_scope': '全文', 'followup_questions': False}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def confirm(root, stage, values, prefill):
    root = Path(root)
    if not isinstance(values, dict): raise ValueError('确认内容必须是对象')
    path = root / 'confirmation.json'
    state = read_json(path) if path.exists() else {}
    if stage == 1:
        source = values.get('jd_source')
        if source not in {'provided', 'auto', 'none'}: raise ValueError('请选择 JD 来源')
        focus = values.get('focus')
        if not isinstance(focus, list) or not focus or any(x not in {'岗位匹配', '项目经历', '业务价值', '能力差距', '表达结构'} for x in focus):
            raise ValueError('至少选择一个分析重点')
        target = str(values.get('target', '')).strip()
        choice = values.get('target_choice', 'specified' if target else 'unclear')
        if choice not in {'unclear','specified'}: raise ValueError('请选择目标岗位状态')
        if choice == 'specified' and not target: raise ValueError('请填写意向岗位名称')
        if choice == 'unclear': target = ''
        result = {'target': target, 'target_choice': choice, 'target_route': 'discover' if choice == 'unclear' else 'specified', 'jd_source': source, 'focus': focus,
                  'route': {'provided': '01', 'auto': '02', 'none': '03'}[source]}
        # Any change to the goal invalidates the previously confirmed analysis plan.
        resume = next(s for s in read_json(root / 'sources.json')['sources'] if s['kind'] == 'resume')
        state = {'stage1': result, 'stage1_hash': fingerprint(result), 'resume_sha256': resume['sha256']}
    else:
        first = state.get('stage1')
        if not first or prefill.get('stage1_hash') != state.get('stage1_hash'):
            raise ValueError('需求已变化，请先重新准备分析方案')
        sources = read_json(root / 'sources.json')['sources']
        valid = {s['id']: s for s in sources if s['kind'] in {'jd', 'jd_sample'}}
        ids = values.get('selected_jd_ids', [])
        if not isinstance(ids, list) or any(x not in valid for x in ids) or len(ids) != len(set(ids)):
            raise ValueError('所选 JD 引用无效')
        displayed = {j['source_id'] for j in prefill.get('jobs', [])}
        if any(i not in displayed for i in ids): raise ValueError('请选择页面列出的 JD')
        if first['route'] != '03' and not ids: raise ValueError('岗位匹配需要选择至少一份实际 JD')
        if first['route'] == '03' and ids: raise ValueError('通用诊断不选择目标 JD')
        if any(valid[i].get('metadata', {}).get('availability') == 'closed' for i in ids): raise ValueError('请勿选择已结束的职位')
        if not isinstance(values.get('sentence_review'), bool) or not isinstance(values.get('optimized_resume'), bool):
            raise ValueError('请确认输出选项')
        target = str(values.get('target', first.get('target', ''))).strip()
        if first['route'] != '03' and not target: raise ValueError('请确认本次分析的目标岗位')
        scope = str(values.get('modification_scope', '')).strip()
        capabilities = str(values.get('capabilities', '')).strip()
        if not scope or not capabilities: raise ValueError('请确认修改范围和核心能力要求')
        state['stage2'] = {'target': target, 'selected_jd_ids': ids, 'capabilities': capabilities,
            'modification_scope': scope, 'sentence_review': values['sentence_review'],
            'optimized_resume': values['optimized_resume'], 'stage1_hash': state['stage1_hash'],
            'plan_hash': fingerprint(prefill),
            'source_hashes': {i: valid[i]['sha256'] for i in ids}}
    write_json(path, state)
    return state


def execution_ready(root):
    root = Path(root)
    state = read_json(root / 'confirmation.json')
    if state.get('kind') == 'single_target':
        goal = state.get('target_decision', {})
        if state.get('target_hash') != fingerprint(goal): raise ValueError('求职目标已变化，请更新目标记录')
        if state.get('outputs') != DEFAULT_OUTPUTS: raise ValueError('完整任务使用默认输出，不设输出确认关卡')
        sources = {s['id']: s for s in read_json(root / 'sources.json')['sources']}
        resume = next(s for s in sources.values() if s['kind'] == 'resume')
        if state.get('resume_sha256') != resume['sha256']: raise ValueError('简历来源已变化，请重新核对目标')
        for ident, sha in state['source_hashes'].items():
            if ident not in sources or sources[ident]['sha256'] != sha:
                raise ValueError('目标 JD 已变化，请核对目标')
            if sources[ident].get('metadata', {}).get('availability') == 'closed':
                raise ValueError('目标职位已结束，请重新选择目标')
        receipt = state['reply']
        path = root / receipt['file']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != receipt['sha256']:
            raise ValueError('用户目标回答记录已变化')
        return state
    first, second = state.get('stage1'), state.get('stage2')
    if not first or not second or second.get('stage1_hash') != fingerprint(first):
        raise ValueError('尚未完成两阶段确认')
    sources = {s['id']: s for s in read_json(root / 'sources.json')['sources']}
    resume = next(s for s in sources.values() if s['kind'] == 'resume')
    if state.get('resume_sha256') != resume['sha256']: raise ValueError('简历来源已变化，请重新确认需求')
    plan = root / 'plan-prefill.json'
    if plan.exists() and fingerprint(read_json(plan)) != second['plan_hash']: raise ValueError('分析方案已变化，请重新确认')
    for ident, sha in second['source_hashes'].items():
        if ident not in sources or sources[ident]['sha256'] != sha:
            raise ValueError('选定 JD 已变化，请重新确认方案')
    for item in state.get('conversation_receipts', {}).values():
        reply = Path(root) / item['file']
        if not reply.is_file() or hashlib.sha256(reply.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('对话确认记录已变化，请核对用户原始回答')
    return state


def record_target(root, values, response):
    """One user decision joins direction, JD source and selected/delegated job."""
    root = Path(root)
    reply = Path(response).read_text(encoding='utf-8').strip()
    if not reply or not isinstance(values, dict): raise ValueError('需要实际目标选择与回答')
    source = values.get('jd_source')
    choice = values.get('target_choice')
    if source not in {'provided', 'auto', 'none'} or choice not in {'unclear', 'specified'}:
        raise ValueError('请在同一次目标选择中记录方向与 JD 来源')
    sources = {s['id']: s for s in read_json(root / 'sources.json')['sources']}
    ids = values.get('selected_jd_ids', [])
    if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('目标 JD 引用无效')
    expected_kind = 'jd' if source == 'provided' else 'jd_sample'
    if any(i not in sources or sources[i]['kind'] != expected_kind for i in ids):
        raise ValueError('目标 JD 与来源不一致')
    target = str(values.get('target', '')).strip()
    if source == 'none':
        if ids: raise ValueError('通用诊断不选择 JD')
    elif not ids or not target:
        raise ValueError('先取得真实 JD 并明确分析对象；委托选岗无需再次询问用户')
    if choice == 'specified' and not target: raise ValueError('请记录用户指定目标')
    delegated = values.get('delegated', False)
    if not isinstance(delegated, bool): raise ValueError('delegated 必须为布尔值')
    if any(sources[i].get('metadata', {}).get('availability') == 'closed' for i in ids):
        raise ValueError('不能选择已结束职位')
    goal = {'target_choice': choice, 'target': target, 'jd_source': source,
            'selected_jd_ids': ids, 'delegated': delegated,
            'route': {'provided':'01', 'auto':'02', 'none':'03'}[source]}
    relative = 'confirmation-replies/target.txt'
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reply, encoding='utf-8')
    resume = next(s for s in sources.values() if s['kind'] == 'resume')
    state = {'kind': 'single_target', 'target_decision': goal, 'target_hash': fingerprint(goal),
             'resume_sha256': resume['sha256'], 'source_hashes': {i:sources[i]['sha256'] for i in ids},
             'outputs': dict(DEFAULT_OUTPUTS),
             'reply': {'channel':'codex', 'file':relative, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
    write_json(root / 'confirmation.json', state)
    return state


def record_reply(root, stage, values, prefill, response):
    """The host supplies the actual reply only after the user answers in Codex."""
    reply = Path(response).read_text(encoding='utf-8').strip()
    if not reply: raise ValueError('需要用户实际回答，不能将预填内容视为确认')
    state = confirm(root, stage, values, prefill)
    relative = f'confirmation-replies/stage{stage}.txt'
    target = Path(root) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(reply, encoding='utf-8')
    state.setdefault('conversation_receipts', {})[str(stage)] = {
        'channel': 'codex', 'file': relative,
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    write_json(Path(root) / 'confirmation.json', state)
    return state


def serve(root, stage, prefill, open_browser):
    token = secrets.token_urlsafe(32)
    template = (ROOT / 'assets/confirm.html').read_text(encoding='utf-8')
    payload = dict(prefill, stage=stage)
    if stage == 2:
        state = read_json(Path(root) / 'confirmation.json')
        payload['goal'] = state['stage1']
        if payload.get('stage1_hash') != state['stage1_hash']: raise ValueError('请使用当前需求生成分析方案')
    raw = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c')
    page = template.replace('/* PREFILL */', 'const PREFILL=' + raw + ';const TOKEN=' + json.dumps(token) + ';')
    complete = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            if parse_qs(urlsplit(self.path).query).get('token') != [token]:
                self.send_error(403); return
            body = page.encode()
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            origin = 'http://127.0.0.1:' + str(self.server.server_port)
            if self.path != '/confirm' or self.headers.get('X-Radar-Token') != token or self.headers.get('Origin') != origin:
                self.send_error(403); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size < 100000: raise ValueError('提交内容大小不合适')
                values = json.loads(self.rfile.read(size))
                confirm(root, stage, values, prefill)
                response, status = {'ok': True}, 200
            except (ValueError, KeyError, TypeError) as exc:
                response, status = {'ok': False, 'error': str(exc)}, 400
            self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
            if status == 200: complete.set()

    server = HTTPServer(('127.0.0.1', 0), Handler)
    server.timeout = .5
    url = f'http://127.0.0.1:{server.server_port}/?token={token}'
    print(json.dumps({'url': url, 'stage': stage, 'status': 'awaiting_confirmation'}), flush=True)
    if open_browser: webbrowser.open(url)
    try:
        while not complete.is_set(): server.handle_request()
    finally: server.server_close()
    return {'ok': True, 'stage': stage, 'status': 'confirmed'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', required=True); p.add_argument('--stage', type=int, choices=(1, 2))
    p.add_argument('--prefill'); p.add_argument('--open', action='store_true'); p.add_argument('--ready', action='store_true')
    p.add_argument('--record', help='已确认选项的 JSON 文件')
    p.add_argument('--response', help='用户在 Codex 中的实际回答文本文件')
    p.add_argument('--target-record', help='合并后的求职目标 JSON 文件；完整任务的唯一决策')
    a = p.parse_args()
    try:
        if a.target_record:
            if not a.response or a.stage or a.open or a.record or a.ready:
                raise ValueError('单目标记录只需 target-record 与 response')
            result = record_target(a.run_dir, read_json(a.target_record), a.response)
        elif a.ready: result = execution_ready(a.run_dir)
        else:
            if not a.stage or not a.prefill: raise ValueError('需要 stage 与 prefill')
            if a.record:
                if not a.response or a.open: raise ValueError('对话确认需要 response，且不能同时打开网页')
                result = record_reply(a.run_dir, a.stage, read_json(a.record), read_json(a.prefill), a.response)
            else:
                if not a.open: raise ValueError('请使用 record 保存对话确认；旧网页模式需要显式 open')
                result = serve(a.run_dir, a.stage, read_json(a.prefill), True)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False)); return 1


if __name__ == '__main__':
    from cli_support import configure_stdio
    configure_stdio(); raise SystemExit(main())
