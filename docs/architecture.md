# Discord ROAS Bot 全端架構文件

## 簡介

此文件概述 Discord ROAS Bot v2.2 的完整全端架構，包括後端系統、Discord UI 實作，以及它們的整合。此架構文件作為 AI 驅動開發的唯一真實來源，確保整個技術堆疊的一致性。

此統一方法結合了傳統上分離的後端與前端架構文件，為現代 Discord Bot 應用程式簡化開發流程，這些應用的關注點越來越相互交織。

### 現有專案基礎

**專案類型：** 棕地專案（Brownfield Enhancement）- 基於現有 ROAS Bot v2.1
**原始架構：** Python Discord Bot with PostgreSQL
**升級目標：** v2.2 with 貨幣系統、政府模組、效能優化

## 異動日誌

| 日期 | 版本 | 描述 | 作者 |
|------|------|------|------|
| 2025-01-23 | v1.0 | 初始架構文件 | Winston (Architect) |

## 高階架構

### 技術摘要

Discord ROAS Bot v2.2 採用模組化 Discord Bot 架構，使用 Python 3.12.10 和 discord.py 2.x 作為核心框架。系統採用 Cog 模式組織功能模組，整合 PostgreSQL 15 資料庫進行資料持久化，並透過 Discord 的原生 UI 元件（Embeds、Buttons、Modals）提供使用者介面。架構設計支援水平擴展、模組化開發，並通過 NumPy 優化實現高效能數據處理，滿足社群伺服器管理和經濟系統的 PRD 目標。

### 平台與基礎設施選擇

**平台：** 自建部署 (Self-hosted)
**核心服務：** 
- Discord Bot Hosting (VM/VPS)
- PostgreSQL 15 Database
- uv Package Management
- GitHub Actions CI/CD

**部署主機與區域：** 可配置的 VPS/雲端實例，建議選擇延遲最低的地區

### 版本庫結構

**結構：** 單一版本庫 (Monorepo)
**套件管理工具：** uv (replacing Docker-Compose)
**套件組織：** 按功能模組分層的 cogs 架構

### 高階架構圖

```mermaid
graph TB
    subgraph "Discord Platform"
        DC[Discord Client]
        DG[Discord Gateway]
        DA[Discord API]
    end
    
    subgraph "ROAS Bot Application"
        BM[Bot Main Process]
        
        subgraph "Core Layer"
            BC[Bot Core]
            CFG[Config Manager]
            DB[Database Layer]
            LOG[Logger]
        end
        
        subgraph "Cog Modules"
            ACH[Achievement Cog]
            CUR[Currency Cog]
            GOV[Government Cog]
            ACT[Activity Meter]
            PRO[Protection Cog]
            WEL[Welcome Cog]
            MSG[Message Listener]
            SYN[Sync Data]
        end
        
        subgraph "UI Components"
            EMB[Embeds]
            BTN[Buttons & Modals]
            PNL[Panels & Views]
        end
    end
    
    subgraph "Data Layer"
        PG[(PostgreSQL 15)]
        CACHE[Redis Cache]
    end
    
    subgraph "External Integrations"
        DAPI[Discord API]
        DEPT[departments.json]
    end
    
    DC --> DG
    DG --> DA
    DA --> BM
    BM --> BC
    BC --> CFG
    BC --> DB
    BC --> LOG
    
    ACH --> DB
    CUR --> DB
    GOV --> DB
    GOV --> DEPT
    ACT --> DB
    PRO --> DB
    WEL --> DB
    MSG --> DB
    SYN --> DB
    
    EMB --> DC
    BTN --> DC
    PNL --> DC
    
    DB --> PG
    DB --> CACHE
    
    DAPI --> DA
```

### 架構模式

- **Cog-based Modular Architecture:** 使用 discord.py 的 Cog 系統進行模組化設計 - _理由：_ 實現清晰的關注點分離和熱重載能力
- **Component-based UI:** 可重複使用的 Discord UI 元件與 TypeScript 型別定義 - _理由：_ 在大型程式碼庫中實現可維護性和型別安全
- **Repository Pattern:** 抽象資料存取邏輯 - _理由：_ 支援測試並提供未來資料庫遷移的靈活性
- **Event-driven Architecture:** 基於 Discord 事件的響應式系統 - _理由：_ 與 Discord 平台的自然整合和即時響應能力
- **Service Layer Pattern:** 業務邏輯封裝在服務層 - _理由：_ 分離關注點並提高代碼可測試性

