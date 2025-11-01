"""Streamlit-Abschnitt für das Angebot-/Nachfrage-Dashboard von Tugba."""

from datetime import datetime, time
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from data_utilities import database_connector


@st.cache_data(show_spinner="Analysiere verfügbare Fahrtdaten...", ttl=600)
def load_trip_bounds() -> Optional[pd.Series]:
    """Ermittelt das früheste und späteste Abholdatum als Rahmen für das Datums-Widget."""
    query = """
        SELECT
            MIN(pickup_datetime) AS min_pickup,
            MAX(pickup_datetime) AS max_pickup
        FROM trips;
    """
    engine = database_connector.get_sqlalchemy_engine()
    df = pd.read_sql_query(query, engine, parse_dates=["min_pickup", "max_pickup"])
    if df.empty or pd.isna(df.loc[0, "min_pickup"]) or pd.isna(df.loc[0, "max_pickup"]):
        return None
    return df.loc[0]


@st.cache_data(show_spinner="Lade verfügbare Zonen...", ttl=600)
def load_zones() -> pd.DataFrame:
    """Lädt alle Taxi-Zonen, damit Fahrer einen Fokusbereich auswählen können."""
    query = """
        SELECT id, zone_name
        FROM taxi_zones
        ORDER BY zone_name;
    """
    engine = database_connector.get_sqlalchemy_engine()
    return pd.read_sql_query(query, engine)


@st.cache_data(show_spinner="Berechne Angebots- und Nachfrageprofil...", ttl=600)
def load_hourly_supply_demand(start_ts: datetime, end_ts: datetime, zone_id: Optional[int]) -> pd.DataFrame:
    """Berechnet pro Stunde die Nachfrage (Pickups) und das Angebot (Dropoffs)."""
    query = """
        WITH pickup_data AS (
            SELECT pickup_datetime, pu_location_id
            FROM trips
            WHERE pickup_datetime BETWEEN %(start_ts)s AND %(end_ts)s
        ),
        dropoff_data AS (
            SELECT dropoff_datetime, do_location_id
            FROM trips
            WHERE dropoff_datetime BETWEEN %(start_ts)s AND %(end_ts)s
        ),
        demand AS (
            SELECT
                EXTRACT(HOUR FROM pickup_datetime)::INT AS hour_of_day,
                COUNT(*) AS demand_count
            FROM pickup_data
            WHERE %(zone_id)s IS NULL OR pu_location_id = %(zone_id)s
            GROUP BY hour_of_day
        ),
        supply AS (
            SELECT
                EXTRACT(HOUR FROM dropoff_datetime)::INT AS hour_of_day,
                COUNT(*) AS supply_count
            FROM dropoff_data
            WHERE %(zone_id)s IS NULL OR do_location_id = %(zone_id)s
            GROUP BY hour_of_day
        )
        SELECT
            hours.hour_of_day,
            COALESCE(demand.demand_count, 0) AS demand_count,
            COALESCE(supply.supply_count, 0) AS supply_count,
            COALESCE(demand.demand_count, 0) - COALESCE(supply.supply_count, 0) AS gap
        FROM generate_series(0, 23) AS hours(hour_of_day)
        LEFT JOIN demand ON demand.hour_of_day = hours.hour_of_day
        LEFT JOIN supply ON supply.hour_of_day = hours.hour_of_day
        ORDER BY hours.hour_of_day;
    """
    engine = database_connector.get_sqlalchemy_engine()
    params = {"start_ts": start_ts, "end_ts": end_ts, "zone_id": zone_id}
    df = pd.read_sql_query(query, engine, params=params)
    return df


@st.cache_data(show_spinner="Erstelle Wochen-Heatmap...", ttl=600)
def load_weekly_gap(start_ts: datetime, end_ts: datetime, zone_id: Optional[int]) -> pd.DataFrame:
    """Berechnet die Nachfrage-Lücke für jede Kombination aus Wochentag und Stunde."""
    query = """
        WITH pickup_data AS (
            SELECT pickup_datetime, pu_location_id
            FROM trips
            WHERE pickup_datetime BETWEEN %(start_ts)s AND %(end_ts)s
        ),
        dropoff_data AS (
            SELECT dropoff_datetime, do_location_id
            FROM trips
            WHERE dropoff_datetime BETWEEN %(start_ts)s AND %(end_ts)s
        ),
        demand AS (
            SELECT
                EXTRACT(DOW FROM pickup_datetime)::INT AS dow,
                TO_CHAR(pickup_datetime, 'FMDay') AS weekday,
                EXTRACT(HOUR FROM pickup_datetime)::INT AS hour_of_day,
                COUNT(*) AS demand_count
            FROM pickup_data
            WHERE %(zone_id)s IS NULL OR pu_location_id = %(zone_id)s
            GROUP BY dow, weekday, hour_of_day
        ),
        supply AS (
            SELECT
                EXTRACT(DOW FROM dropoff_datetime)::INT AS dow,
                TO_CHAR(dropoff_datetime, 'FMDay') AS weekday,
                EXTRACT(HOUR FROM dropoff_datetime)::INT AS hour_of_day,
                COUNT(*) AS supply_count
            FROM dropoff_data
            WHERE %(zone_id)s IS NULL OR do_location_id = %(zone_id)s
            GROUP BY dow, weekday, hour_of_day
        )
        SELECT
            COALESCE(demand.dow, supply.dow)::INT AS dow,
            COALESCE(demand.weekday, supply.weekday) AS weekday,
            COALESCE(demand.hour_of_day, supply.hour_of_day)::INT AS hour_of_day,
            COALESCE(demand.demand_count, 0) AS demand_count,
            COALESCE(supply.supply_count, 0) AS supply_count,
            COALESCE(demand.demand_count, 0) - COALESCE(supply.supply_count, 0) AS gap
        FROM demand
        FULL OUTER JOIN supply
            ON demand.dow = supply.dow AND demand.hour_of_day = supply.hour_of_day
        ORDER BY dow, hour_of_day;
    """
    engine = database_connector.get_sqlalchemy_engine()
    params = {"start_ts": start_ts, "end_ts": end_ts, "zone_id": zone_id}
    return pd.read_sql_query(query, engine, params=params)


