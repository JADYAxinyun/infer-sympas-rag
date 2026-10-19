"""Incremental orchestrator over the existing Infer, rule, local LLM and repair modules."""
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from context.builder import build_context
from context.repository import index_repository, retrieve
from infer_runner import run_infer
from providers import invoke
from repair import propose_return_check
from repair_validation import source_patch, validate_candidate
from review import review_source
from validation import parse_review, validate_evidence
from sympas_adapter import SymPasAdapter


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def markdown(result):
    lines = ['# Evidence-enhanced code review', '',
             'Research MVP; partial/conservative slicing is not a complete SymPas reproduction.', '',
             f"- Run: `{result['run_id']}`", f"- Infer: `{result['infer']['status']}`",
             f"- slice_status: `{result.get('slice_status', 'not_analyzed')}`",
             f"- provider: `{result['llm']['provider']}`", f"- model: `{result['llm'].get('model')}`",
             f"- LLM: `{result['llm']['provider']}/{result['llm']['status']}`",
             f"- JSON parse: `{result['llm'].get('parse_status', 'unknown')}`",
             f"- Local findings: {len(result['findings'])}",
             f"- Validation: `{result['validation']['status']}`",
             f"- Candidate validation: `{result.get('candidate_validation_status', 'not_verified')}`", '',
             '| File | Line | Rule | Contract source |', '|---|---:|---|---|']
    for finding in result['findings']:
        lines.append(f"| {finding['file']} | {finding['line']} | {finding['rule']} | {finding.get('contract', {}).get('source', 'unknown')} |")
    lines += ['', '## Stage status and failure reasons', '', '```json',
              json.dumps(dict(stages=result.get('stages', {}), notes=result.get('stage_notes', {})), ensure_ascii=False, indent=2), '```']
    for title, kind in [('Infer findings', 'INFER_FACT'), ('SymPas slices', 'SYMPAS_SLICE'), ('DRaCo context', 'DRACO_CONTEXT')]:
        lines += ['', '## ' + title, '', '| Evidence ID | Source | Detail |', '|---|---|---|']
        entries = [item for item in result.get('evidence', []) if item['kind'] == kind]
        if not entries:
            lines.append('| — | — | not_analyzed / no_results |')
        for item in entries:
            data = item['data']
            location = data.get('criterion', {}).get('location', {}) if kind == 'SYMPAS_SLICE' else data
            source = str(location.get('file', 'unknown')) + ':' + str(location.get('line', '?'))
            detail = data.get('status', data.get('kind', data.get('relation', 'context')))
            if kind == 'DRACO_CONTEXT':
                detail += '; ' + data.get('relevance_reason', '')
            lines.append(f"| `{item['id']}` | {source} | {detail} |")
    lines += ['', '## Model conclusion and evidence_refs', '', '```json',
              json.dumps(result.get('model_review'), ensure_ascii=False, indent=2), '```',
              '', '## Evidence validation', '', '```json',
              json.dumps(result['validation'], ensure_ascii=False, indent=2), '```',
              '', '## Candidate validation', '']
    for repair in result['repairs']:
        lines.append(f"- {repair['finding_id']}: `{repair['status']}`; Infer recheck: `{repair.get('infer_after', {}).get('status', 'not_run')}`. Candidate only; see bounded behavior/static receipts; not applied to the input repository.")
        if repair.get('reason'):
            lines.append('  - Reason: ' + str(repair['reason']))
    lines += ['', 'Full receipts: [run.json](run.json), [evidence.json](evidence.json), [slices.json](slices.json), [retrieval.json](retrieval.json).',
              '', '## Limits', ''] + ['- ' + item for item in result['limitations']]
    return '\n'.join(lines) + '\n'


