"""Evidence origin, source integrity and partial-slice compatibility regressions."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).parents[1]))
from agent import ReviewAgent, markdown
from context.builder import build_context
from context.repository import index_repository
from provider_config import load_env_file
from providers import mock_response
from sympas_adapter import SymPasAdapter
from validation import validate_evidence


@pytest.fixture
def source_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'a.c').write_text('int f(int x) {\n return x;\n}\n')
    return repo


@pytest.mark.parametrize('status', ['partial', 'unsupported', 'failed', 'not_analyzed'])
def test_partial_slice_compatibility(status):
    raw = dict(kind='SYMPAS_SLICE', status=status, procedure='f',
               criterion=dict(location=dict(file='a.c', line=2)), data_dependencies=['formal[0]'])
    original = deepcopy(raw)
    adapter = SymPasAdapter()
    result = adapter.read({'slices': [raw]})
    assert result[0]['status'] == status
    assert adapter.status(result) == status
    assert result[0]['raw_slice'] == raw == original
    assert result[0]['dependencies']['data'] == ['formal[0]']
    assert adapter.adapt({'status': 'new_unknown_status'})['status'] == 'not_analyzed'


def test_evidence_references_match_original_artifacts(source_repo, tmp_path):
    index = index_repository(source_repo)
    raw = dict(kind='SYMPAS_SLICE', procedure='f', analysis_status='partial',
               criterion=dict(location=dict(file='a.c', line=2)), source_locations=[dict(file='a.c', line=2)], data_dependencies=['formal[0]'])
    issue = dict(bug_type='SYMPAS_SLICE', qualifier='sympas_json=' + json.dumps(raw), file='a.c', line=2)
    artifacts = {}
    for name, data in [('index', index), ('infer_report', [issue]), ('rules', []), ('retrieval', [])]:
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(data))
        artifacts[name] = path
    evidence = [dict(id='sympas:slice-001', kind='SYMPAS_SLICE', provenance='real_infer', data=SymPasAdapter().adapt(raw))]
    model = mock_response(evidence)
    assert validate_evidence(model, evidence, source_repo, artifacts=artifacts)['status'] == 'verified'
    forged = deepcopy(evidence)
    forged[0]['data']['data_dependencies'] = ['fabricated']
    assert 'artifact_mismatch:sympas:slice-001' in validate_evidence(model, forged, source_repo, artifacts=artifacts)['errors']
    (source_repo / 'a.c').write_text('int f(int x) {\n return 0;\n}\n')
    assert 'source_changed_or_unindexed:sympas:slice-001' in validate_evidence(model, evidence, source_repo, artifacts=artifacts)['errors']


def test_context_only_cannot_confirm_bug(source_repo, tmp_path):
    run = ReviewAgent().review(source_repo, infer_mode='off', llm_provider='mock', output_dir=tmp_path / 'run')
    model = deepcopy(run['model_review'])
    assert model['status'] == 'evidence_insufficient'
    model['status'] = 'confirmed'
    artifacts = dict(index=tmp_path / 'run/index.json', retrieval=tmp_path / 'run/retrieval.json', rules=tmp_path / 'run/rules.json')
    result = validate_evidence(model, run['evidence'], source_repo, artifacts=artifacts)
    assert result['errors'] == ['evidence_insufficient_required']
    model.update(status='not_a_bug', evidence_refs=[])
    assert 'evidence_insufficient_required' in validate_evidence(model, [], source_repo, artifacts=artifacts)['errors']


@pytest.mark.parametrize('kind', ['INFER_FACT', 'DRACO_CONTEXT', 'RULE_FACT'])
def test_existing_id_is_not_enough_to_prove_origin(kind, source_repo, tmp_path):
    evidence = [dict(id='known:1', kind=kind, provenance='real_infer', data=dict(file='a.c', line=2))]
    model = mock_response(evidence)
    result = validate_evidence(model, evidence, source_repo, artifacts={})
    assert 'artifact_mismatch:known:1' in result['errors']


def test_agent_partial_mock_e2e(source_repo, tmp_path, monkeypatch):
    raw = dict(kind='SYMPAS_SLICE', status='partial', procedure='f',
               criterion=dict(location=dict(file='a.c', line=2)), source_locations=[dict(file='a.c', line=2)], data_dependencies=['formal[0]'])
    report = tmp_path / 'report.json'
    report.write_text(json.dumps([dict(bug_type='SYMPAS_SLICE', qualifier='sympas_json=' + json.dumps(raw), file='a.c', line=2)]))
    monkeypatch.setattr('agent.run_infer', lambda *a, **k: dict(ok=True, status='ok', report=str(report), raw_report=json.loads(report.read_text()),
                                                             findings=[], slices=[raw], return_contract_candidates=[]))
    run = ReviewAgent().review(source_repo, llm_provider='mock', output_dir=tmp_path / 'partial')
    assert run['slice_status'] == 'partial'
    assert run['validation']['evidence']['status'] == 'verified'
    assert run['model_review']['status'] == 'evidence_insufficient'
    assert 'slice_status: `partial`' in markdown(run)
    assert 'sympas:slice-001' in markdown(run)
    assert 'DRaCo context' in markdown(run)
    assert (tmp_path / 'partial/slices.json').is_file()


def test_deepseek_config_file_is_explicit_and_does_not_execute(tmp_path, monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('DEEPSEEK_MODEL', raising=False)
    path = tmp_path / '.env'
    path.write_text('DEEPSEEK_API_KEY="offline-placeholder"\nDEEPSEEK_MODEL=deepseek-flash\n')
    assert load_env_file(path) == ['DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL']
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'environment-wins')
    assert 'DEEPSEEK_API_KEY' not in load_env_file(path)
    path.write_text('OTHER_SECRET=do-not-display-this-value\n')
    with pytest.raises(ValueError) as caught:
        load_env_file(path)
    assert 'do-not-display' not in str(caught.value)


def test_deepseek_response_parse_status_is_explicit(source_repo, tmp_path, monkeypatch):
    monkeypatch.setattr('agent.invoke', lambda *a, **k: dict(provider='deepseek', status='ok', raw_response='invalid JSON', usage=None))
    run = ReviewAgent().review(source_repo, infer_mode='off', llm_provider='deepseek', output_dir=tmp_path / 'invalid-json')
    assert run['llm']['parse_status'] == 'parse_failed'
    assert run['validation']['status'] == 'validation_failed'
    assert run['llm']['raw_response'] == 'invalid JSON'
