-- =================================================================
-- ROAS Discord Bot v2.4.4 核心架構資料庫遷移
-- Migration ID: 0009
-- Description: 建立支援子機器人、AI系統和部署管理的核心資料表
-- Created: 2025-08-25
-- =================================================================

-- 子機器人配置表
-- 用於存儲子機器人的基本配置和運行狀態
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

-- 子機器人頻道關聯表
-- 管理子機器人與頻道的多對多關係
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

-- AI 對話記錄表
-- 記錄所有AI對話的詳細信息，用於統計和審計
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

-- AI 使用配額表
-- 管理用戶的AI使用限制和統計
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

-- AI 提供商配置表
-- 存儲AI服務提供商的配置信息
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

-- 部署日誌表
-- 記錄部署過程的詳細日誌
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

-- =================================================================
-- 索引建立 - 優化查詢效能
-- =================================================================

-- sub_bots 索引
CREATE INDEX IF NOT EXISTS idx_sub_bots_bot_id ON sub_bots(bot_id);
CREATE INDEX IF NOT EXISTS idx_sub_bots_status ON sub_bots(status);
CREATE INDEX IF NOT EXISTS idx_sub_bots_ai_enabled ON sub_bots(ai_enabled);
CREATE INDEX IF NOT EXISTS idx_sub_bots_created_at ON sub_bots(created_at);

-- sub_bot_channels 索引
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_sub_bot_id ON sub_bot_channels(sub_bot_id);
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_channel_id ON sub_bot_channels(channel_id);
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_type ON sub_bot_channels(channel_type);

-- ai_conversations 索引
CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_id ON ai_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_sub_bot_id ON ai_conversations(sub_bot_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_provider ON ai_conversations(provider);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_created_at ON ai_conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_date ON ai_conversations(user_id, created_at);

-- ai_usage_quotas 索引
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_user_id ON ai_usage_quotas(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_last_reset_daily ON ai_usage_quotas(last_reset_daily);
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_last_reset_weekly ON ai_usage_quotas(last_reset_weekly);
CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_last_reset_monthly ON ai_usage_quotas(last_reset_monthly);

-- ai_providers 索引
CREATE INDEX IF NOT EXISTS idx_ai_providers_name ON ai_providers(provider_name);
CREATE INDEX IF NOT EXISTS idx_ai_providers_active ON ai_providers(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_providers_priority ON ai_providers(priority);

-- deployment_logs 索引
CREATE INDEX IF NOT EXISTS idx_deployment_logs_deployment_id ON deployment_logs(deployment_id);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_status ON deployment_logs(status);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_mode ON deployment_logs(mode);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_created_at ON deployment_logs(created_at);

-- =================================================================
-- 觸發器建立 - 自動維護數據一致性
-- =================================================================

-- 子機器人表更新時間觸發器
CREATE TRIGGER IF NOT EXISTS trg_sub_bots_updated_at 
    AFTER UPDATE ON sub_bots
BEGIN
    UPDATE sub_bots SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- AI使用配額表更新時間觸發器
CREATE TRIGGER IF NOT EXISTS trg_ai_usage_quotas_updated_at 
    AFTER UPDATE ON ai_usage_quotas
BEGIN
    UPDATE ai_usage_quotas SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- AI提供商配置表更新時間觸發器
CREATE TRIGGER IF NOT EXISTS trg_ai_providers_updated_at 
    AFTER UPDATE ON ai_providers
BEGIN
    UPDATE ai_providers SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 部署結束時自動計算持續時間觸發器
CREATE TRIGGER IF NOT EXISTS trg_deployment_logs_duration 
    AFTER UPDATE OF end_time ON deployment_logs
    WHEN NEW.end_time IS NOT NULL AND OLD.end_time IS NULL
BEGIN
    UPDATE deployment_logs 
    SET duration_seconds = CAST((julianday(NEW.end_time) - julianday(NEW.start_time)) * 86400 AS INTEGER)
    WHERE id = NEW.id;
END;

-- =================================================================
-- 初始資料插入
-- =================================================================

-- 插入預設AI提供商配置（佔位符，實際API Key需要在配置時設定）
INSERT OR IGNORE INTO ai_providers (provider_name, api_key_hash, base_url, priority, rate_limit_per_minute, cost_per_token) VALUES
    ('openai', 'placeholder_hash_will_be_replaced', 'https://api.openai.com/v1', 1, 60, 0.000002),
    ('anthropic', 'placeholder_hash_will_be_replaced', 'https://api.anthropic.com', 2, 50, 0.000003),
    ('google', 'placeholder_hash_will_be_replaced', 'https://generativelanguage.googleapis.com', 3, 60, 0.000001);

-- =================================================================
-- 資料完整性檢查
-- =================================================================

-- 檢查所有必要的表是否已建立
-- 這些查詢會在遷移後執行以驗證表的存在性
-- SELECT name FROM sqlite_master WHERE type='table' AND name IN ('sub_bots', 'sub_bot_channels', 'ai_conversations', 'ai_usage_quotas', 'ai_providers', 'deployment_logs');