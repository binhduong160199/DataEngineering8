import argparse
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when
import psycopg2

PROVIDER_NAMES = {
    "HV0002": "Juno",
    "HV0003": "Uber",
    "HV0004": "Via",
    "HV0005": "Lyft",
}

def get_pg_conn(args):
    return psycopg2.connect(
        host=args.pg_host, port=args.pg_port, dbname=args.pg_db,
        user=args.pg_user, password=args.pg_pass
    )

def get_or_create_providers(args, unique_codes):
    conn = get_pg_conn(args)
    cur = conn.cursor()
    provider_map = {}
    for code in unique_codes:
        label = PROVIDER_NAMES.get(code, code)
        cur.execute("SELECT id FROM providers WHERE provider_name=%s", (label,))
        row = cur.fetchone()
        if row:
            provider_map[code] = int(row[0])
        else:
            cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM providers")
            new_id = int(cur.fetchone()[0])
            cur.execute("INSERT INTO providers (id, provider_name) VALUES (%s, %s)", (new_id, label))
            provider_map[code] = new_id
    conn.commit()
    cur.close()
    conn.close()
    return provider_map

def get_or_create_zones(args, zone_ids):
    conn = get_pg_conn(args)
    cur = conn.cursor()
    for zid in zone_ids:
        cur.execute("SELECT 1 FROM taxi_zones WHERE id=%s", (int(zid),))
        if not cur.fetchone():
            cur.execute("INSERT INTO taxi_zones (id, zone_name) VALUES (%s, %s)", (int(zid), f"Zone {zid}"))
    conn.commit()
    cur.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Load Parquet to PostgreSQL with Spark")
    parser.add_argument("--data-file", required=True, help="Path to parquet file")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", default="5432")
    parser.add_argument("--pg-db", default="postgres")
    parser.add_argument("--pg-user", default="appuser")
    parser.add_argument("--pg-pass", default="group8")
    parser.add_argument("--partitions", default=16, type=int, help="Number of partitions")
    parser.add_argument("--batchsize", default=1000, type=int, help="JDBC batchsize")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    spark = SparkSession.builder.appName("NYC Loader").getOrCreate()
    df = spark.read.parquet(args.data_file)

    # 1. Providers
    unique_providers = [row['hvfhs_license_num'] for row in df.select("hvfhs_license_num").distinct().collect()]
    provider_map = get_or_create_providers(args, unique_providers)
    broadcast_provider_map = spark.sparkContext.broadcast(provider_map)

    # 2. Zones (PU & DO)
    all_zone_ids = set([int(x.PULocationID) for x in df.select("PULocationID").distinct().collect()] +
                       [int(x.DOLocationID) for x in df.select("DOLocationID").distinct().collect()])
    get_or_create_zones(args, all_zone_ids)

    # 3. Map to provider_id
    from pyspark.sql.functions import udf
    from pyspark.sql.types import IntegerType

    def map_provider(code):
        return broadcast_provider_map.value.get(code, None)
    provider_id_udf = udf(map_provider, IntegerType())
    df = df.withColumn("provider_id", provider_id_udf(col("hvfhs_license_num")))

    # 4. Rename columns
    df = df.withColumnRenamed("PULocationID", "pu_location_id") \
           .withColumnRenamed("DOLocationID", "do_location_id")

    # 5. Boolean conversion
    bool_cols = [
        "shared_request_flag", "shared_match_flag",
        "access_a_ride_flag", "wav_request_flag", "wav_match_flag"
    ]
    for c in bool_cols:
        df = df.withColumn(c, when(col(c) == "Y", True).when(col(c) == "N", False).otherwise(None))

    # 6. Select/Order Columns (excluding id if SERIAL, else generate ids)
    trips_cols = [
        "provider_id", "pu_location_id", "do_location_id",
        "request_datetime", "on_scene_datetime", "pickup_datetime", "dropoff_datetime",
        "trip_miles", "trip_time", "base_passenger_fare", "tolls", "bcf", "sales_tax",
        "congestion_surcharge", "airport_fee", "tips", "driver_pay", "cbd_congestion_fee",
        *bool_cols
    ]

    # 7. Filter out non-positive or missing required fields if needed
    df = df.filter(
        (col("trip_miles") > 0) & (col("base_passenger_fare") > 0) & (col("driver_pay") > 0)
    )

    # 8. Repartition for performance
    df = df.repartition(args.partitions)

    # 9. Write to DB with batchsize
    url = f"jdbc:postgresql://{args.pg_host}:{args.pg_port}/{args.pg_db}"
    properties = {
        "user": args.pg_user,
        "password": args.pg_pass,
        "driver": "org.postgresql.Driver",
        "batchsize": str(args.batchsize),
        "stringtype": "unspecified"  # For some PG versions
    }
    df.select(*trips_cols).write.jdbc(url=url, table="trips", mode="append", properties=properties)
    logging.info("✅ Data loaded to PostgreSQL.")

    spark.stop()

if __name__ == "__main__":
    main()