-- ROAS Bot v2.4.4 Core Tables Migration
-- Task ID: 1 - 核心架構和基礎設施建置
-- 創建支持新功能的核心資料表：子機器人、AI對話、部署日誌
-- Author: Elena (API設計專家)
-- Created: 2025-08-25

-- ========== 子機器人系統資料模型 ==========

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
    message_count INTEGER DEFAULT 0,
    CHECK (status IN ('offline', 'online', 'error', 'maintenance')),
    CHECK (rate_limit > 0)
);

-- sub_bot_channels (子機器人頻道關聯表)
CREATE TABLE IF NOT EXISTS sub_bot_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_bot_id INTEGER NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_type VARCHAR(20) DEFAULT 'text',
    permissions TEXT, -- JSON 格式的權限設定
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sub_bot_id) REFERENCES sub_bots(id) ON DELETE CASCADE,
    UNIQUE(sub_bot_id, channel_id),
    CHECK (channel_type IN ('text', 'voice', 'category', 'dm', 'group_dm'))
);

-- ========== AI系統資料模型 ==========

-- ai_conversations (AI 對話記錄表)
CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL,
    sub_bot_id INTEGER,
    provider VARCHAR(20) NOT NULL,
    model VARCHAR(50) NOT NULL,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    cost DECIMAL(10, 6) NOT NULL DEFAULT 0.0,
    response_time DECIMAL(8, 3),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sub_bot_id) REFERENCES sub_bots(id) ON DELETE SET NULL,
    CHECK (provider IN ('openai', 'anthropic', 'google', 'local')),
    CHECK (tokens_used >= 0),
    CHECK (cost >= 0),
    CHECK (response_time >= 0)
);

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
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (daily_limit >= 0),
    CHECK (weekly_limit >= 0),
    CHECK (monthly_limit >= 0),
    CHECK (daily_used >= 0),
    CHECK (weekly_used >= 0),
    CHECK (monthly_used >= 0),
    CHECK (total_cost_limit >= 0),
    CHECK (total_cost_used >= 0)
);

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
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (provider_name IN ('openai', 'anthropic', 'google', 'local')),
    CHECK (priority > 0),
    CHECK (rate_limit_per_minute > 0),
    CHECK (cost_per_token >= 0)
);

-- ========== 部署系統資料模型 ==========

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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (mode IN ('docker', 'uv_python', 'fallback')),
    CHECK (status IN ('pending', 'installing', 'configuring', 'starting', 'running', 'failed', 'degraded')),
    CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
);

-- ========== 創建索引以優化查詢效能 ==========

-- sub_bots 表索引
CREATE INDEX IF NOT EXISTS idx_sub_bots_bot_id ON sub_bots(bot_id);
CREATE INDEX IF NOT EXISTS idx_sub_bots_status ON sub_bots(status);
CREATE INDEX IF NOT EXISTS idx_sub_bots_created_at ON sub_bots(created_at);
CREATE INDEX IF NOT EXISTS idx_sub_bots_ai_enabled ON sub_bots(ai_enabled);

-- sub_bot_channels 表索引
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_sub_bot_id ON sub_bot_channels(sub_bot_id);
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_channel_id ON sub_bot_channels(channel_id);
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_type ON sub_bot_channels(channel_type);

-- ai_conversations 表索引
CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_id ON ai_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_sub_bot_id ON ai_conversations(sub_bot_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_provider ON ai_conversations(provider);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_created_at ON ai_conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_date ON ai_conversations(user_id, created_at);

-- ai_usage_quotas 表索引
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_user_id ON ai_usage_quotas(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_daily_reset ON ai_usage_quotas(last_reset_daily);
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_weekly_reset ON ai_usage_quotas(last_reset_weekly);
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_monthly_reset ON ai_usage_quotas(last_reset_monthly);

-- ai_providers 表索引
CREATE INDEX IF NOT EXISTS idx_ai_providers_name ON ai_providers(provider_name);
CREATE INDEX IF NOT EXISTS idx_ai_providers_active ON ai_providers(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_providers_priority ON ai_providers(priority);

-- deployment_logs 表索引
CREATE INDEX IF NOT EXISTS idx_deployment_logs_deployment_id ON deployment_logs(deployment_id);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_mode ON deployment_logs(mode);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_status ON deployment_logs(status);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_start_time ON deployment_logs(start_time);

-- ========== 插入預設配置資料 ==========

-- 插入預設AI提供商配置 (使用虛擬hash，實際使用時需要更新)
INSERT OR IGNORE INTO ai_providers (provider_name, api_key_hash, base_url, is_active, priority, rate_limit_per_minute, cost_per_token) VALUES
('openai', 'PLACEHOLDER_HASH_OPENAI', 'https://api.openai.com/v1', FALSE, 1, 60, 0.000002),
('anthropic', 'PLACEHOLDER_HASH_ANTHROPIC', 'https://api.anthropic.com', FALSE, 2, 50, 0.000003),
('google', 'PLACEHOLDER_HASH_GOOGLE', 'https://generativelanguage.googleapis.com/v1', FALSE, 3, 40, 0.0000015);

-- ========== 驗證查詢 ==========

-- 驗證所有表都已創建
SELECT name, type FROM sqlite_master 
WHERE type='table' AND name IN (
    'sub_bots',
    'sub_bot_channels', 
    'ai_conversations',
    'ai_usage_quotas',
    'ai_providers',
    'deployment_logs'
)
ORDER BY name;

-- 驗證索引都已創建
SELECT name FROM sqlite_master 
WHERE type='index' AND (
    name LIKE 'idx_sub_bots%' OR
    name LIKE 'idx_sub_bot_channels%' OR 
    name LIKE 'idx_ai_%' OR
    name LIKE 'idx_deployment_logs%'
)
ORDER BY name;

-- 統計預設資料
SELECT 'ai_providers' as table_name, COUNT(*) as record_count FROM ai_providers
WHERE provider_name IN ('openai', 'anthropic', 'google');