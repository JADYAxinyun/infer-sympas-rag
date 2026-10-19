"""Offline safety boundaries and one opt-in real Infer integration."""
import io
import json
import os
from pathlib import Path
import sys
import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from agent import ReviewAgent, markdown
from context.builder import build_context
from context.repository import index_repository, retrieve
from infer_runner import run_infer
from providers import invoke, mock_response
from validation import parse_review, validate_evidence


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    (root / 'helper.c').write_text('int open_config(const char *p) {\n if (!p) return -1;\n return 0;\n}\n')
    (root / 'main.c').write_text('int open_config(const char *);\nint run(void) {\n int ret = open_config("x");\n return ret;\n}\n')
    return root


def test_relation_paths_across_files(repo):
    index = index_repository(repo)
    assert not index['diagnostics']
    edges = [edge for edge in index['edges'] if edge['relation'] == 'CALLS']
    assert edges[0]['symbol'] == 'open_config'
    result = retrieve(index, file='main.c', line=3, token_budget=10000)
    helper = next(item for item in result['items'] if item['file'] == 'helper.c')
    assert helper['distance'] == 1
    assert 'CALLS' in helper['retrieval_path']
    assert retrieve(index, file='missing', line=1)['status'] == 'no_results'
    assert not retrieve(index, file='main.c', line=3, token_budget=1)['items']
    assert retrieve(index, mode='off')['status'] == 'disabled'


def test_python_all_relation_types(tmp_path):
    (tmp_path / 'sample.py').write_text('class Base: pass\nclass Child(Base):\n def run(self, x: int):\n  import math as m\n  y: int = x\n  return target(y)\ndef target(v): return v\n')
    result = index_repository(tmp_path)
    assert {'ASSIGNS', 'REFERS', 'TYPEOF', 'INHERITS', 'AS', 'CALLS'} <= {edge['relation'] for edge in result['edges']}
    assert result['status'] == 'partial'


def test_budget_dedup_hash_and_diff():
    records = [dict(id='draco:a', kind='DRACO_CONTEXT', data={'code': 'same'}),
               dict(id='draco:b', kind='DRACO_CONTEXT', data={'code': 'same'}),
               dict(id='rule:c', kind='RULE_FACT', data={'line': 1})]
    result = build_context(records, diff='汉字"\\' * 1000, token_budget=2000)
    assert result['token_upper_bound'] <= 2000
    assert result['diff_truncated']
    assert result['evidence'][0]['kind'] == 'RULE_FACT'
    assert any(item['reason'] == 'duplicate' for item in result['dropped'])
    assert build_context(records, diff='汉字"\\' * 1000, token_budget=2000)['context_hash'] == result['context_hash']
    with pytest.raises(ValueError):
        build_context([], token_budget=10)


@pytest.mark.parametrize('value', ['no-json', '[]', '{}', '{"status": []}', '{"confidence": true}'])
def test_rejects_invalid_json_schema(value):
    _, errors = parse_review(value)
    assert errors


def test_unknown_ref_and_locations(repo):
    value = mock_response([dict(id='infer:fake', kind='INFER_FACT')])
    assert not parse_review(json.dumps(value))[1]
    assert validate_evidence(value, [], repo)['status'] == 'validation_failed'
    registry = [dict(id='infer:fake', kind='INFER_FACT', provenance='mock', data=dict(file='main.c', line=999))]
    result = validate_evidence(value, registry, repo)
    assert 'non_real_infer:infer:fake' in result['errors']
    assert 'invalid_line:infer:fake' in result['errors']
    registry[0]['data']['file'] = '../outside.c'
    assert 'invalid_file:infer:fake' in validate_evidence(value, registry, repo)['errors']


def test_providers_never_require_key_offline(monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('unexpected network'))
    context = build_context([])
    assert invoke('none', context)['status'] == 'not_run'
    assert invoke('mock', context)['status'] == 'ok'
    assert invoke('deepseek', context)['status'] == 'configuration_error'


def test_deepseek_request_timeout_retries_and_raw_response(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'unit-test-secret')
    monkeypatch.setenv('DEEPSEEK_MODEL', 'test-model')
    context = build_context([])
    calls = []
    text = json.dumps(mock_response([]))
    envelope = json.dumps({'choices': [{'message': {'content': text}}], 'usage': {'prompt_tokens': 4}})

    def open_request(request, timeout):
        calls.append(request)
        assert timeout == 7
        assert request.get_header('Authorization') == 'Bearer unit-test-secret'
        assert json.loads(request.data)['model'] == 'test-model'
        assert json.loads(request.data)['response_format'] == {'type': 'json_object'}
        if len(calls) == 1:
            raise urllib.error.HTTPError(request.full_url, 429, 'rate limited', {}, None)
        return io.BytesIO(envelope.encode())

    monkeypatch.setattr('urllib.request.urlopen', open_request)
    monkeypatch.setattr('providers.time.sleep', lambda seconds: None)
    result = invoke('deepseek', context, timeout=7, retries=1)
    assert result['attempts'] == 2
    assert result['raw_response'] == text
    assert result['raw_envelope'] == envelope
    assert result['usage']['prompt_tokens'] == 4
    assert 'unit-test-secret' not in json.dumps(result)


def test_auth_failure_is_not_retried(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'unit-test-secret')
    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, 'denied', {}, None)
    monkeypatch.setattr('urllib.request.urlopen', fail)
    result = invoke('deepseek', build_context([]))
    assert result['status'] == 'api_error'
    assert result['attempts'] == 1


