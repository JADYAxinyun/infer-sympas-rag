"""Opt-in paid/network smoke test; never active in default pytest runs."""
import os
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).parents[1]))
from context.builder import build_context
from providers import invoke
from validation import parse_review


@pytest.mark.skipif(os.getenv('RUN_DEEPSEEK_LIVE') != '1', reason='requires explicit RUN_DEEPSEEK_LIVE=1')
def test_live_deepseek_json(tmp_path):
    assert os.getenv('DEEPSEEK_API_KEY'), 'DEEPSEEK_API_KEY is required for live smoke'
    result = invoke('deepseek', build_context([]))
    # Preserve API receipt even if parsing fails; never persist request headers.
    (tmp_path / 'deepseek-receipt.json').write_text(__import__('json').dumps(result))
    assert result['status'] == 'ok', result.get('error')
    _, errors = parse_review(result['raw_response'])
    assert not errors, errors
