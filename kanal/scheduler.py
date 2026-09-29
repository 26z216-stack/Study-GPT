"""Deterministic study-plan builder. Pure functions over plain dicts, no DB.

A topic's score says how much it deserves the next block of study time:

    urgency x (topic difficulty + subject priority) x (1 - confidence)

where urgency = 1 / days until that subject's exam. Days are filled greedily
with 30-60 minute blocks, re-scoring after every block so work interleaves
across topics instead of finishing one topic at a time.
"""
from datetime import timedelta

BLOCK_MIN = 30
BLOCK_MAX = 60
NO_EXAM_HORIZON_DAYS = 28   # subjects without an exam date are planned over 4 weeks
MAX_HORIZON_DAYS = 90
SAME_DAY_PENALTY = 0.35     # each block a topic already has today scales its score by this


def _round_up(minutes, step=BLOCK_MIN):
    return -(-minutes // step) * step


def remaining_minutes(topic):
    """Minutes of study the topic still needs, in whole 30-minute blocks."""
    if topic['status'] == 'done':
        return 0
    need = max(0, (topic.get('est_hours') or 2) * 60 - topic.get('done_minutes', 0))
    need = need * (1 - (topic.get('confidence') or 0) / 100)
    return max(BLOCK_MIN, _round_up(int(round(need))))


def exam_date_of(subject, today):
    return subject.get('exam_date') or today + timedelta(days=NO_EXAM_HORIZON_DAYS)


def topic_score(topic, subject, day):
    days_left = max(1, (exam_date_of(subject, day) - day).days)
    urgency = 1 / days_left
    weight = (topic.get('difficulty') or 3) + (subject.get('priority') or 3)
    gap = 1 - (topic.get('confidence') or 0) / 100
    return urgency * weight * max(gap, 0.05)


def build_plan(subjects, topics, availability, today, used_today=0):
    """Return a list of {date, topic_id, subject_id, minutes, kind} from today onward.

    availability maps weekday (0=Mon) to minutes available that day;
    used_today is minutes already studied today, taken off today's budget.
    """
    subj_by_id = {s['id']: s for s in subjects}
    exams = {s['id']: exam_date_of(s, today) for s in subjects}
    topics = [t for t in topics if t['subject_id'] in subj_by_id]
    remaining = {t['id']: remaining_minutes(t) for t in topics}
    if not topics or not exams:
        return []

    last_day = min(max(exams.values()), today + timedelta(days=MAX_HORIZON_DAYS))
    plan = []
    day = today
    while day < last_day:
        budget = availability.get(day.weekday(), 0) - (used_today if day == today else 0)
        cap = (max(0, budget) // BLOCK_MIN) * BLOCK_MIN
        today_count = {}

        # Revision block the day before each exam, on its weakest topic.
        for sid, exam in exams.items():
            if cap >= BLOCK_MIN and exam - timedelta(days=1) == day and subj_by_id[sid].get('exam_date'):
                subj_topics = [t for t in topics if t['subject_id'] == sid]
                if not subj_topics:
                    continue
                weakest = min(subj_topics, key=lambda t: t.get('confidence') or 0)
                minutes = min(BLOCK_MAX, cap)
                plan.append({'date': day, 'topic_id': weakest['id'], 'subject_id': sid,
                             'minutes': minutes, 'kind': 'revision'})
                cap -= minutes

        while cap >= BLOCK_MIN:
            candidates = [t for t in topics if remaining[t['id']] > 0 and day < exams[t['subject_id']]]
            if not candidates:
                break
            best = max(candidates, key=lambda t: topic_score(t, subj_by_id[t['subject_id']], day)
                       * SAME_DAY_PENALTY ** today_count.get(t['id'], 0))
            minutes = min(BLOCK_MAX, remaining[best['id']], cap)
            plan.append({'date': day, 'topic_id': best['id'], 'subject_id': best['subject_id'],
                         'minutes': minutes, 'kind': 'study'})
            remaining[best['id']] -= minutes
            today_count[best['id']] = today_count.get(best['id'], 0) + 1
            cap -= minutes
        day += timedelta(days=1)

    return _merge_adjacent(plan)


def _merge_adjacent(plan):
    """Join back-to-back blocks of the same topic and kind on the same day."""
    merged = []
    for s in plan:
        prev = merged[-1] if merged else None
        if prev and prev['date'] == s['date'] and prev['topic_id'] == s['topic_id'] and prev['kind'] == s['kind']:
            prev['minutes'] += s['minutes']
        else:
            merged.append(dict(s))
    return merged
