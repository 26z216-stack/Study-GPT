import unittest
from datetime import date, timedelta

from studygpt.srs import review, NEW_CARD
from studygpt.readiness import subject_readiness, overall_readiness

TODAY = date(2026, 10, 1)


class SrsTest(unittest.TestCase):
    def test_good_on_new_card_is_due_tomorrow(self):
        s = review(NEW_CARD, 'good', TODAY)
        self.assertEqual(s['due'], TODAY + timedelta(days=1))
        self.assertEqual(s['repetitions'], 1)

    def test_intervals_grow_with_repeated_good(self):
        s = review(NEW_CARD, 'good', TODAY)
        s = review(s, 'good', TODAY)
        self.assertEqual(s['interval'], 6)
        s = review(s, 'good', TODAY)
        self.assertGreater(s['interval'], 6)

    def test_again_resets_and_is_due_today(self):
        s = review(review(review(NEW_CARD, 'good', TODAY), 'good', TODAY), 'again', TODAY)
        self.assertEqual(s['repetitions'], 0)
        self.assertEqual(s['due'], TODAY)

    def test_ease_never_below_1_3(self):
        s = NEW_CARD
        for _ in range(20):
            s = review(s, 'again', TODAY)
        self.assertGreaterEqual(s['ease'], 1.3)

    def test_easy_beats_good(self):
        base = review(review(NEW_CARD, 'good', TODAY), 'good', TODAY)
        self.assertGreater(review(base, 'easy', TODAY)['interval'], review(base, 'good', TODAY)['interval'])


class ReadinessTest(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(subject_readiness([]), 0)

    def test_all_done_full_confidence_is_100(self):
        self.assertEqual(subject_readiness([{'status': 'done', 'confidence': 100}] * 3), 100)

    def test_mix(self):
        topics = [{'status': 'done', 'confidence': 80}, {'status': 'not_started', 'confidence': 0}]
        # 0.4*0.5 + 0.6*0.4 = 0.44
        self.assertEqual(subject_readiness(topics), 44)

    def test_overall_weights_by_topic_count(self):
        a = [{'status': 'done', 'confidence': 100}] * 3
        b = [{'status': 'not_started', 'confidence': 0}]
        self.assertEqual(overall_readiness([a, b]), 75)


if __name__ == '__main__':
    unittest.main()
