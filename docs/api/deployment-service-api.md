# 部署服務API文檔

## 概述

部署服務API為ROAS Discord Bot v2.4.4提供統一的自動化部署接口。作為Elena（API架構師）設計的專業API系統，它提供RESTful風格的接口，支援異步部署操作、即時狀態監控和與現有服務架構的無縫整合。

## 核心特性

### 🚀 多模式部署支援
- **Docker模式**: 容器化部署，適合生產環境
- **UV模式**: 現代Python包管理，適合開發環境  
- **降級模式**: 標準Python環境，確保最大相容性
- **自動模式**: 智能選擇最佳部署方式

### 💫 異步操作設計
- 非阻塞部署流程
- 即時進度回調
- 並發部署管理
- 任務取消支援

### 📊 完整監控體系
- 健康檢查API
- 部署狀態追蹤
- 進度即時更新
- 歷史記錄查詢

### 🔗 服務整合
- 與服務註冊中心整合
- 生命週期管理
- 依賴關係處理
- 自動恢復機制

## API 接口規範

### 1. 健康檢查

```python
# API端點
GET /api/deployment/health

# 使用範例
from src.services.deployment_api import get_deployment_api

async def check_health():
    api = await get_deployment_api()
    health = await api.health_check()
    return health
```

**回應格式**:
```json
{
  "api_status": "ready",
  "timestamp": "2025-08-27T10:00:00Z",
  "version": "1.0.0",
  "deployment_managers": {
    "docker": {"status": "available"},
    "uv": {"status": "available"}, 
    "fallback": {"status": "available"}
  },
  "active_deployments": 0,
  "max_concurrent_deployments": 3,
  "system_resources": {
    "cpu_percent": 25.3,
    "memory_percent": 45.2,
    "disk_percent": 60.1
  },
  "statistics": {
    "total_deployments": 15,
    "successful_deployments": 12,
    "failed_deployments": 2,
    "cancelled_deployments": 1,
    "average_deployment_time": 145.3
  }
}
```

### 2. 開始部署

```python
# 創建部署請求
from src.services.deployment_api import DeploymentRequest, get_deployment_api

async def start_deployment():
    # 創建部署請求
    request = DeploymentRequest(
        mode='uv',  # 或 'docker', 'fallback', 'auto'
        config={
            'environment_variables': {
                'DISCORD_TOKEN': 'your-bot-token',
                'DATABASE_URL': 'sqlite:///bot.db'
            },
            'profile': 'development'
        },
        environment='dev',
        timeout=300,
        force_rebuild=False,
        skip_health_check=False,
        callback_url='https://your-webhook-url.com/callback',
        metadata={
            'initiated_by': 'user_12345',
            'deployment_reason': 'feature_update'
        }
    )
    
    # 提交部署
    api = await get_deployment_api()
    response = await api.start_deployment(request)
    
    return response
```

**回應格式**:
```json
{
  "deployment_id": "uv_20250827_100000_a1b2c3d4",
  "status": "accepted", 
  "message": "部署已開始",
  "mode": "uv",
  "start_time": "2025-08-27T10:00:00Z",
  "estimated_duration": 120,
  "progress_url": "/api/deployments/uv_20250827_100000_a1b2c3d4/progress",
  "logs_url": "/api/deployments/uv_20250827_100000_a1b2c3d4/logs",
  "metadata": {
    "initiated_by": "user_12345",
    "deployment_reason": "feature_update",
    "api_version": "1.0.0"
  }
}
```

### 3. 查詢部署狀態

```python
async def check_deployment_status(deployment_id: str):
    api = await get_deployment_api()
    status = await api.get_deployment_status(deployment_id)
    return status
```

**回應格式**:
```json
{
  "deployment_id": "uv_20250827_100000_a1b2c3d4",
  "status": "running",
  "mode": "uv",
  "start_time": "2025-08-27T10:00:00Z",
  "current_step": "安裝依賴",
  "progress_percentage": 65.0,
  "estimated_time_remaining": 45,
  "logs_available": true,
  "metadata": {
    "initiated_by": "user_12345"
  }
}
```

### 4. 獲取部署進度

```python
async def get_deployment_progress(deployment_id: str):
    api = await get_deployment_api()
    progress = await api.get_deployment_progress(deployment_id)
    return progress
```

**回應格式**:
```json
{
  "deployment_id": "uv_20250827_100000_a1b2c3d4",
  "current_step": "配置環境",
  "progress_percentage": 75.0,
  "completed_steps": 3,
  "total_steps": 5,
  "estimated_time_remaining": 30,
  "last_update": "2025-08-27T10:02:30Z"
}
```

### 5. 取消部署

```python
async def cancel_deployment(deployment_id: str):
    api = await get_deployment_api()
    result = await api.cancel_deployment(deployment_id)
    return result
```

