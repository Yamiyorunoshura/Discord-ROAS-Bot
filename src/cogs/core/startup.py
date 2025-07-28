"""
優化的啟動流程模塊 v1.6
- 實現異步並行啟動
- 智能批次載入
- 啟動狀態追蹤
- 失敗優雅處理
- 重試機制
- 依賴關係管理
- 進度監控
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from discord.ext import commands

from .error_handler import create_error_handler
from .logger import get_logger_manager


class ModuleStatus(Enum):
    """模組狀態枚舉"""

    PENDING = "pending"  # 等待載入
    LOADING = "loading"  # 載入中
    LOADED = "loaded"  # 載入成功
    FAILED = "failed"  # 載入失敗
    RETRYING = "retrying"  # 重試中
    CRITICAL_FAILED = "critical_failed"  # 關鍵模組失敗


@dataclass
class ModuleInfo:
    """模組資訊類別"""

    name: str
    path: str
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    is_critical: bool = False
    description: str = ""

    # 運行時狀態
    status: ModuleStatus = ModuleStatus.PENDING
    load_time: float = 0.0
    error: Exception | None = None
    retry_count: int = 0
    max_retries: int = 3
    last_attempt_time: float = 0.0

    def __post_init__(self):
        """後初始化處理"""
        if not self.description:
            self.description = f"模組 {self.name}"


@dataclass
class StartupStats:
    """啟動統計資料"""

    total_modules: int = 0
    success_count: int = 0
    failure_count: int = 0
    retry_count: int = 0
    critical_failures: int = 0
    total_time: float = 0.0
    start_time: float = 0.0

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_modules == 0:
            return 0.0
        return (self.success_count / self.total_modules) * 100

    @property
    def is_complete(self) -> bool:
        """是否完成載入"""
        return (self.success_count + self.failure_count) >= self.total_modules


class StartupManager:
    """優化的啟動管理器"""

    def __init__(self, bot: commands.Bot):
        """
        初始化啟動管理器

        Args:
            bot: Discord 機器人實例
        """
        self.bot = bot
        self.logger = get_logger_manager().get_logger("startup")
        self.error_handler = create_error_handler("startup", self.logger)

        # 模組資訊
        self.modules: dict[str, ModuleInfo] = {}
        self.load_order: list[str] = []

        # 啟動統計
        self.stats = StartupStats()

        # 進度回調
        self.progress_callbacks: list[Callable[[int, int, str], None]] = []

        # 預定義的模組配置
        self.module_configs = {
            "database": {
                "priority": 0,
                "dependencies": [],
                "is_critical": True,
                "description": "資料庫核心模組",
            },
            "activity_meter": {
                "priority": 1,
                "dependencies": ["database"],
                "is_critical": False,
                "description": "活躍度系統",
            },
            "message_listener": {
                "priority": 1,
                "dependencies": ["database"],
                "is_critical": False,
                "description": "訊息監聽系統",
            },
            "welcome": {
                "priority": 1,
                "dependencies": ["database"],
                "is_critical": False,
                "description": "歡迎系統",
            },
            "protection": {
                "priority": 2,
                "dependencies": ["database"],
                "is_critical": False,
                "description": "群組保護系統",
            },
            "sync_data": {
                "priority": 3,
                "dependencies": ["database", "activity_meter"],
                "is_critical": False,
                "description": "資料同步系統",
            },
        }

    def add_progress_callback(self, callback: Callable[[int, int, str], None]):
        """
        添加進度回調函數

        Args:
            callback: 回調函數 (current, total, module_name)
        """
        self.progress_callbacks.append(callback)

    def _notify_progress(self, current: int, total: int, module_name: str = ""):
        """
        通知進度更新

        Args:
            current: 當前進度
            total: 總數
            module_name: 當前模組名稱
        """
        for callback in self.progress_callbacks:
            try:
                callback(current, total, module_name)
            except Exception as exc:
                self.logger.warning(f"進度回調執行失敗:{exc}")

    def register_module(
        self,
        name: str,
        path: str,
        priority: int = 0,
        dependencies: list[str | None] | None = None,
        is_critical: bool = False,
        description: str = "",
    ):
        """
        註冊模組

        Args:
            name: 模組名稱
            path: 模組路徑
            priority: 優先級
            dependencies: 依賴列表
            is_critical: 是否為關鍵模組
            description: 模組描述
        """
        self.modules[name] = ModuleInfo(
            name=name,
            path=path,
            priority=priority,
            dependencies=dependencies or [],
            is_critical=is_critical,
            description=description or f"模組 {name}",
        )
        self.logger.info(f"📦 已註冊模組:{name} - {description}")

    def auto_discover_modules(self, cogs_dir: str = "cogs") -> int:
        """
        自動發現模組

        Args:
            cogs_dir: Cogs 目錄路徑

        Returns:
            int: 發現的模組數量
        """
        self.logger.info("🔍 開始自動發現模組...")

        cogs_path = Path(cogs_dir)
        if not cogs_path.exists():
            self.logger.warning(f"⚠️ Cogs 目錄不存在:{cogs_dir}")
            return 0

        discovered_count = 0

        # 掃描 cogs 目錄
        for module_dir in cogs_path.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue

            # 檢查是否有 __init__.py 文件
            init_file = module_dir / "__init__.py"
            if not init_file.exists():
                continue

            module_name = module_dir.name
            module_path = f"cogs.{module_name}"

            # 獲取模組配置
            config = self.module_configs.get(
                module_name,
                {
                    "priority": 99,
                    "dependencies": [],
                    "is_critical": False,
                    "description": f"自定義模組 {module_name}",
                },
            )

            # 註冊模組
            self.register_module(
                module_name,
                module_path,
                config["priority"],
                config["dependencies"],
                config["is_critical"],
                config["description"],
            )

            discovered_count += 1

        self.stats.total_modules = len(self.modules)
        self.logger.info(f"✅ 共發現 {discovered_count} 個模組")
        return discovered_count

    def _resolve_load_order(self) -> list[str]:
        """
        解析載入順序(拓撲排序)

        Returns:
            List[str]: 載入順序列表

        Raises:
            ValueError: 檢測到循環依賴
        """
        self.logger.info("🔄 正在解析模組依賴關係...")

        visited = set()
        temp_visited = set()
        order = []

        def visit(module_name: str):
            if module_name in temp_visited:
                raise ValueError(f"檢測到循環依賴:{module_name}")

            if module_name in visited:
                return

            temp_visited.add(module_name)

            # 訪問依賴
            module = self.modules.get(module_name)
            if module:
                for dep in module.dependencies:
                    if dep in self.modules:
                        visit(dep)
                    else:
                        self.logger.warning(
                            f"模組 {module_name} 依賴的模組 {dep} 不存在"
                        )

            temp_visited.remove(module_name)
            visited.add(module_name)
            order.append(module_name)

        # 按優先級排序
        sorted_modules = sorted(
            self.modules.keys(), key=lambda x: (self.modules[x].priority, x)
        )

        # 執行拓撲排序
        for module_name in sorted_modules:
            if module_name not in visited:
                visit(module_name)

        self.logger.info(f"📋 載入順序:{' → '.join(order)}")
        return order

    def _validate_dependencies(self, module_name: str) -> bool:
        """
        驗證模組依賴是否已載入

        Args:
            module_name: 模組名稱

        Returns:
            bool: 依賴是否滿足
        """
        module = self.modules.get(module_name)
        if not module:
            return False

        for dep in module.dependencies:
            dep_module = self.modules.get(dep)
            if not dep_module or dep_module.status != ModuleStatus.LOADED:
                self.logger.warning(f"模組 {module_name} 的依賴 {dep} 尚未載入")
                return False

        return True

    async def _load_module_with_retry(self, module_name: str) -> bool:
        """
        載入單個模組(含重試機制)

        Args:
            module_name: 模組名稱

        Returns:
            bool: 是否成功載入
        """
        module = self.modules.get(module_name)
        if not module:
            self.logger.error(f"模組 {module_name} 不存在")
            return False

        # 檢查是否已載入
        if module.status == ModuleStatus.LOADED:
            return True

        # 執行重試邏輯
        for attempt in range(module.max_retries + 1):
            start_time = time.time()
            module.status = (
                ModuleStatus.RETRYING if attempt > 0 else ModuleStatus.LOADING
            )
            module.last_attempt_time = start_time

            try:
                # 驗證依賴
                if not self._validate_dependencies(module_name):
                    raise RuntimeError(f"模組 {module_name} 的依賴未滿足")

                # 載入模組
                self.logger.info(
                    f"🔄 正在載入模組:{module_name} (嘗試 {attempt + 1}/{module.max_retries + 1})"
                )
                await self.bot.load_extension(module.path)

                # 更新狀態
                module.status = ModuleStatus.LOADED
                module.load_time = time.time() - start_time
                self.stats.success_count += 1

                self.logger.info(
                    f"✅ 模組載入成功:{module_name} ({module.load_time:.2f}s)"
                )
                return True

            except Exception as exc:
                module.error = exc
                module.load_time = time.time() - start_time
                module.retry_count = attempt + 1
                self.stats.retry_count += 1

                if attempt < module.max_retries:
                    # 計算退避時間
                    backoff_time = 0.5 * (2**attempt)  # 指數退避
                    self.logger.warning(
                        f"⚠️ 模組 {module_name} 載入失敗,{backoff_time:.1f}s 後重試:{exc}"
                    )
                    await asyncio.sleep(backoff_time)
                    continue
                # 最終失敗
                elif module.is_critical:
                    module.status = ModuleStatus.CRITICAL_FAILED
                    self.stats.critical_failures += 1
                    self.logger.critical(f"💥 關鍵模組 {module_name} 載入失敗:{exc}")
                    raise RuntimeError(f"關鍵模組 {module_name} 載入失敗") from exc
                else:
                    module.status = ModuleStatus.FAILED
                    self.stats.failure_count += 1
                    self.logger.error(f"❌ 模組 {module_name} 載入失敗:{exc}")
                    return False

        return False

    async def _load_modules_batch(self, module_names: list[str]) -> list[bool]:
        """
        批次載入模組

        Args:
            module_names: 模組名稱列表

        Returns:
            List[bool]: 載入結果列表
        """
        if not module_names:
            return []

        # 創建任務
        tasks = []
        for module_name in module_names:
            task = asyncio.create_task(
                self._load_module_with_retry(module_name), name=f"load_{module_name}"
            )
            tasks.append((module_name, task))

        # 等待所有任務完成
        results = []
        for module_name, task in tasks:
            try:
                result = await task
                results.append(result)

                # 更新進度
                current_loaded = self.stats.success_count + self.stats.failure_count
                self._notify_progress(
                    current_loaded, self.stats.total_modules, module_name
                )

            except Exception as exc:
                self.logger.error(f"模組 {module_name} 載入時發生異常:{exc}")
                results.append(False)

        return results

    def _group_modules_by_priority(self) -> dict[int, tuple[list[str], list[str]]]:
        """
        按優先級分組模組

        Returns:
            Dict[int, Tuple[List[str], List[str]]]:
            {priority: (critical_modules, normal_modules)}
        """
        priority_groups = {}

        for module_name in self.load_order:
            module = self.modules[module_name]
            priority = module.priority

            if priority not in priority_groups:
                priority_groups[priority] = ([], [])

            if module.is_critical:
                priority_groups[priority][0].append(module_name)
            else:
                priority_groups[priority][1].append(module_name)

        return priority_groups

    async def start_all_modules(self) -> StartupStats:
        """
        啟動所有模組

        Returns:
            StartupStats: 啟動結果統計
        """
        self.stats.start_time = time.time()
        self.logger.info("🚀 開始載入所有模組...")

        try:
            # 解析載入順序
            self.load_order = self._resolve_load_order()

            # 按優先級分組
            priority_groups = self._group_modules_by_priority()

            # 初始化進度
            self._notify_progress(0, self.stats.total_modules)

            # 按優先級順序載入
            for priority in sorted(priority_groups.keys()):
                critical_modules, normal_modules = priority_groups[priority]

                # 先載入關鍵模組(序列載入)
                if critical_modules:
                    self.logger.info(
                        f"🔑 載入關鍵模組 (優先級 {priority}):{', '.join(critical_modules)}"
                    )
                    for module_name in critical_modules:
                        try:
                            await self._load_module_with_retry(module_name)
                        except RuntimeError as exc:
                            # 關鍵模組失敗,終止載入
                            self.logger.critical(f"關鍵模組載入失敗,終止程序:{exc}")
                            raise

                # 並行載入普通模組
                if normal_modules:
                    self.logger.info(
                        f"⚡ 並行載入模組 (優先級 {priority}):{', '.join(normal_modules)}"
                    )
                    await self._load_modules_batch(normal_modules)

            # 完成進度通知
            self._notify_progress(self.stats.total_modules, self.stats.total_modules)

        except Exception as exc:
            self.logger.error(f"載入過程中發生錯誤:{exc}", exc_info=True)
            raise
        finally:
            # 計算總時間
            self.stats.total_time = time.time() - self.stats.start_time

            # 記錄統計
            self._log_final_stats()

        return self.stats

    def _log_final_stats(self):
        """記錄最終統計資訊"""
        self.logger.info("=" * 50)
        self.logger.info("📊 模組載入統計報告")
        self.logger.info("=" * 50)
        self.logger.info(f"📦 總模組數:{self.stats.total_modules}")
        self.logger.info(f"✅ 成功載入:{self.stats.success_count}")
        self.logger.info(f"❌ 載入失敗:{self.stats.failure_count}")
        self.logger.info(f"🔄 重試次數:{self.stats.retry_count}")
        self.logger.info(f"💥 關鍵失敗:{self.stats.critical_failures}")
        self.logger.info(f"⏱️ 總耗時:{self.stats.total_time:.2f}s")
        self.logger.info(f"📈 成功率:{self.stats.success_rate:.1f}%")

        # 詳細模組資訊
        loaded_modules = [
            m for m in self.modules.values() if m.status == ModuleStatus.LOADED
        ]
        failed_modules = [
            m
            for m in self.modules.values()
            if m.status in [ModuleStatus.FAILED, ModuleStatus.CRITICAL_FAILED]
        ]

        if loaded_modules:
            self.logger.info("\n✅ 成功載入的模組:")
            for module in sorted(loaded_modules, key=lambda x: x.priority):
                critical_mark = "🔑" if module.is_critical else "📦"
                self.logger.info(
                    f"  {critical_mark} {module.name} ({module.load_time:.2f}s) - {module.description}"
                )

        if failed_modules:
            self.logger.info("\n❌ 載入失敗的模組:")
            for module in failed_modules:
                critical_mark = "🔑" if module.is_critical else "📦"
                retry_info = (
                    f" (重試 {module.retry_count} 次)" if module.retry_count > 0 else ""
                )
                self.logger.info(
                    f"  {critical_mark} {module.name}{retry_info}: {module.error}"
                )

        self.logger.info("=" * 50)

    def get_module_status(self, module_name: str) -> ModuleStatus | None:
        """
        獲取模組狀態

        Args:
            module_name: 模組名稱

        Returns:
            ModuleStatus | None: 模組狀態,如果模組不存在則返回 None
        """
        module = self.modules.get(module_name)
        return module.status if module else None

    def get_loaded_modules(self) -> list[str]:
        """
        獲取已載入的模組列表

        Returns:
            List[str]: 已載入的模組名稱列表
        """
        return [
            name
            for name, module in self.modules.items()
            if module.status == ModuleStatus.LOADED
        ]

    def get_failed_modules(self) -> list[str]:
        """
        獲取載入失敗的模組列表

        Returns:
            List[str]: 載入失敗的模組名稱列表
        """
        return [
            name
            for name, module in self.modules.items()
            if module.status in [ModuleStatus.FAILED, ModuleStatus.CRITICAL_FAILED]
        ]


def create_startup_manager(bot: commands.Bot) -> StartupManager:
    """
    創建啟動管理器

    Args:
        bot: Discord 機器人實例

    Returns:
        StartupManager: 啟動管理器實例
    """
    return StartupManager(bot)


# 工具函數
def print_progress_bar(
    current: int, total: int, module_name: str = "", width: int = 20
):
    """
    列印進度條

    Args:
        current: 當前進度
        total: 總數
        module_name: 當前模組名稱
        width: 進度條寬度
    """
    if total == 0:
        return

    percentage = (current / total) * 100
    filled_length = int(width * current // total)
    bar = "█" * filled_length + "░" * (width - filled_length)

    status = f"載入中: {module_name}" if module_name else "完成"
    print(f"\r🚀 [進度] |{bar}| {percentage:.1f}% {status}", end="", flush=True)


def create_progress_callback() -> Callable[[int, int, str], None]:
    """
    創建進度回調函數

    Returns:
        Callable: 進度回調函數
    """

    def callback(current: int, total: int, module_name: str = ""):
        print_progress_bar(current, total, module_name)

    return callback