## 技術堆疊

### 技術堆疊表

| 類別 | 技術 | 版本 | 用途 | 理由 |
|------|------|------|------|------|
| 主要語言 | Python | 3.12.10 | Bot 核心開發 | 成熟的生態系統和優秀的 Discord.py 支援 |
| Bot 框架 | discord.py | 2.x | Discord 整合 | 官方推薦的 Python Discord 函式庫 |
| UI 組件庫 | Discord UI Kit | Native | 使用者介面 | 原生 Discord 體驗，無額外依賴 |
| 狀態管理 | Python Classes | Native | 資料狀態 | 簡潔且高效的 OOP 方法 |
| 資料庫 | PostgreSQL | 15 | 主要資料儲存 | 強大的關聯式資料庫，支援複雜查詢 |
| 快取 | Redis | 7.x | 效能快取 | 高速記憶體快取，減少資料庫負載 |
| 檔案儲存 | Local Filesystem | - | 靜態資源 | 簡單且成本效益高的解決方案 |
| 身分驗證 | Discord OAuth2 | - | 使用者認證 | 與 Discord 平台無縫整合 |
| 測試框架 | pytest | 7.x | 單元和整合測試 | Python 生態系統中的標準測試工具 |
| E2E 測試 | pytest-asyncio | - | 異步測試 | 支援 Discord Bot 的異步操作測試 |
| 建置工具 | uv | latest | 套件管理 | 現代 Python 套件管理器，替代 pip |
| 打包工具 | uv build | latest | 專案打包 | 與 uv 整合的建置系統 |
| IaC 工具 | Ansible | - | 部署自動化 | 簡單的伺服器設定管理 |
| CI/CD | GitHub Actions | - | 持續整合部署 | 與 GitHub 原生整合 |
| 監控 | 自建日誌系統 | - | 應用監控 | 簡化的日誌和監控解決方案 |
| 日誌 | Python logging | - | 應用日誌 | Python 標準日誌函式庫 |
| 數值計算 | NumPy | 1.24+ | 效能優化 | 高效能數學運算，特別用於活躍度計算 |

## 資料模型

### 核心業務實體

#### User
**用途：** 代表 Discord 使用者在 ROAS Bot 系統中的資料

**主要屬性：**

- user_id: int64 - Discord 使用者 ID
- username: str - 使用者名稱
- display_name: str - 顯示名稱
- created_at: datetime - 帳戶建立時間
- updated_at: datetime - 最後更新時間

```typescript
interface User {
  user_id: bigint;
  username: string;
  display_name: string;
  created_at: Date;
  updated_at: Date;
}
```

**關係：**

- 一對多：UserCurrency（使用者貨幣餘額）
- 一對多：Achievement（使用者成就）
- 一對多：ActivityRecord（活躍度記錄）

#### Currency
**用途：** 定義自訂貨幣類型與設定

**主要屬性：**

- currency_id: int - 貨幣 ID
- guild_id: int64 - 伺服器 ID
- name: str - 貨幣名稱
- symbol: str - 貨幣符號
- icon_url: str - 貨幣圖示
- is_active: bool - 是否啟用

```typescript
interface Currency {
  currency_id: number;
  guild_id: bigint;
  name: string;
  symbol: string;
  icon_url: string;
  is_active: boolean;
}
```

#### Government
**用途：** 政府部門與職級管理

**主要屬性：**

- department_id: int - 部門 ID
- guild_id: int64 - 伺服器 ID
- name: str - 部門名稱
- description: str - 部門描述
- parent_id: int - 上級部門 ID
- role_id: int64 - 對應 Discord 角色 ID

```typescript
interface Government {
  department_id: number;
  guild_id: bigint;
  name: string;
  description: string;
  parent_id?: number;
  role_id: bigint;
}
```

#### Achievement
**用途：** 成就系統的成就定義與使用者獲得記錄

**主要屬性：**

- achievement_id: int - 成就 ID
- guild_id: int64 - 伺服器 ID
- category: str - 成就分類
- name: str - 成就名稱
- description: str - 成就描述
- criteria: json - 達成條件

```typescript
interface Achievement {
  achievement_id: number;
  guild_id: bigint;
  category: string;
  name: string;
  description: string;
  criteria: Record<string, any>;
}
```

## API 規格

### Discord Bot Commands API

本系統使用 Discord 的 Slash Commands 和 Context Menus 作為主要 API 介面：

