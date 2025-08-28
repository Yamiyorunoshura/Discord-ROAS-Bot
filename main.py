# =============================================================================
# Discord ADR Bot v2.4 - 主程式檔案 (重構版本)
# =============================================================================
# 功能說明：
# - 自動載入所有 Cogs（功能模組）
# - 支援開發/生產環境切換
# - 完整的錯誤處理與日誌記錄
# - 事件迴圈最佳化（uvloop）
# - 人性化的錯誤訊息顯示
# - 服務註冊和依賴注入機制
# - 統一的服務生命週期管理
# =============================================================================

from __future__ import annotations
import os, sys, glob, logging, logging.handlers, asyncio, functools, importlib
from typing import List, Optional
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.ext.commands import errors as command_errors
from discord.app_commands import AppCommandError
from datetime import datetime

# 導入新架構的核心模組
from core.database_manager import get_database_manager
from core.base_service import service_registry
from core.service_startup_manager import get_startup_manager

# =============================================================================
# 1️⃣ 事件迴圈最佳化：uvloop（僅在非Windows平台啟用）
# =============================================================================
# uvloop 是一個基於 libuv 的高性能事件迴圈實現，可顯著提升 Discord bot 效能
# 注意：Windows 平台不支援 uvloop，會自動跳過
def _setup_uvloop() -> None:
    """設定 uvloop 事件迴圈最佳化"""
    if sys.platform != "win32":
        try:
            # 嘗試載入 uvloop（可能未安裝）
            #pylint: disable=import-error
            #flake8: noqa
            #mypy: ignore-errors
            #type: ignore
            import uvloop
            uvloop.install()
            print("✅ [事件迴圈] 已啟用 uvloop 最佳化")
            print("   📈 效能提升：約 2-4 倍的事件處理速度")
        except ImportError:
            print("⚠️  [事件迴圈] uvloop 未安裝，使用標準事件迴圈")
            print("   💡 建議：執行 'pip install uvloop' 以獲得更好效能")
        except Exception as exc:
            print(f"❌ [事件迴圈] uvloop 載入失敗：{exc}")
            print("   🔧 將自動回退到標準事件迴圈")
    else:
        print("ℹ️  [事件迴圈] Windows 平台，跳過 uvloop（不支援）")

_setup_uvloop()

# =============================================================================
# 2️⃣ 全域常量與工具函數
# =============================================================================
# 專案根目錄設定
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("PROJECT_ROOT", PROJECT_ROOT)

# 日誌目錄設定
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
# 3️⃣ 日誌系統設定
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
# 4️⃣ 環境變數載入
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
    
    # 尋找存在的 .env 檔案（相對於專案根目錄）
    dotenv_path = None
    for env_file in env_files:
        candidate = os.path.join(PROJECT_ROOT, env_file)
        if os.path.exists(candidate):
            dotenv_path = candidate
            break
    
    if dotenv_path:
        try:
            load_dotenv(dotenv_path)
            print(f"✅ [環境] 已載入環境檔案：{dotenv_path}")
            logger.info(f"環境檔案載入成功：{dotenv_path}")
            return env
        except Exception as exc:
            error_msg = f"❌ [環境] 載入 {dotenv_path} 失敗"
            print(error_msg)
            print("   🔧 常見問題：")
            print("      - 檔案格式錯誤（缺少等號或引號）")
            print("      - 檔案編碼不是 UTF-8")
            print("      - 檔案權限不足")
            print(f"   📋 錯誤詳情：{exc}")
            error_logger.exception(f"環境檔案載入失敗：{dotenv_path}")
            sys.exit(1)
    else:
        print("⚠️  [環境] 找不到 .env 檔案")
        print("   💡 將使用系統環境變數")
        print("   📝 建議建立 .env 檔案以管理敏感資訊")
        return env

ENV = _load_environment()

