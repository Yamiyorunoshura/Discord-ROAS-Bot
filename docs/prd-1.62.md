# Discord ADR Bot v1.62 產品需求文檔 (PRD) - 優化版本
## 📋 專案概述

### 核心目標
基於現有的 Discord ADR Bot v1.6 架構，實現三個關鍵功能的完善和優化：

1. **智能虛擬環境管理** - 自動檢測、創建和管理 Python 虛擬環境
2. **模塊面板系統完善** - 統一化所有模塊的用戶界面面板
3. **全面除錯與測試系統** - 建立完整的錯誤處理、測試和監控機制

---

## 🚨 緊急修復需求 (優先級：最高)

### 現狀問題分析與解決方案

#### 🔧 技術架構現狀
- **現有基礎**: BasePanelView 已建立統一面板架構
- **錯誤處理**: 統一的 ErrorHandler 和 error_handler 裝飾器
- **模塊結構**: 標準化的 Cog 結構和依賴注入

#### 問題 1: Anti-Link 面板錯誤
**錯誤**: `'AntiLink' object has no attribute 'get_config'`
**根因分析**: AntiLink 類繼承自 ProtectionCog，但缺少直接的 get_config 方法
**解決方案**:
```python
# 位置: cogs/protection/anti_link/main/main.py
class AntiLink(ProtectionCog):
    async def get_config(self, guild_id: int, key: str, default: Any = None) -> Any:
        """獲取配置項目 - 面板系統適配方法"""
        return await self.db.get_config(guild_id, key, default)
    
    async def set_config(self, guild_id: int, key: str, value: Any) -> None:
        """設置配置項目 - 面板系統適配方法"""
        await self.db.set_config(guild_id, key, str(value))
```

#### 問題 2: 面板指令註冊缺失
**受影響模塊**: Activity Meter, Sync Data
**解決策略**: 統一面板指令註冊模式

```python
# 標準面板指令實現模板
@app_commands.command(name="模塊面板", description="開啟模塊設定面板")
@app_commands.describe()
async def module_panel(self, interaction: discord.Interaction):
    """模塊設定面板指令"""
    # 權限檢查
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ 需要「管理伺服器」權限才能使用此指令",
            ephemeral=True
        )
        return
    
    # 錯誤處理包裝
    with self.error_handler.handle_error(
        interaction, 
        "面板載入失敗", 
        ErrorCodes.MODULE_ERROR[0]
    ):
        from ..panel.main_view import ModulePanelView
        view = ModulePanelView(self, interaction.guild_id, interaction.user.id)
        embed = await view.get_current_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
```

### 🎯 統一面板架構規範

#### 面板視圖基類擴展
```python
# 位置: cogs/core/base_cog.py (擴展 BasePanelView)
class StandardPanelView(BasePanelView):
    """標準化面板架構 - 所有模塊面板的基類"""
    
    # 必需實現的面板類型
    REQUIRED_PANELS = ["main", "settings", "stats"]
    OPTIONAL_PANELS = ["preview", "history", "whitelist", "blacklist", "advanced"]
    
    def __init__(self, cog, guild_id: int, user_id: int, **kwargs):
        super().__init__(**kwargs)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.current_panel = "main"
        self.page_number = 0
        
        # 初始化標準組件
        self._setup_standard_components()
    
    def _setup_standard_components(self):
        """設置標準組件"""
        # 面板選擇器
        if len(self.get_available_panels()) > 1:
            self.add_item(self.create_panel_selector())
        
        # 標準按鈕
        self._add_panel_specific_buttons()
        self._add_common_buttons()
    
    @abstractmethod
    def get_available_panels(self) -> List[str]:
        """返回可用的面板列表"""
        pass
    
    @abstractmethod
    async def get_panel_embed(self, panel_name: str) -> discord.Embed:
        """獲取指定面板的 Embed"""
        pass
```

#### 面板組件標準化
```python
# 標準按鈕配置
STANDARD_BUTTON_CONFIG = {
    "enable": {"label": "啟用", "style": "success", "emoji": "✅", "row": 0},
    "disable": {"label": "停用", "style": "danger", "emoji": "❌", "row": 0},
    "settings": {"label": "設定", "style": "primary", "emoji": "⚙️", "row": 1},
    "stats": {"label": "統計", "style": "secondary", "emoji": "📊", "row": 1},
    "refresh": {"label": "重新整理", "style": "secondary", "emoji": "🔄", "row": 2},
    "close": {"label": "關閉", "style": "danger", "emoji": "❌", "row": 2}
}

# 標準選擇器配置
STANDARD_SELECTOR_CONFIG = {
    "panel_switcher": {
        "placeholder": "選擇面板...",
        "row": 0,
        "max_values": 1
    }
}
```

