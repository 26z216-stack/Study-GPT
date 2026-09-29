import json
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import ai, db
from .models import Availability, Flashcard, StudySession, Subject, Topic
from .plan_service import (attach_times, availability_for, windows_for, owned_subject_or_404, owned_topic_or_404, plan_context,
                           readiness_by_subject, replan)

planner = Blueprint('planner', __name__)

WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
COLORS = ['#6C5CE7', '#00B894', '#E17055', '#0984E3', '#FDCB6E', '#E84393', '#00CEC9', '#2D3436']


def _int(value, lo, hi, default):
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def _float(value, lo, hi, default):
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def _date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() if value else None
    except ValueError:
        return None


# ── Dashboard ────────────────────────────────────────────────────────────────

@planner.route('/')
@login_required
def dashboard():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    if not subjects:
        return redirect(url_for('planner.subjects'))
    today = date.today()
    if current_user.last_replan != today:
        moved = replan(current_user, today)
        if moved:
            flash(f'You missed {moved} session(s). StudyGPT has rescheduled that work into your upcoming days.', 'info')

    todays = (StudySession.query.filter_by(user_id=current_user.id, date=today)
              .filter(StudySession.status != 'missed').order_by(StudySession.id).all())
    attach_times(current_user, todays)
    rows, overall = readiness_by_subject(current_user)
    upcoming_exams = sorted([s for s in subjects if s.exam_date and s.exam_date >= today],
                            key=lambda s: s.exam_date)
    due_cards = (Flashcard.query.join(Topic).join(Subject)
                 .filter(Subject.user_id == current_user.id, Flashcard.due <= today).count())
    planned_min = sum(s.minutes for s in todays)
    done_min = sum(s.minutes for s in todays if s.status == 'done')
    weak = (Topic.query.join(Subject).filter(Subject.user_id == current_user.id, Topic.status != 'done')
            .order_by(Topic.confidence, Topic.difficulty.desc()).limit(3).all())
    return render_template('dashboard.html', todays=todays, rows=rows, overall=overall,
                           upcoming_exams=upcoming_exams, due_cards=due_cards,
                           planned_min=planned_min, done_min=done_min, weak=weak, today=today)


@planner.route('/replan', methods=['POST'])
@login_required
def replan_now():
    moved = replan(current_user)
    msg = 'Plan regenerated from today.'
    if moved:
        msg += f' {moved} missed session(s) were redistributed.'
    flash(msg, 'success')
    return redirect(request.referrer or url_for('planner.dashboard'))


@planner.route('/session/<int:sid>/<action>', methods=['POST'])
@login_required
def session_action(sid, action):
    s = StudySession.query.filter_by(id=sid, user_id=current_user.id).first_or_404()
    if action == 'done':
        s.status = 'done'
        if s.topic.status == 'not_started':
            s.topic.status = 'in_progress'
        db.session.commit()
        flash(f'Nice! {s.minutes} min of {s.topic.name} done.', 'success')
    elif action == 'skip':
        s.status = 'missed'
        db.session.commit()
        replan(current_user)
        flash(f'Skipped. {s.topic.name} has been rescheduled into your upcoming days.', 'info')
    elif action == 'undo':
        s.status = 'planned'
        db.session.commit()
    if request.headers.get('Accept') == 'application/json':
        return jsonify(ok=True)
    return redirect(request.referrer or url_for('planner.dashboard'))


# ── Subjects & availability ──────────────────────────────────────────────────

@planner.route('/subjects', methods=['GET', 'POST'])
@login_required
def subjects():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Subject name is required.', 'error')
        else:
            count = Subject.query.filter_by(user_id=current_user.id).count()
            s = Subject(user_id=current_user.id, name=name[:100],
                        color=request.form.get('color') or COLORS[count % len(COLORS)],
                        difficulty=_int(request.form.get('difficulty'), 1, 5, 3),
                        priority=_int(request.form.get('priority'), 1, 5, 3),
                        exam_date=_date(request.form.get('exam_date')))
            db.session.add(s)
            db.session.commit()
            flash(f'{s.name} added. Now add its syllabus topics.', 'success')
            return redirect(url_for('planner.syllabus', subject_id=s.id))
    subs = Subject.query.filter_by(user_id=current_user.id).order_by(Subject.exam_date).all()
    return render_template('subjects.html', subjects=subs, avail=availability_for(current_user),
                           windows=windows_for(current_user), routine=current_user.routine or '',
                           weekdays=WEEKDAYS, next_color=COLORS[len(subs) % len(COLORS)])