```python
# 貨幣系統 Commands
@app_commands.command(name="balance", description="查看貨幣餘額")
async def balance(interaction: discord.Interaction, user: discord.User = None) -> None:
    """查看指定使用者或自己的貨幣餘額"""

@app_commands.command(name="transfer", description="轉帳給其他使用者")
async def transfer(
    interaction: discord.Interaction, 
    recipient: discord.User, 
    amount: int,
    currency: str = "default"
) -> None:
    """執行使用者間的貨幣轉帳"""

@app_commands.command(name="leaderboard", description="貨幣排行榜")
async def leaderboard(interaction: discord.Interaction, currency: str = "default") -> None:
    """顯示貨幣持有量排行榜"""

# 政府系統 Commands
@app_commands.command(name="department", description="部門管理")
async def department(interaction: discord.Interaction, action: str) -> None:
    """管理政府部門結構"""

@app_commands.command(name="assign_role", description="指派政府職務")
async def assign_role(
    interaction: discord.Interaction, 
    user: discord.User, 
    department: str
) -> None:
    """將使用者指派到政府部門"""

# 成就系統 Commands
@app_commands.command(name="achievements", description="查看成就")
async def achievements(interaction: discord.Interaction, user: discord.User = None) -> None:
    """顯示成就列表和進度"""

@app_commands.command(name="activity", description="查看活躍度")
async def activity(interaction: discord.Interaction, user: discord.User = None) -> None:
    """顯示活躍度分數和統計"""
```

### 內部服務 API

```python
# 貨幣服務介面
class CurrencyService:
    async def get_balance(self, user_id: int, guild_id: int, currency_id: int) -> int
    async def transfer(self, from_user: int, to_user: int, amount: int, currency_id: int) -> bool
    async def add_currency(self, user_id: int, amount: int, currency_id: int, reason: str) -> None
    async def get_leaderboard(self, guild_id: int, currency_id: int, limit: int = 10) -> List[Dict]

# 成就服務介面
class AchievementService:
    async def check_achievement(self, user_id: int, event_type: str, event_data: Dict) -> List[Achievement]
    async def award_achievement(self, user_id: int, achievement_id: int) -> bool
    async def get_user_achievements(self, user_id: int, guild_id: int) -> List[Achievement]

# 政府服務介面
class GovernmentService:
    async def create_department(self, guild_id: int, name: str, parent_id: int = None) -> Department
    async def assign_user_to_department(self, user_id: int, department_id: int) -> bool
    async def sync_departments_from_json(self, guild_id: int, departments_data: Dict) -> None
```

## 元件架構

### 核心元件

#### BotCore
**職責：** Discord Bot 的主要控制器，管理事件分發和 Cog 載入

**主要介面：**

- `load_cog(cog_name: str)` - 載入指定 Cog
- `unload_cog(cog_name: str)` - 卸載指定 Cog
- `handle_event(event_type: str, data: Dict)` - 處理 Discord 事件

**依賴：** DatabaseManager, ConfigManager, Logger

**技術堆疊：** discord.py 2.x, asyncio

#### CurrencyCog
**職責：** 處理所有貨幣相關功能，包括餘額查詢、轉帳和排行榜

**主要介面：**

- Slash Commands: `/balance`, `/transfer`, `/leaderboard`
- UI Components: Balance embeds, Transfer modals
- Events: 貨幣變動事件

**依賴：** CurrencyService, DatabaseRepository

**技術堆疊：** discord.py, NumPy (計算優化)

#### GovernmentCog
**職責：** 管理政府部門結構和角色指派

**主要介面：**

- Slash Commands: `/department`, `/assign_role`
- UI Components: Department management panels
- Integration: departments.json 同步

**依賴：** GovernmentService, DiscordRoleManager

**技術堆疊：** discord.py, JSON 處理

#### AchievementCog
**職責：** 成就系統的核心邏輯，包括條件檢查和獎勵發放

**主要介面：**

- Event Handlers: 監聽各種 Discord 事件
- UI Components: Achievement browser, Progress displays
- Achievement Engine: 條件匹配和獎勵邏輯

**依賴：** AchievementService, EventProcessor

**技術堆疊：** discord.py, asyncio 事件處理

#### ActivityMeterCog
**職責：** 追蹤和計算使用者活躍度分數

**主要介面：**

- Score Calculation: NumPy 優化的分數計算
- UI Components: Activity charts, Progress bars
- Decay System: 時間衰減算法

**依賴：** ActivityService, NumPy

