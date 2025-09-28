
"""
AUTHOR: GROUP8, DATA ENGINEERING, DANIEL IYAMU - FH TECHNIKUM AI ENGINEERING
Minimal NYC TLC HVFHS → Postgres loader (single Parquet file).
Fixes '_provider_id' attribute error by computing provider_id inline.

- Matches schema: providers, taxi_zones, trips
- Progress via tqdm
- Logs & skips row errors, continues loading


USAGE: python ./load_nyc.py --data-file <PATH TO .PARQUET FILE>
Example - python ./load_nyc.py --data-file ./july-25-hv.parquet

REMINDER: DONT FORGET TO INSTALL ALL THE REQUIRED PACKAGES

"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd
import psycopg2
from tqdm import tqdm

# Map common HVFHS codes to readable provider names
PROVIDER_NAMES = {
    "HV0002": "Juno",
    "HV0003": "Uber",
    "HV0004": "Via",
    "HV0005": "Lyft",
}

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

def connect_pg(host, port, db, user, pw):
    conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=pw)
    conn.autocommit = True  # simplest: each INSERT is its own transaction
    return conn

def yn_to_bool(v):
    if pd.isna(v): return None
    s = str(v).strip().upper()
    return True if s == "Y" else False if s == "N" else None

def val_or_none(v):
    return None if pd.isna(v) else v

def provider_label_from_code(code):
    if pd.isna(code):
        return "Unknown"
    c = str(code).strip().upper()
    return PROVIDER_NAMES.get(c, c)  # friendly name if known, else keep code

def ensure_provider(cur, provider_label):
    """Ensure providers(name) exists, return id (assign MAX(id)+1 if new)."""
    cur.execute("SELECT id FROM providers WHERE provider_name=%s", (provider_label,))
    row = cur.fetchone()
    if row:
        return int(row[0])

    # allocate simple sequential id
    cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM providers")
    new_id = int(cur.fetchone()[0])
    try:
        cur.execute(
            "INSERT INTO providers (id, provider_name) VALUES (%s, %s)",
            (new_id, provider_label),
        )
        return new_id
    except Exception as e:
        # If unique race happened, read it back
        logging.error("Provider insert error (%s): %s", provider_label, e)
        cur.execute("SELECT id FROM providers WHERE provider_name=%s", (provider_label,))
        row = cur.fetchone()
        return int(row[0]) if row else None

def ensure_zone(cur, zone_id: int):
    try:
        cur.execute("SELECT 1 FROM taxi_zones WHERE id=%s", (zone_id,))
        if cur.fetchone():
            return
        cur.execute(
            "INSERT INTO taxi_zones (id, zone_name) VALUES (%s, %s)",
            (zone_id, f"Zone {zone_id}"),
        )
    except Exception as e:
        logging.error("Taxi zone insert error (id=%s): %s", zone_id, e)

def next_trip_id(cur):
    cur.execute("SELECT COALESCE(MAX(id),0) FROM trips")
    return int(cur.fetchone()[0]) + 1

def main():
    setup_logging()
    ap = argparse.ArgumentParser(description="Load ONE NYC TLC Parquet file into Postgres.")
    ap.add_argument("--data-file", required=True, help="Path to a .parquet file")
    ap.add_argument("--pg-host", default="127.0.0.1")
    ap.add_argument("--pg-port", type=int, default=5432)
    ap.add_argument("--pg-db", default="postgres")
    ap.add_argument("--pg-user", default="appuser")
    ap.add_argument("--pg-pass", default="group8")
    args = ap.parse_args()

    # Read parquet
    f = Path(args.data_file)
    if not f.exists():
        logging.error("File not found: %s", f)
        sys.exit(1)
    logging.info("Reading %s ...", f)
    try:
        df = pd.read_parquet(f)
    except Exception as e:
        logging.error("Failed to read parquet: %s", e)
        sys.exit(1)

    # Connect DB
    try:
        conn = connect_pg(args.pg_host, args.pg_port, args.pg_db, args.pg_user, args.pg_pass)
    except Exception as e:
        logging.error("DB connection failed: %s", e)
        sys.exit(2)
    cur = conn.cursor()

    # Ensure providers (build a small cache for speed)
    logging.info("Ensuring providers ...")
    provider_cache = {}
    for code in pd.unique(df["hvfhs_license_num"]):
        label = provider_label_from_code(code)
        provider_cache[label] = ensure_provider(cur, label)

    # Ensure zones (PU & DO). Your columns are int32 already; cast to int safely.
    logging.info("Ensuring taxi zones ...")
    for col in ("PULocationID", "DOLocationID"):
        if col in df.columns:
            for zid in pd.unique(df[col].dropna()):
                try:
                    ensure_zone(cur, int(zid))
                except Exception as e:
                    logging.error("Zone ensure error (%s=%s): %s", col, zid, e)

    # Prepare convenience flags
    has_on_scene = "on_scene_datetime" in df.columns
    has_cbd = "cbd_congestion_fee" in df.columns

    # Next trip id
    tid = next_trip_id(cur)

    # Insert SQL (matches your trips schema order)
    insert_sql = """
        INSERT INTO trips (
            id, provider_id, pu_location_id, do_location_id,
            request_datetime, on_scene_datetime, pickup_datetime, dropoff_datetime,
            trip_miles, trip_time, base_passenger_fare, tolls, bcf, sales_tax,
            congestion_surcharge, airport_fee, tips, driver_pay, cbd_congestion_fee,
            shared_request_flag, shared_match_flag, access_a_ride_flag, wav_request_flag, wav_match_flag
        ) VALUES (
            %s,%s,%s,%s,
            %s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s
        )
    """

    bool_cols = [
        "shared_request_flag", "shared_match_flag",
        "access_a_ride_flag", "wav_request_flag", "wav_match_flag"
    ]

    total = len(df)
    ok = failed = 0

    logging.info("Inserting trips ...")
    for r in tqdm(df.itertuples(index=False), total=total, desc="Loading trips"):
        try:
            # compute provider_id inline (no _provider_id column)
            provider_label = provider_label_from_code(getattr(r, "hvfhs_license_num"))
            provider_id = provider_cache.get(provider_label)
            if provider_id is None:
                provider_id = ensure_provider(cur, provider_label)
                provider_cache[provider_label] = provider_id

            pu = getattr(r, "PULocationID", None)
            do = getattr(r, "DOLocationID", None)
            pu = int(pu) if pd.notna(pu) else None
            do = int(do) if pd.notna(do) else None

            request_dt = val_or_none(getattr(r, "request_datetime", None))
            on_scene_dt = val_or_none(getattr(r, "on_scene_datetime", None)) if has_on_scene else None
            pickup_dt = val_or_none(getattr(r, "pickup_datetime", None))
            dropoff_dt = val_or_none(getattr(r, "dropoff_datetime", None))

            trip_miles = val_or_none(getattr(r, "trip_miles", None))
            trip_time = val_or_none(getattr(r, "trip_time", None))
            base_fare = val_or_none(getattr(r, "base_passenger_fare", None))
            tolls = val_or_none(getattr(r, "tolls", None))
            bcf = val_or_none(getattr(r, "bcf", None))
            sales_tax = val_or_none(getattr(r, "sales_tax", None))
            congestion = val_or_none(getattr(r, "congestion_surcharge", None))
            airport_fee = val_or_none(getattr(r, "airport_fee", None))
            tips = val_or_none(getattr(r, "tips", None))
            driver_pay = val_or_none(getattr(r, "driver_pay", None))
            cbd = val_or_none(getattr(r, "cbd_congestion_fee", None)) if has_cbd else None

            flags = [yn_to_bool(getattr(r, c, None)) for c in bool_cols]

            row = (
                tid, provider_id, pu, do,
                request_dt, on_scene_dt, pickup_dt, dropoff_dt,
                trip_miles, trip_time, base_fare, tolls, bcf, sales_tax,
                congestion, airport_fee, tips, driver_pay, cbd,
                *flags
            )
            cur.execute(insert_sql, row)
            tid += 1
            ok += 1
        except Exception as e:
            failed += 1
            logging.error("Trip insert error (row %d): %s", ok + failed, e)

    logging.info("Done. Inserted OK: %d | Failed: %d | Total: %d", ok, failed, total)
    try:
        cur.close(); conn.close()
    except Exception:
        pass

if __name__ == "__main__":
    main()
