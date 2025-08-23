-- Simple Activity Meter Table Setup and Fix
-- 描述: T4 - 建立或修復 activity_meter 表的 UNIQUE 約束問題
-- Task ID: T4
-- Migration 0005: 簡化的 activity_meter 表設置和約束修復

-- Step 1: 創建備份表（如果原表存在）
CREATE TABLE IF NOT EXISTS activity_meter_backup_v5 (
    guild_id INTEGER,
    user_id INTEGER,
    score REAL,
    last_msg INTEGER,
    backup_timestamp TEXT
);

-- 備份現有資料（如果表存在）
INSERT OR IGNORE INTO activity_meter_backup_v5 (guild_id, user_id, score, last_msg, backup_timestamp)
SELECT guild_id, user_id, score, last_msg, datetime('now')
FROM activity_meter;

-- Step 2: 刪除並重建表
DROP TABLE IF EXISTS activity_meter;

CREATE TABLE activity_meter (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL, 
    score REAL DEFAULT 0.0,
    last_msg INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (guild_id, user_id)
);

-- Step 3: 還原資料並去重
INSERT OR REPLACE INTO activity_meter (guild_id, user_id, score, last_msg)
SELECT 
    guild_id,
    user_id,
    MAX(score) as score,
    MAX(last_msg) as last_msg
FROM activity_meter_backup_v5
GROUP BY guild_id, user_id;

-- Step 4: 創建索引
CREATE INDEX IF NOT EXISTS idx_activity_meter_composite 
ON activity_meter(guild_id, user_id);

CREATE INDEX IF NOT EXISTS idx_activity_meter_last_msg 
ON activity_meter(last_msg);

CREATE INDEX IF NOT EXISTS idx_activity_meter_score 
ON activity_meter(score DESC);

-- Step 5: 測試 UPSERT 功能
INSERT OR REPLACE INTO activity_meter (guild_id, user_id, score, last_msg) 
VALUES (-999, -999, 100, 123456);

-- 再次插入相同ID但不同值
INSERT OR REPLACE INTO activity_meter (guild_id, user_id, score, last_msg) 
VALUES (-999, -999, 200, 654321);

-- 清理測試資料
DELETE FROM activity_meter WHERE guild_id = -999 AND user_id = -999;

-- Step 6: 清理備份表
DROP TABLE IF EXISTS activity_meter_backup_v5;