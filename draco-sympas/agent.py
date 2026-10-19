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
from review import review_source
from validation import parse_review, validate_evidence


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def markdown(result):
    lines = ['# Evidence-enhanced code review', '', 'Research MVP; static evidence and heuristic rules, not a production verdict.', '',
             f"- Run: `{result['run_id']}`", f"- Infer: `{result['infer']['status']}`", f"- LLM: `{result['llm']['provider']}/{result['llm']['status']}`",
             f"- Local findings: {len(result['findings'])}", f"- Validation: `{result['validation']['status']}`", '',
             '| File | Line | Rule | Contract source |', '|---|---:|---|---|']
    for finding in result['findings']:
        lines.append(f"| {finding['file']} | {finding['line']} | {finding['rule']} | {finding.get('contract', {}).get('source', 'unknown')} |")
    lines += ['', '## Model response', '', '```json', json.dumps(result.get('model_review'), ensure_ascii=False, indent=2), '```',
              '', '## Candidate validation', '', '```json', json.dumps(result['repairs'], ensure_ascii=False, indent=2), '```',
              '', '## Limits', ''] + ['- ' + item for item in result['limitations']]
    return '\n'.join(lines) + '\n'


class ReviewAgent:
    def review(self, repo_path, diff=None, target_files=None, rule='unchecked_return_value', llm_provider='none',
               *, output_dir=None, infer_mode='real', infer_bin=None, model=None, retrieval='relations',
               token_budget=16000, max_contexts=8, return_contracts=None):
        if rule != 'unchecked_return_value':
            raise ValueError('Only existing unchecked_return_value rule is supported')
        if infer_mode not in ('real', 'mock', 'off') or retrieval not in ('relations', 'text', 'off'):
            raise ValueError('unsupported analysis mode')
        started = time.perf_counter()
        repo = Path(repo_path).resolve()
        if not repo.is_dir():
            raise ValueError('repo_path must be a directory')
        if token_budget < 1500 or max_contexts < 0:
            raise ValueError('token_budget must be >=1500 and max_contexts must be nonnegative')
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        out = Path(output_dir or Path(__file__).parent / 'artifacts' / 'agent' / run_id).resolve()
        out.mkdir(parents=True, exist_ok=False)
        index = index_repository(repo)
        save(out / 'index.json', index)
        if diff is None:
            completed = subprocess.run(['git', '-C', str(repo), 'diff', 'HEAD', '--'], capture_output=True, text=True)
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
                              out / 'infer', sympas_only=True)
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
        for number, item in enumerate(infer.get('slices', []), 1):
            data = dict(item, slice_id=f'slice-{number:03d}', status=item.get('analysis_status', 'partial'), confidence='conservative')
            data['nodes'] = item.get('source_locations', [])
            data['edges'] = item.get('call_chain', [])
            data['procedures'] = sorted({item.get('procedure', '')} | {call.get('callee', '') for call in item.get('call_chain', [])})
            data['dependencies'] = dict(data=item.get('data_dependencies', []), control=item.get('control_dependencies', []), calls=item.get('call_chain', []))
            evidence.append(dict(id='sympas:' + data['slice_id'], kind='SYMPAS_SLICE', provenance='real_infer', data=data))
        for path in paths:
            file = path.relative_to(repo).as_posix()
            source = path.read_text(errors='replace')
            sources[file] = source
            reviewed = review_source(source, return_contracts=return_contracts,
                                     infer_candidates=infer.get('return_contract_candidates', []))
            for item in reviewed['findings']:
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
        context = build_context(evidence, diff, token_budget)
        save(out / 'evidence.json', evidence)
        save(out / 'context.json', context)
        save(out / 'retrieval.json', contexts)
        (out / 'prompt.json').write_text(json.dumps(context['messages'], ensure_ascii=False, indent=2))
        llm = invoke(llm_provider, context, model=model)
        model_review, errors = parse_review(llm['raw_response']) if llm['status'] == 'ok' else (None, [])
        reference_validation = validate_evidence(model_review, context['evidence'], repo) if model_review and not errors else dict(status='not_verified', errors=[])
        validation = dict(status='validation_failed' if errors or reference_validation['errors'] else
                          'partially_verified' if model_review else 'not_verified', schema_errors=errors,
                          evidence=reference_validation, rule='unchecked_return_value',
                          note='Local rule findings remain independent of model status; evidence checks do not prove semantics.')
        repairs = []
        for finding in findings:
            # Existing repair assumes a negative error code and an integer return.
            # Never apply arbitrary model patches or infer this contract from int alone.
            candidate = propose_return_check(sources[finding['file']], finding) if finding['file'].endswith('.c') else None
            if not candidate:
                repairs.append(dict(finding_id=finding['finding_id'], status='not_verified', reason='no_supported_candidate'))
                continue
            candidate_path = out / ('candidate-' + finding['finding_id'] + '.c')
            candidate_path.write_text(candidate['source'])
            after = review_source(candidate['source'], return_contracts=return_contracts,
                                  infer_candidates=infer.get('return_contract_candidates', []))
            before_count = sum(item['file'] == finding['file'] for item in findings)
            decreased = after['summary']['count'] < before_count
            try:
                check = subprocess.run(['clang', '-fsyntax-only', '-I', str((repo / finding['file']).parent), str(candidate_path)], capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired) as error:
                repairs.append(dict(finding_id=finding['finding_id'], status='validation_failed',
                                    candidate_file=str(candidate_path), reason=type(error).__name__))
                continue
            recheck = dict(status='not_run')
            if infer_mode == 'real' and infer.get('ok') and check.returncode == 0:
                recheck = run_infer(repo, ['clang', '-c', str(candidate_path), '-I', str((repo / finding['file']).parent)],
                                    infer_bin, out / ('infer-after-' + finding['finding_id']), sympas_only=True)
            repairs.append(dict(finding_id=finding['finding_id'], status='partially_verified' if decreased and check.returncode == 0 else 'validation_failed',
                                before_findings=before_count, after_findings=after['summary']['count'],
                                candidate_file=str(candidate_path), syntax_check=dict(returncode=check.returncode, stderr=check.stderr), infer_after=recheck,
                                note='Rule reduction and syntax only; no behavioral equivalence, API-contract or runtime-test proof.'))
        result = dict(run_id=run_id, repo=str(repo), output_dir=str(out), findings=findings, infer=infer,
                      slices=[entry['data'] for entry in evidence if entry['kind'] == 'SYMPAS_SLICE'],
                      slice_status='partial' if infer.get('slices') else 'not_analyzed', index_status=index['status'],
                      diff_status=diff_status, review_scope='explicit targets or all indexed files; diff is context',
                      llm=llm, model_review=model_review, validation=validation, repairs=repairs,
                      context_hash=context['context_hash'], evidence_count=len(evidence), context_evidence_count=len(context['evidence']),
                      telemetry=dict(elapsed_ms=round((time.perf_counter() - started) * 1000, 3), usage=llm.get('usage'),
                                     prompt_token_upper_bound=context['token_upper_bound']),
                      limitations=['Research MVP, not complete SymPas/DRaCo or production review.',
                                   'Unchecked return rule scans five following lines; may miss or misclassify control flow.',
                                   'Bundled return contracts are manual demo policy; Infer candidates need human confirmation.',
                                   'C/C++ Infer capture uses clang directly; project-specific flags/build systems are not inferred.',
                                   'Local CodeGen is optional and may fail strict JSON parsing; no live model validation is implied.',
                                   'Candidate files remain separate; user repository source is never patched.'])
        save(out / 'run.json', result)
        (out / 'review.md').write_text(markdown(result))
        return result
