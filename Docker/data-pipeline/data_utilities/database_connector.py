import os
from sqlalchemy import create_engine

DB_HOST = os.getenv("PG_HOST", "db")
DB_NAME = "postgres"
DB_USER = "appuser"
DB_PASS = "group8"
DB_PORT = 5432


def get_sqlalchemy_engine():
    return create_engine(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")