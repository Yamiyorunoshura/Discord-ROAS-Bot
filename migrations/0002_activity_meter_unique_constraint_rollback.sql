-- Activity Meter Rollback Script
-- T3 - 併發與資料庫鎖定穩定性實施
-- Rollback 0002: 移除 activity_meter 表的唯一約束

-- Step 1: 創建備份表
CREATE TABLE IF NOT EXISTS activity_meter_backup AS 
SELECT * FROM activity_meter;

-- Step 2: 刪除含約束的表
DROP TABLE IF EXISTS activity_meter;

-- Step 3: 重新創建原始表格（不含約束）
CREATE TABLE activity_meter (
    guild_id INTEGER,
    user_id INTEGER,
    score REAL DEFAULT 0,
    last_msg INTEGER DEFAULT 0
);

-- Step 4: 還原所有資料
INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
SELECT guild_id, user_id, score, last_msg
FROM activity_meter_backup;

-- Step 5: 刪除備份表
DROP TABLE activity_meter_backup;

-- Step 6: 刪除相關索引
DROP INDEX IF EXISTS idx_activity_meter_guild_user;
DROP INDEX IF EXISTS idx_activity_meter_last_msg;