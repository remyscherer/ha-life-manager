ALTER TABLE rewards
  ADD COLUMN IF NOT EXISTS wishlist TINYINT(1) NOT NULL DEFAULT 0;

ALTER TABLE savings_goals
  ADD COLUMN IF NOT EXISTS reserved_coins INT NOT NULL DEFAULT 0;

INSERT INTO life_manager_meta (meta_key, meta_value)
VALUES ('schema_version','1.6.0')
ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value);
