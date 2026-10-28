"""Silver-layer SQL shared by Spark (Fabric notebooks) and DuckDB (local tests)."""

VALID_STATUSES = ("BOOKED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED")

RULES = {
    "missing_booking_id": "booking_id IS NULL OR TRIM(booking_id) = ''",
    "bad_amount": "TRY_CAST(amount AS DOUBLE) IS NULL OR TRY_CAST(amount AS DOUBLE) < 0",
    "invalid_status": "status IS NULL OR status NOT IN ({})".format(
        ", ".join(f"'{s}'" for s in VALID_STATUSES)
    ),
    "bad_timestamp": "TRY_CAST(event_ts AS TIMESTAMP) IS NULL",
}

SILVER_COLUMNS = ("booking_id", "guest_id", "property_code", "amount", "status", "event_ts")


def failed_rule_expr():
    cases = " ".join(f"WHEN {cond} THEN '{name}'" for name, cond in RULES.items())
    return f"CASE {cases} END"


def tag_sql(bronze):
    return f"SELECT *, {failed_rule_expr()} AS dq_failed_rule FROM {bronze}"


def latest_clean_sql(tagged):
    # Out-of-order and duplicate events collapse to the newest state per booking.
    return f"""
SELECT booking_id, guest_id, property_code, amount, status, event_ts FROM (
  SELECT booking_id, guest_id, property_code,
         CAST(amount AS DOUBLE) AS amount,
         status,
         CAST(event_ts AS TIMESTAMP) AS event_ts,
         ROW_NUMBER() OVER (
           PARTITION BY booking_id ORDER BY CAST(event_ts AS TIMESTAMP) DESC
         ) AS rn
  FROM {tagged}
  WHERE dq_failed_rule IS NULL
) AS ranked
WHERE rn = 1"""


def merge_sql(target, source):
    return f"""
MERGE INTO {target} AS t
USING {source} AS s
ON t.booking_id = s.booking_id
WHEN MATCHED AND s.event_ts > t.event_ts THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *"""
