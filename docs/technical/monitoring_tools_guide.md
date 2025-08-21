# 監控維護工具使用指南
# Task ID: 11 - 建立文件和部署準備 - F11-4: 監控維護工具

## 概覽

本系統提供完整的監控和維護工具集，幫助管理員監控Discord機器人的健康狀態、效能指標，並執行自動化維護任務。

## 工具架構

### 核心組件
- **MonitoringService**: 監控服務核心，提供健康檢查、效能監控、自動維護功能
- **健康檢查器**: 監控系統各組件的健康狀態
- **效能收集器**: 收集系統效能指標
- **維護任務執行器**: 執行自動化維護任務
- **警報系統**: 處理和發送系統警報

### 命令行工具
1. **monitor.py** - 監控工具統一入口
2. **health_check.py** - 健康檢查工具
3. **performance_monitor.py** - 效能監控工具
4. **maintenance.py** - 維護管理工具
5. **dashboard.py** - 監控儀表板工具

## 快速開始

### 統一入口使用

```bash
# 顯示幫助
python scripts/monitor.py help

# 快速健康檢查
python scripts/monitor.py quick-check

# 系統狀態概覽
python scripts/monitor.py status

# 緊急維護預覽
python scripts/monitor.py emergency
```

### 健康檢查工具

#### 基本用法
```bash
# 完整系統健康檢查
python scripts/monitor.py health check

# JSON格式輸出
python scripts/monitor.py health check --format json

# 檢查特定組件
python scripts/monitor.py health component database

# 查看健康歷史
python scripts/monitor.py health history --hours 24
```

#### 組件檢查範圍
- **database**: 資料庫連接和響應時間
- **discord_api**: Discord API連接狀態
- **redis**: Redis服務狀態
- **disk_space**: 磁碟使用率
- **memory**: 記憶體使用率
- **cpu**: CPU使用率
- **services**: 關鍵服務運行狀態

#### 健康狀態等級
- ✅ **HEALTHY**: 正常狀態
- ⚠️ **WARNING**: 警告狀態
- ❌ **CRITICAL**: 嚴重狀態
- ❓ **UNKNOWN**: 未知狀態

#### 退出碼說明
- `0`: 系統健康
- `1`: 存在警告
- `2`: 存在嚴重問題
- `3`: 檢查執行失敗

### 效能監控工具

#### 基本用法
```bash
# 即時效能監控（5秒間隔，持續60秒）
python scripts/monitor.py performance monitor

# 自定義監控參數
python scripts/monitor.py performance monitor --interval 10 --duration 120

# 生成效能報告
python scripts/monitor.py performance report --hours 24

# 顯示指標摘要
python scripts/monitor.py performance summary

# 檢查閾值違規
python scripts/monitor.py performance thresholds
```

#### 監控指標類型
- **cpu_usage**: CPU使用率 (%)
- **memory_usage**: 記憶體使用率 (%)
- **disk_usage**: 磁碟使用率 (%)
- **database_response_time**: 資料庫響應時間 (ms)
- **api_response_time**: API響應時間 (ms)
- **database_size**: 資料庫大小 (MB)

#### 警報閾值
```yaml
cpu_usage:
  warning: 70%
  critical: 90%

memory_usage:
  warning: 80%
  critical: 95%

disk_usage:
  warning: 85%
  critical: 95%

response_time:
  warning: 1000ms
  critical: 5000ms
```

### 維護管理工具

#### 基本用法
```bash
# 執行所有維護任務（預覽模式）
python scripts/monitor.py maintenance all --dry-run

# 實際執行所有維護
python scripts/monitor.py maintenance all

# 單個維護任務
python scripts/monitor.py maintenance logs
python scripts/monitor.py maintenance database
python scripts/monitor.py maintenance backup
python scripts/monitor.py maintenance cache
```

#### 維護任務類型

##### 1. 日誌清理 (log_cleanup)
- 清理過期的日誌文件
- 預設保留期：30天
- 自動壓縮和歸檔

```bash
# 預覽日誌清理
python scripts/monitor.py maintenance logs --dry-run

# 執行日誌清理
python scripts/monitor.py maintenance logs
```

##### 2. 資料庫優化 (database_optimization)
- 執行VACUUM重整資料庫
- 更新統計信息(ANALYZE)
- 優化查詢效能

```bash
# 預覽資料庫優化
python scripts/monitor.py maintenance database --dry-run

# 執行資料庫優化
python scripts/monitor.py maintenance database
```

##### 3. 備份管理 (backup_management)
- 創建資料庫備份
- 清理過期備份
- 驗證備份完整性

```bash
# 預覽備份管理
python scripts/monitor.py maintenance backup --dry-run

# 執行備份管理
python scripts/monitor.py maintenance backup
```

##### 4. 快取清理 (cache_cleanup)
- 清理Redis快取
- 清理應用程式快取
- 釋放記憶體空間

```bash
# 預覽快取清理
python scripts/monitor.py maintenance cache --dry-run

# 執行快取清理
python scripts/monitor.py maintenance cache
```

#### 任務調度
```bash
# 立即執行任務
python scripts/monitor.py maintenance schedule log_cleanup "緊急日誌清理" "清理過期日誌" now

# 調度未來任務
python scripts/monitor.py maintenance schedule database_optimization "週末資料庫優化" "執行資料庫維護" "2024-01-07T02:00:00"

# 查看已調度任務
python scripts/monitor.py maintenance list

# 查看維護歷史
python scripts/monitor.py maintenance history --days 7
```

### 監控儀表板工具

