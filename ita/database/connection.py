
from contextlib import contextmanager

import pyodbc
from langgraph.checkpoint.mssql import MSSQLSaver


DB_URI = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=.\\SQLEXPRESS;"
    "DATABASE=ITA;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


@contextmanager
def db_connection():
    """Open a SQL Server connection and manage its transaction."""
    conn = pyodbc.connect(DB_URI)

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_checkpointer():
    """Return the LangGraph SQL Server checkpointer context manager."""
    return MSSQLSaver.from_conn_string(DB_URI)