**技術堆疊：** discord.py, NumPy, 數據視覺化

### 元件關係圖

```mermaid
graph TB
    subgraph "Discord Bot Application"
        BC[BotCore]
        
        subgraph "Cog Layer"
            CUR[CurrencyCog]
            GOV[GovernmentCog]
            ACH[AchievementCog]
            ACT[ActivityMeterCog]
            PRO[ProtectionCog]
        end
        
        subgraph "Service Layer"
            CS[CurrencyService]
            GS[GovernmentService]
            AS[AchievementService]
            ACS[ActivityService]
        end
        
        subgraph "Data Layer"
            DR[DatabaseRepository]
            CR[CacheRepository]
        end
        
        subgraph "UI Layer"
            EMB[EmbedBuilder]
            VW[ViewBuilder]
            MD[ModalBuilder]
        end
    end
    
    BC --> CUR
    BC --> GOV
    BC --> ACH
    BC --> ACT
    BC --> PRO
    
    CUR --> CS
    GOV --> GS
    ACH --> AS
    ACT --> ACS
    
    CS --> DR
    GS --> DR
    AS --> DR
    ACS --> DR
    
    CS --> CR
    AS --> CR
    
    CUR --> EMB
    CUR --> VW
    GOV --> EMB
    ACH --> EMB
    ACT --> EMB
    
    EMB --> VW
    VW --> MD
```

## 核心工作流程

### 貨幣轉帳流程

```mermaid
sequenceDiagram
    participant U as User
    participant D as Discord
    participant BC as BotCore
    participant CC as CurrencyCog
    participant CS as CurrencyService
    participant DB as Database
    participant C as Cache
    
    U->>D: /transfer @recipient 100 gold
    D->>BC: Interaction Event
    BC->>CC: Route Command
    CC->>CC: Validate Parameters
    CC->>CS: transfer(from_user, to_user, amount, currency)
    CS->>DB: BEGIN TRANSACTION
    CS->>DB: Check sender balance
    DB-->>CS: Balance: 500
    CS->>CS: Validate sufficient funds
    CS->>DB: UPDATE sender balance (-100)
    CS->>DB: UPDATE recipient balance (+100)
    CS->>DB: INSERT transaction_log
    CS->>DB: COMMIT TRANSACTION
    CS->>C: Invalidate cache
    CS-->>CC: Transfer successful
    CC->>CC: Build success embed
    CC->>D: Send response embed
    D-->>U: Transfer completed
```

### 成就檢查流程

```mermaid
sequenceDiagram
    participant E as Event Source
    participant BC as BotCore
    participant AC as AchievementCog
    participant AS as AchievementService
    participant DB as Database
    participant N as NotificationService
    
    E->>BC: Discord Event (message, reaction, etc.)
    BC->>AC: Event notification
    AC->>AS: check_achievement(user_id, event_type, data)
    AS->>DB: Get user's current achievements
    AS->>DB: Get matching criteria
    AS->>AS: Evaluate achievement conditions
    alt Achievement unlocked
        AS->>DB: INSERT user_achievement
        AS->>AS: Calculate rewards
        AS-->>AC: Achievement(s) unlocked
        AC->>N: Send achievement notification
        N->>BC: Display achievement embed
    else No new achievements
        AS-->>AC: No achievements
    end
```

## 資料庫架構

### PostgreSQL 資料庫結構

```sql
-- 核心使用者表
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 貨幣系統
CREATE TABLE currencies (
    currency_id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10),
    icon_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_currencies (
    user_id BIGINT REFERENCES users(user_id),
    currency_id INTEGER REFERENCES currencies(currency_id),
    balance BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, currency_id)
);

CREATE TABLE currency_transactions (
    transaction_id SERIAL PRIMARY KEY,
    from_user_id BIGINT REFERENCES users(user_id),
    to_user_id BIGINT REFERENCES users(user_id),
    currency_id INTEGER REFERENCES currencies(currency_id),
    amount BIGINT NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 政府系統
CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES departments(department_id),
    role_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_departments (
    user_id BIGINT REFERENCES users(user_id),
    department_id INTEGER REFERENCES departments(department_id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by BIGINT REFERENCES users(user_id),
    PRIMARY KEY (user_id, department_id)
);

-- 成就系統
CREATE TABLE achievements (
    achievement_id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    category VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    criteria JSONB NOT NULL,
    rewards JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_achievements (
    user_id BIGINT REFERENCES users(user_id),
    achievement_id INTEGER REFERENCES achievements(achievement_id),
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    progress JSONB,
    PRIMARY KEY (user_id, achievement_id)
);

-- 活躍度系統
CREATE TABLE activity_records (
    record_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    guild_id BIGINT NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    score_delta INTEGER DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引優化
CREATE INDEX idx_user_currencies_balance ON user_currencies(balance DESC);
CREATE INDEX idx_currency_transactions_created_at ON currency_transactions(created_at DESC);
CREATE INDEX idx_activity_records_user_guild ON activity_records(user_id, guild_id);
CREATE INDEX idx_achievements_guild_category ON achievements(guild_id, category);
```

