# 開發者指南

**版本：** v2.4.1  
**最後更新：** 2025-08-23  
**任務ID：** T10 - Release and documentation readiness  

## 歡迎

歡迎加入Discord機器人模組化系統的開發團隊！本指南將幫助您快速上手項目開發，了解開發流程、代碼規範和最佳實踐。

## 快速開始

### 環境要求

- **Python 3.13+**
- **uv 包管理器** (推薦) 或 pip
- **Git 2.30+**
- **SQLite 3.30+**
- **Discord.py 2.0+**

### 開發環境設置

#### 1. 克隆項目

```bash
git clone <repository-url>
cd roas-bot
```

#### 2. 使用 uv 設置環境 (推薦)

##### 安裝 uv
```bash
# macOS/Linux (Homebrew)
brew install uv

# 或使用官方安裝腳本
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

##### 項目設置
```bash
# 一鍵安裝所有依賴（包含開發依賴）
uv sync --extra dev

# 僅安裝生產依賴
uv sync
```

#### 3. 傳統 Python 環境設置 (備用方案)

##### 創建虛擬環境

```bash
python -m venv venv

# Windows
venv\\Scripts\\activate

# macOS/Linux
source venv/bin/activate
```

##### 安裝依賴

```bash
# 從 pyproject.toml 安裝（推薦）
pip install -e ".[dev]"

# 或使用舊版相容方式（如果有 requirements.txt）
pip install -r requirements.txt
```

#### 4. 環境配置

創建 `.env` 文件：

```env
DISCORD_TOKEN=your_discord_bot_token
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=sqlite:///data/discord_data.db
MESSAGE_DATABASE_URL=sqlite:///data/message.db
LOG_LEVEL=DEBUG
```

#### 5. 資料庫初始化

```bash
python -c "
import asyncio
from core.database_manager import DatabaseManager
from scripts.migration_manager import MigrationManager

async def init_db():
    db_manager = DatabaseManager()
    await db_manager.initialize()
    
    migration_manager = MigrationManager(db_manager)
    await migration_manager.run_migrations()
    
    await db_manager.close()

asyncio.run(init_db())
"
```

#### 6. 運行測試

```bash
python run_integration_tests.py --type unit
```

#### 7. 啟動機器人

```bash
python main.py
```

## 項目結構

```
roas-bot/
├── core/                    # 核心基礎設施
│   ├── base_service.py     # 服務基礎類
│   ├── database_manager.py # 資料庫管理
│   ├── exceptions.py       # 異常處理
│   └── service_startup_manager.py
├── services/               # 業務服務層
│   ├── achievement/        # 成就系統
│   ├── economy/           # 經濟系統
│   ├── government/        # 政府系統
│   ├── documentation/     # 文檔服務
│   ├── deployment/        # 部署服務
│   └── monitoring/        # 監控服務
├── panels/                # Discord UI面板
│   ├── achievement/       # 成就面板
│   ├── economy/          # 經濟面板
│   └── government/       # 政府面板
├── cogs/                  # Discord Cogs
├── tests/                 # 測試文件
├── docs/                  # 文檔
├── scripts/               # 工具腳本
└── main.py               # 主程序入口
```

## 開發工作流程

### 1. 功能開發流程

#### Step 1: 創建功能分支

```bash
git checkout -b feature/your-feature-name
```

#### Step 2: 編寫測試

遵循測試驅動開發（TDD），先編寫測試：

```python
# tests/services/your_service/test_your_service.py
import pytest
from services.your_service.your_service import YourService

class TestYourService:
    @pytest.mark.unit
    async def test_your_method(self):
        service = YourService()
        result = await service.your_method()
        assert result is not None
```

#### Step 3: 實現功能

創建服務：

```python
# services/your_service/your_service.py
from core.base_service import BaseService

class YourService(BaseService):
    async def _initialize(self) -> bool:
        # 初始化邏輯
        return True
    
    async def _cleanup(self) -> None:
        # 清理邏輯
        pass
    
    async def _validate_permissions(self, user_id, guild_id, action) -> bool:
        # 權限驗證邏輯
        return True
