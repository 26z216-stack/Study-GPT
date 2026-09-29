from datetime import date

QUOTES = [
    ("The secret of getting ahead is getting started.", "Mark Twain"),
    ("It always seems impossible until it's done.", "Nelson Mandela"),
    ("Small daily improvements are the key to staggering long-term results.", "Unknown"),
    ("If you can't explain it simply, you don't understand it well enough.", "Attributed to Albert Einstein"),
    ("Learning never exhausts the mind.", "Leonardo da Vinci"),
    ("The expert in anything was once a beginner.", "Helen Hayes"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
    ("Success is the sum of small efforts, repeated day in and day out.", "Robert Collier"),
    ("An investment in knowledge pays the best interest.", "Benjamin Franklin"),
    ("Focus on being productive instead of busy.", "Tim Ferriss"),
    ("You don't have to be great to start, but you have to start to be great.", "Zig Ziglar"),
    ("Discipline is choosing between what you want now and what you want most.", "Unknown"),
]


def quote_of_the_day(day=None):
    day = day or date.today()
    return QUOTES[day.toordinal() % len(QUOTES)]
