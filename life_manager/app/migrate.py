import os
from pathlib import Path

from sqlalchemy import text
from database import engine

DB_PATH = Path(os.environ.get("LIFE_MANAGER_DB_PATH", "/data/life_manager.db"))

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  icon TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  category_id INTEGER NOT NULL,
  quest_type TEXT NOT NULL,
  description TEXT,
  estimated_minutes INTEGER,
  kbr INTEGER,
  xp_mode TEXT NOT NULL DEFAULT 'formula',
  fixed_xp INTEGER,
  frequency_days INTEGER,
  project_factor REAL,
  priority TEXT NOT NULL DEFAULT 'normal',
  due_date TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS quest_schedules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quest_id INTEGER NOT NULL,
  weekday INTEGER,
  interval_days INTEGER,
  next_due TEXT,
  FOREIGN KEY(quest_id) REFERENCES quests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quest_completions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quest_id INTEGER NOT NULL,
  completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  xp_awarded INTEGER NOT NULL DEFAULT 0,
  willpower_xp INTEGER NOT NULL DEFAULT 0,
  kbr_at_completion INTEGER,
  FOREIGN KEY(quest_id) REFERENCES quests(id)
);

CREATE TABLE IF NOT EXISTS xp_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  amount INTEGER NOT NULL,
  xp_type TEXT NOT NULL,
  source_type TEXT,
  source_id INTEGER,
  description TEXT
);

CREATE TABLE IF NOT EXISTS coin_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  amount INTEGER NOT NULL,
  reason TEXT
);

CREATE TABLE IF NOT EXISTS daily_summary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  summary_date TEXT NOT NULL UNIQUE,
  earned_xp INTEGER NOT NULL DEFAULT 0,
  possible_xp INTEGER NOT NULL DEFAULT 0,
  percentage INTEGER NOT NULL DEFAULT 0,
  coins_awarded INTEGER NOT NULL DEFAULT 0,
  finalized_at TEXT
);

CREATE TABLE IF NOT EXISTS rewards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  cost INTEGER NOT NULL DEFAULT 0,
  icon TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  wishlist INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reward_purchases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reward_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  total_cost INTEGER NOT NULL,
  purchased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(reward_id) REFERENCES rewards(id)
);

CREATE TABLE IF NOT EXISTS savings_goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  target_coins INTEGER NOT NULL,
  reward_id INTEGER,
  active INTEGER NOT NULL DEFAULT 1,
  reserved_coins INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(reward_id) REFERENCES rewards(id)
);

CREATE TABLE IF NOT EXISTS achievements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT,
  icon TEXT,
  metric TEXT NOT NULL,
  target_value INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS achievement_unlocks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  achievement_id INTEGER NOT NULL UNIQUE,
  unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(achievement_id) REFERENCES achievements(id)
);

CREATE TABLE IF NOT EXISTS planner_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_date TEXT NOT NULL UNIQUE,
  generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  recommendation_quest_id INTEGER,
  recommendation_score REAL
);

CREATE TABLE IF NOT EXISTS weekly_goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  goal_type TEXT NOT NULL,
  quest_id INTEGER,
  target_count INTEGER NOT NULL DEFAULT 1,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(quest_id) REFERENCES quests(id)
);

CREATE TABLE IF NOT EXISTS quest_occurrences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quest_id INTEGER NOT NULL,
  occurrence_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled',
  moved_to TEXT,
  note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(quest_id, occurrence_date),
  FOREIGN KEY(quest_id) REFERENCES quests(id)
);

CREATE INDEX IF NOT EXISTS idx_occurrence_date_status
  ON quest_occurrences(occurrence_date,status);

CREATE TABLE IF NOT EXISTS life_manager_meta (
  meta_key TEXT PRIMARY KEY,
  meta_value TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  migration_name TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    raw = engine.raw_connection()
    try:
        raw.executescript(SCHEMA)
        raw.commit()
    finally:
        raw.close()

    with engine.begin() as c:
        if not c.execute(text(
            "SELECT id FROM weekly_goals WHERE name='Trainings pro Woche' LIMIT 1"
        )).first():
            c.execute(text("""
                INSERT INTO weekly_goals
                  (name,goal_type,quest_id,target_count,active,sort_order)
                VALUES
                  ('Trainings pro Woche','quest_type',NULL,5,1,10)
            """))

        c.execute(text("""
            INSERT INTO life_manager_meta(meta_key,meta_value,updated_at)
            VALUES('schema_version','1.7.0',CURRENT_TIMESTAMP)
            ON CONFLICT(meta_key) DO UPDATE SET
              meta_value=excluded.meta_value,
              updated_at=CURRENT_TIMESTAMP
        """))

        c.execute(text("""
            INSERT INTO schema_migrations(migration_name)
            VALUES('170_embedded_sqlite')
            ON CONFLICT(migration_name) DO NOTHING
        """))

    print(f"[sqlite] Database ready: {DB_PATH}", flush=True)

if __name__ == "__main__":
    main()