# =============================================================================
# 5️⃣ 進階錯誤處理工具
# =============================================================================
def rich_traceback(exc: BaseException) -> str:
    """
    產生彩色化的錯誤追蹤資訊
    
    參數：
        exc: 例外物件
    
    回傳：格式化的錯誤訊息
    """
    try:
        import traceback
        import colorama
        
        # 初始化 colorama（Windows 彩色輸出支援）
        colorama.init()
        
        # 產生完整的追蹤資訊
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_text = "".join(tb_lines)
        
        # 添加顏色
        return f"{colorama.Fore.RED}{tb_text}{colorama.Style.RESET_ALL}"
    except ImportError:
        # 如果沒有 colorama，使用標準格式
        import traceback
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:
        # 如果連 traceback 都失敗，回傳基本資訊
        return f"錯誤類型：{type(exc).__name__}\n錯誤訊息：{exc}"

def interaction_try(func):
    """
    裝飾器：為 Discord 互動指令提供統一的錯誤處理
    
    功能：
    - 自動捕獲並記錄錯誤
    - 向用戶顯示友善的錯誤訊息
    - 支援已回應和未回應的互動
    """
    @functools.wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        try:
            await func(self, interaction, *args, **kwargs)
        except discord.Forbidden:
            # Discord 權限錯誤
            error_msg = "❌ 權限不足，無法執行此操作"
            error_logger.warning(f"{func.__name__} 權限不足：{interaction.user}")
        except discord.HTTPException as exc:
            # Discord API 錯誤
            error_msg = f"❌ Discord API 錯誤：{exc.status} - {exc.text}"
            error_logger.error(f"{func.__name__} HTTP 錯誤：{exc}")
        except asyncio.TimeoutError:
            # 超時錯誤
            error_msg = "⏰ 操作超時，請稍後再試"
            error_logger.warning(f"{func.__name__} 操作超時")
        except Exception as exc:
            # 其他未預期的錯誤
            error_msg = f"❌ 執行 {func.__name__} 時發生未預期錯誤"
            error_logger.exception(f"{func.__name__} 發生例外")
            print(rich_traceback(exc))
        
        # 嘗試向用戶發送錯誤訊息
        try:
            if interaction.response.is_done():
                await interaction.followup.send(error_msg)
            else:
                await interaction.response.send_message(error_msg)
        except Exception as send_exc:
            # 如果連錯誤訊息都發送失敗，記錄到日誌
            error_logger.error(f"無法發送錯誤訊息：{send_exc}")
    
    return wrapper

# =============================================================================
# 6️⃣ Discord Intents 設定
# =============================================================================
def _setup_intents() -> discord.Intents:
    """
    設定 Discord Bot 的權限意圖
    
    權限說明：
    - message_content: 讀取訊息內容（斜線指令必需）
    - members: 讀取伺服器成員資訊
    - guilds: 讀取伺服器資訊
    - presences: 讀取用戶狀態資訊
    """
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    intents.presences = True
    
    print("🔐 [權限] Discord Intents 已設定")
    return intents

intents = _setup_intents()

# =============================================================================
# 7️⃣ Cog 模組自動發現
# =============================================================================
def discover_cogs() -> List[str]:
    """
    自動發現並排序所有可用的 Cog 模組
    
    規則：
    - 只載入 .py 檔案
    - 排除特定檔案（__init__.py, config.py 等）
    - 排除基礎類別檔案（base.py）
    - database 模組優先載入
    - 支援子目錄結構
    
    回傳：排序後的模組名稱列表
    """
    # 要忽略的檔案
    IGNORE_FILES = {
        "__init__.py", "config.py", "storage.py", 
        "db.py", "view.py", "views.py", "utils.py", "base.py"
    }
    
    discovered_cogs: List[str] = []
    cogs_dir = os.path.join(PROJECT_ROOT, "cogs")
    
    if not os.path.exists(cogs_dir):
        print(f"❌ [Cogs] 找不到 cogs 目錄：{cogs_dir}")
        return []
    
    print("🔍 [Cogs] 正在掃描模組...")
    
    # 遍歷 cogs 目錄
    for root, dirs, files in os.walk(cogs_dir):
        # 計算相對路徑
        rel_path = os.path.relpath(root, PROJECT_ROOT)
        module_prefix = rel_path.replace(os.sep, ".")
        
        for file in files:
            # 檢查是否為 Python 檔案且不在忽略列表中
            if not file.endswith(".py") or file in IGNORE_FILES:
                continue
            
            # 排除以 .base 結尾的檔案
            if file.endswith(".base.py"):
                continue
            
            # 建立模組名稱
            if module_prefix == ".":
                module_name = f"cogs.{file[:-3]}"
            else:
                module_name = f"{module_prefix}.{file[:-3]}"
            
            discovered_cogs.append(module_name)
            print(f"   📦 發現模組：{module_name}")
    
    # 確保 database 模組優先載入
    discovered_cogs.sort(key=lambda m: (m != "cogs.database", m))
    
    print(f"✅ [Cogs] 共發現 {len(discovered_cogs)} 個模組")
    return discovered_cogs

