"""Gemini calls. Every helper returns parsed JSON or raises AIError with a user-facing message."""
import json
import os

import requests

MODEL_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'


class AIError(Exception):
    pass


def ask_json(prompt, timeout=60):
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise AIError('AI is not configured. Add GEMINI_API_KEY to your .env file.')
    try:
        resp = requests.post(
            MODEL_URL,
            params={'key': api_key},
            json={'contents': [{'parts': [{'text': prompt}]}],
                  # thinkingBudget 0 turns off 2.5 Flash's reasoning pass: ~5x faster, fine for these tasks
                  'generationConfig': {'responseMimeType': 'application/json',
                                       'thinkingConfig': {'thinkingBudget': 0}}},
            timeout=timeout,
        )
        resp.raise_for_status()
        text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text)
    except requests.RequestException as e:
        raise AIError(f'The AI service could not be reached ({e.__class__.__name__}). Try again.') from e
    except (KeyError, IndexError, ValueError) as e:
        raise AIError('The AI returned an unexpected answer. Try again.') from e


def split_syllabus(subject_name, syllabus_text):
    data = ask_json(f"""You are helping a student plan study for the subject "{subject_name}".
Split this syllabus into study topics. Merge tiny items, split huge units. Aim for 4-15 topics.

Syllabus:
{syllabus_text[:8000]}

Return JSON: {{"topics": [{{"name": str, "difficulty": 1-5, "est_hours": number}}]}}
difficulty 5 = hardest. est_hours = realistic hours for a student to learn it well (0.5 to 10).""")
    topics = []
    for t in data.get('topics', []):
        name = str(t.get('name', '')).strip()[:200]
        if name:
            topics.append({'name': name,
                           'difficulty': _clamp(t.get('difficulty'), 1, 5, 3),
                           'est_hours': _clamp_hours(t.get('est_hours'))})
    if not topics:
        raise AIError('The AI could not find topics in that text.')
    return topics


def make_quiz(subject_name, topic_name, n=5):
    data = ask_json(f"""Write a {n}-question multiple choice quiz on "{topic_name}" ({subject_name}).
Mix recall and understanding questions. Exactly 4 options each, one correct.
Return JSON: {{"questions": [{{"q": str, "options": [str, str, str, str], "answer": 0-3, "why": str}}]}}""")
    qs = [q for q in data.get('questions', [])
          if isinstance(q.get('options'), list) and len(q['options']) == 4
          and isinstance(q.get('answer'), int) and 0 <= q['answer'] <= 3]
    if not qs:
        raise AIError('The AI did not return a usable quiz. Try again.')
    return qs[:n]


def make_flashcards(subject_name, topic_name, n=8):
    data = ask_json(f"""Create {n} flashcards for studying "{topic_name}" ({subject_name}).
Front: a short question or term. Back: a concise answer (max 2 sentences).
Return JSON: {{"cards": [{{"front": str, "back": str}}]}}""")
    cards = [c for c in data.get('cards', []) if c.get('front') and c.get('back')]
    if not cards:
        raise AIError('The AI did not return flashcards. Try again.')
    return cards[:n]


def feynman_feedback(subject_name, topic_name, explanation):
    data = ask_json(f"""A student is using the Feynman Technique: explaining "{topic_name}" ({subject_name})
in simple words, as if teaching a 12-year-old. Evaluate their explanation honestly and kindly.

Explanation:
\"\"\"{explanation[:4000]}\"\"\"

Return JSON: {{
  "score": 0-100 (how complete and correct the understanding is),
  "strengths": [str],
  "gaps": [str]  (important ideas missing),
  "misconceptions": [str] (things stated wrongly; empty if none),
  "jargon": [str] (terms used without explaining them),
  "analogy": str (one simple analogy that would help),
  "next_step": str (one concrete thing to study next)
}}""")
    data['score'] = _clamp(data.get('score'), 0, 100, 0)
    for key in ('strengths', 'gaps', 'misconceptions', 'jargon'):
        data[key] = [str(x) for x in data.get(key) or []]
    data['analogy'] = str(data.get('analogy') or '')
    data['next_step'] = str(data.get('next_step') or '')
    return data


