import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from data_utilities import database_connector
from sqlalchemy import text, bindparam

# Configuration & Constants
TAKEHOME_EXPR = "COALESCE(t.driver_pay,0) + COALESCE(t.tips,0)"
TOTAL_REVENUE_EXPR = """COALESCE(t.base_passenger_fare,0) + COALESCE(t.tolls,0) + 
                        COALESCE(t.bcf,0) + COALESCE(t.sales_tax,0) + 
                        COALESCE(t.congestion_surcharge,0) + COALESCE(t.airport_fee,0) + 
                        COALESCE(t.tips,0)"""

# Set matplotlib style
sns.set_style("whitegrid")
plt.rcParams['figure.facecolor'] = 'white'

# Helper Functions
def safe_float(value, default=0.0):
    """Safely convert value to float, handling None and NaN."""
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Safely convert value to int, handling None and NaN."""
    if value is None or pd.isna(value):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

# Data Access Functions
@st.cache_data(show_spinner=True, ttl=600)
def load_providers():
    engine = database_connector.get_sqlalchemy_engine()
    return pd.read_sql_query("SELECT id, provider_name FROM providers ORDER BY provider_name", engine)

@st.cache_data(show_spinner=True, ttl=600)
def load_zones():
    engine = database_connector.get_sqlalchemy_engine()
    return pd.read_sql_query("SELECT id, zone_name FROM taxi_zones ORDER BY zone_name", engine)

def _bind_zone_expanding(query_text: str, zone_ids: list[int] | None):
    q = text(query_text)
    extra = {}
    if zone_ids:
        q = q.bindparams(bindparam("zone_ids", expanding=True))
        extra["zone_ids"] = tuple(zone_ids)
    return q, extra

@st.cache_data(show_spinner=True, ttl=600)
def load_market_benchmarks(start_dt: datetime, end_dt: datetime, zone_ids=None):
    engine = database_connector.get_sqlalchemy_engine()
    base_where = "t.pickup_datetime >= :start_dt AND t.pickup_datetime < :end_dt"
    zone_where = " AND t.pu_location_id IN :zone_ids" if zone_ids else ""

    provider_sql = f"""
        SELECT p.provider_name,
               COUNT(*) AS trips,
               SUM({TAKEHOME_EXPR}) AS total_takehome,
               AVG({TAKEHOME_EXPR}) AS avg_takehome_per_trip,
               SUM(COALESCE(t.trip_miles,0)) AS miles,
               SUM(COALESCE(t.trip_time,0)) AS minutes,
               AVG(COALESCE(t.trip_miles,0)) AS avg_miles,
               AVG(COALESCE(t.trip_time,0)) AS avg_minutes,
               SUM(COALESCE(t.tips,0)) AS total_tips,
               AVG(COALESCE(t.tips,0)) AS avg_tips,
               SUM({TOTAL_REVENUE_EXPR}) AS total_revenue,
               AVG({TOTAL_REVENUE_EXPR}) AS avg_revenue_per_trip
        FROM trips t
        JOIN providers p ON p.id = t.provider_id
        WHERE {base_where}{zone_where}
        GROUP BY p.provider_name
        ORDER BY total_takehome DESC
    """
    
    overall_sql = f"""
        SELECT COUNT(*) AS trips,
               SUM({TAKEHOME_EXPR}) AS total_takehome,
               AVG({TAKEHOME_EXPR}) AS avg_takehome_per_trip,
               SUM(COALESCE(t.tips,0)) AS total_tips,
               AVG(COALESCE(t.tips,0)) AS avg_tips,
               SUM(COALESCE(t.trip_miles,0)) AS total_miles,
               AVG(COALESCE(t.trip_miles,0)) AS avg_miles,
               SUM(COALESCE(t.trip_time,0)) AS total_minutes,
               AVG(COALESCE(t.trip_time,0)) AS avg_minutes
        FROM trips t
        WHERE {base_where}{zone_where}
    """

    prov_q, prov_extra = _bind_zone_expanding(provider_sql, zone_ids)
    overall_q, overall_extra = _bind_zone_expanding(overall_sql, zone_ids)
    params = {"start_dt": start_dt, "end_dt": end_dt}

    prov = pd.read_sql_query(prov_q, engine, params={**params, **prov_extra})
    overall = pd.read_sql_query(overall_q, engine, params={**params, **overall_extra}).iloc[0]

    rank_df = prov[["provider_name", "avg_takehome_per_trip"]].copy()
    if len(rank_df) > 0:
        rank_df["percentile"] = rank_df["avg_takehome_per_trip"].rank(pct=True) * 100
    else:
        rank_df["percentile"] = []

    return prov, overall, rank_df

@st.cache_data(show_spinner=True, ttl=600)
def load_timeseries(provider_name: str | None, start_dt: datetime, end_dt: datetime, zone_ids=None):
    engine = database_connector.get_sqlalchemy_engine()
    base_where = "t.pickup_datetime >= :start_dt AND t.pickup_datetime < :end_dt"
    zone_where = " AND t.pu_location_id IN :zone_ids" if zone_ids else ""
    prov_where = " AND p.provider_name = :provider_name" if provider_name else ""

    sql = f"""
        SELECT DATE_TRUNC('day', t.pickup_datetime) AS day,
               SUM({TAKEHOME_EXPR}) AS takehome,
               COUNT(*) AS trips,
               AVG({TAKEHOME_EXPR}) AS avg_takehome,
               SUM(COALESCE(t.tips,0)) AS tips,
               SUM(COALESCE(t.trip_miles,0)) AS miles
        FROM trips t
        JOIN providers p ON p.id = t.provider_id
        WHERE {base_where}{zone_where}{prov_where}
        GROUP BY 1
        ORDER BY 1
    """

    q, extra = _bind_zone_expanding(sql, zone_ids)
    params = {"start_dt": start_dt, "end_dt": end_dt}
    if provider_name:
        params["provider_name"] = provider_name
    return pd.read_sql_query(q, engine, params={**params, **extra})

@st.cache_data(show_spinner=True, ttl=600)
def load_hourly_patterns(provider_name: str | None, start_dt: datetime, end_dt: datetime, zone_ids=None):
    engine = database_connector.get_sqlalchemy_engine()
    base_where = "t.pickup_datetime >= :start_dt AND t.pickup_datetime < :end_dt"
    zone_where = " AND t.pu_location_id IN :zone_ids" if zone_ids else ""
    prov_where = " AND p.provider_name = :provider_name" if provider_name else ""

    sql = f"""
        SELECT EXTRACT(HOUR FROM t.pickup_datetime) AS hour,
               COUNT(*) AS trips,
               AVG({TAKEHOME_EXPR}) AS avg_takehome,
               SUM({TAKEHOME_EXPR}) AS total_takehome
        FROM trips t
        JOIN providers p ON p.id = t.provider_id
        WHERE {base_where}{zone_where}{prov_where}
        GROUP BY 1
        ORDER BY 1
    """

    q, extra = _bind_zone_expanding(sql, zone_ids)
    params = {"start_dt": start_dt, "end_dt": end_dt}
    if provider_name:
        params["provider_name"] = provider_name
    return pd.read_sql_query(q, engine, params={**params, **extra})

@st.cache_data(show_spinner=True, ttl=600)
def load_zone_performance(provider_name: str | None, start_dt: datetime, end_dt: datetime, zone_ids=None, limit=10):
    engine = database_connector.get_sqlalchemy_engine()
    base_where = "t.pickup_datetime >= :start_dt AND t.pickup_datetime < :end_dt"
    zone_where = " AND t.pu_location_id IN :zone_ids" if zone_ids else ""
    prov_where = " AND p.provider_name = :provider_name" if provider_name else ""

    sql = f"""
        SELECT tz.zone_name,
               COUNT(*) AS trips,
               AVG({TAKEHOME_EXPR}) AS avg_takehome,
               SUM({TAKEHOME_EXPR}) AS total_takehome
        FROM trips t
        JOIN providers p ON p.id = t.provider_id
        JOIN taxi_zones tz ON tz.id = t.pu_location_id
        WHERE {base_where}{zone_where}{prov_where}
        GROUP BY tz.zone_name
        ORDER BY total_takehome DESC
        LIMIT {limit}
    """

    q, extra = _bind_zone_expanding(sql, zone_ids)
    params = {"start_dt": start_dt, "end_dt": end_dt}
    if provider_name:
        params["provider_name"] = provider_name
    return pd.read_sql_query(q, engine, params={**params, **extra})

@st.cache_data(show_spinner=True, ttl=600)
def load_weekday_patterns(provider_name: str | None, start_dt: datetime, end_dt: datetime, zone_ids=None):
    """Load trip patterns by day of week."""
    engine = database_connector.get_sqlalchemy_engine()
    base_where = "t.pickup_datetime >= :start_dt AND t.pickup_datetime < :end_dt"
    zone_where = " AND t.pu_location_id IN :zone_ids" if zone_ids else ""
    prov_where = " AND p.provider_name = :provider_name" if provider_name else ""

    sql = f"""
        SELECT EXTRACT(DOW FROM t.pickup_datetime) AS dow,
               COUNT(*) AS trips,
               AVG({TAKEHOME_EXPR}) AS avg_takehome,
               SUM({TAKEHOME_EXPR}) AS total_takehome
        FROM trips t
        JOIN providers p ON p.id = t.provider_id
        WHERE {base_where}{zone_where}{prov_where}
        GROUP BY 1
        ORDER BY 1
    """

    q, extra = _bind_zone_expanding(sql, zone_ids)
    params = {"start_dt": start_dt, "end_dt": end_dt}
    if provider_name:
        params["provider_name"] = provider_name
    df = pd.read_sql_query(q, engine, params={**params, **extra})
    
    # Map day of week numbers to names
    day_names = {0: 'Sonntag', 1: 'Montag', 2: 'Dienstag', 3: 'Mittwoch', 
                 4: 'Donnerstag', 5: 'Freitag', 6: 'Samstag'}
    df['day_name'] = df['dow'].map(day_names)
    return df

# Calculation Functions
def compute_my_metrics_from_provider(prov_df: pd.DataFrame, rank_df: pd.DataFrame, provider_name: str):
    row = prov_df[prov_df.provider_name == provider_name]
    if row.empty:
        return {
            "trips": 0, "total": 0.0, "avg": 0.0, "percentile": np.nan,
            "tips": 0.0, "avg_tips": 0.0, "miles": 0.0, "minutes": 0.0,
            "avg_miles": 0.0, "avg_minutes": 0.0,
            "label": f"{provider_name} - keine Daten im Zeitraum"
        }
    
    r = row.iloc[0]
    percentile = float(rank_df.loc[rank_df.provider_name == provider_name, "percentile"].iloc[0]) if len(rank_df) else np.nan
    
    return {
        "trips": safe_int(r["trips"]),
        "total": safe_float(r["total_takehome"]),
        "avg": safe_float(r["avg_takehome_per_trip"]),
        "tips": safe_float(r["total_tips"]),
        "avg_tips": safe_float(r["avg_tips"]),
        "miles": safe_float(r["miles"]),
        "minutes": safe_float(r["minutes"]),
        "avg_miles": safe_float(r["avg_miles"]),
        "avg_minutes": safe_float(r["avg_minutes"]),
        "percentile": percentile,
        "label": provider_name
    }

def compute_my_metrics_manual(trips: int, total_takehome: float = None, avg_takehome: float = None, 
                              tips: float = None, miles: float = None, minutes: float = None,
                              rank_df: pd.DataFrame | None = None):
    total, avg = 0.0, 0.0
    trips = safe_int(trips)

    if avg_takehome is not None and avg_takehome > 0:
        avg = float(avg_takehome)
        total = float(trips * avg)
    elif total_takehome is not None and total_takehome > 0:
        total = float(total_takehome)
        avg = float(total / trips) if trips > 0 else 0.0

    percentile = np.nan
    if rank_df is not None and len(rank_df) > 0 and avg > 0:
        percentile = float((rank_df["avg_takehome_per_trip"] <= avg).mean() * 100)

    return {
        "trips": trips,
        "total": total,
        "avg": avg,
        "tips": safe_float(tips),
        "avg_tips": safe_float(tips / trips) if trips > 0 else 0.0,
        "miles": safe_float(miles),
        "minutes": safe_float(minutes),
        "avg_miles": safe_float(miles / trips) if trips > 0 else 0.0,
        "avg_minutes": safe_float(minutes / trips) if trips > 0 else 0.0,
        "percentile": percentile,
        "label": "Manuelle Eingabe"
    }

# Visualization Functions
def plot_provider_comparison(prov_df, my_avg, selected_provider, top_n=10):
    fig, ax = plt.subplots(figsize=(10, 6))
    plot_df = prov_df.sort_values("avg_takehome_per_trip", ascending=False).head(top_n)
    
    colors = ['#1f77b4' if p != selected_provider else '#ff7f0e' for p in plot_df["provider_name"]]
    bars = ax.barh(plot_df["provider_name"], plot_df["avg_takehome_per_trip"], color=colors)
    
    ax.set_xlabel("Durchschnittliche Einnahmen pro Fahrt ($)", fontsize=11)
    ax.set_ylabel("Anbieter", fontsize=11)
    ax.set_title(f"Top {top_n} Anbieter nach Durchschnittseinnahmen pro Fahrt", fontsize=12, fontweight='bold')
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, f'${width:.2f}', 
                ha='left', va='center', fontsize=9)
    
    plt.tight_layout()
    return fig

def plot_earnings_distribution(prov_df, my_avg):
    fig, ax = plt.subplots(figsize=(10, 5))
    
    ax.hist(prov_df["avg_takehome_per_trip"], bins=20, alpha=0.7, color='steelblue', edgecolor='black')
    
    ax.axvline(my_avg, color='red', linestyle='--', linewidth=2, label=f'Ihre Position: ${my_avg:.2f}')
    
    median_val = prov_df["avg_takehome_per_trip"].median()
    ax.axvline(median_val, color='green', linestyle='--', linewidth=2, label=f'Median: ${median_val:.2f}')
    
    ax.set_xlabel("Durchschnittliche Einnahmen pro Fahrt ($)", fontsize=11)
    ax.set_ylabel("Anzahl Anbieter", fontsize=11)
    ax.set_title("Verteilung der Anbieter-Durchschnitte", fontsize=12, fontweight='bold')
    ax.legend()
    plt.tight_layout()
    return fig

def plot_timeseries_comparison(my_ts, market_ts, metric='takehome', is_provider_mode=True):
    fig, ax = plt.subplots(figsize=(12, 5))
    
    if len(my_ts) > 0:
        label = "Anbieter Einnahmen" if is_provider_mode else "Ihre Einnahmen"
        ax.plot(my_ts["day"], my_ts[metric], marker="o", label=label, linewidth=2, markersize=6)
    
    if len(market_ts) > 0:
        market_avg = market_ts[metric] / market_ts["trips"] if metric == "takehome" else market_ts[metric]
        ax.plot(market_ts["day"], market_avg, marker="s", label="Markt Durchschnitt pro Fahrt", 
                linewidth=2, markersize=6, alpha=0.7)
    
    ax.set_ylabel("Einnahmen ($)", fontsize=11)
    ax.set_xlabel("Datum", fontsize=11)
    ax.set_title("Zeitlicher Verlauf der Einnahmen", fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

def plot_hourly_pattern(hourly_df, market_hourly_df=None, is_provider_mode=True):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    label = "Anbieter Fahrten" if is_provider_mode else "Ihre Fahrten"
    if len(hourly_df) > 0:
        ax1.bar(hourly_df["hour"], hourly_df["trips"], alpha=0.7, color='steelblue', label=label)
    if market_hourly_df is not None and len(market_hourly_df) > 0:
        ax1.plot(market_hourly_df["hour"], market_hourly_df["trips"], 
                color='orange', marker='o', linewidth=2, label='Markt gesamt')
    ax1.set_xlabel("Stunde des Tages", fontsize=11)
    ax1.set_ylabel("Anzahl Fahrten", fontsize=11)
    ax1.set_title("Fahrten nach Tageszeit", fontsize=12, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    label_earnings = "Anbieter Durchschnittseinnahmen" if is_provider_mode else "Ihre Durchschnittseinnahmen"
    if len(hourly_df) > 0:
        ax2.plot(hourly_df["hour"], hourly_df["avg_takehome"], 
                marker='o', linewidth=2, color='green', label=label_earnings)
    if market_hourly_df is not None and len(market_hourly_df) > 0:
        ax2.plot(market_hourly_df["hour"], market_hourly_df["avg_takehome"],
                marker='s', linewidth=2, color='red', alpha=0.7, label='Markt Durchschnittseinnahmen')
    ax2.set_xlabel("Stunde des Tages", fontsize=11)
    ax2.set_ylabel("Durchschnittseinnahmen pro Fahrt ($)", fontsize=11)
    ax2.set_title("Durchschnittliche Einnahmen nach Tageszeit", fontsize=12, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig

def plot_zone_performance(zone_df, title="Top Pickup-Zonen"):
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(zone_df)))
    bars = ax.barh(zone_df["zone_name"], zone_df["avg_takehome"], color=colors)
    
    ax.set_xlabel("Durchschnittliche Einnahmen pro Fahrt ($)", fontsize=11)
    ax.set_ylabel("Zone", fontsize=11)
    ax.set_title(title, fontsize=12, fontweight='bold')
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2, 
                f'${width:.2f} ({int(zone_df.iloc[i]["trips"])} Fahrten)', 
                ha='left', va='center', fontsize=9)
    
    plt.tight_layout()
    return fig

def plot_weekday_pattern(weekday_df, is_provider_mode=True):
    """Plot trips and earnings by day of week."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    day_order = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    weekday_df['day_name'] = pd.Categorical(weekday_df['day_name'], categories=day_order, ordered=True)
    weekday_df = weekday_df.sort_values('day_name')
    
    # Trips by weekday
    ax1.bar(weekday_df["day_name"], weekday_df["trips"], alpha=0.7, color='steelblue')
    ax1.set_xlabel("Wochentag", fontsize=11)
    ax1.set_ylabel("Anzahl Fahrten", fontsize=11)
    ax1.set_title("Fahrten nach Wochentag", fontsize=12, fontweight='bold')
    ax1.tick_params(axis='x', rotation=45)
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Earnings by weekday
    ax2.plot(weekday_df["day_name"], weekday_df["avg_takehome"], 
            marker='o', linewidth=2, color='green', markersize=8)
    ax2.set_xlabel("Wochentag", fontsize=11)
    ax2.set_ylabel("Durchschnittseinnahmen pro Fahrt ($)", fontsize=11)
    ax2.set_title("Durchschnittliche Einnahmen nach Wochentag", fontsize=12, fontweight='bold')
    ax2.tick_params(axis='x', rotation=45)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig

