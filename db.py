import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def connection_settings(include_database=True):
    settings = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }
    if include_database:
        settings["database"] = os.getenv("DB_NAME", "Bookstore")
    return settings


def get_connection(include_database=True):
    """Return a new MySQL connection using credentials from .env."""
    settings = connection_settings(include_database)
    if not settings["user"]:
        raise RuntimeError("DB_USER is missing. Copy .env.example to .env and fill it in.")
    return mysql.connector.connect(**settings)
