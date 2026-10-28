from helpers import ObjectSummary, ts
from ocifabric.watermark import next_watermark, select_new_objects


def test_first_run_picks_everything_in_time_order():
    objs = [ObjectSummary("b.csv", ts(11)), ObjectSummary("a.csv", ts(9))]
    picked = select_new_objects(objs, last_watermark=None)
    assert [o.name for o in picked] == ["a.csv", "b.csv"]


def test_only_files_after_watermark_minus_lookback():
    objs = [
        ObjectSummary("old.csv", ts(8)),
        ObjectSummary("late.csv", ts(9, 40)),
        ObjectSummary("new.csv", ts(11)),
    ]
    picked = select_new_objects(objs, last_watermark=ts(10), lookback_minutes=30)
    assert [o.name for o in picked] == ["late.csv", "new.csv"]


def test_watermark_moves_forward_never_back():
    picked = [ObjectSummary("x.csv", ts(9))]
    assert next_watermark(picked, last_watermark=ts(10)) == ts(10)
    assert next_watermark([ObjectSummary("y.csv", ts(12))], ts(10)) == ts(12)


def test_empty_batch_keeps_watermark():
    assert next_watermark([], ts(10)) == ts(10)
    assert next_watermark([], None) is None