## Discord UI 架構

### 元件組織

Discord Bot 的 UI 基於 Discord 的原生元件系統：

```python
# UI 元件結構
src/cogs/{module}/panel/
├── components/           # 可重複使用的 UI 元件
│   ├── buttons.py       # 按鈕元件
│   ├── modals.py        # 模態對話框
│   └── selects.py       # 選擇器元件
├── embeds/              # Embed 訊息模板
│   ├── info_embed.py    # 資訊顯示
│   ├── error_embed.py   # 錯誤訊息
│   └── success_embed.py # 成功回饋
└── views/               # 主要檢視
    ├── main_view.py     # 主控制面板
    └── admin_view.py    # 管理員面板
```

### UI 元件模板

```python
# 標準 Embed 模板
class BaseEmbed(discord.Embed):
    def __init__(self, title: str, description: str = None, color: int = 0x3498db):
        super().__init__(title=title, description=description, color=color)
        self.timestamp = datetime.utcnow()
        self.set_footer(text="ROAS Bot v2.2", icon_url="...")

# 標準按鈕元件
class BaseButton(discord.ui.Button):
    def __init__(self, label: str, custom_id: str, style: discord.ButtonStyle = discord.ButtonStyle.primary):
        super().__init__(label=label, custom_id=custom_id, style=style)
    
    async def callback(self, interaction: discord.Interaction):
        # 標準回調處理
        await interaction.response.defer()

# 標準檢視
class BaseView(discord.ui.View):
    def __init__(self, timeout: int = 300):
        super().__init__(timeout=timeout)
    
    async def on_timeout(self):
        # 清理邏輯
        for item in self.children:
            item.disabled = True
```

### 狀態管理架構

```python
# Discord Bot 狀態管理
class BotState:
    def __init__(self):
        self.user_sessions: Dict[int, UserSession] = {}
        self.guild_configs: Dict[int, GuildConfig] = {}
        self.active_panels: Dict[int, PanelState] = {}
    
    def get_user_session(self, user_id: int) -> UserSession:
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = UserSession(user_id)
        return self.user_sessions[user_id]

class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.current_panel: Optional[str] = None
        self.session_data: Dict[str, Any] = {}
        self.last_activity = datetime.utcnow()
```

## 服務層架構

### 服務組織

每個 Cog 模組都有對應的服務層，封裝業務邏輯：

```python
# 服務層結構範例
class CurrencyService:
    def __init__(self, db_repository: DatabaseRepository, cache: CacheRepository):
        self.db = db_repository
        self.cache = cache
    
    async def get_balance(self, user_id: int, guild_id: int, currency_id: int) -> int:
        # 快取優先策略
        cache_key = f"balance:{user_id}:{currency_id}"
        cached_balance = await self.cache.get(cache_key)
        
        if cached_balance is not None:
            return int(cached_balance)
        
        # 從資料庫查詢
        balance = await self.db.get_user_currency_balance(user_id, currency_id)
        
        # 更新快取
        await self.cache.set(cache_key, balance, ttl=300)  # 5分鐘 TTL
        
        return balance
    
    async def transfer(self, from_user: int, to_user: int, amount: int, currency_id: int) -> bool:
        async with self.db.transaction():
            # 檢查餘額
            sender_balance = await self.get_balance(from_user, currency_id)
            if sender_balance < amount:
                return False
            
            # 執行轉帳
            await self.db.update_user_balance(from_user, currency_id, -amount)
            await self.db.update_user_balance(to_user, currency_id, amount)
            
            # 記錄交易
            await self.db.create_transaction(from_user, to_user, amount, currency_id, "transfer")
            
            # 清除快取
            await self.cache.delete(f"balance:{from_user}:{currency_id}")
            await self.cache.delete(f"balance:{to_user}:{currency_id}")
            
            return True
```

## 統一專案結構

