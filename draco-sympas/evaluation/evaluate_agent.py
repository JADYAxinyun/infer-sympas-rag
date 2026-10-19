#!/usr/bin/env python3
"""Four explicit ablations on constructed smoke cases; no model-quality claims."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import ReviewAgent, save

MODES = {
    'A_text': dict(retrieval='text', infer_mode='off', llm_provider='mock'),
    'B_relations': dict(retrieval='relations', infer_mode='off', llm_provider='mock'),
    'C_infer_slice': dict(retrieval='off', infer_mode='real', llm_provider='none'),
    'D_full_mock': dict(retrieval='relations', infer_mode='real', llm_provider='mock'),
}
CASES = [('unchecked', 'open_config', False, 1), ('checked', 'open_config', True, 0),
         ('unknown_numeric', 'numeric_value', False, 0), ('unknown_negative', 'unknown_status', False, 1)]


def evaluate(output, infer_bin):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    with tempfile.TemporaryDirectory(prefix='agent-smoke-cases-') as tmp:
        for label, callee, checked, expected in CASES:
            repo = Path(tmp) / label
            repo.mkdir()
            negative = callee != 'numeric_value'
            (repo / 'helper.c').write_text(f'int {callee}(const char *p) {{\n if (!p) return {"-1" if negative else "0"};\n return 0;\n}}\n')
            (repo / 'caller.c').write_text(f'int {callee}(const char *);\nint run(void) {{\n int ret = {callee}("x");\n' +
                                          (' if (ret < 0) return ret;\n' if checked else '') + ' return ret;\n}\n')
            for name, options in MODES.items():
                run = ReviewAgent().review(repo, target_files=['caller.c', 'helper.c'], infer_bin=infer_bin,
                                            output_dir=output / (label + '-' + name), **options)
                folder = Path(run['output_dir'])
                context = json.loads((folder / 'context.json').read_text())
                retrieval = json.loads((folder / 'retrieval.json').read_text())
                # Expected related context is the callee implementation; count once.
                hits = any(item['file'] == 'helper.c' and item['procedure'] == callee
                           for result in retrieval if result['query']['file'] == 'caller.c' for item in result['items'])
                model_ran = run['llm']['status'] == 'ok'
                parsed = bool(run['model_review']) and not run['validation']['schema_errors']
                predicted = len(run['findings'])
                # unknown_negative contract only becomes a candidate under real Infer.
                rows.append(dict(case=label, mode=name, expected=expected, predicted=predicted,
                                 false_reports=max(predicted - expected, 0), missed_reports=max(expected - predicted, 0),
                                 evidence_coverage=round(run['context_evidence_count'] / run['evidence_count'], 4) if run['evidence_count'] else None,
                                 related_context_hit=int(hits) if options['retrieval'] != 'off' else None,
                                 evidence_insufficient=int(run['model_review']['status'] == 'evidence_insufficient') if parsed else None,
                                 json_parse_success=int(parsed) if model_ran else None,
                                 rule_validation_pass=all(item.get('after_findings', 0) < item.get('before_findings', 0)
                                                          for item in run['repairs']) if run['repairs'] else None,
                                 elapsed_ms=run['telemetry']['elapsed_ms'], token_usage=run['llm'].get('usage'),
                                 prompt_token_upper_bound=context['token_upper_bound'], api_status='not_run',
                                 infer_status=run['infer']['status']))
    summary = {}
    for mode in MODES:
        selected = [row for row in rows if row['mode'] == mode]
        def average(field):
            values = [row[field] for row in selected if row[field] is not None]
            return round(sum(values) / len(values), 4) if values else None
        summary[mode] = dict(samples=len(selected), false_reports=sum(row['false_reports'] for row in selected),
                             missed_reports=sum(row['missed_reports'] for row in selected),
                             **{field: average(field) for field in ('evidence_coverage', 'related_context_hit', 'evidence_insufficient',
                                                                 'json_parse_success', 'rule_validation_pass', 'elapsed_ms')})
    result = dict(scope='prototype smoke evaluation', samples='4 constructed C cases x 4 modes', modes=MODES,
                  metrics_definitions=dict(evidence_coverage='prompt records / available records; not semantic coverage',
                                           related_context_hit='callee implementation retrieved, binary per case',
                                           rule_validation_pass='local finding count decreased for available repair candidates',
                                           token_usage='null for mock/none; byte upper bound is separate, never billed usage'),
                  limitations=['Constructed cases are not independent real-project labels.',
                               'Mock is deterministic; this does not measure DeepSeek judgment quality.',
                               'C uses no LLM; A/B omit Infer and share the same conservative local rule.',
                               'API status is not_run in all four modes.'], summary=summary, rows=rows)
    save(output / 'evaluation.json', result)
    lines = ['# Prototype smoke evaluation', '', result['samples'], '',
             '| Mode | False reports | Missed | Context hit | JSON parse | Mean ms |', '|---|---:|---:|---:|---:|---:|']
    for mode, value in summary.items():
        lines.append(f"| {mode} | {value['false_reports']} | {value['missed_reports']} | {value['related_context_hit']} | {value['json_parse_success']} | {value['elapsed_ms']} |")
    lines += ['', 'Null = not applicable / not run.'] + ['', *result['limitations']]
    (output / 'evaluation.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(output=str(output), scope=result['scope'], summary=summary), indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--infer-bin', default=os.getenv('INFER_BIN', 'infer'))
    parser.add_argument('--output', type=Path, default=Path(__file__).parents[1] / 'artifacts' / 'agent-evaluation' /
                        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    args = parser.parse_args()
    evaluate(args.output, args.infer_bin)
