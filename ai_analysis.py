"""Optional Groq evidence-based research commentary; no automatic calls or trades."""
import json
import requests

MODEL = 'openai/gpt-oss-20b'
ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
LANG = {'en': 'English', 'zh': 'Simplified Chinese', 'de': 'German'}


class AIAnalysisError(Exception):
    pass


def explain(snapshot: dict, api_key: str, language: str = 'en') -> str:
    """Caller supplies only verified data; no fabricated fallback or price prediction."""
    if not api_key or not api_key.strip():
        raise AIAnalysisError('Connect a Groq API key in Streamlit Secrets first.')
    language = language if language in LANG else 'en'
    try:
        data = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, default=str)
    except (TypeError, ValueError) as exc:
        raise AIAnalysisError('Research snapshot has invalid data.') from exc
    if len(data) > 16000:
        raise AIAnalysisError('Research snapshot exceeds the safe request size.')
    system = (
        'You are an educational, evidence-first equity research assistant. '
        f'Write the report in {LANG[language]} with clear Markdown headings: Summary, Technical Evidence, '
        'Fundamental Evidence, Relevant Headlines, Bull/Bear Scenarios, Risks & Watchlist, Limitations. '
        'Only use the supplied JSON snapshot, quote its observation dates, distinguish verified numerical '
        'data from speculative interpretation, explicitly note unavailable evidence. '
        'Never invent a company description, fundamental metrics, articles, news content, current price, '
        'source attribution, win rate, target prices, future probabilities or analyst recommendations. '
        'Headlines are titles, not verified full articles; do not state what their articles contain. '
        'Rule signal is a technical classification, not an instruction to buy/sell. '
        'Never provide individual investment advice, guaranteed returns or trading instructions. '
        'If observations are stale or absent, say so. The retrieved timestamp is not a market price timestamp. '
        'Keep under 450 words and end with an educational-not-investment-advice note in the report language.'
    )
    try:
        r = requests.post(
            ENDPOINT,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={'model': MODEL, 'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': data},
            ], 'temperature': 0.15, 'max_completion_tokens': 2300, 'stream': False},
            timeout=(5, 48),
        )
    except requests.RequestException as exc:
        raise AIAnalysisError('AI request failed or timed out. The underlying research data remains available.') from exc
    if r.status_code == 429:
        raise AIAnalysisError('Groq rate limit or free quota reached. Retry later; no paid fallback is used.')
    if r.status_code in (401, 403):
        raise AIAnalysisError('Groq rejected the API key or model permission. Check your Streamlit Secrets.')
    if r.status_code != 200:
        raise AIAnalysisError(f'Groq temporarily returned HTTP {r.status_code}.')
    try:
        choice = r.json()['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise AIAnalysisError('AI report was incomplete; it was not displayed.')
        content = choice['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Empty AI message')
        return content.strip()
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        raise AIAnalysisError('Groq returned an unreadable report.') from exc