class ReviewAgent:
    def review(self, repo_path, diff=None, target_files=None, rule='unchecked_return_value', llm_provider='none',
               *, output_dir=None, infer_mode='real', infer_bin=None, model=None, retrieval='relations',
               token_budget=16000, max_contexts=8, return_contracts=None, test_command=None,
               use_slices=True, run_rules=True, infer_profile='sympas'):
        if rule != 'unchecked_return_value':
            raise ValueError('Only existing unchecked_return_value rule is supported')
        if infer_mode not in ('real', 'mock', 'off') or retrieval not in ('relations', 'text', 'off'):
            raise ValueError('unsupported analysis mode')
        if infer_profile not in ('sympas', 'native', 'combined'):
            raise ValueError('unsupported infer_profile')
        started = time.perf_counter()
        repo = Path(repo_path).resolve()
        if not repo.is_dir():
            raise ValueError('repo_path must be a directory')
        if token_budget <= 0 or max_contexts < 0:
            raise ValueError('token_budget must be positive and max_contexts nonnegative')
        if test_command is not None and (not isinstance(test_command, list) or not test_command or any(not isinstance(arg, str) for arg in test_command)):
            raise ValueError('test_command must be an explicit argv list')
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        out = Path(output_dir or Path(__file__).parent / 'artifacts' / 'agent' / run_id).resolve()
        out.mkdir(parents=True, exist_ok=False)
        index = index_repository(repo)
        save(out / 'index.json', index)
        if diff is None:
            completed = subprocess.run(['git', '-C', str(repo), 'diff', 'HEAD', '--', '.'], capture_output=True, text=True)
            diff = completed.stdout if completed.returncode == 0 else ''
            diff_status = 'ok' if completed.returncode == 0 else 'unavailable'
        else:
            diff_status = 'provided'
        # Explicit target files take precedence. Otherwise review the indexed repository;
        # diff supplies context, not an implicit added-lines-only semantic filter.
        targets = list(target_files or sorted(index['file_hashes']))
        paths = []
        for file in targets:
            path = (repo / file).resolve()
            if not path.is_relative_to(repo) or not path.is_file():
                raise ValueError('target must exist inside repo: ' + str(file))
            paths.append(path)
        c_files = [path for path in paths if path.suffix in ('.c', '.cc', '.cpp')]
        infer_bin = infer_bin or os.environ.get('INFER_BIN', 'infer')
        if infer_mode == 'real' and c_files:
            infer = run_infer(repo, ['clang', '-c'] + [str(path) for path in c_files], infer_bin,
                              out / 'infer', sympas_only=infer_profile == 'sympas',
                              checker_args=['--sympas'] if infer_profile == 'combined' else ['--no-sympas'] if infer_profile == 'native' else None)
        else:
            infer = dict(status='mock' if infer_mode == 'mock' else 'not_analyzed' if not c_files else 'not_run',
                         ok=False, findings=[], slices=[], return_contract_candidates=[], commands=[])
        evidence, findings, sources = [], [], {}
        raw_report = infer.get('raw_report', [])
        raw_issues = raw_report if isinstance(raw_report, list) else raw_report.get('issues', [])
        for number, finding in enumerate(infer.get('findings', []), 1):
            raw = raw_issues[number - 1]
            # Slices and contract candidates are analyzer facts, never bug verdicts.
            fact = dict(finding, finding_id=f'finding-{number:03d}', tool='infer', kind=finding['rule'],
                        procedure=raw.get('procedure'), evidence=dict(source_location=f"{finding.get('file')}:{finding.get('line')}", raw_report=raw))
            evidence.append(dict(id='infer:' + fact['finding_id'], kind='INFER_FACT', provenance='real_infer', data=fact))
        slice_adapter = SymPasAdapter()
        slice_results = slice_adapter.read(infer) if use_slices else []
        for data in slice_results:
            evidence.append(dict(id='sympas:' + data['slice_id'], kind='SYMPAS_SLICE', provenance='real_infer', data=data))
        for path in paths:
            file = path.relative_to(repo).as_posix()
            source = path.read_text(errors='replace')
            sources[file] = source
            reviewed = review_source(source, return_contracts=return_contracts,
                                     infer_candidates=infer.get('return_contract_candidates', []))
            for item in reviewed['findings'] if run_rules else []:
                finding = dict(item, file=file, finding_id=f'rule-{len(findings) + 1:03d}')
                findings.append(finding)
                evidence.append(dict(id='rule:' + finding['finding_id'], kind='RULE_FACT', provenance='local_rule', data=finding))
        contexts = []
        context_ids = set()
        target_names = {path.relative_to(repo).as_posix() for path in paths}
        queries = findings or [dict(file=node['file'], line=node['line'], procedure=node['procedure'])
                               for node in index['nodes'] if node['file'] in target_names]
        if not queries:
            queries = [dict(file=file, line=1) for file in sorted(target_names)]
        for query in queries:
            context = retrieve(index, file=query['file'], procedure=query.get('procedure'), line=query.get('line'), finding=query,
                               slices=infer.get('slices', []), diff=diff, max_items=max_contexts,
                               token_budget=token_budget // 2, mode=retrieval)
            context['query'] = dict(query)
            contexts.append(context)
            for item in context['items']:
                identity = hashlib.sha256(item['id'].encode()).hexdigest()[:16]
                if identity not in context_ids and len(context_ids) < max_contexts:
                    context_ids.add(identity)
                    evidence.append(dict(id='draco:' + identity, kind='DRACO_CONTEXT', provenance='repository_ast', data=item))
        try:
            context = build_context(evidence, diff, token_budget)
            context['status'] = 'ok'
        except ValueError as error:
            context = dict(status='budget_exceeded', reason=str(error), messages=[], evidence=[], dropped=[],
                           context_hash=hashlib.sha256(b'').hexdigest(), token_upper_bound=0, token_budget=token_budget)
        save(out / 'rules.json', findings)
        save(out / 'slices.json', slice_results)
        save(out / 'slice.json', dict(status=slice_adapter.status(slice_results), slices=slice_results))
        save(out / 'infer.json', infer)
        save(out / 'evidence.json', evidence)
        save(out / 'context.json', context)
        save(out / 'retrieval.json', contexts)
        (out / 'prompt.json').write_text(json.dumps(context['messages'], ensure_ascii=False, indent=2))
        llm = invoke(llm_provider, context, model=model) if context['status'] == 'ok' else dict(provider=llm_provider, status='context_error', error=context['reason'], raw_response=None, usage=None)
        model_review, errors = parse_review(llm['raw_response']) if llm['status'] == 'ok' else (None, [])
        llm['parse_status'] = 'not_run' if llm['status'] != 'ok' else 'parse_failed' if errors else 'ok'
        registry = {item['id']: item for item in evidence}
        prompt_evidence = [registry[item['id']] for item in context['evidence']]
        source_artifacts = dict(infer_report=infer.get('report'), index=out / 'index.json',
                                retrieval=out / 'retrieval.json', rules=out / 'rules.json')
        reference_validation = validate_evidence(model_review, prompt_evidence, repo, artifacts=source_artifacts) if model_review and not errors else dict(status='not_verified', errors=[])
        validation = dict(status='validation_failed' if errors or reference_validation['errors'] else
                          'partially_verified' if model_review else 'not_verified', schema_errors=errors,
                          evidence=reference_validation, rule='unchecked_return_value',
                          note='Local rule findings remain independent of model status; evidence checks do not prove semantics.')
        repairs = []
        model_patch = model_review.get('candidate_fix', {}).get('patch') if model_review and not errors and reference_validation['status'] == 'verified' else None
        for finding in findings:
            candidate = propose_return_check(sources[finding['file']], finding) if finding['file'].endswith('.c') else None
            patch = model_patch if model_patch else source_patch(finding['file'], sources[finding['file']], candidate['source']) if candidate else None
            if not patch:
                repairs.append(dict(finding_id=finding['finding_id'], status='not_verified', reason='no_supported_candidate'))
                continue
            repair_result = validate_candidate(repo, patch, out / ('repair-' + finding['finding_id']),
                target_files=[path.relative_to(repo).as_posix() for path in paths], finding_id=finding['finding_id'],
                origin='llm' if model_patch else 'local_rule', return_contracts=return_contracts,
                infer_candidates=infer.get('return_contract_candidates', []), infer_bin=infer_bin,
                run_static=infer_mode == 'real' and bool(infer.get('ok')), test_command=test_command,
                infer_before=infer, infer_profile=infer_profile)
            repairs.append(repair_result)
            model_patch = None
        candidate_status = 'validation_failed' if any(item['status'] == 'validation_failed' for item in repairs) else 'partially_verified' if repairs and all(item['status'] == 'partially_verified' for item in repairs) else 'not_verified'
        result = dict(run_id=run_id, repo=str(repo), output_dir=str(out), findings=findings, infer=infer,
                      slices=[entry['data'] for entry in evidence if entry['kind'] == 'SYMPAS_SLICE'],
                      slice_status=slice_adapter.status(slice_results), index_status=index['status'],
                      evidence_refs=model_review.get('evidence_refs', []) if model_review else [],
                      evidence=evidence, retrieval=contexts,
                      stage_notes=dict(infer_error=infer.get('stderr') if not infer.get('ok') else None,
                                       slice_errors=infer.get('slice_errors', []),
                                       slice_reason=None if slice_results else 'disabled_by_profile' if not use_slices else 'no_structured_slices',
                                       context_dropped=context.get('dropped', []),
                                       context_error=context.get('reason'), llm_error=llm.get('error')),
                      diff_status=diff_status, review_scope='explicit targets or all indexed files; diff is context',
                      provider=llm['provider'], model=llm.get('model'), validation_status=validation['status'],
                      candidate_validation_status=candidate_status,
                      stages=dict(infer=infer['status'], slice=slice_adapter.status(slice_results),
                                  retrieval='disabled' if retrieval == 'off' else 'ok' if any(item['items'] for item in contexts) else 'no_results',
                                  context=context['status'], llm=llm['status'], json_parse=llm['parse_status'], validation=validation['status'], candidate_validation=candidate_status),
                      llm=llm, model_review=model_review, validation=validation, repairs=repairs,
                      context_hash=context['context_hash'], evidence_count=len(evidence), context_evidence_count=len(context['evidence']),
                      telemetry=dict(elapsed_ms=round((time.perf_counter() - started) * 1000, 3), usage=llm.get('usage'),
                                     prompt_token_upper_bound=context['token_upper_bound']),
                      limitations=['Research MVP, not complete SymPas/DRaCo or production review.',
                                   'Unchecked return rule scans five following lines; may miss or misclassify control flow.',
                                   'Bundled return contracts are manual demo policy; Infer candidates need human confirmation.',
                                   'C/C++ Infer capture uses clang directly; project-specific flags/build systems are not inferred.',
                                   'Local CodeGen is optional and may fail strict JSON parsing; no live model validation is implied.',
                                   'Candidate patches are restricted to existing source return guards; other edits are rejected.',
                                   'Tests run only from explicit trusted argv in a disposable source copy; no model-specified commands.',
                                   'Candidate files remain separate; user repository source is never patched.'])
        save(out / 'llm_response.json', llm)
        save(out / 'validation.json', dict(validation=validation, repairs=repairs))
        save(out / 'run.json', result)
        (out / 'review.md').write_text(markdown(result))
        return result