**回應格式**:
```json
{
  "deployment_id": "uv_20250827_100000_a1b2c3d4",
  "status": "cancelled",
  "message": "部署已取消",
  "cancelled_at": "2025-08-27T10:03:00Z"
}
```

### 6. 查看部署歷史

```python
async def list_deployment_history(limit: int = 50):
    api = await get_deployment_api()
    history = await api.list_deployments(limit=limit)
    return history
```

**回應格式**:
```json
[
  {
    "deployment_id": "uv_20250827_100000_a1b2c3d4",
    "status": "completed",
    "mode": "uv", 
    "start_time": "2025-08-27T10:00:00Z",
    "end_time": "2025-08-27T10:02:15Z",
    "duration_seconds": 135,
    "is_active": false
  },
  {
    "deployment_id": "docker_20250827_090000_e5f6g7h8",
    "status": "running",
    "mode": "docker",
    "start_time": "2025-08-27T09:00:00Z", 
    "is_active": true,
    "metadata": {
      "initiated_by": "admin_67890"
    }
  }
]
```

## 進階功能

### 回調機制

部署API支援Webhook回調，可以在部署過程中即時通知外部系統：

```python
async def deployment_with_callback():
    request = DeploymentRequest(
        mode='auto',
        callback_url='https://your-app.com/webhook/deployment',
        config={
            'notifications_enabled': True
        }
    )
    
    api = await get_deployment_api()
    response = await api.start_deployment(request)
    
    # Webhook將接收到以下格式的進度更新
    # {
    #   "deployment_id": "...",
    #   "current_step": "...",
    #   "progress_percentage": 50.0,
    #   "timestamp": "..."
    # }
    
    return response
```

### 併發控制

API自動管理併發部署，確保系統穩定性：

```python
# 最大併發部署數量由配置決定，預設為3
# 超出限制的請求會被拒絕並返回錯誤

try:
    response = await api.start_deployment(request)
except DeploymentError as e:
    if "併發限制" in str(e):
        print("已達到最大併發部署限制，請稍後重試")
```

### 錯誤處理

API提供完善的錯誤處理機制：

```python
from src.core.errors import DeploymentError, EnvironmentError

async def deploy_with_error_handling():
    try:
        request = DeploymentRequest(mode='docker')
        api = await get_deployment_api()
        response = await api.start_deployment(request)
        return response
        
    except DeploymentError as e:
        # 部署相關錯誤
        print(f"部署失敗: {e}")
        
    except EnvironmentError as e:
        # 環境相關錯誤
        print(f"環境問題: {e}")
        
    except Exception as e:
        # 其他未預期錯誤
        print(f"未知錯誤: {e}")
```

## 服務註冊整合

### 註冊部署服務

```python
from src.services.deployment_api import create_deployment_service_api
from src.core.service_registry import extended_service_registry

async def register_deployment_service():
    # 創建API實例
    api = create_deployment_service_api()
    await api.start()
    
    # 註冊到服務註冊中心
    service_name = await api.register_with_service_registry()
    
    print(f"部署服務已註冊: {service_name}")
    
    # 檢查註冊狀態
    services = extended_service_registry.list_services()
    if service_name in services:
        print("註冊成功!")
    
    return service_name
```

### 服務發現

```python
async def discover_deployment_services():
    # 自動發現部署服務
    discovered = await extended_service_registry.discover_services()
    
    deployment_services = discovered.get('deployment_services', [])
    print(f"發現 {len(deployment_services)} 個部署服務:")
    
    for service in deployment_services:
        print(f"  - {service['name']} ({service['type']})")
```

### 生命週期管理

```python
async def manage_service_lifecycle():
    # 獲取服務狀態
    lifecycle_manager = extended_service_registry.lifecycle_manager
    
    service_name = "DeploymentServiceAPI"
    status = lifecycle_manager.get_service_status(service_name)
    print(f"服務狀態: {status}")
    
    # 執行健康檢查
    health = await lifecycle_manager.perform_health_check(service_name)
    print(f"健康狀態: {health.status}")
    
    # 獲取生命週期事件
    events = extended_service_registry.get_lifecycle_events(service_name)
    for event in events[-5:]:  # 最近5個事件
        print(f"事件: {event['event_type']} - {event['message']}")
```

## 最佳實踐

### 1. 選擇合適的部署模式

```python
async def choose_deployment_mode():
    # 檢查環境可用性
    api = await get_deployment_api()
    health = await api.health_check()
    
    managers = health['deployment_managers']
    
    # 生產環境優先使用Docker
    if managers['docker']['status'] == 'available':
        mode = 'docker'
    # 開發環境使用UV
    elif managers['uv']['status'] == 'available':
        mode = 'uv'
    # 兜底使用降級模式
    else:
        mode = 'fallback'
    
    return mode
```

### 2. 監控部署進度

