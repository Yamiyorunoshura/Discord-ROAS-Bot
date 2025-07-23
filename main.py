#!/usr/bin/env python3
# =============================================================================
# Discord ADR Bot v1.6 - 主程式檔案
# =============================================================================
# 功能說明：
# - 異步並行啟動優化
# - 智能批次載入模組
# - 啟動狀態追蹤與監控
# - 優雅的失敗處理機制
# - 完整的錯誤處理與日誌記錄
# - 事件迴圈最佳化（uvloop）
# - 人性化的錯誤訊息顯示
# - 自動檢測和啟用虛擬環境
# =============================================================================

# 自動檢測和啟用虛擬環境
import os
import sys
import site

# 智能虛擬環境管理
async def _setup_virtual_environment():
    """智能虛擬環境設置"""
    try:
        # 導入虛擬環境管理器
        from cogs.core.venv_manager import VirtualEnvironmentManager
        
        # 創建管理器實例
        venv_manager = VirtualEnvironmentManager()
        
        # 獲取當前環境資訊
        env_info = venv_manager.get_environment_info()
        
        print("🔍 [環境] 環境檢測結果：")
        print(f"   平台：{env_info['platform']}")
        print(f"   Python 版本：{env_info['python_version']}")
        print(f"   虛擬環境：{'是' if env_info['is_in_virtual_env'] else '否'}")
        
        if env_info['is_in_virtual_env']:
            print(f"   ✅ 已在虛擬環境中運行：{env_info.get('current_venv', '系統檢測')}")
            return True
        
        print("   ⚠️  未在虛擬環境中，嘗試自動設置...")
        
        # 執行自動設置
        setup_result = await venv_manager.auto_setup()
        
        # 顯示設置結果
        if setup_result["success"]:
            print("   ✅ 虛擬環境設置成功")
            for step in setup_result["steps"]:
                print(f"      • {step}")
        else:
            print("   ⚠️  虛擬環境設置部分成功")
            for step in setup_result["steps"]:
                print(f"      • {step}")
            if setup_result["errors"]:
                print("   錯誤：")
                for error in setup_result["errors"]:
                    print(f"      ❌ {error}")
        
        # 顯示最終狀態
        final_state = setup_result.get("final_state", {})
        if final_state.get("healthy", False):
            print("   🎉 環境健康檢查通過")
        else:
            print("   ⚠️  環境存在一些問題，但可以繼續運行")
            for issue in final_state.get("issues", []):
                print(f"      • {issue}")
            for rec in final_state.get("recommendations", []):
                print(f"      💡 建議：{rec}")
        
        return True
        
    except ImportError:
        print("   ⚠️  無法導入虛擬環境管理器，使用舊版邏輯")
        return _activate_venv_legacy()
    except Exception as exc:
        print(f"   ❌ 虛擬環境設置失敗：{exc}")
        print("   🔄 回退到舊版邏輯")
        return _activate_venv_legacy()

# 舊版虛擬環境激活邏輯（作為回退）
def _activate_venv_legacy():
    """舊版虛擬環境激活邏輯（回退機制）"""
    # 檢查是否已在虛擬環境中
    if sys.prefix != sys.base_prefix:
        print("✅ [環境] 已在虛擬環境中運行")
        return True
    
    # 尋找虛擬環境路徑
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_paths = [
        os.path.join(script_dir, "venv"),
        os.path.join(script_dir, ".venv"),
        os.path.join(script_dir, "env")
    ]
    
    for venv_path in venv_paths:
        # 檢查不同平台的 site-packages 路徑
        if os.name == "nt":  # Windows
            site_packages = os.path.join(venv_path, "Lib", "site-packages")
        else:  # macOS/Linux
            # 尋找 Python 版本目錄
            lib_dir = os.path.join(venv_path, "lib")
            if not os.path.isdir(lib_dir):
                continue
                
            # 尋找 Python 版本目錄 (如 python3.10)
            py_dirs = [d for d in os.listdir(lib_dir) if d.startswith("python")]
            if not py_dirs:
                continue
                
            site_packages = os.path.join(lib_dir, py_dirs[0], "site-packages")
        
        # 檢查 site-packages 是否存在
        if os.path.isdir(site_packages):
            # 將虛擬環境的 site-packages 添加到 Python 路徑
            sys.path.insert(0, site_packages)
            # 重新初始化 site 模組以更新 sys.path
            site.main()
            print(f"✅ [環境] 已啟用虛擬環境：{venv_path}")
            return True
    
    print("⚠️  [環境] 未找到虛擬環境，使用系統 Python")
    print("   💡 建議：建立並啟用虛擬環境以避免依賴問題")
    return False

