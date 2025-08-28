-- =================================================================
-- ROAS Discord Bot v2.4.4 核心架構資料庫回滾腳本
-- Migration ID: 0009_rollback
-- Description: 回滾v2.4.4核心架構的所有資料表和相關物件
-- Created: 2025-08-25
-- =================================================================

-- 安全檢查：確認這是有意的回滾操作
-- 本腳本將完全移除v2.4.4新增的所有資料庫物件
-- 執行前請確保已備份重要資料

-- =================================================================
-- 刪除觸發器
-- =================================================================

DROP TRIGGER IF EXISTS trg_deployment_logs_duration;
DROP TRIGGER IF EXISTS trg_ai_providers_updated_at;
DROP TRIGGER IF EXISTS trg_ai_usage_quotas_updated_at;
DROP TRIGGER IF EXISTS trg_sub_bots_updated_at;

-- =================================================================
-- 刪除索引
-- =================================================================

-- deployment_logs 索引
DROP INDEX IF EXISTS idx_deployment_logs_created_at;
DROP INDEX IF EXISTS idx_deployment_logs_mode;
DROP INDEX IF EXISTS idx_deployment_logs_status;
DROP INDEX IF EXISTS idx_deployment_logs_deployment_id;

-- ai_providers 索引
DROP INDEX IF EXISTS idx_ai_providers_priority;
DROP INDEX IF EXISTS idx_ai_providers_active;
DROP INDEX IF EXISTS idx_ai_providers_name;

-- ai_usage_quotas 索引
DROP INDEX IF EXISTS idx_ai_usage_quotas_last_reset_monthly;
DROP INDEX IF EXISTS idx_ai_usage_quotas_last_reset_weekly;
DROP INDEX IF EXISTS idx_ai_usage_quotas_last_reset_daily;
DROP INDEX IF EXISTS idx_ai_usage_quotas_user_id;

-- ai_conversations 索引
DROP INDEX IF EXISTS idx_ai_conversations_user_date;
DROP INDEX IF EXISTS idx_ai_conversations_created_at;
DROP INDEX IF EXISTS idx_ai_conversations_provider;
DROP INDEX IF EXISTS idx_ai_conversations_sub_bot_id;
DROP INDEX IF EXISTS idx_ai_conversations_user_id;

-- sub_bot_channels 索引
DROP INDEX IF EXISTS idx_sub_bot_channels_type;
DROP INDEX IF EXISTS idx_sub_bot_channels_channel_id;
DROP INDEX IF EXISTS idx_sub_bot_channels_sub_bot_id;

-- sub_bots 索引
DROP INDEX IF EXISTS idx_sub_bots_created_at;
DROP INDEX IF EXISTS idx_sub_bots_ai_enabled;
DROP INDEX IF EXISTS idx_sub_bots_status;
DROP INDEX IF EXISTS idx_sub_bots_bot_id;

-- =================================================================
-- 刪除資料表（按依賴關係順序）
-- =================================================================

-- 刪除有外鍵依賴的表
DROP TABLE IF EXISTS ai_conversations;       -- 依賴 sub_bots
DROP TABLE IF EXISTS sub_bot_channels;       -- 依賴 sub_bots

-- 刪除獨立表
DROP TABLE IF EXISTS deployment_logs;
DROP TABLE IF EXISTS ai_usage_quotas;
DROP TABLE IF EXISTS ai_providers;
DROP TABLE IF EXISTS sub_bots;              -- 最後刪除被依賴的表

-- =================================================================
-- 清理遷移記錄
-- =================================================================

-- 從遷移歷史中移除此版本記錄
DELETE FROM schema_migrations WHERE version = '0009_v2_4_4_core_tables';

-- =================================================================
-- 回滾驗證
-- =================================================================

-- 驗證所有v2.4.4相關表已被移除
-- 執行後應該返回0行結果，確認回滾成功
-- SELECT name FROM sqlite_master WHERE type='table' AND name IN ('sub_bots', 'sub_bot_channels', 'ai_conversations', 'ai_usage_quotas', 'ai_providers', 'deployment_logs');

-- 回滾完成標記
-- PRAGMA user_version; -- 可用於檢查當前版本