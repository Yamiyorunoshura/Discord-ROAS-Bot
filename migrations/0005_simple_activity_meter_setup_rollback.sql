-- Rollback script for Simple Activity Meter Setup
-- 描述: T4 - 回滾簡化的 activity_meter 表設置
-- Task ID: T4
-- Migration 0005 Rollback

-- 備份當前資料
CREATE TABLE IF NOT EXISTS activity_meter_rollback_backup_v5 (
    guild_id INTEGER,
    user_id INTEGER,
    score REAL,
    last_msg INTEGER,
    rollback_timestamp TEXT
);

INSERT INTO activity_meter_rollback_backup_v5 (guild_id, user_id, score, last_msg, rollback_timestamp)
SELECT guild_id, user_id, score, last_msg, datetime('now')
FROM activity_meter;

-- 刪除當前表
DROP TABLE IF EXISTS activity_meter;

-- 重建簡單版本
CREATE TABLE activity_meter (
    guild_id INTEGER,
    user_id INTEGER,
    score REAL DEFAULT 0,
    last_msg INTEGER DEFAULT 0
);

-- 還原資料
INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
SELECT guild_id, user_id, score, last_msg
FROM activity_meter_rollback_backup_v5;

-- 創建基本索引
CREATE INDEX IF NOT EXISTS idx_activity_meter_guild_user 
ON activity_meter(guild_id, user_id);

-- 清理備份表
DROP TABLE IF EXISTS activity_meter_rollback_backup_v5;