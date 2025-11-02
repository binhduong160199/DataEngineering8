import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from data_utilities import database_connector

USER_STORY = (
    "Als Fahrgast möchte ich einen Überblick über die durchschnittliche Warte- und Fahrzeit bekommen, "
    "damit ich meine Fahrt besser planen kann"
)

# Helper to run SQL and return df
def load_sql(query):
    engine = database_connector.get_sqlalchemy_engine()
    return pd.read_sql_query(query, engine)

# 1. Overall Mean
@st.cache_data(show_spinner="Lade Durchschnittsdaten...", ttl=600)
def load_overall():
    query = """
        SELECT
            ROUND(AVG(EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60),1) AS avg_wait,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60),1) AS avg_trip
        FROM trips t
        WHERE t.request_datetime IS NOT NULL AND t.pickup_datetime IS NOT NULL AND t.dropoff_datetime IS NOT NULL
              AND t.pickup_datetime > t.request_datetime AND t.dropoff_datetime > t.pickup_datetime
              AND EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60 BETWEEN 0 AND 60
              AND EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60 BETWEEN 1 AND 120
    """
    return load_sql(query)

# 2. By Provider
@st.cache_data(show_spinner="Lade Anbieter-Stats...", ttl=600)
def load_by_provider():
    query = """
        SELECT
            p.provider_name,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60),1) AS avg_wait,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60),1) AS avg_trip
        FROM trips t
        JOIN providers p ON t.provider_id = p.id
        WHERE t.request_datetime IS NOT NULL AND t.pickup_datetime IS NOT NULL AND t.dropoff_datetime IS NOT NULL
              AND t.pickup_datetime > t.request_datetime AND t.dropoff_datetime > t.pickup_datetime
              AND EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60 BETWEEN 0 AND 60
              AND EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60 BETWEEN 1 AND 120
        GROUP BY p.provider_name
        ORDER BY avg_wait
    """
    return load_sql(query)

# 3. By Hour
@st.cache_data(show_spinner="Lade Stunden-Stats...", ttl=600)
def load_by_hour():
    query = """
        SELECT
            EXTRACT(HOUR FROM t.pickup_datetime) AS pickup_hour,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60),1) AS avg_wait,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60),1) AS avg_trip
        FROM trips t
        WHERE t.request_datetime IS NOT NULL AND t.pickup_datetime IS NOT NULL AND t.dropoff_datetime IS NOT NULL
              AND t.pickup_datetime > t.request_datetime AND t.dropoff_datetime > t.pickup_datetime
              AND EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60 BETWEEN 0 AND 60
              AND EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60 BETWEEN 1 AND 120
        GROUP BY pickup_hour
        ORDER BY pickup_hour
    """
    return load_sql(query)

# 4. By Weekday
@st.cache_data(show_spinner="Lade Wochentag-Stats...", ttl=600)
def load_by_weekday():
    query = """
        SELECT
            TRIM(TO_CHAR(t.pickup_datetime, 'Day')) AS weekday,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60),1) AS avg_wait,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60),1) AS avg_trip
        FROM trips t
        WHERE t.request_datetime IS NOT NULL AND t.pickup_datetime IS NOT NULL AND t.dropoff_datetime IS NOT NULL
              AND t.pickup_datetime > t.request_datetime AND t.dropoff_datetime > t.pickup_datetime
              AND EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60 BETWEEN 0 AND 60
              AND EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60 BETWEEN 1 AND 120
        GROUP BY TRIM(TO_CHAR(t.pickup_datetime, 'Day'))
        ORDER BY
            CASE TRIM(TO_CHAR(t.pickup_datetime, 'Day'))
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
    """
    return load_sql(query)

# 5. By Pickup Zone (top 10 slowest)
@st.cache_data(show_spinner="Lade Zonen-Stats...", ttl=600)
def load_by_zone():
    query = """
        SELECT
            z.zone_name AS pickup_zone,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60),1) AS avg_wait,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60),1) AS avg_trip,
            COUNT(*) AS trip_count
        FROM trips t
        JOIN taxi_zones z ON t.pu_location_id = z.id
        WHERE t.request_datetime IS NOT NULL AND t.pickup_datetime IS NOT NULL AND t.dropoff_datetime IS NOT NULL
              AND t.pickup_datetime > t.request_datetime AND t.dropoff_datetime > t.pickup_datetime
              AND EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60 BETWEEN 0 AND 60
              AND EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60 BETWEEN 1 AND 120
        GROUP BY z.zone_name
        HAVING COUNT(*) > 1000
        ORDER BY avg_wait DESC
        LIMIT 10
    """
    return load_sql(query)

# 6. Histogram (Sampled)
@st.cache_data(show_spinner="Lade Hist-Daten...", ttl=600)
def load_hist():
    query = """
        SELECT
            EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60 AS wait_minutes,
            EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60 AS trip_minutes
        FROM trips t
        WHERE t.request_datetime IS NOT NULL AND t.pickup_datetime IS NOT NULL AND t.dropoff_datetime IS NOT NULL
              AND t.pickup_datetime > t.request_datetime AND t.dropoff_datetime > t.pickup_datetime
              AND EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60 BETWEEN 0 AND 60
              AND EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60 BETWEEN 1 AND 120
        LIMIT 100000
    """
    return load_sql(query)

