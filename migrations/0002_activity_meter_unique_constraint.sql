-- Activity Meter Unique Constraint Migration
-- T3 - 併發與資料庫鎖定穩定性實施
-- Migration 0002: 為 activity_meter 表添加唯一約束以支持 UPSERT

-- 檢查並備份現有資料
-- 這個遷移會先備份現有資料，然後重建表格加上約束

-- Step 1: 創建備份表
CREATE TABLE IF NOT EXISTS activity_meter_backup AS 
SELECT * FROM activity_meter;

-- Step 2: 刪除舊表
DROP TABLE IF EXISTS activity_meter;

-- Step 3: 創建新表格，加上唯一約束
CREATE TABLE activity_meter (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    score REAL DEFAULT 0,
    last_msg INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

-- Step 4: 還原資料，去除重複項
-- 對於重複的 (guild_id, user_id) 組合，保留 last_msg 最新的記錄
INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
SELECT 
    guild_id,
    user_id,
    MAX(score) as score,
    MAX(last_msg) as last_msg
FROM activity_meter_backup
GROUP BY guild_id, user_id;

-- Step 5: 刪除備份表
DROP TABLE activity_meter_backup;

-- Step 6: 創建索引以優化查詢性能
CREATE INDEX IF NOT EXISTS idx_activity_meter_guild_user 
ON activity_meter(guild_id, user_id);

CREATE INDEX IF NOT EXISTS idx_activity_meter_last_msg 
ON activity_meter(last_msg);

-- 驗證遷移結果
-- 可以運行以下查詢確認約束已正確建立：
-- PRAGMA table_info(activity_meter);
-- SELECT COUNT(*) FROM activity_meter;