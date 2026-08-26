CREATE TABLE IF NOT EXISTS life_manager_meta (
    meta_key VARCHAR(100) PRIMARY KEY,
    meta_value VARCHAR(255) NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
      ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO life_manager_meta (meta_key, meta_value)
VALUES ('schema_version', '0.9.1')
ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value);
