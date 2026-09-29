"""Exam readiness: 40% syllabus coverage + 60% average confidence."""


def subject_readiness(topics):
    if not topics:
        return 0
    done = sum(1 for t in topics if t['status'] == 'done') / len(topics)
    conf = sum((t['confidence'] or 0) for t in topics) / len(topics) / 100
    return round(100 * (0.4 * done + 0.6 * conf))


def overall_readiness(topic_groups):
    total = sum(len(g) for g in topic_groups)
    if not total:
        return 0
    return round(sum(subject_readiness(g) * len(g) for g in topic_groups) / total)
