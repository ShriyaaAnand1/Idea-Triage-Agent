from langgraph.checkpoint.mssql import MSSQLSaver


DB_URI = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=.\\SQLEXPRESS;"
    "DATABASE=ITA;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def get_checkpointer():
    return MSSQLSaver.from_conn_string(DB_URI)