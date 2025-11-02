import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from data_utilities import database_connector

@st.cache_data(show_spinner="Loading Negar's Data...", ttl=900)
def load_trip_data():
    """Loads hourly aggregated trip counts and pickup zones."""
    engine = database_connector.get_sqlalchemy_engine()
    query = """
        SELECT
            DATE_PART('hour', pickup_datetime) AS pickup_hour,
            DATE(pickup_datetime) AS pickup_date,
            pu_location_id,
            COUNT(*) AS ride_count
        FROM trips
        GROUP BY pickup_hour, pickup_date, pu_location_id
    """
    df = pd.read_sql_query(query, engine)
    engine.dispose()
    df["pickup_hour"] = pd.to_numeric(df["pickup_hour"], errors="coerce").astype("Int64")
    return df


def render():
    st.header("Negar's Analysis: Taxi Demand by Hour and Zone")
    st.markdown(
        "Explore hourly taxi demand in NYC: choose a specific hour or time range and see which pickup zones are most active."
    )

    df = load_trip_data()

    # --- Filters ---
    st.sidebar.header("Filters")
    all_hours = sorted(df["pickup_hour"].dropna().unique())
    selected_hours = st.sidebar.slider(
        "Select hour range", int(min(all_hours)), int(max(all_hours)), (8, 18)
    )

    # Filtered Data
    filtered = df[
        (df["pickup_hour"] >= selected_hours[0]) & (df["pickup_hour"] <= selected_hours[1])
    ]

    st.write(
        f"Showing data for **hours {selected_hours[0]}–{selected_hours[1]}**, total {len(filtered):,} records."
    )

    # --- Visualization 1: Trips by Hour ---
    st.subheader("Trips by Hour")
    hourly_df = (
        filtered.groupby("pickup_hour")["ride_count"].sum().reset_index()
    )

    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.bar(hourly_df["pickup_hour"], hourly_df["ride_count"], color="#2E86C1")
    ax1.set_xlabel("Hour of Day")
    ax1.set_ylabel("Number of Rides")
    ax1.set_title("Taxi Demand by Hour")
    st.pyplot(fig1)

    # --- Visualization 2: Top Pickup Zones ---
    st.subheader("Top 10 Pickup Zones in Selected Time Range")
    top_zones = (
        filtered.groupby("pu_location_id")["ride_count"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.bar(top_zones.index.astype(str), top_zones.values, color="#E67E22")
    ax2.set_xlabel("Pickup Zone ID")
    ax2.set_ylabel("Number of Rides")
    ax2.set_title("Top 10 Pickup Zones")
    st.pyplot(fig2)

    # --- Data Table ---
    st.subheader("Detailed Data Sample")
    st.dataframe(filtered.sample(min(200, len(filtered))), use_container_width=True)

    st.markdown("---")
