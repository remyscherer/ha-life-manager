import os
from datetime import date, datetime

from sqlalchemy import create_engine, event

DB_PATH = os.environ.get("LIFE_MANAGER_DB_PATH", "/data/life_manager.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)

def _as_date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None

@event.listens_for(engine, "connect")
def _sqlite_compat(dbapi_connection, _):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")
    dbapi_connection.execute("PRAGMA journal_mode=WAL")
    dbapi_connection.execute("PRAGMA synchronous=NORMAL")

    dbapi_connection.create_function(
        "NOW", 0, lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    dbapi_connection.create_function("CURDATE", 0, lambda: date.today().isoformat())

    def datediff(a, b):
        da, db = _as_date(a), _as_date(b)
        return (da - db).days if da and db else None

    def yearweek(value, mode=1):
        d = _as_date(value)
        if not d:
            return None
        iso = d.isocalendar()
        return iso.year * 100 + iso.week

    dbapi_connection.create_function("DATEDIFF", 2, datediff)
    dbapi_connection.create_function("YEARWEEK", 1, lambda value: yearweek(value, 1))
    dbapi_connection.create_function("YEARWEEK", 2, yearweek)
