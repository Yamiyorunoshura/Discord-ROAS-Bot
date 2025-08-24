-- Migration Rollback: 0008_connection_pool_monitoring_rollback.sql
-- Task ID: T2 - Connection Pool Monitoring Infrastructure
-- Created: 2025-08-24
-- Purpose: Rollback connection pool monitoring tables and infrastructure

-- Drop triggers first (they depend on tables)
DROP TRIGGER IF EXISTS cleanup_old_pool_events;
DROP TRIGGER IF EXISTS cleanup_old_pool_stats;
DROP TRIGGER IF EXISTS update_pool_config_timestamp;

-- Drop indices
DROP INDEX IF EXISTS idx_pool_config_name;
DROP INDEX IF EXISTS idx_pool_events_level;
DROP INDEX IF EXISTS idx_pool_events_type;
DROP INDEX IF EXISTS idx_pool_events_timestamp;
DROP INDEX IF EXISTS idx_pool_stats_pool_name;
DROP INDEX IF EXISTS idx_pool_stats_timestamp;

-- Drop views
DROP VIEW IF EXISTS connection_pool_recent_events;
DROP VIEW IF EXISTS connection_pool_performance;

-- Drop tables in reverse order of dependencies
DROP TABLE IF EXISTS connection_pool_config;
DROP TABLE IF EXISTS connection_pool_events;
DROP TABLE IF EXISTS connection_pool_stats;