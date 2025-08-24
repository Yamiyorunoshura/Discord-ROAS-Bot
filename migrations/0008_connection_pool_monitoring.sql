-- Migration: 0008_connection_pool_monitoring.sql
-- Task ID: T2 - Connection Pool Monitoring Infrastructure
-- Created: 2025-08-24
-- Purpose: Create monitoring tables and infrastructure for connection pool management

-- Connection Pool Statistics Table
-- Stores real-time statistics about connection pool usage
CREATE TABLE IF NOT EXISTS connection_pool_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Pool Configuration
    pool_name TEXT NOT NULL DEFAULT 'default',
    max_pool_size INTEGER NOT NULL DEFAULT 20,
    
    -- Current State
    active_connections INTEGER NOT NULL DEFAULT 0,
    idle_connections INTEGER NOT NULL DEFAULT 0,
    pending_connections INTEGER NOT NULL DEFAULT 0,
    
    -- Performance Metrics
    average_wait_time_ms REAL DEFAULT 0.0,
    max_wait_time_ms REAL DEFAULT 0.0,
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    
    -- Resource Usage
    memory_usage_bytes INTEGER DEFAULT 0,
    cpu_usage_percent REAL DEFAULT 0.0,
    
    -- Health Status
    pool_health_score REAL DEFAULT 1.0,
    last_optimization_timestamp TIMESTAMP,
    
    CONSTRAINT positive_connections CHECK (
        active_connections >= 0 AND 
        idle_connections >= 0 AND 
        pending_connections >= 0
    ),
    CONSTRAINT valid_health_score CHECK (
        pool_health_score >= 0.0 AND pool_health_score <= 1.0
    )
);

-- Connection Pool Events Table
-- Logs significant events in connection pool lifecycle
CREATE TABLE IF NOT EXISTS connection_pool_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Event Information
    event_type TEXT NOT NULL,
    event_level TEXT NOT NULL DEFAULT 'INFO',
    pool_name TEXT NOT NULL DEFAULT 'default',
    
    -- Event Details
    event_message TEXT NOT NULL,
    event_data TEXT, -- JSON formatted additional data
    
    -- Context
    thread_id TEXT,
    connection_id TEXT,
    session_id TEXT,
    
    -- Performance Impact
    duration_ms REAL,
    error_code TEXT,
    
    CONSTRAINT valid_event_level CHECK (
        event_level IN ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
    ),
    CONSTRAINT valid_event_type CHECK (
        event_type IN (
            'pool_created', 'pool_destroyed', 'pool_resized',
            'connection_created', 'connection_destroyed', 'connection_reused',
            'connection_timeout', 'connection_error', 'connection_recovery',
            'performance_alert', 'health_check', 'optimization_triggered'
        )
    )
);

-- Connection Pool Configuration Table
-- Stores dynamic configuration for connection pools
CREATE TABLE IF NOT EXISTS connection_pool_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_name TEXT UNIQUE NOT NULL DEFAULT 'default',
    
    -- Pool Sizing
    min_pool_size INTEGER NOT NULL DEFAULT 5,
    max_pool_size INTEGER NOT NULL DEFAULT 20,
    optimal_pool_size INTEGER NOT NULL DEFAULT 10,
    
    -- Timeout Configuration
    connection_timeout_ms INTEGER NOT NULL DEFAULT 30000,
    idle_timeout_ms INTEGER NOT NULL DEFAULT 300000,  -- 5 minutes
    max_lifetime_ms INTEGER NOT NULL DEFAULT 1800000, -- 30 minutes
    
    -- Health Check Configuration
    health_check_interval_ms INTEGER NOT NULL DEFAULT 60000, -- 1 minute
    health_check_timeout_ms INTEGER NOT NULL DEFAULT 5000,   -- 5 seconds
    
    -- Performance Tuning
    auto_scaling_enabled BOOLEAN NOT NULL DEFAULT 1,
    scaling_factor REAL NOT NULL DEFAULT 1.2,
    performance_threshold REAL NOT NULL DEFAULT 0.8,
    
    -- Monitoring
    monitoring_enabled BOOLEAN NOT NULL DEFAULT 1,
    detailed_logging BOOLEAN NOT NULL DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT positive_pool_sizes CHECK (
        min_pool_size > 0 AND 
        max_pool_size >= min_pool_size AND
        optimal_pool_size >= min_pool_size AND
        optimal_pool_size <= max_pool_size
    ),
    CONSTRAINT positive_timeouts CHECK (
        connection_timeout_ms > 0 AND
        idle_timeout_ms > 0 AND
        max_lifetime_ms > idle_timeout_ms AND
        health_check_interval_ms > 0 AND
        health_check_timeout_ms > 0
    )
);

