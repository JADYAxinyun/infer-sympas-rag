#!/usr/bin/env python3
"""Small-scale prototype evaluation: constructed source and independent behavior oracles."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import ReviewAgent, save
from provider_config import load_env_file
from repair_validation import validate_candidate

CASES = ROOT / 'examples/realistic_case'
MODES = {
    'A_infer_only': dict(infer_profile='native', use_slices=False, run_rules=False, retrieval='off', llm_provider='none'),
    'B_infer_slice': dict(infer_profile='combined', retrieval='off', llm_provider='none'),
    'C_infer_slice_draco': dict(infer_profile='combined', retrieval='relations', llm_provider='none'),
    'D_full_mock': dict(infer_profile='combined', retrieval='relations', llm_provider='mock'),
    'E_full_deepseek': dict(infer_profile='combined', retrieval='relations', llm_provider='deepseek'),
}
REQUIRED_ARTIFACTS = ['infer.json', 'slice.json', 'retrieval.json', 'context.json', 'llm_response.json', 'validation.json', 'review.md']


def evaluate(output, *, infer_bin='infer', live=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for repo in sorted(path for path in CASES.iterdir() if path.is_dir()):
        expected = json.loads((repo / 'expected.json').read_text())
        contracts = json.loads((repo / 'contracts.json').read_text())
        baseline = subprocess.run([sys.executable, 'tests/check.py'], cwd=repo, capture_output=True, text=True, timeout=30)
        save(output / (repo.name + '-baseline.json'), dict(command=[sys.executable, 'tests/check.py'],
             returncode=baseline.returncode, stdout=baseline.stdout, stderr=baseline.stderr,
             expected_exit=expected['expected_behavior']['before_exit']))
        for mode, options in MODES.items():
            if mode == 'E_full_deepseek' and not live:
                rows.append(dict(case=repo.name, mode=mode, api_status='not_run', reason='explicit --live-deepseek required'))
                continue
            result = ReviewAgent().review(repo, target_files=expected['targets'], return_contracts=contracts,
                test_command=[sys.executable, 'tests/check.py'], infer_bin=infer_bin,
                output_dir=output / (repo.name + '-' + mode), **options)
            run = Path(result['output_dir'])
            context = json.loads((run / 'context.json').read_text())
            native = [item for item in result['infer'].get('findings', []) if not item['rule'].startswith('SYMPAS_')]
            matching_rule = [item for item in result['findings'] if item['callee'] == expected['expected_review']['callee']]
            matching_native = [item for item in native if item['rule'] == expected['expected_infer']['native_bug_kind']]
            slices = [item for item in result['slices'] if item.get('procedure') == expected['expected_slice']['procedure']]
            hit = any(item['file'] == expected['expected_context']['file'] and item['procedure'] == expected['expected_context']['procedure']
                      for query in result['retrieval'] for item in query['items'])
            refs = result['validation']['evidence']
            llm_ran = result['llm']['provider'] != 'none'
            row = dict(case=repo.name, mode=mode, detected=bool(matching_rule or matching_native),
                native_expected_finding_found=bool(matching_native), rule_expected_finding_found=bool(matching_rule),
                expected_slice_found=bool(slices) and any(snapshot.get('instruction', {}).get('callee') == expected['expected_slice']['required_callee']
                    for item in slices for snapshot in item.get('call_sites', [])) if options.get('use_slices', True) else None,
                key_context_found=hit if options['retrieval'] != 'off' else None,
                key_evidence_in_prompt=any(item['kind'] == 'DRACO_CONTEXT' and item['data'].get('procedure') == expected['expected_context']['procedure'] for item in context['evidence']) if options['retrieval'] != 'off' else None,
                evidence_refs_valid=refs['status'] == 'verified' if llm_ran else None,
                llm_parse_success=result['llm']['parse_status'] == 'ok' if llm_ran else None,
                review_validation_passed=result['validation']['status'] != 'validation_failed',
                candidate_validation_passed=all(item['status'] != 'validation_failed' for item in result['repairs']) if result['repairs'] else None,
                validation_passed=result['validation']['status'] != 'validation_failed' and all(item['status'] != 'validation_failed' for item in result['repairs']),
                validation_status=result['validation']['status'], model_conclusion=result['model_review'].get('status') if result['model_review'] else None,
                slice_status=result['slice_status'], api_status=result['llm']['status'] if options['llm_provider'] == 'deepseek' else 'not_run',
                token_usage=result['llm'].get('usage'), elapsed_ms=result['telemetry']['elapsed_ms'],
                baseline_behavior_failed_as_expected=baseline.returncode == expected['expected_behavior']['before_exit'],
                candidate_statuses=[item['status'] for item in result['repairs']],
                candidate_origins=[item.get('origin') for item in result['repairs']],
                candidate_behavior_pass=[item.get('tests_after', {}).get('status') == 'passed' for item in result['repairs']],
                artifacts_complete=all((run / name).is_file() for name in REQUIRED_ARTIFACTS), run_dir=str(run))
            rows.append(row)
            print(json.dumps(dict(case=repo.name, mode=mode, detected=row['detected'], refs=row['evidence_refs_valid'],
                                  candidate=row['candidate_statuses'], api=row['api_status'])), flush=True)
    result = dict(scope='small-scale prototype evaluation', source_provenance='3 constructed realistic fixtures; not production defects',
                  modes=MODES, rows=rows,
                  limitations=['Only three constructed scenarios with manual contracts and independent behavior oracles.',
                               'A disables SymPas and local rules; B-E enable native Infer plus SymPas and identical local rules.',
                               'A vs B is not an isolated slicing-effect experiment because B also consumes local contracts.',
                               'Candidate checks are bounded, even when runtime oracles pass.'])
    save(output / 'evaluation.json', result)
    lines = ['# Small-scale prototype evaluation', '', result['source_provenance'], '',
             '| Case | Mode | Detected | Slice | Context | Ref valid | JSON | API | Candidate |', '|---|---|---|---|---|---|---|---|---|']
    for row in rows:
        lines.append('| ' + ' | '.join(str(row.get(key, 'not_run')) for key in ('case','mode','detected','slice_status','key_context_found','evidence_refs_valid','llm_parse_success','api_status','candidate_statuses')) + ' |')
    lines += ['', *result['limitations']]
    (output / 'evaluation.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(output=str(output), runs=sum('run_dir' in row for row in rows))), flush=True)
    return result


def revalidate_saved(evaluation_dir, output, infer_bin='infer'):
    """Recheck saved model patches without another API call; preserve original runs."""
    evaluation_dir, output = Path(evaluation_dir).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipts = []
    for repo in sorted(path for path in CASES.iterdir() if path.is_dir()):
        source = evaluation_dir / (repo.name + '-E_full_deepseek') / 'run.json'
        run = json.loads(source.read_text())
        patch = run.get('model_review', {}).get('candidate_fix', {}).get('patch')
        if not patch:
            receipts.append(dict(case=repo.name, status='not_verified', reason='model_patch_not_available', source_run=str(source)))
            continue
        if run['llm']['status'] != 'ok' or run['validation']['evidence']['status'] != 'verified':
            receipts.append(dict(case=repo.name, status='validation_failed', reason='original_response_or_evidence_not_valid'))
            continue
        expected = json.loads((repo / 'expected.json').read_text())
        result = validate_candidate(repo, patch, output / repo.name, target_files=expected['targets'],
            finding_id=run['findings'][0]['finding_id'], origin='llm', infer_profile='combined',
            infer_before=run['infer'], infer_candidates=run['infer'].get('return_contract_candidates', []),
            return_contracts=json.loads((repo / 'contracts.json').read_text()), infer_bin=infer_bin,
            test_command=[sys.executable, 'tests/check.py'])
        receipts.append(dict(case=repo.name, status=result['status'], reason=result.get('reason'),
                             source_run=str(source), validation_file=str(output / repo.name / 'validation.json')))
    save(output / 'revalidation.json', dict(api_status='not_run_saved_response_reuse', source_evaluation=str(evaluation_dir), receipts=receipts))
    print(json.dumps(dict(output=str(output), receipts=receipts), indent=2))
    return receipts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--infer-bin', default=os.getenv('INFER_BIN', 'infer'))
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/realistic-evaluation' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    parser.add_argument('--live-deepseek', action='store_true')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--revalidate', type=Path, help='Reuse saved E responses; no API call')
    args = parser.parse_args()
    if args.live_deepseek and args.env_file:
        load_env_file(args.env_file)
    if args.revalidate:
        revalidate_saved(args.revalidate, args.output, args.infer_bin)
    else:
        evaluate(args.output, infer_bin=args.infer_bin, live=args.live_deepseek)
