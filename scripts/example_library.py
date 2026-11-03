"""Integrity-checked access to the bundled, unchanged Hired reference library."""
import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'hired-library'


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def checked_file(meta):
    path = (ROOT / meta['path']).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Invalid library resource path')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != meta['sha256']:
        raise ValueError('案例库文件校验失败：' + meta['path'])
    return json.loads(raw)


@lru_cache(maxsize=1)
def library():
    release = load_json(ROOT / 'release.json')
    catalog = checked_file(release['catalog'])
    roles = {r['id']: r['name'] for r in catalog['roles']}
    directions = {r['id']: r['name'] for r in catalog['directions']}
    duties = {r['id']: r for r in catalog['duties'] + catalog['commonDuties']}
    cases = {}
    for meta in release['blocks'].values():
        block = checked_file(meta)
        if len(block['cases']) != meta['caseCount']:
            raise ValueError('案例块数量不符')
        for case in block['cases']:
            if case['id'] in cases:
                raise ValueError('Duplicate case ID')
            duty = duties[case['dutyId']]
            cases[case['id']] = dict(case,
                roleName=roles.get(case['roleId'], '通用产品职责'),
                directionName=directions.get(case['directionId'], '通用产品职责'),
                dutyName=duty['name'])
    if len(cases) != release['counts']['workExamples']:
        raise ValueError('案例总数不符')
    return {'roles': catalog['roles'], 'directions': catalog['directions'],
            'cases': cases, 'version': release['contentVersion'], 'count': len(cases)}


def search(query='', role_id='', limit=12):
    terms = query.lower().split()
    found = []
    for case in library()['cases'].values():
        if role_id and case['roleId'] != role_id: continue
        title = ' '.join([case['roleName'], case['directionName'], case['dutyName']])
        if terms and not all(t in title.lower() for t in terms): continue
        found.append({k: case[k] for k in ('id', 'roleId', 'directionId', 'dutyId', 'roleName', 'directionName', 'dutyName')})
        if len(found) >= limit: break
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', default='')
    parser.add_argument('--role-id', default='')
    parser.add_argument('--case-id')
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        data = library()
        if args.verify:
            result = {'ok': True, 'cases': data['count'], 'roles': len(data['roles']), 'directions': len(data['directions'])}
        elif args.case_id:
            if args.case_id not in data['cases']: raise ValueError('未知案例 ID')
            result = data['cases'][args.case_id]
        else:
            result = search(args.query, args.role_id, max(1, min(args.limit, 100)))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    from cli_support import configure_stdio
    configure_stdio()
    raise SystemExit(main())