```plaintext
Discord-ROAS-Bot/
├── .github/                    # GitHub Actions 工作流程
│   └── workflows/
│       ├── ci.yaml
│       ├── test.yaml
│       └── deploy.yaml
├── src/                        # 主要應用程式源碼
│   ├── main.py                 # Bot 入口點
│   ├── core/                   # 核心系統
│   │   ├── bot.py              # Bot 主類別
│   │   ├── config.py           # 配置管理
│   │   ├── database/           # 資料庫層
│   │   │   ├── postgresql.py   # PostgreSQL 連接
│   │   │   ├── models.py       # SQLAlchemy 模型
│   │   │   └── migrations/     # Alembic 遷移
│   │   ├── logger.py           # 日誌系統
│   │   └── utils.py            # 通用工具
│   ├── cogs/                   # Bot 功能模組
│   │   ├── currency/           # 貨幣系統
│   │   │   ├── main/          # 主要邏輯
│   │   │   ├── service/       # 業務服務
│   │   │   ├── database/      # 資料存取
│   │   │   └── panel/         # UI 介面
│   │   ├── government/         # 政府系統
│   │   ├── achievement/        # 成就系統
│   │   ├── activity_meter/     # 活躍度追蹤
│   │   ├── protection/         # 安全防護
│   │   ├── welcome/           # 歡迎系統
│   │   ├── message_listener/  # 訊息監聽
│   │   └── sync_data/         # 資料同步
│   ├── assets/                # 靜態資源
│   │   ├── fonts/             # 字型檔案
│   │   └── backgrounds/       # 背景圖片
│   └── tools/                 # 開發工具
│       └── migration/         # 遷移工具
├── tests/                     # 測試套件
│   ├── unit/                  # 單元測試
│   ├── integration/           # 整合測試
│   └── conftest.py           # pytest 配置
├── config/                    # 配置檔案
│   ├── database.yaml
│   ├── achievement.yaml
│   └── government.yaml
├── docs/                      # 專案文件
│   ├── prd.md
│   ├── front-end-spec.md
│   └── architecture.md
├── scripts/                   # 部署與維護腳本
├── logs/                      # 日誌檔案
├── .env.example              # 環境變數模板
├── pyproject.toml            # uv 專案配置
├── uv.lock                   # 依賴鎖定檔
└── README.md
```

## 開發工作流程

### 本地開發設定

#### 先決條件

```bash
# 安裝 Python 3.12.10
python --version  # 確認版本 3.12.10

# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安裝 PostgreSQL 15
# Ubuntu/Debian:
sudo apt install postgresql-15 postgresql-contrib

# macOS:
brew install postgresql@15

# Windows:
# 下載並安裝 PostgreSQL 15 from https://www.postgresql.org/download/
```

#### 初始設定

```bash
# 複製專案
git clone https://github.com/your-org/discord-roas-bot.git
cd discord-roas-bot

# 安裝依賴
uv sync

# 複製環境變數模板
cp .env.example .env

# 編輯環境變數
# 填入 Discord Bot Token、資料庫連接等
```

#### 開發指令

```bash
# 啟動 Bot（開發模式）
uv run python src/main.py --dev

# 運行所有測試
uv run pytest

# 運行特定模組測試
uv run pytest tests/unit/currency/

# 資料庫遷移
uv run alembic upgrade head

# 代碼格式化
uv run ruff format src/

# 代碼檢查
uv run ruff check src/
```

### 環境變數配置

#### 必要環境變數

```bash
# Bot 配置 (.env)
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_BOT_PREFIX=!
DISCORD_GUILD_ID=your_test_guild_id

# 資料庫配置
DATABASE_URL=postgresql://user:password@localhost:5432/roas_bot
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis 快取
REDIS_URL=redis://localhost:6379/0

# 日誌配置
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log

# 開發模式
DEV_MODE=true
DEBUG=true
```

## 部署架構

### 部署策略

**Bot 部署：**

- **平台：** 自建 VPS/雲端實例
- **建置指令：** `uv build`
- **輸出目錄：** `dist/`
- **套件格式：** Python Wheel (.whl)

**資料庫部署：**

- **平台：** PostgreSQL 15 (同一伺服器或分離)
- **備份策略：** 每日自動備份
- **遷移方法：** Alembic

### CI/CD 流水線

