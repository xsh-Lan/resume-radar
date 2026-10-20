#!/usr/bin/env python3
"""Sanitize explicitly named files only, with visible errors."""
import argparse
import json
import re
from pathlib import Path

PATTERNS = [re.compile(x,re.I) for x in (
    r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
    r'(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)',
    r'(?:微信|WeChat|QQ)\s*[:：]\s*[A-Za-z0-9_\-]{5,}',
    r'https?://(?:www\.)?linkedin\.com/[^\s<>|，。；）\]]+')]

def contact_matches(text):
    return any(p.search(text) for p in PATTERNS)

def sanitize_text(text, names=()):
    text=re.sub(r'姓名\s*[:：]\s*[^\r\n<>|；，。]{1,20}','[姓名已删除]',text)
    for pattern in PATTERNS:
        text=pattern.sub('[联系方式已删除]',text)
    for name in sorted((n for n in names if n),key=len,reverse=True):
        text=text.replace(name,'[姓名已删除]')
    return text

def sanitize_values(value,names):
    if isinstance(value,str): return sanitize_text(value,names)
    if isinstance(value,list): return [sanitize_values(v,names) for v in value]
    if isinstance(value,dict): return {k:sanitize_values(v,names) for k,v in value.items()}
    return value

def process_files(paths,names=()):
    result={'ok':True,'processed':[],'changed':[],'errors':[]}
    for raw in dict.fromkeys(str(Path(p).resolve()) for p in paths):
        p=Path(raw)
        try:
            if p.suffix.lower() not in {'.md','.txt','.json','.html','.csv'}: raise ValueError('Unsupported text file suffix')
            text=p.read_text(encoding='utf-8-sig')
            if p.suffix.lower()=='.json':
                original=json.loads(text); clean=sanitize_values(original,names)
                new=json.dumps(clean,ensure_ascii=False,indent=2)+'\n' if original!=clean else text
            else: new=sanitize_text(text,names)
            if new!=text:
                p.write_text(new,encoding='utf-8'); result['changed'].append(raw)
            result['processed'].append(raw)
        except (OSError,ValueError) as exc:
            result['errors'].append({'path':raw,'error':str(exc)})
    result['ok']=not result['errors']
    result['boundary']='Known contact patterns and explicitly supplied names only; inspect unusual identifiers manually.'
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',action='append',required=True)
    parser.add_argument('--redact-name',action='append',default=[])
    args=parser.parse_args(); result=process_files(args.file,args.redact_name)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1

if __name__=='__main__': raise SystemExit(main())