@st.cache_data(show_spinner="Ermittle Zonen mit Engpässen...", ttl=600)
def load_zone_balance(start_ts: datetime, end_ts: datetime) -> pd.DataFrame:
    """Zeigt Zonen mit besonders hoher oder niedriger Auslastung, um Fahrten zu priorisieren."""
    query = """
        WITH pickup_counts AS (
            SELECT pu_location_id AS zone_id, COUNT(*) AS demand_count
            FROM trips
            WHERE pickup_datetime BETWEEN %(start_ts)s AND %(end_ts)s
            GROUP BY pu_location_id
        ),
        dropoff_counts AS (
            SELECT do_location_id AS zone_id, COUNT(*) AS supply_count
            FROM trips
            WHERE dropoff_datetime BETWEEN %(start_ts)s AND %(end_ts)s
            GROUP BY do_location_id
        )
        SELECT
            z.id AS zone_id,
            z.zone_name,
            COALESCE(p.demand_count, 0) AS demand_count,
            COALESCE(d.supply_count, 0) AS supply_count,
            COALESCE(p.demand_count, 0) - COALESCE(d.supply_count, 0) AS gap
        FROM taxi_zones z
        LEFT JOIN pickup_counts p ON z.id = p.zone_id
        LEFT JOIN dropoff_counts d ON z.id = d.zone_id
        WHERE COALESCE(p.demand_count, 0) > 0 OR COALESCE(d.supply_count, 0) > 0
        ORDER BY gap DESC, zone_name
        LIMIT 50;
    """
    engine = database_connector.get_sqlalchemy_engine()
    params = {"start_ts": start_ts, "end_ts": end_ts}
    return pd.read_sql_query(query, engine, params=params)