@planner.route('/subjects/<int:subject_id>/edit', methods=['POST'])
@login_required
def edit_subject(subject_id):
    s = owned_subject_or_404(subject_id, current_user)
    s.name = (request.form.get('name') or s.name).strip()[:100]
    s.color = request.form.get('color') or s.color
    s.difficulty = _int(request.form.get('difficulty'), 1, 5, s.difficulty)
    s.priority = _int(request.form.get('priority'), 1, 5, s.priority)
    s.exam_date = _date(request.form.get('exam_date'))
    db.session.commit()
    replan(current_user)
    flash(f'{s.name} updated and plan regenerated.', 'success')
    return redirect(request.referrer or url_for('planner.subjects'))


@planner.route('/subjects/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete_subject(subject_id):
    s = owned_subject_or_404(subject_id, current_user)
    db.session.delete(s)
    db.session.commit()
    replan(current_user)
    flash('Subject deleted.', 'info')
    return redirect(url_for('planner.subjects'))


@planner.route('/availability', methods=['POST'])
@login_required
def save_availability():
    for d in range(7):
        hours = _float(request.form.get(f'day{d}'), 0, 16, 2)
        row = Availability.query.filter_by(user_id=current_user.id, weekday=d).first()
        if not row:
            row = Availability(user_id=current_user.id, weekday=d)
            db.session.add(row)
        row.minutes = int(round(hours * 60))
        row.windows = None   # manual hours replace any AI time windows
    db.session.commit()
    replan(current_user)
    flash('Availability saved and plan regenerated.', 'success')
    return redirect(url_for('planner.subjects'))


@planner.route('/availability/ai', methods=['POST'])
@login_required
def availability_ai():
    text = request.form.get('routine', '').strip()
    if len(text) < 10:
        flash('Describe your routine first.', 'error')
        return redirect(url_for('planner.subjects'))
    try:
        parsed = ai.parse_routine(text)
    except ai.AIError as e:
        flash(str(e), 'error')
        return redirect(url_for('planner.subjects'))
    for d, windows in parsed['days'].items():
        row = Availability.query.filter_by(user_id=current_user.id, weekday=d).first()
        if not row:
            row = Availability(user_id=current_user.id, weekday=d)
            db.session.add(row)
        row.windows = json.dumps(windows)
        row.minutes = min(8 * 60, sum(_mins(b) - _mins(a) for a, b in windows))   # never plan more than 8h a day
    current_user.routine = text
    db.session.commit()
    replan(current_user)
    flash('✨ ' + (parsed['summary'] or 'Your routine is set.') + ' Your timetable now has real clock times.', 'success')
    return redirect(url_for('planner.timetable'))


def _mins(hhmm):
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)


# ── Syllabus ─────────────────────────────────────────────────────────────────

