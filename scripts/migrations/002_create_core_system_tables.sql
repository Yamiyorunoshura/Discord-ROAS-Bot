CREATE TABLE IF NOT EXISTS schema_migrations (
version TEXT PRIMARY KEY,
description TEXT NOT NULL,
filename TEXT NOT NULL,
checksum TEXT NOT NULL,
applied_at TIMESTAMP NOT NULL,
execution_time_ms INTEGER NOT NULL,
success INTEGER NOT NULL DEFAULT 1,
error_message TEXT,
CHECK (success IN (0, 1)),
CHECK (execution_time_ms >= 0)
);

CREATE INDEX IF NOT EXISTS idx_schema_migrations_version ON schema_migrations(version);

CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at ON schema_migrations(applied_at);

CREATE INDEX IF NOT EXISTS idx_schema_migrations_success ON schema_migrations(success);

CREATE TABLE IF NOT EXISTS system_config (
guild_id INTEGER NOT NULL,
config_key TEXT NOT NULL,
config_value TEXT,
config_type TEXT NOT NULL DEFAULT 'string',
description TEXT,
is_encrypted INTEGER NOT NULL DEFAULT 0,
created_at TIMESTAMP NOT NULL,
updated_at TIMESTAMP NOT NULL,
updated_by INTEGER,
PRIMARY KEY (guild_id, config_key),
CHECK (config_type IN ('string', 'number', 'boolean', 'json')),
CHECK (is_encrypted IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_system_config_guild_id ON system_config(guild_id);

CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(config_key);

CREATE INDEX IF NOT EXISTS idx_system_config_type ON system_config(config_type);

CREATE INDEX IF NOT EXISTS idx_system_config_updated_at ON system_config(updated_at);

CREATE TABLE IF NOT EXISTS system_logs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
level TEXT NOT NULL,
category TEXT NOT NULL,
message TEXT NOT NULL,
guild_id INTEGER,
user_id INTEGER,
correlation_id TEXT,
metadata TEXT,
created_at TIMESTAMP NOT NULL,
ip_address TEXT,
user_agent TEXT,
CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);

CREATE INDEX IF NOT EXISTS idx_system_logs_category ON system_logs(category);

CREATE INDEX IF NOT EXISTS idx_system_logs_guild_id ON system_logs(guild_id);

CREATE INDEX IF NOT EXISTS idx_system_logs_user_id ON system_logs(user_id);

CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_system_logs_correlation_id ON system_logs(correlation_id);

CREATE TABLE IF NOT EXISTS user_sessions (
session_id TEXT PRIMARY KEY,
user_id INTEGER NOT NULL,
guild_id INTEGER NOT NULL,
session_data TEXT,
created_at TIMESTAMP NOT NULL,
last_accessed_at TIMESTAMP NOT NULL,
expires_at TIMESTAMP NOT NULL,
is_active INTEGER NOT NULL DEFAULT 1,
ip_address TEXT,
user_agent TEXT,
CHECK (is_active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_user_sessions_guild_id ON user_sessions(guild_id);

CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);

CREATE INDEX IF NOT EXISTS idx_user_sessions_is_active ON user_sessions(is_active);

CREATE INDEX IF NOT EXISTS idx_user_sessions_last_accessed ON user_sessions(last_accessed_at);

CREATE TABLE IF NOT EXISTS permissions (
id INTEGER PRIMARY KEY AUTOINCREMENT,
permission_name TEXT NOT NULL,
description TEXT NOT NULL,
category TEXT NOT NULL,
is_system_permission INTEGER NOT NULL DEFAULT 0,
created_at TIMESTAMP NOT NULL,
CHECK (is_system_permission IN (0, 1)),
UNIQUE(permission_name)
);

CREATE INDEX IF NOT EXISTS idx_permissions_name ON permissions(permission_name);

CREATE INDEX IF NOT EXISTS idx_permissions_category ON permissions(category);

CREATE INDEX IF NOT EXISTS idx_permissions_system ON permissions(is_system_permission);

CREATE TABLE IF NOT EXISTS role_permissions (
id INTEGER PRIMARY KEY AUTOINCREMENT,
guild_id INTEGER NOT NULL,
role_id INTEGER NOT NULL,
permission_id INTEGER NOT NULL,
granted_by INTEGER,
granted_at TIMESTAMP NOT NULL,
expires_at TIMESTAMP,
is_active INTEGER NOT NULL DEFAULT 1,
FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
CHECK (is_active IN (0, 1)),
UNIQUE(guild_id, role_id, permission_id)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_guild_role ON role_permissions(guild_id, role_id);

CREATE INDEX IF NOT EXISTS idx_role_permissions_permission ON role_permissions(permission_id);

CREATE INDEX IF NOT EXISTS idx_role_permissions_active ON role_permissions(is_active);

CREATE INDEX IF NOT EXISTS idx_role_permissions_expires ON role_permissions(expires_at);

CREATE TABLE IF NOT EXISTS system_statistics (
id INTEGER PRIMARY KEY AUTOINCREMENT,
guild_id INTEGER NOT NULL,
metric_name TEXT NOT NULL,
metric_value REAL NOT NULL,
metric_type TEXT NOT NULL,
tags TEXT,
recorded_at TIMESTAMP NOT NULL,
CHECK (metric_type IN ('counter', 'gauge', 'histogram', 'summary'))
);

CREATE INDEX IF NOT EXISTS idx_system_statistics_guild_id ON system_statistics(guild_id);

CREATE INDEX IF NOT EXISTS idx_system_statistics_metric ON system_statistics(metric_name);

CREATE INDEX IF NOT EXISTS idx_system_statistics_recorded_at ON system_statistics(recorded_at);

CREATE INDEX IF NOT EXISTS idx_system_statistics_guild_metric ON system_statistics(guild_id, metric_name);

INSERT OR IGNORE INTO permissions (permission_name, description, category, is_system_permission, created_at) VALUES
('system.admin', '系統管理員權限', 'system', 1, datetime('now')),
('system.config', '系統配置管理權限', 'system', 1, datetime('now')),
('economy.admin', '經濟系統管理權限', 'economy', 0, datetime('now')),
('economy.transfer', '經濟轉帳權限', 'economy', 0, datetime('now')),
('government.admin', '政府系統管理權限', 'government', 0, datetime('now')),
('government.member', '政府系統成員權限', 'government', 0, datetime('now')),
('achievement.admin', '成就系統管理權限', 'achievement', 0, datetime('now')),
('achievement.view', '成就系統查看權限', 'achievement', 0, datetime('now'));

SELECT name FROM sqlite_master
WHERE type='table' AND name IN (
'schema_migrations',
'system_config',
'system_logs',
'user_sessions',
'permissions',
'role_permissions',
'system_statistics'
);

SELECT name FROM sqlite_master
WHERE type='index' AND name LIKE 'idx_system%'
OR name LIKE 'idx_schema%'
OR name LIKE 'idx_permissions%'
OR name LIKE 'idx_role_permissions%'
OR name LIKE 'idx_user_sessions%';

SELECT count(*) as permission_count FROM permissions WHERE is_system_permission = 1;

SELECT 'economy_compatibility' as check_name,
CASE WHEN EXISTS (SELECT 1 FROM sqlite_master WHERE name = 'economy_accounts')
THEN 'PASS'
ELSE 'FAIL'
END as result;