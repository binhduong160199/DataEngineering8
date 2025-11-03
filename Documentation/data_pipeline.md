# Datenpipeline – Architektur und Betrieb

Diese Dokumentation beschreibt die Datenpipeline in diesem Projekt: vom Laden der NYC-Fahrtdaten (Parquet) über Spark nach PostgreSQL bis zur Visualisierung im Streamlit‑Dashboard.

## Überblick
- Komponenten
  - Spark Master/Worker: liest Parquet, transformiert Daten und schreibt per JDBC nach PostgreSQL.
  - PostgreSQL: persistiert Dimensionen (`providers`, `taxi_zones`) und Faktentabelle (`trips`).
  - Streamlit: interaktives Dashboard, das direkt aus PostgreSQL liest.
- Orchestrierung: Docker Compose startet Spark, Postgres und das Dashboard in einem Netzwerk.
- Codepfade
  - Compose/Infra: `Docker/data-pipeline/docker-compose.yml`
  - Dashboard: `Docker/data-pipeline/streamlit_app.py`, `Docker/data-pipeline/dashboard_sections/*`
  - DB‑Connector: `Docker/data-pipeline/data_utilities/database_connector.py`
  - Spark Loader: `Docker/data-pipeline/load_nyc_dataset.py`
  - DB‑Schema: `Docker/data-pipeline/init/database_schema.sql`

## Datenfluss
1) Parquet‑Datei liegt lokal im Container‑Pfad `/app/...`.
2) Spark liest Parquet, bereitet Felder auf, erzeugt fehlende Dimensionen und filtert Ausreißer.
3) Spark schreibt die Spalten in die Tabelle `trips` per JDBC; bei Bedarf werden `providers` und `taxi_zones` ergänzt.
4) Streamlit fragt aus `trips`, `providers`, `taxi_zones` und berechnet KPIs/Charts.

## Lokales Starten (Docker Compose)
- Befehle ausführen im Ordner: `Docker/data-pipeline`
- Start:
  - `docker compose up --build`
  - Services:
    - Spark Master UI: `http://localhost:8080`
    - Spark Worker UI: `http://localhost:8081`
    - Streamlit: `http://localhost:8501`
    - PostgreSQL: `localhost:5432` (User `appuser`, Passwort `group8`, DB `postgres`)

## Daten laden (Spark → Postgres)
- Beispiel (mit Maven‑Paketauflösung):
  - `docker compose exec spark-master spark-submit --packages org.postgresql:postgresql:42.7.8 /app/load_nyc_dataset.py --data-file /app/path/to/data.parquet --pg-host db --pg-user appuser --pg-pass group8`
- Offline‑Variante (treiber JAR liegt im Repo):
  - `docker compose exec spark-master spark-submit --jars /app/postgresql-42.7.8.jar /app/load_nyc_dataset.py --data-file /app/path/to/data.parquet --pg-host db --pg-user appuser --pg-pass group8`
- Wichtige Argumente (`load_nyc_dataset.py`):
  - `--data-file`: Parquet‑Pfad im Container (unter `/app` gemountet)
  - `--pg-host`: innerhalb des Compose‑Netzes `db`, außerhalb `localhost`
  - `--pg-user`, `--pg-pass`, `--pg-db`, `--pg-port`
  - `--partitions` (Default 16), `--batchsize` (Default 1000)

### Annahmen zum Quell‑Schema (Parquet)
- Erwartete Felder (NYC HVFHS‑ähnlich):
  - `hvfhs_license_num`, `PULocationID`, `DOLocationID`
  - Zeitstempel: `request_datetime`, `on_scene_datetime`, `pickup_datetime`, `dropoff_datetime`
  - Metriken/Kosten: `trip_miles`, `trip_time`, `base_passenger_fare`, `tolls`, `bcf`, `sales_tax`, `congestion_surcharge`, `airport_fee`, `tips`, `driver_pay`, `cbd_congestion_fee`
  - Flags: `shared_request_flag`, `shared_match_flag`, `access_a_ride_flag`, `wav_request_flag`, `wav_match_flag` (Y/N)

