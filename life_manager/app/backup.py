import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from database import DB_PATH, engine

BACKUP_DIR = Path(os.environ.get("LIFE_MANAGER_BACKUP_DIR", "/data/backups"))
BACKUP_RETENTION = max(1, int(os.environ.get("BACKUP_RETENTION", "20")))
SAFE_NAME = re.compile(r"^life_manager_\d{8}_\d{6}_\d{6}_(manual|pre_restore)\.sqlite3$")


def _ensure_dirs():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _backup_name(kind: str):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"life_manager_{stamp}_{kind}.sqlite3"


def _safe_backup_path(name: str):
    if not SAFE_NAME.fullmatch(name or ""):
        raise ValueError("Invalid backup name")
    path = (BACKUP_DIR / name).resolve()
    if path.parent != BACKUP_DIR.resolve():
        raise ValueError("Invalid backup path")
    return path


def _integrity_check(path: Path):
    con = sqlite3.connect(str(path))
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
        return bool(row and row[0] == "ok")
    finally:
        con.close()


def _create_sqlite_copy(destination: Path):
    source_path = Path(DB_PATH)
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")

    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.unlink(missing_ok=True)

    src = sqlite3.connect(str(source_path), timeout=30)
    dst = sqlite3.connect(str(tmp), timeout=30)
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()

    if not _integrity_check(tmp):
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Backup integrity check failed")

    os.replace(tmp, destination)


def _prune_manual_backups():
    manual = sorted(
        BACKUP_DIR.glob("life_manager_*_manual.sqlite3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in manual[BACKUP_RETENTION:]:
        old.unlink(missing_ok=True)


def create_backup(kind: str = "manual"):
    if kind not in {"manual", "pre_restore"}:
        raise ValueError("Invalid backup kind")

    _ensure_dirs()
    name = _backup_name(kind)
    path = BACKUP_DIR / name
    _create_sqlite_copy(path)

    if kind == "manual":
        _prune_manual_backups()

    return backup_info(path)


def backup_info(path: Path):
    stat = path.stat()
    return {
        "name": path.name,
        "kind": "pre_restore" if path.name.endswith("_pre_restore.sqlite3") else "manual",
        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "size_bytes": int(stat.st_size),
        "size_mb": round(stat.st_size / 1024 / 1024, 2),
    }


def list_backups():
    _ensure_dirs()
    items = []
    for path in BACKUP_DIR.glob("life_manager_*.sqlite3"):
        if SAFE_NAME.fullmatch(path.name):
            items.append(backup_info(path))

    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "directory": str(BACKUP_DIR),
        "database_path": str(DB_PATH),
        "retention": BACKUP_RETENTION,
        "count": len(items),
        "backups": items,
    }


def restore_backup(name: str):
    _ensure_dirs()
    source_path = _safe_backup_path(name)

    if not source_path.exists():
        raise FileNotFoundError("Backup not found")

    if not _integrity_check(source_path):
        raise RuntimeError("Selected backup failed integrity check")

    # Always preserve the current live database immediately before restoring.
    safety = create_backup("pre_restore")

    # Dispose SQLAlchemy connections before replacing database contents.
    engine.dispose()

    source = sqlite3.connect(str(source_path), timeout=30)
    destination = sqlite3.connect(str(DB_PATH), timeout=30)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()

    if not _integrity_check(Path(DB_PATH)):
        raise RuntimeError("Restored database failed integrity check")

    # Ensure future SQLAlchemy connections see the restored file.
    engine.dispose()

    return {
        "success": True,
        "restored_backup": backup_info(source_path),
        "safety_backup": safety,
    }


def delete_backup(name: str):
    _ensure_dirs()
    path = _safe_backup_path(name)
    if not path.exists():
        raise FileNotFoundError("Backup not found")
    info = backup_info(path)
    path.unlink()
    return {"success": True, "deleted": info}
