"""Lazy local CodeGen service used by the optional review endpoint."""
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from generation.explain_report import build_prompt

_MODEL = None
_TOKENIZER = None


def explain(analysis, model_name="Salesforce/codegen-350M-mono"):
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _TOKENIZER = AutoTokenizer.from_pretrained(model_name)
        _TOKENIZER.truncation_side = "left"
        _MODEL = AutoModelForCausalLM.from_pretrained(model_name).to(device)
        _MODEL.eval()
    device = next(_MODEL.parameters()).device
    inputs = _TOKENIZER(build_prompt(analysis), return_tensors="pt", truncation=True, max_length=2000).to(device)
    with torch.no_grad():
        generated = _MODEL.generate(**inputs, max_new_tokens=96, do_sample=False)
    return _TOKENIZER.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
