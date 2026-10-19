"""Lazy local CodeGen service used by the optional review endpoint."""
import json
from generation.explain_report import build_prompt

_MODEL = None
_TOKENIZER = None


def explain(analysis, model_name="Salesforce/codegen-350M-mono", *, prompt=None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _TOKENIZER = AutoTokenizer.from_pretrained(model_name)
        _TOKENIZER.truncation_side = "left"
        _MODEL = AutoModelForCausalLM.from_pretrained(model_name).to(device)
        _MODEL.eval()
    device = next(_MODEL.parameters()).device
    inputs = _TOKENIZER(prompt if prompt is not None else build_prompt(analysis), return_tensors="pt", truncation=True, max_length=2000).to(device)
    with torch.no_grad():
        generated = _MODEL.generate(**inputs, max_new_tokens=96, do_sample=False)
    return _TOKENIZER.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def token_usage(analysis, explanation, *, prompt=None):
    """Return exact CodeGen tokenizer counts after ``explain`` has loaded it."""
    if _TOKENIZER is None:
        raise RuntimeError("token_usage is available only after explain()")
    prompt_ids = _TOKENIZER(prompt if prompt is not None else build_prompt(analysis), add_special_tokens=False)["input_ids"]
    output_ids = _TOKENIZER(explanation, add_special_tokens=False)["input_ids"]
    return {"prompt_tokens": len(prompt_ids), "output_tokens": len(output_ids)}
