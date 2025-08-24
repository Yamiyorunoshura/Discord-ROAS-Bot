# 連結檢查API服務文檔

## 概述

文檔連結檢查API服務提供完整的Markdown文檔連結有效性檢查功能，支援內部連結驗證、錨點連結檢查、定期自動檢查等功能。

## API端點

### 檢查連結

**端點**: `POST /api/documentation/check-links`  
**描述**: 檢查指定文檔的連結有效性

#### 請求參數

```python
{
    "target_paths": ["docs/", "README.md"],  # 可選，要檢查的路徑列表
    "check_external": false,                  # 可選，是否檢查外部連結
    "check_anchors": true,                   # 可選，是否檢查錨點連結
    "output_format": "json"                  # 可選，輸出格式 ("json", "summary")
}
```

#### 響應範例

```python
{
    "success": true,
    "data": {
        "check_id": "check_abc123",
        "timestamp": "2025-08-24T12:00:00Z",
        "summary": {
            "documents_checked": 15,
            "total_links": 127,
            "valid_links": 120,
            "broken_links": 7,
            "success_rate": 94.5,
            "has_failures": true,
            "duration_ms": 2341
        },
        "details": {
            "broken_links": [
                {
                    "text": "API Guide",
                    "url": "api/guide.md",
                    "line_number": 23,
                    "link_type": "internal",
                    "error_message": "檔案不存在"
                }
            ],
            "warnings": ["發現未使用的錨點: unused-section"],
            "errors": [],
            "link_distribution": {
                "internal_links": 89,
                "external_links": 23,
                "anchor_links": 15,
                "file_links": 0
            }
        },
        "recommendations": [
            "修復 7 個無效連結",
            "檢查警告信息並進行相應調整"
        ]
    },
    "timestamp": "2025-08-24T12:00:00Z"
}
```

### 獲取檢查結果

**端點**: `GET /api/documentation/check-result/{check_id}`  
**描述**: 獲取指定檢查的詳細結果

#### 響應範例

```python
{
    "success": true,
    "data": {
        "check_id": "check_abc123",
        "timestamp": "2025-08-24T12:00:00Z",
        "summary": { /* 同上 */ },
        "details": { /* 同上 */ },
        "configuration": {
            "check_external_links": false,
            "check_anchors": true,
            "base_path": "/Users/project/roas-bot"
        }
    }
}
```

### 檢查歷史

**端點**: `GET /api/documentation/check-history?limit=10&since_days=7`  
**描述**: 獲取檢查歷史記錄

#### 響應範例

```python
{
    "success": true,
    "data": {
        "history": [
            {
                "check_id": "check_abc123",
                "timestamp": "2025-08-24T12:00:00Z",
                "documents_checked": 15,
                "total_links": 127,
                "success_rate": 94.5,
                "has_failures": true,
                "duration_ms": 2341
            }
        ],
        "total_count": 1,
        "limit": 10,
        "since_days": 7
    }
}
```

### 創建定期排程

**端點**: `POST /api/documentation/schedule`  
**描述**: 創建定期檢查排程

#### 請求參數

```python
{
    "name": "daily_docs_check",
    "interval_hours": 24,
    "target_directories": ["docs/"],
    "config": {
        "check_external_links": false,
        "check_anchors": true,
        "timeout_seconds": 10
    }
}
```

#### 響應範例

```python
{
    "success": true,
    "data": {
        "schedule_id": "schedule_daily_docs_check_1692875400",
        "name": "daily_docs_check",
        "interval_hours": 24,
        "target_directories": ["docs/"],
        "created_at": "2025-08-24T12:30:00Z"
    }
}
```

### 排程管理

**列出排程**: `GET /api/documentation/schedules`  
**取消排程**: `DELETE /api/documentation/schedule/{schedule_id}`

### 報告匯出

**端點**: `POST /api/documentation/export-report`  
**描述**: 匯出檢查報告

#### 請求參數

```python
{
    "check_id": "check_abc123",
    "format": "markdown"  # "markdown", "json", "csv", "text"
}
```

#### 響應範例

```python
{
    "success": true,
    "data": {
        "check_id": "check_abc123",
        "format": "markdown",
        "report_path": "/path/to/report.md",
        "file_size": 5432,
        "exported_at": "2025-08-24T12:45:00Z"
    }
}
```

### 服務狀態