# 7. By Hour & Weekday Heatmap
@st.cache_data(show_spinner="Lade Heatmap-Stats...", ttl=600)
def load_by_hour_day():
    query = """
        SELECT
            EXTRACT(HOUR FROM t.pickup_datetime) AS hour,
            TRIM(TO_CHAR(t.pickup_datetime, 'Day')) AS weekday,
            ROUND(AVG(EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60),1) AS avg_wait
        FROM trips t
        WHERE t.request_datetime IS NOT NULL AND t.pickup_datetime IS NOT NULL AND t.dropoff_datetime IS NOT NULL
              AND t.pickup_datetime > t.request_datetime AND t.dropoff_datetime > t.pickup_datetime
              AND EXTRACT(EPOCH FROM (t.pickup_datetime - t.request_datetime))/60 BETWEEN 0 AND 60
              AND EXTRACT(EPOCH FROM (t.dropoff_datetime - t.pickup_datetime))/60 BETWEEN 1 AND 120
        GROUP BY hour, weekday
    """
    return load_sql(query)

##render for the dashboard 
def render():
    st.header(USER_STORY)
    st.markdown("""
    Übersicht über **durchschnittliche Wartezeit** (Anfrage → Abholung) und **Fahrzeit** (Abholung → Ziel) – insgesamt, nach Anbieter, Stunde, Wochentag, Zone und mehr.
    """)

    # 1. Overall Stats
    overall = load_overall()
    st.metric("Durchschnittliche Wartezeit (min)", f"{overall['avg_wait'][0]:.1f}")
    st.metric("Durchschnittliche Fahrzeit (min)", f"{overall['avg_trip'][0]:.1f}")
    st.divider()

    # 2. By Provider
    st.subheader("Durchschnittliche Zeiten pro Anbieter")
    by_provider = load_by_provider()
    st.dataframe(
        by_provider.rename(columns={"avg_wait": "Wartezeit", "avg_trip": "  Fahrzeit"}),
        width="stretch"
    )
    # Fastest/slowest
    if not by_provider.empty:
        st.write("**Schnellster Anbieter (Wartezeit):**")
        st.dataframe(by_provider.nsmallest(1, "avg_wait").rename(
            columns={"avg_wait":"Wartezeit","avg_trip":"  Fahrzeit"}), width="content")
        st.write("**Langsamster Anbieter (Wartezeit):**")
        st.dataframe(by_provider.nlargest(1, "avg_wait").rename(
            columns={"avg_wait":"Wartezeit","avg_trip":"  Fahrzeit"}), width="content")

    # 3. By Hour (Line Plot)
    st.subheader("1. Zeiten nach Stunde des Tages")
    by_hour = load_by_hour()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(by_hour['pickup_hour'], by_hour['avg_wait'], label="Wartezeit", marker='o')
    ax.plot(by_hour['pickup_hour'], by_hour['avg_trip'], label="Fahrzeit", marker='o')
    ax.set_xticks(range(0, 24))
    ax.set_xlabel("Stunde")
    ax.set_ylabel("Minuten")
    ax.set_title("Warte- und Fahrzeit nach Stunde")
    ax.legend()
    st.pyplot(fig)

    # 4. By Weekday (Bar Plot)
    st.subheader("2. Zeiten nach Wochentag")
    by_weekday = load_by_weekday()
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.bar(by_weekday['weekday'], by_weekday['avg_wait'], alpha=0.6, label="Wartezeit (min)")
    ax2.bar(by_weekday['weekday'], by_weekday['avg_trip'], alpha=0.6, label="Fahrzeit (min)")
    ax2.set_xlabel("Wochentag")
    ax2.set_ylabel("Minuten")
    ax2.set_title("  Zeiten nach Wochentag")
    ax2.legend()
    st.pyplot(fig2)

    # 5. By Pickup Zone (Top 10 slowest)
    st.subheader("3. Zonen mit längster Wartezeit (Top 10, >1000 Fahrten)")
    by_zone = load_by_zone()
    st.dataframe(by_zone.rename(
        columns={'pickup_zone': 'Zone', 'avg_wait': '  Wartezeit', 'avg_trip': '  Fahrzeit', 'trip_count': 'Anzahl Fahrten'}
    ), width="stretch")

    # 6. Histogram (Distribution)
    st.subheader("4. Verteilung der Warte- und Fahrzeiten (Histogramm)")
    hist_df = load_hist()
    fig3, ax3 = plt.subplots(figsize=(10,4))
    ax3.hist(hist_df['wait_minutes'], bins=40, alpha=0.6, label='Wartezeit')
    ax3.hist(hist_df['trip_minutes'], bins=40, alpha=0.6, label='Fahrzeit')
    ax3.set_xlabel('Minuten')
    ax3.set_ylabel('Anzahl Fahrten')
    ax3.set_title('Verteilung der Warte- und Fahrzeiten')
    ax3.legend()
    st.pyplot(fig3)

    # 7. Heatmap by Hour & Day
    st.subheader("5. Heatmap: Wartezeit nach Stunde & Wochentag")
    heatmap_df = load_by_hour_day()
    # Prepare heatmap
    weekday_order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    pivot = pd.pivot_table(
        heatmap_df,
        values='avg_wait',
        index='weekday',
        columns='hour',
        aggfunc=np.mean
    ).reindex(weekday_order)
    fig4, ax4 = plt.subplots(figsize=(14,4))
    cax = ax4.imshow(pivot, aspect='auto', cmap='YlOrRd', origin='upper')
    ax4.set_xticks(range(24))
    ax4.set_xticklabels(range(24))
    ax4.set_yticks(range(len(weekday_order)))
    ax4.set_yticklabels(weekday_order)
    fig4.colorbar(cax, ax=ax4, label="  Wartezeit (min)")
    ax4.set_title("Heatmap:   Wartezeit nach Stunde und Tag")
    ax4.set_xlabel("Stunde")
    ax4.set_ylabel("Wochentag")
    st.pyplot(fig4)

    st.markdown("---")