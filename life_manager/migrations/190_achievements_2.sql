-- v1.9.0 Achievements 2.0
ALTER TABLE achievements ADD COLUMN tier TEXT NOT NULL DEFAULT 'bronze';
ALTER TABLE achievements ADD COLUMN reward_coins INTEGER NOT NULL DEFAULT 0;
ALTER TABLE achievements ADD COLUMN title TEXT;
ALTER TABLE achievements ADD COLUMN category TEXT NOT NULL DEFAULT 'general';

ALTER TABLE achievement_unlocks ADD COLUMN reward_granted INTEGER NOT NULL DEFAULT 0;
