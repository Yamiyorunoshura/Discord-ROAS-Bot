-- 部署系統資料庫支援
-- Task ID: 2 - 自動化部署和啟動系統開發
-- 
-- 擴展現有資料庫架構，添加部署日誌和監控相關表格
-- 支援部署歷史、環境資訊、性能指標等資料儲存

-- 部署日誌表
CREATE TABLE IF NOT EXISTS deployment_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id VARCHAR(50) UNIQUE NOT NULL,
    mode VARCHAR(20) NOT NULL, -- docker, uv_python, fallback
    status VARCHAR(20) NOT NULL, -- pending, installing, configuring, starting, running, failed, degraded, stopped
    message TEXT,
    environment_info TEXT, -- JSON 格式的環境資訊
    deployment_details TEXT, -- JSON 格式的部署詳細資訊
    error_logs TEXT, -- JSON 格式的錯誤日誌陣列
    performance_metrics TEXT, -- JSON格式：安裝時間、啟動時間等
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    duration_seconds INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 環境檢測歷史表
CREATE TABLE IF NOT EXISTS environment_detection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id VARCHAR(50) UNIQUE NOT NULL,
    platform VARCHAR(20) NOT NULL, -- linux, macos, windows, unknown
    architecture VARCHAR(50),
    python_version VARCHAR(20),
    docker_available BOOLEAN DEFAULT FALSE,
    docker_version VARCHAR(50),
    uv_available BOOLEAN DEFAULT FALSE,
    uv_version VARCHAR(50),
    package_manager VARCHAR(20),
    sudo_available BOOLEAN DEFAULT FALSE,
    permissions TEXT, -- JSON 格式的權限資訊
    environment_variables TEXT, -- JSON 格式的環境變數
    recommended_mode VARCHAR(20), -- 推薦的部署模式
    detection_duration_ms INTEGER, -- 檢測耗時（毫秒）
    detected_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 部署管理器狀態表
CREATE TABLE IF NOT EXISTS deployment_manager_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_type VARCHAR(20) NOT NULL, -- docker, uv_python, fallback
    deployment_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- healthy, unhealthy, degraded, error
    health_check_result TEXT, -- JSON 格式的健康檢查結果
    last_health_check DATETIME,
    services_status TEXT, -- JSON 格式的服務狀態
    resource_usage TEXT, -- JSON 格式的資源使用情況
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 外鍵約束
    FOREIGN KEY (deployment_id) REFERENCES deployment_logs (deployment_id)
);

-- 部署性能指標表
CREATE TABLE IF NOT EXISTS deployment_performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id VARCHAR(50) NOT NULL,
    metric_name VARCHAR(50) NOT NULL, -- dependency_install_time, service_start_time, health_check_time, etc.
    metric_value REAL NOT NULL,
    metric_unit VARCHAR(20) NOT NULL, -- seconds, milliseconds, bytes, etc.
    measurement_time DATETIME NOT NULL,
    additional_data TEXT, -- JSON 格式的額外資料
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 外鍵約束
    FOREIGN KEY (deployment_id) REFERENCES deployment_logs (deployment_id),
    
    -- 索引
    INDEX idx_deployment_metrics_deployment_id (deployment_id),
    INDEX idx_deployment_metrics_name (metric_name),
    INDEX idx_deployment_metrics_time (measurement_time)
);

-- 部署事件日誌表
CREATE TABLE IF NOT EXISTS deployment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id VARCHAR(50) UNIQUE NOT NULL,
    deployment_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(30) NOT NULL, -- status_change, error_occurred, service_started, service_stopped, etc.
    event_level VARCHAR(10) NOT NULL, -- info, warning, error, critical
    event_message TEXT NOT NULL,
    event_details TEXT, -- JSON 格式的事件詳細資料
    source_component VARCHAR(50), -- EnvironmentDetector, DockerManager, UVManager, Orchestrator
    occurred_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 外鍵約束
    FOREIGN KEY (deployment_id) REFERENCES deployment_logs (deployment_id),
    
    -- 索引
    INDEX idx_deployment_events_deployment_id (deployment_id),
    INDEX idx_deployment_events_type (event_type),
    INDEX idx_deployment_events_level (event_level),
    INDEX idx_deployment_events_time (occurred_at)
);

