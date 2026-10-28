from pathlib import Path

import duckdb
import pytest
from ocifabric.quality import latest_clean_sql, merge_sql, tag_sql

FIXTURE = Path(__file__).parent / "fixtures" / "bookings_batch.csv"

SILVER_DDL = """
CREATE TABLE silver_bookings (
  booking_id VARCHAR, guest_id VARCHAR, property_code VARCHAR,
  amount DOUBLE, status VARCHAR, event_ts TIMESTAMP
)"""


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute(
        f"CREATE VIEW bronze_bookings AS SELECT * FROM read_csv('{FIXTURE}', header=true, all_varchar=true)"
    )
    c.execute(f"CREATE VIEW tagged AS {tag_sql('bronze_bookings')}")
    c.execute(f"CREATE VIEW silver_batch AS {latest_clean_sql('tagged')}")
    c.execute(SILVER_DDL)
    return c


def test_each_bad_row_is_quarantined_with_its_reason(con):
    rows = con.execute(
        "SELECT dq_failed_rule, COUNT(*) FROM tagged WHERE dq_failed_rule IS NOT NULL GROUP BY 1 ORDER BY 1"
    ).fetchall()
    assert rows == [
        ("bad_amount", 2),
        ("bad_timestamp", 1),
        ("invalid_status", 1),
        ("missing_booking_id", 1),
    ]


def test_duplicates_and_out_of_order_events_keep_latest_state(con):
    rows = con.execute("SELECT booking_id, status FROM silver_batch ORDER BY 1").fetchall()
    assert rows == [("B-100", "CHECKED_IN"), ("B-101", "CHECKED_IN"), ("B-106", "CANCELLED")]


def test_merge_is_idempotent(con):
    for _ in range(3):
        con.execute(merge_sql("silver_bookings", "silver_batch"))
    assert con.execute("SELECT COUNT(*) FROM silver_bookings").fetchone()[0] == 3


def test_stale_event_never_overwrites_newer_state(con):
    con.execute(merge_sql("silver_bookings", "silver_batch"))
    con.execute(
        "CREATE VIEW stale AS SELECT 'B-100' AS booking_id, 'G-1' AS guest_id, 'CAS-RIO' AS property_code, "
        "450.0 AS amount, 'BOOKED' AS status, TIMESTAMP '2026-10-01 09:00:00' AS event_ts"
    )
    con.execute(merge_sql("silver_bookings", "stale"))
    status = con.execute("SELECT status FROM silver_bookings WHERE booking_id = 'B-100'").fetchone()[0]
    assert status == "CHECKED_IN"
