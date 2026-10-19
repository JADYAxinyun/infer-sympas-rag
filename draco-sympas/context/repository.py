"""Small AST relation index inspired by DRaCo, not an upstream reproduction."""
import ast
import hashlib
import json
import re
import subprocess
from collections import deque
from pathlib import Path

RELATIONS = ('ASSIGNS', 'REFERS', 'TYPEOF', 'INHERITS', 'AS', 'CALLS')
SKIP = {'.git', '.venv', '__pycache__', 'artifacts', 'node_modules', 'third_party'}


def index_repository(repo):
    repo = Path(repo).resolve()
    if not repo.is_dir():
        raise ValueError('repo must be an existing directory')
    nodes, edges, diagnostics, hashes = [], [], [], {}

    def add(file, name, line, end, code, relations):
        identity = f'{file}:{line}:{name}'
        nodes.append(dict(id=identity, file=file, procedure=name, line=line,
                          end_line=end, code=code, symbols=sorted(set(re.findall(r'\b[A-Za-z_]\w*\b', code)))))
        for relation, symbol, location in relations:
            if symbol:
                edges.append(dict(source=identity, relation=relation, symbol=symbol, line=location))

    for path in sorted(repo.rglob('*')):
        if not path.is_file() or path.is_symlink() or set(path.relative_to(repo).parts) & SKIP:
            continue
        if path.suffix not in ('.py', '.c', '.h', '.cc', '.cpp'):
            continue
        file = path.relative_to(repo).as_posix()
        source = path.read_text(errors='replace')
        hashes[file] = hashlib.sha256(source.encode()).hexdigest()
        lines = source.splitlines()
        try:
            if path.suffix == '.py':
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        continue
                    relations = []
                    for item in ast.walk(node):
                        if isinstance(item, ast.Call):
                            relations.append(('CALLS', ast.unparse(item.func), item.lineno))
                        elif isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load):
                            relations.append(('REFERS', item.id, item.lineno))
                        elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                            for target in targets:
                                relations.append(('ASSIGNS', ast.unparse(target), item.lineno))
                            if isinstance(item, ast.AnnAssign):
                                relations.append(('TYPEOF', ast.unparse(item.annotation), item.lineno))
                        elif isinstance(item, ast.arg) and item.annotation:
                            relations.append(('TYPEOF', ast.unparse(item.annotation), item.lineno))
                        elif isinstance(item, (ast.Import, ast.ImportFrom)):
                            for alias in item.names:
                                relations.append(('REFERS', alias.name, item.lineno))
                                if alias.asname:
                                    relations.append(('AS', alias.name, item.lineno))
                        elif isinstance(item, ast.ClassDef):
                            relations.extend(('INHERITS', ast.unparse(base), item.lineno) for base in item.bases)
                    add(file, node.name, node.lineno, node.end_lineno,
                        '\n'.join(lines[node.lineno - 1:node.end_lineno]), relations)
            else:
                command = ['clang', '-Xclang', '-ast-dump=json', '-fsyntax-only', str(path)]
                completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
                if completed.returncode:
                    diagnostics.append(dict(file=file, status='partial', reason='clang_parse_failed', stderr=completed.stderr[-2000:]))
                    continue
                tree = json.loads(completed.stdout)

                def walk(item):
                    yield item
                    for child in item.get('inner', []):
                        yield from walk(child)

                for node in walk(tree):
                    if node.get('kind') != 'FunctionDecl' or not any(x.get('kind') == 'CompoundStmt' for x in node.get('inner', [])):
                        continue
                    loc = node.get('loc', {})
                    if loc.get('includedFrom') or loc.get('file', str(path)) != str(path):
                        continue
                    begin = node.get('range', {}).get('begin', {}).get('offset')
                    endloc = node.get('range', {}).get('end', {})
                    end = endloc.get('offset')
                    if begin is None or end is None:
                        continue
                    # Clang offsets are bytes; decoding preserves non-ASCII source locations.
                    raw = source.encode()
                    line = raw[:begin].count(b'\n') + 1
                    end_line = raw[:end].count(b'\n') + 1
                    relations = []
                    for item in walk(node):
                        kind = item.get('kind')
                        iloc = item.get('range', {}).get('begin', {}).get('offset', begin)
                        at = raw[:iloc].count(b'\n') + 1
                        if kind == 'CallExpr':
                            first = item.get('inner', [])[:1]
                            for child in first:
                                for ref in walk(child):
                                    decl = ref.get('referencedDecl', {})
                                    if decl.get('kind') == 'FunctionDecl':
                                        relations.append(('CALLS', decl.get('name'), at))
                        elif kind == 'DeclRefExpr':
                            relations.append(('REFERS', item.get('referencedDecl', {}).get('name'), at))
                        elif kind in ('VarDecl', 'ParmVarDecl'):
                            if kind == 'VarDecl' and item.get('init'):
                                relations.append(('ASSIGNS', item.get('name'), at))
                            relations.append(('TYPEOF', item.get('type', {}).get('qualType'), at))
                    add(file, node['name'], line, end_line,
                        raw[begin:end + endloc.get('tokLen', 1)].decode(errors='replace'), relations)
        except (SyntaxError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            diagnostics.append(dict(file=file, status='unsupported', reason=type(error).__name__))
    by_name = {}
    for node in nodes:
        by_name.setdefault(node['procedure'], []).append(node)
    for edge in edges:
        candidates = by_name.get(edge['symbol'].split('.')[-1], [])
        same_file = [node for node in candidates if node['file'] == edge['source'].split(':')[0]]
        targets = same_file or candidates
        edge['targets'] = [node['id'] for node in targets]
        edge['resolution'] = 'unique' if len(targets) == 1 else 'ambiguous' if targets else 'unresolved'
    return dict(schema_version=1, root=str(repo), nodes=nodes, edges=edges, file_hashes=hashes,
                status='partial', diagnostics=diagnostics,
                limitations=['Static name resolution may be ambiguous; no dynamic dispatch or pointer-call resolution.',
                             'C/C++ require clang and usable headers; TYPEOF is an AST annotation, not type inference.',
                             'AS/INHERITS supported for Python AST only; module-level imports are not resolved.'])


def retrieve(index, *, file=None, procedure=None, symbols=(), line=None, diff='', finding=None,
             slices=(), max_items=8, token_budget=1600, mode='relations'):
    if mode == 'off':
        return dict(items=[], retrieval_trace=[], status='disabled', mode=mode)
    nodes = {node['id']: node for node in index['nodes']}
    symbols = set(symbols) | set(re.findall(r'\b[A-Za-z_]\w*\b', diff))
    if finding:
        symbols.update(filter(None, [finding.get('callee'), finding.get('variable')]))
        line = line or finding.get('line')
    for item in slices:
        symbols.add(item.get('procedure', ''))
        symbols.update(call.get('callee', '') for call in item.get('call_chain', []))
    seeds = [key for key, node in nodes.items() if
             (file is None or node['file'] == file) and
             ((procedure and node['procedure'] == procedure) or
              (line and node['line'] <= line <= node['end_line']))]
    if not seeds:
        seeds = [key for key, node in nodes.items() if node['procedure'] in symbols]
    adjacency = {key: [] for key in nodes}
    for edge in index['edges']:
        for target in edge['targets']:
            adjacency[edge['source']].append((target, edge['relation']))
            adjacency[target].append((edge['source'], edge['relation'] + '_REVERSE'))
    if mode == 'text':
        words = set(re.findall(r'\w+', diff)) | symbols
        for key in seeds:
            words.update(nodes[key]['symbols'])
        ranked = sorted(nodes, key=lambda key: (-len(words & set(nodes[key]['symbols'])), key))
        queue = deque((key, ['TEXT_SIMILARITY'], 0) for key in ranked if words & set(nodes[key]['symbols']))
    else:
        queue = deque((key, [key], 0) for key in seeds)
    seen, items, trace, used = set(), [], [], 0
    while queue and len(items) < max_items:
        key, path, distance = queue.popleft()
        if key in seen:
            continue
        seen.add(key)
        node = nodes[key]
        # UTF-8 byte count is a conservative token upper bound, not billed usage.
        cost = len(json.dumps(node, ensure_ascii=False).encode())
        if used + cost <= token_budget:
            items.append(dict(node, relation=path[-2] if len(path) > 1 else path[0], distance=distance,
                              relevance_reason=' -> '.join(path), retrieval_path=path))
            used += cost
            trace.append(path)
        if mode == 'relations':
            for target, relation in sorted(adjacency[key]):
                if distance < 3:
                    queue.append((target, path + [relation, target], distance + 1))
    return dict(items=items, retrieval_trace=trace, status='ok' if items else 'no_results', mode=mode,
                budget_upper_bound=used, budget_unit='UTF-8 bytes', context_id='ctx-001')