---

## 🎯 需求 1：智能虛擬環境管理系統

### 1.1 技術實現規格

#### 1.1.1 虛擬環境管理器設計
```python
# 位置: cogs/core/venv_manager.py
import os
import sys
import subprocess
import site
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

class VirtualEnvironmentManager:
    """虛擬環境管理器"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.logger = logging.getLogger("venv_manager")
        
        # 虛擬環境路徑優先級
        self.venv_paths = [
            self.project_root / "venv",
            self.project_root / ".venv", 
            self.project_root / "env"
        ]
    
    def detect_current_environment(self) -> Dict[str, Any]:
        """檢測當前環境狀態"""
        return {
            "in_venv": sys.prefix != sys.base_prefix,
            "python_version": sys.version_info,
            "venv_path": os.environ.get('VIRTUAL_ENV'),
            "site_packages": site.getsitepackages()
        }
    
    async def ensure_virtual_environment(self) -> bool:
        """確保虛擬環境存在並激活"""
        env_status = self.detect_current_environment()
        
        if env_status["in_venv"]:
            self.logger.info("✅ 已在虛擬環境中運行")
            return True
        
        # 尋找現有虛擬環境
        existing_venv = self._find_existing_venv()
        if existing_venv:
            return self._activate_venv(existing_venv)
        
        # 創建新的虛擬環境
        return await self._create_and_activate_venv()
    
    def _find_existing_venv(self) -> Optional[Path]:
        """尋找現有的虛擬環境"""
        for venv_path in self.venv_paths:
            if self._is_valid_venv(venv_path):
                return venv_path
        return None
    
    def _is_valid_venv(self, venv_path: Path) -> bool:
        """檢查是否為有效的虛擬環境"""
        if not venv_path.exists():
            return False
        
        # 檢查關鍵文件
        if os.name == "nt":  # Windows
            return (venv_path / "Scripts" / "python.exe").exists()
        else:  # Unix-like
            return (venv_path / "bin" / "python").exists()
    
    async def _create_and_activate_venv(self) -> bool:
        """創建並激活虛擬環境"""
        venv_path = self.venv_paths[0]  # 使用第一個路徑作為默認
        
        try:
            # 創建虛擬環境
            subprocess.run([
                sys.executable, "-m", "venv", str(venv_path)
            ], check=True)
            
            self.logger.info(f"✅ 虛擬環境創建成功: {venv_path}")
            
            # 激活虛擬環境
            return self._activate_venv(venv_path)
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ 虛擬環境創建失敗: {e}")
            return False
    
    def _activate_venv(self, venv_path: Path) -> bool:
        """激活虛擬環境"""
        try:
            if os.name == "nt":  # Windows
                site_packages = venv_path / "Lib" / "site-packages"
            else:  # Unix-like
                # 找到 Python 版本目錄
                lib_dir = venv_path / "lib"
                py_dirs = [d for d in lib_dir.iterdir() if d.name.startswith("python")]
                if not py_dirs:
                    return False
                site_packages = py_dirs[0] / "site-packages"
            
            if site_packages.exists():
                # 將虛擬環境添加到 Python 路徑
                sys.path.insert(0, str(site_packages))
                site.main()
                
                self.logger.info(f"✅ 虛擬環境激活成功: {venv_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 虛擬環境激活失敗: {e}")
        
        return False
    
    async def install_dependencies(self, requirements_file: str = "requirement.txt") -> bool:
        """安裝依賴包"""
        req_path = self.project_root / requirements_file
        if not req_path.exists():
            self.logger.warning(f"⚠️ 需求文件不存在: {req_path}")
            return False
        
        try:
            # 獲取 pip 路徑
            pip_path = self._get_pip_path()
            if not pip_path:
                return False
            
            # 安裝依賴
            subprocess.run([
                pip_path, "install", "-r", str(req_path)
            ], check=True)
            
            self.logger.info("✅ 依賴安裝成功")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ 依賴安裝失敗: {e}")
            return False
    
    def _get_pip_path(self) -> Optional[str]:
        """獲取 pip 可執行文件路徑"""
        # 嘗試不同的 pip 路徑
        pip_commands = ["pip", "pip3", sys.executable + " -m pip"]
        
        for pip_cmd in pip_commands:
            try:
                subprocess.run([pip_cmd, "--version"], 
                             check=True, 
                             capture_output=True)
                return pip_cmd
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        return None
```

