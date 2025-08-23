# welcome.py  ── auto-preview & panel-refresh (optimized) edition
# ============================================================
# 主要功能：
#  - 歡迎訊息自動發送與圖片生成
#  - 互動式設定面板與即時預覽
#  - 背景圖片上傳與自訂
#  - 動態欄位支援（成員、伺服器、頻道、表情）
# 
# 效能優化：
#  - 圖片處理快取機制
#  - 資料庫連線池化
#  - 非同步操作優化
#  - 記憶體使用優化
# ============================================================

import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import io
import os
import logging
import logging.handlers
import traceback
import aiohttp
import aiosqlite
import asyncio
import contextlib
import datetime
import re
import textwrap
import typing as t
from functools import lru_cache

from config import (
    WELCOME_DB_PATH,
    WELCOME_LOG_PATH,
    WELCOME_BG_DIR,
    WELCOME_FONTS_DIR,
    WELCOME_DEFAULT_FONT,
    is_allowed,
)

# ────────────────────────────
# Logging 與錯誤 utils
# ────────────────────────────
file_handler = logging.handlers.RotatingFileHandler(
    WELCOME_LOG_PATH, encoding='utf-8', mode='a', maxBytes=2*1024*1024, backupCount=2
)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

logger = logging.getLogger("welcome")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def friendly_trace(exc: BaseException, depth: int = 3) -> str:
    """生成友善的錯誤追蹤資訊"""
    tb = traceback.TracebackException.from_exception(exc, limit=depth)
    return ''.join(tb.format())


def friendly_log(msg: str, exc: BaseException | None = None, level=logging.ERROR):
    """記錄友善的錯誤訊息，包含追蹤碼和詳細資訊"""
    if exc:
        msg = f"{msg}\n原因：{exc.__class__.__name__}: {exc}\n{friendly_trace(exc)}"
    logger.log(level, msg, exc_info=bool(exc))


@contextlib.contextmanager
def handle_error(ctx_or_inter: t.Any | None, user_msg: str = "發生未知錯誤"):
    """統一的錯誤處理上下文管理器"""
    track_code = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    try:
        yield
    except Exception as exc:
        friendly_log(user_msg, exc)
        reply = f"❌ {user_msg}。\n追蹤碼：`{track_code}`\n請將此碼提供給管理員。"
        try:
            if isinstance(ctx_or_inter, discord.Interaction):
                if ctx_or_inter.response.is_done():
                    asyncio.create_task(ctx_or_inter.followup.send(reply))
                else:
                    asyncio.create_task(ctx_or_inter.response.send_message(reply))
            elif isinstance(ctx_or_inter, commands.Context):
                asyncio.create_task(ctx_or_inter.reply(reply, mention_author=False))
        except Exception:
            pass


# ────────────────────────────
# Default settings
# ────────────────────────────
def get_default_settings():
    """取得預設的歡迎訊息設定"""
    return dict(
        channel_id=None,
        title="歡迎 {member.name}!",
        description="很高興見到你～",
        message="歡迎 {member.mention} 加入 {guild.name}！",
        avatar_x=30,
        avatar_y=80,
        title_y=60,
        description_y=120,
        title_font_size=36,
        desc_font_size=22,
        avatar_size=None
    )


