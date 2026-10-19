"""Fail-closed model schema and evidence validation; no LLM verdict promotion."""
import json
import math
from pathlib import Path

STATUSES = {'confirmed', 'likely', 'uncertain', 'evidence_insufficient', 'not_a_bug'}


def parse_review(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return None, ['invalid_json']
    if not isinstance(value, dict):
        return None, ['expected_object']
    errors = []
    for name in ('status', 'finding_type', 'summary', 'reasoning', 'risk'):
        if not isinstance(value.get(name), str):
            errors.append('invalid_' + name)
    if not isinstance(value.get('status'), str) or value['status'] not in STATUSES:
        errors.append('invalid_status')
    if not isinstance(value.get('risk'), str) or value['risk'] not in {'low', 'medium', 'high'}:
        errors.append('invalid_risk')
    confidence = value.get('confidence')
    if type(confidence) not in (float, int) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        errors.append('invalid_confidence')
    for name in ('evidence_refs', 'limitations'):
        if not isinstance(value.get(name), list) or any(not isinstance(x, str) for x in value.get(name, [])):
            errors.append('invalid_' + name)
    fix = value.get('candidate_fix')
    if not isinstance(fix, dict) or not {'available', 'description', 'patch'} <= fix.keys() or type(fix.get('available')) is not bool or not isinstance(fix.get('description'), str) or not (fix.get('patch') is None or isinstance(fix.get('patch'), str)):
        errors.append('invalid_candidate_fix')
    if value.get('status') in ('confirmed', 'likely') and not value.get('evidence_refs'):
        errors.append('missing_evidence_refs')
    return value, errors


def validate_evidence(review, evidence, repo):
    known = {item['id']: item for item in evidence}
    errors = []
    root = Path(repo).resolve()
    for ref in review.get('evidence_refs', []):
        if ref not in known:
            errors.append('unknown_evidence:' + ref)
            continue
        item = known[ref]
        if item['kind'] in ('INFER_FACT', 'SYMPAS_SLICE') and item.get('provenance') != 'real_infer':
            errors.append('non_real_infer:' + ref)
        data = item['data']
        locations = []
        if data.get('file'):
            locations.append(data)
        if item['kind'] == 'SYMPAS_SLICE':
            locations.extend(data.get('source_locations', []))
            loc = data.get('criterion', {}).get('location')
            if loc:
                locations.append(loc)
        for loc in locations:
            path = (root / loc.get('file', '')).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                errors.append('invalid_file:' + ref)
            elif type(loc.get('line')) is not int or not 1 <= loc['line'] <= len(path.read_text(errors='replace').splitlines()):
                errors.append('invalid_line:' + ref)
    return dict(status='validation_failed' if errors else 'verified', errors=errors,
                scope='Reference existence, provenance, source file and line only; not semantic correctness.')
