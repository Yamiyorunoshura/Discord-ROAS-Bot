# 故障排除指南

**版本：** v2.4.1  
**最後更新：** 2025-08-23  
**任務ID：** T10 - Release and documentation readiness  

## 概覽

本指南提供Discord機器人模組化系統常見問題的診斷步驟和解決方案。按照症狀分類，幫助您快速定位和解決問題。

## 問題分類索引

- [錯誤代碼查詢](#錯誤代碼查詢)
- [啟動和初始化問題](#啟動和初始化問題)
- [資料庫相關問題](#資料庫相關問題)
- [Discord API問題](#discord-api問題)
- [權限和認證問題](#權限和認證問題)
- [效能和記憶體問題](#效能和記憶體問題)
- [服務整合問題](#服務整合問題)
- [測試相關問題](#測試相關問題)
- [部署和環境問題](#部署和環境問題)

---

## 錯誤代碼查詢

### 使用標準錯誤代碼系統

roas-bot v2.4.1採用統一的錯誤代碼系統，所有錯誤都會附帶標準化的錯誤代碼，幫助快速定位問題原因。

**錯誤代碼格式：**
```
[模組縮寫]_[數字]
```

### 常見錯誤代碼對照表

#### 應用程式核心錯誤 (APP_1000-1099)
- `APP_1000`: 未知錯誤 - 檢查日誌獲取詳細資訊
- `APP_1001`: 系統內部錯誤 - 重啟服務或聯繫支援
- `APP_1002`: 初始化錯誤 - 檢查配置文件和環境變數
- `APP_1004`: 逾時錯誤 - 檢查網路連線和資源可用性

#### 服務層錯誤 (SVC_1100-1199)  
- `SVC_1101`: 服務無法使用 - 檢查服務狀態和依賴
- `SVC_1102`: 服務初始化失敗 - 檢查服務配置
- `SVC_1104`: 服務依賴錯誤 - 確認所有依賴服務正常運行

#### 成就系統錯誤 (ACH_1200-1299)
- `ACH_1200`: 成就不存在 - 檢查成就ID是否正確
- `ACH_1201`: 成就已獲得 - 用戶已獲得此成就
- `ACH_1202`: 成就要求未滿足 - 檢查成就觸發條件

#### 經濟系統錯誤 (ECO_1300-1399)
- `ECO_1300`: 餘額不足 - 用戶帳戶餘額不足以完成操作
- `ECO_1301`: 金額無效 - 檢查輸入金額格式
- `ECO_1305`: 帳戶不存在 - 用戶帳戶未創建

#### 政府系統錯誤 (GOV_1400-1499)
- `GOV_1400`: 身分組不存在 - 檢查身分組配置
- `GOV_1403`: 權限不足 - 用戶權限不足以執行此操作
- `GOV_1407`: 權限檢查失敗 - 權限驗證過程發生錯誤

#### 資料庫錯誤 (DB_1500-1599)
- `DB_1500`: 資料庫連線錯誤 - 檢查資料庫連線設定
- `DB_1501`: 資料查詢錯誤 - 檢查查詢語法和資料完整性
- `DB_1506`: 資料庫鎖定錯誤 - 重試操作或檢查併發衝突

### 錯誤代碼查詢工具

```bash
# 查詢特定錯誤代碼詳細資訊
python -m tools.error_code_lookup APP_1002

# 檢查錯誤代碼一致性
python -m tools.consistency_checker

# 查看錯誤代碼使用統計
python -m tools.error_usage_stats
```

### 日誌中錯誤代碼識別

當系統發生錯誤時，日誌中會包含標準化的錯誤資訊：

```
[2025-08-23 10:30:15] ERROR [SVC_1102] AchievementService: 服務初始化失敗
Context: {"user_id": 12345, "guild_id": 67890, "operation": "initialize"}
Details: 無法連接到資料庫，檢查DATABASE_URL配置
```

### 錯誤恢復建議

根據錯誤代碼類型，採用相應的恢復策略：

- **APP_xxxx**: 檢查系統級配置和環境
- **SVC_xxxx**: 重啟相關服務或檢查服務依賴
- **ACH/ECO/GOV_xxxx**: 檢查業務邏輯和用戶操作
- **DB_xxxx**: 檢查資料庫連線和資料完整性

---

## 啟動和初始化問題

### 機器人無法啟動

**症狀：**
```
python main.py
ERROR: 機器人啟動失敗
```

**可能原因：**
1. Discord Token無效或過期
2. 環境變數未正確設置
3. 依賴包版本衝突
4. 資料庫連接失敗

**診斷步驟：**

1. **檢查Token**
   ```bash
   # 檢查環境變數
   echo $DISCORD_TOKEN
   
   # 或檢查.env文件
   cat .env | grep DISCORD_TOKEN
   ```

2. **檢查依賴**
   ```bash
   pip list | grep discord
   python -c "import discord; print(discord.__version__)"
   ```

3. **檢查資料庫**
   ```bash
   # 檢查資料庫文件是否存在
   ls -la data/
   
   # 測試資料庫連接
   sqlite3 data/discord_data.db ".tables"
   ```

**解決方案：**

1. **更新Token**
   ```bash
   # 在Discord Developer Portal獲取新Token
   # 更新.env文件
   DISCORD_TOKEN=your_new_token_here
   ```

2. **重新安裝依賴**
   ```bash
   pip uninstall discord.py
   pip install discord.py==2.0+
   ```

3. **重新初始化資料庫**
   ```bash
   python scripts/init_database.py
   ```

### 服務初始化失敗

**症狀：**
```
ServiceInitializationError: AchievementService 初始化失敗
```

**診斷步驟：**

1. **檢查服務依賴**
   ```python
   # 在Python控制台中
   from core.base_service import service_registry
   print(service_registry.list_services())
   
   # 檢查依賴順序
   print(service_registry.get_initialization_order())
   ```

2. **檢查循環依賴**
   ```bash
   python -c "
   from core.base_service import service_registry
   try:
       order = service_registry.get_initialization_order()
       print('無循環依賴')
   except Exception as e:
       print(f'發現循環依賴: {e}')
   "
   ```

**解決方案：**

1. **修復依賴關係**
   ```python
   # 確保依賴服務已註冊
   await dependency_service.register()
   await your_service.register()
   
   # 正確設置依賴
   your_service.add_dependency(dependency_service)
   ```

2. **檢查服務構造函數**
   ```python
   class YourService(BaseService):
       def __init__(self, db_manager):
           super().__init__("YourService")
           self.db_manager = db_manager
           # 確保db_manager不為None
           if not db_manager:
               raise ValueError("db_manager 不能為 None")
   ```

---

## 資料庫相關問題

### 資料庫鎖定錯誤

**症狀：**
```
sqlite3.OperationalError: database is locked
```

**可能原因：**
1. 多個進程同時訪問資料庫
2. 未正確關閉資料庫連接
3. 長時間運行的事務

**診斷步驟：**

1. **檢查進程**
   ```bash
   # Linux/macOS
   lsof data/discord_data.db
   
   # Windows
   handle discord_data.db
   ```

2. **檢查連接池**
   ```python
   # 在服務中檢查
   db_status = await self.db_manager.get_connection_status()
   print(f"活躍連接: {db_status['active_connections']}")
   print(f"池大小: {db_status['pool_size']}")
   ```

**解決方案：**

1. **正確使用事務**
   ```python
   # 正確方式
   async with self.db_manager.transaction() as tx:
       await tx.execute("UPDATE users SET ...")
       await tx.execute("INSERT INTO logs ...")
   # 事務自動提交或回滾
   
   # 避免手動事務管理
   # await self.db_manager.begin()  # 避免
   ```

2. **設置連接超時**
   ```python
   # 在DatabaseManager中
   self.connection_timeout = 30  # 30秒超時
   self.busy_timeout = 10000    # 10秒忙碌超時
   ```

3. **關閉殭屍連接**
   ```bash
   # 重啟機器人
   pkill -f "python main.py"
   python main.py
   ```

### 資料庫遷移失敗

**症狀：**
```
MigrationError: 遷移 003_create_government_tables.sql 失敗
```

**診斷步驟：**

1. **檢查遷移狀態**
   ```bash
   python scripts/migration_validator.py --check-status
   ```

2. **查看遷移日誌**
   ```bash
   cat logs/migration_validation_*.json | jq '.migration_history'
   ```

3. **檢查SQL語法**
   ```bash
   sqlite3 :memory: < scripts/migrations/003_create_government_tables.sql
   ```

**解決方案：**

1. **手動修復遷移**
   ```bash
   # 備份資料庫
   cp data/discord_data.db data/discord_data.db.backup
   
   # 手動執行遷移
   sqlite3 data/discord_data.db < scripts/migrations/003_create_government_tables.sql
   
   # 更新遷移記錄
   python scripts/migration_manager.py --mark-completed 003
   ```

2. **回滾並重試**
   ```bash
   # 恢復備份
   cp data/discord_data.db.backup data/discord_data.db
   
   # 修復遷移文件
   # 重新執行遷移
   python scripts/migration_manager.py --run-pending
   ```

---

## Discord API問題

### API速率限制

**症狀：**
```
discord.errors.HTTPException: 429 Too Many Requests
```

**診斷步驟：**

1. **檢查請求頻率**
   ```python
   # 在服務中添加監控
   import time
   
   class APIRateLimiter:
       def __init__(self):
           self.requests = []
       
       def can_make_request(self):
           now = time.time()
           # 清理1分鐘前的請求
           self.requests = [req for req in self.requests if now - req < 60]
           return len(self.requests) < 50  # Discord限制
   ```

2. **檢查全域限制**
   ```bash
   # 查看日誌中的限制信息
   grep "rate limit" logs/main.log
   ```

**解決方案：**

1. **實施退避策略**
   ```python
   import asyncio
   import random
   
   async def api_request_with_backoff(func, *args, **kwargs):
       for attempt in range(5):
           try:
               return await func(*args, **kwargs)
           except discord.HTTPException as e:
               if e.status == 429:
                   # 指數退避
                   delay = (2 ** attempt) + random.uniform(0, 1)
                   await asyncio.sleep(delay)
               else:
                   raise
       raise Exception("API請求超過重試次數")
   ```

2. **批量處理請求**
   ```python
   async def batch_send_messages(self, messages):
       batch_size = 5
       for i in range(0, len(messages), batch_size):
           batch = messages[i:i + batch_size]
           await asyncio.gather(*[self.send_message(msg) for msg in batch])
           await asyncio.sleep(1)  # 批次間暫停
   ```

### WebSocket連接問題

**症狀：**
```
ConnectionResetError: 連接被遠端主機重置
```

**診斷步驟：**

1. **檢查網路連接**
   ```bash
   ping discord.com
   nslookup gateway.discord.gg
   ```

2. **檢查機器人權限**
   ```python
   # 檢查機器人是否在伺服器中
   guild = bot.get_guild(guild_id)
   if not guild:
       print("機器人不在此伺服器中")
   
   # 檢查權限
   permissions = guild.me.guild_permissions
   print(f"管理員權限: {permissions.administrator}")
   ```

**解決方案：**

1. **自動重連機制**
   ```python
   @bot.event
   async def on_disconnect():
       logging.warning("Discord連接斷開，嘗試重連...")
   
   @bot.event
   async def on_resumed():
       logging.info("Discord連接已恢復")
   ```

2. **健康檢查**
   ```python
   async def check_bot_health():
       try:
           latency = bot.latency
           if latency > 1.0:  # 延遲超過1秒
               logging.warning(f"高延遲檢測: {latency:.2f}s")
           return latency < 5.0
       except:
           return False
   ```

---

## 權限和認證問題

### 用戶權限驗證失敗

**症狀：**
```
ServicePermissionError: 用戶 12345 沒有執行 manage_economy 的權限
```

**診斷步驟：**

1. **檢查用戶角色**
   ```python
   async def debug_user_permissions(interaction):
       user = interaction.user
       guild = interaction.guild
       
       print(f"用戶: {user.display_name}")
       print(f"角色: {[role.name for role in user.roles]}")
       print(f"權限: {user.guild_permissions}")
   ```

2. **檢查權限配置**
   ```bash
   # 檢查政府系統權限配置
   sqlite3 data/discord_data.db "
   SELECT u.user_id, u.display_name, r.role_name, r.permissions 
   FROM government_users u
   JOIN government_roles r ON u.role_id = r.id;"
   ```

**解決方案：**

1. **更新權限映射**
   ```python
   # 在GovernmentService中
   async def update_user_permissions(self, user_id: int, permissions: List[str]):
       await self.db_manager.execute("""
           UPDATE government_users 
           SET permissions = ? 
           WHERE user_id = ?
       """, (json.dumps(permissions), user_id))
   ```

2. **實施權限繼承**
   ```python
   async def check_inherited_permissions(self, user_id: int, action: str) -> bool:
       # 檢查直接權限
       direct_perms = await self.get_user_permissions(user_id)
       if action in direct_perms:
           return True
       
       # 檢查角色權限
       user_roles = await self.get_user_roles(user_id)
       for role in user_roles:
           role_perms = await self.get_role_permissions(role.id)
           if action in role_perms:
               return True
       
       return False
   ```

---

## 效能和記憶體問題

### 記憶體洩漏

**症狀：**
```
系統記憶體使用率持續上升，最終導致程序崩潰
```

**診斷步驟：**

1. **監控記憶體使用**
   ```python
   import psutil
   import gc
   
   def check_memory_usage():
       process = psutil.Process()
       memory_info = process.memory_info()
       print(f"RSS: {memory_info.rss / 1024 / 1024:.2f} MB")
       print(f"VMS: {memory_info.vms / 1024 / 1024:.2f} MB")
       print(f"物件數量: {len(gc.get_objects())}")
   ```

2. **檢查物件引用**
   ```python
   import weakref
   
   # 在服務中使用弱引用
   class ServiceWithWeakRefs:
       def __init__(self):
           self._dependent_services = weakref.WeakSet()
   ```

**解決方案：**

1. **修復循環引用**
   ```python
   # 使用弱引用避免循環引用
   class AchievementService(BaseService):
       def add_economy_service(self, economy_service):
           self._economy_service_ref = weakref.ref(economy_service)
       
       @property
       def economy_service(self):
           if self._economy_service_ref is not None:
               return self._economy_service_ref()
           return None
   ```

2. **定期清理**
   ```python
   async def periodic_cleanup(self):
       while True:
           await asyncio.sleep(300)  # 每5分鐘
           
           # 清理過期快取
           self.clear_expired_cache()
           
           # 強制垃圾回收
           import gc
           collected = gc.collect()
           self.logger.debug(f"垃圾回收釋放了 {collected} 個物件")
   ```

### 查詢效能問題

**症狀：**
```
資料庫查詢響應時間超過1秒
```

**診斷步驟：**

1. **啟用查詢日誌**
   ```python
   # 在DatabaseManager中
   import time
   
   async def execute_with_timing(self, query, params):
       start_time = time.time()
       result = await self.execute(query, params)
       execution_time = time.time() - start_time
       
       if execution_time > 0.1:  # 超過100ms
           self.logger.warning(f"慢查詢: {execution_time:.3f}s - {query}")
       
       return result
   ```

2. **分析查詢計劃**
   ```bash
   sqlite3 data/discord_data.db "EXPLAIN QUERY PLAN 
   SELECT * FROM users WHERE guild_id = 12345;"
   ```

**解決方案：**

1. **添加索引**
   ```sql
   -- 為常用查詢添加索引
   CREATE INDEX IF NOT EXISTS idx_users_guild_id ON users(guild_id);
   CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON user_achievements(user_id);
   CREATE INDEX IF NOT EXISTS idx_economy_user_guild ON economy_accounts(user_id, guild_id);
   ```

2. **優化查詢**
   ```python
   # 避免N+1查詢
   async def get_users_with_achievements(self, guild_id: int):
       # 一次查詢獲取所有資料
       return await self.db_manager.fetch_all("""
           SELECT u.id, u.display_name, 
                  GROUP_CONCAT(a.name) as achievements
           FROM users u
           LEFT JOIN user_achievements ua ON u.id = ua.user_id
           LEFT JOIN achievements a ON ua.achievement_id = a.id
           WHERE u.guild_id = ?
           GROUP BY u.id
       """, (guild_id,))
   ```

---

## 服務整合問題

### 服務間通信失敗

**症狀：**
```
ServiceError: 無法與 EconomyService 通信
```

**診斷步驟：**

1. **檢查服務狀態**
   ```python
   async def check_service_health():
       for service_name in service_registry.list_services():
           service = service_registry.get_service(service_name)
           health = await service.health_check()
           print(f"{service_name}: {health['status']}")
   ```

2. **檢查依賴關係**
   ```python
   def visualize_dependencies():
       import graphviz
       
       dot = graphviz.Digraph()
       for service_name in service_registry.list_services():
           service = service_registry.get_service(service_name)
           dot.node(service_name)
           
           for dep_name in service._dependencies.keys():
               dot.edge(service_name, dep_name)
       
       return dot
   ```

**解決方案：**

1. **實施重試機制**
   ```python
   async def call_service_with_retry(self, service_name: str, method: str, *args, **kwargs):
       service = service_registry.get_service(service_name)
       
       for attempt in range(3):
           try:
               method_func = getattr(service, method)
               return await method_func(*args, **kwargs)
           except Exception as e:
               if attempt == 2:  # 最後一次嘗試
                   raise
               await asyncio.sleep(1 * (attempt + 1))
   ```

2. **服務降級**
   ```python
   async def get_user_balance_with_fallback(self, user_id: int):
       try:
           economy_service = service_registry.get_service("EconomyService")
           return await economy_service.get_balance(user_id)
       except ServiceError:
           # 降級到基本餘額
           self.logger.warning("EconomyService不可用，使用快取餘額")
           return await self.get_cached_balance(user_id)
   ```

---

## 測試相關問題

### 測試資料庫衝突

**症狀：**
```
pytest tests/ 
Database is locked or fixture conflict
```

**診斷步驟：**

1. **檢查測試隔離**
   ```python
   # 確保每個測試使用獨立資料庫
   @pytest.fixture
   async def test_db():
       db_name = f"test_{uuid.uuid4().hex}.db"
       db_manager = DatabaseManager(f"sqlite:///{db_name}")
       await db_manager.initialize()
       yield db_manager
       await db_manager.close()
       os.remove(db_name)
   ```

2. **檢查並發測試**
   ```bash
   # 避免並行測試導致衝突
   pytest tests/ -n 1  # 單線程執行
   ```

**解決方案：**

1. **使用內存資料庫**
   ```python
   @pytest.fixture
   async def memory_db():
       db_manager = DatabaseManager("sqlite:///:memory:")
       await db_manager.initialize()
       yield db_manager
       await db_manager.close()
   ```

2. **清理測試檔案**
   ```bash
   # 清理測試產生的檔案
   find . -name "test_*.db" -delete
   find . -name "*.db-shm" -delete
   find . -name "*.db-wal" -delete
   ```

### 異步測試問題

**症狀：**
```
RuntimeError: Event loop is closed
```

**解決方案：**

1. **正確的異步測試設置**
   ```python
   # pytest.ini 或 pyproject.toml
   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   
   # 測試函數
   @pytest.mark.asyncio
   async def test_async_function():
       result = await some_async_function()
       assert result is not None
   ```

2. **修復事件循環**
   ```python
   # conftest.py
   import asyncio
   import pytest
   
   @pytest.fixture(scope="session")
   def event_loop():
       loop = asyncio.new_event_loop()
       yield loop
       loop.close()
   ```

---

## 部署和環境問題

### Docker容器啟動失敗

**症狀：**
```
docker: Error response from daemon: container exited with code 1
```

**診斷步驟：**

1. **檢查容器日誌**
   ```bash
   docker logs <container_id>
   docker run --rm -it your-image /bin/bash  # 互動模式調試
   ```

2. **檢查環境變數**
   ```bash
   docker run --rm your-image env | grep DISCORD
   ```

**解決方案：**

1. **修復Dockerfile**
   ```dockerfile
   FROM python:3.10-slim
   
   # 設置工作目錄
   WORKDIR /app
   
   # 安裝系統依賴
   RUN apt-get update && apt-get install -y \
       gcc \
       && rm -rf /var/lib/apt/lists/*
   
   # 安裝Python依賴
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   # 複製應用程序
   COPY . .
   
   # 創建資料目錄
   RUN mkdir -p /app/data /app/logs
   
   # 設置健康檢查
   HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
     CMD python -c "import requests; requests.get('http://localhost:8000/health')"
   
   CMD ["python", "main.py"]
   ```

2. **環境變數配置**
   ```yaml
   # docker-compose.yml
   version: '3.8'
   services:
     discord-bot:
       build: .
       environment:
         - DISCORD_TOKEN=${DISCORD_TOKEN}
         - ENVIRONMENT=production
         - DEBUG=false
       volumes:
         - ./data:/app/data
         - ./logs:/app/logs
       restart: unless-stopped
   ```

### 權限問題

**症狀：**
```
PermissionError: [Errno 13] Permission denied: '/app/data'
```

**解決方案：**

1. **修復檔案權限**
   ```dockerfile
   # 在Dockerfile中
   RUN adduser --disabled-password --gecos '' appuser
   RUN chown -R appuser:appuser /app
   USER appuser
   ```

2. **卷權限設置**
   ```bash
   # 在主機上設置正確權限
   sudo chown -R 1000:1000 ./data ./logs
   chmod -R 755 ./data ./logs
   ```

---

## 預防措施

### 監控和警報

1. **健康檢查端點**
   ```python
   from flask import Flask, jsonify
   
   app = Flask(__name__)
   
   @app.route('/health')
   async def health_check():
       try:
           # 檢查資料庫連接
           await db_manager.execute("SELECT 1")
           
           # 檢查Discord連接
           latency = bot.latency
           
           # 檢查服務狀態
           service_health = {}
           for service_name in service_registry.list_services():
               service = service_registry.get_service(service_name)
               service_health[service_name] = await service.health_check()
           
           return jsonify({
               "status": "healthy",
               "timestamp": datetime.now().isoformat(),
               "latency": latency,
               "services": service_health
           })
       except Exception as e:
           return jsonify({
               "status": "unhealthy",
               "error": str(e)
           }), 503
   ```

2. **自動化監控**
   ```bash
   # Cron作業進行健康檢查
   */5 * * * * curl -f http://localhost:8000/health || echo "Bot health check failed" | mail admin@example.com
   ```

### 日誌管理

1. **結構化日誌**
   ```python
   import structlog
   
   logger = structlog.get_logger()
   
   # 記錄結構化日誌
   logger.info(
       "用戶操作",
       user_id=12345,
       action="transfer_currency",
       amount=100,
       success=True,
       duration_ms=150
   )
   ```

2. **日誌聚合**
   ```bash
   # 使用 ELK Stack 或類似工具
   # 配置 Filebeat 收集日誌
   filebeat.inputs:
   - type: log
     paths:
       - /app/logs/*.log
     fields:
       service: discord-bot
       environment: production
   ```

### 定期維護

1. **資料庫優化**
   ```sql
   -- 每週執行的維護查詢
   VACUUM;
   REINDEX;
   ANALYZE;
   
   -- 清理舊日誌
   DELETE FROM logs WHERE created_at < datetime('now', '-30 days');
   ```

2. **系統清理**
   ```bash
   #!/bin/bash
   # cleanup.sh - 定期清理腳本
   
   # 清理日誌檔案
   find /app/logs -name "*.log" -mtime +7 -delete
   
   # 清理臨時檔案
   find /tmp -name "discord_bot_*" -mtime +1 -delete
   
   # 重啟服務（如需要）
   if [ -f /app/.restart_required ]; then
       systemctl restart discord-bot
       rm /app/.restart_required
   fi
   ```

---

## 緊急應對

### 系統崩潰恢復

1. **立即響應清單**
   - [ ] 確認系統狀態
   - [ ] 檢查錯誤日誌
   - [ ] 嘗試重啟服務
   - [ ] 恢復資料庫備份
   - [ ] 通知相關人員

2. **恢復腳本**
   ```bash
   #!/bin/bash
   # emergency_recovery.sh
   
   echo "開始緊急恢復程序..."
   
   # 停止所有相關進程
   pkill -f "python main.py"
   
   # 檢查資料庫完整性
   sqlite3 data/discord_data.db "PRAGMA integrity_check;"
   
   # 如果資料庫損壞，恢復備份
   if [ $? -ne 0 ]; then
       echo "資料庫損壞，恢復最新備份..."
       cp backups/latest_backup.db data/discord_data.db
   fi
   
   # 重啟服務
   python main.py &
   
   echo "恢復程序完成"
   ```

### 資料恢復

1. **增量備份恢復**
   ```bash
   # 恢復到特定時間點
   python scripts/restore_backup.py --timestamp "2025-08-21 14:30:00"
   ```

2. **選擇性資料恢復**
   ```python
   # 恢復特定表或用戶資料
   async def recover_user_data(user_id: int, backup_file: str):
       backup_db = DatabaseManager(f"sqlite:///{backup_file}")
       
       # 從備份恢復用戶資料
       user_data = await backup_db.fetch_one(
           "SELECT * FROM users WHERE id = ?", (user_id,)
       )
       
       if user_data:
           await current_db.execute(
               "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)",
               user_data
           )
   ```

---

## 聯繫支援

如果本指南無法解決您的問題，請：

1. **收集診斷信息**
   - 錯誤訊息和堆疊追蹤
   - 系統環境信息
   - 重現步驟
   - 相關日誌檔案

2. **提交問題報告**
   - 創建詳細的Issue
   - 使用提供的模板
   - 標記適當的標籤

3. **緊急聯繫**
   - 生產環境問題：立即聯繫管理員
   - 資料丟失風險：停止所有操作並尋求幫助

---

**記住**：預防總是比治療更好。定期備份、監控系統健康、保持依賴更新，可以避免大多數問題的發生。