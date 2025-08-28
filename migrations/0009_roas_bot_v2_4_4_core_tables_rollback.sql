-- ROAS Bot v2.4.4 Core Tables Rollback Migration
-- Task ID: 1 - 核心架構和基礎設施建置
-- 回滾v2.4.4新功能的核心資料表
-- Author: Elena (API設計專家)
-- Created: 2025-08-25

-- ========== 刪除索引 ==========

-- sub_bots 表索引
DROP INDEX IF EXISTS idx_sub_bots_bot_id;
DROP INDEX IF EXISTS idx_sub_bots_status;
DROP INDEX IF EXISTS idx_sub_bots_created_at;
DROP INDEX IF EXISTS idx_sub_bots_ai_enabled;

-- sub_bot_channels 表索引
DROP INDEX IF EXISTS idx_sub_bot_channels_sub_bot_id;
DROP INDEX IF EXISTS idx_sub_bot_channels_channel_id;
DROP INDEX IF EXISTS idx_sub_bot_channels_type;

-- ai_conversations 表索引
DROP INDEX IF EXISTS idx_ai_conversations_user_id;
DROP INDEX IF EXISTS idx_ai_conversations_sub_bot_id;
DROP INDEX IF EXISTS idx_ai_conversations_provider;
DROP INDEX IF EXISTS idx_ai_conversations_created_at;
DROP INDEX IF EXISTS idx_ai_conversations_user_date;

-- ai_usage_quotas 表索引
DROP INDEX IF EXISTS idx_ai_usage_quotas_user_id;
DROP INDEX IF EXISTS idx_ai_usage_quotas_daily_reset;
DROP INDEX IF EXISTS idx_ai_usage_quotas_weekly_reset;
DROP INDEX IF EXISTS idx_ai_usage_quotas_monthly_reset;

-- ai_providers 表索引
DROP INDEX IF EXISTS idx_ai_providers_name;
DROP INDEX IF EXISTS idx_ai_providers_active;
DROP INDEX IF EXISTS idx_ai_providers_priority;

-- deployment_logs 表索引
DROP INDEX IF EXISTS idx_deployment_logs_deployment_id;
DROP INDEX IF EXISTS idx_deployment_logs_mode;
DROP INDEX IF EXISTS idx_deployment_logs_status;
DROP INDEX IF EXISTS idx_deployment_logs_start_time;

-- ========== 刪除資料表 (按依賴關係的反向順序) ==========

-- 刪除有外鍵依賴的表
DROP TABLE IF EXISTS ai_conversations;      -- 依賴 sub_bots
DROP TABLE IF EXISTS sub_bot_channels;      -- 依賴 sub_bots

-- 刪除獨立的表
DROP TABLE IF EXISTS ai_usage_quotas;
DROP TABLE IF EXISTS ai_providers;
DROP TABLE IF EXISTS deployment_logs;

-- 最後刪除主表
DROP TABLE IF EXISTS sub_bots;

-- ========== 驗證清理完成 ==========

-- 驗證所有相關表都已刪除
SELECT name, type FROM sqlite_master 
WHERE type='table' AND name IN (
    'sub_bots',
    'sub_bot_channels', 
    'ai_conversations',
    'ai_usage_quotas',
    'ai_providers',
    'deployment_logs'
);

-- 驗證所有相關索引都已刪除
SELECT name FROM sqlite_master 
WHERE type='index' AND (
    name LIKE 'idx_sub_bots%' OR
    name LIKE 'idx_sub_bot_channels%' OR 
    name LIKE 'idx_ai_%' OR
    name LIKE 'idx_deployment_logs%'
);

-- 如果上述查詢返回空結果，則表示回滾成功