-- Insert default configuration
INSERT OR REPLACE INTO connection_pool_config (
    pool_name, min_pool_size, max_pool_size, optimal_pool_size,
    connection_timeout_ms, idle_timeout_ms, max_lifetime_ms,
    health_check_interval_ms, health_check_timeout_ms,
    auto_scaling_enabled, scaling_factor, performance_threshold,
    monitoring_enabled, detailed_logging
) VALUES (
    'default', 5, 20, 10,
    30000, 300000, 1800000,
    60000, 5000,
    1, 1.2, 0.8,
    1, 0
);

-- Performance Monitoring Views
CREATE VIEW IF NOT EXISTS connection_pool_performance AS
SELECT 
    pool_name,
    timestamp,
    active_connections,
    (active_connections * 1.0 / max_pool_size) AS utilization_ratio,
    average_wait_time_ms,
    (successful_requests * 1.0 / NULLIF(total_requests, 0)) AS success_rate,
    pool_health_score,
    CASE 
        WHEN pool_health_score >= 0.9 THEN 'Excellent'
        WHEN pool_health_score >= 0.7 THEN 'Good'
        WHEN pool_health_score >= 0.5 THEN 'Fair'
        ELSE 'Poor'
    END AS health_status
FROM connection_pool_stats
ORDER BY timestamp DESC;

-- Recent Events View
CREATE VIEW IF NOT EXISTS connection_pool_recent_events AS
SELECT 
    timestamp,
    event_type,
    event_level,
    pool_name,
    event_message,
    duration_ms,
    error_code
FROM connection_pool_events
WHERE timestamp >= datetime('now', '-1 hour')
ORDER BY timestamp DESC
LIMIT 100;

-- Indices for Performance
CREATE INDEX IF NOT EXISTS idx_pool_stats_timestamp ON connection_pool_stats(timestamp);
CREATE INDEX IF NOT EXISTS idx_pool_stats_pool_name ON connection_pool_stats(pool_name);
CREATE INDEX IF NOT EXISTS idx_pool_events_timestamp ON connection_pool_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_pool_events_type ON connection_pool_events(event_type);
CREATE INDEX IF NOT EXISTS idx_pool_events_level ON connection_pool_events(event_level);
CREATE INDEX IF NOT EXISTS idx_pool_config_name ON connection_pool_config(pool_name);

-- Triggers for automated maintenance
CREATE TRIGGER IF NOT EXISTS update_pool_config_timestamp
    AFTER UPDATE ON connection_pool_config
    BEGIN
        UPDATE connection_pool_config 
        SET updated_at = CURRENT_TIMESTAMP 
        WHERE id = NEW.id;
    END;

-- Clean up old statistics (keep last 7 days)
CREATE TRIGGER IF NOT EXISTS cleanup_old_pool_stats
    AFTER INSERT ON connection_pool_stats
    BEGIN
        DELETE FROM connection_pool_stats 
        WHERE timestamp < datetime('now', '-7 days');
    END;

-- Clean up old events (keep last 24 hours)
CREATE TRIGGER IF NOT EXISTS cleanup_old_pool_events
    AFTER INSERT ON connection_pool_events
    BEGIN
        DELETE FROM connection_pool_events 
        WHERE timestamp < datetime('now', '-1 day')
        AND event_level NOT IN ('ERROR', 'CRITICAL');
    END;

-- Initial health check event
INSERT INTO connection_pool_events (
    event_type, event_level, pool_name, event_message
) VALUES (
    'pool_created', 'INFO', 'default', 'Connection pool monitoring infrastructure initialized'
);