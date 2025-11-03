import streamlit as st
import pandas as pd
import plotly.express as px
import altair as alt
import geopandas as gpd
from data_utilities import database_connector


@st.cache_data(show_spinner="Lade Preisverteilung...", ttl=600)
def load_price_distribution_data(distance_range: tuple):
    """Lädt ein Sample von Rohdaten für den Boxplot."""
    engine = database_connector.get_sqlalchemy_engine()
    query = """
            SELECT p.provider_name,
                   t.base_passenger_fare
            FROM trips t
                     JOIN providers p ON t.provider_id = p.id
            WHERE t.trip_miles >= %(min_dist)s
              AND t.trip_miles <= %(max_dist)s
            ORDER BY RANDOM() LIMIT 50000;
            """
    params = {'min_dist': distance_range[0], 'max_dist': distance_range[1]}
    try:
        df = pd.read_sql_query(query, engine, params=params)
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der Preisverteilungsdaten: {e}")
        return pd.DataFrame(columns=['provider_name', 'base_passenger_fare'])


@st.cache_data(show_spinner="Lade Heatmapdaten...", ttl=600)
def load_heatmap_data():
    """
    Lädt die aggregierten Durchschnittspreise pro Stunde und Wochentag
    für die Heatmap.
    """
    engine = database_connector.get_sqlalchemy_engine()
    query = """
            SELECT p.provider_name,
                   EXTRACT(DOW FROM t.pickup_datetime)  AS dow,
                   EXTRACT(HOUR FROM t.pickup_datetime) AS hour_of_day,
                   AVG(t.base_passenger_fare)           AS avg_fare
            FROM trips t
                     JOIN
                 providers p ON t.provider_id = p.id
            GROUP BY p.provider_name, dow, hour_of_day
            """
    try:
        df = pd.read_sql_query(query, engine)
        day_map = {0: 'So', 1: 'Mo', 2: 'Di', 3: 'Mi', 4: 'Do', 5: 'Fr', 6: 'Sa'}
        day_order = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
        df['wochentag'] = df['dow'].map(day_map)
        return df, day_order
    except Exception as e:
        st.error(f"Fehler beim Laden der Heatmap-Daten: {e}")
        return pd.DataFrame(), []


@st.cache_data(show_spinner="Lade Preisdaten...", ttl=600)
def load_scatter_data(distance_range: tuple):
    """
    Lädt ein Sample von Fahrten, um Preis vs. Distanz/Zeit
    zu plotten. Filtert extreme Ausreißer UND den Distanzbereich.
    """
    engine = database_connector.get_sqlalchemy_engine()
    query = """
            SELECT p.provider_name,
                   t.base_passenger_fare,
                   t.trip_miles,
                   t.trip_time
            FROM trips t
                     JOIN
                 providers p ON t.provider_id = p.id
            WHERE t.trip_miles > 0.5
              AND t.trip_time > 60
              AND t.base_passenger_fare > 2.5
              AND t.base_passenger_fare < 500
              AND t.trip_miles < 100
              AND t.trip_miles >= %(min_dist)s
              AND t.trip_miles <= %(max_dist)s
            ORDER BY RANDOM() LIMIT
                25000;
            """
    params = {'min_dist': distance_range[0], 'max_dist': distance_range[1]}
    try:
        df = pd.read_sql_query(query, engine, params=params)
        if 'trip_time' in df.columns:
            df['trip_time'] = pd.to_numeric(df['trip_time'])
            df['trip_minutes'] = df['trip_time'] / 60
        else:
            df['trip_minutes'] = 0
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der Scatterdaten: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner="Lade KPIs...", ttl=600)
def load_dashboard_kpis():
    """
    Lädt NUR die wichtigsten KPIs für die oberste Zeile des Dashboards.
    """
    engine = database_connector.get_sqlalchemy_engine()
    query_market = """
                   SELECT p.provider_name, COUNT(*) AS total_trips
                   FROM trips t
                            JOIN providers p ON t.provider_id = p.id
                   GROUP BY p.provider_name
                   """
    df_market = pd.read_sql_query(query_market, engine)
    query_rates = """
                  SELECT p.provider_name,
                         AVG(t.base_passenger_fare / t.trip_miles) AS avg_price_per_mile
                  FROM trips t
                           JOIN providers p ON t.provider_id = p.id
                  WHERE t.trip_miles > 0.5
                    AND t.trip_time > 60
                    AND t.base_passenger_fare > 2.5
                    AND t.trip_miles < 100
                  GROUP BY p.provider_name
                  """
    df_rates = pd.read_sql_query(query_rates, engine)
    try:
        df_kpis = pd.merge(df_market, df_rates, on='provider_name', how='outer')
        kpis = df_kpis.set_index('provider_name').to_dict('index')
        return kpis
    except Exception:
        return {}


