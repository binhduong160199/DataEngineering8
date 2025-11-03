import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from data_utilities import database_connector

USER_STORY = (
    "Als Fahrgast möchte ich einen Überblick über die durchschnittliche Warte- und Fahrzeit bekommen, "
    "damit ich meine Fahrt besser planen kann"
)

def load_sql(query):
    engine = database_connector.get_sqlalchemy_engine()
    return pd.read_sql_query(query, engine)

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

def render():
    # Local dark card just for your dashboard section!
    st.markdown(
        """
        <div style="background-color: #181C22; border-radius: 18px; padding: 32px 28px 24px 28px; margin-bottom:24px;">
        """,
        unsafe_allow_html=True
    )

    st.header(f":blue[User Story]")
    st.markdown(
        "<span style='color:#b3e5fc; font-size:1.2em;'>"
        f"{USER_STORY}</span>", unsafe_allow_html=True
    )

    overall = load_overall()
    kpi1, kpi2 = st.columns(2)
    with kpi1:
        st.metric("Durchschnittliche Wartezeit (min)", f"{overall['avg_wait'][0]:.1f}", label_visibility="visible", help="Ø Wartezeit aller Fahrten (min)")
    with kpi2:
        st.metric("Durchschnittliche Fahrzeit (min)", f"{overall['avg_trip'][0]:.1f}", label_visibility="visible", help="Ø Fahrzeit aller Fahrten (min)")

    st.divider()

    st.subheader("Durchschnittliche Zeiten pro Anbieter")
    by_provider = load_by_provider()
    st.dataframe(
        by_provider.rename(columns={"avg_wait": "Wartezeit", "avg_trip": "Fahrzeit"}),
        width="stretch",
        hide_index=True
    )
    if not by_provider.empty:
        best = by_provider.nsmallest(1, "avg_wait")
        worst = by_provider.nlargest(1, "avg_wait")
        st.markdown(
            f"<span style='color:#81d4fa;'><b>Schnellster Anbieter:</b> {best.iloc[0,0]}, "
            f"<b>Langsamster Anbieter:</b> {worst.iloc[0,0]}</span>", unsafe_allow_html=True
        )

    st.subheader("Zeiten nach Stunde des Tages")
    hour_range = st.slider(
        "Wähle einen Stundenbereich",
        min_value=0, max_value=23, value=(7, 19)
    )
    by_hour = load_by_hour()
    by_hour = by_hour[(by_hour['pickup_hour'] >= hour_range[0]) & (by_hour['pickup_hour'] <= hour_range[1])]
    fig = px.line(
        by_hour, x="pickup_hour", y=["avg_wait", "avg_trip"],
        labels={"value": "Minuten", "pickup_hour": "Stunde"},
        color_discrete_sequence=["#4fc3f7", "#1976d2"],
        template="plotly_dark",
    )
    fig.update_layout(plot_bgcolor="#181C22", paper_bgcolor="#181C22")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Zeiten nach Wochentag")
    # Interactive toggle (only for your section!)
    option = st.radio(
        "Anzeigen:", options=["Beide", "Nur Wartezeit", "Nur Fahrzeit"], horizontal=True
    )
    by_weekday = load_by_weekday()
    if option == "Nur Wartezeit":
        y_data = ["avg_wait"]
    elif option == "Nur Fahrzeit":
        y_data = ["avg_trip"]
    else:
        y_data = ["avg_wait", "avg_trip"]

    fig2 = px.bar(
        by_weekday, x="weekday", y=y_data,
        labels={"value": "Minuten", "weekday": "Wochentag"},
        barmode="group", color_discrete_sequence=["#4fc3f7", "#1976d2"][:len(y_data)],
        template="plotly_dark",
    )
    fig2.update_layout(plot_bgcolor="#181C22", paper_bgcolor="#181C22")
    st.plotly_chart(fig2, use_container_width=True)
    with st.expander("Tabellarische Werte anzeigen"):
        st.dataframe(
            by_weekday.rename(
                columns={"weekday": "Wochentag", "avg_wait": "Wartezeit (min)", "avg_trip": "Fahrzeit (min)"}
            ),
            hide_index=True,
            use_container_width=True
        )

        # --- INTERAKTIVER BEREICH: Zonen mit längster/kürzester Wartezeit ---
    st.subheader("Zonen mit längster/kürzester Wartezeit (Top 10, >1000 Fahrten)")
    by_zone = load_by_zone()
    option_zone = st.radio(
        "Welche Zonen anzeigen?",
        options=["Top 10 längste Wartezeit", "Top 10 kürzeste Wartezeit"],
        horizontal=True
    )
    if option_zone == "Top 10 längste Wartezeit":
        top_zones = by_zone.nlargest(10, "avg_wait")
        sort_order = False
    else:
        top_zones = by_zone.nsmallest(10, "avg_wait")
        sort_order = True

    st.dataframe(
        top_zones.rename(
            columns={'pickup_zone': 'Zone', 'avg_wait': 'Wartezeit', 'avg_trip': 'Fahrzeit', 'trip_count': 'Anzahl Fahrten'}
        ),
        width="stretch",
        hide_index=True
    )

    fig_zone = px.bar(
        top_zones.sort_values("avg_wait", ascending=sort_order),
        x="avg_wait",
        y="pickup_zone",
        orientation="h",
        color="avg_wait",
        color_continuous_scale="Blues",
        labels={"pickup_zone": "Zone", "avg_wait": "Wartezeit (min)"},
        template="plotly_dark",
        title="Durchschnittliche Wartezeit nach Zone"
    )
    fig_zone.update_layout(
        plot_bgcolor="#181C22",
        paper_bgcolor="#181C22",
        yaxis=dict(categoryorder="total ascending" if sort_order else "total descending"),
        height=380,
        margin=dict(l=120, r=20, t=50, b=30)
    )
    st.plotly_chart(fig_zone, use_container_width=True)

    # --- INTERAKTIVER BEREICH: Histogramm ---
    st.subheader("Verteilung der Warte- und Fahrzeiten (Histogramm)")
    hist_df = load_hist()
    hist_mode = st.radio(
        "Anzeigen:",
        ["Beides (Overlay)", "Nur Wartezeit", "Nur Fahrzeit"],
        horizontal=True
    )
    if hist_mode == "Nur Wartezeit":
        columns_hist = ["wait_minutes"]
        colors_hist = ["#4fc3f7"]
    elif hist_mode == "Nur Fahrzeit":
        columns_hist = ["trip_minutes"]
        colors_hist = ["#1976d2"]
    else:
        columns_hist = ["wait_minutes", "trip_minutes"]
        colors_hist = ["#4fc3f7", "#1976d2"]

    fig3 = px.histogram(
        hist_df, x=columns_hist, nbins=40,
        color_discrete_sequence=colors_hist,
        labels={"value": "Minuten", "variable": "Art"},
        barmode="overlay", opacity=0.7,
        template="plotly_dark",
        title="Verteilung der Warte- und Fahrzeiten"
    )
    fig3.update_layout(plot_bgcolor="#181C22", paper_bgcolor="#181C22")
    st.plotly_chart(fig3, use_container_width=True)

    # --- INTERAKTIVER BEREICH: Heatmap ---
    st.subheader("Heatmap: Wartezeit nach Stunde & Wochentag")
    heatmap_df = load_by_hour_day()
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    selected_days = st.multiselect(
        "Wochentage auswählen:",
        weekday_order,
        default=weekday_order
    )
    hour_range_heatmap = st.slider(
        "Stundenbereich auswählen:",
        min_value=0, max_value=23, value=(0, 23)
    )
    filtered_heatmap = heatmap_df[
        heatmap_df['weekday'].isin(selected_days) &
        (heatmap_df['hour'] >= hour_range_heatmap[0]) &
        (heatmap_df['hour'] <= hour_range_heatmap[1])
    ]
    pivot = pd.pivot_table(
        filtered_heatmap,
        values='avg_wait',
        index='weekday',
        columns='hour',
        aggfunc=np.mean
    ).reindex(selected_days)
    fig4 = px.imshow(
        pivot,
        color_continuous_scale="Blues",
        labels=dict(x="Stunde", y="Wochentag", color="Wartezeit (min)"),
        aspect="auto",
        template="plotly_dark",
        title="Heatmap: Wartezeit nach Stunde und Tag"
    )
    fig4.update_layout(plot_bgcolor="#181C22", paper_bgcolor="#181C22", coloraxis_showscale=True)
    st.plotly_chart(fig4, use_container_width=True)