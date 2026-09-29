import unittest
from datetime import date, timedelta

from studygpt.clock import assign_times
from studygpt.scheduler import build_plan, topic_score, remaining_minutes

TODAY = date(2026, 10, 1)  # a Thursday


def subj(id, exam_in_days, priority=3):
    return {'id': id, 'priority': priority, 'exam_date': TODAY + timedelta(days=exam_in_days)}


def topic(id, subject_id, difficulty=3, confidence=0, est_hours=2, status='not_started', done_minutes=0):
    return {'id': id, 'subject_id': subject_id, 'difficulty': difficulty, 'confidence': confidence,
            'est_hours': est_hours, 'status': status, 'done_minutes': done_minutes}


EVERY_DAY_2H = {d: 120 for d in range(7)}


class RemainingMinutesTest(unittest.TestCase):
    def test_done_topic_needs_nothing(self):
        self.assertEqual(remaining_minutes(topic(1, 1, status='done')), 0)

    def test_scales_with_confidence_and_rounds_up_to_30(self):
        # 2h at 50% confidence = 60 min
        self.assertEqual(remaining_minutes(topic(1, 1, confidence=50)), 60)
        # 1h at 10% = 54 -> 60
        self.assertEqual(remaining_minutes(topic(1, 1, est_hours=1, confidence=10)), 60)

    def test_done_minutes_are_subtracted(self):
        self.assertEqual(remaining_minutes(topic(1, 1, done_minutes=60)), 60)

    def test_unfinished_topic_gets_at_least_one_block(self):
        self.assertEqual(remaining_minutes(topic(1, 1, confidence=99)), 30)


class TopicScoreTest(unittest.TestCase):
    def test_closer_exam_scores_higher(self):
        near, far = subj(1, 3), subj(2, 20)
        t = topic(1, 1)
        self.assertGreater(topic_score(t, near, TODAY), topic_score(t, far, TODAY))

    def test_harder_and_higher_priority_score_higher(self):
        s = subj(1, 10)
        self.assertGreater(topic_score(topic(1, 1, difficulty=5), s, TODAY),
                           topic_score(topic(2, 1, difficulty=1), s, TODAY))
        self.assertGreater(topic_score(topic(1, 1), subj(1, 10, priority=5), TODAY),
                           topic_score(topic(1, 1), subj(1, 10, priority=1), TODAY))

    def test_confident_topic_scores_lower(self):
        s = subj(1, 10)
        self.assertGreater(topic_score(topic(1, 1, confidence=0), s, TODAY),
                           topic_score(topic(2, 1, confidence=80), s, TODAY))


class BuildPlanTest(unittest.TestCase):
    def test_respects_daily_availability(self):
        plan = build_plan([subj(1, 10)], [topic(i, 1, est_hours=5) for i in range(5)], EVERY_DAY_2H, TODAY)
        per_day = {}
        for s in plan:
            per_day[s['date']] = per_day.get(s['date'], 0) + s['minutes']
        self.assertTrue(plan)
        self.assertTrue(all(m <= 120 for m in per_day.values()))

    def test_no_study_on_zero_availability_days(self):
        avail = {d: 120 for d in range(7)}
        avail[TODAY.weekday()] = 0
        plan = build_plan([subj(1, 10)], [topic(1, 1)], avail, TODAY)
        self.assertFalse(any(s['date'] == TODAY for s in plan))

    def test_nothing_scheduled_on_or_after_exam_day_for_that_subject(self):
        plan = build_plan([subj(1, 3)], [topic(i, 1, est_hours=10) for i in range(3)], EVERY_DAY_2H, TODAY)
        exam = TODAY + timedelta(days=3)
        self.assertTrue(all(s['date'] < exam for s in plan))

    def test_revision_block_day_before_exam(self):
        plan = build_plan([subj(1, 3)], [topic(1, 1)], EVERY_DAY_2H, TODAY)
        eve = TODAY + timedelta(days=2)
        self.assertTrue(any(s['date'] == eve and s['kind'] == 'revision' for s in plan))

    def test_does_not_overschedule_a_topic(self):
        plan = build_plan([subj(1, 10)], [topic(1, 1, est_hours=1)], EVERY_DAY_2H, TODAY)
        study = sum(s['minutes'] for s in plan if s['kind'] == 'study')
        self.assertEqual(study, 60)

    def test_urgent_subject_comes_first(self):
        plan = build_plan([subj(1, 2), subj(2, 20)],
                          [topic(1, 1, est_hours=1), topic(2, 2, est_hours=1)],
                          {d: 60 for d in range(7)}, TODAY)
        first = [s for s in plan if s['date'] == TODAY][0]
        self.assertEqual(first['topic_id'], 1)

    def test_interleaves_topics_within_a_day(self):
        plan = build_plan([subj(1, 10)], [topic(1, 1, est_hours=4), topic(2, 1, est_hours=4)],
                          EVERY_DAY_2H, TODAY)
        today_topics = {s['topic_id'] for s in plan if s['date'] == TODAY}
        self.assertEqual(today_topics, {1, 2})

    def test_minutes_already_studied_today_reduce_todays_budget(self):
        plan = build_plan([subj(1, 10)], [topic(i, 1, est_hours=5) for i in range(3)], EVERY_DAY_2H, TODAY,
                          used_today=90)
        self.assertEqual(sum(s['minutes'] for s in plan if s['date'] == TODAY), 30)

    def test_windowed_plan_always_fits_clock_times(self):
        wins = [['07:00', '08:30'], ['18:30', '21:30']]
        lengths = [90, 180]
        plan = build_plan([subj(1, 10), subj(2, 12)], [topic(i, 1 + i % 2, est_hours=6) for i in range(6)],
                          {d: 240 for d in range(7)}, TODAY, windows={d: lengths for d in range(7)})
        by_day = {}
        for s in plan:
            by_day.setdefault(s['date'], []).append(s['minutes'])
        self.assertTrue(by_day)
        for day, durations in by_day.items():
            self.assertNotIn(None, assign_times(durations, wins), day)
            self.assertLessEqual(sum(durations), 240)

    def test_subject_without_exam_still_gets_planned(self):
        s = {'id': 1, 'priority': 3, 'exam_date': None}
        plan = build_plan([s], [topic(1, 1)], EVERY_DAY_2H, TODAY)
        self.assertTrue(plan)


if __name__ == '__main__':
    unittest.main()
