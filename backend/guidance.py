"""Gemini chooses approved actions; no free-form diagnoses or invented scores."""
from datetime import datetime, timezone
import json
import os
import socket
from typing import Literal
import urllib.error
import urllib.request

from pydantic import BaseModel, ConfigDict, Field

ACTIONS = {
    'pause': 'Take a brief break from your current task.',
    'grounding': 'Pause and notice a few things you can see, hear, and feel around you.',
    'prioritize': 'Choose one manageable next task; consider discussing workload with someone you trust.',
    'sleep_routine': 'Plan a consistent bedtime and a quiet wind-down period tonight.',
    'connect': 'Check in with a trusted friend or someone who supports you.',
    'reflect': 'Note what feels demanding today and what might make it easier.',
}
FOCUS = {
    'pause': 'Make room for a short pause.',
    'workload': 'Consider your workload and your next manageable step.',
    'rest': 'Reflect on your rest and daily routine.',
    'reflection': 'Notice how you feel and what support would help.',
}
ActionId = Literal['pause', 'grounding', 'prioritize', 'sleep_routine', 'connect', 'reflect']

class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    focus: Literal['pause', 'workload', 'rest', 'reflection']
    actions: list[ActionId] = Field(min_length=2, max_length=3)

def request_gemini(inputs):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    model = os.getenv('GEMINI_MODEL', 'gemini-3.8-flash').strip()
    # Use a fixed endpoint; model is only a validated path segment.
    if not model or not all(c.isalnum() or c in '-._' for c in model):
        raise ValueError('Invalid model configuration')
    schema = {
        'type': 'object', 'properties': {
            'focus': {'type': 'string', 'enum': list(FOCUS)},
            'actions': {'type': 'array', 'items': {'type': 'string', 'enum': list(ACTIONS)}, 'minItems': 2, 'maxItems': 3}},
        'required': ['focus', 'actions'], 'additionalProperties': False}
    body = {
        'systemInstruction': {'parts': [{'text': 'Select 2 or 3 distinct practical wellbeing actions from the approved list and one focus. Use only the self-reported check-in as context. This is not diagnosis or stress measurement. Do not infer conditions or scores. Approved actions: ' + json.dumps(ACTIONS)}]},
        'contents': [{'role': 'user', 'parts': [{'text': json.dumps(inputs)}]}],
        'generationConfig': {'responseMimeType': 'application/json', 'responseJsonSchema': schema}}
    req = urllib.request.Request(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key}, method='POST')
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read(100001)
        if len(raw) > 100000:
            raise ValueError('Oversized response')
        payload = json.loads(raw)
    parts = payload['candidates'][0]['content']['parts']
    text = ''.join(part.get('text', '') for part in parts if not part.get('thought'))
    selection = Selection.model_validate_json(text)
    if len(set(selection.actions)) != len(selection.actions):
        raise ValueError('Duplicate actions')
    return selection, model

def generate_guidance(session, consent, request_fn=None):
    context = session.get('context') or {}
    # No identifiers, timestamps, video, camera metrics, or past sessions.
    inputs = {'self_reported_stress': session['self_reported_stress'],
              **{key: context.get(key) for key in ['sleep_hours', 'workload', 'caffeine', 'recent_exercise']}}
    status = 'local_requested'
    source = 'local'
    model = None
    if consent:
        if not os.getenv('GEMINI_API_KEY', '').strip():
            status = 'missing_key'
        else:
            try:
                selection, model = (request_fn or request_gemini)(inputs)
                source, status = 'gemini', 'ready'
            except urllib.error.HTTPError as error:
                status = 'provider_unavailable' if error.code not in (401, 403) else 'credential_rejected'
            except (TimeoutError, socket.timeout):
                status = 'timeout'
            except Exception:
                # Never expose provider exception strings, request headers, or secrets.
                status = 'invalid_or_unavailable_response'
    if source == 'local':
        actions = ['pause', 'reflect']
        focus = 'reflection'
        if inputs['workload'] == 'heavy':
            actions, focus = ['prioritize', 'connect'], 'workload'
        elif inputs['sleep_hours'] is not None and inputs['sleep_hours'] < 6:
            actions, focus = ['sleep_routine', 'pause'], 'rest'
        selection = Selection(focus=focus, actions=actions)
    return {'source': source, 'status': status, 'model': model,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'cloud_consent': consent,
            'summary': f"You reported {inputs['self_reported_stress']}/10 stress. {FOCUS[selection.focus]}",
            'actions': [ACTIONS[action] for action in selection.actions],
            'limitations': 'Based on your self-report, not a clinical assessment. Camera signals do not establish stress. If distress persists, consider qualified support.'}
