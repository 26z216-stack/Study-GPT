"""Lay a day's planned sessions into that day's free windows to give them clock times."""

BREAK_MIN = 10


def _m(hhmm):
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)


def _fmt(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def assign_times(durations, windows):
    """durations: minutes per session, in order. windows: [["16:30", "18:00"], ...].

    Returns a list (same length) of ("HH:MM", "HH:MM") or None when a session
    doesn't fit. Sessions fill windows in order with a 10-minute break between them.
    Hardest-first ordering is up to the caller.
    """
    slots = [[_m(a), _m(b)] for a, b in windows]
    out = []
    wi = 0
    cursor = slots[0][0] if slots else 0
    for d in durations:
        placed = None
        while wi < len(slots):
            start, end = slots[wi]
            cursor = max(cursor, start)
            if cursor + d <= end:
                placed = (_fmt(cursor), _fmt(cursor + d))
                cursor += d + BREAK_MIN
                break
            wi += 1
        out.append(placed)
    return out