@planner.route('/subjects/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def syllabus(subject_id):
    s = owned_subject_or_404(subject_id, current_user)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            db.session.add(Topic(subject_id=s.id, name=name[:200],
                                 difficulty=_int(request.form.get('difficulty'), 1, 5, 3),
                                 est_hours=_float(request.form.get('est_hours'), 0.5, 40, 2)))
            db.session.commit()
            replan(current_user)
        return redirect(url_for('planner.syllabus', subject_id=s.id))
    return render_template('syllabus.html', subject=s)


@planner.route('/subjects/<int:subject_id>/import', methods=['POST'])
@login_required
def import_syllabus(subject_id):
    s = owned_subject_or_404(subject_id, current_user)
    text = request.form.get('syllabus', '').strip()
    if len(text) < 10:
        flash('Paste your syllabus text first.', 'error')
        return redirect(url_for('planner.syllabus', subject_id=s.id))
    try:
        topics = ai.split_syllabus(s.name, text)
    except ai.AIError as e:
        flash(str(e), 'error')
        return redirect(url_for('planner.syllabus', subject_id=s.id))
    for t in topics:
        db.session.add(Topic(subject_id=s.id, **t))
    db.session.commit()
    replan(current_user)
    flash(f'AI added {len(topics)} topics with difficulty and time estimates. Adjust anything that looks off.',
          'success')
    return redirect(url_for('planner.syllabus', subject_id=s.id))


@planner.route('/topics/<int:topic_id>/edit', methods=['POST'])
@login_required
def edit_topic(topic_id):
    t = owned_topic_or_404(topic_id, current_user)
    t.name = (request.form.get('name') or t.name).strip()[:200]
    t.difficulty = _int(request.form.get('difficulty'), 1, 5, t.difficulty)
    t.est_hours = _float(request.form.get('est_hours'), 0.5, 40, t.est_hours)
    t.confidence = _int(request.form.get('confidence'), 0, 100, t.confidence)
    status = request.form.get('status')
    if status in ('not_started', 'in_progress', 'done'):
        t.status = status
    db.session.commit()
    replan(current_user)
    if request.headers.get('Accept') == 'application/json':
        return jsonify(ok=True)
    return redirect(request.referrer or url_for('planner.syllabus', subject_id=t.subject_id))


@planner.route('/topics/<int:topic_id>/delete', methods=['POST'])
@login_required
def delete_topic(topic_id):
    t = owned_topic_or_404(topic_id, current_user)
    sid = t.subject_id
    db.session.delete(t)
    db.session.commit()
    replan(current_user)
    return redirect(url_for('planner.syllabus', subject_id=sid))


# ── Timetable ────────────────────────────────────────────────────────────────

@planner.route('/timetable')
@login_required
def timetable():
    offset = _int(request.args.get('week'), -52, 52, 0)
    today = date.today()
    start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    days = [start + timedelta(days=i) for i in range(7)]
    sessions = (StudySession.query.filter(StudySession.user_id == current_user.id,
                                          StudySession.date >= days[0], StudySession.date <= days[-1])
                .order_by(StudySession.date, StudySession.id).all())
    attach_times(current_user, sessions)
    by_day = {d: [] for d in days}
    for s in sessions:
        by_day[s.date].append(s)
    exams = {s.exam_date: s for s in Subject.query.filter_by(user_id=current_user.id) if s.exam_date}
    avail = availability_for(current_user)
    return render_template('timetable.html', days=days, by_day=by_day, exams=exams, offset=offset,
                           today=today, avail=avail, windows=windows_for(current_user))


@planner.route('/timetable.ics')
@login_required
def timetable_ics():
    """Calendar export: each planned session as an all-day-ish event starting 18:00."""
    sessions = (StudySession.query.filter(StudySession.user_id == current_user.id,
                                          StudySession.status == 'planned',
                                          StudySession.date >= date.today())
                .order_by(StudySession.date, StudySession.id).all())
    attach_times(current_user, sessions)
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//StudyGPT//Study Planner//EN', 'X-WR-CALNAME:StudyGPT study plan']
    cursor = {}
    for s in sessions:
        start = cursor.get(s.date, datetime.combine(s.date, datetime.min.time()).replace(hour=18))
        if s.start:
            start = datetime.combine(s.date, datetime.strptime(s.start, '%H:%M').time())
        end = start + timedelta(minutes=s.minutes)
        cursor[s.date] = end
        title = f'{"Revise" if s.kind == "revision" else "Study"}: {s.topic.subject.name} - {s.topic.name}'
        lines += ['BEGIN:VEVENT', f'UID:studygpt-{s.id}@studygpt', f'DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}',
                  f'DTSTART:{start:%Y%m%dT%H%M%S}', f'DTEND:{end:%Y%m%dT%H%M%S}',
                  'SUMMARY:' + title.replace(',', '\\,').replace(';', '\\;'), 'END:VEVENT']
    for s in Subject.query.filter_by(user_id=current_user.id):
        if s.exam_date and s.exam_date >= date.today():
            lines += ['BEGIN:VEVENT', f'UID:studygpt-exam-{s.id}@studygpt', f'DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}',
                      f'DTSTART;VALUE=DATE:{s.exam_date:%Y%m%d}', f'SUMMARY:EXAM: {s.name}', 'END:VEVENT']
    lines.append('END:VCALENDAR')
    return Response('\r\n'.join(lines), mimetype='text/calendar',
                    headers={'Content-Disposition': 'attachment; filename=studygpt-plan.ics'})


# ── Report ───────────────────────────────────────────────────────────────────

@planner.route('/report')
@login_required
def report():
    rows, overall = readiness_by_subject(current_user)
    done = StudySession.query.filter_by(user_id=current_user.id, status='done').all()
    missed = StudySession.query.filter_by(user_id=current_user.id, status='missed').count()
    total_done = len(done)
    minutes_done = sum(s.minutes for s in done)
    adherence = round(100 * total_done / (total_done + missed)) if (total_done + missed) else None
    return render_template('report.html', rows=rows, overall=overall, minutes_done=minutes_done,
                           sessions_done=total_done, missed=missed, adherence=adherence)


@planner.route('/report/ai', methods=['POST'])
@login_required
def report_ai():
    try:
        return jsonify(ai.readiness_summary(plan_context(current_user)))
    except ai.AIError as e:
        return jsonify(error=str(e)), 502


# ── Focus timer ──────────────────────────────────────────────────────────────

@planner.route('/focus')
@login_required
def focus():
    sid = request.args.get('session', type=int)
    session = StudySession.query.filter_by(id=sid, user_id=current_user.id).first() if sid else None
    return render_template('focus.html', session=session)