#### 基本用法
```bash
# 系統概覽
python scripts/monitor.py dashboard overview

# 生成HTML儀表板報告
python scripts/monitor.py dashboard dashboard --output /path/to/report.html

# 生成JSON報告
python scripts/monitor.py dashboard json

# 警報摘要
python scripts/monitor.py dashboard alerts --hours 24
```

#### 儀表板功能
- **系統概覽**: 整體健康狀態和關鍵指標
- **健康趨勢**: 24小時健康檢查趨勢
- **效能圖表**: 效能指標變化趨勢
- **維護記錄**: 近期維護任務執行情況
- **警報統計**: 警報發生和解決情況

## 配置管理

### 監控配置
```python
# 監控配置示例
config = MonitoringConfig(
    health_check_interval=60,        # 健康檢查間隔（秒）
    performance_monitoring_interval=300,  # 效能監控間隔（秒）
    retention_days=30,               # 數據保留天數
    alert_thresholds={               # 警報閾值
        'cpu_usage': {'warning': 70.0, 'critical': 90.0},
        'memory_usage': {'warning': 80.0, 'critical': 95.0},
        'disk_usage': {'warning': 85.0, 'critical': 95.0}
    },
    notification_webhooks=[          # 通知Webhook
        'https://hooks.slack.com/services/...'
    ]
)
```

### 維護調度配置
```yaml
maintenance_schedule:
  log_cleanup: "0 2 * * *"          # 每天2點
  database_optimization: "0 3 * * 0" # 每週日3點
  backup_management: "0 1 * * *"    # 每天1點
  cache_cleanup: "0 4 * * *"        # 每天4點
```

## 整合與自動化

### 系統服務整合
```python
# 在主應用中啟用監控
from services.monitoring import MonitoringService

# 初始化監控服務
monitoring = MonitoringService(db_manager)
await monitoring.initialize()

# 啟動監控
await monitoring.start_monitoring()
```

### Cron任務配置
```bash
# 每小時執行健康檢查
0 * * * * /usr/bin/python3 /path/to/scripts/monitor.py quick-check

# 每天凌晨2點執行維護
0 2 * * * /usr/bin/python3 /path/to/scripts/monitor.py maintenance all

# 每週生成報告
0 9 * * 1 /usr/bin/python3 /path/to/scripts/monitor.py dashboard dashboard --output /var/www/html/monitoring.html
```

### Docker整合
```yaml
# docker-compose.yml 監控配置
services:
  discord-bot:
    # ... 其他配置
    healthcheck:
      test: ["CMD", "python3", "/app/scripts/monitor.py", "quick-check"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## 警報和通知

### 警報類型
- **INFO**: 信息性警報
- **WARNING**: 警告級別警報
- **ERROR**: 錯誤級別警報
- **CRITICAL**: 嚴重級別警報

### 通知渠道
1. **資料庫日誌**: 所有警報都記錄在資料庫中
2. **控制台輸出**: 實時警報輸出到控制台
3. **Webhook通知**: 發送到配置的Webhook URL
4. **文件日誌**: 記錄到日誌文件

### Webhook通知格式
```json
{
  "alert_id": "550e8400-e29b-41d4-a716-446655440000",
  "level": "critical",
  "title": "資料庫健康檢查警報",
  "message": "資料庫連接失敗: connection timeout",
  "component": "database",
  "created_at": "2024-01-01T10:30:00",
  "metadata": {
    "health_check_result": {...}
  }
}
```

## 故障排除

### 常見問題

#### 1. 健康檢查失敗
```bash
# 問題: 資料庫檢查失敗
# 解決: 檢查資料庫連接和權限
python scripts/monitor.py health component database

# 問題: API檢查超時
# 解決: 檢查網絡連接和Discord API狀態
python scripts/monitor.py health component discord_api
```

#### 2. 效能指標異常
```bash
# 問題: CPU使用率過高
# 解決: 檢查系統進程和資源使用
python scripts/monitor.py performance thresholds

# 問題: 記憶體洩漏
# 解決: 監控記憶體使用趨勢
python scripts/monitor.py performance monitor --interval 5 --duration 300
```

#### 3. 維護任務失敗
```bash
# 問題: 維護任務執行失敗
# 解決: 檢查任務歷史和錯誤信息
python scripts/monitor.py maintenance history

# 問題: 權限不足
# 解決: 確保腳本有適當的文件和資料庫權限
```

### 調試模式
```bash
# 啟用詳細輸出
python scripts/monitor.py health check --verbose

# 使用預覽模式測試
python scripts/monitor.py maintenance all --dry-run
```

### 日誌檢查
```bash
# 檢查應用日誌
tail -f logs/discord_bot.log

# 檢查系統日誌
journalctl -u discord-bot -f

# 檢查監控服務日誌
grep "MonitoringService" logs/*.log
```

## 最佳實踐

### 1. 定期監控
- 設置自動化健康檢查
- 配置效能基準線
- 建立警報響應流程

### 2. 預防性維護
- 定期執行維護任務
- 監控資源使用趨勢
- 及時處理警告信號

### 3. 容量規劃
- 監控增長趨勢
- 預測資源需求
- 制定擴展計劃

### 4. 應急準備
- 建立應急響應程序
- 測試備份恢復流程
- 準備回滾計劃

## 參考資料

### API參考
- [MonitoringService API](../api/api_reference.md#monitoring-service)
- [健康檢查配置](../technical/architecture.md#health-checks)
- [效能指標定義](../technical/architecture.md#performance-metrics)

### 相關文檔
- [系統架構指南](../technical/architecture.md)
- [部署指南](../user/admin_guide.md#deployment)
- [故障排除指南](../troubleshooting/troubleshooting.md)