**端點**: `GET /api/documentation/status`  
**描述**: 獲取服務狀態資訊

#### 響應範例

```python
{
    "success": true,
    "data": {
        "service": {
            "initialized": true,
            "base_path": "/Users/project/roas-bot",
            "running_checks": 0,
            "periodic_schedules": 2,
            "active_schedules": 1,
            "history_count": 15
        },
        "cache": {
            "hits": 45,
            "misses": 12,
            "hit_rate_percent": 78.9,
            "current_size": 23
        },
        "errors": {
            "total_errors": 3,
            "recent_errors_1h": 0,
            "top_error_codes": [
                {"code": "LINK_CHECK_001", "count": 2},
                {"code": "LINK_CHECK_002", "count": 1}
            ]
        },
        "api_version": "v1"
    }
}
```

## Python SDK 使用範例

### 基本使用

```python
import asyncio
from services.documentation.api_endpoints import LinkCheckAPI

async def main():
    # 初始化API
    api = LinkCheckAPI("/path/to/project")
    await api.initialize()
    
    try:
        # 執行基本連結檢查
        result = await api.check_links(
            target_paths=["docs/"],
            check_anchors=True,
            output_format="json"
        )
        
        if result["success"]:
            summary = result["data"]["summary"]
            print(f"檢查了 {summary['documents_checked']} 個文檔")
            print(f"總連結數: {summary['total_links']}")
            print(f"成功率: {summary['success_rate']:.1f}%")
            
            if summary["has_failures"]:
                print(f"發現 {summary['broken_links']} 個無效連結")
        else:
            print(f"檢查失敗: {result['error']}")
    
    finally:
        await api.shutdown()

asyncio.run(main())
```

### 定期檢查排程

```python
async def setup_periodic_checks():
    api = LinkCheckAPI("/path/to/project")
    await api.initialize()
    
    try:
        # 創建每日檢查排程
        daily_schedule = await api.create_periodic_schedule(
            name="daily_full_check",
            interval_hours=24,
            target_directories=["docs/", "README.md"]
        )
        
        # 創建每週深度檢查
        weekly_schedule = await api.create_periodic_schedule(
            name="weekly_comprehensive",
            interval_hours=168,  # 7天
            config={
                "check_external_links": True,
                "check_anchors": True,
                "timeout_seconds": 30
            }
        )
        
        print(f"每日檢查排程ID: {daily_schedule['data']['schedule_id']}")
        print(f"每週檢查排程ID: {weekly_schedule['data']['schedule_id']}")
        
        # 列出所有排程
        schedules = await api.list_schedules()
        print(f"共有 {schedules['data']['total_count']} 個活躍排程")
        
    finally:
        await api.shutdown()
```

### 整合到文檔服務

```python
from core.database_manager import DatabaseManager
from services.documentation.documentation_service import DocumentationService

async def integrate_with_documentation_service():
    # 初始化數據庫管理器
    db_manager = DatabaseManager("project.db")
    await db_manager.initialize()
    
    # 初始化文檔服務（已整合連結檢查功能）
    doc_service = DocumentationService(db_manager)
    await doc_service.initialize()
    
    try:
        # 使用整合的連結檢查功能
        check_result = await doc_service.check_documentation_links(
            target_paths=["docs/"],
            check_external=False,
            check_anchors=True
        )
        
        if check_result["success"]:
            # 生成API文檔（如果連結檢查通過）
            if check_result["data"]["summary"]["success_rate"] > 90:
                await doc_service.generate_api_docs()
                print("API文檔已更新")
            else:
                print("連結有效性不足，請修復後再生成文檔")
        
        # 設置定期檢查
        schedule_id = await doc_service.schedule_periodic_link_check(
            interval_hours=24,
            name="docs_daily_check"
        )
        print(f"已設置定期檢查: {schedule_id}")
        
        # 查看檢查歷史
        history = await doc_service.get_link_check_history(limit=5)
        for record in history:
            print(f"檢查時間: {record['timestamp']}, "
                  f"成功率: {record['success_rate']:.1f}%")
    
    finally:
        await doc_service.cleanup()
        await db_manager.close()
```

### 高級用法：自定義通知

