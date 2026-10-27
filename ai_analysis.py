"""Optional, bounded LLM explanation. No fabricated fallback or trading actions."""
import json
import requests

MODEL = 'openai/gpt-oss-20b'
ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'


class AIAnalysisError(Exception):
    pass


def explain(snapshot, api_key):
    if not api_key:
        raise AIAnalysisError('Connect a Groq Free tier API key first.')
    try:
        response = requests.post(
            ENDPOINT,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': MODEL,
                'messages': [
                    {'role': 'system', 'content': (
                        'Write a concise English educational equity research note using ONLY the supplied numeric snapshot. '
                        'This is a rules-based research demo, not a validated investment strategy. '
                        'Preserve the supplied rule signal exactly; do not invent a separate prediction. '
                        'Use these headings: Signal interpretation; What supports it; What could invalidate it; Limitations. '
                        'Do not invent news, company fundamentals, future prices, probabilities, citations or a backtest. '
                        'No news articles were provided. Explain SMA/RSI limitations and the potentially incomplete latest daily bar. '
                        'Describe conditions to monitor, never claim an optimal entry price or guaranteed return. '
                        'A price decline does not by itself push RSI above 70. Explain price below SMA20 and RSI outside its allowed range as distinct invalidation conditions. '
                        'The retrieval timestamp is not a market timestamp. Do not infer whether the exchange was open from retrieval time. '
                        'Limit the final answer to 220 words. End with: Research demonstration, not investment advice.'
                    )},
                    {'role': 'user', 'content': json.dumps(snapshot, allow_nan=False)},
                ],
                'temperature': 0.2,
                'reasoning_effort': 'low',
                'max_completion_tokens': 1500,
                'stream': False,
            },
            timeout=(5, 40),
        )
    except requests.RequestException as exc:
        raise AIAnalysisError('AI connection failed or timed out. No report was generated.') from exc
    if response.status_code == 429:
        raise AIAnalysisError('Free quota or rate limit reached. Try later; no paid fallback is configured.')
    if response.status_code in (401, 403):
        raise AIAnalysisError('The API key or model access was rejected. Check your Groq console.')
    if response.status_code != 200:
        raise AIAnalysisError(f'AI service returned HTTP {response.status_code}. No report was generated.')
    try:
        choice = response.json()['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise AIAnalysisError('The model response was incomplete. Please try later.')
        result = choice['message']['content']
        if not isinstance(result, str) or not result.strip():
            raise ValueError('Empty response')
        return result.strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AIAnalysisError('The AI service returned an unusable response.') from exc