# 同步包裝器來啟用虛擬環境
def _activate_venv():
    """虛擬環境激活的同步包裝器"""
    try:
        # 嘗試使用 asyncio 運行智能設置
        import asyncio
        return asyncio.run(_setup_virtual_environment())
    except Exception:
        # 如果異步方式失敗，使用舊版邏輯
        return _activate_venv_legacy()

# 啟用虛擬環境
_activate_venv()

import glob, logging, logging.handlers, asyncio, functools, importlib, time
from typing import List, Optional, Dict, Any, Tuple
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.ext.commands import errors as command_errors
from discord.app_commands import AppCommandError
from datetime import datetime
from pathlib import Path

# =============================================================================
# 1️⃣ 專案基礎設定
# =============================================================================
# 專案根目錄
PROJECT_ROOT = os.getcwd()  # 使用當前工作目錄作為專案根目錄
os.environ.setdefault("PROJECT_ROOT", PROJECT_ROOT)

# 日誌目錄
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def _truncate_old_logs() -> None:
    """
    清空舊的日誌檔案，避免日誌檔案過大
    
    錯誤處理：
    - 檔案權限問題
    - 檔案被其他程序佔用
    - 磁碟空間不足
    """
    print("🧹 [日誌] 正在清理舊日誌檔案...")
    cleared_count = 0
    error_count = 0
    
    for log_file in glob.glob(os.path.join(LOG_DIR, "*.log")):
        try:
            # 清空檔案內容但保留檔案
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("")
            cleared_count += 1
        except PermissionError:
            print(f"   ⚠️  權限不足，無法清空：{os.path.basename(log_file)}")
            error_count += 1
        except OSError as exc:
            print(f"   ❌ 清空失敗 {os.path.basename(log_file)}：{exc}")
            error_count += 1
        except Exception as exc:
            print(f"   ❌ 未知錯誤 {os.path.basename(log_file)}：{exc}")
            error_count += 1
    
    if cleared_count > 0:
        print(f"   ✅ 已清空 {cleared_count} 個日誌檔案")
    if error_count > 0:
        print(f"   ⚠️  有 {error_count} 個檔案清空失敗")

_truncate_old_logs()

# =============================================================================
# 2️⃣ 模組資訊類別
# =============================================================================
class ModuleInfo:
    """模組資訊類別"""
    
    def __init__(self, name: str, path: str, priority: int = 0, 
                 dependencies: List[str | None] = None, is_critical: bool = False):
        """
        初始化模組資訊
        
        參數：
            name: 模組名稱
            path: 模組路徑
            priority: 優先級（數字越小越早載入）
            dependencies: 依賴的模組列表
            is_critical: 是否為關鍵模組（失敗時終止程序）
        """
        self.name = name
        self.path = path
        self.priority = priority
        self.dependencies = dependencies or []
        self.is_critical = is_critical
        self.loaded = False
        self.load_time = 0.0
        self.error: Exception | None = None
        self.retry_count = 0
        self.max_retries = 3