def coach_reply(context, history, message):
    convo = '\n'.join(f"{m['role'].upper()}: {m['content']}" for m in history[-10:])
    data = ask_json(f"""You are Kanal, a warm, practical AI study coach. Use the student's real plan below.
Be specific (name subjects, topics, dates). Keep answers under 150 words. Use short bullet points when listing.
If they are behind, suggest what to cut or reprioritise. Never invent topics that aren't in the plan.

STUDENT DATA:
{context}

CONVERSATION SO FAR:
{convo}

STUDENT: {message}

Return JSON: {{"reply": str}}""")
    reply = str(data.get('reply', '')).strip()
    if not reply:
        raise AIError('The coach had nothing to say. Try rephrasing.')
    return reply


def readiness_summary(context):
    data = ask_json(f"""You are a study coach writing a short exam-readiness report.

STUDENT DATA:
{context}

Return JSON: {{"headline": str (one sentence), "focus": [str] (3 concrete priorities for the next 3 days),
"risk": str (the biggest risk to their exams, one sentence)}}""")
    return {'headline': str(data.get('headline', '')),
            'focus': [str(x) for x in data.get('focus') or []][:3],
            'risk': str(data.get('risk', ''))}


def parse_routine(routine_text):
    """Turn a plain-language weekly routine into free study windows per weekday."""
    data = ask_json(f"""A student describes their weekly routine. Work out the time windows each day when
they are FREE TO STUDY. Leave out sleep, classes, commute, meals, exercise and anything else they mention.
Leave a short gap after classes/commute/exercise, but DO include the free time after an activity ends
(e.g. gym 6-7pm and sleep at 11pm -> free roughly 7:30-10:30pm). Leave time for dinner. Respect any stated preferences (e.g. "I study best in the morning",
"max 3 hours a day", "keep Sunday light"). If they don't mention a day, assume a sensible evening window.
Don't make the total study time unrealistic: at most 8h on any day, and usually 1-4h on weekdays.

Routine:
\"\"\"{routine_text[:3000]}\"\"\"

Return JSON: {{
  "days": {{"0": [["HH:MM", "HH:MM"], ...], ..., "6": [...]}}  (0=Monday ... 6=Sunday, 24h time, empty list = no study),
  "peak": "morning" | "afternoon" | "evening" | "night" (when they focus best; guess if not stated),
  "summary": str (one friendly sentence describing the plan's shape)
}}""")
    days = {}
    for d in range(7):
        windows = []
        for w in (data.get('days') or {}).get(str(d)) or []:
            try:
                start, end = _to_min(w[0]), _to_min(w[1])
            except (TypeError, ValueError, IndexError):
                continue
            if end - start >= 30:
                windows.append([_fmt(start), _fmt(end)])
        days[d] = sorted(windows)
    if not any(days.values()):
        raise AIError('The AI could not find any free time in that routine. Add a bit more detail.')
    return {'days': days, 'peak': str(data.get('peak') or ''), 'summary': str(data.get('summary') or '')}


def _to_min(hhmm):
    h, m = str(hhmm).strip().split(':')
    h, m = int(h), int(m)
    if not (0 <= h <= 24 and 0 <= m < 60):
        raise ValueError(hhmm)
    return min(24 * 60, h * 60 + m)


def _fmt(minutes):
    minutes = min(minutes, 24 * 60 - 1)
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _clamp_hours(value):
    try:
        return round(max(0.5, min(10.0, float(value))) * 2) / 2
    except (TypeError, ValueError):
        return 2.0


def _clamp(value, lo, hi, default):
    try:
        return max(lo, min(hi, int(round(float(value)))))
    except (TypeError, ValueError):
        return default
