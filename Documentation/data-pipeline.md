# Data Pipeline

Comprehensive guide to run, load, and validate the NYC trips data pipeline and dashboard in this repository.

## Overview
- Technologies: Docker, Spark 3.5, PostgreSQL 16, Streamlit, Python 3.10+
- Workflow: Spark reads Parquet → transforms → writes to Postgres → Streamlit reads from Postgres and renders dashboards.

## Architecture
- Streamlit dashboard (`streamlit_app.py`) with multiple sections under `dashboard_sections/` (each exposes a `render()` function).
- DB utilities in `data_utilities/` use `PG_HOST` to resolve the database host.
- Postgres schema bootstrapped from `init/database_schema.sql`.
- Spark loader `load_nyc_dataset.py` ingests Parquet and writes to `trips`, creating `providers` and `taxi_zones` as needed.

## Directory Layout
- `Docker/data-pipeline/`
  - `streamlit_app.py` – Dashboard entry point.
  - `dashboard_sections/section_*.py` – Dashboard tabs; each defines `render()`.
  - `data_utilities/database_connector.py` – Postgres connectors (psycopg2/SQLAlchemy), reads `PG_HOST` (default `db`).
  - `init/database_schema.sql` – Postgres DDL executed on first DB start.
  - `load_nyc_dataset.py` – Spark → Postgres loader.
  - `docker-compose.yml`, `Dockerfile.streamlit` – Container orchestration/build.

## Prerequisites
- Docker Desktop (or Docker Engine) with Compose v2.
- For notebooks: Python 3.10+ and Jupyter (see local dev below).

## Quick Start (Docker stack)
1. Start services (Spark, Postgres, Streamlit):
   ```bash
   cd Docker/data-pipeline
   docker compose up --build
   ```
2. Open dashboard: http://localhost:8501
3. Database is exposed locally at `localhost:5432` (user `appuser`, password `group8`, db `postgres`).

## Loading Data with Spark
Run the loader from inside the Spark master container. Use service name `db` for the in-network Postgres host.
```bash
cd Docker/data-pipeline
# Example with an in-repo parquet path under /app
docker compose exec spark-master \
  spark-submit --packages org.postgresql:postgresql:42.7.8 \
  /app/load_nyc_dataset.py \
  --data-file /app/path/to/data.parquet \
  --pg-host db \
  --pg-user appuser \
  --pg-pass group8
```
Notes:
- The compose mounts the repo at `/app` in containers.
- The Postgres JDBC driver is available via `--packages` and also included as `postgresql-42.7.8.jar` if needed.
- Defaults: `--pg-port 5432`, `--pg-db postgres`, `--partitions 16`, `--batchsize 1000`.

## Validating the Load
- List tables after schema/init or a load:
  ```bash
  docker compose exec db psql -U appuser -d postgres -c "\\dt"
  ```
- Expect at least: `providers`, `taxi_zones`, `trips`.

## Local Notebook Development
- Create a venv and run Jupyter:
  ```bash
  python -m venv .venv
  # Windows PowerShell
  .venv\\Scripts\\Activate.ps1
  # macOS/Linux
  source .venv/bin/activate

  pip install -r requirements.txt
  jupyter lab
  ```
- Notebooks live at repo root and under `UserStories/`.

## Configuration
- Streamlit DB connector (`data_utilities/database_connector.py`) uses env var `PG_HOST`.
  - In Docker network, `PG_HOST=db` (default) connects to the Postgres service.
  - If running dashboard locally without Docker Compose, set `PG_HOST=localhost`.
  - Example override when running a container:
    ```bash
    docker compose run -e PG_HOST=db streamlit
    ```
- Do not commit real credentials. Use environment variables for overrides when needed.

## Troubleshooting
- Spark cannot reach Postgres: confirm `--pg-host db`, DB is healthy, and network `spark-net` is up.
- Schema not present or changed: Compose runs `init/database_schema.sql` on first DB start. If you change the schema and need a clean seed, stop containers and remove the Postgres volume (destructive):
  ```bash
  docker compose down -v
  docker compose up --build
  ```
- Dashboard errors: verify each `dashboard_sections/*` tab renders with a small sample dataset and DB connectivity.

## Contributing & Conventions
- Python 3.10+, PEP 8, 4-space indentation; `snake_case` for functions/modules, `CapWords` for classes.
- Keep SQL readable: uppercase keywords, multiline strings.
- Group related changes in commits; avoid mixing formatting-only changes with logic.

