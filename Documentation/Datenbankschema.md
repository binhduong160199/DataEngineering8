# Datenbankschema: Aufbau und Dokumentation

## Überblick

Für das Projekt **„NYC Taxi Data Analysis“** wurde eine **relationale Datenbank** in **PostgreSQL** entwickelt.  
Sie bildet die wichtigsten Entitäten und Beziehungen zwischen **Anbietern**, **Stadtzonen** und **Fahrten** ab.  
Das Schema (`database_schema.sql`) besteht aus drei Haupttabellen:

- `providers` (Anbieter)
- `taxi_zones` (Stadtzonen)
- `trips` (Fahrten)

Diese Tabellen sind logisch miteinander verknüpft und ermöglichen umfassende Auswertungen zu Fahrverhalten, Kostenstruktur und regionalen Trends.

---

## Tabellenstruktur

### 1. Tabelle: `providers`

| Spalte | Datentyp | Beschreibung |
|---------|-----------|--------------|
| `id` | SERIAL PRIMARY KEY | Eindeutige ID für jeden Anbieter |
| `provider_name` | VARCHAR(32) UNIQUE NOT NULL | Name des Fahrdienstanbieters (z. B. Uber, Lyft) |

**Beschreibung:**  
Die Tabelle `providers` speichert alle Anbieter von Fahrdiensten. Jeder Anbieter besitzt eine eindeutige ID, die automatisch generiert wird.  
Der Name ist eindeutig und darf nicht mehrfach vorkommen (UNIQUE).

---

### 2. Tabelle: `taxi_zones`

| Spalte | Datentyp | Beschreibung |
|---------|-----------|--------------|
| `id` | SERIAL PRIMARY KEY | Eindeutiger Identifikator der Zone |
| `zone_name` | VARCHAR(64) NOT NULL | Name bzw. Bezeichnung der Stadtzone (z. B. Manhattan, Brooklyn) |

**Beschreibung:**  
Die Tabelle `taxi_zones` enthält alle Stadtgebiete, in denen Taxis starten oder enden können.  
Sie wird über Fremdschlüssel mit der Tabelle `trips` verknüpft.

---

### 3. Tabelle: `trips`

| Spalte | Datentyp | Beschreibung |
|---------|-----------|--------------|
| `id` | SERIAL PRIMARY KEY | Eindeutige ID jeder Fahrt |
| `provider_id` | INTEGER REFERENCES providers(id) | Verweis auf den Fahrdienstanbieter |
| `pu_location_id` | INTEGER REFERENCES taxi_zones(id) | Startzone (Pickup Location) |
| `do_location_id` | INTEGER REFERENCES taxi_zones(id) | Zielzone (Dropoff Location) |
| `request_datetime` | TIMESTAMP NOT NULL | Zeitpunkt der Fahrtanfrage |
| `on_scene_datetime` | TIMESTAMP | Zeitpunkt, an dem das Taxi am Abholort eintraf |
| `pickup_datetime` | TIMESTAMP NOT NULL | Startzeit der Fahrt |
| `dropoff_datetime` | TIMESTAMP NOT NULL | Ende der Fahrt |
| `trip_miles` | NUMERIC(12,3) | Fahrstrecke in Meilen |
| `trip_time` | NUMERIC(12,3) | Fahrtdauer in Minuten |
| `base_passenger_fare` | DECIMAL(10,2) | Grundpreis der Fahrt |
| `tolls` | DECIMAL(10,2) | Mautgebühren |
| `bcf` | DECIMAL(10,2) | Black Car Fund Gebühr |
| `sales_tax` | DECIMAL(10,2) | Verkaufssteuer |
| `congestion_surcharge` | DECIMAL(10,2) | Stauzuschlag |
| `airport_fee` | DECIMAL(10,2) | Flughafenzuschlag |
| `tips` | DECIMAL(10,2) | Trinkgeld |
| `driver_pay` | DECIMAL(10,2) | Auszahlung an den Fahrer |
| `cbd_congestion_fee` | DECIMAL(10,2) | Zusatzgebühr für das Central Business District |
| `shared_request_flag` | BOOLEAN | Wahr/Falsch – Fahrt wurde als geteilte Fahrt angefragt |
| `shared_match_flag` | BOOLEAN | Wahr/Falsch – Fahrt wurde tatsächlich geteilt |
| `access_a_ride_flag` | BOOLEAN | Wahr/Falsch – Behindertentransport (Access-A-Ride) |
| `wav_request_flag` | BOOLEAN | Wahr/Falsch – Rollstuhlgerechtes Fahrzeug angefragt |
| `wav_match_flag` | BOOLEAN | Wahr/Falsch – Rollstuhlgerechtes Fahrzeug zugeteilt |

**Beschreibung:**  
Die Tabelle `trips` enthält sämtliche Fahrten mit zeitlichen Angaben, Preisen, Gebühren und zusätzlichen Kennzeichen.  
Sie verknüpft Anbieter (`providers`) und Stadtzonen (`taxi_zones`) über Fremdschlüssel und bildet die zentrale Datengrundlage für alle Analysen.  
So können Auswertungen zu Preisstrukturen, Fahrverhalten, Fahrdauer und Servicearten durchgeführt werden.

---

## Umsetzung mit Docker Compose

Die Datenbank wird als Service `db` in einem **PostgreSQL-Container** betrieben.  
Beim **ersten Start** des Containers werden automatisch alle SQL-Skripte aus dem Verzeichnis `./init/` (z. B. `database_schema.sql`) ausgeführt.  
Dies geschieht, weil der Ordner als `docker-entrypoint-initdb.d` gemountet ist – ein Standardmechanismus von PostgreSQL-Dockerimages.

**Wichtige Hinweise:**
- Die SQL-Skripte werden nur beim **ersten Start** ausgeführt, wenn das Datenverzeichnis leer ist (neues Volume).  
- Die Ausführung erfolgt gegen die in `POSTGRES_DB` definierte Datenbank (aktuell: `postgres`).  
- Wenn eine eigene Datenbank gewünscht ist, z. B. `nyc_taxi`, kann dies durch Anpassung der Umgebungsvariablen erfolgen:
  ```yaml
  - POSTGRES_DB=nyc_taxi