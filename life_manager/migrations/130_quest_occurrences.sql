CREATE TABLE IF NOT EXISTS quest_occurrences (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    quest_id INT NOT NULL,
    occurrence_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    moved_to DATE NULL,
    note VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_quest_occurrence (quest_id, occurrence_date),
    KEY idx_occurrence_date_status (occurrence_date, status),
    CONSTRAINT fk_quest_occurrence_quest FOREIGN KEY (quest_id) REFERENCES quests(id)
);

INSERT INTO life_manager_meta (meta_key, meta_value)
VALUES ('schema_version','1.3.0')
ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value);
