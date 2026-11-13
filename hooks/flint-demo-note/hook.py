"""Use only the event name. Do not store the user's input."""
import json
import sys

payload = json.load(sys.stdin)
if payload.get('hook_event_name') != 'UserPromptSubmit':
    raise SystemExit(1)
print(json.dumps({'hookSpecificOutput': {
    'hookEventName': 'UserPromptSubmit',
    'additionalContext': 'FLINT_DEMO_HOOK: сообщай только о фактически проверенных результатах.'
}}, ensure_ascii=False))
