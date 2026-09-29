import json
from datetime import date

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from . import ai, db
from .models import FeynmanAttempt, Flashcard, QuizAttempt, Subject, Topic
from .plan_service import owned_topic_or_404, replan, update_confidence
from .srs import GRADES, review

learn = Blueprint('learn', __name__)


@learn.route('/topic/<int:topic_id>')
@login_required
def topic(topic_id):
    t = owned_topic_or_404(topic_id, current_user)
    quizzes = sorted(t.quizzes, key=lambda q: q.created_at, reverse=True)[:5]
    feynmans = sorted(t.feynmans, key=lambda f: f.created_at, reverse=True)[:3]
    for f in feynmans:
        f.parsed = json.loads(f.feedback) if f.feedback else {}
    due = sum(1 for c in t.flashcards if c.due <= date.today())
    return render_template('topic.html', topic=t, quizzes=quizzes, feynmans=feynmans, due=due,
                           tab=request.args.get('tab', 'quiz'))


# ── Quiz ─────────────────────────────────────────────────────────────────────

@learn.route('/topic/<int:topic_id>/quiz', methods=['POST'])
@login_required
def quiz_generate(topic_id):
    t = owned_topic_or_404(topic_id, current_user)
    try:
        return jsonify(questions=ai.make_quiz(t.subject.name, t.name))
    except ai.AIError as e:
        return jsonify(error=str(e)), 502


@learn.route('/topic/<int:topic_id>/quiz/submit', methods=['POST'])
@login_required
def quiz_submit(topic_id):
    t = owned_topic_or_404(topic_id, current_user)
    data = request.get_json(silent=True) or {}
    total = max(1, int(data.get('total') or 1))
    score = max(0, min(total, int(data.get('score') or 0)))
    before = t.confidence
    db.session.add(QuizAttempt(topic_id=t.id, score=score, total=total))
    update_confidence(t, 100 * score / total)
    db.session.commit()
    replan(current_user)
    return jsonify(confidence_before=before, confidence=t.confidence)


# ── Flashcards ───────────────────────────────────────────────────────────────

@learn.route('/topic/<int:topic_id>/flashcards', methods=['POST'])
@login_required
def flashcards_generate(topic_id):
    t = owned_topic_or_404(topic_id, current_user)
    try:
        cards = ai.make_flashcards(t.subject.name, t.name)
    except ai.AIError as e:
        return jsonify(error=str(e)), 502
    for c in cards:
        db.session.add(Flashcard(topic_id=t.id, front=str(c['front'])[:1000], back=str(c['back'])[:2000]))
    db.session.commit()
    return jsonify(added=len(cards))


@learn.route('/topic/<int:topic_id>/flashcards/add', methods=['POST'])
@login_required
def flashcard_add(topic_id):
    t = owned_topic_or_404(topic_id, current_user)
    front = request.form.get('front', '').strip()
    back = request.form.get('back', '').strip()
    if front and back:
        db.session.add(Flashcard(topic_id=t.id, front=front, back=back))
        db.session.commit()
    return jsonify(ok=True)


@learn.route('/review')
@login_required
def review_page():
    q = (Flashcard.query.join(Topic).join(Subject)
         .filter(Subject.user_id == current_user.id, Flashcard.due <= date.today()))
    topic_id = request.args.get('topic', type=int)
    if topic_id:
        q = q.filter(Flashcard.topic_id == topic_id)
    cards = q.order_by(Flashcard.due, Flashcard.id).limit(50).all()
    payload = [{'id': c.id, 'front': c.front, 'back': c.back, 'topic': c.topic.name,
                'subject': c.topic.subject.name, 'color': c.topic.subject.color} for c in cards]
    upcoming = (Flashcard.query.join(Topic).join(Subject)
                .filter(Subject.user_id == current_user.id, Flashcard.due > date.today()).count())
    return render_template('review.html', cards=payload, upcoming=upcoming)


@learn.route('/flashcard/<int:card_id>/review', methods=['POST'])
@login_required
def flashcard_review(card_id):
    c = (Flashcard.query.join(Topic).join(Subject)
         .filter(Flashcard.id == card_id, Subject.user_id == current_user.id).first_or_404())
    grade = (request.get_json(silent=True) or {}).get('grade')
    if grade not in GRADES:
        return jsonify(error='bad grade'), 400
    state = review({'ease': c.ease, 'interval': c.interval, 'repetitions': c.repetitions}, grade, date.today())
    c.ease, c.interval, c.repetitions, c.due = state['ease'], state['interval'], state['repetitions'], state['due']
    db.session.commit()
    return jsonify(interval=c.interval, due=c.due.isoformat())


# ── Feynman ──────────────────────────────────────────────────────────────────

@learn.route('/topic/<int:topic_id>/feynman', methods=['POST'])
@login_required
def feynman(topic_id):
    t = owned_topic_or_404(topic_id, current_user)
    explanation = ((request.get_json(silent=True) or {}).get('explanation') or '').strip()
    if len(explanation.split()) < 15:
        return jsonify(error='Write at least a few sentences (15+ words) in your own words.'), 400
    try:
        fb = ai.feynman_feedback(t.subject.name, t.name, explanation)
    except ai.AIError as e:
        return jsonify(error=str(e)), 502
    before = t.confidence
    db.session.add(FeynmanAttempt(topic_id=t.id, explanation=explanation, feedback=json.dumps(fb), score=fb['score']))
    update_confidence(t, fb['score'])
    db.session.commit()
    replan(current_user)
    fb['confidence_before'] = before
    fb['confidence'] = t.confidence
    return jsonify(fb)
