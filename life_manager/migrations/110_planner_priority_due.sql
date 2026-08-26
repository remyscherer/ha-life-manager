ALTER TABLE quests
  ADD COLUMN IF NOT EXISTS priority VARCHAR(20) NOT NULL DEFAULT 'normal',
  ADD COLUMN IF NOT EXISTS due_date DATE NULL;

INSERT INTO life_manager_meta (meta_key, meta_value)
VALUES ('schema_version', '1.1.0')
ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value);
