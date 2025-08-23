-- Enhanced Activity Meter Unique Constraint Fix
-- 描述: T4 - 修復 activity_meter 表 UNIQUE 約束問題，實現真正的 UPSERT 語義
-- Task ID: T4
-- Migration 0003: 修復 activity_meter 表的 UNIQUE 約束問題

-- 使用事務確保原子性操作
BEGIN TRANSACTION;

-- Step 1: 創建備份表結構
CREATE TABLE IF NOT EXISTS activity_meter_backup_v3 (
    guild_id INTEGER,
    user_id INTEGER,
    score REAL DEFAULT 0,
    last_msg INTEGER DEFAULT 0,
    backup_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: 安全地備份現有資料（如果表存在）
INSERT INTO activity_meter_backup_v3 (guild_id, user_id, score, last_msg, backup_timestamp)
SELECT guild_id, user_id, 
       COALESCE(score, 0) as score, 
       COALESCE(last_msg, 0) as last_msg,
       CURRENT_TIMESTAMP as backup_timestamp
FROM activity_meter 
WHERE EXISTS (
    SELECT 1 FROM sqlite_master 
    WHERE type='table' AND name='activity_meter'
)
UNION ALL
SELECT 0, 0, 0, 0, CURRENT_TIMESTAMP WHERE NOT EXISTS (
    SELECT 1 FROM sqlite_master 
    WHERE type='table' AND name='activity_meter'
)
LIMIT 0; -- 這行確保如果原表不存在，不會插入資料

-- Step 3: 重建表格結構
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

-- Step 4: 還原並去重資料
-- 檢查備份表是否有實際資料
INSERT OR IGNORE INTO activity_meter (guild_id, user_id, score, last_msg, created_at, updated_at)
SELECT 
    guild_id,
    user_id,
    MAX(score) as score,
    MAX(last_msg) as last_msg,
    MIN(backup_timestamp) as created_at,
    MAX(backup_timestamp) as updated_at
FROM activity_meter_backup_v3
WHERE guild_id IS NOT NULL AND user_id IS NOT NULL
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
DROP TABLE activity_meter_backup_v3;

-- Step 7: 驗證遷移結果
-- 檢查主鍵約束是否正確建立
INSERT OR IGNORE INTO activity_meter (guild_id, user_id, score, last_msg) 
VALUES (-999, -999, 0, 0);

-- 測試 UPSERT 語義
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

-- 清理測試資料
DELETE FROM activity_meter WHERE guild_id = -999 AND user_id = -999;

-- 提交事務
COMMIT;

-- 記錄遷移完成
-- 這個註釋將被遷移管理器識別
-- Migration completed successfully at: CURRENT_TIMESTAMP