def test_infer_never_reads_stale_report(tmp_path):
    (tmp_path / 'report.json').write_text('[]')
    result = run_infer(tmp_path, ['true'], results_dir=tmp_path)
    assert result['status'] == 'results_exist'
    assert result['findings'] == []


def test_mock_pipeline_preserves_sources(repo, tmp_path, monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    before = (repo / 'main.c').read_bytes()
    result = ReviewAgent().review(repo, target_files=['main.c'], infer_mode='mock', llm_provider='mock', output_dir=tmp_path / 'run')
    assert result['infer']['status'] == 'mock'
    assert not result['slices']
    assert result['slice_status'] == 'not_analyzed'
    assert len(result['findings']) == 1
    assert result['validation']['status'] == 'partially_verified'
    assert (repo / 'main.c').read_bytes() == before
    assert result['repairs'][0]['status'] == 'partially_verified'
    assert (tmp_path / 'run' / 'prompt.json').is_file()
    assert 'Mock' in markdown(result)
    assert json.loads((tmp_path / 'run' / 'run.json').read_text())['run_id'] == result['run_id']
    with pytest.raises(FileExistsError):
        ReviewAgent().review(repo, output_dir=tmp_path / 'run')


@pytest.mark.skipif(not os.getenv('INFER_BIN'), reason='explicit INFER_BIN required')
def test_real_infer_mock_integration(repo, tmp_path):
    result = ReviewAgent().review(repo, target_files=['main.c', 'helper.c'], llm_provider='mock', output_dir=tmp_path / 'real')
    assert result['infer']['ok']
    assert result['slices']
    assert all(item['status'] == 'partial' for item in result['slices'])
    assert result['infer']['raw_report']
    assert result['validation']['evidence']['status'] == 'verified'
    assert len(result['findings']) == 1
    assert result['repairs'][0]['infer_after']['status'] == 'ok'


def test_provider_timeout_and_malformed_envelope(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'unit-test-secret')
    monkeypatch.setattr('providers.time.sleep', lambda seconds: None)
    def timeout(*args, **kwargs):
        raise TimeoutError('request secret must not appear in errors')
    monkeypatch.setattr('urllib.request.urlopen', timeout)
    result = invoke('deepseek', build_context([]), retries=1)
    assert result['status'] == 'api_error' and result['attempts'] == 2
    assert result['error'] == 'TimeoutError'
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: io.BytesIO(b'{"no_choices": true}'))
    result = invoke('deepseek', build_context([]))
    assert result['status'] == 'response_parse_failed'
    assert result['raw_envelope'] == '{"no_choices": true}'


def test_none_pipeline_and_cli_export(repo, tmp_path, monkeypatch):
    result = ReviewAgent().review(repo, target_files=['main.c'], llm_provider='none', infer_mode='off', output_dir=tmp_path / 'none')
    assert result['llm']['status'] == 'not_run'
    assert result['model_review'] is None
    assert result['validation']['status'] == 'not_verified'
    import cli
    destination = tmp_path / 'export.md'
    monkeypatch.setattr(sys, 'argv', ['cli', 'report', '--input', str(tmp_path / 'none/run.json'), '--output', str(destination)])
    assert cli.main() == 0
    assert destination.read_text() == markdown(result)


def test_fail_closed_invented_model_reference(repo, tmp_path, monkeypatch):
    model = mock_response([])
    model.update(status='confirmed', evidence_refs=['infer:not-real'], confidence=1)
    monkeypatch.setattr('agent.invoke', lambda *a, **k: dict(provider='mock', status='ok', raw_response=json.dumps(model), usage=None))
    result = ReviewAgent().review(repo, target_files=['main.c'], infer_mode='off', llm_provider='mock', output_dir=tmp_path / 'invented')
    assert result['validation']['status'] == 'validation_failed'
    assert len(result['findings']) == 1
    assert result['validation']['evidence']['errors'] == ['unknown_evidence:infer:not-real']


def test_clang_absent_is_explicit(repo, monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError('clang')
    monkeypatch.setattr('context.repository.subprocess.run', missing)
    result = index_repository(repo)
    assert not result['nodes']
    assert all(item['status'] == 'unsupported' for item in result['diagnostics'])


def test_missing_fix_field_rejected():
    model = mock_response([])
    del model['candidate_fix']['patch']
    assert 'invalid_candidate_fix' in parse_review(json.dumps(model))[1]


def test_failed_infer_does_not_consume_existing_issue(tmp_path, monkeypatch):
    from types import SimpleNamespace
    def fail(command, **kwargs):
        (tmp_path / 'report.json').write_text('[{"bug_type":"DEAD_STORE"}]')
        return SimpleNamespace(returncode=7, stdout='capture failed', stderr='compile error')
    monkeypatch.setattr('infer_runner.subprocess.run', fail)
    result = run_infer(tmp_path, ['clang'], results_dir=tmp_path)
    assert result['status'] == 'execution_failed'
    assert result['findings'] == []
    assert result['commands'][0]['returncode'] == 7


def test_checked_code_still_retrieves_callee(repo, tmp_path):
    path = repo / 'main.c'
    path.write_text(path.read_text().replace(' return ret;', ' if (ret < 0) return ret;\n return ret;'))
    result = ReviewAgent().review(repo, target_files=['main.c'], llm_provider='mock', infer_mode='off', output_dir=tmp_path / 'checked')
    assert not result['findings']
    trace = json.loads((tmp_path / 'checked/retrieval.json').read_text())
    assert any(item['file'] == 'helper.c' for query in trace for item in query['items'])
    assert result['model_review']['status'] == 'evidence_insufficient'
