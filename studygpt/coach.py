from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import ai, db
from .models import ChatMessage
from .plan_service import plan_context

coach = Blueprint('coach', __name__)

SUGGESTIONS = [
    'What should I study today?',
    "I'm behind schedule. What should I cut?",
    'Which subject am I weakest in?',
    'Give me a plan for the day before my next exam.',
]


@coach.route('/coach')
@login_required
def chat():
    msgs = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.id).all()
    return render_template('coach.html', messages=msgs, suggestions=SUGGESTIONS)


@coach.route('/coach/send', methods=['POST'])
@login_required
def send():
    text = ((request.get_json(silent=True) or {}).get('message') or '').strip()[:2000]
    if not text:
        return jsonify(error='Type a message.'), 400
    history = [{'role': m.role, 'content': m.content} for m in
               ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.id.desc()).limit(10)][::-1]
    try:
        reply = ai.coach_reply(plan_context(current_user), history, text)
    except ai.AIError as e:
        return jsonify(error=str(e)), 502
    db.session.add(ChatMessage(user_id=current_user.id, role='user', content=text))
    db.session.add(ChatMessage(user_id=current_user.id, role='coach', content=reply))
    db.session.commit()
    return jsonify(reply=reply)


@coach.route('/coach/clear', methods=['POST'])
@login_required
def clear():
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return redirect(url_for('coach.chat'))