```

#### Step 4: 創建面板（如需要）

```python
# panels/your_panel/your_panel.py
from panels.base_panel import BasePanel

class YourPanel(BasePanel):
    async def _handle_slash_command(self, interaction):
        # 處理斜線命令
        pass
```

#### Step 5: 運行測試

```bash
python run_integration_tests.py --type unit
python run_integration_tests.py --type integration
```

#### Step 6: 提交代碼

```bash
git add .
git commit -m "feat: add your feature description

- Implement YourService with basic functionality
- Add comprehensive unit tests
- Update documentation

Task ID: X"
```

### 2. 代碼審查流程

#### 創建Pull Request

1. 推送分支到遠端倉庫
2. 創建Pull Request
3. 填寫PR模板
4. 請求代碼審查

#### PR模板

```markdown
## 概述
簡要描述這個PR的目的和內容

## 變更類型
- [ ] 新功能
- [ ] Bug修復
- [ ] 重構
- [ ] 文檔更新
- [ ] 測試改進

## 測試
- [ ] 單元測試通過
- [ ] 整合測試通過
- [ ] 手動測試完成

## 任務ID
Task ID: X

## 檢查清單
- [ ] 代碼遵循項目規範
- [ ] 添加了必要的測試
- [ ] 更新了相關文檔
- [ ] 沒有破壞性變更
```

## 代碼規範

### Python代碼風格

#### 1. 遵循PEP 8

```python
# 好的範例
class UserService(BaseService):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__("UserService")
        self.db_manager = db_manager
    
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """獲取用戶信息"""
        return await self.db_manager.fetch_one(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        )
```

#### 2. 類型註解

```python
from typing import Optional, Dict, Any, List

async def process_users(
    user_ids: List[int], 
    include_details: bool = False
) -> Dict[int, Optional[Dict[str, Any]]]:
    """處理用戶列表"""
    results = {}
    for user_id in user_ids:
        user_info = await self.get_user_info(user_id)
        results[user_id] = user_info
    return results
```

#### 3. 文檔字符串

```python
async def transfer_currency(
    self, 
    from_user: int, 
    to_user: int, 
    amount: int,
    currency_type: str = "coins"
) -> bool:
    """
    在用戶間轉移貨幣
    
    參數：
        from_user: 轉出用戶ID
        to_user: 轉入用戶ID
        amount: 轉移金額（必須為正數）
        currency_type: 貨幣類型，預設為coins
        
    返回：
        bool: 轉移是否成功
        
    異常：
        ValueError: 當金額為負數或用戶不存在時
        InsufficientFundsError: 當餘額不足時
    """
```

#### 4. 錯誤處理

```python
from core.exceptions import ServiceError, ValidationError

async def update_user_balance(self, user_id: int, amount: int):
    try:
        if amount < 0:
            raise ValidationError(
                "金額不能為負數",
                field="amount",
                value=amount
            )
        
        result = await self.db_manager.execute(
            "UPDATE users SET balance = balance + ? WHERE id = ?",
            (amount, user_id)
        )
        
        if result == 0:
            raise ServiceError(
                f"用戶 {user_id} 不存在",
                service_name=self.name,
                operation="update_balance"
            )
            
    except Exception as e:
        self.logger.exception(f"更新用戶餘額失敗：{e}")
        raise
```

### 測試規範

#### 1. 測試結構

```python
class TestEconomyService:
    @pytest.fixture
    async def economy_service(self, mock_db_manager):
        service = EconomyService(mock_db_manager)
        await service.initialize()
        return service
    
    @pytest.mark.unit
    async def test_add_currency_success(self, economy_service):
        # Arrange
        user_id = 12345
        amount = 100
        
        # Act
        result = await economy_service.add_currency(user_id, amount)
        
        # Assert
        assert result is True
    
    @pytest.mark.unit
    async def test_add_currency_negative_amount(self, economy_service):
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await economy_service.add_currency(12345, -100)
        
        assert "金額不能為負數" in str(exc_info.value)