@st.cache_data(show_spinner="Lade Preiszusammensetzungsdaten...", ttl=600)
def load_fare_composition_data(hour_range: tuple):
    """
    Lädt die durchschnittliche Aufschlüsselung der Preiskomponenten
    (Basistarif, Maut, Gebühren) pro Anbieter, gefiltert nach Uhrzeit.
    """
    engine = database_connector.get_sqlalchemy_engine()
    where_sql = """
            WHERE EXTRACT(HOUR FROM t.pickup_datetime) BETWEEN %(min_hour)s AND %(max_hour)s
            """
    params = {'min_hour': hour_range[0], 'max_hour': hour_range[1]}
    query = f"""
            SELECT
                p.provider_name,
                AVG(COALESCE(t.base_passenger_fare, 0)) AS avg_base_fare,
                AVG(COALESCE(t.tolls, 0)) AS avg_tolls,
                AVG(COALESCE(t.bcf, 0)) AS avg_bcf,
                AVG(COALESCE(t.sales_tax, 0)) AS avg_sales_tax,
                AVG(COALESCE(t.congestion_surcharge, 0)) AS avg_congestion,
                AVG(COALESCE(t.airport_fee, 0)) AS avg_airport
            FROM
                trips t
            JOIN
                providers p ON t.provider_id = p.id
            {where_sql}
            GROUP BY
                p.provider_name
            """
    try:
        df_wide = pd.read_sql_query(query, engine, params=params)
        if df_wide.empty:
            st.warning(f"Keine Preiszusammensetzungsdaten für {hour_range[0]}-{hour_range[1]} Uhr gefunden.")
            return pd.DataFrame()
        cols_to_convert = [
            'avg_base_fare', 'avg_tolls', 'avg_bcf',
            'avg_sales_tax', 'avg_congestion', 'avg_airport'
        ]
        for col in cols_to_convert:
            df_wide[col] = pd.to_numeric(df_wide[col])
        df_wide['avg_fees'] = (
                df_wide['avg_bcf'] +
                df_wide['avg_sales_tax'] +
                df_wide['avg_congestion'] +
                df_wide['avg_airport']
        )
        df_wide = df_wide[['provider_name', 'avg_base_fare', 'avg_tolls', 'avg_fees']]
        df_wide = df_wide.set_index('provider_name')
        df_wide = df_wide.rename(columns={
            'avg_base_fare': '1. Basistarif',
            'avg_tolls': '2. Maut',
            'avg_fees': '3. Gebühren & Steuern'
        })
        df_long = df_wide.reset_index().melt(
            id_vars='provider_name',
            var_name='preiskomponente',
            value_name='avg_anteil'
        )
        return df_long
    except Exception as e:
        st.error(f"Fehler beim Laden der Preiszusammensetzungs-Daten: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner="Lade Karte...", ttl=3600)
def load_shapefile_shapes():
    """
    Lädt das Shapefile mit den Formen der NYC Taxi Zones.
    Liest 'taxi_zones.shp' (und die zugehörigen Dateien).
    Projiziert die Koordinaten in EPSG:4326 (Lat/Lon) für Plotly.
    """
    try:
        gdf = gpd.read_file("taxi_zones/taxi_zones.shp")
        gdf['LocationID'] = gdf['LocationID'].astype(int)
        gdf = gdf.to_crs(epsg=4326)
        return gdf[['LocationID', 'zone', 'borough', 'geometry']]

    except Exception as e:
        st.error(f"Fehler beim Laden der Shapefile 'taxi_zones.shp': {e}")
        st.error(
            "Stelle sicher, dass ALLE Shapefile-Dateien (.shp, .shx, .dbf, .prj) vorhanden sind und 'geopandas' installiert ist.")
        return None


@st.cache_data(show_spinner="Lade Kartendaten...", ttl=600)
def load_map_data():
    """
    Lädt die vorab aggregierten Daten für die Choropleth-Karte.
    Aggregiert nach Anbieter, Wochentag, Stunde und Abhol-Zone.
    """
    engine = database_connector.get_sqlalchemy_engine()

    query = """
            SELECT p.provider_name, \
                   t.pu_location_id, \
                   EXTRACT(DOW FROM t.pickup_datetime) AS dow, \
                   EXTRACT(HOUR FROM t.pickup_datetime) AS hour,
            AVG(t.base_passenger_fare / t.trip_miles) AS avg_rate
            FROM
                trips t
                JOIN
                providers p \
            ON t.provider_id = p.id
            WHERE
                t.trip_miles \
                > 0.5
            GROUP BY
                p.provider_name, t.pu_location_id, dow, hour; \
            """
    try:
        df = pd.read_sql_query(query, engine)
        df['dow'] = df['dow'].astype(int)
        df['hour'] = df['hour'].astype(int)
        df['pu_location_id'] = df['pu_location_id'].astype(int)
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der Karten-Aggregationsdaten: {e}")
        return pd.DataFrame()


def render():
    st.header("Userstory: Als Taxiunternehmen möchte ich einen Überblick über die Fahrpreisentwicklungen bekommen, "
              "um einen besseren Preis als meine Konkurrenz anbieten zu können.")

    tab_dashboard, tab_geo = st.tabs([
        "Dashboard-Übersicht",
        "Interaktive Karte"
    ])

    with tab_dashboard:
        st.subheader("KPIs")
        kpi_data = load_dashboard_kpis()
        if not kpi_data:
            st.warning("KPI-Daten konnten nicht geladen werden.")
        else:
            provider_names = sorted(kpi_data.keys())
            p1_name = provider_names[0] if len(provider_names) > 0 else "P1"
            p2_name = provider_names[1] if len(provider_names) > 1 else "P2"
            p1_kpis = kpi_data.get(p1_name, {})
            p2_kpis = kpi_data.get(p2_name, {})

            kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
            with kpi_col1:
                st.metric(f"Trips {p1_name}", f"{p1_kpis.get('total_trips', 0):,}")
            with kpi_col2:
                st.metric(f"Trips {p2_name}", f"{p2_kpis.get('total_trips', 0):,}")
            with kpi_col3:
                st.metric(f" Ø-Preis/Meile {p1_name}", f"${p1_kpis.get('avg_price_per_mile', 0):.2f}")
            with kpi_col4:
                p1_rate = p1_kpis.get('avg_price_per_mile', 0)
                p2_rate = p2_kpis.get('avg_price_per_mile', 0)
                delta = p2_rate - p1_rate if p1_rate > 0 else 0
                st.metric(f"Ø-Preis/Meile {p2_name}", f"${p2_rate:.2f}",
                          delta=f"${delta:.2f} vs {p1_name}", delta_color="inverse")

        st.markdown("---")
        st.subheader("Übersicht über die Preisstruktur")
        dist_range = st.slider(
            "Fahrtdistanzbereich wählen (Meilen):",
            min_value=0.0, max_value=50.0,
            value=(3.0, 10.0), step=0.5,
            key="dash_slider_dist_GLOBAL"
        )
        row2_col1, row2_col2 = st.columns(2)

        with row2_col1:
            st.markdown("#### Preisverteilung")
            price_df = load_price_distribution_data(dist_range)
            if price_df.empty:
                st.warning("Keine Daten für Boxplot gefunden.")
            else:
                provider_order = sorted(price_df['provider_name'].unique())
                fig_box = px.box(
                    price_df, x='provider_name', y='base_passenger_fare',
                    color='provider_name',
                    title=f"Zwischen {dist_range[0]}-{dist_range[1]} Meilen",
                    labels={'provider_name': 'Anbieter', 'base_passenger_fare': 'Preis (USD)'},
                    points='outliers',
                    category_orders={'provider_name': provider_order}
                )
                fig_box.update_layout(height=400, margin=dict(t=50, b=0))
                st.plotly_chart(fig_box, use_container_width=True)

        with row2_col2:
            st.markdown("#### Trendanalyse")
            scatter_df = load_scatter_data(dist_range)

            if scatter_df.empty or 'trip_minutes' not in scatter_df.columns:
                st.warning("Keine Daten für Scatter-Plot gefunden oder 'trip_minutes' fehlt.")
            else:
                plot_choice = st.selectbox(
                    "Analyse-Achse auswählen:",
                    options=["Preis vs. Distanz", "Preis vs. Zeit"],
                    key="dash_scatter_select"
                )

                trendline_dark_colors = ['red', 'darkred']

                def style_trendlines(fig_object):
                    scatter_traces, line_traces = [], []
                    legend_groups = []

                    for trace in fig_object.data:
                        if trace.legendgroup not in legend_groups:
                            legend_groups.append(trace.legendgroup)

                    color_map = {}
                    for i, group in enumerate(legend_groups):
                        color_map[group] = trendline_dark_colors[i] if i < len(trendline_dark_colors) else 'black'

                    for trace in fig_object.data:
                        if trace.mode == 'markers':
                            trace.name = trace.legendgroup
                            scatter_traces.append(trace)
                        elif trace.mode == 'lines':
                            trace.name = f"{trace.legendgroup} (Trend)"
                            trace.line.color = color_map.get(trace.legendgroup, 'black')
                            trace.line.width = 4
                            line_traces.append(trace)

                    fig_object.data = scatter_traces + line_traces
                    return fig_object

                if plot_choice == "Preis vs. Distanz":
                    fig_scatter_dist = px.scatter(
                        scatter_df, x='trip_miles', y='base_passenger_fare',
                        color='provider_name', trendline='ols',
                        title=f"Zwischen {dist_range[0]}-{dist_range[1]} Meilen",
                        labels={'trip_miles': 'Distanz (Meilen)', 'base_passenger_fare': 'Preis (USD)'}
                    )

                    fig_scatter_dist = style_trendlines(fig_scatter_dist)
                    fig_scatter_dist.update_layout(
                        legend_title="Anbieter",
                        height=400,
                        margin=dict(t=50, b=0)
                    )

                    st.plotly_chart(fig_scatter_dist, use_container_width=True)

                else:
                    fig_scatter_time = px.scatter(
                        scatter_df, x='trip_minutes', y='base_passenger_fare',
                        color='provider_name', trendline='ols',
                        title=f"Preis-Engine ({dist_range[0]}-{dist_range[1]} Mi)",
                        labels={'trip_minutes': 'Dauer (Minuten)', 'base_passenger_fare': 'Preis (USD)'}
                    )

                    fig_scatter_time = style_trendlines(fig_scatter_time)
                    fig_scatter_time.update_layout(
                        legend_title="Anbieter",
                        height=400,
                        margin=dict(t=50, b=0)
                    )

                    st.plotly_chart(fig_scatter_time, use_container_width=True)

        st.markdown("---")
        st.subheader("Preiszusammensetzung und Preishöhe über die Woche")
        hour_range = st.slider(
            "Uhrzeitbereich auswählen:",
            min_value=0, max_value=23,
            value=(7, 10), step=1,
            key="dash_hour_range_filter"
        )

        st.markdown("#### Analyse der Preiszusammensetzung")
        composition_df = load_fare_composition_data(hour_range)
        if composition_df.empty:
            st.warning(f"Keine Daten zur Preiszusammensetzung für {hour_range[0]}-{hour_range[1]} Uhr gefunden.")
        else:
            chart = alt.Chart(composition_df).mark_bar().encode(
                y=alt.Y('provider_name:N', title='Anbieter'),
                x=alt.X('avg_anteil:Q', title='Durchschnittlicher Gesamtpreis (USD)'),
                color=alt.Color('preiskomponente:N', title="Preiskomponente"),
                order=alt.Order('preiskomponente', sort='ascending'),
                tooltip=[
                    alt.Tooltip('provider_name', title='Anbieter'),
                    alt.Tooltip('preiskomponente', title='Komponente'),
                    alt.Tooltip('avg_anteil', title='Durchschnittl. Anteil ($)', format='$.2f')
                ]
            ).properties(
                title=f"Preiszusammensetzung ({hour_range[0]}:00 - {hour_range[1]}:00 Uhr)"
            ).interactive()
            st.altair_chart(chart, use_container_width=True)


        st.markdown("#### Heatmap der Preisentwicklung über Tageszeit und Woche")
        heatmap_df, day_order = load_heatmap_data()
        if heatmap_df.empty:
            st.warning("Keine Heatmap-Daten geladen.")
        else:
            heatmap_df_filtered = heatmap_df[
                heatmap_df['hour_of_day'].between(hour_range[0], hour_range[1])
            ]
            provider_list = sorted(heatmap_df_filtered['provider_name'].unique())
            if not provider_list:
                st.warning(f"Keine Anbieterdaten für {hour_range[0]}-{hour_range[1]} Uhr gefunden.")
            else:
                selected_provider = st.selectbox(
                    "Anbieter wählen:",
                    options=provider_list,
                    key="dash_select_heatmap"
                )
                plot_data = heatmap_df_filtered[
                    heatmap_df_filtered['provider_name'] == selected_provider
                    ]
                chart = alt.Chart(plot_data).mark_rect().encode(
                    x=alt.X('hour_of_day:O', title=f'Stunde ({hour_range[0]}-{hour_range[1]} Uhr)',
                            axis=alt.Axis(format='d', labelAngle=0)),
                    y=alt.Y('wochentag:O', title='Wochentag', sort=day_order),
                    color=alt.Color('avg_fare:Q', legend=alt.Legend(title="Ø-Preis"),
                                    scale=alt.Scale(range='heatmap')),
                    tooltip=[
                        alt.Tooltip('wochentag', title='Tag'),
                        alt.Tooltip('hour_of_day', title='Stunde'),
                        alt.Tooltip('avg_fare', title='Ø-Preis', format='$.2f')
                    ]
                ).properties(
                    title=f"Ø-Preise für {selected_provider} ({hour_range[0]}-{hour_range[1]} Uhr)",
                    height=300
                ).interactive()
                st.altair_chart(chart, use_container_width=True)

    with tab_geo:
        st.header("Geografische Preisanalyse")
        st.markdown("""
        Analyse der Preis-Hotspots. Die Karte zeigt den durchschnittlichen **Preis pro Meile**
        für jede Abholzone.
        """)

        map_data = load_map_data()
        shapefile = load_shapefile_shapes()

        if map_data.empty or shapefile is None:
            st.error("Konnte Karten-Daten oder Shapefile-Formen nicht laden. Analyse wird gestoppt.")
        else:
            filter_col, map_col = st.columns([0.3, 0.7])

            with filter_col:
                st.subheader("Kartenfilter")

                provider_list_map = sorted(map_data['provider_name'].unique())
                selected_provider_map = st.selectbox(
                    "Anbieter auswählen:",
                    options=provider_list_map,
                    key="map_provider_select"
                )

                day_map_map = {
                    'Montag': 1, 'Dienstag': 2, 'Mittwoch': 3, 'Donnerstag': 4,
                    'Freitag': 5, 'Samstag': 6, 'Sonntag': 0
                }
                selected_day_name_map = st.radio(
                    "Wochentag auswählen:",
                    options=day_map_map.keys(),
                    key="map_day_radio"
                )
                selected_day_dow_map = day_map_map[selected_day_name_map]

                selected_hour_map = st.slider(
                    "Stunde auswählen (1-Stunden-Fenster):",
                    min_value=0,
                    max_value=23,
                    value=9,
                    format="%d:00 Uhr",
                    key="map_hour_slider"
                )

            with map_col:
                try:
                    filtered_data = map_data[
                        (map_data['provider_name'] == selected_provider_map) &
                        (map_data['dow'] == selected_day_dow_map) &
                        (map_data['hour'] == selected_hour_map)
                        ]

                    merged_gdf = shapefile.merge(
                        filtered_data,
                        left_on='LocationID',
                        right_on='pu_location_id',
                        how='left'
                    )

                    merged_gdf['avg_rate'] = merged_gdf['avg_rate'].fillna(0)

                except Exception as e:
                    st.error(f"Fehler beim Filtern oder Mergen der Daten: {e}")
                    merged_gdf = shapefile.copy()
                    merged_gdf['avg_rate'] = 0

                if merged_gdf.empty:
                    st.warning("Konnte Geodaten nicht korrekt verarbeiten.")
                else:
                    max_rate = merged_gdf['avg_rate'].max()

                    fig_map = px.choropleth_mapbox(
                        merged_gdf,
                        geojson=merged_gdf.geometry,
                        locations=merged_gdf.index,
                        color="avg_rate",
                        color_continuous_scale="Reds",
                        range_color=(0, max_rate if max_rate > 0 else 1),
                        mapbox_style="carto-positron",
                        zoom=9.5,
                        center={"lat": 40.73, "lon": -73.94},
                        opacity=0.7,
                        labels={'avg_rate': 'Ø-Preis/Meile ($)'},
                        hover_data={
                            'zone': True,
                            'borough': True,
                            'avg_rate': ':.2f'
                        }
                    )

                    fig_map.update_layout(
                        margin={"r": 0, "t": 0, "l": 0, "b": 0},
                        height=600
                    )
                    st.plotly_chart(fig_map, use_container_width=True)