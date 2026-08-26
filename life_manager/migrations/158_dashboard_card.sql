INSERT INTO life_manager_meta (meta_key, meta_value)
VALUES ('schema_version','1.5.8')
ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value);
