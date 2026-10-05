#!/usr/bin/env python3
"""Use the local CodeGen model to turn a structured review into a short explanation."""
import argparse
import json
from pathlib import Path


def build_prompt(analysis):
    return ("You are a code review assistant. Explain the findings and give a concise fix.\n"
            "Return: issue, evidence, recommendation.\n\n"
            + json.dumps(analysis, ensure_ascii=False, indent=2) + "\nReview:\n")


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="Salesforce/codegen-350M-mono")
    parser.add_argument("--max-new-tokens", type=int, default=96)
    args = parser.parse_args()
    analysis = json.loads(Path(args.input).read_text())
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    tokenizer.truncation_side = "left"
    model = AutoModelForCausalLM.from_pretrained(args.model).to(device)
    model.eval()
    prompt = build_prompt(analysis)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2000).to(device)
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
    text = tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    Path(args.output).write_text(json.dumps({"prompt": prompt, "explanation": text}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
