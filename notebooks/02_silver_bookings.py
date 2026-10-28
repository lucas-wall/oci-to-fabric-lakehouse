# Fabric notebook | default lakehouse attached
# Bronze CSV -> quality gates -> quarantine | latest state -> silver (Delta MERGE)

from pyspark.sql import functions as F

from ocifabric.quality import latest_clean_sql, merge_sql, tag_sql

raw = spark.read.option("header", True).csv("Files/bronze/oci/bookings/")  # noqa: F821
raw.createOrReplaceTempView("bronze_bookings")

tagged = spark.sql(tag_sql("bronze_bookings"))  # noqa: F821
tagged.createOrReplaceTempView("tagged_bookings")

(
    tagged.filter("dq_failed_rule IS NOT NULL")
    .withColumn("quarantined_at", F.current_timestamp())
    .write.mode("append")
    .saveAsTable("quarantine_bookings")
)

spark.sql(latest_clean_sql("tagged_bookings")).createOrReplaceTempView("silver_batch")  # noqa: F821

spark.sql("""
CREATE TABLE IF NOT EXISTS silver_bookings (
  booking_id STRING, guest_id STRING, property_code STRING,
  amount DOUBLE, status STRING, event_ts TIMESTAMP
) USING DELTA
""")  # noqa: F821

spark.sql(merge_sql("silver_bookings", "silver_batch"))  # noqa: F821
