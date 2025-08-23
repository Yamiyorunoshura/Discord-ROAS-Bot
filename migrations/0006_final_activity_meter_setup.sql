-- Final Activity Meter Table Setup
-- 描述: T4 - 建立或修復 activity_meter 表的 UNIQUE 約束問題
-- Task ID: T4
-- Migration 0006: 最終的 activity_meter 表設置

-- 檢查並處理現有表
DROP TABLE IF EXISTS activity_meter_backup_v6;

-- 如果 activity_meter 表存在，先備份其資料
CREATE TABLE activity_meter_backup_v6 (
    guild_id INTEGER,
    user_id INTEGER,
    score REAL,
    last_msg INTEGER
);

-- 只在表存在時才備份資料
INSERT INTO activity_meter_backup_v6 (guild_id, user_id, score, last_msg)
SELECT guild_id, user_id, score, last_msg
FROM activity_meter
WHERE EXISTS (
    SELECT 1 FROM sqlite_master 
    WHERE type='table' AND name='activity_meter'
);

-- 刪除舊表
DROP TABLE IF EXISTS activity_meter;

-- 創建新表結構
CREATE TABLE activity_meter (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL, 
    score REAL DEFAULT 0.0,
    last_msg INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (guild_id, user_id)
);

-- 還原資料（如果有的話）
INSERT OR REPLACE INTO activity_meter (guild_id, user_id, score, last_msg)
SELECT 
    guild_id,
    user_id,
    MAX(score) as score,
    MAX(last_msg) as last_msg
FROM activity_meter_backup_v6
GROUP BY guild_id, user_id;

-- 創建索引
CREATE INDEX IF NOT EXISTS idx_activity_meter_composite 
ON activity_meter(guild_id, user_id);

CREATE INDEX IF NOT EXISTS idx_activity_meter_last_msg 
ON activity_meter(last_msg);

CREATE INDEX IF NOT EXISTS idx_activity_meter_score 
ON activity_meter(score DESC);

-- 測試 UPSERT 功能
INSERT OR REPLACE INTO activity_meter (guild_id, user_id, score, last_msg) 
VALUES (-999, -999, 100, 123456);

-- 再次插入相同ID但不同值（測試 PRIMARY KEY 約束）
INSERT OR REPLACE INTO activity_meter (guild_id, user_id, score, last_msg) 
VALUES (-999, -999, 200, 654321);

-- 驗證只有一筆記錄
SELECT CASE 
    WHEN (SELECT COUNT(*) FROM activity_meter WHERE guild_id=-999 AND user_id=-999) = 1 
    THEN 'UPSERT_SUCCESS'
    ELSE 'UPSERT_FAILED'
END;

-- 清理測試資料
DELETE FROM activity_meter WHERE guild_id = -999 AND user_id = -999;

-- 清理備份表
DROP TABLE IF EXISTS activity_meter_backup_v6;