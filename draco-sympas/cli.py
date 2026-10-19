"""Compatibility CLI: python draco-sympas/cli.py {index,review,report}."""
import argparse
import json
from pathlib import Path
from provider_config import load_env_file
from agent import ReviewAgent, markdown, save
from context.repository import index_repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    index = commands.add_parser('index')
    index.add_argument('--repo', required=True)
    index.add_argument('--output', required=True)
    review = commands.add_parser('review')
    review.add_argument('--repo', required=True)
    review.add_argument('--target-file', action='append')
    review.add_argument('--diff', type=Path)
    review.add_argument('--output', help='New run directory; must not already exist')
    review.add_argument('--llm-provider', choices=['none', 'mock', 'local', 'deepseek'], default='none')
    review.add_argument('--model')
    review.add_argument('--env-file', type=Path, help='Explicit local DeepSeek settings file; existing environment takes precedence')
    review.add_argument('--infer-mode', choices=['real', 'mock', 'off'], default='real')
    review.add_argument('--infer-bin')
    review.add_argument('--retrieval', choices=['relations', 'text', 'off'], default='relations')
    review.add_argument('--token-budget', type=int, default=16000)
    review.add_argument('--max-contexts', type=int, default=8)
    report = commands.add_parser('report')
    report.add_argument('--input', required=True)
    report.add_argument('--format', choices=['markdown', 'json'], default='markdown')
    report.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'review':
            if args.env_file:
                load_env_file(args.env_file)
            result = ReviewAgent().review(args.repo, diff=args.diff.read_text() if args.diff else None,
                                          target_files=args.target_file, output_dir=args.output,
                                          llm_provider=args.llm_provider, model=args.model,
                                          infer_mode=args.infer_mode, infer_bin=args.infer_bin,
                                          retrieval=args.retrieval, token_budget=args.token_budget,
                                          max_contexts=args.max_contexts)
            print(json.dumps(dict(output=result['output_dir'], findings=len(result['findings']),
                                  infer=result['infer']['status'], slice_status=result['slice_status'], llm=result['llm']['status'],
                                  parse_status=result['llm']['parse_status'], error=result['llm'].get('error'), validation=result['validation']['status'])))
            return 2 if result['infer']['status'] in {'execution_failed', 'report_parse_failed', 'missing_report'} or result['llm']['status'] not in {'ok', 'not_run'} or result['validation']['status'] == 'validation_failed' else 0
        destination = Path(args.output)
        if destination.exists():
            raise ValueError('Output exists; choose a new path to preserve evidence')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if args.command == 'index':
            value = index_repository(args.repo)
            save(destination, value)
            print(json.dumps(dict(output=str(destination), nodes=len(value['nodes']), edges=len(value['edges']))))
        else:
            result = json.loads(Path(args.input).read_text())
            destination.write_text(markdown(result) if args.format == 'markdown' else json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, type(error).__name__ + ': ' + str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
