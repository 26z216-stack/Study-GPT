import unittest

from kanal.clock import assign_times


class AssignTimesTest(unittest.TestCase):
    def test_fills_window_with_breaks(self):
        self.assertEqual(assign_times([60, 30], [['16:30', '18:30']]),
                         [('16:30', '17:30'), ('17:40', '18:10')])

    def test_spills_into_next_window(self):
        self.assertEqual(assign_times([60, 60], [['07:00', '08:00'], ['19:00', '21:00']]),
                         [('07:00', '08:00'), ('19:00', '20:00')])

    def test_session_that_does_not_fit_gets_none(self):
        self.assertEqual(assign_times([60, 60], [['18:00', '19:00']]), [('18:00', '19:00'), None])

    def test_no_windows(self):
        self.assertEqual(assign_times([30], []), [None])


if __name__ == '__main__':
    unittest.main()
