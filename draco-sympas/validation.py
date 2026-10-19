"""Fail-closed model schema and evidence validation; no LLM verdict promotion."""
import hashlib
import json
from infer_adapter import normalize_report
from sympas_adapter import SymPasAdapter
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


def validate_evidence(review, evidence, repo, *, artifacts=None):
    known = {item['id']: item for item in evidence}
    errors = []
    root = Path(repo).resolve()
    receipts = {}
    if artifacts is not None:
        for name, path in artifacts.items():
            if path is None:
                continue
            try:
                receipts[name] = json.loads(Path(path).read_text())
            except (OSError, ValueError):
                errors.append('unreadable_artifact:' + name)
    checks = []
    for ref in review.get('evidence_refs', []):
        if ref not in known:
            errors.append('unknown_evidence:' + ref)
            continue
        item = known[ref]
        if item['kind'] in ('INFER_FACT', 'SYMPAS_SLICE') and item.get('provenance') != 'real_infer':
            errors.append('non_real_infer:' + ref)
        data = item['data']
        origin_ok = False
        if artifacts is not None:
            if item['kind'] == 'INFER_FACT':
                report = receipts.get('infer_report', [])
                issues = report if isinstance(report, list) else report.get('issues', [])
                raw = data.get('evidence', {}).get('raw_report')
                origin_ok = raw is not None and raw in issues
                if origin_ok:
                    normalized = normalize_report([raw])['findings'][0]
                    origin_ok = all(data.get(key) == normalized.get(key) for key in ('rule', 'file', 'line', 'message')) and data.get('kind') == normalized['rule'] and data.get('procedure') == raw.get('procedure')
            elif item['kind'] == 'SYMPAS_SLICE':
                report = receipts.get('infer_report', [])
                origin_ok = data in SymPasAdapter().read(normalize_report(report))
            elif item['kind'] == 'DRACO_CONTEXT':
                node = next((node for node in receipts.get('index', {}).get('nodes', []) if node['id'] == data.get('id')), None)
                retrieved = any(data == entry for query in receipts.get('retrieval', []) for entry in query.get('items', []))
                origin_ok = bool(node) and retrieved and all(data.get(key) == value for key, value in node.items())
            elif item['kind'] == 'RULE_FACT':
                origin_ok = data in receipts.get('rules', [])
            if not origin_ok:
                errors.append('artifact_mismatch:' + ref)
        locations = []
        if data.get('file'):
            locations.append(data)
        if item['kind'] == 'SYMPAS_SLICE':
            locations.extend(data.get('source_locations', []))
            loc = data.get('criterion', {}).get('location')
            if loc:
                locations.append(loc)
        if not locations:
            errors.append('missing_source_location:' + ref)
        for loc in locations:
            path = (root / loc.get('file', '')).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                errors.append('invalid_file:' + ref)
            elif type(loc.get('line')) is not int or not 1 <= loc['line'] <= len(path.read_text(errors='replace').splitlines()):
                errors.append('invalid_line:' + ref)
            elif artifacts is not None:
                name = path.relative_to(root).as_posix()
                expected = receipts.get('index', {}).get('file_hashes', {}).get(name)
                actual = hashlib.sha256(path.read_text(errors='replace').encode()).hexdigest()
                if expected != actual:
                    errors.append('source_changed_or_unindexed:' + ref)
        checks.append(dict(evidence_ref=ref, kind=item['kind'], origin_verified=origin_ok,
                           locations=[{key: location.get(key) for key in ('file', 'line', 'column') if location.get(key) is not None}
                                      for location in locations]))
    cited = [known[ref] for ref in review.get('evidence_refs', []) if ref in known]
    positive = review.get('status') in ('confirmed', 'likely')
    supports_finding = any(item['kind'] == 'RULE_FACT' or
                           (item['kind'] == 'INFER_FACT' and not item['data'].get('kind', '').startswith('SYMPAS_'))
                           for item in cited)
    if not cited and review.get('status') != 'evidence_insufficient' and not errors:
        errors.append('evidence_insufficient_required')
    if positive and not supports_finding and not errors:
        errors.append('evidence_insufficient_required')
    return dict(status='validation_failed' if errors else 'not_verified' if not cited else 'verified' if artifacts is not None else 'partially_verified',
                errors=sorted(set(errors)), checks=checks,
                scope='Original Infer report, raw slice, index/retrieval/rule receipts and source hashes; not semantic correctness.')
