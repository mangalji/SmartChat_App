import json
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET

logger = logging.getLogger(__name__)

QUICK_PROMPTS = [
    {'label': 'Write a reply',      'hint': 'Compose a message',     'icon': 'chat-left-text',  'text': 'Help me write a polite reply to: '},
    {'label': 'Summarise',          'hint': 'Shorten long text',      'icon': 'file-text',       'text': 'Summarise this in 2 sentences: '},
    {'label': 'Make it formal',     'hint': 'Professional tone',      'icon': 'briefcase',       'text': 'Rewrite this in a formal tone: '},
    {'label': 'Make it casual',     'hint': 'Friendly tone',          'icon': 'emoji-smile',     'text': 'Rewrite this in a casual, friendly tone: '},
    {'label': 'Hindi mein likho',   'hint': 'Translate to Hindi',     'icon': 'translate',       'text': 'इसे हिंदी में लिखो: '},
    {'label': 'Fix grammar',        'hint': 'Correct mistakes',       'icon': 'spellcheck',      'text': 'Fix the grammar in this text: '},
    {'label': 'Schedule message',   'hint': 'Draft timed message',    'icon': 'clock',           'text': 'Write a message I can send tomorrow morning about: '},
    {'label': 'Apologise',          'hint': 'Apology message',        'icon': 'heart',           'text': 'Help me write a sincere apology for: '},
]


@login_required
@require_GET
def assistant_page(request):
    return render(request, 'ai_assist/assistant.html', {'prompts': QUICK_PROMPTS})


@login_required
@require_POST
def chat_with_ai(request):
    try:
        data    = json.loads(request.body)
        message = data.get('message', '').strip()
        history = data.get('history', [])
    except Exception:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    if not message:
        return JsonResponse({'error': 'Empty message.'}, status=400)

    # Build conversation history string
    history_text = ''
    for turn in history[-6:]:
        role = 'User' if turn.get('role') == 'user' else 'Assistant'
        history_text += f"{role}: {turn.get('text', '')}\n"

    prompt = f"""You are SmartChat AI — a friendly, helpful assistant built into a chat app.
You support both English and Hindi. Always reply in the same language the user writes in,
unless they ask you to switch. Keep replies concise (2–4 sentences max unless asked for more).

{f'Conversation so far:{chr(10)}{history_text}' if history_text else ''}
User: {message}
Assistant:"""

    try:
        from ai_assist.gemini import get_suggestion_raw, detect_language
        reply = get_suggestion_raw(prompt)
        lang  = detect_language(reply)
    except Exception as e:
        logger.warning(f'AI chat fallback triggered: {e}')
        from ai_assist.gemini import _mock_suggestion, detect_language
        lang  = detect_language(message)
        reply = _mock_suggestion(message, lang)

    return JsonResponse({'reply': reply, 'lang': lang})