```

#### 2. 測試標記

```python
@pytest.mark.unit          # 單元測試
@pytest.mark.integration   # 整合測試
@pytest.mark.performance   # 效能測試
@pytest.mark.slow          # 慢速測試
@pytest.mark.e2e           # 端到端測試
```

#### 3. Mock使用

```python
@patch('services.economy.EconomyService.get_user_balance')
async def test_transfer_currency(self, mock_get_balance, economy_service):
    # 設置Mock
    mock_get_balance.return_value = 500
    
    # 執行測試
    result = await economy_service.transfer_currency(1, 2, 100)
    
    # 驗證Mock調用
    mock_get_balance.assert_called_with(1)
    assert result is True
```

### 資料庫規範

#### 1. 遷移文件

```sql
-- migrations/005_add_user_preferences.sql
-- Task ID: X - 添加用戶偏好設置

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, preference_key),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id 
ON user_preferences (user_id);
```

#### 2. 查詢優化

```python
# 好的範例：使用參數化查詢
async def get_user_achievements(self, user_id: int) -> List[Dict]:
    return await self.db_manager.fetch_all("""
        SELECT a.id, a.name, a.description, ua.earned_at
        FROM achievements a
        JOIN user_achievements ua ON a.id = ua.achievement_id
        WHERE ua.user_id = ?
        ORDER BY ua.earned_at DESC
    """, (user_id,))

# 避免：字符串拼接
# query = f"SELECT * FROM users WHERE id = {user_id}"  # 危險！
```

## 最佳實踐

### 1. 服務設計

#### 單一職責原則

```python
# 好的範例：專注於經濟功能
class EconomyService(BaseService):
    async def add_currency(self, user_id: int, amount: int):
        """只處理貨幣添加"""
        pass
    
    async def transfer_currency(self, from_user: int, to_user: int, amount: int):
        """只處理貨幣轉移"""
        pass

# 避免：混合多種職責
class UserManagementService(BaseService):
    async def add_currency(self, user_id: int, amount: int):
        """應該在EconomyService中"""
        pass
    
    async def update_user_profile(self, user_id: int, profile: Dict):
        """應該在UserService中"""
        pass
```

#### 依賴注入

```python
class AchievementService(BaseService):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__("AchievementService")
        self.db_manager = db_manager
        # 不要在構造函數中直接創建依賴
        # self.economy_service = EconomyService()  # 避免
    
    async def initialize(self):
        # 在初始化時解析依賴
        self.economy_service = service_registry.get_service("EconomyService")
        return await super().initialize()
```

### 2. 錯誤處理

#### 優雅降級

```python
async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
    try:
        # 嘗試獲取詳細統計
        stats = await self._get_detailed_stats(user_id)
        return stats
    except DatabaseError:
        # 降級到基本統計
        self.logger.warning(f"無法獲取用戶 {user_id} 的詳細統計，降級到基本統計")
        return await self._get_basic_stats(user_id)
    except Exception as e:
        # 返回默認值
        self.logger.error(f"獲取用戶統計失敗：{e}")
        return {"error": "統計數據暫時不可用"}
```

#### 重試機制

```python
import asyncio
from functools import wraps

