# Data Engineering – NYC TLC Trip Record Data

- NYC TLC (Taxi & Limousine Commision) Dataset.
- Unterschiedliche Arten von Transport Daten - Bspw. Yellow Cab, Green Cab.
- Wir fokussieren uns auf High-Volume Trips. Also moderne Transportvermittler wie Uber & Lyft.

## Stakeholder

- **Taxiunternehmen**  
  _Marktanalyse, bessere Preismodelle_

- **Taxifahrer**  
  _Mehr Fahrten, bessere Arbeitsplanung, Vergleich der Taxiunternehmen für Ertragsoptimierung_

- **Stadtverkehrsplaner**  
  _Nutzung der Daten für städtische Planung, Verbesserung des Verkehrsflusses_

- **Fahrgäste**  
  _Preisvergleich, Transparenz_

- **Data Scientists**  
  _Mobilitätstrends, Umweltauswirkungen, sozioökonomische Muster_

---

## User Stories

### Taxiunternehmen
- Als Taxiunternehmen möchte ich einen Überblick über die Fahrpreisentwicklungen bekommen,  
  um einen besseren Preis als meine Konkurrenz anbieten zu können.
- Als Taxiunternehmen möchte ich Einblick auf den Mobilitätsbedarf erhalten,  
  um effektives Flottenmanagement betreiben zu können.
- Als Taxiunternehmen möchte ich Umwelt- und Ereigniseffekte (Saison, Events) simulieren,  
  um dynamische Preismodelle zu optimieren.

### Taxifahrer
- Als Taxifahrer möchte ich eine Darstellung über Angebot und Nachfrage aller Fahrten bekommen,  
  um mehr Aufträge zu erhalten und die Arbeitszeit effizienter (z. B. weniger Leerfahrten) nutzen zu können.
- Als Taxifahrer möchte ich meine Einnahmen mit dem Branchendurchschnitt vergleichen,  
  um meine berufliche Leistung besser bewerten zu können.
- Als Taxifahrer möchte ich wissen, welchen Lohn Taxiunternehmen zahlen,  
  um gegebenenfalls Arbeitgeber zu wechseln und mehr Einnahmen zu generieren.

### Stadtverkehrsplaner
- Als Stadtverkehrsplaner möchte ich die Verkehrsbelastung der Straßenzonen sehen,  
  damit Engpässe identifiziert werden können.
- Als Stadtverkehrsplaner möchte ich Zeitdaten nutzen,  
  um saisonale und tagesabhängige Verkehrsprobleme zu identifizieren.
- Als Stadtverkehrsplaner möchte ich die Fahrtbelastung der Stadtteile sehen,  
  um die Straßenzölle besser gestalten zu können.

### Fahrgäste
- Als Fahrgast möchte ich die Durchschnittspreise von Fahrten sehen,  
  um Anbieter vergleichen zu können.
- Als Fahrgast möchte ich einen Überblick über die durchschnittliche Warte- und Fahrzeit bekommen,  
  damit ich meine Fahrt besser planen kann.
- Als Fahrgast möchte ich einen Überblick über die durchschnittliche Wartezeit und den durchschnittlichen Preis von Rollstuhlfahrten bekommen, damit ich meine Fahrt besser planen kann.

### Data Scientists
- Als Data Scientist möchte ich qualitativ hochwertige Mobilitätsdaten zur Verfügung haben,  
  um Muster für nachhaltige Verkehrslösungen zu identifizieren.
- Als Data Scientist möchte ich die Daten nach Einkommensgebieten clustern,  
  um sozioökonomische Muster zu erkennen.

---

## Anforderungen

### Funktionale Anforderungen

- Zentrale Speicherung aller Daten in einer SQL-Datenbank (wie Fahrten, Fahrgäste, Zonen, Preise) sind gut strukturiert und tabellarisch. SQL-Datenbanken (z. B. PostgreSQL) bieten gute Performance, klare Abfragen, Integrität )
- Transformation, Standardisierung und Batchverarbeitung der Daten mit Spark
- Visuelle Darstellung der Daten durch Streamlit
- Filterung der Daten anhand unterschiedlicher D
imensionen (Zeit, Geld, Ort usw.)
- virtualisierte Infrastruktur mit Docker

### Nicht-funktionale Anforderungen

- Sicherstellung der langfristigen Wartbarkeit der Pipeline durch Dokumentation und Testbarkeit
- Gewährleistung der Datenqualität und Zuverlässigkeit durch Normalisierung
- Benutzerfreundlichkeit des Datendashboards in Streamlit
- Transparenz der Datenquellen