# =============================================================================
# 3️⃣ 優化的啟動管理器
# =============================================================================
class OptimizedStartupManager:
    """優化的啟動管理器"""
    
    def __init__(self, bot: commands.Bot):
        """
        初始化啟動管理器
        
        參數：
            bot: Discord 機器人實例
        """
        self.bot = bot
        
        # 模組資訊
        self.modules: Dict[str, ModuleInfo] = {}
        self.load_order: List[str] = []
        
        # 啟動統計
        self.start_time = 0.0
        self.total_time = 0.0
        self.success_count = 0
        self.failure_count = 0
        self.retry_count = 0
        
        # 進度追蹤
        self.total_modules = 0
        self.loaded_modules = 0
        
        # 預定義的模組配置
        self.module_configs = {
            "activity_meter": {
                "priority": 1, 
                "dependencies": [], 
                "is_critical": False,
                "description": "活躍度系統"
            },
            "message_listener": {
                "priority": 1, 
                "dependencies": [], 
                "is_critical": False,
                "description": "訊息監聽系統"
            },
            "welcome": {
                "priority": 1, 
                "dependencies": [], 
                "is_critical": False,
                "description": "歡迎系統"
            },
            "protection": {
                "priority": 2, 
                "dependencies": [], 
                "is_critical": False,
                "description": "群組保護系統"
            },
            "sync_data": {
                "priority": 3, 
                "dependencies": ["activity_meter"], 
                "is_critical": False,
                "description": "資料同步系統"
            },
            "core": {
                "priority": 0, 
                "dependencies": [], 
                "is_critical": True,
                "description": "核心功能模組"
            }
        }
    
    def auto_discover_modules(self, cogs_dir: str = "cogs") -> None:
        """
        自動發現模組
        
        參數：
            cogs_dir: Cogs 目錄路徑
        """
        print("🔍 [啟動] 正在掃描模組...")
        
        cogs_path = Path(cogs_dir)
        if not cogs_path.exists():
            print(f"⚠️  [啟動] Cogs 目錄不存在：{cogs_dir}")
            return
        
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
            config = self.module_configs.get(module_name, {
                "priority": 99, 
                "dependencies": [], 
                "is_critical": False,
                "description": "自定義模組"
            })
            
            # 註冊模組
            self.modules[module_name] = ModuleInfo(
                module_name, 
                module_path, 
                config["priority"], 
                config["dependencies"],
                config["is_critical"]
            )
            
            print(f"   📦 發現模組：{module_name} - {config['description']}")
            discovered_count += 1
        
        self.total_modules = len(self.modules)
        print(f"✅ [啟動] 共發現 {discovered_count} 個模組")
    
    def _resolve_load_order(self) -> List[str]:
        """
        解析載入順序（拓撲排序）
        
        回傳：
            List[str]: 載入順序列表
        """
        print("🔄 [啟動] 正在解析模組依賴關係...")
        
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(module_name: str):
            if module_name in temp_visited:
                raise ValueError(f"檢測到循環依賴：{module_name}")
            
            if module_name in visited:
                return
            
            temp_visited.add(module_name)
            
            # 訪問依賴
            module = self.modules.get(module_name)
            if module:
                for dep in module.dependencies:
                    if dep in self.modules:
                        visit(dep)
            
            temp_visited.remove(module_name)
            visited.add(module_name)
            order.append(module_name)
        
        # 按優先級排序
        sorted_modules = sorted(
            self.modules.keys(), 
            key=lambda x: self.modules[x].priority
        )
        
        # 執行拓撲排序
        for module_name in sorted_modules:
            if module_name not in visited:
                visit(module_name)
        
        return order
    
    def _print_progress(self, current: int, total: int, module_name: str = ""):
        """
        列印進度條
        
        參數：
            current: 當前進度
            total: 總數
            module_name: 當前模組名稱
        """
        if total == 0:
            return
            
        percentage = (current / total) * 100
        filled_length = int(20 * current // total)
        bar = "█" * filled_length + "░" * (20 - filled_length)
        
        status = f"載入中: {module_name}" if module_name else "完成"
        print(f"\r🚀 [進度] |{bar}| {percentage:.1f}% {status}", end="", flush=True)
    
    async def _load_module_with_retry(self, module_name: str) -> bool:
        """
        載入單個模組（含重試機制）
        
        參數：
            module_name: 模組名稱
            
        回傳：
            bool: 是否成功載入
        """
        module = self.modules.get(module_name)
        if not module:
            return False
        
        for attempt in range(module.max_retries + 1):
            start_time = time.time()
            
            try:
                # 檢查依賴是否已載入
                for dep in module.dependencies:
                    dep_module = self.modules.get(dep)
                    if not dep_module or not dep_module.loaded:
                        raise RuntimeError(f"依賴模組 {dep} 尚未載入")
                
                # 載入模組
                await self.bot.load_extension(module.path)
                
                # 更新狀態
                module.loaded = True
                module.load_time = time.time() - start_time
                self.success_count += 1
                self.loaded_modules += 1
                
                return True
                
            except Exception as exc:
                module.error = exc
                module.load_time = time.time() - start_time
                module.retry_count = attempt + 1
                
                if attempt < module.max_retries:
                    # 重試
                    self.retry_count += 1
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指數退避
                    continue
                else:
                    # 最終失敗
                    self.failure_count += 1
                    
                    if module.is_critical:
                        print(f"\n❌ [致命] 關鍵模組載入失敗：{module_name}")
                        print(f"   錯誤：{exc}")
                        print("   程序將終止")
                        sys.exit(1)
                    
                    return False
        
        return False
    
    async def _load_modules_batch(self, module_names: List[str]) -> List[bool]:
        """
        批次載入模組
        
        參數：
            module_names: 模組名稱列表
            
        回傳：
            List[bool]: 載入結果列表
        """
        if not module_names:
            return []
        
        # 並行載入
        tasks = []
        for module_name in module_names:
            task = asyncio.create_task(
                self._load_module_with_retry(module_name),
                name=f"load_{module_name}"
            )
            tasks.append(task)
        
        # 等待所有任務完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 處理結果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"\n❌ [錯誤] 模組 {module_names[i]} 載入時發生異常：{result}")
                final_results.append(False)
            else:
                final_results.append(result)
        
        return final_results
    
    async def start_all_modules(self) -> Dict[str, Any]:
        """
        啟動所有模組
        
        回傳：
            Dict[str, Any]: 啟動結果統計
        """
        self.start_time = time.time()
        print("\n🚀 [啟動] 開始載入所有模組...")
        
        try:
            # 解析載入順序
            self.load_order = self._resolve_load_order()
            print(f"📋 [啟動] 載入順序：{' → '.join(self.load_order)}")
            
            # 按優先級分組
            priority_groups = {}
            for module_name in self.load_order:
                module = self.modules[module_name]
                priority = module.priority
                
                if priority not in priority_groups:
                    priority_groups[priority] = []
                priority_groups[priority].append(module_name)
            
            # 初始化進度
            self._print_progress(0, self.total_modules)
            
            # 按優先級順序載入
            for priority in sorted(priority_groups.keys()):
                group = priority_groups[priority]
                
                # 關鍵模組單獨載入
                critical_modules = [name for name in group if self.modules[name].is_critical]
                normal_modules = [name for name in group if not self.modules[name].is_critical]
                
                # 先載入關鍵模組
                if critical_modules:
                    print(f"\n🔑 [啟動] 載入關鍵模組 (優先級 {priority})：{', '.join(critical_modules)}")
                    for module_name in critical_modules:
                        success = await self._load_module_with_retry(module_name)
                        if success:
                            print(f"   ✅ {module_name}")
                        else:
                            print(f"   ❌ {module_name}")
                        self._print_progress(self.loaded_modules, self.total_modules, module_name)
                
                # 並行載入普通模組
                if normal_modules:
                    print(f"\n⚡ [啟動] 並行載入模組 (優先級 {priority})：{', '.join(normal_modules)}")
                    results = await self._load_modules_batch(normal_modules)
                    
                    for i, (module_name, success) in enumerate(zip(normal_modules, results)):
                        if success:
                            print(f"   ✅ {module_name}")
                        else:
                            print(f"   ❌ {module_name}")
                        self._print_progress(self.loaded_modules, self.total_modules, module_name)
            
            # 完成進度條
            self._print_progress(self.total_modules, self.total_modules)
            print()  # 換行
            
        except Exception as exc:
            print(f"\n❌ [錯誤] 載入過程中發生錯誤：{exc}")
            import traceback
            traceback.print_exc()
        
        # 計算總時間
        self.total_time = time.time() - self.start_time
        
        # 生成統計報告
        stats = self._generate_stats()
        self._print_stats(stats)
        
        return stats
    
    def _generate_stats(self) -> Dict[str, Any]:
        """
        生成啟動統計
        
        回傳：
            Dict[str, Any]: 統計資訊
        """
        loaded_modules = []
        failed_modules = []
        
        for module_name, module in self.modules.items():
            if module.loaded:
                loaded_modules.append({
                    "name": module_name,
                    "load_time": module.load_time,
                    "path": module.path,
                    "priority": module.priority,
                    "is_critical": module.is_critical
                })
            else:
                failed_modules.append({
                    "name": module_name,
                    "error": str(module.error) if module.error else "未知錯誤",
                    "path": module.path,
                    "retry_count": module.retry_count,
                    "is_critical": module.is_critical
                })
        
        return {
            "total_modules": self.total_modules,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "retry_count": self.retry_count,
            "total_time": self.total_time,
            "loaded_modules": loaded_modules,
            "failed_modules": failed_modules,
            "load_order": self.load_order,
            "success_rate": (self.success_count / self.total_modules * 100) if self.total_modules > 0 else 0
        }
    
    def _print_stats(self, stats: Dict[str, Any]) -> None:
        """
        列印統計資訊
        
        參數：
            stats: 統計資訊
        """
        print("\n" + "=" * 60)
        print("📊 模組載入統計報告")
        print("=" * 60)
        print(f"📦 總模組數：{stats['total_modules']}")
        print(f"✅ 成功載入：{stats['success_count']}")
        print(f"❌ 載入失敗：{stats['failure_count']}")
        print(f"🔄 重試次數：{stats['retry_count']}")
        print(f"⏱️  總耗時：{stats['total_time']:.2f}s")
        print(f"📈 成功率：{stats['success_rate']:.1f}%")
        
        if stats['loaded_modules']:
            print("\n✅ 成功載入的模組：")
            for module in sorted(stats['loaded_modules'], key=lambda x: x['priority']):
                critical_mark = "🔑" if module['is_critical'] else "📦"
                print(f"   {critical_mark} {module['name']} ({module['load_time']:.2f}s)")
        
        if stats['failed_modules']:
            print("\n❌ 載入失敗的模組：")
            for module in stats['failed_modules']:
                critical_mark = "🔑" if module['is_critical'] else "📦"
                retry_info = f" (重試 {module['retry_count']} 次)" if module['retry_count'] > 0 else ""
                print(f"   {critical_mark} {module['name']}{retry_info}: {module['error']}")
        
        print("=" * 60)

# =============================================================================
# 4️⃣ 日誌系統設定
# =============================================================================
def _get_logger(name: str, file: str, level: int = logging.INFO) -> logging.Logger:
    """
    建立具備輪轉功能的日誌記錄器
    
    參數：
        name: 日誌記錄器名稱
        file: 日誌檔案名稱
        level: 日誌等級
    
    特性：
    - 自動輪轉（5MB 一個檔案，保留 3 個備份）
    - UTF-8 編碼支援
    - 統一的時間格式
    """
    # 日誌格式：時間戳 | 等級 | 訊息
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 輪轉檔案處理器
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, file),
        encoding="utf-8",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3
    )
    handler.setFormatter(formatter)
    
    # 建立日誌記錄器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重複添加處理器
    if not logger.hasHandlers():
        logger.addHandler(handler)
    
    return logger

