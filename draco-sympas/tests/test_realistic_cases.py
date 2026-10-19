"""Constructed realistic cases, bounded repair safety and failure reports."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).parents[1]))
from agent import ReviewAgent
from repair import propose_return_check
from repair_validation import source_patch, validate_candidate, check_patch
from review import review_source
from sympas_adapter import SymPasAdapter

CASES = Path(__file__).parents[1] / 'examples/realistic_case'
REQUIRED = ['infer.json', 'slice.json', 'retrieval.json', 'context.json', 'llm_response.json', 'validation.json', 'review.md']


@pytest.mark.parametrize('name', ['unchecked_return', 'error_propagation', 'cross_file'])
def test_realistic_unchecked_return(name, tmp_path):
    repo = CASES / name
    expected = json.loads((repo / 'expected.json').read_text())
    contracts = json.loads((repo / 'contracts.json').read_text())
    run = ReviewAgent().review(repo, infer_mode='off', llm_provider='mock', target_files=expected['targets'],
        return_contracts=contracts, test_command=[sys.executable, 'tests/check.py'], output_dir=tmp_path / 'run')
    assert len(run['findings']) == expected['expected_review']['count']
    assert run['findings'][0]['callee'] == expected['expected_review']['callee']
    assert run['findings'][0]['line'] == expected['expected_review']['line']
    repair = run['repairs'][0]
    assert repair['tests_before']['returncode'] == 1
    assert repair['tests_after']['returncode'] == 0
    assert repair['status'] == 'partially_verified'
    assert repair['after_findings'] == 0
    assert all((tmp_path / 'run' / name).is_file() for name in REQUIRED)
    assert run['evidence_refs']
    if name == 'cross_file':
        assert any(item['file'] == 'storage.c' for query in run['retrieval'] for item in query['items'])


def test_partial_and_complete_slice_compatibility():
    adapter = SymPasAdapter()
    for state in ('partial', 'complete'):
        raw = dict(kind='SYMPAS_SLICE', analysis_status=state, instruction_slices=[{'instruction': {'event': 'call', 'callee': 'f'}}])
        result = adapter.read({'slices': [raw]})
        assert adapter.status(result) == state
        assert result[0]['call_sites'] == raw['instruction_slices']
        assert raw['analysis_status'] == state


@pytest.mark.parametrize('failure', ['infer_failed', 'empty_slice', 'missing_context', 'budget', 'timeout', 'invalid_json', 'missing_key', 'unknown_ref'])
def test_failure_still_generates_full_agent_report(failure, tmp_path, monkeypatch):
    repo = CASES / 'unchecked_return'
    options = dict(infer_mode='off', llm_provider='mock', target_files=['job.c'])
    if failure == 'infer_failed':
        options.update(infer_mode='real', infer_bin='/missing/infer')
    if failure == 'empty_slice':
        options.update(infer_mode='real')
        monkeypatch.setattr('agent.run_infer', lambda *a, **k: dict(ok=False,status='empty_test_report', findings=[],slices=[]))
    if failure == 'missing_context':
        options['max_contexts'] = 0
    if failure == 'budget':
        options['token_budget'] = 20
    if failure in ('timeout', 'missing_key'):
        options['llm_provider'] = 'deepseek'
        if failure == 'timeout':
            monkeypatch.setattr('agent.invoke', lambda *a, **k: dict(provider='deepseek',status='api_error',error='TimeoutError',raw_response=None,usage=None))
        else:
            monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    if failure == 'invalid_json':
        monkeypatch.setattr('agent.invoke', lambda *a, **k: dict(provider='mock',status='ok',raw_response='{',usage=None))
    if failure == 'unknown_ref':
        from providers import mock_response
        model = mock_response([])
        model['evidence_refs'] = ['infer:invented']
        monkeypatch.setattr('agent.invoke', lambda *a, **k: dict(provider='mock',status='ok',raw_response=json.dumps(model),usage=None))
    run = ReviewAgent().review(repo, output_dir=tmp_path / 'run', **options)
    assert all((tmp_path / 'run' / name).is_file() for name in REQUIRED)
    assert 'Stage status' in (tmp_path / 'run/review.md').read_text()
    if failure == 'infer_failed': assert run['infer']['status'] == 'execution_failed'
    if failure == 'empty_slice': assert run['slice_status'] == 'not_analyzed'
    if failure == 'missing_context': assert run['stages']['retrieval'] == 'no_results'
    if failure == 'budget': assert run['stages']['context'] == 'budget_exceeded' and run['llm']['status'] == 'context_error'
    if failure == 'timeout': assert run['llm']['error'] == 'TimeoutError'
    if failure == 'missing_key': assert run['llm']['status'] == 'configuration_error'
    if failure == 'invalid_json': assert run['llm']['parse_status'] == 'parse_failed'
    if failure == 'unknown_ref': assert run['validation']['status'] == 'validation_failed'


def test_candidate_fix_revalidation_safety_and_behavior(tmp_path):
    repo = CASES / 'unchecked_return'
    source = (repo / 'job.c').read_text()
    finding = review_source(source)['findings'][0]
    candidate = propose_return_check(source, finding)
    patch = source_patch('job.c', source, candidate['source'])
    assert not check_patch(repo, patch, ['job.c'])
    assert check_patch(repo, patch.replace('return rc;', 'system("unsafe");'), ['job.c'])
    assert check_patch(repo, patch.replace('a/job.c', 'a/../escape.c'), ['job.c'])
    assert check_patch(repo, patch.replace('a/job.c', 'a/tests/driver.c'), ['job.c'])
    # A syntactically valid guard with incorrect error value fails the trusted oracle.
    bad_patch = patch.replace('return rc;', 'return 0;')
    bad = validate_candidate(repo, bad_patch, tmp_path / 'bad', target_files=['job.c'], finding_id='test',
                             run_static=False, test_command=[sys.executable, 'tests/check.py'])
    assert bad['status'] == 'validation_failed'
    assert bad['tests_after']['returncode'] != 0
    assert (repo / 'job.c').read_text() == source


def test_single_line_guard_patch_is_supported():
    repo = CASES / 'cross_file'
    source = (repo / 'service.c').read_text()
    fixed = source.replace('    accepted++;', '    if (rc < 0) { return rc; }\n    accepted++;')
    assert not check_patch(repo, source_patch('service.c', source, fixed), ['service.c','storage.c'])


@pytest.mark.skipif(not os.getenv('INFER_BIN'), reason='explicit INFER_BIN required')
def test_cross_file_review_with_real_infer(tmp_path):
    repo = CASES / 'cross_file'
    run = ReviewAgent().review(repo, target_files=['service.c','storage.c'], infer_profile='combined',
        llm_provider='mock', test_command=[sys.executable,'tests/check.py'], output_dir=tmp_path/'real')
    assert run['infer']['status'] == 'ok'
    assert run['slice_status'] in ('partial','complete')
    assert run['validation']['evidence']['status'] == 'verified'
    assert run['repairs'][0]['infer_after']['status'] == 'ok'
    assert run['repairs'][0]['tests_before']['returncode'] == 1
    assert run['repairs'][0]['tests_after']['returncode'] == 0


def test_context_budget_keeps_target_slice_and_key_callee():
    from context.builder import build_context
    rule = dict(file='caller.c', line=4, callee='flush_state')
    snapshot = dict(instruction=dict(file='caller.c',line=4,callee='flush_state',event='call',instruction='x' * 20000),
                    data_dependencies=['formal[0]'],source_locations=[])
    evidence = [dict(id='rule:1',kind='RULE_FACT',data=rule),
                dict(id='infer:1',kind='INFER_FACT',data={'kind':'DEAD_STORE','line':4}),
                dict(id='sympas:target',kind='SYMPAS_SLICE',data=dict(procedure='handle_request',call_sites=[snapshot])),
                dict(id='draco:callee',kind='DRACO_CONTEXT',data=dict(procedure='flush_state',code='int flush_state(int x) { return x; }'))]
    context = build_context(evidence, token_budget=5000)
    assert {item['kind'] for item in context['evidence']} == {'RULE_FACT','INFER_FACT','SYMPAS_SLICE','DRACO_CONTEXT'}
    assert context['token_upper_bound'] <= 5000
    assert snapshot['instruction']['instruction'] == 'x' * 20000


def test_unapplicable_model_patch_is_not_repaired_silently(tmp_path):
    repo = CASES / 'cross_file'
    patch = '--- a/service.c\n+++ b/service.c\n@@ -1,1 +1,2 @@\n this line does not exist\n+    if (rc < 0) { return rc; }\n'
    result = validate_candidate(repo, patch, tmp_path/'bad-hunk', target_files=['service.c','storage.c'], finding_id='test', run_static=False)
    assert result['status'] == 'validation_failed'
    assert result['reason'] == ['patch_does_not_apply']
