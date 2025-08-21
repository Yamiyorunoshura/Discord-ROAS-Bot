CREATE TABLE IF NOT EXISTS achievements (
id TEXT PRIMARY KEY,
name TEXT NOT NULL,
description TEXT NOT NULL,
achievement_type TEXT NOT NULL,
guild_id INTEGER NOT NULL,
trigger_conditions TEXT NOT NULL,
rewards TEXT NOT NULL,
status TEXT NOT NULL DEFAULT 'active',
metadata TEXT,
created_at TIMESTAMP NOT NULL,
updated_at TIMESTAMP NOT NULL,
CONSTRAINT achievements_type_check
CHECK (achievement_type IN ('milestone', 'recurring', 'hidden', 'progressive')),
CONSTRAINT achievements_status_check
CHECK (status IN ('active', 'disabled', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_achievements_guild_id ON achievements(guild_id);

CREATE INDEX IF NOT EXISTS idx_achievements_type ON achievements(achievement_type);

CREATE INDEX IF NOT EXISTS idx_achievements_status ON achievements(status);

CREATE INDEX IF NOT EXISTS idx_achievements_guild_status ON achievements(guild_id, status);

CREATE TABLE IF NOT EXISTS user_achievement_progress (
id TEXT PRIMARY KEY,
achievement_id TEXT NOT NULL,
user_id INTEGER NOT NULL,
guild_id INTEGER NOT NULL,
current_progress TEXT NOT NULL,
completed BOOLEAN NOT NULL DEFAULT 0,
completed_at TIMESTAMP,
last_updated TIMESTAMP NOT NULL,
FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_progress_user_id ON user_achievement_progress(user_id);

CREATE INDEX IF NOT EXISTS idx_progress_achievement_id ON user_achievement_progress(achievement_id);

CREATE INDEX IF NOT EXISTS idx_progress_guild_id ON user_achievement_progress(guild_id);

CREATE INDEX IF NOT EXISTS idx_progress_completed ON user_achievement_progress(completed);

CREATE INDEX IF NOT EXISTS idx_progress_user_guild ON user_achievement_progress(user_id, guild_id);

CREATE INDEX IF NOT EXISTS idx_progress_user_achievement ON user_achievement_progress(user_id, achievement_id);

CREATE TABLE IF NOT EXISTS achievement_rewards_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
achievement_id TEXT NOT NULL,
user_id INTEGER NOT NULL,
guild_id INTEGER NOT NULL,
reward_type TEXT NOT NULL,
reward_value TEXT NOT NULL,
reward_metadata TEXT,
status TEXT NOT NULL DEFAULT 'pending',
error_message TEXT,
created_at TIMESTAMP NOT NULL,
processed_at TIMESTAMP,
FOREIGN KEY (achievement_id) REFERENCES achievements(id),
CONSTRAINT rewards_type_check
CHECK (reward_type IN ('currency', 'role', 'badge', 'custom')),
CONSTRAINT rewards_status_check
CHECK (status IN ('pending', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_rewards_log_user_id ON achievement_rewards_log(user_id);

CREATE INDEX IF NOT EXISTS idx_rewards_log_achievement_id ON achievement_rewards_log(achievement_id);

CREATE INDEX IF NOT EXISTS idx_rewards_log_guild_id ON achievement_rewards_log(guild_id);

CREATE INDEX IF NOT EXISTS idx_rewards_log_status ON achievement_rewards_log(status);

CREATE INDEX IF NOT EXISTS idx_rewards_log_type ON achievement_rewards_log(reward_type);

CREATE INDEX IF NOT EXISTS idx_rewards_log_created_at ON achievement_rewards_log(created_at);

CREATE TABLE IF NOT EXISTS user_badges (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER NOT NULL,
guild_id INTEGER NOT NULL,
achievement_id TEXT NOT NULL,
badge_name TEXT NOT NULL,
badge_metadata TEXT,
earned_at TIMESTAMP NOT NULL,
FOREIGN KEY (achievement_id) REFERENCES achievements(id),
UNIQUE(user_id, guild_id, achievement_id)
);

CREATE INDEX IF NOT EXISTS idx_badges_user_id ON user_badges(user_id);

CREATE INDEX IF NOT EXISTS idx_badges_guild_id ON user_badges(guild_id);

CREATE INDEX IF NOT EXISTS idx_badges_achievement_id ON user_badges(achievement_id);

CREATE INDEX IF NOT EXISTS idx_badges_user_guild ON user_badges(user_id, guild_id);

CREATE INDEX IF NOT EXISTS idx_badges_earned_at ON user_badges(earned_at);

CREATE TABLE IF NOT EXISTS achievement_audit_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
operation TEXT NOT NULL,
target_type TEXT NOT NULL,
target_id TEXT NOT NULL,
guild_id INTEGER NOT NULL,
user_id INTEGER,
old_values TEXT,
new_values TEXT,
created_at TIMESTAMP NOT NULL,
success BOOLEAN NOT NULL DEFAULT 1,
error_message TEXT,
CONSTRAINT audit_target_type_check
CHECK (target_type IN ('achievement', 'progress', 'reward', 'badge'))
);

CREATE INDEX IF NOT EXISTS idx_audit_log_operation ON achievement_audit_log(operation);

CREATE INDEX IF NOT EXISTS idx_audit_log_target_type ON achievement_audit_log(target_type);

CREATE INDEX IF NOT EXISTS idx_audit_log_target_id ON achievement_audit_log(target_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_guild_id ON achievement_audit_log(guild_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON achievement_audit_log(user_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON achievement_audit_log(created_at);

CREATE INDEX IF NOT EXISTS idx_audit_log_success ON achievement_audit_log(success);

CREATE VIEW IF NOT EXISTS active_achievements AS
SELECT
id,
name,
description,
achievement_type,
guild_id,
trigger_conditions,
rewards,
metadata,
created_at,
updated_at
FROM achievements
WHERE status = 'active';

CREATE VIEW IF NOT EXISTS user_achievement_stats AS
SELECT
user_id,
guild_id,
COUNT(*) as total_achievements,
COUNT(CASE WHEN completed = 1 THEN 1 END) as completed_achievements,
COUNT(CASE WHEN completed = 0 THEN 1 END) as in_progress_achievements,
MAX(completed_at) as last_completion_date
FROM user_achievement_progress
GROUP BY user_id, guild_id;

CREATE VIEW IF NOT EXISTS guild_achievement_stats AS
SELECT
guild_id,
COUNT(DISTINCT id) as total_achievements,
COUNT(CASE WHEN status = 'active' THEN 1 END) as active_achievements,
COUNT(CASE WHEN achievement_type = 'milestone' THEN 1 END) as milestone_achievements,
COUNT(CASE WHEN achievement_type = 'recurring' THEN 1 END) as recurring_achievements,
COUNT(CASE WHEN achievement_type = 'progressive' THEN 1 END) as progressive_achievements,
COUNT(CASE WHEN achievement_type = 'hidden' THEN 1 END) as hidden_achievements
FROM achievements
GROUP BY guild_id;

CREATE TRIGGER IF NOT EXISTS update_achievements_timestamp
AFTER UPDATE ON achievements
FOR EACH ROW
BEGIN
UPDATE achievements
SET updated_at = datetime('now')
WHERE id = NEW.id;

END;

CREATE TRIGGER IF NOT EXISTS update_progress_timestamp
AFTER UPDATE ON user_achievement_progress
FOR EACH ROW
WHEN OLD.current_progress != NEW.current_progress OR OLD.completed != NEW.completed
BEGIN
UPDATE user_achievement_progress
SET last_updated = datetime('now')
WHERE id = NEW.id;

END;

CREATE TRIGGER IF NOT EXISTS set_completion_timestamp
AFTER UPDATE ON user_achievement_progress
FOR EACH ROW
WHEN OLD.completed = 0 AND NEW.completed = 1 AND NEW.completed_at IS NULL
BEGIN
UPDATE user_achievement_progress
SET completed_at = datetime('now')
WHERE id = NEW.id;

END;