```yaml
# .github/workflows/ci.yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12.10"]
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_roas_bot
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
    - uses: actions/checkout@v4
    - name: Install uv
      uses: astral-sh/setup-uv@v2
    - name: Set up Python
      run: uv python install ${{ matrix.python-version }}
    - name: Install dependencies
      run: uv sync --all-extras --dev
    - name: Run tests
      run: uv run pytest --cov=src --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    - name: Install uv
      uses: astral-sh/setup-uv@v2
    - name: Build package
      run: uv build
    - name: Deploy to production
      run: |
        # 部署腳本 (根據實際部署方式調整)
        scp dist/*.whl user@server:/path/to/bot/
        ssh user@server 'systemctl restart roas-bot'
```

### 環境

| 環境 | Bot URL | 資料庫 URL | 用途 |
|------|---------|-----------|------|
| Development | localhost:本地 | localhost:5432 | 本地開發 |
| Staging | staging.yourserver.com | staging-db.yourserver.com | 預生產測試 |
| Production | prod.yourserver.com | prod-db.yourserver.com | 正式環境 |

## 安全性與效能

### 安全需求

**Bot 安全：**

- 權限最小化原則：僅申請必要的 Discord 權限
- 指令權限控制：管理員功能需要適當角色驗證
- 資料驗證：所有使用者輸入都經過嚴格驗證

**資料庫安全：**

- 輸入驗證：使用 SQLAlchemy ORM 防止 SQL 注入
- 存取控制：資料庫用戶只有必要權限
- 資料加密：敏感資料欄位加密儲存

**身分驗證安全：**

- Discord OAuth2：使用官方身分驗證
- Session 管理：適當的 Session 超時機制
- 權限檢查：每次操作都驗證使用者權限

### 效能優化

**Bot 效能：**

- 連接池：資料庫連接池優化
- NumPy 加速：活躍度計算使用 NumPy 向量化
- 異步處理：全面使用 asyncio 避免阻塞

**資料庫效能：**

- 查詢優化：適當的索引和查詢優化
- 快取策略：Redis 快取熱門資料
- 分頁查詢：大型列表使用分頁減少記憶體使用

## 測試策略

### 測試金字塔

```plaintext
              E2E Tests
             /        \
        Integration Tests
           /            \
      Unit Tests    Component Tests
```

### 測試組織

#### 單元測試

```plaintext
tests/unit/
├── currency/               # 貨幣模組測試
│   ├── test_service.py     # 服務層測試
│   ├── test_repository.py  # 資料存取測試
│   └── test_commands.py    # 指令測試
├── achievement/            # 成就模組測試
│   ├── test_criteria.py    # 條件邏輯測試
│   ├── test_rewards.py     # 獎勵系統測試
│   └── test_events.py      # 事件處理測試
└── core/                   # 核心系統測試
    ├── test_bot.py         # Bot 核心測試
    └── test_database.py    # 資料庫層測試
```

#### 整合測試

```plaintext
tests/integration/
├── test_currency_flow.py   # 貨幣系統完整流程
├── test_achievement_unlock.py # 成就解鎖流程
└── test_database_migration.py # 資料庫遷移測試
```

#### E2E 測試

```plaintext
tests/e2e/
├── test_user_journey.py    # 完整使用者體驗測試
└── test_admin_workflow.py  # 管理員工作流程測試
```

### 測試範例

#### 單元測試範例

```python
# tests/unit/currency/test_service.py
import pytest
from unittest.mock import AsyncMock
from src.cogs.currency.service.currency_service import CurrencyService

@pytest.mark.asyncio
async def test_transfer_sufficient_balance():
    # Arrange
    mock_db = AsyncMock()
    mock_cache = AsyncMock()
    mock_db.get_user_currency_balance.return_value = 1000
    
    service = CurrencyService(mock_db, mock_cache)
    
    # Act
    result = await service.transfer(
        from_user=12345, 
        to_user=67890, 
        amount=500, 
        currency_id=1
    )
    
    # Assert
    assert result is True
    mock_db.update_user_balance.assert_called()
```

#### 整合測試範例

```python
# tests/integration/test_currency_flow.py
import pytest
from src.core.bot import create_bot

@pytest.mark.asyncio
async def test_complete_transfer_flow():
    # Arrange
    bot = create_bot(test_mode=True)
    
    # 模擬 Discord 互動
    interaction = create_mock_interaction(
        command="/transfer",
        options={"recipient": "@testuser", "amount": 100}
    )
    
    # Act
    await bot.process_interaction(interaction)
    
    # Assert
    # 驗證轉帳完成和通知發送
    assert interaction.response_sent
    assert "轉帳成功" in interaction.response_content
```