#### 1.1.2 主程式集成
```python
# 位置: main.py (修改 _activate_venv 函數)
from cogs.core.venv_manager import VirtualEnvironmentManager

async def _activate_venv():
    """自動檢測並啟用虛擬環境 - 增強版"""
    venv_manager = VirtualEnvironmentManager(PROJECT_ROOT)
    
    # 檢測當前環境
    env_status = venv_manager.detect_current_environment()
    
    if env_status["in_venv"]:
        print("✅ [環境] 已在虛擬環境中運行")
        print(f"   📁 虛擬環境路徑: {env_status['venv_path']}")
        return True
    
    print("🔍 [環境] 檢測虛擬環境...")
    
    # 確保虛擬環境
    success = await venv_manager.ensure_virtual_environment()
    
    if success:
        # 安裝依賴
        print("📦 [環境] 檢查依賴...")
        await venv_manager.install_dependencies()
        return True
    else:
        print("⚠️  [環境] 虛擬環境設置失敗，使用系統 Python")
        print("   💡 建議：手動創建虛擬環境以避免依賴問題")
        return False
```

---

## 🎯 需求 2：模塊面板系統完善

### 2.1 實現策略

#### 2.1.1 Activity Meter 面板實現
```python
# 位置: cogs/activity_meter/main/main.py (添加面板指令)
@app_commands.command(name="活躍度面板", description="開啟活躍度系統設定面板")
async def activity_panel(self, interaction: discord.Interaction):
    """活躍度系統設定面板"""
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ 需要「管理伺服器」權限才能使用此指令",
            ephemeral=True
        )
        return
    
    with error_handler.handle_error(
        interaction, 
        "活躍度面板載入失敗", 
        ErrorCodes.MODULE_ERROR[0]
    ):
        from ..panel.main_view import ActivityPanelView
        view = ActivityPanelView(self.bot, interaction.guild_id, interaction.user.id)
        await view.start(interaction)
```

#### 2.1.2 Sync Data 面板增強
```python
# 位置: cogs/sync_data/main/main.py (添加面板指令)
@app_commands.command(name="資料同步面板", description="開啟資料同步管理面板")
async def sync_panel(self, interaction: discord.Interaction):
    """資料同步管理面板"""
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ 需要「管理伺服器」權限才能使用此指令",
            ephemeral=True
        )
        return
    
    with error_handler.handle_error(
        interaction,
        "資料同步面板載入失敗",
        ErrorCodes.MODULE_ERROR[0]
    ):
        from ..panel.main_view import SyncDataMainView
        view = SyncDataMainView(self, interaction.user.id, interaction.guild)
        embed = await view.get_current_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
```

#### 2.1.3 Anti-Spam 面板擴展
```python
# 位置: cogs/protection/anti_spam/panel/main_view.py
class AntiSpamMainView(StandardPanelView):
    """反垃圾訊息保護面板"""
    
    def get_available_panels(self) -> List[str]:
        return ["main", "settings", "whitelist", "patterns", "stats", "history"]
    
    async def get_panel_embed(self, panel_name: str) -> discord.Embed:
        """獲取面板 Embed"""
        embed_map = {
            "main": self._create_main_embed,
            "settings": self._create_settings_embed,
            "whitelist": self._create_whitelist_embed,
            "patterns": self._create_patterns_embed,
            "stats": self._create_stats_embed,
            "history": self._create_history_embed
        }
        
        embed_func = embed_map.get(panel_name, self._create_main_embed)
        return await embed_func()
    
    async def _create_main_embed(self) -> discord.Embed:
        """主面板 Embed"""
        # 獲取模塊狀態
        enabled = await self.cog.get_config(self.guild_id, "enabled", "false") == "true"
        
        embed = discord.Embed(
            title="🛡️ 反垃圾訊息保護",
            description="防止垃圾訊息和洗版行為",
            color=discord.Color.green() if enabled else discord.Color.red()
        )
        
        # 狀態信息
        status = "🟢 已啟用" if enabled else "🔴 已停用"
        embed.add_field(name="📊 狀態", value=status, inline=True)
        
        # 統計信息
        stats = await self.cog.get_stats(self.guild_id)
        embed.add_field(
            name="📈 統計",
            value=f"攔截: {stats.get('blocked', 0)}\n誤報: {stats.get('false_positives', 0)}",
            inline=True
        )
        
        return embed
```