```python
async def monitor_deployment(deployment_id: str):
    api = await get_deployment_api()
    
    while True:
        status = await api.get_deployment_status(deployment_id)
        
        if status['status'] in ['completed', 'failed', 'cancelled']:
            print(f"部署結束: {status['status']}")
            break
        
        if status.get('is_active'):
            progress = await api.get_deployment_progress(deployment_id)
            print(f"進度: {progress.progress_percentage:.1f}% - {progress.current_step}")
        
        await asyncio.sleep(5)  # 每5秒檢查一次
```

### 3. 錯誤恢復

```python
async def deploy_with_fallback(config: Dict[str, Any]):
    """帶降級機制的部署"""
    modes = ['docker', 'uv', 'fallback']
    
    for mode in modes:
        try:
            request = DeploymentRequest(mode=mode, config=config)
            api = await get_deployment_api()
            response = await api.start_deployment(request)
            
            print(f"使用 {mode} 模式部署成功")
            return response
            
        except DeploymentError as e:
            print(f"{mode} 模式部署失敗: {e}")
            if mode == 'fallback':  # 最後一個模式
                raise
            continue
```

### 4. 批次部署管理

```python
async def batch_deployment(configs: List[Dict[str, Any]]):
    """批次部署管理"""
    api = await get_deployment_api()
    deployments = []
    
    for i, config in enumerate(configs):
        request = DeploymentRequest(
            mode='auto',
            config=config,
            metadata={'batch_id': f'batch_{i}'}
        )
        
        try:
            response = await api.start_deployment(request)
            deployments.append(response.deployment_id)
            
        except DeploymentError as e:
            if "併發限制" in str(e):
                # 等待現有部署完成
                await wait_for_available_slot(api)
                response = await api.start_deployment(request)
                deployments.append(response.deployment_id)
            else:
                raise
    
    return deployments

async def wait_for_available_slot(api):
    """等待部署槽位可用"""
    while True:
        health = await api.health_check()
        if health['active_deployments'] < health['max_concurrent_deployments']:
            break
        await asyncio.sleep(10)
```

## 故障排除

### 常見問題

1. **部署請求被拒絕**
   ```python
   # 檢查併發限制
   health = await api.health_check()
   print(f"活躍部署: {health['active_deployments']}/{health['max_concurrent_deployments']}")
   ```

2. **部署卡住不動**
   ```python
   # 檢查系統資源
   health = await api.health_check()
   resources = health['system_resources']
   if resources['cpu_percent'] > 90 or resources['memory_percent'] > 90:
       print("系統資源不足，可能影響部署速度")
   ```

3. **部署管理器不可用**
   ```python
   # 檢查各管理器狀態
   health = await api.health_check()
   for mode, status in health['deployment_managers'].items():
       if status['status'] != 'available':
           print(f"{mode} 管理器不可用: {status}")
   ```

### 日誌分析

```python
# 啟用詳細日誌
import logging
logging.getLogger('deployment_api').setLevel(logging.DEBUG)
logging.getLogger('uv_deployment_manager').setLevel(logging.DEBUG)

# 查看特定部署的日誌
async def get_deployment_logs(deployment_id: str):
    # 實作部署日誌查詢
    # 這裡可以整合日誌系統
    pass
```

## 安全考慮

### API權限控制

部署API整合了權限驗證機制：

```python
# 權限檢查會在每個API調用時執行
# 管理員操作: deploy, cancel, restart
# 只讀操作: status, progress, list, health

async def deploy_with_permission_check(user_id: int, guild_id: int):
    api = await get_deployment_api()
    
    # 權限檢查在API內部執行
    has_permission = await api._validate_permissions(user_id, guild_id, 'deploy')
    if not has_permission:
        raise PermissionError("用戶沒有部署權限")
    
    # 繼續部署流程...
```

### 敏感資料保護

```python
# 環境變數和配置會被安全處理
request = DeploymentRequest(
    mode='uv',
    config={
        'environment_variables': {
            'DISCORD_TOKEN': 'your-bot-token',  # 將被安全儲存
            'DATABASE_URL': 'sqlite:///bot.db'
        }
    }
)
```

## 總結

部署服務API提供了完整的自動化部署解決方案，具有以下優勢：

1. **專業的API設計**: 遵循RESTful原則，提供直觀的接口
2. **異步操作支援**: 長時間部署操作不會阻塞系統
3. **完善的監控**: 即時狀態查詢和進度跟蹤
4. **靈活的部署模式**: 支援多種部署方式和自動選擇
5. **服務整合**: 與現有架構無縫整合
6. **錯誤處理**: 完善的錯誤處理和恢復機制
7. **安全性**: 權限控制和敏感資料保護

這個API系統為ROAS Discord Bot提供了enterprise級別的部署能力，確保系統可以在任何環境中穩定可靠地部署和運行。