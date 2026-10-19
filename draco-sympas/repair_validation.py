"""Validate source-only patches in a disposable copy, never the input repository."""
import difflib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess

from infer_runner import run_infer
from review import review_source


def source_patch(file, before, after):
    return ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        fromfile='a/' + file, tofile='b/' + file))


def check_patch(repo, patch, target_files):
    """Reject new/deleted files, escapes, metadata changes and non-source edits."""
    if not isinstance(patch, str) or not patch.strip():
        return ['empty_patch']
    if len(patch.encode()) > 65536:
        return ['patch_too_large']
    forbidden = ('GIT binary patch', 'Binary files ', 'new file mode', 'deleted file mode',
                 'old mode ', 'new mode ', 'rename from ', 'rename to ', 'copy from ', 'copy to ')
    if any(line.startswith(forbidden) for line in patch.splitlines()):
        return ['unsupported_patch_metadata']
    safe_line = re.compile(r'^\s*(?://.*|[{}]?|return\s+(?:[A-Za-z_]\w*|-?\d+)\s*;|if\s*\(\s*[A-Za-z_]\w*\s*(?:<\s*0|!=\s*0)\s*\)\s*(?:\{(?:\s*return\s+[A-Za-z_]\w*\s*;\s*\})?|return\s+[A-Za-z_]\w*\s*;)?)\s*$')
    for line in patch.splitlines():
        if line.startswith('+') and not line.startswith('+++') and not safe_line.fullmatch(line[1:]):
            return ['patch_outside_return_guard_subset']
        if line.startswith('-') and not line.startswith('---') and not re.fullmatch(r'\s*(?:return\s+(?:[A-Za-z_]\w*|-?\d+)\s*;)?\s*', line[1:]):
            return ['patch_removes_nonreturn_statement']
    paths = []
    for line in patch.splitlines():
        if line.startswith(('--- ', '+++ ')):
            value = line[4:].split('\t', 1)[0]
            if not value.startswith(('a/', 'b/')):
                return ['invalid_patch_path']
            name = value[2:]
            path = repo / name
            if name not in target_files or Path(name).is_absolute() or '..' in Path(name).parts:
                return ['patch_outside_targets']
            if path.suffix not in ('.c', '.h', '.cc', '.cpp') or path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(repo):
                return ['unsafe_patch_target']
            paths.append(name)
    if not paths or len(paths) % 2 or any(a != b for a, b in zip(paths[::2], paths[1::2])):
        return ['invalid_patch_headers']
    return []


def validate_candidate(repo, patch, output, *, target_files, finding_id, origin='local_rule',
                       return_contracts=None, infer_candidates=None, infer_bin='infer',
                       run_static=True, test_command=None, infer_before=None, infer_profile='sympas'):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = dict(finding_id=finding_id, origin=origin, status='not_verified',
                  before_findings=None, after_findings=None, infer_after={'status': 'not_run'},
                  note='Candidate only. Passing checks are bounded evidence, not general correctness or automatic application.')
    result['infer_before'] = infer_before or {'status': 'not_run'}
    (output / 'candidate.patch').write_text(patch or '')
    errors = check_patch(repo, patch, target_files)
    if errors:
        result.update(status='validation_failed', reason=errors)
    else:
        workspace = output / 'workspace'
        ignored = shutil.ignore_patterns('.git', '.env', '.env.*', '*.key', '*.pem', '.venv', 'venv',
            '__pycache__', 'artifacts', 'node_modules', '*.o', '*.bin', '*.pt', '*.safetensors', '.pytest_cache')
        def ignore(folder, names):
            return set(ignored(folder, names)) | {name for name in names
                if (Path(folder) / name).is_symlink() or (Path(folder) / name).resolve() == output}
        shutil.copytree(repo, workspace, ignore=ignore)
        env = dict(os.environ)
        for name in ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
            env.pop(name, None)

        def execute(command, timeout=60):
            try:
                completed = subprocess.run(command, cwd=workspace, env=env, capture_output=True, text=True, timeout=timeout)
                return dict(status='passed' if completed.returncode == 0 else 'failed', command=command,
                            returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
            except (OSError, subprocess.TimeoutExpired) as error:
                return dict(status='failed', command=command, returncode=None, error=type(error).__name__)

        def rules():
            values = []
            for name in target_files:
                for finding in review_source((workspace / name).read_text(), return_contracts=return_contracts,
                                             infer_candidates=infer_candidates)['findings']:
                    values.append(dict(finding, file=name))
            return values

        result['before_findings'] = len(rules())
        if test_command:
            result['tests_before'] = execute(test_command)
        else:
            result['tests_before'] = {'status': 'not_run'}
        command = ['git', 'apply', '--no-index', '--whitespace=error', '--check', str(output / 'candidate.patch')]
        result['patch_check'] = execute(command)
        if result['patch_check']['status'] != 'passed':
            result.update(status='validation_failed', reason=['patch_does_not_apply'])
        else:
            result['patch_apply'] = execute([arg for arg in command if arg != '--check'])
            if result['patch_apply']['status'] != 'passed':
                result.update(status='validation_failed', reason=['patch_apply_failed'])
            else:
                result['after_findings'] = len(rules())
                sources = [str(workspace / name) for name in target_files if Path(name).suffix in ('.c', '.cc', '.cpp')]
                result['syntax_check'] = execute(['clang', '-fsyntax-only'] + sources)
                if run_static and result['syntax_check']['status'] == 'passed':
                    result['infer_after'] = run_infer(workspace, ['clang', '-c'] + sources, infer_bin,
                                                      output / 'infer-after', sympas_only=infer_profile == 'sympas',
                                                      checker_args=['--sympas'] if infer_profile == 'combined' else ['--no-sympas'] if infer_profile == 'native' else None)
                result['tests_after'] = execute(test_command) if test_command else {'status': 'not_run'}
                rules_improved = result['after_findings'] < result['before_findings']
                static_failed = run_static and not result['infer_after'].get('ok')
                tests_failed = result['tests_after']['status'] == 'failed'
                if not rules_improved or result['syntax_check']['status'] != 'passed' or static_failed or tests_failed:
                    result.update(status='validation_failed', reason=['candidate_recheck_failed'])
                elif result['infer_after'].get('ok') or result['tests_after']['status'] == 'passed':
                    result.update(status='partially_verified', reason=['bounded_checks_passed'])
                else:
                    result.update(status='partially_verified', reason=['rule_and_syntax_only_no_infer_or_behavior_tests'])
                result['checks'] = dict(rule_count_decreased=rules_improved,
                                       static_recheck=result['infer_after'].get('status'),
                                       behavior_tests=result['tests_after']['status'])
        result['workspace'] = str(workspace)
    (output / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result
