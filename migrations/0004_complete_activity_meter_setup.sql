-- Complete Activity Meter Table Setup and Fix
-- 描述: T4 - 建立或修復 activity_meter 表的 UNIQUE 約束問題
-- Task ID: T4
-- Migration 0004: 完整的 activity_meter 表設置和約束修復

-- 使用事務確保原子性操作
BEGIN TRANSACTION;

-- Step 1: 檢查是否存在 activity_meter 表
-- 如果不存在，創建基礎表；如果存在，檢查約束

-- Step 2: 創建備份表（如果原表存在且有資料）
DROP TABLE IF EXISTS activity_meter_backup_v4;
CREATE TABLE activity_meter_backup_v4 AS 
SELECT * FROM activity_meter WHERE 1=0; -- 創建空的備份表結構

-- 如果原表存在且有資料，則備份
INSERT INTO activity_meter_backup_v4 
SELECT guild_id, user_id, score, last_msg, 
       CURRENT_TIMESTAMP as backup_timestamp
FROM activity_meter 
WHERE EXISTS (
    SELECT 1 FROM sqlite_master 
    WHERE type='table' AND name='activity_meter'
);

-- Step 3: 重建表格結構（無論是否存在）
DROP TABLE IF EXISTS activity_meter;

CREATE TABLE activity_meter (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL, 
    score REAL DEFAULT 0.0,
    last_msg INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, user_id)
);

-- Step 4: 還原資料（如果有備份資料）
INSERT OR IGNORE INTO activity_meter (guild_id, user_id, score, last_msg, created_at, updated_at)
SELECT 
    guild_id,
    user_id,
    COALESCE(MAX(score), 0.0) as score,
    COALESCE(MAX(last_msg), 0) as last_msg,
    CURRENT_TIMESTAMP as created_at,
    CURRENT_TIMESTAMP as updated_at
FROM activity_meter_backup_v4
GROUP BY guild_id, user_id;

-- Step 5: 創建效能優化索引
CREATE INDEX IF NOT EXISTS idx_activity_meter_composite 
ON activity_meter(guild_id, user_id);

CREATE INDEX IF NOT EXISTS idx_activity_meter_last_msg 
ON activity_meter(last_msg);

CREATE INDEX IF NOT EXISTS idx_activity_meter_score 
ON activity_meter(score DESC);

CREATE INDEX IF NOT EXISTS idx_activity_meter_updated_at 
ON activity_meter(updated_at);

-- Step 6: 清理備份表
DROP TABLE IF EXISTS activity_meter_backup_v4;

-- Step 7: 插入測試資料以驗證 UPSERT 語義
-- 測試插入
INSERT OR IGNORE INTO activity_meter (guild_id, user_id, score, last_msg) 
VALUES (-999, -999, 0, 0);

-- 測試 UPSERT
INSERT INTO activity_meter (guild_id, user_id, score, last_msg, updated_at) 
VALUES (-999, -999, 100, 123456789, CURRENT_TIMESTAMP)
ON CONFLICT(guild_id, user_id) DO UPDATE SET
    score = CASE 
        WHEN excluded.score > activity_meter.score 
        THEN excluded.score 
        ELSE activity_meter.score 
    END,
    last_msg = CASE 
        WHEN excluded.last_msg > activity_meter.last_msg 
        THEN excluded.last_msg 
        ELSE activity_meter.last_msg 
    END,
    updated_at = CURRENT_TIMESTAMP;

-- 驗證UPSERT結果
-- 應該只有一筆記錄，score=100, last_msg=123456789
SELECT CASE 
    WHEN (SELECT COUNT(*) FROM activity_meter WHERE guild_id=-999 AND user_id=-999) = 1 
    AND (SELECT score FROM activity_meter WHERE guild_id=-999 AND user_id=-999) = 100
    THEN 'UPSERT_TEST_PASSED'
    ELSE 'UPSERT_TEST_FAILED'
END as test_result;

-- 清理測試資料
DELETE FROM activity_meter WHERE guild_id = -999 AND user_id = -999;

-- 提交事務
COMMIT;

-- 記錄遷移完成
-- Migration completed successfully at: CURRENT_TIMESTAMP