# Main App
def render(page_title: str | None = "NYC TLC Driver Benchmark"):
    try:
        if page_title:
            st.set_page_config(page_title=page_title, layout="wide")
    except Exception:
        pass

    st.title("NYC TLC Driver Performance Benchmark")
    st.markdown("""
    Vergleichen Sie Ihre Einnahmen als Taxifahrer mit Branchenbenchmarks, um Ihre Leistung 
    besser zu bewerten und Optimierungspotenziale zu identifizieren.
    """)

    # Filters in Main Dashboard
    st.subheader("Filter und Einstellungen")
    
    filter_container = st.container(border=True)
    with filter_container:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Zeitraum**")
            default_start = datetime(2025, 7, 1)
            default_end = datetime(2025, 8, 1)
            
            start_dt = st.date_input("Startdatum", value=default_start, key="start_date")
            end_dt = st.date_input("Enddatum (exklusiv)", value=default_end, key="end_date")
            start_dt = datetime.combine(start_dt, datetime.min.time())
            end_dt = datetime.combine(end_dt, datetime.min.time())
        
        with col2:
            st.markdown("**Zonen-Filter**")
            with st.spinner("Lade Zonen..."):
                zones_df = load_zones()
            zone_names = st.multiselect(
                "Pickup-Zonen (optional)",
                options=zones_df["zone_name"].tolist(),
                help="Filtern nach Pickup-Zonen. Leer lassen für alle Zonen."
            )
            zone_ids = zones_df.loc[zones_df.zone_name.isin(zone_names), "id"].tolist() if zone_names else None
        
        with col3:
            st.markdown("**Dateneingabe-Modus**")
            mode = st.radio(
                "Wie möchten Sie Ihre Daten eingeben?",
                ["Anbieter-Analyse", "Persönliche Analyse"],
                help="Wählen Sie zwischen Anbieter-Vergleich oder persönlicher Leistungsanalyse"
            )

    # Load Market Data
    with st.spinner("Lade Marktdaten..."):
        prov_df, overall_row, rank_df = load_market_benchmarks(start_dt, end_dt, zone_ids)

    is_provider_mode = (mode == "Anbieter-Analyse")

    # User Input Section
    st.subheader("Datenauswahl")
    
    with st.spinner("Lade Anbieter..."):
        providers_df = load_providers()
    
    selected_provider = None
    manual_trips = 0
    manual_total = None
    manual_avg = None
    manual_tips = None
    manual_miles = None
    manual_minutes = None

    if is_provider_mode:
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_provider = st.selectbox(
                "Anbieter auswählen",
                options=providers_df["provider_name"].tolist() if len(providers_df) else [],
                index=0 if len(providers_df) else None,
            )
        with col2:
            st.info(f"Zeitraum: {(end_dt - start_dt).days} Tage")
        
        my = compute_my_metrics_from_provider(prov_df, rank_df, selected_provider)
    else:
        with st.form("manual_input_form"):
            st.markdown("**Geben Sie Ihre persönlichen Fahrtdaten ein:**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                manual_trips = st.number_input("Anzahl Fahrten", min_value=0, step=1, value=0)
            with col2:
                input_mode = st.radio("Eingabeart", ["Durchschnitt pro Fahrt", "Gesamteinnahmen"])
            with col3:
                if input_mode == "Durchschnitt pro Fahrt":
                    manual_avg = st.number_input("Durchschnittseinnahmen pro Fahrt ($)", 
                                                min_value=0.0, step=1.0, value=0.0, format="%.2f")
                else:
                    manual_total = st.number_input("Gesamteinnahmen ($)", 
                                                  min_value=0.0, step=10.0, value=0.0, format="%.2f")
            with col4:
                manual_tips = st.number_input("Trinkgelder gesamt ($)", 
                                             min_value=0.0, step=1.0, value=0.0, format="%.2f")
            
            col5, col6, col7 = st.columns([1, 1, 2])
            with col5:
                manual_miles = st.number_input("Gesamte Meilen", 
                                              min_value=0.0, step=1.0, value=0.0, format="%.2f")
            with col6:
                manual_minutes = st.number_input("Gesamte Minuten", 
                                                min_value=0.0, step=1.0, value=0.0, format="%.2f")
            
            submitted = st.form_submit_button("Berechnen", type="primary")
        
        my = compute_my_metrics_manual(
            trips=manual_trips or 0,
            total_takehome=manual_total,
            avg_takehome=manual_avg,
            tips=manual_tips,
            miles=manual_miles,
            minutes=manual_minutes,
            rank_df=rank_df
        )

    # Key Metrics Dashboard
    st.subheader("Wichtigste Kennzahlen")
    
    m_avg = safe_float(overall_row["avg_takehome_per_trip"])
    m_avg_tips = safe_float(overall_row["avg_tips"])
    m_avg_miles = safe_float(overall_row["avg_miles"])
    m_avg_minutes = safe_float(overall_row["avg_minutes"])
    
    earnings_delta = my['avg'] - m_avg
    earnings_delta_pct = (earnings_delta / m_avg * 100) if m_avg > 0 else 0
    
    if is_provider_mode:
        # Provider Mode - Show provider metrics vs market
        st.markdown(f"### Anbieter: {my['label']}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Gesamtfahrten",
                f"{my['trips']:,}",
                help=f"Anzahl der Fahrten im Zeitraum. Markt gesamt: {safe_int(overall_row['trips']):,}"
            )
        
        with col2:
            st.metric(
                "Gesamteinnahmen",
                f"${my['total']:,.2f}",
                help=f"Gesamte Fahrereinnahmen (Driver Pay + Tips)"
            )
        
        with col3:
            market_share = (my['trips'] / safe_int(overall_row['trips']) * 100) if safe_int(overall_row['trips']) > 0 else 0
            st.metric(
                "Marktanteil",
                f"{market_share:.1f}%",
                help=f"Anteil der Fahrten am Gesamtmarkt"
            )
        
        with col4:
            position = safe_int(prov_df[prov_df['provider_name'] == my['label']].index[0] + 1) if len(prov_df) > 0 else 0
            total_providers = len(prov_df)
            st.metric(
                "Ranking",
                f"{position} von {total_providers}",
                help=f"Position nach Gesamteinnahmen sortiert"
            )
        
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            st.metric(
                "Ø Einnahmen pro Fahrt",
                f"${my['avg']:.2f}",
                f"{earnings_delta:+.2f}$ ({earnings_delta_pct:+.1f}%)",
                delta_color="normal",
                help=f"Vergleich zum Marktdurchschnitt von ${m_avg:.2f}"
            )
        
        with col6:
            st.metric(
                "Ø Trinkgeld pro Fahrt",
                f"${my['avg_tips']:.2f}",
                f"{my['avg_tips'] - m_avg_tips:+.2f}$",
                delta_color="normal",
                help=f"Marktdurchschnitt: ${m_avg_tips:.2f}"
            )
        
        with col7:
            st.metric(
                "Ø Meilen pro Fahrt",
                f"{my['avg_miles']:.2f}",
                f"{my['avg_miles'] - m_avg_miles:+.2f}",
                delta_color="off",
                help=f"Marktdurchschnitt: {m_avg_miles:.2f} Meilen"
            )
        
        with col8:
            st.metric(
                "Ø Minuten pro Fahrt",
                f"{my['avg_minutes']:.1f}",
                f"{my['avg_minutes'] - m_avg_minutes:+.1f}",
                delta_color="off",
                help=f"Marktdurchschnitt: {m_avg_minutes:.1f} Minuten"
            )
        
    else:
        # Personal Mode - Show user metrics vs market with percentile
        st.markdown("### Ihre persönliche Leistung")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Ihre Durchschnittseinnahmen pro Fahrt",
                f"${my['avg']:,.2f}",
                f"{earnings_delta:+.2f}$ ({earnings_delta_pct:+.1f}%)",
                help=f"Vergleich zum Marktdurchschnitt von ${m_avg:.2f}"
            )
        
        with col2:
            pct_txt = "Keine Daten" if np.isnan(my["percentile"]) else f"{my['percentile']:.0f}. Perzentil"
            st.metric(
                "Ihr Ranking",
                pct_txt,
                help="Ihr Perzentil im Vergleich zu allen Anbietern. 90. Perzentil bedeutet, Sie verdienen mehr als 90% der Anbieter."
            )
        
        with col3:
            st.metric(
                "Ihre Gesamteinnahmen",
                f"${my['total']:,.2f}",
                f"{my['trips']} Fahrten",
                help=f"Ihre Gesamteinnahmen im gewählten Zeitraum"
            )
        
        with col4:
            tips_pct = (my['avg_tips'] / my['avg'] * 100) if my['avg'] > 0 else 0
            st.metric(
                "Ihr Ø Trinkgeld pro Fahrt",
                f"${my['avg_tips']:,.2f}",
                f"{tips_pct:.1f}% der Einnahmen",
                help=f"Marktdurchschnitt: ${m_avg_tips:.2f}"
            )
        
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            st.metric(
                "Ihre Ø Meilen pro Fahrt",
                f"{my['avg_miles']:.2f}",
                help=f"Marktdurchschnitt: {m_avg_miles:.2f} Meilen"
            )
        
        with col6:
            st.metric(
                "Ihre Ø Minuten pro Fahrt",
                f"{my['avg_minutes']:.1f}",
                help=f"Marktdurchschnitt: {m_avg_minutes:.1f} Minuten"
            )
        
        with col7:
            hourly_rate = (my['avg'] / (my['avg_minutes'] / 60)) if my['avg_minutes'] > 0 else 0
            market_hourly = (m_avg / (m_avg_minutes / 60)) if m_avg_minutes > 0 else 0
            st.metric(
                "Ihr Stundensatz (geschätzt)",
                f"${hourly_rate:.2f}/h",
                f"{hourly_rate - market_hourly:+.2f}$/h",
                help=f"Berechnet aus Ø Einnahmen und Ø Fahrtzeit. Markt: ${market_hourly:.2f}/h"
            )
        
        with col8:
            efficiency = (my['avg'] / my['avg_miles']) if my['avg_miles'] > 0 else 0
            market_efficiency = (m_avg / m_avg_miles) if m_avg_miles > 0 else 0
            st.metric(
                "Ihre Effizienz ($/Meile)",
                f"${efficiency:.2f}",
                f"{efficiency - market_efficiency:+.2f}",
                help=f"Einnahmen pro gefahrene Meile. Markt: ${market_efficiency:.2f}"
            )

    st.divider()

    # Visualizations
    st.subheader("Detaillierte Analysen")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Anbieter-Vergleich",
        "Zeitliche Entwicklung",
        "Tageszeit-Analyse",
        "Wochentag-Analyse",
        "Zonen-Performance"
    ])
    
    with tab1:
        st.markdown("### Vergleich mit anderen Anbietern")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            top_n = st.slider("Anzahl Top-Anbieter", 5, min(20, len(prov_df)), 10)
            if selected_provider:
                fig = plot_provider_comparison(prov_df, my['avg'], selected_provider, top_n)
            else:
                fig = plot_provider_comparison(prov_df, my['avg'], None, top_n)
            st.pyplot(fig, clear_figure=True)
        
        with col2:
            st.markdown("#### Insights")
            if len(prov_df) > 0:
                best_provider = prov_df.iloc[0]
                
                if is_provider_mode:
                    st.info(f"""
                    **Bester Anbieter:** {best_provider['provider_name']}  
                    Durchschnitt ${best_provider['avg_takehome_per_trip']:.2f} pro Fahrt
                    
                    **Ausgewählter Anbieter:** {my['label']}  
                    Durchschnitt ${my['avg']:.2f} pro Fahrt
                    
                    **Differenz zum Besten:** ${my['avg'] - best_provider['avg_takehome_per_trip']:.2f}
                    """)
                    
                    if my['avg'] > m_avg:
                        st.success(f"Dieser Anbieter verdient {earnings_delta_pct:.1f}% mehr als der Marktdurchschnitt!")
                    else:
                        st.warning(f"Dieser Anbieter verdient {abs(earnings_delta_pct):.1f}% weniger als der Marktdurchschnitt.")
                else:
                    st.info(f"""
                    **Bester Anbieter:** {best_provider['provider_name']}  
                    Durchschnitt ${best_provider['avg_takehome_per_trip']:.2f} pro Fahrt
                    
                    **Ihre Position:** {my['label']}  
                    Durchschnitt ${my['avg']:.2f} pro Fahrt
                    
                    **Differenz zum Besten:** ${my['avg'] - best_provider['avg_takehome_per_trip']:.2f}
                    """)
                    
                    if my['avg'] > m_avg:
                        st.success(f"Sie verdienen {earnings_delta_pct:.1f}% mehr als der Marktdurchschnitt!")
                    else:
                        st.warning(f"Sie verdienen {abs(earnings_delta_pct):.1f}% weniger als der Marktdurchschnitt.")
        
        st.divider()
        
        if len(prov_df) > 1 and not is_provider_mode:
            st.markdown("### Verteilung der Anbieter-Einnahmen")
            fig = plot_earnings_distribution(prov_df, my['avg'])
            st.pyplot(fig, clear_figure=True)
    
    with tab2:
        st.markdown("### Zeitlicher Verlauf der Einnahmen")
        
        if is_provider_mode and selected_provider:
            with st.spinner("Lade Zeitreihen..."):
                my_ts = load_timeseries(selected_provider, start_dt, end_dt, zone_ids)
                market_ts = load_timeseries(None, start_dt, end_dt, zone_ids)
            
            if len(my_ts) > 0:
                market_ts['avg_per_trip'] = market_ts['takehome'] / market_ts['trips']
                
                fig = plot_timeseries_comparison(my_ts, market_ts, is_provider_mode=True)
                st.pyplot(fig, clear_figure=True)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    daily_avg = my_ts['takehome'].mean()
                    st.metric("Durchschnittliche Tageseinnahmen", f"${daily_avg:,.2f}")
                with col2:
                    best_day = my_ts.loc[my_ts['takehome'].idxmax()]
                    st.metric("Bester Tag", f"${best_day['takehome']:,.2f}", 
                             f"{best_day['day'].strftime('%d.%m.%Y')}")
                with col3:
                    worst_day = my_ts.loc[my_ts['takehome'].idxmin()]
                    st.metric("Schwächster Tag", f"${worst_day['takehome']:,.2f}",
                             f"{worst_day['day'].strftime('%d.%m.%Y')}")
                with col4:
                    trend = "Steigend" if my_ts['takehome'].iloc[-1] > my_ts['takehome'].iloc[0] else "Fallend"
                    st.metric("Trend", trend)
            else:
                st.info("Keine Zeitreihendaten für den gewählten Zeitraum verfügbar.")
        elif not is_provider_mode:
            st.info("Zeitreihenanalyse ist nur im Anbieter-Analyse-Modus verfügbar. Wechseln Sie zu 'Anbieter-Analyse' und wählen Sie einen Anbieter aus.")
        else:
            st.info("Bitte wählen Sie einen Anbieter aus.")
    
    with tab3:
        st.markdown("### Performance nach Tageszeit")
        
        if is_provider_mode and selected_provider:
            with st.spinner("Lade Stundenmuster..."):
                my_hourly = load_hourly_patterns(selected_provider, start_dt, end_dt, zone_ids)
                market_hourly = load_hourly_patterns(None, start_dt, end_dt, zone_ids)
            
            if len(my_hourly) > 0:
                fig = plot_hourly_pattern(my_hourly, market_hourly, is_provider_mode=True)
                st.pyplot(fig, clear_figure=True)
                
                st.markdown("#### Beste Zeiten")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Höchste Einnahmen pro Fahrt**")
                    best_hours_earnings = my_hourly.nlargest(5, 'avg_takehome')[['hour', 'avg_takehome', 'trips']]
                    for _, row in best_hours_earnings.iterrows():
                        st.write(f"- {int(row['hour']):02d}:00 Uhr: ${row['avg_takehome']:.2f} ({int(row['trips'])} Fahrten)")
                
                with col2:
                    st.markdown("**Meiste Fahrten**")
                    best_hours_volume = my_hourly.nlargest(5, 'trips')[['hour', 'trips', 'avg_takehome']]
                    for _, row in best_hours_volume.iterrows():
                        st.write(f"- {int(row['hour']):02d}:00 Uhr: {int(row['trips'])} Fahrten (${row['avg_takehome']:.2f})")
            else:
                st.info("Keine Stundendaten für den gewählten Zeitraum verfügbar.")
        elif not is_provider_mode:
            st.info("Tageszeit-Analyse ist nur im Anbieter-Analyse-Modus verfügbar.")
        else:
            st.info("Bitte wählen Sie einen Anbieter aus.")
    
    with tab4:
        st.markdown("### Performance nach Wochentag")
        
        if is_provider_mode and selected_provider:
            with st.spinner("Lade Wochentagsmuster..."):
                my_weekday = load_weekday_patterns(selected_provider, start_dt, end_dt, zone_ids)
            
            if len(my_weekday) > 0:
                fig = plot_weekday_pattern(my_weekday, is_provider_mode=True)
                st.pyplot(fig, clear_figure=True)
                
                st.markdown("#### Wochentag-Statistiken")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Stärkste Tage (nach Einnahmen)**")
                    best_days = my_weekday.nlargest(3, 'avg_takehome')[['day_name', 'avg_takehome', 'trips']]
                    for _, row in best_days.iterrows():
                        st.write(f"- {row['day_name']}: ${row['avg_takehome']:.2f} ({int(row['trips'])} Fahrten)")
                
                with col2:
                    st.markdown("**Verkehrsreichste Tage (nach Fahrten)**")
                    busiest_days = my_weekday.nlargest(3, 'trips')[['day_name', 'trips', 'avg_takehome']]
                    for _, row in busiest_days.iterrows():
                        st.write(f"- {row['day_name']}: {int(row['trips'])} Fahrten (${row['avg_takehome']:.2f})")
            else:
                st.info("Keine Wochentagsdaten für den gewählten Zeitraum verfügbar.")
        elif not is_provider_mode:
            st.info("Wochentag-Analyse ist nur im Anbieter-Analyse-Modus verfügbar.")
        else:
            st.info("Bitte wählen Sie einen Anbieter aus.")
    
    with tab5:
        st.markdown("### Performance nach Pickup-Zone")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            zone_limit = st.slider("Top-N Zonen", 5, 20, 10)
        
        if is_provider_mode and selected_provider:
            with st.spinner("Lade Zonen-Performance..."):
                my_zones = load_zone_performance(selected_provider, start_dt, end_dt, zone_ids, zone_limit)
                market_zones = load_zone_performance(None, start_dt, end_dt, zone_ids, zone_limit)
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                if len(my_zones) > 0:
                    st.markdown(f"**Top-Zonen: {selected_provider}**")
                    fig = plot_zone_performance(my_zones, f"Profitabelste Pickup-Zonen: {selected_provider}")
                    st.pyplot(fig, clear_figure=True)
                else:
                    st.info("Keine Zonendaten verfügbar.")
            
            with col_b:
                if len(market_zones) > 0:
                    st.markdown("**Top-Zonen: Gesamtmarkt**")
                    fig = plot_zone_performance(market_zones, "Profitabelste Pickup-Zonen (Gesamtmarkt)")
                    st.pyplot(fig, clear_figure=True)
                else:
                    st.info("Keine Markt-Zonendaten verfügbar.")
        else:
            with st.spinner("Lade Zonen-Performance..."):
                market_zones = load_zone_performance(None, start_dt, end_dt, zone_ids, zone_limit)
            
            if len(market_zones) > 0:
                fig = plot_zone_performance(market_zones, "Profitabelste Pickup-Zonen (Gesamtmarkt)")
                st.pyplot(fig, clear_figure=True)
            else:
                st.info("Keine Zonendaten verfügbar.")

    st.divider()

    # =============================================================
    # Data Tables
    # =============================================================
    st.subheader("Detaildaten")
    
    detail_tab1, detail_tab2, detail_tab3 = st.tabs([
        "Anbieter-Übersicht",
        "Marktstatistiken",
        "Dokumentation"
    ])
    
    with detail_tab1:
        st.markdown("### Anbieter-Benchmarks")
        if len(prov_df) > 0:
            display_df = prov_df.copy()
            display_df = display_df.round(2)
            
            total_trips = display_df['trips'].sum()
            display_df['market_share'] = (display_df['trips'] / total_trips * 100).round(1)
            
            st.dataframe(
                display_df.rename(columns={
                    "provider_name": "Anbieter",
                    "trips": "Fahrten",
                    "total_takehome": "Einnahmen gesamt ($)",
                    "avg_takehome_per_trip": "Ø pro Fahrt ($)",
                    "miles": "Meilen gesamt",
                    "minutes": "Minuten gesamt",
                    "avg_miles": "Ø Meilen",
                    "avg_minutes": "Ø Minuten",
                    "total_tips": "Trinkgeld gesamt ($)",
                    "avg_tips": "Ø Trinkgeld ($)",
                    "total_revenue": "Umsatz gesamt ($)",
                    "avg_revenue_per_trip": "Ø Umsatz/Fahrt ($)",
                    "market_share": "Marktanteil (%)"
                }),
                use_container_width=True,
                hide_index=True
            )
            
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="Daten als CSV herunterladen",
                data=csv,
                file_name=f"anbieter_benchmarks_{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Keine Anbieterdaten verfügbar.")
    
    with detail_tab2:
        st.markdown("### Markt-Gesamtstatistiken")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Gesamtfahrten (Markt)", f"{safe_int(overall_row['trips']):,}")
            st.metric("Gesamteinnahmen (Markt)", f"${safe_float(overall_row['total_takehome']):,.2f}")
        
        with col2:
            st.metric("Ø Einnahmen/Fahrt", f"${m_avg:.2f}")
            st.metric("Ø Trinkgeld/Fahrt", f"${m_avg_tips:.2f}")
        
        with col3:
            st.metric("Ø Meilen/Fahrt", f"{m_avg_miles:.2f}")
            st.metric("Ø Minuten/Fahrt", f"{m_avg_minutes:.1f}")
        
        st.divider()
        
        stats_data = {
            "Kennzahl": [
                "Gesamtfahrten",
                "Gesamteinnahmen ($)",
                "Ø Einnahmen pro Fahrt ($)",
                "Gesamttrinkgeld ($)",
                "Ø Trinkgeld pro Fahrt ($)",
                "Gesamtmeilen",
                "Ø Meilen pro Fahrt",
                "Gesamtminuten",
                "Ø Minuten pro Fahrt"
            ],
            "Wert": [
                f"{safe_int(overall_row['trips']):,}",
                f"${safe_float(overall_row['total_takehome']):,.2f}",
                f"${m_avg:.2f}",
                f"${safe_float(overall_row['total_tips']):,.2f}",
                f"${m_avg_tips:.2f}",
                f"{safe_float(overall_row['total_miles']):,.2f}",
                f"{m_avg_miles:.2f}",
                f"{safe_float(overall_row['total_minutes']):,.1f}",
                f"{m_avg_minutes:.1f}"
            ]
        }
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True, hide_index=True)
    
    with detail_tab3:
        st.markdown("""
        ### Dokumentation und Definitionen
        
        #### Kennzahlen-Definitionen
        
        **Einnahmen (Take-home)**  
        `driver_pay + tips` - Das Geld, das der Fahrer tatsächlich erhält.
        
        **Perzentil (nur im Persönlichen Modus)**  
        Ihr Ranking im Vergleich zu allen Anbietern. Ein 75. Perzentil bedeutet, dass Sie mehr verdienen 
        als 75% aller Anbieter im gewählten Zeitraum.
        
        **Stundensatz (geschätzt, nur im Persönlichen Modus)**  
        Berechnet als: `(Ø Einnahmen pro Fahrt) / (Ø Fahrtzeit in Stunden)`  
        Dies ist eine Schätzung basierend auf der reinen Fahrtzeit, ohne Wartezeiten zwischen Fahrten.
        
        **Effizienz ($/Meile)**  
        Einnahmen pro gefahrene Meile. Eine höhere Effizienz bedeutet mehr Einnahmen pro Strecke.
        
        **Marktanteil (nur im Anbieter-Modus)**  
        Prozentsatz der Fahrten eines Anbieters im Vergleich zum Gesamtmarkt.
        """)

    st.divider()
    st.caption(f"""
    Zeitraum: {start_dt.strftime('%d.%m.%Y')} bis {end_dt.strftime('%d.%m.%Y')} ({(end_dt - start_dt).days} Tage)
    """)


if __name__ == "__main__":
    render()