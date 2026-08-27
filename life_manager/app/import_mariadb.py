import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from database import engine as sqlite_engine

MYSQL_HOST = os.environ.get("MYSQL_HOST", "")
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "life_manager")
MYSQL_USER = os.environ.get("MYSQL_USER", "")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MARKER = Path("/data/.mariadb_import_done")

TABLE_ORDER = [
    "categories",
    "rewards",
    "quests",
    "quest_schedules",
    "quest_completions",
    "xp_ledger",
    "coin_ledger",
    "daily_summary",
    "reward_purchases",
    "savings_goals",
    "achievements",
    "achievement_unlocks",
    "planner_history",
    "weekly_goals",
    "quest_occurrences",
    "life_manager_meta",
]

def row_count(conn, table, mysql=False):
    quoted = f"`{table}`" if mysql else f'"{table}"'
    return int(conn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one())

def main():
    if MARKER.exists():
        print("[import] Already completed; skip.", flush=True)
        return 0

    if not MYSQL_HOST or not MYSQL_USER:
        print("[import] MariaDB is not configured; skip.", flush=True)
        return 0

    mysql_url = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    )

    try:
        mysql_engine = create_engine(mysql_url, pool_pre_ping=True)
        with mysql_engine.connect() as src:
            src.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"[import] MariaDB not reachable; fresh SQLite will be used: {exc}", flush=True)
        return 0

    src_inspector = inspect(mysql_engine)
    dst_inspector = inspect(sqlite_engine)
    src_tables = set(src_inspector.get_table_names())
    dst_tables = set(dst_inspector.get_table_names())

    with mysql_engine.connect() as src, sqlite_engine.begin() as dst:
        dst.exec_driver_sql("PRAGMA foreign_keys=OFF")

        for table in TABLE_ORDER:
            if table not in src_tables or table not in dst_tables:
                continue

            if row_count(dst, table) > 0:
                print(f"[import] {table}: destination not empty; skip.", flush=True)
                continue

            src_columns = [c["name"] for c in src_inspector.get_columns(table)]
            dst_columns = {c["name"] for c in dst_inspector.get_columns(table)}
            columns = [c for c in src_columns if c in dst_columns]
            if not columns:
                continue

            rows = src.execute(text(f"SELECT * FROM `{table}`")).mappings().all()
            if not rows:
                continue

            cols_sql = ",".join(f'"{c}"' for c in columns)
            values_sql = ",".join(f":{c}" for c in columns)
            statement = text(
                f'INSERT INTO "{table}" ({cols_sql}) VALUES ({values_sql})'
            )

            payload = []
            for row in rows:
                item = {}
                for col in columns:
                    value = row[col]
                    if hasattr(value, "isoformat"):
                        try:
                            value = value.isoformat(sep=" ")
                        except TypeError:
                            value = value.isoformat()
                    item[col] = value
                payload.append(item)

            dst.execute(statement, payload)
            print(f"[import] {table}: copied {len(payload)} row(s).", flush=True)

        dst.exec_driver_sql("PRAGMA foreign_keys=ON")

    failed = False
    important = [
        "categories","quests","quest_completions",
        "xp_ledger","coin_ledger","rewards"
    ]

    with mysql_engine.connect() as src, sqlite_engine.connect() as dst:
        for table in important:
            if table not in src_tables or table not in dst_tables:
                continue
            before = row_count(src, table, mysql=True)
            after = row_count(dst, table)
            ok = before == after
            print(
                f"[import-check] {table}: MariaDB={before}, SQLite={after} "
                f"[{'OK' if ok else 'MISMATCH'}]",
                flush=True
            )
            failed = failed or not ok

        if "coin_ledger" in src_tables:
            a = int(src.execute(text(
                "SELECT COALESCE(SUM(amount),0) FROM coin_ledger"
            )).scalar_one())
            b = int(dst.execute(text(
                "SELECT COALESCE(SUM(amount),0) FROM coin_ledger"
            )).scalar_one())
            print(f"[import-check] coin balance: MariaDB={a}, SQLite={b}", flush=True)
            failed = failed or a != b

        if "xp_ledger" in src_tables:
            a = int(src.execute(text(
                "SELECT COALESCE(SUM(amount),0) FROM xp_ledger"
            )).scalar_one())
            b = int(dst.execute(text(
                "SELECT COALESCE(SUM(amount),0) FROM xp_ledger"
            )).scalar_one())
            print(f"[import-check] XP sum: MariaDB={a}, SQLite={b}", flush=True)
            failed = failed or a != b

    if failed:
        print(
            "[import] Plausibility check failed. Import marker was not written.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    MARKER.write_text(
        "MariaDB -> SQLite migration completed successfully.\n",
        encoding="utf-8",
    )
    print("[import] MariaDB -> SQLite migration completed successfully.", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