## 編碼標準

### 關鍵全端規則

- **型別定義：** 所有公共介面必須有完整的型別標註
- **錯誤處理：** 所有 Discord 指令必須有統一的錯誤處理機制
- **日誌記錄：** 所有業務操作必須記錄適當的日誌
- **快取策略：** 頻繁查詢的資料必須使用快取，TTL 不超過 5 分鐘
- **資料庫交易：** 涉及多表操作必須使用資料庫交易
- **使用者驗證：** 所有管理員功能必須檢查使用者權限

### 命名慣例

| 元素 | Discord Bot | 資料庫 | 範例 |
|------|-------------|--------|------|
| Cog 類別 | PascalCase | - | `CurrencyCog` |
| 指令名稱 | kebab-case | - | `/transfer-money` |
| 服務方法 | snake_case | - | `get_user_balance()` |
| 資料庫表格 | - | snake_case | `user_currencies` |
| 資料庫欄位 | - | snake_case | `created_at` |

## 錯誤處理策略

### 錯誤流程

```mermaid
sequenceDiagram
    participant U as User
    participant C as Command Handler
    participant S as Service
    participant D as Database
    participant L as Logger
    participant N as Notifier
    
    U->>C: Discord Command
    C->>S: Business Logic Call
    S->>D: Database Operation
    D-->>S: Error Occurred
    S->>L: Log Error Details
    S->>S: Determine Error Type
    S-->>C: Formatted Error Response
    C->>N: User-friendly Message
    N-->>U: Error Notification
```

### 錯誤回應格式

```python
class BotError(Exception):
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        super().__init__(message)

# 標準錯誤類型
class InsufficientFundsError(BotError):
    def __init__(self, required: int, available: int):
        super().__init__(
            message="餘額不足以完成此操作",
            error_code="INSUFFICIENT_FUNDS",
            details={"required": required, "available": available}
        )
```

### Discord 錯誤處理

```python
@discord.app_commands.error
async def command_error_handler(interaction: discord.Interaction, error: Exception):
    """統一的指令錯誤處理器"""
    if isinstance(error, BotError):
        embed = discord.Embed(
            title="操作失敗",
            description=error.message,
            color=0xe74c3c
        )
        embed.add_field(name="錯誤代碼", value=error.error_code)
    else:
        # 記錄未預期的錯誤
        logger.error(f"Unexpected error: {error}", exc_info=True)
        embed = discord.Embed(
            title="系統錯誤",
            description="發生未預期的錯誤，請稍後再試",
            color=0xe74c3c
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
```

## 監控與可觀測性

### 監控堆疊

- **Bot 監控：** 自建日誌系統 + Python logging
- **資料庫監控：** PostgreSQL 內建統計 + 自訂查詢監控
- **錯誤追蹤：** 結構化日誌記錄
- **效能監控：** 響應時間和記憶體使用追蹤

### 關鍵指標

**Bot 指標：**

- 指令執行次數和成功率
- 平均回應時間
- 活躍使用者數量
- 錯誤發生頻率

**資料庫指標：**

- 查詢執行時間
- 連接池使用率
- 慢查詢記錄
- 資料庫大小成長

**系統指標：**

- 記憶體使用量
- CPU 使用率
- 網路延遲
- 磁碟空間使用

### 日誌範例

```python
# 結構化日誌記錄
logger.info(
    "Currency transfer completed",
    extra={
        "event_type": "currency_transfer",
        "from_user_id": from_user,
        "to_user_id": to_user,
        "amount": amount,
        "currency_id": currency_id,
        "transaction_id": transaction_id,
        "execution_time_ms": execution_time
    }
)
```

---

## 檢查清單結果報告

此架構文件已完成，涵蓋了 Discord ROAS Bot v2.2 的完整全端架構設計。文件包含了從高階架構到具體實作細節的所有必要資訊，可作為 AI 驅動開發的權威參考。

主要完成項目：
✅ 高階架構與技術摘要
✅ 完整技術堆疊定義
✅ 資料模型與 API 規格
✅ 元件架構與工作流程
✅ 資料庫架構設計
✅ Discord UI 架構
✅ 統一專案結構
✅ 開發與部署工作流程
✅ 安全性與效能考量
✅ 測試策略與編碼標準
✅ 錯誤處理與監控策略

此架構文件現已準備就緒，可支援 v2.2 的貨幣系統、政府模組開發，以及現有系統的優化工作。
