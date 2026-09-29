"""SM-2 spaced repetition over plain dicts."""
from datetime import timedelta

NEW_CARD = {'ease': 2.5, 'interval': 0, 'repetitions': 0}
GRADES = {'again': 1, 'hard': 3, 'good': 4, 'easy': 5}


def review(card, grade, today):
    """Return the card's new {ease, interval, repetitions, due} after a review."""
    q = GRADES[grade]
    ease = card['ease']
    reps = card['repetitions']
    interval = card['interval']

    if q < 3:
        reps, interval = 0, 0
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = round(interval * ease)
        if grade == 'hard':
            interval = max(1, round(interval * 0.6)) if reps > 1 else 1
        elif grade == 'easy':
            interval = round(interval * 1.3) + 1

    ease = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    return {'ease': round(ease, 2), 'interval': interval, 'repetitions': reps,
            'due': today + timedelta(days=interval)}
