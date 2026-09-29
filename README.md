# Kanal: AI-Powered Study Planner

**A smart study planner that generates a personalized, self-adjusting study schedule from your exam dates, syllabus, and free time.**

Tell Kanal your subjects, exam dates, the topics in each syllabus, and how many hours you can study each day. It builds a day-by-day timetable that puts the most urgent, hardest and weakest topics first. When you miss a session, score low on a quiz, or finish a topic early, it re-plans automatically.

## Features

| Feature | How it works |
|---|---|
| 🧠 **Personalized timetable** | A deterministic scheduler fills each day's available minutes with 30–60 min study blocks, ranked by urgency, difficulty, priority and confidence. |
| 🔄 **Automatic rescheduling** | Overdue sessions are marked *missed* and their work is redistributed into future days. This happens daily, on **Skip**, and whenever you change the syllabus, availability or a quiz score. |
| 🎯 **Difficulty + priority** | Every subject has a priority (1–5), and every subject and topic has a difficulty (1–5). Both feed directly into the scheduling score. |
| 📚 **Syllabus tracker** | Topics with status, time estimate and confidence. **Paste your syllabus and AI splits it into topics**, with a difficulty and an hours estimate for each. |
| 🤖 **AI quiz generator** | 5 MCQs per topic with explanations. The score updates the topic's confidence, which re-prioritises the plan. |
| 🃏 **Flashcards + 🔁 spaced repetition** | AI-generated or your own cards, reviewed with the SM-2 algorithm (Again / Hard / Good / Easy, keys 1–4). |
| 🧠 **Feynman Technique** | Explain a topic in simple words. The AI returns your strengths, gaps, misconceptions, unexplained jargon and an analogy, plus a score that feeds into confidence. |
| 📊 **Exam readiness report** | Per-subject readiness (40% syllabus coverage + 60% measured confidence), study hours, plan adherence, and an AI "next 3 days" analysis. |
| 💬 **AI study coach** | A chatbot that sees your actual plan, exam dates and weak topics. |
| ⏱️ **Focus timer** | Pomodoro / deep-work timer linked to a planned session. It keeps running across page reloads. |
| 📅 **Calendar export** | `.ics` export of the timetable and exams for Google Calendar or Outlook. |
| 🎨 **Theme** / 💬 **Quotes** | Light/dark mode and a daily motivational quote. |

## How the scheduler decides

```
score(topic, day) = urgency × (topic difficulty + subject priority) × (1 − confidence)
urgency           = 1 / days until that subject's exam
remaining work    = estimated hours × (1 − confidence) − minutes already studied
```

- Each day is filled greedily up to that weekday's available minutes, re-scoring after every block.
- A topic already scheduled that day is penalised, so subjects interleave instead of cramming one topic.
- The day before each exam gets a revision block on that subject's weakest topic.
- Nothing is scheduled for a subject on or after its exam day.

The scheduler is plain Python ([kanal/scheduler.py](kanal/scheduler.py)) and unit-tested. The AI is used where it adds value (reading syllabi, generating questions, giving feedback and coaching), not for the core planning logic.

## Tech stack

- Flask 3, Flask-SQLAlchemy (SQLite), Flask-Login, Flask-WTF (CSRF)
- Jinja templates, vanilla JS, a responsive layout (desktop sidebar, bottom nav on mobile)
- Google Gemini 2.5 Flash via REST, returning JSON

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env          # then put your GEMINI_API_KEY in .env
python seed_demo.py             # optional: demo account demo@kanal.app / demo123
python start.py                 # http://localhost:5000
```

Get a free Gemini key at https://aistudio.google.com/apikey. Without a key, everything except the AI features still works.

## Tests

```bash
python -m unittest discover -s tests -t .
```

The tests cover the scheduler, spaced repetition, readiness, and an end-to-end flow through every page with the AI stubbed out.

## Project layout

```
kanal/
  scheduler.py     # pure scheduling algorithm
  srs.py           # SM-2 spaced repetition
  readiness.py     # exam readiness score
  plan_service.py  # DB <-> scheduler glue, auto-rescheduling, AI context
  ai.py            # Gemini prompts (syllabus, quiz, flashcards, Feynman, coach, report)
  planner.py       # dashboard, subjects, syllabus, timetable, report, focus routes
  learn.py         # quiz, flashcards, review, Feynman routes
  coach.py         # chatbot routes
  auth.py          # signup / login
  templates/ static/
tests/
seed_demo.py
```