---

## 🎯 需求 3：全面除錯與測試系統

### 3.1 錯誤處理系統增強

#### 3.1.1 統一錯誤代碼系統
```python
# 位置: cogs/core/error_codes.py
from enum import IntEnum

class ErrorCategory(IntEnum):
    """錯誤分類"""
    STARTUP = 1000       # 啟動相關錯誤
    ENVIRONMENT = 1100   # 環境相關錯誤
    DATABASE = 1200      # 資料庫錯誤
    NETWORK = 1300       # 網路錯誤
    PERMISSION = 1400    # 權限錯誤
    MODULE = 1500        # 模塊錯誤
    UI = 1600           # 界面錯誤
    INTEGRATION = 1700   # 整合錯誤

class ErrorCode(IntEnum):
    """具體錯誤代碼"""
    # 啟動錯誤
    STARTUP_TOKEN_INVALID = 1001
    STARTUP_DEPENDENCY_MISSING = 1002
    STARTUP_CONFIG_ERROR = 1003
    
    # 環境錯誤
    VENV_CREATION_FAILED = 1101
    VENV_ACTIVATION_FAILED = 1102
    DEPENDENCY_INSTALL_FAILED = 1103
    
    # 資料庫錯誤
    DB_CONNECTION_FAILED = 1201
    DB_QUERY_FAILED = 1202
    DB_MIGRATION_FAILED = 1203
    
    # 模塊錯誤
    MODULE_LOAD_FAILED = 1501
    MODULE_CONFIG_ERROR = 1502
    MODULE_PANEL_ERROR = 1503
```

#### 3.1.2 智能錯誤恢復系統
```python
# 位置: cogs/core/error_recovery.py
import asyncio
import logging
from typing import Dict, Callable, Any, Optional
from enum import Enum

class RecoveryStrategy(Enum):
    """恢復策略"""
    RETRY = "retry"
    FALLBACK = "fallback"
    RESTART = "restart"
    IGNORE = "ignore"

class ErrorRecoveryManager:
    """錯誤恢復管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger("error_recovery")
        self.recovery_strategies: Dict[int, RecoveryStrategy] = {}
        self.recovery_handlers: Dict[RecoveryStrategy, Callable] = {}
        self._setup_default_strategies()
    
    def _setup_default_strategies(self):
        """設置默認恢復策略"""
        # 網路錯誤 - 重試
        self.recovery_strategies.update({
            ErrorCode.NETWORK_TIMEOUT: RecoveryStrategy.RETRY,
            ErrorCode.NETWORK_CONNECTION_FAILED: RecoveryStrategy.RETRY,
        })
        
        # 資料庫錯誤 - 重試後回退
        self.recovery_strategies.update({
            ErrorCode.DB_CONNECTION_FAILED: RecoveryStrategy.RETRY,
            ErrorCode.DB_QUERY_FAILED: RecoveryStrategy.FALLBACK,
        })
        
        # 模塊錯誤 - 重啟模塊
        self.recovery_strategies.update({
            ErrorCode.MODULE_LOAD_FAILED: RecoveryStrategy.RESTART,
            ErrorCode.MODULE_PANEL_ERROR: RecoveryStrategy.FALLBACK,
        })
    
    async def handle_error(self, error_code: int, context: Dict[str, Any]) -> bool:
        """處理錯誤並嘗試恢復"""
        strategy = self.recovery_strategies.get(error_code, RecoveryStrategy.IGNORE)
        
        self.logger.info(f"錯誤恢復: 代碼 {error_code}, 策略 {strategy.value}")
        
        if strategy == RecoveryStrategy.RETRY:
            return await self._retry_operation(context)
        elif strategy == RecoveryStrategy.FALLBACK:
            return await self._fallback_operation(context)
        elif strategy == RecoveryStrategy.RESTART:
            return await self._restart_component(context)
        else:
            return False
    
    async def _retry_operation(self, context: Dict[str, Any]) -> bool:
        """重試操作"""
        max_retries = context.get("max_retries", 3)
        retry_delay = context.get("retry_delay", 1.0)
        operation = context.get("operation")
        
        if not operation:
            return False
        
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(retry_delay * (attempt + 1))
                result = await operation()
                self.logger.info(f"重試成功: 第 {attempt + 1} 次嘗試")
                return True
            except Exception as e:
                self.logger.warning(f"重試失敗: 第 {attempt + 1} 次嘗試 - {e}")
        
        return False
```

