# Kanal: AI-Powered Study Planner (design)

**Problem statement:** A smart application that generates personalized study schedules based on exam dates, subjects, and available time.

**Deadline:** demo on 2026-09-30. Ideas are borrowed from Monad (Subject/Exam models, minute-based day blocks, focus timer core, `_gemini_call`), but Kanal is a new, much smaller app.

## Stack
- Flask 3, Flask-SQLAlchemy (SQLite at `instance/kanal.db`), Flask-Login, Flask-WTF CSRF.
- Jinja templates, one stylesheet, vanilla JS.
- Gemini 2.5 Flash through REST (`GEMINI_API_KEY`) with JSON output. Every AI feature has a clear error message when the key is missing or the call fails.
- Runs locally: `python start.py`.

## Data model
- `User`: email, password hash, name.
- `Subject`: name, color, difficulty 1–5, priority 1–5, exam_date.
- `Topic`: subject, name, difficulty 1–5, status (`not_started`/`in_progress`/`done`), confidence 0–100, est_hours.
- `Availability`: user, weekday 0–6, minutes.
- `StudySession`: user, topic, date, minutes, kind (`study`/`revision`), status (`planned`/`done`/`missed`).
- `QuizAttempt`: topic, score, total.
- `Flashcard`: topic, front, back, ease, interval, repetitions, due.
- `FeynmanAttempt`: topic, explanation, feedback JSON, score.
- `ChatMessage`: user, role, content.

## Scheduler (`kanal/scheduler.py`, pure Python, unit-tested)
- **Topic score:** `urgency × (topic.difficulty + subject.priority) × (1 − confidence/100)`, where `urgency = 1 / max(1, days_to_exam)`.
- **Remaining work per topic:** `est_hours × 60 × (1 − confidence/100)`. The minimum is one 30-minute block for any topic that isn't done.
- **Filling days:** for each day from today until the last exam, fill that weekday's available minutes with 30–60 minute blocks.
  - Blocks are handed out greedily by score.
  - Scores are recomputed after every block, so work interleaves across subjects.
  - A subject stops being scheduled once its exam date is reached.
  - The day before each exam gets a revision block for that subject first.
- **Rescheduling** (`replan(user)`):
  1. Past `planned` sessions become `missed`.
  2. Future `planned` sessions are deleted.
  3. New sessions are generated from today, while `done` sessions are kept.
- Rescheduling is triggered by:
  - opening the dashboard (at most once per day, or when data is marked as changed),
  - the Reschedule button,
  - editing a topic, subject, availability or confidence,
  - completing a quiz or a Feynman attempt.

## Learning loop
- **Quiz:** 5 AI multiple-choice questions. The topic's new confidence is `0.5 × old + 0.5 × score%`, and a replan follows.
- **Flashcards:** AI-generated. Reviews use SM-2 (`kanal/srs.py`, unit-tested) with Again/Hard/Good/Easy buttons. The dashboard shows how many cards are due.
- **Feynman:** the student explains the topic, and the AI returns gaps, misconceptions, a simpler analogy and a score from 0–100. Confidence then blends the same way as for a quiz.
- **Readiness** (`kanal/readiness.py`, unit-tested): per subject, `0.4 × done-topic ratio + 0.6 × average confidence`. An AI summary is available on the report page.
- **Coach:** chat about the plan. The AI receives the plan and progress as context and has no tools.

## Pages
- Login / Signup
- Dashboard
- Subjects (with exam date and availability)
- Syllabus (per subject, including AI import from pasted text)
- Timetable (14 days)
- Topic (quiz, flashcards, Feynman)
- Review (flashcards due)
- Report
- Coach
- Focus timer

Extras: a light/dark theme toggle, a daily quote, and `.ics` export of the timetable.

## Build order
1. Auth, subjects, syllabus, scheduler, timetable, dashboard.
2. Quiz and readiness.
3. Flashcards/SRS and Feynman.
4. Coach and focus timer.
5. Theme, quotes and `.ics` export.

## Testing
`python -m unittest` covers the scheduler, SRS and readiness. Everything else is checked by hand in the browser.