COGS: List[str] = discover_cogs()

# =============================================================================
# 8️⃣ Bot 主類別
# =============================================================================
class ADRBot(commands.Bot):
    """
    Discord ADR Bot 主類別 - 重構版本
    
    特性：
    - 自動載入所有 Cog 模組
    - 分批並行載入以提升啟動速度
    - 完整的錯誤處理
    - 開發/生產環境自動切換
    - 服務註冊和依賴注入機制
    - 統一的服務生命週期管理
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database_manager = None
        self.startup_manager = None
        self.services_initialized = False
    
    async def setup_hook(self):
        """
        Bot 啟動時的初始化程序
        
        流程：
        1. 初始化核心服務（資料庫管理器）
        2. 註冊所有業務服務
        3. 分批載入所有 Cog 模組
        4. 根據環境決定是否同步斜線指令
        5. 註冊管理員同步指令
        """
        print("🚀 [Bot] 開始初始化...")
        
        # 步驟 1: 初始化核心服務
        await self._initialize_core_services()
        
        # 步驟 2: 註冊業務服務
        await self._register_business_services()
        
        # 步驟 3: 分批載入 Cog 模組（每批 6 個）
        BATCH_SIZE = 6
        
        if not COGS:
            print("❌ [Bot] 沒有找到任何 Cog 模組")
            return
        
        # 確保 database 模組第一個載入
        first_batch = [COGS[0]]
        remaining_cogs = COGS[1:]
        
        print(f"📦 [Bot] 優先載入核心模組：{first_batch[0]}")
        await self._load_batch(first_batch)
        
        # 分批載入其餘模組
        for i in range(0, len(remaining_cogs), BATCH_SIZE):
            batch = remaining_cogs[i:i + BATCH_SIZE]
            print(f"📦 [Bot] 載入批次 {i//BATCH_SIZE + 1}：{batch}")
            await self._load_batch(batch)
        
        # 步驟 4: 根據環境決定是否同步斜線指令
        if ENV != "production":
            print("🔄 [Bot] 開發模式：同步斜線指令")
            try:
                synced = await self.tree.sync()
                print(f"✅ [Bot] 已同步 {len(synced)} 個斜線指令")
                logger.info(f"開發模式同步指令：{len(synced)} 個")
            except Exception as exc:
                print(f"❌ [Bot] 同步指令失敗：{exc}")
                error_logger.exception("斜線指令同步失敗")
        else:
            print("🎯 [Bot] 生產模式：跳過指令同步")
            print("   💡 使用 /sync 指令手動同步")
            logger.info("生產模式：跳過指令同步")
        
        # 步驟 5: 註冊管理員同步指令
        self._register_sync_command()
        
        print("✅ [Bot] 初始化完成")
    
    async def _initialize_core_services(self):
        """
        初始化核心服務
        
        核心服務包括：
        - 資料庫管理器
        - 服務啟動管理器
        """
        print("🔧 [服務] 初始化核心服務...")
        
        try:
            # 初始化資料庫管理器
            self.database_manager = await get_database_manager()
            if self.database_manager.is_initialized:
                print("   ✅ 資料庫管理器已初始化")
                logger.info("資料庫管理器初始化成功")
            else:
                raise Exception("資料庫管理器初始化失敗")
            
            # 初始化服務啟動管理器
            from config import (
                SERVICE_INIT_TIMEOUT, SERVICE_CLEANUP_TIMEOUT, 
                SERVICE_BATCH_SIZE, SERVICE_HEALTH_CHECK_INTERVAL,
                FONTS_DIR, WELCOME_DEFAULT_FONT, BG_DIR
            )
            
            startup_config = {
                'service_init_timeout': SERVICE_INIT_TIMEOUT,
                'service_cleanup_timeout': SERVICE_CLEANUP_TIMEOUT,
                'service_batch_size': SERVICE_BATCH_SIZE,
                'service_health_check_interval': SERVICE_HEALTH_CHECK_INTERVAL,
                'fonts_dir': FONTS_DIR,
                'default_font': WELCOME_DEFAULT_FONT,
                'bg_dir': BG_DIR
            }
            
            self.startup_manager = await get_startup_manager(startup_config)
            print("   ✅ 服務啟動管理器已初始化")
            logger.info("服務啟動管理器初始化成功")
        
        except Exception as e:
            print(f"❌ [服務] 核心服務初始化失敗：{e}")
            error_logger.exception("核心服務初始化失敗")
            sys.exit(1)
    
    async def _register_business_services(self):
        """
        註冊業務服務
        
        使用服務啟動管理器來統一管理所有業務服務的初始化
        """
        print("🔧 [服務] 註冊業務服務...")
        
        try:
            # 使用服務啟動管理器初始化所有已發現的服務
            success = await self.startup_manager.initialize_all_services()
            
            if success:
                initialized_services = list(self.startup_manager.service_instances.keys())
                print(f"   ✅ 業務服務初始化完成，共 {len(initialized_services)} 個服務")
                for service_name in initialized_services:
                    print(f"      - {service_name}")
                logger.info(f"業務服務初始化完成：{initialized_services}")
                self.services_initialized = True
                
                # 顯示啟動摘要
                startup_summary = self.startup_manager.get_startup_summary()
                if startup_summary['elapsed_seconds']:
                    print(f"   ⏱️  服務啟動耗時：{startup_summary['elapsed_seconds']:.2f} 秒")
                
            else:
                print("⚠️  [服務] 部分業務服務初始化失敗")
                logger.warning("部分業務服務初始化失敗")
                # 獲取健康狀況報告以了解失敗詳情
                health_report = await self.startup_manager.get_service_health_status()
                failed_services = [
                    name for name, status in health_report.get('services', {}).items()
                    if status.get('status') != 'healthy'
                ]
                if failed_services:
                    print(f"   ❌ 失敗的服務：{', '.join(failed_services)}")
        
        except Exception as e:
            print(f"❌ [服務] 業務服務註冊失敗：{e}")
            error_logger.exception("業務服務註冊失敗")
            # 不終止程序，讓 Cogs 在載入時自行處理服務依賴
            print("   ⚠️  將使用備用服務註冊機制")
    
    async def close(self):
        """
        Bot 關閉時的清理程序
        """
        print("🛑 [Bot] 開始關閉程序...")
        
        try:
            # 清理所有服務
            if self.services_initialized and self.startup_manager:
                print("🧹 [服務] 清理所有服務...")
                await self.startup_manager.cleanup_all_services()
                print("   ✅ 服務清理完成")
            elif service_registry:
                # 備用清理機制
                print("🧹 [服務] 使用備用清理機制...")
                await service_registry.cleanup_all_services()
                print("   ✅ 備用服務清理完成")
            
            # 關閉資料庫連接
            if self.database_manager:
                await self.database_manager.cleanup()
                print("   ✅ 資料庫連接已關閉")
        
        except Exception as e:
            print(f"⚠️  [Bot] 清理過程中發生錯誤：{e}")
            error_logger.exception("Bot 清理過程錯誤")
        
        # 調用父類的清理方法
        await super().close()
        
        print("✅ [Bot] 關閉完成")
    
    def _register_sync_command(self):
        """註冊管理員專用的同步指令"""
        @self.tree.command(
            name="sync", 
            description="手動同步斜線指令（僅限伺服器管理員）"
        )
        async def sync_command(interaction: discord.Interaction):
            # 檢查執行環境
            if interaction.guild is None:
                await interaction.response.send_message(
                    "❌ 此指令必須在伺服器中使用"
                )
                return
            
            # 檢查權限
            member = interaction.guild.get_member(interaction.user.id)
            if member is None or not member.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "❌ 需要「管理伺服器」權限才能使用此指令"
                )
                return
            
            # 執行同步
            await interaction.response.defer(thinking=True)
            try:
                synced = await self.tree.sync()
                await interaction.followup.send(
                    f"✅ 已同步 {len(synced)} 個斜線指令"
                )
                logger.info(f"管理員 {interaction.user} 手動同步了 {len(synced)} 個指令")
            except Exception as exc:
                await interaction.followup.send(
                    f"❌ 同步失敗：{exc}"
                )
                error_logger.exception(f"管理員同步指令失敗：{interaction.user}")
    
    async def _load_batch(self, modules: List[str]):
        """
        分批並行載入 Cog 模組
        
        參數：
            modules: 要載入的模組名稱列表
        
        錯誤處理：
        - 個別模組載入失敗不影響其他模組
        - database 模組失敗會導致整個程序終止
        """
        async def _load_single_module(module_name: str):
            try:
                await self.load_extension(module_name)
                print(f"   ✅ {module_name}")
                logger.info(f"模組載入成功：{module_name}")
            except command_errors.ExtensionNotFound:
                error_msg = f"❌ 找不到模組：{module_name}"
                print(error_msg)
                error_logger.error(error_msg)
            except command_errors.ExtensionAlreadyLoaded:
                print(f"   ⚠️  {module_name}（已載入）")
            except command_errors.ExtensionFailed as exc:
                error_msg = f"❌ 模組載入失敗：{module_name}"
                print(error_msg)
                print(f"   📋 錯誤：{exc}")
                error_logger.exception(f"模組載入失敗：{module_name}")
                
                # database 模組失敗時終止程序
                if module_name == "cogs.database":
                    print("💥 核心模組載入失敗，程序終止")
                    print("🔧 請檢查：")
                    print("   - 資料庫檔案權限")
                    print("   - 資料庫連線設定")
                    print("   - 模組程式碼語法")
                    sys.exit(1)
            except Exception as exc:
                error_msg = f"❌ 未知錯誤載入 {module_name}：{exc}"
                print(error_msg)
                error_logger.exception(f"模組載入未知錯誤：{module_name}")
        
        # 並行載入所有模組
        await asyncio.gather(*map(_load_single_module, modules))

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
        print("=" * 60)
        print(f"🤖 Bot 已就緒！")
        print(f"   名稱：{bot.user.name}")
        print(f"   ID：{bot.user.id}")
        print(f"   環境：{ENV}")
        print(f"   延遲：{round(bot.latency * 1000)}ms")
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
        "🤖 **Discord ADR Bot 使用說明**\n\n"
        "📝 **主要指令**：\n"
        "   • 使用 `/` 開頭的斜線指令\n"
        "   • 例如：`/help`、`/sync`\n\n"
        "🔧 **管理員指令**：\n"
        "   • `/sync` - 同步斜線指令\n\n"
        "📚 **更多資訊**：\n"
        "   • 查看各功能模組的說明\n"
        "   • 聯絡管理員取得協助"
    )
    
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
    # 檢查 Token（支援多種環境變數名稱，優先使用 DISCORD_TOKEN）
    token = (
        os.getenv("DISCORD_TOKEN")
        or os.getenv("TOKEN")
        or os.getenv("BOT_TOKEN")
    )
    if not token:
        print("❌ 找不到 Discord Bot Token")
        print("🔧 解決方法：")
        print("   1. 在 .env 檔案中設定 DISCORD_TOKEN=your_token_here")
        print("      （也相容 TOKEN / BOT_TOKEN）")
        print("   2. 或在系統環境變數中設定 DISCORD_TOKEN")
        print("   3. 確保 Token 格式正確")
        sys.exit(1)
    
    # 驗證 Token 格式（基本檢查）
    if not token.startswith(("MTI", "OTk", "MTA", "MTM", "MTQ", "MTE", "MTY", "MTg", "MTk")):
        print("⚠️  Token 格式可能不正確")
        print("   💡 Discord Bot Token 通常以 MT 開頭，後接數字")
    
    
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
    
    print("🎯 Discord ADR Bot v2.4 啟動中...")
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