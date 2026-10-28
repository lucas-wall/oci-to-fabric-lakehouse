from datetime import timedelta


def select_new_objects(objects, last_watermark, lookback_minutes=60):
    # Overlap window re-reads late-landing files; silver MERGE absorbs the repeats.
    if last_watermark is None:
        cutoff = None
    else:
        cutoff = last_watermark - timedelta(minutes=lookback_minutes)
    picked = [o for o in objects if cutoff is None or o.time_modified > cutoff]
    return sorted(picked, key=lambda o: o.time_modified)


def next_watermark(picked, last_watermark):
    if not picked:
        return last_watermark
    newest = max(o.time_modified for o in picked)
    if last_watermark is None:
        return newest
    return max(newest, last_watermark)