def retry(max_attempts: int = 3, delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (ConnectionError, TimeoutError) as e:
                    if attempt == max_attempts - 1:
                        raise
                    await asyncio.sleep(delay * (2 ** attempt))
            return None
        return wrapper
    return decorator

@retry(max_attempts=3, delay=1.0)
async def fetch_external_data(self, url: str):
    # 網路請求邏輯
    pass
```

### 3. 效能優化

#### 批量處理

```python
# 好的範例：批量處理
async def update_multiple_users(self, updates: List[Dict]):
    query = "UPDATE users SET balance = ? WHERE id = ?"
    params = [(update['balance'], update['id']) for update in updates]
    await self.db_manager.execute_many(query, params)

# 避免：逐個處理
async def update_multiple_users_slow(self, updates: List[Dict]):
    for update in updates:
        await self.db_manager.execute(
            "UPDATE users SET balance = ? WHERE id = ?",
            (update['balance'], update['id'])
        )
```

#### 快取策略

```python
from functools import lru_cache
import asyncio

class ConfigService(BaseService):
    def __init__(self):
        super().__init__()
        self._config_cache = {}
        self._cache_expiry = {}
    
    async def get_config(self, key: str) -> Any:
        # 檢查快取
        if key in self._config_cache:
            if time.time() < self._cache_expiry[key]:
                return self._config_cache[key]
        
        # 從資料庫載入
        value = await self._load_config_from_db(key)
        
        # 更新快取
        self._config_cache[key] = value
        self._cache_expiry[key] = time.time() + 300  # 5分鐘過期
        
        return value
```

## 調試和故障排除

### 1. 日誌配置

```python
import logging

# 在服務中使用結構化日誌
class YourService(BaseService):
    async def your_method(self, user_id: int):
        self.logger.info(
            "開始處理用戶請求",
            extra={
                "user_id": user_id,
                "method": "your_method",
                "service": self.name
            }
        )
        
        try:
            result = await self._process_user(user_id)
            self.logger.info(
                "用戶請求處理完成",
                extra={
                    "user_id": user_id,
                    "result": result,
                    "method": "your_method"
                }
            )
            return result
        except Exception as e:
            self.logger.exception(
                "用戶請求處理失敗",
                extra={
                    "user_id": user_id,
                    "error": str(e),
                    "method": "your_method"
                }
            )
            raise
```

### 2. 調試技巧

#### 使用健康檢查

```python
async def debug_service_health():
    """調試服務健康狀態"""
    for service_name in service_registry.list_services():
        service = service_registry.get_service(service_name)
        health = await service.health_check()
        print(f"{service_name}: {health}")
```

#### 資料庫調試

```bash
# 檢查資料庫結構
sqlite3 data/discord_data.db ".schema"

# 查看表內容
sqlite3 data/discord_data.db "SELECT * FROM users LIMIT 10;"

# 檢查索引
sqlite3 data/discord_data.db ".indices"
```

### 3. 常見問題

#### Discord.py 兼容性

```python
# conftest.py 中的修復
import sys
if sys.version_info >= (3, 10):
    import collections
    collections.Callable = collections.abc.Callable
```

#### 資料庫鎖定

```python
# 使用事務避免鎖定
async def safe_user_update(self, user_id: int, updates: Dict):
    async with self.db_manager.transaction() as tx:
        current_data = await tx.fetch_one(
            "SELECT * FROM users WHERE id = ?", 
            (user_id,)
        )
        
        # 更新邏輯
        new_data = {**current_data, **updates}
        
        await tx.execute(
            "UPDATE users SET ... WHERE id = ?",
            (*new_data.values(), user_id)
        )
```

## 部署和發布

### 1. 版本管理

```bash
# 創建發布分支
git checkout -b release/v2.5.0

# 更新版本號
echo "v2.5.0" > VERSION

# 生成變更日誌
git log --oneline v2.4.0..HEAD > CHANGELOG.md

# 提交並標記
git add .
git commit -m "release: v2.5.0"
git tag v2.5.0
```

### 2. 部署檢查清單

- [ ] 所有測試通過
- [ ] 代碼審查完成
- [ ] 文檔已更新
- [ ] 資料庫遷移準備就緒
- [ ] 監控配置正確
- [ ] 回滾計劃準備

## 資源和參考

### 內部文檔

- [API參考文檔](../api/api_reference.md)
- [測試指南](../TESTING.md)
- [疑難排解指南](../troubleshooting/troubleshooting.md)

### 外部資源

- [Discord.py 文檔](https://discordpy.readthedocs.io/)
- [Python 風格指南 (PEP 8)](https://www.python.org/dev/peps/pep-0008/)
- [SQLite 文檔](https://www.sqlite.org/docs.html)

### 社群支援

- 項目Issue追蹤
- 開發者討論群組
- 代碼審查指南

## 貢獻認可

感謝所有為這個項目做出貢獻的開發者！請查看項目的貢獻者列表，了解更多關於項目貢獻的信息。

---

**注意**：本指南會隨著項目的發展持續更新。如果您有任何建議或發現錯誤，請創建Issue或提交PR。