### 3.2 自動化測試框架

#### 3.2.1 測試配置
```python
# 位置: tests/config.py
import os
import pytest
from typing import Dict, Any

# 測試環境配置
TEST_CONFIG = {
    "database": {
        "path": ":memory:",  # 使用內存資料庫
        "timeout": 30.0
    },
    "discord": {
        "mock_guild_id": 123456789,
        "mock_user_id": 987654321,
        "mock_channel_id": 111222333
    },
    "modules": {
        "load_timeout": 10.0,
        "test_data_path": "tests/data"
    }
}

# 測試標記
pytest_marks = {
    "unit": pytest.mark.asyncio,
    "integration": pytest.mark.asyncio,
    "slow": pytest.mark.slow,
    "database": pytest.mark.database
}
```

#### 3.2.2 面板測試框架
```python
# 位置: tests/panel_test_framework.py
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock
from typing import Type, Any, Dict

class PanelTestFramework:
    """面板測試框架"""
    
    @staticmethod
    def create_mock_interaction(
        guild_id: int = 123456789,
        user_id: int = 987654321,
        user_permissions: Dict[str, bool] = None
    ) -> discord.Interaction:
        """創建模擬的 Discord Interaction"""
        interaction = MagicMock(spec=discord.Interaction)
        
        # 設置基本屬性
        interaction.guild_id = guild_id
        interaction.user.id = user_id
        interaction.guild.id = guild_id
        
        # 設置權限
        permissions = user_permissions or {"manage_guild": True}
        interaction.user.guild_permissions = MagicMock()
        for perm, value in permissions.items():
            setattr(interaction.user.guild_permissions, perm, value)
        
        # 設置異步方法
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.response.edit_message = AsyncMock()
        
        return interaction
    
    @staticmethod
    async def test_panel_initialization(panel_class: Type, cog_mock: Any):
        """測試面板初始化"""
        panel = panel_class(cog_mock, 123456789, 987654321)
        
        # 檢查基本屬性
        assert hasattr(panel, 'cog')
        assert hasattr(panel, 'guild_id')
        assert hasattr(panel, 'user_id')
        assert hasattr(panel, 'current_panel')
        
        # 檢查組件
        assert len(panel.children) > 0
        
        return panel
    
    @staticmethod
    async def test_panel_embed_generation(panel: Any):
        """測試面板 Embed 生成"""
        if hasattr(panel, 'get_current_embed'):
            embed = await panel.get_current_embed()
            assert isinstance(embed, discord.Embed)
            assert embed.title is not None
            assert embed.description is not None
```

#### 3.2.3 模塊測試模板
```python
# 位置: tests/templates/module_test_template.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from tests.panel_test_framework import PanelTestFramework

class ModuleTestTemplate:
    """模塊測試模板"""
    
    @pytest.fixture
    async def mock_bot(self):
        """模擬 Bot"""
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        bot.remove_cog = AsyncMock()
        return bot
    
    @pytest.fixture
    async def mock_database(self):
        """模擬資料庫"""
        db = MagicMock()
        db.init_db = AsyncMock()
        db.get_config = AsyncMock(return_value="default_value")
        db.set_config = AsyncMock()
        return db
    
    @pytest.fixture
    async def module_cog(self, mock_bot, mock_database):
        """模塊 Cog 實例"""
        # 子類需要實現此方法
        raise NotImplementedError("子類必須實現 module_cog fixture")
    
    async def test_cog_initialization(self, module_cog):
        """測試 Cog 初始化"""
        assert module_cog is not None
        assert hasattr(module_cog, 'bot')
        
    async def test_panel_command(self, module_cog):
        """測試面板指令"""
        interaction = PanelTestFramework.create_mock_interaction()
        
        # 查找面板指令
        panel_commands = [cmd for cmd in module_cog.get_app_commands() 
                         if "面板" in cmd.name]
        assert len(panel_commands) > 0
        
        # 測試指令執行
        panel_command = panel_commands[0]
        await panel_command.callback(module_cog, interaction)
        
        # 驗證響應
        interaction.response.send_message.assert_called_once()
```

### 3.3 性能監控系統