### Transformationen im Loader
- Provider‑Mapping: hvfhs‑Code → `providers(id)`; unbekannte Codes werden als Name übernommen.
- Zonen: `PULocationID`/`DOLocationID` werden in `taxi_zones` angelegt, falls fehlend.
- Spaltenumbenennung: `PULocationID`→`pu_location_id`, `DOLocationID`→`do_location_id`.
- Flags: Y/N → BOOLEAN; andere Werte → NULL.
- Filter: entfernt Zeilen mit `trip_miles <= 0` oder `base_passenger_fare <= 0` oder `driver_pay <= 0`.
- Schreiben: JDBC nach Tabelle `trips` mit Batchsize/Partitionen.

## Datenmodell (PostgreSQL)
- Datei: `Docker/data-pipeline/init/database_schema.sql`
- Tabellen
  - `providers(id SERIAL PK, provider_name UNIQUE)`
  - `taxi_zones(id SERIAL PK, zone_name)`
  - `trips(id SERIAL PK, provider_id FK, pu_location_id FK, do_location_id FK, ... Kostenfelder, Flags)`
- Typen/Einheiten
  - Zeiten: `TIMESTAMP` (UTC gem. Quelle), Differenzen werden im Dashboard in Minuten berechnet.
  - Distanzen: `trip_miles` in Meilen.
  - Geldbeträge: `DECIMAL(10,2)`.

## Dashboard & DB‑Zugriff
- Einstieg: `Docker/data-pipeline/streamlit_app.py`
- Abschnitte: `Docker/data-pipeline/dashboard_sections/*` mit `render()`
- DB‑Zugriff: `Docker/data-pipeline/data_utilities/database_connector.py`
  - Verbindungsparameter:
    - Host über Env `PG_HOST` (Default: `db` im Compose‑Netz)
    - User: `appuser`, Passwort: `group8`, DB: `postgres`, Port: `5432`

## Validierung
- DB‑Tabellen prüfen:
  - `docker compose exec db psql -U appuser -d postgres -c "\\dt"`
- Sample‑Abfrage:
  - `docker compose exec db psql -U appuser -d postgres -c "SELECT COUNT(*) FROM trips;"`
- UI‑Smoke‑Test: `http://localhost:8501` öffnen und jede Registerkarte einmal laden.

## Häufige Probleme & Lösungen
- JDBC‑Treiber fehlt: Verwende die Offline‑Variante mit `--jars /app/postgresql-42.7.8.jar`.
- Keine Daten im Dashboard: Prüfe, ob `trips` befüllt ist und Zeitfilter nicht leer laufen.
- Shapefile‑Fehler in Geokarten: Stelle sicher, dass alle Dateien in `taxi_zones/` vorhanden sind und `geopandas` installiert ist (im Streamlit‑Image enthalten, siehe `requirements.txt`).
- Verbindung von lokalem Client zu Postgres: Host `localhost`, Port `5432`, User `appuser`, DB `postgres` (Passwort `group8`).

## Erweiterung: Neues Dataset laden
- Parquet muss die oben genannten Felder enthalten oder entsprechend vorprozessiert werden.
- Anpassungen im Loader (`load_nyc_dataset.py`) bei abweichenden Spaltennamen vornehmen.
- Bei neuen Providern: Mapping in `PROVIDER_NAMES` ergänzen (optional – reine Kosmetik).
- Nach Ladevorgang KPIs/Charts in den Sections prüfen; ggf. SQLs um neue Felder erweitern.

## Nützliche Pfade & Referenzen
- Compose: `Docker/data-pipeline/docker-compose.yml:1`
- Loader: `Docker/data-pipeline/load_nyc_dataset.py:1`
- Schema: `Docker/data-pipeline/init/database_schema.sql:1`
- DB‑Connector: `Docker/data-pipeline/data_utilities/database_connector.py:1`
- Dashboard: `Docker/data-pipeline/streamlit_app.py:1`

