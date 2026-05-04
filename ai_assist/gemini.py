"""
ai_assist/gemini.py

Gemini AI integration for SmartChat.
- get_suggestion()     : suggest a reply based on recent chat context
- detect_language()    : detect if context is Hindi or English
- get_suggestion_raw() : raw Gemini call with custom prompt
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Lazy initialisation — import SDK only when needed ──
_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model

    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY is not set in .env')

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            generation_config={
                'temperature':     0.7,
                'top_p':           0.9,
                'top_k':           40,
                'max_output_tokens': 120,
            },
            safety_settings=[
                {'category': 'HARM_CATEGORY_HARASSMENT',        'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
                {'category': 'HARM_CATEGORY_HATE_SPEECH',       'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
                {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
                {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
            ],
        )
        logger.info('Gemini model initialised (gemini-2.5-flash)')
    except ImportError:
        raise RuntimeError(
            'google-generativeai not installed. Run: pip install google-generativeai'
        )

    return _model


# ─────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────

def detect_language(text: str) -> str:
    """
    Heuristic: if >15% of characters are Devanagari → 'hindi', else 'english'.
    Fast, no API call needed.
    """
    if not text:
        return 'english'
    devanagari = sum(1 for ch in text if '\u0900' <= ch <= '\u097f')
    return 'hindi' if (devanagari / max(len(text), 1)) > 0.15 else 'english'


def get_suggestion(context: str, other_name: str = 'them') -> str:
    """
    Generate a context-aware reply suggestion.

    Args:
        context:    Pipe-separated recent messages e.g. "Hey | How are you | I'm good"
        other_name: Name of the other person / group

    Returns:
        A short suggested reply string.
    """
    lang = detect_language(context)

    if lang == 'hindi':
        lang_instruction = (
            'Reply in Hindi (Devanagari script). '
            'Keep it conversational and natural.'
        )
    else:
        lang_instruction = (
            'Reply in English. '
            'Keep it conversational and natural.'
        )

    prompt = f"""You are helping someone reply in a chat conversation.

Recent messages (newest last):
{context}

The other person/group is: {other_name}

Your task:
- Suggest ONE short, friendly reply (max 2 sentences).
- {lang_instruction}
- Do NOT add quotes, prefixes like "Reply:", or explanations.
- Just output the reply text directly.
"""

    return _call_gemini(prompt, fallback=_mock_suggestion(context, lang))


def get_suggestion_raw(prompt: str) -> str:
    """Call Gemini with a fully custom prompt. Returns raw text."""
    return _call_gemini(prompt, fallback='')


# ─────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────

def _call_gemini(prompt: str, fallback: str = '') -> str:
        try:
            model    = _get_model()
            response = model.generate_content(prompt)
            
            # Check if the response was blocked by safety filters
            if not response.candidates or not response.candidates[0].content.parts:
                logger.warning('Gemini response blocked by safety filters.')
                return fallback

            text = response.text.strip()

            # Strip common unwanted prefixes
            for prefix in ('Reply:', 'Suggested reply:', 'Response:', 'Answer:'):
                if text.lower().startswith(prefix.lower()):
                    text = text[len(prefix):].strip()

            return text if text else fallback

        except RuntimeError as e:
            # API key missing / SDK not installed — use mock
            logger.warning(f'Gemini unavailable: {e}')
            return fallback

        except Exception as e:
            logger.error(f'Gemini API error: {e}')
            return fallback


def _mock_suggestion(context: str, lang: str) -> str:
    """
    Deterministic-ish fallback when Gemini is not available.
    Picks based on keywords in context.
    """
    import random

    ctx = context.lower()

    en_map = [
        (['hello', 'hi', 'hey'],              ['Hey! How are you?', 'Hi there!', 'Hello there!']),
        (['thanks', 'thank'],                  ['You are welcome!', 'Anytime!', 'Happy to help!']),
        (['how are you', 'how r u', 'kaise'], ['Doing great, thanks! You?', 'All good! How about you?']),
        (['meet', 'meeting', 'call'],          ['Sure, let me check my schedule.', 'Works for me!']),
        (['help', 'issue', 'problem'],         ['Sure, I can help with that!', 'Tell me more about the issue.']),
        (['ok', 'okay', 'sure', 'alright'],   ['Great!', 'Perfect!', 'Sounds good!']),
        (['bye', 'goodbye', 'later'],          ['Take care!', 'Bye! Talk soon.', 'See you!']),
    ]
    hi_map = [
        (['hello', 'hi', 'hey', 'namaste'],   ['Namaste! Kaise ho?', 'Haan, bolo!']),
        (['thanks', 'shukriya'],               ['Koi baat nahi!', 'Khushi hui!']),
        (['kaise', 'how'],                     ['Main theek hoon, aap batao?', 'Badhiya! Aap kaise ho?']),
        (['theek', 'ok', 'okay'],              ['Achha!', 'Theek hai!']),
        (['bye', 'alvida'],                    ['Theek hai, alvida!', 'Baad mein baat karte hain!']),
    ]

    pool = hi_map if lang == 'hindi' else en_map
    for keywords, options in pool:
        if any(kw in ctx for kw in keywords):
            return random.choice(options)

    generic_en = [
        'Sure, sounds good!',
        'Got it, I will look into it.',
        'Okay, let me check and get back to you.',
        'Thanks for letting me know!',
        'Interesting! Tell me more.',
        'Let me think about that.',
        'Absolutely!',
    ]
    generic_hi = [
        'Haan, bilkul!',
        'Theek hai, main dekhta hoon.',
        'Samajh gaya, thoda samay do.',
        'Batane ke liye shukriya!',
        'Accha vichar hai!',
    ]
    return random.choice(generic_hi if lang == 'hindi' else generic_en)
