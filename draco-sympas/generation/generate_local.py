#!/usr/bin/env python3
"""Generate code completions for DraCo prompt JSONL with a local HF model."""
import argparse
import json
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prompts', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', default='Salesforce/codegen-350M-mono')
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--max-new-tokens', type=int, default=48)
    args = parser.parse_args()
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model).to(device)
    model.eval()
    with Path(args.prompts).open() as src, Path(args.output).open('w') as dst:
        for index, line in enumerate(src):
            if index >= args.limit:
                break
            prompt = json.loads(line)
            inputs = tokenizer(prompt, return_tensors='pt', truncation=True, max_length=1536).to(device)
            with torch.no_grad():
                generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
            completion = tokenizer.decode(generated[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            dst.write(json.dumps({'index': index, 'completion': completion}, ensure_ascii=False) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
