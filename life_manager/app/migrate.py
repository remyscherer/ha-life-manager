import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

MYSQL_HOST = os.environ["MYSQL_HOST"]
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]

DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
)

MIGRATION_DIR = Path("/app/migrations")

def main():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_name VARCHAR(255) PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))

    migrations = sorted(MIGRATION_DIR.glob("*.sql"))
    print(f"[migrations] Found {len(migrations)} migration file(s).", flush=True)

    for migration in migrations:
        name = migration.name

        with engine.connect() as connection:
            applied = connection.execute(
                text("SELECT migration_name FROM schema_migrations WHERE migration_name=:name"),
                {"name": name},
            ).first()

        if applied:
            print(f"[migrations] Skip {name}", flush=True)
            continue

        sql = migration.read_text(encoding="utf-8")
        statements = [
            st.strip()
            for st in sql.split(";")
            if st.strip()
            and not st.strip().upper().startswith("USE ")
            and not st.strip().upper().startswith("SELECT ")
        ]

        print(f"[migrations] Apply {name}", flush=True)
        try:
            with engine.begin() as connection:
                for statement in statements:
                    connection.exec_driver_sql(statement)
                connection.execute(
                    text("INSERT INTO schema_migrations (migration_name) VALUES (:name)"),
                    {"name": name},
                )
        except Exception as exc:
            print(f"[migrations] ERROR in {name}: {exc}", file=sys.stderr, flush=True)
            raise

        print(f"[migrations] Done {name}", flush=True)

    print("[migrations] Database is up to date.", flush=True)

if __name__ == "__main__":
    main()