# 建立主要日誌記錄器
logger = _get_logger("main", "main.log")
error_logger = _get_logger("main_error", "main_error.log", level=logging.ERROR)

print("📝 [日誌] 日誌系統已初始化")

# =============================================================================
# 5️⃣ 環境變數載入
# =============================================================================
def _load_environment() -> str:
    """
    載入環境變數檔案
    
    支援的檔案：
    - .env.production（生產環境）
    - .env.development（開發環境）
    - .env（通用）
    
    回傳：當前環境名稱
    """
    # 判斷當前環境
    env = os.getenv("ENVIRONMENT", "development")
    print(f"🌍 [環境] 當前環境：{env}")
    
    # 決定要載入的 .env 檔案
    env_files = []
    if env == "production":
        env_files = [".env.production", ".env"]
    else:
        env_files = [".env.development", ".env"]
    
    # 載入環境變數
    loaded_files = []
    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            loaded_files.append(env_file)
    
    if loaded_files:
        print(f"✅ [環境] 已載入環境變數：{', '.join(loaded_files)}")
    else:
        print("⚠️  [環境] 未找到 .env 檔案")
        print("   💡 建議：建立 .env 檔案並設定必要的環境變數")
    
    return env

# 載入環境變數
ENV = _load_environment()

# =============================================================================
# 6️⃣ 錯誤處理工具
# =============================================================================
def rich_traceback(exc: BaseException) -> str:
    """
    生成豐富的錯誤追蹤資訊
    
    參數：
        exc: 例外物件
    
    回傳：
        str: 格式化的錯誤資訊
    """
    import traceback
    
    # 基本錯誤資訊
    error_info = [
        "💥 詳細錯誤資訊",
        "=" * 50,
        f"🔸 錯誤類型：{type(exc).__name__}",
        f"🔸 錯誤訊息：{str(exc)}",
        f"🔸 發生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 50
    ]
    
    # 錯誤追蹤
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    error_info.extend(tb_lines)
    
    return "\n".join(error_info)

