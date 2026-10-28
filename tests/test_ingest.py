from types import SimpleNamespace

import pytest
from helpers import ObjectSummary, ts
from ocifabric.ingest import ingest, load_state


class FakeOCIClient:
    """Mimics ObjectStorageClient: paginated list_objects + get_object."""

    def __init__(self, pages, contents, fail_on=None):
        self.pages = pages
        self.contents = contents
        self.fail_on = fail_on
        self.list_calls = 0

    def list_objects(self, namespace, bucket, prefix, fields, start):
        index = 0 if start is None else int(start)
        self.list_calls += 1
        next_start = str(index + 1) if index + 1 < len(self.pages) else None
        return SimpleNamespace(
            data=SimpleNamespace(objects=self.pages[index], next_start_with=next_start)
        )

    def get_object(self, namespace, bucket, name):
        if name == self.fail_on:
            raise ConnectionError("network dropped")
        return SimpleNamespace(data=SimpleNamespace(content=self.contents[name]))


def make_client(**kwargs):
    pages = [
        [ObjectSummary("bookings/2026-10-01.csv", ts(9))],
        [ObjectSummary("bookings/2026-10-02.csv", ts(10))],
    ]
    contents = {
        "bookings/2026-10-01.csv": b"booking_id\nB-1\n",
        "bookings/2026-10-02.csv": b"booking_id\nB-2\n",
    }
    return FakeOCIClient(pages, contents, **kwargs)


def test_reads_every_page_and_lands_files(tmp_path):
    client = make_client()
    landed = ingest(client, "ns", "raw", "bookings/", tmp_path / "landing", tmp_path / "state.json")
    assert landed == ["bookings/2026-10-01.csv", "bookings/2026-10-02.csv"]
    assert client.list_calls == 2
    assert (tmp_path / "landing/bookings/2026-10-02.csv").read_bytes() == b"booking_id\nB-2\n"
    assert load_state(tmp_path / "state.json") == ts(10)


def test_second_run_skips_already_loaded_files(tmp_path):
    state = tmp_path / "state.json"
    ingest(make_client(), "ns", "raw", "bookings/", tmp_path / "landing", state, lookback_minutes=0)
    assert ingest(make_client(), "ns", "raw", "bookings/", tmp_path / "landing", state, lookback_minutes=0) == []


def test_crash_mid_run_does_not_advance_watermark(tmp_path):
    state = tmp_path / "state.json"
    with pytest.raises(ConnectionError):
        ingest(make_client(fail_on="bookings/2026-10-02.csv"), "ns", "raw", "bookings/", tmp_path / "landing", state)
    assert load_state(state) is None
    landed = ingest(make_client(), "ns", "raw", "bookings/", tmp_path / "landing", state)
    assert len(landed) == 2


def test_rejects_object_names_that_escape_landing(tmp_path):
    client = FakeOCIClient([[ObjectSummary("../evil.csv", ts(9))]], {"../evil.csv": b"x"})
    with pytest.raises(ValueError):
        ingest(client, "ns", "raw", "", tmp_path / "landing", tmp_path / "state.json")
