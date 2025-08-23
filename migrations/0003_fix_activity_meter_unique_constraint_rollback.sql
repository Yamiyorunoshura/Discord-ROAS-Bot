-- Rollback script for Activity Meter Unique Constraint Fix
-- 描述: T4 - 回滾 activity_meter 表 UNIQUE 約束修復
-- Task ID: T4
-- Migration 0003 Rollback: 回滾到原始 activity_meter 表結構

-- 使用事務確保原子性操作
BEGIN TRANSACTION;

-- Step 1: 備份當前資料
CREATE TABLE IF NOT EXISTS activity_meter_rollback_backup AS 
SELECT guild_id, user_id, score, last_msg, 
       created_at, updated_at,
       CURRENT_TIMESTAMP as rollback_timestamp
FROM activity_meter;

-- Step 2: 刪除當前表
DROP TABLE IF EXISTS activity_meter;

-- Step 3: 重建原始表結構（無主鍵約束）
CREATE TABLE activity_meter (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    score REAL DEFAULT 0,
    last_msg INTEGER DEFAULT 0
);

-- Step 4: 還原資料
INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
SELECT guild_id, user_id, score, last_msg
FROM activity_meter_rollback_backup;

-- Step 5: 創建原始索引
CREATE INDEX IF NOT EXISTS idx_activity_meter_guild_user 
ON activity_meter(guild_id, user_id);

CREATE INDEX IF NOT EXISTS idx_activity_meter_last_msg 
ON activity_meter(last_msg);

-- Step 6: 清理備份表
DROP TABLE IF EXISTS activity_meter_rollback_backup;

-- 提交事務
COMMIT;

-- 記錄回滾完成
-- Rollback completed successfully at: CURRENT_TIMESTAMP