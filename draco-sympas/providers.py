"""Optional providers. Only explicit deepseek selection can send network traffic."""
import json
import os
import time
import urllib.error
import urllib.request


def mock_response(evidence):
    rules = [item for item in evidence if item['kind'] == 'RULE_FACT']
    return dict(status='likely' if rules else 'evidence_insufficient',
                finding_type='unchecked_return_value', summary='Mock review; inspect local evidence.',
                reasoning='Deterministic test response; no model was called.',
                evidence_refs=[item['id'] for item in evidence], risk='medium',
                candidate_fix=dict(available=bool(rules), description='Check documented return contract before handling errors.', patch=None),
                confidence=0.5 if rules else 0.0, limitations=['Mock output has no semantic model judgment.'])


def invoke(provider, context, model=None, timeout=30, retries=2):
    if provider == 'none':
        return dict(provider=provider, status='not_run', raw_response=None, usage=None)
    if provider == 'mock':
        return dict(provider=provider, status='ok', raw_response=json.dumps(mock_response(context['evidence'])), usage=None)
    if provider == 'local':
        from llm_service import explain, token_usage
        try:
            prompt = json.dumps(context['messages'], ensure_ascii=False) + '\nJSON review:\n'
            text = explain({}, model or 'Salesforce/codegen-350M-mono', prompt=prompt)
            return dict(provider=provider, status='ok', raw_response=text,
                        usage=token_usage({}, text, prompt=prompt))
        except Exception as error:
            return dict(provider=provider, status='provider_error', error=type(error).__name__, raw_response=None, usage=None)
    if provider != 'deepseek':
        raise ValueError('unknown llm provider')
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        return dict(provider=provider, status='configuration_error', error='DEEPSEEK_API_KEY is missing', raw_response=None, usage=None)
    if timeout <= 0 or retries < 0 or retries > 5:
        raise ValueError('timeout must be positive; retries must be 0..5')
    model = model or os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash')
    payload = dict(model=model, messages=context['messages'], temperature=0,
                   response_format={'type': 'json_object'}, stream=False)
    request = urllib.request.Request('https://api.deepseek.com/chat/completions',
                                     data=json.dumps(payload).encode(), method='POST',
                                     headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    raw = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode()
            envelope = json.loads(raw)
            content = envelope['choices'][0]['message']['content']
            return dict(provider=provider, model=model, status='ok', attempts=attempt + 1,
                        raw_response=content, raw_envelope=raw, usage=envelope.get('usage'))
        except urllib.error.HTTPError as error:
            # Never persist request headers, key, or untrusted error body.
            retryable = error.code == 429 or error.code >= 500
            status, detail = 'api_error', 'HTTP ' + str(error.code)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            retryable, status, detail = True, 'api_error', type(error).__name__
        except (ValueError, KeyError, IndexError, TypeError):
            return dict(provider=provider, model=model, status='response_parse_failed', raw_envelope=raw,
                        raw_response=None, usage=None, attempts=attempt + 1)
        if not retryable or attempt == retries:
            return dict(provider=provider, model=model, status=status, error=detail,
                        raw_response=None, usage=None, attempts=attempt + 1)
        time.sleep(min(2 ** attempt, 4))
