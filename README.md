# DataEngineering8 Project

This project contains code, notebooks, and data for my Data Engineering batch processing and analysis tasks.
It uses Python, pandas, and JupyterLab in a virtual environment.

## Setup

1. Create and activate virtual environment:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install requirements:
   ```
   pip install -r requirements.txt
   ```
3. Launch Jupyter Lab:
   ```
   jupyter lab
   ```

## Streamlit Dashboard

Im Ordner `Docker/data-pipeline/dashboard_sections/` liegt der Abschnitt `section_tugba.py`. Dieses Modul baut die Angebots- und Nachfrageanalyse für Taxifahrer auf: Es lädt die Fahrten aus PostgreSQL, ermöglicht Datum- und Zonenfilter und zeigt Diagramme zu stündlichen Fahrgastzahlen sowie eine Heatmap der Nachfrage-Lücken. Starte den Streamlit-Container (`docker compose run --rm streamlit streamlit run streamlit_app.py`), um die Oberfläche aufzurufen.

