USE life_manager;

CREATE TABLE IF NOT EXISTS achievements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    description VARCHAR(255) NULL,
    icon VARCHAR(80) NULL,
    metric VARCHAR(100) NOT NULL,
    target_value INT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS achievement_unlocks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    achievement_id INT NOT NULL,
    unlocked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_achievement_unlock (achievement_id),
    CONSTRAINT fk_achievement_unlock
      FOREIGN KEY (achievement_id) REFERENCES achievements(id)
);

SELECT 'Life Manager v0.8.0 migration complete' AS info;
