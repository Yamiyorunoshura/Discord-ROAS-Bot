-- Ultra Simple Activity Meter Setup
-- 描述: T4 - 建立 activity_meter 表
-- Task ID: T4

-- 1. 刪除舊表（如果存在）
DROP TABLE IF EXISTS activity_meter;

-- 2. 創建新表
CREATE TABLE activity_meter (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL, 
    score REAL DEFAULT 0.0,
    last_msg INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

-- 3. 創建索引
CREATE INDEX idx_activity_meter_guild_user ON activity_meter(guild_id, user_id);
CREATE INDEX idx_activity_meter_last_msg ON activity_meter(last_msg);
CREATE INDEX idx_activity_meter_score ON activity_meter(score);

-- 4. 測試插入
INSERT OR REPLACE INTO activity_meter (guild_id, user_id, score, last_msg) VALUES (1, 1, 100, 1000);
INSERT OR REPLACE INTO activity_meter (guild_id, user_id, score, last_msg) VALUES (1, 1, 200, 2000);

-- 5. 清理測試資料
DELETE FROM activity_meter WHERE guild_id = 1 AND user_id = 1;