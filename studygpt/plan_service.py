"""Glue between the DB and the pure scheduler / readiness modules."""
import json
from collections import defaultdict
from datetime import date

from . import db
from .models import Availability, StudySession, Subject, Topic
from .clock import assign_times
from .readiness import overall_readiness, subject_readiness
from .scheduler import build_plan

DEFAULT_MINUTES = 120


def availability_for(user):
    rows = {a.weekday: a.minutes for a in Availability.query.filter_by(user_id=user.id)}
    return {d: rows.get(d, DEFAULT_MINUTES) for d in range(7)}


def windows_for(user):
    """Free-time windows per weekday from the AI routine parser ({} if never set)."""
    out = {}
    for a in Availability.query.filter_by(user_id=user.id):
        if a.windows:
            try:
                out[a.weekday] = json.loads(a.windows)
            except ValueError:
                pass
    return out


def attach_times(user, sessions):
    """Set .start/.end on each non-missed session, grouped by day, laid into that day's windows."""
    windows = windows_for(user)
    by_day = defaultdict(list)
    for s in sessions:
        s.start = s.end = None
        if s.status != 'missed':
            by_day[s.date].append(s)
    for day, items in by_day.items():
        if windows.get(day.weekday()):
            for s, t in zip(items, assign_times([s.minutes for s in items], windows[day.weekday()])):
                if t:
                    s.start, s.end = t
    return sessions


def replan(user, today=None):
    """Mark overdue sessions missed, then rebuild every future planned session.

    Returns how many overdue sessions were marked missed (their work is
    automatically redistributed into the new plan).
    """
    today = today or date.today()
    overdue = StudySession.query.filter(StudySession.user_id == user.id,
                                        StudySession.status == 'planned',
                                        StudySession.date < today).all()
    for s in overdue:
        s.status = 'missed'
    StudySession.query.filter(StudySession.user_id == user.id,
                              StudySession.status == 'planned',
                              StudySession.date >= today).delete(synchronize_session=False)

    subjects = Subject.query.filter_by(user_id=user.id).all()
    done_minutes = defaultdict(int)
    used_today = 0
    for s in StudySession.query.filter_by(user_id=user.id, status='done'):
        if s.kind == 'study':
            done_minutes[s.topic_id] += s.minutes
        if s.date == today:
            used_today += s.minutes

    topics = [{'id': t.id, 'subject_id': t.subject_id, 'difficulty': t.difficulty,
               'confidence': t.confidence, 'est_hours': t.est_hours, 'status': t.status,
               'done_minutes': done_minutes[t.id]}
              for s in subjects for t in s.topics]
    subj_dicts = [{'id': s.id, 'priority': s.priority, 'exam_date': s.exam_date} for s in subjects]

    for block in build_plan(subj_dicts, topics, availability_for(user), today, used_today=used_today):
        db.session.add(StudySession(user_id=user.id, topic_id=block['topic_id'], date=block['date'],
                                    minutes=block['minutes'], kind=block['kind']))
    user.last_replan = today
    db.session.commit()
    return len(overdue)


def update_confidence(topic, percent):
    """Blend a new measurement (quiz / Feynman score) into the topic's confidence."""
    percent = max(0, min(100, int(percent)))
    if topic.status == 'not_started' and not topic.confidence:
        topic.confidence = percent
    else:
        topic.confidence = round(0.5 * (topic.confidence or 0) + 0.5 * percent)
    if topic.status == 'not_started':
        topic.status = 'in_progress'


def readiness_by_subject(user):
    subjects = Subject.query.filter_by(user_id=user.id).order_by(Subject.exam_date).all()
    rows = []
    for s in subjects:
        ts = [{'status': t.status, 'confidence': t.confidence} for t in s.topics]
        rows.append({'subject': s, 'readiness': subject_readiness(ts),
                     'done': sum(1 for t in s.topics if t.status == 'done'), 'total': len(s.topics)})
    overall = overall_readiness([[{'status': t.status, 'confidence': t.confidence} for t in s.topics]
                                 for s in subjects])
    return rows, overall


def plan_context(user):
    """Compact text description of the student's plan for AI prompts."""
    today = date.today()
    lines = [f'Today: {today:%A %d %B %Y}. Student: {user.name}.']
    rows, overall = readiness_by_subject(user)
    lines.append(f'Overall readiness: {overall}%.')
    for r in rows:
        s = r['subject']
        exam = f'exam {s.exam_date:%d %b} ({s.days_left} days left)' if s.exam_date else 'no exam date'
        lines.append(f'\nSUBJECT {s.name}: {exam}, priority {s.priority}/5, readiness {r["readiness"]}%, '
                     f'{r["done"]}/{r["total"]} topics done.')
        for t in s.topics:
            lines.append(f'  - {t.name}: {t.status}, confidence {t.confidence}%, difficulty {t.difficulty}/5')
    upcoming = (StudySession.query.filter(StudySession.user_id == user.id, StudySession.date >= today,
                                          StudySession.status == 'planned')
                .order_by(StudySession.date).limit(12).all())
    if upcoming:
        lines.append('\nNEXT PLANNED SESSIONS:')
        for s in upcoming:
            lines.append(f'  {s.date:%a %d %b}: {s.topic.subject.name} / {s.topic.name}, {s.minutes} min ({s.kind})')
    missed = StudySession.query.filter_by(user_id=user.id, status='missed').count()
    done = StudySession.query.filter_by(user_id=user.id, status='done').count()
    lines.append(f'\nSessions completed: {done}, missed: {missed}.')
    wins = windows_for(user)
    if wins:
        lines.append('Free study windows: ' + '; '.join(
            f"{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d]} " + ', '.join(f'{a}-{b}' for a, b in wins[d])
            for d in sorted(wins) if wins[d]))
    avail = availability_for(user)
    lines.append('Daily availability (min): ' + ', '.join(
        f'{d}={avail[i]}' for i, d in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])))
    return '\n'.join(lines)


def owned_topic_or_404(topic_id, user):
    return (Topic.query.join(Subject).filter(Topic.id == topic_id, Subject.user_id == user.id)
            .first_or_404())


def owned_subject_or_404(subject_id, user):
    return Subject.query.filter_by(id=subject_id, user_id=user.id).first_or_404()