# 裝飾器：自動處理互動錯誤
def interaction_try(func):
    """
    裝飾器：自動處理 Discord 互動中的錯誤
    
    功能：
    - 捕獲並記錄錯誤
    - 向用戶顯示友善的錯誤訊息
    - 避免互動超時
    """
    @functools.wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        try:
            await func(self, interaction, *args, **kwargs)
        except Exception as exc:
            # 記錄錯誤
            error_logger.exception(f"互動錯誤 [{func.__name__}]：{interaction.user}")
        
            # 向用戶顯示錯誤
            error_msg = (
                "❌ **發生錯誤**\n"
                f"指令：`{func.__name__}`\n"
                f"錯誤：`{str(exc)}`\n"
                f"時間：{datetime.now().strftime('%H:%M:%S')}\n\n"
                "🔧 如果問題持續發生，請聯絡管理員。"
            )
            
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await interaction.response.send_message(error_msg, ephemeral=True)
            except:
                pass  # 忽略回應錯誤
    
    return wrapper

# =============================================================================
# 7️⃣ Discord 設定
# =============================================================================
def _setup_intents() -> discord.Intents:
    """
    設定 Discord Intents
    
    回傳：
        discord.Intents: 配置好的 Intents
    """
    intents = discord.Intents.default()
    intents.message_content = True  # 讀取訊息內容
    intents.members = True          # 讀取成員資訊
    intents.guilds = True           # 讀取伺服器資訊
    intents.guild_messages = True   # 讀取伺服器訊息
    intents.dm_messages = True      # 讀取私人訊息
    
    print("🔐 [權限] Discord Intents 已設定")
    return intents

