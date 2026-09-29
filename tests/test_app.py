"""End-to-end smoke test through the Flask test client, with the AI stubbed out."""
import json
import unittest
from datetime import date, timedelta
from unittest import mock

from kanal import create_app, db
from kanal.models import Flashcard, StudySession, Topic

FAKE = {
    'topics': [{'name': 'Kinematics', 'difficulty': 4, 'est_hours': 3},
               {'name': 'Newton laws', 'difficulty': 3, 'est_hours': 2}],
    'questions': [{'q': 'Q?', 'options': ['a', 'b', 'c', 'd'], 'answer': 1, 'why': 'b'}] * 5,
    'cards': [{'front': 'F', 'back': 'B'}] * 3,
    'score': 60, 'strengths': ['x'], 'gaps': ['y'], 'misconceptions': [], 'jargon': [],
    'analogy': 'like a ball', 'next_step': 'read',
    'reply': 'Study Kinematics first.',
    'headline': 'On track', 'focus': ['a', 'b', 'c'], 'risk': 'none',
}


class AppTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'WTF_CSRF_ENABLED': False,
                               'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        self.c = self.app.test_client()
        self.patch = mock.patch('kanal.ai.ask_json', return_value=FAKE)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        with self.app.app_context():
            db.drop_all()

    def test_full_flow(self):
        c = self.c
        r = c.post('/signup', data={'name': 'Asha', 'email': 'a@x.com', 'password': 'secret1'})
        self.assertEqual(r.status_code, 302)

        exam = (date.today() + timedelta(days=10)).isoformat()
        r = c.post('/subjects', data={'name': 'Physics', 'exam_date': exam, 'priority': 4, 'difficulty': 4})
        self.assertEqual(r.status_code, 302)
        r = c.post('/subjects/1/import', data={'syllabus': 'Unit 1 kinematics, unit 2 newton laws'})
        self.assertEqual(r.status_code, 302)

        with self.app.app_context():
            self.assertEqual(Topic.query.count(), 2)
            self.assertGreater(StudySession.query.count(), 0)

        for url in ['/', '/subjects', '/subjects/1', '/timetable', '/timetable.ics', '/report', '/coach',
                    '/focus', '/review', '/topic/1']:
            self.assertEqual(c.get(url).status_code, 200, url)

        r = c.post('/topic/1/quiz')
        self.assertEqual(len(r.get_json()['questions']), 5)
        r = c.post('/topic/1/quiz/submit', json={'score': 4, 'total': 5})
        self.assertEqual(r.get_json()['confidence'], 80)

        r = c.post('/topic/1/flashcards')
        self.assertEqual(r.get_json()['added'], 3)
        with self.app.app_context():
            card_id = Flashcard.query.first().id
        r = c.post(f'/flashcard/{card_id}/review', json={'grade': 'good'})
        self.assertEqual(r.get_json()['interval'], 1)

        r = c.post('/topic/2/feynman', json={'explanation': ' '.join(['word'] * 20)})
        self.assertEqual(r.get_json()['score'], 60)

        r = c.post('/coach/send', json={'message': 'what now?'})
        self.assertEqual(r.get_json()['reply'], 'Study Kinematics first.')
        self.assertIn('headline', c.post('/report/ai').get_json())

        # Skipping a session reschedules its work into the future.
        with self.app.app_context():
            s = StudySession.query.filter_by(status='planned').order_by(StudySession.date).first()
            sid, topic_id = s.id, s.topic_id
        c.post(f'/session/{sid}/skip')
        with self.app.app_context():
            self.assertEqual(db.session.get(StudySession, sid).status, 'missed')
            self.assertTrue(StudySession.query.filter_by(topic_id=topic_id, status='planned').count())

    def test_other_users_data_is_private(self):
        c = self.c
        c.post('/signup', data={'name': 'A', 'email': 'a@x.com', 'password': 'secret1'})
        c.post('/subjects', data={'name': 'Physics'})
        c.get('/logout')
        c.post('/signup', data={'name': 'B', 'email': 'b@x.com', 'password': 'secret1'})
        self.assertEqual(c.get('/subjects/1').status_code, 404)

    def test_requires_login(self):
        self.assertEqual(self.c.get('/').status_code, 302)


if __name__ == '__main__':
    unittest.main()
