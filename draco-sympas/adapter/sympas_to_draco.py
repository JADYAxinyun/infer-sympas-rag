#!/usr/bin/env python3
import json, re, sys
from pathlib import Path

def facts_by_file(path):
    grouped = {}
    for item in json.loads(Path(path).read_text()):
        grouped.setdefault(item.get('file',''), []).append(item)
    return grouped

def fact_block(items):
    lines=['\n\n# Static facts from Infer-SymPas']
    for item in items:
        lines.append(f"\n## {item.get('procedure','<unknown>')}")
        q=item.get('qualifier','')
        for label, pattern in [('dependency frontier',r'frontier=(.*?); slice_locations='),('path conditions',r'path_conditions=(.*?)}; candidate summary'),('callee summary',r'candidate summary: (.*?); precise control locations')]:
            m=re.search(pattern,q,re.S)
            if m: value=m.group(1).strip()
            if label == 'path conditions' and not value.endswith('}'):
                value += '}'
            lines.append(f"- {label}: {value}")
    return '\n'.join(lines)

def main():
    if len(sys.argv)!=4:
        print(f'usage: {Path(sys.argv[0]).name} PROMPTS.jsonl REPORT.json OUTPUT.jsonl',file=sys.stderr); return 2
    prompts, report, output=map(Path,sys.argv[1:]); grouped=facts_by_file(report)
    with prompts.open() as src, output.open('w') as dst:
        for line in src:
            prompt=json.loads(line); matched=[]
            for file_name, items in grouped.items():
                if file_name and file_name in prompt: matched.extend(items)
            if matched: prompt += fact_block(matched)
            dst.write(json.dumps(prompt,ensure_ascii=False)+'\n')
    return 0
if __name__=='__main__': raise SystemExit(main())
