"""
db package for Migration Data Quality Scanner V2 persistence.
Built with Python's built-in sqlite3.
"""
from db.connection import get_connection, DEFAULT_DB_PATH
from db.repository import ScanRepository

__all__ = ["get_connection", "ScanRepository", "DEFAULT_DB_PATH"]
