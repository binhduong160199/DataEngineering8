import psycopg2
import os
from sqlalchemy import create_engine

DB_HOST = os.getenv("PG_HOST", "db")
DB_NAME = "postgres"
DB_USER = "appuser"
DB_PASS = "group8"
DB_PORT = 5432

def get_psycopg2_connection():
    """Returns a psycopg2 database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def get_sqlalchemy_engine():
    """Returns a SQLAlchemy engine (useful for pandas.read_sql)."""
    return create_engine(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")