```python
async def notification_handler(notification_data):
    """自定義通知處理器"""
    if notification_data["type"] == "link_check_failure":
        print(f"警告：連結檢查失敗！")
        print(f"檢查ID: {notification_data['check_id']}")
        print(f"無效連結數: {notification_data['broken_links_count']}")
        print(f"成功率: {notification_data['success_rate']:.1f}%")
        
        # 這裡可以發送郵件、Slack通知等

async def setup_with_notifications():
    from services.documentation.link_checker_service import LinkCheckerService
    
    # 初始化帶通知功能的服務
    service = LinkCheckerService(
        base_path="/path/to/project",
        notification_callback=notification_handler
    )
    await service.initialize()
    
    try:
        # 執行檢查
        result = await service.check_documentation(["docs/"])
        
        # 如果有失敗，通知處理器會自動被調用
        if result.has_failures:
            print("已發送失敗通知")
        
    finally:
        await service.shutdown()
```

## 錯誤處理

### 常見錯誤碼

- `LINK_CHECK_001`: 文檔路徑不存在
- `LINK_CHECK_002`: 連結檢查超時
- `LINK_CHECK_003`: 檔案讀取權限不足
- `LINK_CHECK_004`: 配置格式錯誤
- `LINK_CHECK_005`: 服務未初始化

### 錯誤處理範例

```python
try:
    result = await api.check_links(target_paths=["/nonexistent/path"])
except Exception as e:
    print(f"檢查失敗: {e}")

# 或檢查響應
result = await api.check_links(target_paths=["/nonexistent/path"])
if not result["success"]:
    error = result["error"]
    print(f"錯誤碼: {error['error_code']}")
    print(f"錯誤訊息: {error['message']}")
    print(f"用戶訊息: {error['user_message']}")
```

## 配置選項

### LinkCheckConfig 參數

```python
from services.documentation.link_checker_models import LinkCheckConfig

config = LinkCheckConfig(
    check_external_links=False,      # 是否檢查外部連結
    check_anchors=True,              # 是否檢查錨點
    follow_redirects=True,           # 是否跟隨重定向
    timeout_seconds=10,              # 檢查超時時間
    max_concurrent_checks=5,         # 最大並發檢查數
    ignore_patterns=[               # 忽略的模式
        r".*\.tmp$",
        r".*\/temp\/.*"
    ],
    base_path="/project/root",       # 基礎路徑
    file_extensions=[".md", ".txt"]  # 支援的檔案副檔名
)
```

## 效能優化

### 快取配置

```python
from services.documentation.api_cache_and_error import ResponseCache, CachePolicy

# 初始化快取
cache = ResponseCache(
    max_size=500,
    default_ttl_seconds=1800
)

# 使用不同快取策略
cache.set("key1", "value1", CachePolicy.SHORT_TERM)   # 5分鐘
cache.set("key2", "value2", CachePolicy.MEDIUM_TERM)  # 30分鐘
cache.set("key3", "value3", CachePolicy.LONG_TERM)    # 6小時
```

### 並發處理

```python
import asyncio

async def concurrent_checks():
    api = LinkCheckAPI("/path/to/project")
    await api.initialize()
    
    try:
        # 並發檢查多個目錄
        tasks = [
            api.check_links(target_paths=["docs/api/"]),
            api.check_links(target_paths=["docs/user/"]),
            api.check_links(target_paths=["docs/dev/"])
        ]
        
        results = await asyncio.gather(*tasks)
        
        for i, result in enumerate(results):
            print(f"目錄 {i+1}: {result['data']['summary']['success_rate']:.1f}% 成功率")
    
    finally:
        await api.shutdown()
```

## 最佳實踐

1. **定期檢查**: 設置每日或每週的自動檢查
2. **階段性部署**: 在CI/CD管道中集成連結檢查
3. **通知機制**: 設置失敗通知以及時發現問題
4. **效能監控**: 定期檢查服務效能和快取命中率
5. **錯誤處理**: 實施完整的錯誤處理和重試機制

## 故障排除

### 常見問題

**Q: 檢查速度太慢怎麼辦？**  
A: 調整 `max_concurrent_checks` 參數，但不要設置太高以免影響系統效能。

**Q: 大量無效連結報告怎麼處理？**  
A: 使用 `ignore_patterns` 配置忽略已知問題，或分批處理修復。

**Q: 如何處理相對路徑問題？**  
A: 確保正確設置 `base_path` 參數，並使用標準的相對路徑格式。

**Q: 服務記憶體占用過高？**  
A: 檢查快取配置，定期清理舊報告，調整 `max_size` 參數。