#### 3.3.1 性能指標收集器
```python
# 位置: cogs/core/performance_monitor.py
import time
import psutil
import asyncio
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from collections import defaultdict, deque

@dataclass
class PerformanceMetric:
    """性能指標數據類"""
    timestamp: float
    metric_name: str
    value: float
    metadata: Dict[str, Any] = None

class PerformanceMonitor:
    """性能監控器"""
    
    def __init__(self, max_history: int = 1000):
        self.logger = logging.getLogger("performance")
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.thresholds: Dict[str, float] = {}
        self._setup_default_thresholds()
    
    def _setup_default_thresholds(self):
        """設置默認閾值"""
        self.thresholds.update({
            "response_time": 2.0,      # 2秒響應時間
            "memory_usage": 500.0,     # 500MB 內存使用
            "cpu_usage": 80.0,         # 80% CPU 使用率
            "database_query_time": 1.0  # 1秒資料庫查詢時間
        })
    
    def record_metric(self, name: str, value: float, metadata: Dict[str, Any] = None):
        """記錄性能指標"""
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_name=name,
            value=value,
            metadata=metadata or {}
        )
        
        self.metrics[name].append(metric)
        
        # 檢查閾值
        threshold = self.thresholds.get(name)
        if threshold and value > threshold:
            self.logger.warning(f"性能警告: {name} = {value:.2f} (閾值: {threshold})")
    
    def get_system_metrics(self) -> Dict[str, float]:
        """獲取系統性能指標"""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used_mb": psutil.virtual_memory().used / 1024 / 1024,
            "disk_usage_percent": psutil.disk_usage('/').percent
        }
    
    async def start_monitoring(self, interval: float = 60.0):
        """開始性能監控"""
        while True:
            try:
                metrics = self.get_system_metrics()
                for name, value in metrics.items():
                    self.record_metric(name, value)
                
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"性能監控錯誤: {e}")
                await asyncio.sleep(interval)
```

---

## 🔧 實現路徑指導

### 階段 0: 緊急修復 (1-2 天)
1. **修復 Anti-Link 配置方法** (4 小時)
   - 添加 `get_config` 和 `set_config` 方法
   - 測試面板載入功能
   
2. **註冊缺失面板指令** (4 小時)
   - Activity Meter 面板指令
   - Sync Data 面板指令
   - 測試指令註冊和響應

3. **統一中文指令名稱** (2 小時)
   - 更新所有面板指令名稱
   - 更新指令描述

### 階段 1: 虛擬環境管理 (3-5 天)
1. **實現 VirtualEnvironmentManager** (1 天)
   - 環境檢測邏輯
   - 創建和激活功能
   - 依賴安裝邏輯

2. **集成到主程式** (1 天)
   - 修改 main.py 啟動流程
   - 添加錯誤處理
   - 測試跨平台兼容性

3. **測試和優化** (1-2 天)
   - 單元測試
   - 集成測試
   - 性能優化

### 階段 2: 面板系統完善 (5-7 天)
1. **擴展 BasePanelView** (2 天)
   - StandardPanelView 實現
   - 統一組件系統
   - 錯誤處理集成

2. **完善各模塊面板** (3 天)
   - Anti-Spam 面板擴展
   - Welcome 面板增強
   - Sync Data 面板完善

3. **UI 統一化** (1-2 天)
   - 樣式標準化
   - 交互模式統一
   - 響應式設計

### 階段 3: 測試系統建立 (3-5 天)
1. **錯誤處理增強** (2 天)
   - 統一錯誤代碼
   - 智能恢復系統
   - 性能監控

2. **測試框架建立** (2 天)
   - 面板測試框架
   - 模塊測試模板
   - 自動化測試

3. **監控系統** (1 天)
   - 性能指標收集
   - 健康檢查
   - 警報系統

---

## 📊 驗收標準與測試指導

### 緊急修復驗收
```python
# 測試腳本: tests/emergency_fixes_test.py
async def test_anti_link_panel_loading():
    """測試 Anti-Link 面板載入"""
    # 創建模擬環境
    cog = create_mock_anti_link_cog()
    interaction = create_mock_interaction()
    
    # 測試面板指令
    await cog.link_panel(interaction)
    
    # 驗證響應
    assert interaction.response.send_message.called
    args, kwargs = interaction.response.send_message.call_args
    assert "embed" in kwargs
    assert "view" in kwargs

async def test_activity_meter_panel_registration():
    """測試 Activity Meter 面板指令註冊"""
    cog = create_mock_activity_meter_cog()
    commands = cog.get_app_commands()
    
    panel_commands = [cmd for cmd in commands if "活躍度面板" in cmd.name]
    assert len(panel_commands) == 1
```