# ────────────────────────────
# Database Layer (優化版)
# ────────────────────────────
class WelcomeDB:
    """歡迎訊息資料庫管理類別"""
    
    def __init__(self, db_path=WELCOME_DB_PATH):
        self.db_path = db_path
        self._connection_pool = {}  # 簡單的連線池

    async def _get_connection(self):
        """取得資料庫連線（使用簡單連線池）"""
        if self.db_path not in self._connection_pool:
            self._connection_pool[self.db_path] = await aiosqlite.connect(self.db_path)
        return self._connection_pool[self.db_path]

    async def init_db(self):
        """初始化資料庫結構"""
        try:
            db = await self._get_connection()
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcome_settings (
                    guild_id INTEGER PRIMARY KEY
                )
            """)
            
            # 動態添加欄位（如果不存在）
            columns = [
                "channel_id INTEGER",
                "title TEXT",
                "description TEXT",
                "message TEXT",
                "avatar_x INTEGER",
                "avatar_y INTEGER",
                "title_y INTEGER",
                "description_y INTEGER",
                "title_font_size INTEGER",
                "desc_font_size INTEGER",
                "avatar_size INTEGER"
            ]
            
            for col_def in columns:
                with contextlib.suppress(aiosqlite.OperationalError):
                    await db.execute(f"ALTER TABLE welcome_settings ADD COLUMN {col_def}")
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS welcome_backgrounds (
                    guild_id INTEGER PRIMARY KEY,
                    image_path TEXT
                )
            """)
            await db.commit()
            
        except Exception as exc:
            friendly_log("資料庫初始化失敗，請檢查檔案權限或路徑。", exc)

    async def get_settings(self, guild_id: int):
        """取得伺服器的歡迎訊息設定"""
        await self.init_db()
        try:
            db = await self._get_connection()
            cur = await db.execute("SELECT * FROM welcome_settings WHERE guild_id=?", (guild_id,))
            row = await cur.fetchone()
            if row:
                db_settings = dict(zip([c[0] for c in cur.description], row))
                merged = get_default_settings()
                merged.update({k: v for k, v in db_settings.items() if v is not None})
                return merged
        except Exception as exc:
            friendly_log("讀取資料庫設定失敗", exc)
        return get_default_settings()

    async def update_setting(self, guild_id: int, key: str, value):
        """更新單一設定值"""
        await self.init_db()
        try:
            if not await self.exists(guild_id):
                await self.insert_defaults(guild_id)
            db = await self._get_connection()
            await db.execute(f"UPDATE welcome_settings SET {key}=? WHERE guild_id=?", (value, guild_id))
            await db.commit()
        except Exception as exc:
            friendly_log(f"更新設定失敗（欄位: {key}）", exc)

    async def exists(self, guild_id: int):
        """檢查伺服器設定是否存在"""
        await self.init_db()
        try:
            db = await self._get_connection()
            cur = await db.execute("SELECT 1 FROM welcome_settings WHERE guild_id=?", (guild_id,))
            return await cur.fetchone() is not None
        except Exception as exc:
            friendly_log("檢查資料庫紀錄存在失敗", exc)
            return False

    async def insert_defaults(self, guild_id: int):
        """插入預設設定"""
        defaults = get_default_settings()
        try:
            db = await self._get_connection()
            await db.execute("""
                INSERT OR IGNORE INTO welcome_settings
                (guild_id, channel_id, title, description, message, avatar_x, avatar_y,
                 title_y, description_y, title_font_size, desc_font_size, avatar_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                guild_id,
                defaults["channel_id"],
                defaults["title"],
                defaults["description"],
                defaults["message"],
                defaults["avatar_x"],
                defaults["avatar_y"],
                defaults["title_y"],
                defaults["description_y"],
                defaults["title_font_size"],
                defaults["desc_font_size"],
                defaults["avatar_size"],
            ))
            await db.commit()
        except Exception as exc:
            friendly_log("寫入預設設定失敗", exc)

    async def update_welcome_background(self, guild_id: int, image_path: str):
        """更新歡迎背景圖片"""
        await self.init_db()
        try:
            db = await self._get_connection()
            await db.execute(
                "INSERT OR REPLACE INTO welcome_backgrounds (guild_id, image_path) VALUES (?, ?)",
                (guild_id, image_path)
            )
            await db.commit()
        except Exception as exc:
            friendly_log("更新背景圖片失敗", exc)

    async def get_welcome_background(self, guild_id: int):
        """取得歡迎背景圖片路徑"""
        await self.init_db()
        try:
            db = await self._get_connection()
            cur = await db.execute(
                "SELECT image_path FROM welcome_backgrounds WHERE guild_id = ?", (guild_id,)
            )
            row = await cur.fetchone()
            if row and row[0]:
                return row[0]
        except Exception as exc:
            friendly_log("取得背景圖片失敗", exc)
        return None


# ────────────────────────────
# Cog (優化版)
# ────────────────────────────
class WelcomeCog(commands.Cog):
    """歡迎訊息管理 Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = WelcomeDB()
        self.font_path = WELCOME_DEFAULT_FONT if os.path.exists(WELCOME_DEFAULT_FONT) else None
        self._image_cache = {}  # 圖片快取
        self._session = None  # HTTP 會話快取
        logger.info("WelcomeCog 初始化完成")

    async def _get_session(self):
        """取得或建立 HTTP 會話"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    def _safe_int(self, value, default=0):
        """安全地轉換為整數，處理 None 和字串"""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    # ---------- util: 构建設定面板 embed ----------
    async def _build_settings_embed(self, guild: discord.Guild):
        """建構詳細的設定面板 Embed"""
        settings = await self.db.get_settings(guild.id)
        bg_filename = await self.db.get_welcome_background(guild.id)
        
        embed = discord.Embed(
            title="🎉 歡迎訊息設定面板", 
            description="在這裡可以自訂歡迎訊息的各種設定",
            color=discord.Color.green()
        )
        
        # 基本設定
        embed.add_field(
            name="📺 歡迎頻道", 
            value=f"<#{settings['channel_id']}>" if settings['channel_id'] else "❌ 未設定", 
            inline=False
        )
        embed.add_field(
            name="🎨 背景圖片", 
            value=f"✅ {bg_filename}" if bg_filename else "❌ 未設定", 
            inline=False
        )
        
        # 文字設定
        embed.add_field(
            name="📝 圖片標題", 
            value=f"```{settings['title'] or '未設定'}```", 
            inline=False
        )
        embed.add_field(
            name="📄 圖片內容", 
            value=f"```{settings['description'] or '未設定'}```", 
            inline=False
        )
        embed.add_field(
            name="💬 歡迎訊息", 
            value=f"```{settings['message'] or '未設定'}```", 
            inline=False
        )
        
        # 位置設定
        embed.add_field(name="📍 頭像位置", value=f"X: {settings['avatar_x']}, Y: {settings['avatar_y']}", inline=True)
        embed.add_field(name="📍 標題位置", value=f"Y: {settings['title_y']}", inline=True)
        embed.add_field(name="📍 內容位置", value=f"Y: {settings['description_y']}", inline=True)
        
        # 大小設定
        embed.add_field(name="🔤 標題字體", value=f"{settings.get('title_font_size', 36)}px", inline=True)
        embed.add_field(name="🔤 內容字體", value=f"{settings.get('desc_font_size', 22)}px", inline=True)
        embed.add_field(name="🖼️ 頭像大小", value=f"{settings.get('avatar_size', int(0.22*800))}px", inline=True)
        
        # 詳細說明
        embed.add_field(
            name="✨ 動態欄位使用指南",
            value=textwrap.dedent(
                """
                **可用的動態欄位：**
                • `{member}` 或 `{member.mention}` → 提及新成員
                • `{member.name}` → 新成員名稱
                • `{member.display_name}` → 新成員顯示名稱
                • `{guild.name}` → 伺服器名稱
                • `{channel}` → 歡迎頻道
                • `{channel:頻道ID}` → 指定頻道
                • `{emoji:表情名稱}` → 伺服器表情
                
                **使用範例：**
                ```
                歡迎 {member} 加入 {guild.name}！
                請到 {channel:123456789012345678} 報到 {emoji:wave}
                ```
                
                **注意事項：**
                • 頻道 ID 可在頻道右鍵選單中找到
                • 表情名稱必須是伺服器內的表情
                • 支援 Discord 語法：`<#頻道ID>` `<:emoji:ID>`
                """
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 點擊下方選單來調整設定 | 設定完成後可使用 /預覽歡迎訊息 來查看效果")
        return embed

    # ---------- util: 發送最新預覽 ----------
    async def _send_preview(self, interaction: discord.Interaction, target_user: discord.Member | None = None):
        """發送歡迎訊息預覽"""
        user = target_user or interaction.user
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ 無法取得伺服器資訊")
            return
            
        settings = await self.db.get_settings(guild.id)
        img = await self._generate_image(guild.id, user if isinstance(user, discord.Member) else None)
        channel_obj = guild.get_channel(self._safe_int(settings["channel_id"])) if settings["channel_id"] else None
        msg_content = self.render_message(
            user, guild, channel_obj,
            str(settings["message"] or "歡迎 {member.mention} 加入！")
        )
        with io.BytesIO() as buf:
            img.save(buf, 'PNG')
            buf.seek(0)
            file = discord.File(buf, filename="welcome_preview.png")
            await interaction.followup.send(content=msg_content, file=file)

    # ---------- util: 下載頭像 (優化版) ----------
    async def _fetch_avatar_bytes(self, avatar_url: str):
        """下載頭像圖片（使用快取會話）"""
        try:
            session = await self._get_session()
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception as exc:
            friendly_log("下載頭像失敗", exc)
        return None

    # ---------- util: 產生圖片 (優化版) ----------
    async def _generate_image(self, guild_id: int, member: discord.Member | None = None, force_refresh: bool = False):
        """產生歡迎圖片（包含快取機制）
        
        Args:
            guild_id: 伺服器 ID
            member: 成員物件（可選）
            force_refresh: 強制重新生成（忽略快取）
        """
        # 快取鍵
        cache_key = f"{guild_id}_{member.id if member else 'default'}"
        
        # 檢查快取（除非強制重新生成）
        if not force_refresh and cache_key in self._image_cache:
            return self._image_cache[cache_key].copy()
        
        settings = await self.db.get_settings(guild_id)
        bg_filename = await self.db.get_welcome_background(guild_id)
        bg_path = os.path.join(WELCOME_BG_DIR, bg_filename) if bg_filename else None
        
        # 建立基礎圖片
        if bg_path and os.path.exists(bg_path):
            img = Image.open(bg_path).convert("RGBA")
        else:
            img = Image.new("RGBA", (800, 450), (54, 57, 63, 255))
        
        width, height = img.size
        draw = ImageDraw.Draw(img, "RGBA")

        # 安全地取得設定值
        title_font_size = self._safe_int(settings.get("title_font_size"), 36)
        desc_font_size = self._safe_int(settings.get("desc_font_size"), 22)
        avatar_size = self._safe_int(settings.get("avatar_size"), int(0.22 * width))
        avatar_x = self._safe_int(settings.get("avatar_x"), 30)
        avatar_y = self._safe_int(settings.get("avatar_y"), int(height/2 - avatar_size/2))

        # 處理頭像
        if member:
            avatar_bytes = await self._fetch_avatar_bytes(member.display_avatar.url)
            if avatar_bytes:
                avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                avatar.thumbnail((avatar_size, avatar_size))
                mask = Image.new("L", avatar.size, 0)
                ImageDraw.Draw(mask).ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
                avatar.putalpha(mask)
                img.paste(avatar, (avatar_x, avatar_y), avatar)

        # 載入字體
        try:
            font_title = ImageFont.truetype(self.font_path, title_font_size) if self.font_path else ImageFont.load_default()
            font_desc = ImageFont.truetype(self.font_path, desc_font_size) if self.font_path else ImageFont.load_default()
        except OSError:
            friendly_log("找不到字體檔案，已改用預設字體。", None, level=logging.WARNING)
            font_title = font_desc = ImageFont.load_default()

        # 處理文字
        title_template = str(settings["title"] or "歡迎 {member.name}!")
        desc_template = str(settings["description"] or "很高興見到你～")
        title = self.render_message(member, member.guild if member else None, None, title_template)
        desc = self.render_message(member, member.guild if member else None, None, desc_template)

        title_y = self._safe_int(settings.get("title_y"), 60)
        desc_y = self._safe_int(settings.get("description_y"), 120)
        avatar_center_x = avatar_x + avatar_size // 2

        # 計算文字寬度（相容性處理）
        try:
            title_width = font_title.getlength(title)
            desc_width = font_desc.getlength(desc)
        except AttributeError:
            # 舊版 PIL 相容性
            try:
                title_width = font_title.getbbox(title)[2]  # getbbox 回傳 (left, top, right, bottom)，取 right 值
                desc_width = font_desc.getbbox(desc)[2]
            except (AttributeError, IndexError):
                # 如果都失敗，使用估算
                title_width = len(title) * title_font_size // 2
                desc_width = len(desc) * desc_font_size // 2

        # 繪製文字
        draw.text((avatar_center_x - title_width//2, title_y), title, fill=(255,255,255,255), font=font_title)
        draw.text((avatar_center_x - desc_width//2, desc_y), desc, fill=(200,200,200,255), font=font_desc)
        
        # 快取結果
        self._image_cache[cache_key] = img.copy()
        
        return img

    def clear_image_cache(self, guild_id: int | None = None):
        """清除圖片快取
        
        Args:
            guild_id: 伺服器 ID，如果為 None 則清除所有快取
        """
        if guild_id is None:
            self._image_cache.clear()
        else:
            # 清除指定伺服器的所有快取
            keys_to_remove = [k for k in self._image_cache.keys() if k.startswith(f"{guild_id}_")]
            for key in keys_to_remove:
                del self._image_cache[key]

    # ---------- util: 格式化訊息 ----------
    def render_message(self, member, guild, channel, msg_template: str):
        """格式化訊息模板，替換動態欄位"""
        msg = str(msg_template)
        try:
            if member:
                msg = msg.replace("{member}", member.mention).replace("{member.name}", member.name).replace("{member.mention}", member.mention)
                if hasattr(member, 'display_name'):
                    msg = msg.replace("{member.display_name}", member.display_name)
            if guild:
                msg = msg.replace("{guild}", guild.name).replace("{guild.name}", guild.name)
            if channel:
                msg = msg.replace("{channel}", channel.mention).replace("{channel.name}", channel.name)
            if guild:
                # 處理指定頻道
                for chan_id in re.findall(r"{channel:(\d+)}", msg):
                    ch = guild.get_channel(int(chan_id))
                    msg = msg.replace(f"{{channel:{chan_id}}}", ch.mention if ch else f"<#{chan_id}>")
                # 處理表情
                for emojiname in re.findall(r"{emoji:([A-Za-z0-9_]+)}", msg):
                    emoji_obj = discord.utils.get(guild.emojis, name=emojiname)
                    msg = msg.replace(f"{{emoji:{emojiname}}}", str(emoji_obj) if emoji_obj else f":{emojiname}:")
        except Exception as exc:
            friendly_log("render_message 格式化失敗", exc)
        return msg

    # ───────── Slash：歡迎訊息設定 ─────────
    @app_commands.command(name="歡迎訊息設定", description="設定歡迎訊息的所有內容和樣式")
    async def welcome_settings_command(self, interaction: discord.Interaction):
        """歡迎訊息設定指令"""
        if not is_allowed(interaction, "歡迎訊息設定"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。")
            return
        if not interaction.guild:
            await interaction.response.send_message("❌ 此指令只能在伺服器中使用。")
            return
        with handle_error(interaction, "讀取歡迎訊息設定失敗"):
            embed = await self._build_settings_embed(interaction.guild)
            await interaction.response.send_message(embed=embed, view=WelcomeCog.SettingsView(self))

    # ───────── Slash：預覽 ─────────
    @app_commands.command(name="預覽歡迎訊息", description="預覽目前設定的歡迎訊息圖片效果")
    async def preview_welcome_message(self, interaction: discord.Interaction):
        """預覽歡迎訊息指令"""
        if not is_allowed(interaction, "預覽歡迎訊息"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。")
            return
        with handle_error(interaction, "預覽歡迎訊息失敗"):
            await interaction.response.defer(thinking=True)
            await self._send_preview(interaction)

    # ───────── 事件：on_member_join ─────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """新成員加入時自動發送歡迎訊息"""
        with handle_error(None, "自動歡迎訊息發送失敗"):
            settings = await self.db.get_settings(member.guild.id)
            if not settings or not settings["channel_id"]:
                logger.warning(f"伺服器 {member.guild.id} 未設定歡迎頻道，略過自動發送")
                return
            channel = self.bot.get_channel(self._safe_int(settings["channel_id"]))
            if not channel:
                logger.warning(f"找不到歡迎頻道 {settings['channel_id']}")
                return
            if not isinstance(channel, discord.TextChannel):
                logger.warning(f"頻道 {settings['channel_id']} 不是文字頻道，無法發送訊息")
                return
            msg_content = self.render_message(
                member, member.guild, channel,
                str(settings["message"] or "歡迎 {member.mention} 加入！")
            )
            img = await self._generate_image(member.guild.id, member)
            with io.BytesIO() as buf:
                img.save(buf, 'PNG')
                buf.seek(0)
                file = discord.File(buf, filename="welcome.png")
                await channel.send(content=msg_content, file=file)

    # ────────────────────────────
    # 設定互動 UI (優化版)
    # ────────────────────────────
    class SettingsView(discord.ui.View):
        """歡迎訊息設定互動面板"""
        
        def __init__(self, cog: "WelcomeCog"):
            super().__init__(timeout=180)
            self.cog = cog

        @discord.ui.select(
            placeholder="選擇要調整的設定項目",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="📺 設定歡迎頻道", description="設定歡迎訊息發送的頻道"),
                discord.SelectOption(label="📝 設定圖片標題", description="設定歡迎圖片上的標題文字"),
                discord.SelectOption(label="📄 設定圖片內容", description="設定歡迎圖片上的內容文字"),
                discord.SelectOption(label="🎨 上傳背景圖片", description="上傳自訂背景圖片（PNG/JPG）"),
                discord.SelectOption(label="💬 設定歡迎訊息", description="設定純文字歡迎訊息"),
                discord.SelectOption(label="📍 調整頭像 X 位置", description="調整頭像在圖片上的 X 座標"),
                discord.SelectOption(label="📍 調整頭像 Y 位置", description="調整頭像在圖片上的 Y 座標"),
                discord.SelectOption(label="📍 調整標題 Y 位置", description="調整標題的 Y 座標"),
                discord.SelectOption(label="📍 調整內容 Y 位置", description="調整內容的 Y 座標"),
                discord.SelectOption(label="🔤 調整標題字體大小", description="調整標題字體大小（像素）"),
                discord.SelectOption(label="🔤 調整內容字體大小", description="調整內容字體大小（像素）"),
                discord.SelectOption(label="🖼️ 調整頭像大小", description="調整頭像顯示的像素大小"),
            ]
        )
        async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
            """處理設定選單選擇"""
            opt = select.values[0]
            with handle_error(interaction, "設定選單互動發生錯誤"):
                if not interaction.guild:
                    await interaction.response.send_message("❌ 此功能只能在伺服器中使用。")
                    return
                if not interaction.message:
                    await interaction.response.send_message("❌ 無法取得原始訊息。")
                    return
                    
                if opt == "📺 設定歡迎頻道":
                    await interaction.response.send_modal(WelcomeCog.SetChannelModal(self.cog, interaction.message))
                elif opt == "📝 設定圖片標題":
                    await interaction.response.send_modal(WelcomeCog.SetTitleModal(self.cog, interaction.message))
                elif opt == "📄 設定圖片內容":
                    await interaction.response.send_modal(WelcomeCog.SetDescModal(self.cog, interaction.message))
                elif opt == "🎨 上傳背景圖片":
                    await interaction.response.send_message(
                        "📤 **上傳背景圖片**\n\n"
                        "請直接貼上 PNG 或 JPG 格式的圖片，我會自動偵測你的上傳！\n"
                        "💡 **建議尺寸：** 800x450 像素或更大\n"
                        "⏰ **上傳時限：** 3 分鐘"
                    )

                    def check(m):
                        if not (hasattr(m, 'author') and m.author and hasattr(m.author, 'id')):
                            return False
                        if not (hasattr(m, 'channel') and m.channel and hasattr(m.channel, 'id')):
                            return False
                        if m.author.id != interaction.user.id:  # type: ignore
                            return False
                        if m.channel.id != interaction.channel.id:  # type: ignore
                            return False
                        if not m.attachments:
                            return False
                        return True

                    try:
                        msg = await self.cog.bot.wait_for('message', timeout=180.0, check=check)
                        file = msg.attachments[0]
                        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                            data = await file.read()
                            ext = os.path.splitext(file.filename)[-1]
                            filename = f"welcome_bg_{interaction.guild.id}{ext}"
                            filepath = os.path.join(WELCOME_BG_DIR, filename)
                            with open(filepath, "wb") as f:
                                f.write(data)
                            await self.cog.db.update_welcome_background(interaction.guild.id, filename)

                            # 更新面板 & 發送預覽
                            new_embed = await self.cog._build_settings_embed(interaction.guild)
                            new_view = WelcomeCog.SettingsView(self.cog)
                            try:
                                if interaction.message:
                                    await interaction.followup.edit_message(interaction.message.id, embed=new_embed, view=new_view)
                            except discord.NotFound:
                                await interaction.followup.send(embed=new_embed, view=new_view)
                            await self.cog._send_preview(interaction)
                            await interaction.followup.send("✅ 背景圖片已上傳並設定！")
                        else:
                            await interaction.followup.send("❌ 只接受 PNG/JPG 格式圖片！")
                    except asyncio.TimeoutError:
                        await interaction.followup.send("⏰ 上傳逾時，請重新操作。")
                elif opt == "💬 設定歡迎訊息":
                    await interaction.response.send_modal(WelcomeCog.SetMsgModal(self.cog, interaction.message))
                elif opt == "📍 調整頭像 X 位置":
                    await interaction.response.send_modal(WelcomeCog.SetAvatarXModal(self.cog, interaction.message))
                elif opt == "📍 調整頭像 Y 位置":
                    await interaction.response.send_modal(WelcomeCog.SetAvatarYModal(self.cog, interaction.message))
                elif opt == "📍 調整標題 Y 位置":
                    await interaction.response.send_modal(WelcomeCog.SetTitleYModal(self.cog, interaction.message))
                elif opt == "📍 調整內容 Y 位置":
                    await interaction.response.send_modal(WelcomeCog.SetDescYModal(self.cog, interaction.message))
                elif opt == "🔤 調整標題字體大小":
                    await interaction.response.send_modal(WelcomeCog.SetTitleFontSizeModal(self.cog, interaction.message))
                elif opt == "🔤 調整內容字體大小":
                    await interaction.response.send_modal(WelcomeCog.SetDescFontSizeModal(self.cog, interaction.message))
                elif opt == "🖼️ 調整頭像大小":
                    await interaction.response.send_modal(WelcomeCog.SetAvatarSizeModal(self.cog, interaction.message))

    # ───────── Modal 基底 ─────────
    class _BaseModal(discord.ui.Modal):
        """Modal 基底類別，提供通用的更新邏輯"""
        
        def __init__(self, cog, panel_msg: discord.Message, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.cog = cog
            self.panel_msg = panel_msg  # 原設定面板的訊息

        async def _after_update(self, interaction: discord.Interaction):
            """更新後的回調處理"""
            # 清除圖片快取，確保設定立即生效
            if interaction.guild:
                self.cog.clear_image_cache(interaction.guild.id)
            
            # 重新建構最新面板
            if not interaction.guild:
                await interaction.followup.send("❌ 無法取得伺服器資訊")
                return
            new_embed = await self.cog._build_settings_embed(interaction.guild)
            new_view = WelcomeCog.SettingsView(self.cog)
            # 嘗試編輯原本的面板
            try:
                if self.panel_msg:
                    await interaction.followup.edit_message(self.panel_msg.id, embed=new_embed, view=new_view)
            except discord.NotFound:
                # 原訊息已消失 → 再送一則新的
                new_msg = await interaction.followup.send(embed=new_embed, view=new_view)
                self.panel_msg = new_msg
            # 預覽
            await self.cog._send_preview(interaction)

    # ───────── 各 Modal ─────────
    class SetChannelModal(_BaseModal, title="設定歡迎頻道"):
        channel = discord.ui.TextInput(
            label="頻道 ID", 
            required=True,
            placeholder="請輸入頻道 ID（可在頻道右鍵選單中找到）",
            min_length=17,
            max_length=20
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "設定歡迎頻道失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "channel_id", int(self.channel.value))
                await interaction.response.send_message(f"✅ 設定成功！歡迎頻道：<#{self.channel.value}>")
                await self._after_update(interaction)

    class SetTitleModal(_BaseModal, title="設定圖片標題"):
        title_txt = discord.ui.TextInput(
            label="標題文字", 
            required=True, 
            placeholder="可用 {member.name}、{guild.name}、{channel}、{emoji:名稱}",
            max_length=100
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "設定標題失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "title", self.title_txt.value)
                await interaction.response.send_message("✅ 標題已更新")
                await self._after_update(interaction)

    class SetDescModal(_BaseModal, title="設定圖片內容"):
        desc_txt = discord.ui.TextInput(
            label="內容文字", 
            required=True, 
            placeholder="可用 {member.mention}、{guild.name}、{channel}、{emoji:名稱}",
            max_length=200
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "設定內容失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "description", self.desc_txt.value)
                await interaction.response.send_message("✅ 內容已更新")
                await self._after_update(interaction)

    class SetMsgModal(_BaseModal, title="設定歡迎訊息"):
        msg_txt = discord.ui.TextInput(
            label="歡迎訊息", 
            required=True, 
            placeholder="可用 {member}、{channel}、{channel:ID}、{emoji:名稱}",
            max_length=500
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "設定歡迎訊息失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "message", self.msg_txt.value)
                await interaction.response.send_message("✅ 歡迎訊息已設定")
                await self._after_update(interaction)

    class SetAvatarXModal(_BaseModal, title="調整頭像 X 位置"):
        x_txt = discord.ui.TextInput(
            label="X 座標（像素）", 
            required=True,
            placeholder="建議範圍：0-800",
            min_length=1,
            max_length=4
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "調整頭像 X 失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "avatar_x", int(self.x_txt.value))
                await interaction.response.send_message("✅ 頭像 X 位置已設定")
                await self._after_update(interaction)

    class SetAvatarYModal(_BaseModal, title="調整頭像 Y 位置"):
        y_txt = discord.ui.TextInput(
            label="Y 座標（像素）", 
            required=True,
            placeholder="建議範圍：0-450",
            min_length=1,
            max_length=4
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "調整頭像 Y 失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "avatar_y", int(self.y_txt.value))
                await interaction.response.send_message("✅ 頭像 Y 位置已設定")
                await self._after_update(interaction)

    class SetTitleYModal(_BaseModal, title="調整標題 Y 位置"):
        y_txt = discord.ui.TextInput(
            label="Y 座標（像素）", 
            required=True,
            placeholder="建議範圍：0-450",
            min_length=1,
            max_length=4
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "調整標題 Y 失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "title_y", int(self.y_txt.value))
                await interaction.response.send_message("✅ 標題 Y 位置已設定")
                await self._after_update(interaction)

    class SetDescYModal(_BaseModal, title="調整內容 Y 位置"):
        y_txt = discord.ui.TextInput(
            label="Y 座標（像素）", 
            required=True,
            placeholder="建議範圍：0-450",
            min_length=1,
            max_length=4
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "調整內容 Y 失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "description_y", int(self.y_txt.value))
                await interaction.response.send_message("✅ 內容 Y 位置已設定")
                await self._after_update(interaction)

    class SetTitleFontSizeModal(_BaseModal, title="調整標題字體大小"):
        size_txt = discord.ui.TextInput(
            label="標題字體大小（像素）", 
            required=True,
            placeholder="建議範圍：20-60",
            min_length=1,
            max_length=3
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "調整標題字體大小失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "title_font_size", int(self.size_txt.value))
                await interaction.response.send_message("✅ 標題字體大小已設定")
                await self._after_update(interaction)

    class SetDescFontSizeModal(_BaseModal, title="調整內容字體大小"):
        size_txt = discord.ui.TextInput(
            label="內容字體大小（像素）", 
            required=True,
            placeholder="建議範圍：12-40",
            min_length=1,
            max_length=3
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "調整內容字體大小失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "desc_font_size", int(self.size_txt.value))
                await interaction.response.send_message("✅ 內容字體大小已設定")
                await self._after_update(interaction)

    class SetAvatarSizeModal(_BaseModal, title="調整頭像大小"):
        size_txt = discord.ui.TextInput(
            label="頭像像素大小", 
            required=True,
            placeholder="建議範圍：100-300",
            min_length=1,
            max_length=4
        )
        async def on_submit(self, interaction):
            with handle_error(interaction, "調整頭像大小失敗"):
                await self.cog.db.update_setting(interaction.guild.id, "avatar_size", int(self.size_txt.value))
                await interaction.response.send_message("✅ 頭像大小已設定")
                await self._after_update(interaction)


# ────────────────────────────
# setup
# ────────────────────────────
async def setup(bot: commands.Bot):
    """設定 WelcomeCog"""
    logger.info("執行 welcome setup()")
    await bot.add_cog(WelcomeCog(bot))