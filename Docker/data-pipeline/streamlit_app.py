import streamlit as st
import pandas as pd
import psycopg2
import os
import matplotlib.pyplot as plt
import seaborn as sns

def get_connection():
    host = os.getenv("PG_HOST", "localhost")
    return psycopg2.connect(
        host=host,
        port=5432,
        dbname="postgres",
        user="appuser",
        password="group8"
    )

@st.cache_data(show_spinner=True)
def load_stats():
    query = """
        SELECT 
            t.pu_location_id,
            z.zone_name AS pu_zone_name,
            EXTRACT(DOW FROM t.pickup_datetime) AS weekday_num,
            TO_CHAR(t.pickup_datetime, 'Day') AS weekday,
            EXTRACT(HOUR FROM t.pickup_datetime) AS pickup_hour,
            COUNT(*) AS trip_count
        FROM trips t
        LEFT JOIN taxi_zones z ON t.pu_location_id = z.id
        GROUP BY t.pu_location_id, z.zone_name, weekday_num, weekday, pickup_hour
        ORDER BY trip_count DESC
    """
    conn = get_connection()
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['weekday'] = df['weekday'].str.strip()
    return df

@st.cache_data(show_spinner=True)
def load_top_zones():
    query = """
        SELECT 
            t.pu_location_id,
            z.zone_name AS pu_zone_name,
            COUNT(*) AS total_trips
        FROM trips t
        LEFT JOIN taxi_zones z ON t.pu_location_id = z.id
        GROUP BY t.pu_location_id, z.zone_name
        ORDER BY total_trips DESC
        LIMIT 10
    """
    conn = get_connection()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_data(show_spinner=True)
def load_provider_counts(top_zone_ids):
    ids = ",".join(str(z) for z in top_zone_ids)
    query = f"""
        SELECT 
            t.pu_location_id,
            z.zone_name AS pu_zone_name,
            p.provider_name,
            COUNT(*) AS trip_count
        FROM trips t
        LEFT JOIN taxi_zones z ON t.pu_location_id = z.id
        LEFT JOIN providers p ON t.provider_id = p.id
        WHERE t.pu_location_id IN ({ids})
        GROUP BY t.pu_location_id, z.zone_name, p.provider_name
    """
    conn = get_connection()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

st.title("NYC Taxi Zone Analysis Dashboard 🗽🚕")

# 1. Trips per zone/weekday/hour
zone_full_stats = load_stats()
st.subheader("1. Fahrten-Statistik nach Zone, Wochentag, Stunde")
st.dataframe(zone_full_stats.head(50), use_container_width=True)

# 2. Top 10 Zonen
top_zones = load_top_zones()
st.subheader("2. Top 10 Zonen (nach Anzahl Fahrten)")
st.dataframe(top_zones, use_container_width=True)

# 3. Heatmap (Top 10 Zones)
top10_ids = top_zones['pu_location_id'].tolist()
all_hours = list(range(24))
heatmap_data = zone_full_stats[zone_full_stats['pu_location_id'].isin(top10_ids)]
heatmap_pivot = (
    heatmap_data.groupby(['pu_zone_name', 'pickup_hour'])['trip_count'].sum()
    .unstack(fill_value=0)
    .reindex(columns=all_hours, fill_value=0)
)
fig, ax = plt.subplots(figsize=(14, 6))
sns.heatmap(heatmap_pivot, annot=False, fmt="d", cmap="Reds", ax=ax)
plt.title("Fahrten pro Zone und Stunde (Top 10 Zonen)")
plt.xlabel("Stunde")
plt.ylabel("Zone")
plt.tight_layout()
st.pyplot(fig)

# 4. Anbieter-Stacked Bar (Top 10 Zonen)
provider_counts = load_provider_counts(top10_ids)
provider_counts_pivot = provider_counts.pivot_table(
    index='pu_zone_name', columns='provider_name', values='trip_count', fill_value=0
)
fig2, ax2 = plt.subplots(figsize=(12, 5))
provider_counts_pivot.plot(kind='bar', stacked=True, ax=ax2, colormap='Accent')
plt.title("Top 10 Zonen: Fahrten nach Anbieter")
plt.xlabel("Zone")
plt.ylabel("Anzahl Fahrten")
plt.tight_layout()
st.pyplot(fig2)