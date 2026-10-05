#!/usr/bin/env python3
import json, sys
from pathlib import Path

def main():
    if len(sys.argv) != 3:
        print(f'usage: {Path(sys.argv[0]).name} METADATA.jsonl COMPLETIONS.jsonl', file=sys.stderr); return 2
    metadata=[json.loads(x) for x in Path(sys.argv[1]).read_text().splitlines()]
    outputs=[json.loads(x) for x in Path(sys.argv[2]).read_text().splitlines()]
    exact=0
    for item in outputs:
        i=item['index']; pred=item.get('completion','').strip(); gold=metadata[i].get('gt','').strip()
        exact += pred.splitlines()[0].strip() == gold.splitlines()[0].strip()
    print(f'samples: {len(outputs)}')
    print(f'exact_first_line: {exact/len(outputs):.4f}' if outputs else 'exact_first_line: 0.0000')
    return 0
if __name__=='__main__': raise SystemExit(main())
