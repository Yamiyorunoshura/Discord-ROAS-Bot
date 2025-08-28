-- ROAS Discord Bot v2.4.4 核心資料表回滾遷移
-- Task ID: 1 - 核心架構和基礎設施建置
-- 
-- 這個回滾腳本移除 v2.4.4 版本新增的所有資料表和索引
-- 警告：執行此腳本將永久刪除所有子機器人、AI對話和部署記錄資料
--
-- 遷移版本: v2_4_4_core_tables_rollback
-- 創建日期: 2025-08-25

-- ========== 移除索引 ==========

-- 移除 deployment_logs 索引
DROP INDEX IF EXISTS idx_deployment_logs_deployment_id;
DROP INDEX IF EXISTS idx_deployment_logs_mode;
DROP INDEX IF EXISTS idx_deployment_logs_status;
DROP INDEX IF EXISTS idx_deployment_logs_start_time;

-- 移除 ai_providers 索引
DROP INDEX IF EXISTS idx_ai_providers_name;
DROP INDEX IF EXISTS idx_ai_providers_active;
DROP INDEX IF EXISTS idx_ai_providers_priority;

-- 移除 ai_usage_quotas 索引
DROP INDEX IF EXISTS idx_ai_usage_quotas_user_id;
DROP INDEX IF EXISTS idx_ai_usage_quotas_daily_reset;

-- 移除 ai_conversations 索引
DROP INDEX IF EXISTS idx_ai_conversations_user_id;
DROP INDEX IF EXISTS idx_ai_conversations_sub_bot_id;
DROP INDEX IF EXISTS idx_ai_conversations_provider;
DROP INDEX IF EXISTS idx_ai_conversations_created_at;

-- 移除 sub_bot_channels 索引
DROP INDEX IF EXISTS idx_sub_bot_channels_sub_bot_id;
DROP INDEX IF EXISTS idx_sub_bot_channels_channel_id;

-- 移除 sub_bots 索引
DROP INDEX IF EXISTS idx_sub_bots_bot_id;
DROP INDEX IF EXISTS idx_sub_bots_status;
DROP INDEX IF EXISTS idx_sub_bots_ai_enabled;

-- ========== 移除資料表 ==========

-- 注意：由於外鍵約束，需要按照正確順序刪除表格

-- 移除部署系統資料表
DROP TABLE IF EXISTS deployment_logs;

-- 移除 AI 系統資料表
DROP TABLE IF EXISTS ai_conversations; -- 必須在 sub_bots 之前刪除，因為有外鍵約束
DROP TABLE IF EXISTS ai_usage_quotas;
DROP TABLE IF EXISTS ai_providers;

-- 移除子機器人系統資料表
DROP TABLE IF EXISTS sub_bot_channels; -- 必須在 sub_bots 之前刪除，因為有外鍵約束
DROP TABLE IF EXISTS sub_bots;

-- ========== 驗證回滾完成 ==========

-- 驗證所有相關表格已被移除
SELECT 'Rollback verification' as verification_step;
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN 'SUCCESS: All v2.4.4 core tables have been removed'
        ELSE 'ERROR: Some v2.4.4 core tables still exist: ' || GROUP_CONCAT(name, ', ')
    END as result
FROM sqlite_master 
WHERE type='table' 
AND name IN ('sub_bots', 'sub_bot_channels', 'ai_conversations', 'ai_usage_quotas', 'ai_providers', 'deployment_logs');

-- 驗證所有相關索引已被移除
SELECT 
    CASE 
        WHEN COUNT(*) = 0 THEN 'SUCCESS: All v2.4.4 core indexes have been removed'
        ELSE 'ERROR: Some v2.4.4 core indexes still exist: ' || GROUP_CONCAT(name, ', ')
    END as index_result
FROM sqlite_master 
WHERE type='index' 
AND name LIKE 'idx_%' 
AND name LIKE '%sub_bot%' OR name LIKE '%ai_%' OR name LIKE '%deployment%';