# cogs/protection/base.py ── 群組保護模組基礎類別
# ============================================================
# 功能說明:
#  - 提供群組保護模組的基礎功能
#  - 包含資料庫操作、日誌記錄、權限檢查
#  - 統一的錯誤處理機制
#  - 可被其他保護模組繼承使用
# ============================================================

import asyncio
import contextlib
import datetime as dt
import logging
import logging.handlers
import traceback

# ────────────────────────────
# 日誌配置
# ────────────────────────────
import discord
from discord import app_commands
from discord.ext import commands

from src.core.config import get_settings

# 使用配置系統獲取正確的日誌路徑
_settings = get_settings()
LOG_PATH = _settings.get_log_file_path("protection")

# 確保日誌目錄存在
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# 設定日誌處理器
_log_handler = logging.handlers.RotatingFileHandler(
    LOG_PATH, encoding="utf-8", mode="a", maxBytes=2 * 1024 * 1024, backupCount=2
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger = logging.getLogger("protection")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(_log_handler)
    logger.addHandler(logging.StreamHandler())

def friendly_trace(exc: BaseException, depth: int = 3) -> str:
    """生成友善的錯誤追蹤資訊

    Args:
        exc: 異常物件
        depth: 追蹤深度

    Returns:
        格式化的錯誤追蹤字串
    """
    return "".join(
        traceback.TracebackException.from_exception(exc, limit=depth).format()
    )

def friendly_log(msg: str, exc: BaseException | None = None, level=logging.ERROR):
    """記錄友善的錯誤訊息,包含追蹤碼和詳細資訊

    Args:
        msg: 錯誤訊息
        exc: 異常物件(可選)
        level: 日誌等級
    """
    if exc:
        msg += f"\n原因:{exc.__class__.__name__}: {exc}\n{friendly_trace(exc)}"
    logger.log(level, msg, exc_info=bool(exc))

# ────────────────────────────
# 統一錯誤處理
# ────────────────────────────
@contextlib.contextmanager
def handle_error(ctx_or_itx: object | None, user_msg: str = "發生未知錯誤"):
    """統一的錯誤處理上下文管理器

    Args:
        ctx_or_itx: Discord 上下文或互動物件
        user_msg: 顯示給使用者的錯誤訊息
    """
    track = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    try:
        yield
    except Exception as exc:
        friendly_log(user_msg, exc)
        hint = f"❌ {user_msg}\n追蹤碼:`{track}`\n請將此碼提供給管理員."
        try:
            if isinstance(ctx_or_itx, discord.Interaction):
                if ctx_or_itx.response.is_done():
                    task = asyncio.create_task(ctx_or_itx.followup.send(hint, ephemeral=True))
                    task.add_done_callback(lambda t: t.exception())  # Log exceptions
                else:
                    task = asyncio.create_task(
                        ctx_or_itx.response.send_message(hint, ephemeral=True)
                    )
                    task.add_done_callback(lambda t: t.exception())  # Log exceptions
            elif isinstance(ctx_or_itx, commands.Context):
                task = asyncio.create_task(ctx_or_itx.reply(hint, mention_author=False))
                task.add_done_callback(lambda t: t.exception())  # Log exceptions
        except Exception:
            pass

# ────────────────────────────
# 保護模組基礎類別
# ────────────────────────────
class ProtectionCog(commands.Cog):
    """
    群組保護模組的基礎類別

    提供以下功能:
    - 資料庫配置管理(get_cfg / set_cfg)
    - 日誌記錄(log)
    - 權限檢查
    - 快取機制

    子類別需要覆寫 module_name 屬性
    """

    module_name: str = "base"

    def __init__(self, bot: commands.Bot):
        """初始化保護模組

        Args:
            bot: Discord Bot 實例
        """
        self.bot = bot
        self._cache: dict[int, dict[str, str]] = {}  # 配置快取

    # ───────── 資料庫操作 ─────────
    async def _ensure_table(self):
        """確保保護配置資料表存在"""
        sql = """
        CREATE TABLE IF NOT EXISTS protection_config(
            guild_id INTEGER,
            module   TEXT,
            key      TEXT,
            value    TEXT,
            PRIMARY KEY (guild_id, module, key)
        );"""
        database = getattr(self.bot, "database", None)
        if database:
            await database.execute(sql)

    async def get_cfg(
        self, gid: int, key: str, default: str | None = None
    ) -> str | None:
        """取得伺服器配置值

        Args:
            gid: 伺服器 ID
            key: 配置鍵名
            default: 預設值

        Returns:
            配置值或預設值
        """
        if gid not in self._cache:
            await self._ensure_table()
            database = getattr(self.bot, "database", None)
            if database:
                rows = await database.fetchall(
                    "SELECT key,value FROM protection_config WHERE guild_id=? AND module=?",
                    (gid, self.module_name),
                )
                self._cache[gid] = {r["key"]: r["value"] for r in rows}
            else:
                self._cache[gid] = {}
        return self._cache[gid].get(key, default)

    async def set_cfg(self, gid: int, key: str, value: str):
        """設定伺服器配置值

        Args:
            gid: 伺服器 ID
            key: 配置鍵名
            value: 配置值
        """
        await self._ensure_table()
        database = getattr(self.bot, "database", None)
        if database:
            await database.execute(
                "INSERT OR REPLACE INTO protection_config VALUES (?,?,?,?)",
                (gid, self.module_name, key, value),
            )
        self._cache.setdefault(gid, {})[key] = value

    # ───────── 日誌記錄 ─────────
    async def log(self, guild: discord.Guild, msg: str):
        """記錄保護事件到指定頻道

        Args:
            guild: Discord 伺服器
            msg: 日誌訊息
        """
        try:
            chan_id = await self.get_cfg(guild.id, "log_channel")
            if chan_id and chan_id.isdigit():
                ch = guild.get_channel(int(chan_id))
                if ch and isinstance(ch, discord.TextChannel):  # 確保是文字頻道
                    await ch.send(f"[{self.module_name}] {msg}")
        except Exception as exc:
            friendly_log(f"記錄日誌失敗(伺服器:{guild.id})", exc)

    # ───────── 權限檢查 ─────────
    @staticmethod
    def is_admin():
        """檢查是否為伺服器管理員(用於 prefix 指令)"""

        def pred(ctx: commands.Context) -> bool:
            if not ctx.guild:
                return False
            # 透過 guild 獲取成員物件來檢查權限
            member = ctx.guild.get_member(ctx.author.id)
            if member is None:
                return False
            return member.guild_permissions.manage_guild

        return commands.check(pred)

# ────────────────────────────
# Slash 指令權限檢查器
# ────────────────────────────
def admin_only():
    """檢查是否為伺服器管理員(用於 slash 指令)"""

    async def predicate(itx: discord.Interaction) -> bool:
        if not itx.guild:
            return False
        # 透過 guild 獲取成員物件來檢查權限
        member = itx.guild.get_member(itx.user.id)
        if member is None:
            return False
        return member.guild_permissions.manage_guild

    return app_commands.check(predicate)

# ────────────────────────────
# 背景任務安全封裝
# ────────────────────────────
def safe_task(coro):
    """安全地建立背景任務,自動處理異常

    Args:
        coro: 協程物件

    Returns:
        背景任務物件
    """
    return asyncio.create_task(_wrap_err(coro))

async def _wrap_err(coro):
    """包裝協程並處理異常"""
    try:
        await coro
    except Exception as e:
        friendly_log("背景任務錯誤", e)