def render():
    """Hauptfunktion, die den kompletten Abschnitt mit Filtern und Diagrammen aufbaut."""
    st.header("Angebot & Nachfrage im Blick")
    st.markdown(
        "Diese Analyse unterstützt dich dabei, Leerfahrten zu minimieren: Wir vergleichen abgeholte Fahrgäste "
        "(Nachfrage) mit ankommenden Fahrern (Angebot) und zeigen, wann und wo sich Einsätze besonders lohnen."
    )

    bounds = load_trip_bounds()
    if bounds is None:
        st.info("Keine Fahrtdaten gefunden. Lade Daten, um Angebots- und Nachfrageprofile zu erstellen.")
        return

    min_date = bounds["min_pickup"].date()
    max_date = bounds["max_pickup"].date()

    # Das Datumsintervall limitiert alle Auswertungen auf den für den Fahrer relevanten Zeitraum.
    date_range = st.date_input(
        "Zeitraum auswählen",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if not isinstance(date_range, tuple) or len(date_range) != 2:
        st.warning("Bitte Start- und Enddatum wählen, um die Auswertung zu laden.")
        return

    start_date, end_date = date_range
    if start_date > end_date:
        st.error("Das Startdatum muss vor dem Enddatum liegen.")
        return

    # Zonenliste wird in einer Selectbox angezeigt, damit Fahrer ihr Einsatzgebiet eingrenzen können.
    zones_df = load_zones()
    zone_options = ["Alle Gebiete"]
    zone_lookup = {"Alle Gebiete": None}
    for _, row in zones_df.iterrows():
        label = f"{row['zone_name']} (ID {int(row['id'])})"
        zone_options.append(label)
        zone_lookup[label] = int(row["id"])

    selected_zone_label = st.selectbox("Zone (optional)", zone_options, index=0)
    zone_id = zone_lookup[selected_zone_label]

    start_ts = datetime.combine(start_date, time.min)
    end_ts = datetime.combine(end_date, time.max)

    # Stündliche Aggregation bildet die Basis für die Linie-gegen-Linie-Analyse.
    hourly_df = load_hourly_supply_demand(start_ts, end_ts, zone_id)
    if hourly_df.empty:
        st.info("Keine Fahrten im gewählten Zeitraum/Zonenfilter gefunden.")
        return

    weekly_df = load_weekly_gap(start_ts, end_ts, zone_id)

    total_demand = int(hourly_df["demand_count"].sum())
    total_supply = int(hourly_df["supply_count"].sum())
    net_gap = total_demand - total_supply
    coverage = (total_supply / total_demand * 100) if total_demand > 0 else None

    col1, col2, col3 = st.columns(3)
    col1.metric("Nachfrage (Pickups)", f"{total_demand:,}".replace(",", "."))
    col2.metric("Angebot (Dropoffs)", f"{total_supply:,}".replace(",", "."))
    col3.metric(
        "Netto-Lücke",
        f"{net_gap:+,}".replace(",", "."),
        f"{coverage:.1f} %" if coverage is not None else None,
    )

    # Linienplot visualisiert Nachfrage vs. Angebot über den Tag hinweg.
    st.subheader("Stündliche Angebots- und Nachfragekurve")
    fig_hourly, ax_hourly = plt.subplots(figsize=(10, 4))
    ax_hourly.plot(
        hourly_df["hour_of_day"],
        hourly_df["demand_count"],
        marker="o",
        label="Nachfrage (Pickups)",
    )
    ax_hourly.plot(
        hourly_df["hour_of_day"],
        hourly_df["supply_count"],
        marker="s",
        label="Angebot (Dropoffs)",
    )
    ax_hourly.set_xticks(range(0, 24, 2))
    ax_hourly.set_xlabel("Stunde des Tages")
    ax_hourly.set_ylabel("Anzahl Fahrten")
    ax_hourly.set_title("Wann steigt die Nachfrage?")
    ax_hourly.grid(True, alpha=0.3)
    ax_hourly.legend()
    st.pyplot(fig_hourly)

    st.subheader("Heatmap: Nachfrage-Lücke nach Wochentag & Stunde")
    if weekly_df.empty:
        st.write("Für die Heatmap liegen im ausgewählten Zeitraum keine Daten vor.")
    else:
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekly_df["weekday"] = pd.Categorical(weekly_df["weekday"], categories=weekday_order, ordered=True)
        weekly_df = weekly_df.sort_values(["weekday", "hour_of_day"])
        pivot_gap = weekly_df.pivot_table(
            index="weekday",
            columns="hour_of_day",
            values="gap",
            aggfunc="mean",
        )

        fig_heatmap, ax_heatmap = plt.subplots(figsize=(12, 5))
        sns.heatmap(
            pivot_gap,
            cmap="coolwarm",
            center=0,
            ax=ax_heatmap,
            cbar_kws={"label": "Nachfrage minus Angebot"},
        )
        ax_heatmap.set_xlabel("Stunde des Tages")
        ax_heatmap.set_ylabel("Wochentag")
        ax_heatmap.set_title("Positive Werte = Nachfrageüberschuss, Negative = mehr Fahrer vor Ort")
        st.pyplot(fig_heatmap)

    if zone_id is None:
        # Nur wenn alle Gebiete betrachtet werden, zeigen wir eine Rangliste der Zonen.
        zone_balance_df = load_zone_balance(start_ts, end_ts)
        if not zone_balance_df.empty:
            zone_balance_df = zone_balance_df.assign(
                demand_count=zone_balance_df["demand_count"].astype(int),
                supply_count=zone_balance_df["supply_count"].astype(int),
                gap=zone_balance_df["gap"].astype(int),
            )

            high_demand = zone_balance_df[zone_balance_df["gap"] > 0].nlargest(5, "gap")
            oversupply = zone_balance_df[zone_balance_df["gap"] < 0].nsmallest(5, "gap")

            st.subheader("Zonen mit dem größten Nachfrageüberschuss")
            if high_demand.empty:
                st.write("Keine Zonen mit Nachfrageüberschuss im ausgewählten Zeitraum.")
            else:
                st.dataframe(
                    high_demand.rename(
                        columns={
                            "zone_name": "Zone",
                            "demand_count": "Nachfrage",
                            "supply_count": "Angebot",
                            "gap": "Lücke",
                        }
                    )[["Zone", "Nachfrage", "Angebot", "Lücke"]],
                    use_container_width=True,
                )

            st.subheader("Zonen mit möglichem Fahrer-Überschuss")
            if oversupply.empty:
                st.write("Keine Zonen mit Fahrerüberschuss im ausgewählten Zeitraum.")
            else:
                st.dataframe(
                    oversupply.rename(
                        columns={
                            "zone_name": "Zone",
                            "demand_count": "Nachfrage",
                            "supply_count": "Angebot",
                            "gap": "Lücke",
                        }
                    )[["Zone", "Nachfrage", "Angebot", "Lücke"]],
                    use_container_width=True,
                )

    st.markdown(
        "Hinweis: Nachfrage bezieht sich auf abgeholte Fahrgäste. Angebot steht für Fahrer, die nach einer Fahrt in "
        "einem Gebiet ankommen und kurzfristig wieder verfügbar sind. Nutze Zeiten mit positiver Lücke, um "
        "Leerfahrten zu reduzieren und gezielt in Hotspots präsent zu sein."
    )
