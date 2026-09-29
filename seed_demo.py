"""Create a demo account with realistic subjects, topics and history.

    python seed_demo.py      ->  log in as demo@kanal.app / demo123
"""
from datetime import date, timedelta

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

from kanal import create_app, db  # noqa: E402
from kanal.models import Availability, Flashcard, QuizAttempt, StudySession, Subject, Topic, User  # noqa: E402
from kanal.plan_service import replan  # noqa: E402

EMAIL, PASSWORD = 'demo@kanal.app', 'demo123'
T = date.today()

SUBJECTS = [
    ('Physics', '#6C5CE7', 4, 5, 6, [
        ('Kinematics', 3, 3, 'done', 85), ('Newton\'s laws of motion', 3, 3, 'in_progress', 55),
        ('Work, energy and power', 4, 3, 'in_progress', 30), ('Rotational motion', 5, 4, 'not_started', 0),
        ('Gravitation', 3, 2, 'not_started', 0), ('Thermodynamics', 4, 3, 'not_started', 0)]),
    ('Mathematics', '#00B894', 4, 4, 11, [
        ('Limits and continuity', 3, 2, 'done', 90), ('Differentiation', 3, 3, 'in_progress', 60),
        ('Applications of derivatives', 4, 3, 'not_started', 0), ('Integration', 5, 4, 'not_started', 0),
        ('Differential equations', 5, 3, 'not_started', 0)]),
    ('Chemistry', '#E17055', 3, 3, 15, [
        ('Atomic structure', 2, 2, 'done', 75), ('Chemical bonding', 3, 3, 'in_progress', 40),
        ('Periodic table trends', 2, 1.5, 'not_started', 0), ('Organic chemistry basics', 4, 4, 'not_started', 0)]),
]

CARDS = [('What is Newton\'s second law?', 'F = ma: net force equals mass times acceleration.'),
         ('What is inertia?', 'The tendency of an object to resist changes in its state of motion.'),
         ('State Newton\'s third law.', 'Every action has an equal and opposite reaction.')]

app = create_app()
with app.app_context():
    old = User.query.filter_by(email=EMAIL).first()
    if old:
        StudySession.query.filter_by(user_id=old.id).delete()
        Availability.query.filter_by(user_id=old.id).delete()
        db.session.delete(old)
        db.session.commit()

    u = User(email=EMAIL, name='Demo Student', password_hash=generate_password_hash(PASSWORD))
    db.session.add(u)
    db.session.flush()
    for d, hours in enumerate([2, 2, 1.5, 2, 1, 5, 4]):
        db.session.add(Availability(user_id=u.id, weekday=d, minutes=int(hours * 60)))

    first_topics = []
    for name, color, diff, prio, days, topics in SUBJECTS:
        s = Subject(user_id=u.id, name=name, color=color, difficulty=diff, priority=prio,
                    exam_date=T + timedelta(days=days))
        db.session.add(s)
        db.session.flush()
        for tname, tdiff, hours, status, conf in topics:
            t = Topic(subject_id=s.id, name=tname, difficulty=tdiff, est_hours=hours, status=status, confidence=conf)
            db.session.add(t)
            db.session.flush()
            first_topics.append(t)

    # Some history: two done sessions, one missed (gets auto-rescheduled), a quiz, flashcards.
    k, n = first_topics[0], first_topics[1]
    db.session.add(StudySession(user_id=u.id, topic_id=k.id, date=T - timedelta(days=2), minutes=60, status='done'))
    db.session.add(StudySession(user_id=u.id, topic_id=n.id, date=T - timedelta(days=1), minutes=60, status='done'))
    db.session.add(StudySession(user_id=u.id, topic_id=n.id, date=T - timedelta(days=1), minutes=30, status='planned'))
    db.session.add(QuizAttempt(topic_id=k.id, score=4, total=5))
    for front, back in CARDS:
        db.session.add(Flashcard(topic_id=n.id, front=front, back=back, due=T))
    db.session.commit()

    missed = replan(u)
    print(f'Demo ready: {EMAIL} / {PASSWORD}  ({missed} missed session auto-rescheduled, '
          f'{StudySession.query.filter_by(user_id=u.id, status="planned").count()} sessions planned)')
