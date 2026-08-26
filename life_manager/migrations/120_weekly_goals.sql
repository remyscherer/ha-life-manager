CREATE TABLE IF NOT EXISTS weekly_goals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    goal_type VARCHAR(50) NOT NULL,
    quest_id INT NULL,
    target_count INT NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_weekly_goal_quest
      FOREIGN KEY (quest_id) REFERENCES quests(id)
);

INSERT INTO weekly_goals (name, goal_type, quest_id, target_count, active, sort_order)
SELECT 'Trainings pro Woche', 'quest_type', NULL, 5, 1, 10
WHERE NOT EXISTS (
    SELECT 1 FROM weekly_goals WHERE name='Trainings pro Woche'
);

INSERT INTO life_manager_meta (meta_key, meta_value)
VALUES ('schema_version', '1.2.0')
ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value);
