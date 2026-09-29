from datetime import datetime, date

from flask_login import UserMixin

from . import db


class User(db.Model, UserMixin):
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    name          = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    last_replan   = db.Column(db.Date, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    subjects      = db.relationship('Subject', backref='user', lazy=True, cascade='all, delete-orphan')


class Subject(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name       = db.Column(db.String(100), nullable=False)
    color      = db.Column(db.String(20), default='#6C5CE7')
    difficulty = db.Column(db.Integer, default=3)   # 1-5
    priority   = db.Column(db.Integer, default=3)   # 1-5
    exam_date  = db.Column(db.Date, nullable=True)
    topics     = db.relationship('Topic', backref='subject', lazy=True, cascade='all, delete-orphan',
                                 order_by='Topic.id')

    @property
    def days_left(self):
        return (self.exam_date - date.today()).days if self.exam_date else None


class Topic(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    name       = db.Column(db.String(200), nullable=False)
    difficulty = db.Column(db.Integer, default=3)          # 1-5
    status     = db.Column(db.String(20), default='not_started')  # not_started / in_progress / done
    confidence = db.Column(db.Integer, default=0)          # 0-100
    est_hours  = db.Column(db.Float, default=2.0)
    sessions   = db.relationship('StudySession', backref='topic', lazy=True, cascade='all, delete-orphan')
    flashcards = db.relationship('Flashcard', backref='topic', lazy=True, cascade='all, delete-orphan')
    quizzes    = db.relationship('QuizAttempt', backref='topic', lazy=True, cascade='all, delete-orphan')
    feynmans   = db.relationship('FeynmanAttempt', backref='topic', lazy=True, cascade='all, delete-orphan')


class Availability(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)   # 0=Mon .. 6=Sun
    minutes = db.Column(db.Integer, default=120)


class StudySession(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    date     = db.Column(db.Date, nullable=False)
    minutes  = db.Column(db.Integer, nullable=False)
    kind     = db.Column(db.String(20), default='study')    # study / revision
    status   = db.Column(db.String(20), default='planned')  # planned / done / missed


class QuizAttempt(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    topic_id   = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    score      = db.Column(db.Integer, nullable=False)
    total      = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Flashcard(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    topic_id    = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    front       = db.Column(db.Text, nullable=False)
    back        = db.Column(db.Text, nullable=False)
    ease        = db.Column(db.Float, default=2.5)
    interval    = db.Column(db.Integer, default=0)
    repetitions = db.Column(db.Integer, default=0)
    due         = db.Column(db.Date, default=date.today)


class FeynmanAttempt(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    topic_id    = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    feedback    = db.Column(db.Text, nullable=True)   # JSON
    score       = db.Column(db.Integer, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role       = db.Column(db.String(10), nullable=False)   # user / coach
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