### 虛擬環境管理驗收
```python
# 測試腳本: tests/venv_manager_test.py
async def test_venv_detection():
    """測試虛擬環境檢測"""
    manager = VirtualEnvironmentManager("/test/project")
    status = manager.detect_current_environment()
    
    assert "in_venv" in status
    assert "python_version" in status
    assert "venv_path" in status

async def test_venv_creation():
    """測試虛擬環境創建"""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = VirtualEnvironmentManager(temp_dir)
        success = await manager._create_and_activate_venv()
        
        # 驗證虛擬環境文件
        venv_path = Path(temp_dir) / "venv"
        assert venv_path.exists()
        
        if os.name == "nt":
            assert (venv_path / "Scripts" / "python.exe").exists()
        else:
            assert (venv_path / "bin" / "python").exists()
```

### 面板系統驗收
```python
# 測試腳本: tests/panel_system_test.py
async def test_standard_panel_view():
    """測試標準面板視圖"""
    class TestPanelView(StandardPanelView):
        def get_available_panels(self):
            return ["main", "settings", "stats"]
        
        async def get_panel_embed(self, panel_name):
            return discord.Embed(title=f"{panel_name} Panel")
    
    cog_mock = MagicMock()
    panel = TestPanelView(cog_mock, 123456789, 987654321)
    
    # 測試面板切換
    for panel_name in panel.get_available_panels():
        embed = await panel.get_panel_embed(panel_name)
        assert isinstance(embed, discord.Embed)
        assert panel_name.title() in embed.title
```

---

## 🎯 成功指標與監控

### 技術指標
- **啟動成功率**: >99% (虛擬環境自動設置)
- **面板響應時間**: <2 秒 (所有面板載入)
- **錯誤恢復率**: >90% (自動錯誤恢復)
- **測試覆蓋率**: >90% (代碼覆蓋率)

### 用戶體驗指標
- **面板操作成功率**: >95%
- **指令響應時間**: <3 秒
- **錯誤訊息清晰度**: 用戶理解率 >90%

### 開發效率指標
- **新模塊開發時間**: 減少 50%
- **錯誤調試時間**: 減少 60%
- **測試執行時間**: <5 分鐘 (完整測試套件)

---

## 🔒 風險緩解策略

### 技術風險
1. **虛擬環境兼容性問題**
   - 緩解: 詳細的跨平台測試
   - 回退: 提供手動設置指導

2. **面板性能問題**
   - 緩解: 分頁和懶加載
   - 監控: 響應時間指標

3. **測試複雜度過高**
   - 緩解: 模塊化測試框架
   - 優化: 並行測試執行

### 實現風險
1. **API 變更風險**
   - 緩解: 版本鎖定和相容性測試
   - 監控: 依賴版本追蹤

2. **資料庫遷移風險**
   - 緩解: 備份和回滾機制
   - 測試: 遷移腳本驗證

---

## 📚 開發指導原則

### 代碼品質
1. **遵循現有架構模式**
   - 使用 BaseCog 和 BasePanelView
   - 統一錯誤處理機制
   - 標準化日誌記錄

2. **測試驅動開發**
   - 先寫測試，後寫實現
   - 保持高測試覆蓋率
   - 持續集成驗證

3. **文檔化要求**
   - 完整的 docstring
   - 類型提示
   - 使用範例

### 性能要求
1. **響應時間目標**
   - 面板載入: <2 秒
   - 指令執行: <3 秒
   - 資料庫查詢: <1 秒

2. **資源使用限制**
   - 內存使用: <500MB
   - CPU 使用: <50% (平均)
   - 資料庫連接: <10 個併發

### 安全要求
1. **權限檢查**
   - 所有管理指令需要權限驗證
   - 面板操作需要用戶身份驗證
   - 敏感操作需要額外確認

2. **錯誤處理**
   - 不洩露敏感信息
   - 提供追蹤碼用於調試
   - 記錄安全相關事件

---

這份優化版 PRD 提供了詳細的實現指導、具體的代碼範例、完整的測試策略和明確的驗收標準，能夠指導 AI agent 生成正確、可運行、有合理架構的程式碼。 