-- 部署配置快照表
CREATE TABLE IF NOT EXISTS deployment_config_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id VARCHAR(50) NOT NULL,
    config_type VARCHAR(30) NOT NULL, -- app_config, docker_compose, environment_vars, etc.
    config_content TEXT NOT NULL, -- JSON 或 YAML 格式的配置內容
    config_hash VARCHAR(64) NOT NULL, -- 配置內容的 SHA-256 哈希值
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 外鍵約束
    FOREIGN KEY (deployment_id) REFERENCES deployment_logs (deployment_id),
    
    -- 索引
    INDEX idx_deployment_config_deployment_id (deployment_id),
    INDEX idx_deployment_config_type (config_type),
    INDEX idx_deployment_config_hash (config_hash)
);

-- 部署統計視圖
CREATE VIEW IF NOT EXISTS deployment_statistics AS
SELECT 
    mode,
    COUNT(*) as total_deployments,
    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as successful_deployments,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_deployments,
    ROUND(AVG(duration_seconds), 2) as avg_duration_seconds,
    MIN(start_time) as first_deployment,
    MAX(start_time) as last_deployment,
    ROUND(
        (SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 2
    ) as success_rate_percent
FROM deployment_logs 
GROUP BY mode;

-- 環境統計視圖
CREATE VIEW IF NOT EXISTS environment_statistics AS
SELECT 
    platform,
    COUNT(*) as detection_count,
    SUM(CASE WHEN docker_available = 1 THEN 1 ELSE 0 END) as docker_available_count,
    SUM(CASE WHEN uv_available = 1 THEN 1 ELSE 0 END) as uv_available_count,
    recommended_mode,
    COUNT(recommended_mode) as recommended_count,
    ROUND(AVG(detection_duration_ms), 2) as avg_detection_time_ms,
    MAX(detected_at) as last_detection
FROM environment_detection_history 
GROUP BY platform, recommended_mode;

-- 最近部署狀態視圖
CREATE VIEW IF NOT EXISTS recent_deployments AS
SELECT 
    dl.deployment_id,
    dl.mode,
    dl.status,
    dl.message,
    dl.start_time,
    dl.end_time,
    dl.duration_seconds,
    edh.platform,
    edh.docker_available,
    edh.uv_available,
    COUNT(de.id) as event_count,
    COUNT(CASE WHEN de.event_level = 'error' THEN 1 END) as error_count,
    COUNT(CASE WHEN de.event_level = 'warning' THEN 1 END) as warning_count
FROM deployment_logs dl
LEFT JOIN environment_detection_history edh ON DATE(dl.start_time) = DATE(edh.detected_at)
LEFT JOIN deployment_events de ON dl.deployment_id = de.deployment_id
GROUP BY dl.deployment_id, dl.mode, dl.status, dl.message, dl.start_time, dl.end_time, dl.duration_seconds, edh.platform, edh.docker_available, edh.uv_available
ORDER BY dl.start_time DESC
LIMIT 50;

-- 創建觸發器：自動更新 updated_at 欄位
CREATE TRIGGER IF NOT EXISTS update_deployment_logs_timestamp 
    AFTER UPDATE ON deployment_logs
    FOR EACH ROW 
BEGIN
    UPDATE deployment_logs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_deployment_manager_status_timestamp 
    AFTER UPDATE ON deployment_manager_status
    FOR EACH ROW 
BEGIN
    UPDATE deployment_manager_status SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 清理舊資料的程序（可透過定期任務執行）
-- 刪除超過 30 天的部署日誌
-- DELETE FROM deployment_logs WHERE created_at < datetime('now', '-30 days');

-- 刪除超過 7 天的環境檢測歷史（保留每日最新一筆）
-- DELETE FROM environment_detection_history 
-- WHERE id NOT IN (
--     SELECT MAX(id) 
--     FROM environment_detection_history 
--     GROUP BY DATE(detected_at), platform
-- ) AND created_at < datetime('now', '-7 days');

-- 刪除超過 7 天的部署事件
-- DELETE FROM deployment_events WHERE created_at < datetime('now', '-7 days');

-- 插入初始示例資料（可選）
-- INSERT INTO deployment_logs (deployment_id, mode, status, message, start_time, end_time, duration_seconds)
-- VALUES ('deploy_001', 'docker', 'running', 'Docker deployment successful', datetime('now'), datetime('now'), 180);