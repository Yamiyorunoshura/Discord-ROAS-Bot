-- ROAS Discord Bot v2.4.4 核心資料表創建遷移
-- Task ID: 1 - 核心架構和基礎設施建置
-- 
-- 這個遷移腳本創建支援三大新功能所需的所有資料表：
-- 1. 子機器人聊天功能和管理系統
-- 2. AI LLM 集成和安全控制系統
-- 3. 自動化部署和啟動系統
--
-- 遷移版本: v2_4_4_core_tables
-- 創建日期: 2025-08-25

-- ========== 子機器人系統資料表 ==========

-- sub_bots (子機器人配置表)
CREATE TABLE IF NOT EXISTS sub_bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    token_hash VARCHAR(255) NOT NULL, -- 加密儲存的 Token
    target_channels TEXT NOT NULL, -- JSON 格式的頻道 ID 列表
    ai_enabled BOOLEAN DEFAULT FALSE,
    ai_model VARCHAR(50),
    personality TEXT,
    rate_limit INTEGER DEFAULT 10,
    status VARCHAR(20) DEFAULT 'offline',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active_at DATETIME,
    message_count INTEGER DEFAULT 0
);

-- 為sub_bots表創建索引以優化查詢效能
CREATE INDEX IF NOT EXISTS idx_sub_bots_bot_id ON sub_bots(bot_id);
CREATE INDEX IF NOT EXISTS idx_sub_bots_status ON sub_bots(status);
CREATE INDEX IF NOT EXISTS idx_sub_bots_ai_enabled ON sub_bots(ai_enabled);

-- sub_bot_channels (子機器人頻道關聯表)
CREATE TABLE IF NOT EXISTS sub_bot_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_bot_id INTEGER NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_type VARCHAR(20) DEFAULT 'text',
    permissions TEXT, -- JSON 格式的權限設定
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sub_bot_id) REFERENCES sub_bots(id) ON DELETE CASCADE,
    UNIQUE(sub_bot_id, channel_id)
);

-- 為sub_bot_channels表創建索引
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_sub_bot_id ON sub_bot_channels(sub_bot_id);
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_channel_id ON sub_bot_channels(channel_id);

-- ========== AI系統資料表 ==========

-- ai_conversations (AI 對話記錄表)
CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL,
    sub_bot_id INTEGER,
    provider VARCHAR(20) NOT NULL,
    model VARCHAR(50) NOT NULL,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    tokens_used INTEGER NOT NULL,
    cost DECIMAL(10, 6) NOT NULL,
    response_time DECIMAL(8, 3),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sub_bot_id) REFERENCES sub_bots(id) ON DELETE SET NULL
);

-- 為ai_conversations表創建索引
CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_id ON ai_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_sub_bot_id ON ai_conversations(sub_bot_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_provider ON ai_conversations(provider);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_created_at ON ai_conversations(created_at);

-- ai_usage_quotas (AI 使用配額表)
CREATE TABLE IF NOT EXISTS ai_usage_quotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT UNIQUE NOT NULL,
    daily_limit INTEGER DEFAULT 50,
    weekly_limit INTEGER DEFAULT 200,
    monthly_limit INTEGER DEFAULT 1000,
    daily_used INTEGER DEFAULT 0,
    weekly_used INTEGER DEFAULT 0,
    monthly_used INTEGER DEFAULT 0,
    total_cost_limit DECIMAL(10, 2) DEFAULT 10.00,
    total_cost_used DECIMAL(10, 2) DEFAULT 0.00,
    last_reset_daily DATE DEFAULT CURRENT_DATE,
    last_reset_weekly DATE DEFAULT CURRENT_DATE,
    last_reset_monthly DATE DEFAULT CURRENT_DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 為ai_usage_quotas表創建索引
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_user_id ON ai_usage_quotas(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_daily_reset ON ai_usage_quotas(last_reset_daily);

-- ai_providers (AI 提供商配置表)
CREATE TABLE IF NOT EXISTS ai_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name VARCHAR(20) UNIQUE NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL, -- 加密儲存的 API Key
    base_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 1, -- 優先級，數字越小優先級越高
    rate_limit_per_minute INTEGER DEFAULT 60,
    cost_per_token DECIMAL(10, 8) DEFAULT 0.000002,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 為ai_providers表創建索引
CREATE INDEX IF NOT EXISTS idx_ai_providers_name ON ai_providers(provider_name);
CREATE INDEX IF NOT EXISTS idx_ai_providers_active ON ai_providers(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_providers_priority ON ai_providers(priority);

-- ========== 部署系統資料表 ==========

-- deployment_logs (部署日誌表)
CREATE TABLE IF NOT EXISTS deployment_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id VARCHAR(50) UNIQUE NOT NULL,
    mode VARCHAR(20) NOT NULL, -- docker, uv_python, fallback
    status VARCHAR(20) NOT NULL, -- pending, installing, configuring, starting, running, failed, degraded
    environment_info TEXT, -- JSON 格式的環境資訊
    error_message TEXT,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    duration_seconds INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 為deployment_logs表創建索引
CREATE INDEX IF NOT EXISTS idx_deployment_logs_deployment_id ON deployment_logs(deployment_id);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_mode ON deployment_logs(mode);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_status ON deployment_logs(status);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_start_time ON deployment_logs(start_time);

-- ========== 預設資料插入 ==========

-- 插入預設 AI 提供商配置
INSERT OR IGNORE INTO ai_providers (provider_name, api_key_hash, base_url, priority, cost_per_token) VALUES
('openai', '', 'https://api.openai.com/v1', 1, 0.000002),
('anthropic', '', 'https://api.anthropic.com', 2, 0.000008),
('google', '', 'https://generativelanguage.googleapis.com', 3, 0.000001);

-- ========== 資料完整性約束驗證 ==========

-- 驗證外鍵約束
PRAGMA foreign_keys = ON;

-- 驗證表格結構
SELECT 'sub_bots table structure validation' as validation_step;
SELECT sql FROM sqlite_master WHERE type='table' AND name='sub_bots';

SELECT 'sub_bot_channels table structure validation' as validation_step;
SELECT sql FROM sqlite_master WHERE type='table' AND name='sub_bot_channels';

SELECT 'ai_conversations table structure validation' as validation_step;
SELECT sql FROM sqlite_master WHERE type='table' AND name='ai_conversations';

SELECT 'ai_usage_quotas table structure validation' as validation_step;
SELECT sql FROM sqlite_master WHERE type='table' AND name='ai_usage_quotas';

SELECT 'ai_providers table structure validation' as validation_step;
SELECT sql FROM sqlite_master WHERE type='table' AND name='ai_providers';

SELECT 'deployment_logs table structure validation' as validation_step;
SELECT sql FROM sqlite_master WHERE type='table' AND name='deployment_logs';

-- 驗證索引創建
SELECT 'Index validation' as validation_step;
SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';