# 建立 Intents
intents = _setup_intents()

# =============================================================================
# 8️⃣ 優化的 Bot 類別
# =============================================================================
class ADRBot(commands.Bot):
    """
    Discord ADR Bot 主類別
    
    功能：
    - 優化的模組載入
    - 自動錯誤處理
    - 斜線指令同步
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.startup_manager = OptimizedStartupManager(self)
        self.startup_stats: Dict[str, Any | None] = None
        self.performance_dashboard = None
    
    async def setup_hook(self):
        """
        Bot 設定鉤子
        
        功能：
        - 自動發現並載入模組
        - 註冊管理員指令
        - 同步斜線指令
        """
        print("🔧 [設定] 正在初始化 Bot...")
        
        # 自動發現模組
        self.startup_manager.auto_discover_modules()
        
        # 載入所有模組
        self.startup_stats = await self.startup_manager.start_all_modules()
        
        # 註冊管理員指令
        self._register_sync_command()
        self._register_performance_command()
        
        # 同步斜線指令（開發環境）
        if ENV == "development":
            print("🔄 [同步] 正在同步斜線指令...")
            try:
                synced = await self.tree.sync()
                print(f"✅ [同步] 已同步 {len(synced)} 個斜線指令")
                logger.info(f"斜線指令同步成功：{len(synced)} 個指令")
            except Exception as exc:
                print(f"❌ [同步] 斜線指令同步失敗：{exc}")
                error_logger.exception("斜線指令同步失敗")
        
        print("✅ [設定] Bot 初始化完成")
    
    def _register_sync_command(self):
        """註冊同步指令"""
        @self.tree.command(
            name="sync", 
            description="手動同步斜線指令（僅限伺服器管理員）"
        )
        async def sync_command(interaction: discord.Interaction):
            # 檢查權限
            if not interaction.guild or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    "❌ 此指令只能在伺服器中使用",
                    ephemeral=True
                )
                return
            
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 您沒有權限執行此指令（需要管理伺服器權限）",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            try:
                synced = await self.tree.sync()
                await interaction.followup.send(
                    f"✅ 同步成功！已同步 {len(synced)} 個斜線指令"
                )
                logger.info(f"管理員手動同步指令成功：{interaction.user} ({len(synced)} 個指令)")
            except Exception as exc:
                await interaction.followup.send(
                    f"❌ 同步失敗：{exc}"
                )
                error_logger.exception(f"管理員同步指令失敗：{interaction.user}")
    
    def _register_performance_command(self):
        """註冊性能監控儀表板指令"""
        @self.tree.command(
            name="性能監控", 
            description="開啟系統性能監控儀表板（僅限伺服器管理員）"
        )
        async def performance_dashboard_command(interaction: discord.Interaction):
            # 檢查權限
            if not interaction.guild or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    "❌ 此指令只能在伺服器中使用",
                    ephemeral=True
                )
                return
            
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 您沒有權限執行此指令（需要管理伺服器權限）",
                    ephemeral=True
                )
                return
            
            try:
                # 導入性能監控儀表板
                from cogs.core.performance_dashboard import PerformanceDashboard
                
                # 創建儀表板管理器（如果不存在）
                if self.performance_dashboard is None:
                    self.performance_dashboard = PerformanceDashboard(self)
                
                # 創建儀表板實例
                dashboard = await self.performance_dashboard.create_dashboard(interaction)
                
                # 啟動儀表板
                await dashboard.start(interaction, page="overview")
                
                logger.info(f"管理員開啟性能監控儀表板：{interaction.user}")
                
            except Exception as exc:
                await interaction.response.send_message(
                    f"❌ 無法開啟性能監控儀表板：{exc}",
                    ephemeral=True
                )
                error_logger.exception(f"性能監控儀表板開啟失敗：{interaction.user}")

# =============================================================================
# 9️⃣ Bot 實例與事件處理
# =============================================================================
# 建立 Bot 實例
bot = ADRBot(
    command_prefix=commands.when_mentioned_or("!"),
    intents=intents,
    help_command=None  # 停用預設的 help 指令
)

@bot.event
async def on_ready():
    """
    Bot 就緒事件處理
    
    功能：
    - 顯示 Bot 資訊
    - 記錄伺服器資訊
    - 檢查 Bot 狀態
    """
    if bot.user:
        print("\n" + "=" * 60)
        print(f"🤖 Bot 已就緒！")
        print(f"   名稱：{bot.user.name}")
        print(f"   ID：{bot.user.id}")
        print(f"   環境：{ENV}")
        print(f"   延遲：{round(bot.latency * 1000)}ms")
        
        # 顯示啟動統計
        if bot.startup_stats:
            stats = bot.startup_stats
            print(f"   模組：{stats['success_count']}/{stats['total_modules']} 載入成功")
            print(f"   耗時：{stats['total_time']:.2f}s")
        
        print("=" * 60)
        
        # 記錄到日誌
        logger.info(f"Bot 就緒：{bot.user.name}#{bot.user.discriminator} ({bot.user.id})")
        
        # 顯示伺服器資訊
        if bot.guilds:
            guild_info = []
            for guild in bot.guilds:
                guild_info.append(f"{guild.name} ({guild.id})")
            
            print(f"🏠 所在伺服器：{len(bot.guilds)} 個")
            for guild in guild_info:
                print(f"   - {guild}")
            
            logger.info(f"所在伺服器：{', '.join(guild_info)}")
        else:
            print("⚠️  未加入任何伺服器")
            logger.warning("Bot 未加入任何伺服器")
    else:
        error_msg = "❌ Bot 就緒但 user 屬性為 None"
        print(error_msg)
        logger.error(error_msg)

@bot.event
async def on_message(message: discord.Message):
    """
    訊息事件處理
    
    功能：
    - 過濾 Bot 訊息
    - 處理指令
    - 記錄訊息統計
    """
    # 忽略 Bot 自己的訊息
    if message.author.bot:
        return
    
    # 處理指令
    await bot.process_commands(message)

@bot.command(name="help")
async def help_command(ctx: commands.Context):
    """
    基本說明指令
    
    功能：
    - 提供使用指引
    - 引導用戶使用斜線指令
    """
    help_text = (
        "🤖 **Discord ADR Bot v1.6 使用說明**\n\n"
        "📝 **主要指令**：\n"
        "   • 使用 `/` 開頭的斜線指令\n"
        "   • 例如：`/help`、`/sync`\n\n"
        "🔧 **管理員指令**：\n"
        "   • `/sync` - 同步斜線指令\n\n"
        "📚 **更多資訊**：\n"
        "   • 查看各功能模組的說明\n"
        "   • 聯絡管理員取得協助\n\n"
        "🚀 **系統資訊**：\n"
        f"   • 環境：{ENV}\n"
        f"   • 延遲：{round(bot.latency * 1000)}ms"
    )
    
    if bot.startup_stats:
        stats = bot.startup_stats
        help_text += f"\n   • 模組：{stats['success_count']}/{stats['total_modules']} 載入成功"
    
    await ctx.send(help_text)

# =============================================================================
# 🔟 主程式進入點
# =============================================================================
async def _run():
    """
    主程式執行函數
    
    功能：
    - 驗證環境設定
    - 啟動 Bot
    - 處理啟動錯誤
    """
    # 檢查 Token
    token = os.getenv("TOKEN")
    if not token:
        print("❌ 找不到 Discord Bot Token")
        print("🔧 解決方法：")
        print("   1. 在 .env 檔案中設定 TOKEN=your_token_here")
        print("   2. 或在系統環境變數中設定 TOKEN")
        print("   3. 確保 Token 格式正確")
        sys.exit(1)
    
    # 驗證 Token 格式（基本檢查）
    if not token.startswith(("MTI", "OTk", "MTA")):
        print("⚠️  Token 格式可能不正確")
        print("   💡 Discord Bot Token 通常以 MTI、OTk 或 MTA 開頭")
    
    print("🚀 正在啟動 Bot...")
    
    try:
        await bot.start(token)
    except discord.LoginFailure:
        print("❌ Discord Token 無效")
        print("🔧 請檢查：")
        print("   - Token 是否正確複製")
        print("   - Bot 是否已正確建立")
        print("   - Token 是否已重置")
        sys.exit(1)
    except discord.HTTPException as exc:
        print(f"❌ Discord API 錯誤：{exc.status} - {exc.text}")
        print("🔧 可能原因：")
        print("   - 網路連線問題")
        print("   - Discord 服務暫時不可用")
        print("   - Bot 權限設定錯誤")
        sys.exit(1)
    except asyncio.TimeoutError:
        print("⏰ 連線超時")
        print("🔧 請檢查網路連線")
        sys.exit(1)
    except Exception as exc:
        print("💥 Bot 啟動時發生未預期錯誤")
        error_logger.exception("Bot 啟動失敗")
        print(rich_traceback(exc))
        sys.exit(1)

if __name__ == "__main__":
    # 檢查 Python 版本
    if sys.version_info < (3, 9):
        print("❌ 需要 Python 3.9 或更高版本")
        print(f"   當前版本：{sys.version}")
        print("   💡 請升級 Python 版本")
        sys.exit(1)
    
    print("🎯 Discord ADR Bot v1.6 啟動中...")
    print(f"🐍 Python 版本：{sys.version.split()[0]}")
    print(f"📁 專案路徑：{PROJECT_ROOT}")
    
    try:
        # 啟動 Bot
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n🛑 收到中斷信號，正在關閉...")
        print("👋 感謝使用 Discord ADR Bot！")
    except Exception as exc:
        print("💥 主程式發生未預期錯誤")
        error_logger.exception("主程式錯誤")
        print(rich_traceback(exc))
        sys.exit(1)