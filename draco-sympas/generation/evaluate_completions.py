#!/usr/bin/env python3
import json, sys
from pathlib import Path
from difflib import SequenceMatcher

def main():
    if len(sys.argv) != 3:
        print(f'usage: {Path(sys.argv[0]).name} METADATA.jsonl COMPLETIONS.jsonl', file=sys.stderr); return 2
    metadata=[json.loads(x) for x in Path(sys.argv[1]).read_text().splitlines()]
    outputs=[json.loads(x) for x in Path(sys.argv[2]).read_text().splitlines()]
    exact=0
    contains=0
    similarity=0.0
    for item in outputs:
        i=item['index']; pred=item.get('completion','').strip(); gold=metadata[i].get('gt','').strip()
        pred_line = pred.splitlines()[0].strip() if pred else ''
        gold_line = gold.splitlines()[0].strip() if gold else ''
        exact += pred_line == gold_line
        contains += bool(gold_line) and gold_line in pred
        similarity += SequenceMatcher(None, pred_line, gold_line).ratio()
    print(f'samples: {len(outputs)}')
    print(f'exact_first_line: {exact/len(outputs):.4f}' if outputs else 'exact_first_line: 0.0000')
    if outputs:
        print(f'contains_gold_first_line: {contains/len(outputs):.4f}')
        print(f'first_line_similarity: {similarity/len(outputs):.4f}')
    return 0
if __name__=='__main__': raise SystemExit(main())
