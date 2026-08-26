CREATE TABLE IF NOT EXISTS planner_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    plan_date DATE NOT NULL,
    generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recommendation_quest_id INT NULL,
    recommendation_score DECIMAL(10,2) NULL,
    UNIQUE KEY uq_planner_history_date (plan_date)
);

INSERT INTO life_manager_meta (meta_key, meta_value)
VALUES ('schema_version', '1.0.0')
ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value);
