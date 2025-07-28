"""
歡迎系統主要邏輯模組 - 重構版本

此模組採用依賴注入模式,提供更好的可測試性和可維護性
支援完整的依賴注入、配置管理和錯誤處理
"""

import io
import os
from typing import Any, Protocol

import discord
from discord import app_commands
from discord.ext import commands

# 導入核心依賴注入系統
from ...core.dependency_container import DependencyContainer, get_global_container
from ...core.error_handler import create_error_handler
from ...core.logger import setup_module_logger

# 導入權限檢查函數
from ..config.config import is_allowed

# 導入 UI 組件
from ..panel.main_view import SettingsView

# 設置模塊日誌記錄器
logger = setup_module_logger("welcome")
error_handler = create_error_handler("welcome", logger)


# 定義服務接口
class IWelcomeDatabase(Protocol):
    """歡迎系統資料庫服務接口"""

    async def get_settings(self, guild_id: int) -> dict[str, Any]: ...
    async def update_setting(self, guild_id: int, key: str, value: Any) -> None: ...
    async def get_background_path(self, guild_id: int) -> str | None: ...
    async def update_welcome_background(self, guild_id: int, path: str) -> None: ...
    async def exists(self, guild_id: int) -> bool: ...


class IWelcomeRenderer(Protocol):
    """歡迎系統渲染器服務接口"""

    async def generate_welcome_image(
        self,
        member: discord.Member,
        settings: dict[str, Any],
        bg_path: str | None = None,
    ) -> io.BytesIO | None: ...
    def render_message(
        self,
        member: discord.Member,
        guild: discord.Guild,
        channel: discord.TextChannel | None,
        template: str,
    ) -> str: ...


class IWelcomeCache(Protocol):
    """歡迎系統快取服務接口"""

    def get(self, guild_id: int) -> io.BytesIO | None: ...
    def set(self, guild_id: int, image: io.BytesIO) -> None: ...
    def clear(self, guild_id: int | None = None) -> None: ...


class IWelcomeConfig(Protocol):
    """歡迎系統配置服務接口"""

    @property
    def background_dir(self) -> str: ...
    @property
    def cache_timeout(self) -> int: ...
    @property
    def max_cache_size(self) -> int: ...


class WelcomeCog(commands.Cog):
    """歡迎系統 Cog - 採用依賴注入架構"""

    def __init__(self, bot: commands.Bot, container: DependencyContainer | None = None):
        """
        初始化歡迎系統 - 使用依賴注入

        Args:
            bot: Discord Bot 實例
            container: 依賴注入容器(可選,用於測試)
        """
        self.bot = bot
        self._container = container
        self._initialized = False

        # 服務實例將在 initialize 中設置
        self._db: IWelcomeDatabase | None = None
        self._renderer: IWelcomeRenderer | None = None
        self._cache: IWelcomeCache | None = None
        self._config: IWelcomeConfig | None = None

        logger.info("歡迎系統 Cog 創建完成,等待初始化")

    async def initialize(self) -> None:
        """
        異步初始化歡迎系統服務
        """
        if self._initialized:
            return

        try:
            logger.info("開始初始化歡迎系統...")
            
            # 獲取依賴注入容器
            logger.info("正在獲取依賴注入容器...")
            container = self._container or await get_global_container()
            logger.info("依賴注入容器獲取成功")

            # 解析依賴服務
            logger.info("正在解析 IWelcomeDatabase...")
            self._db = await container.resolve(IWelcomeDatabase)
            logger.info("IWelcomeDatabase 解析成功")
            
            logger.info("正在解析 IWelcomeRenderer...")
            self._renderer = await container.resolve(IWelcomeRenderer)
            logger.info("IWelcomeRenderer 解析成功")
            
            logger.info("正在解析 IWelcomeCache...")
            self._cache = await container.resolve(IWelcomeCache)
            logger.info("IWelcomeCache 解析成功")
            
            logger.info("正在解析 IWelcomeConfig...")
            self._config = await container.resolve(IWelcomeConfig)
            logger.info("IWelcomeConfig 解析成功")

            # 確保背景圖片目錄存在
            logger.info("正在創建背景圖片目錄...")
            os.makedirs(self._config.background_dir, exist_ok=True)
            logger.info("背景圖片目錄創建成功")

            self._initialized = True
            logger.info("歡迎系統依賴注入初始化完成")

        except Exception as e:
            logger.error(f"歡迎系統初始化失敗: {e}")
            raise

    @property
    def db(self) -> IWelcomeDatabase:
        """獲取資料庫服務實例"""
        if not self._db:
            raise RuntimeError("歡迎系統尚未初始化,請先調用 initialize()")
        return self._db

    @property
    def renderer(self) -> IWelcomeRenderer:
        """獲取渲染器服務實例"""
        if not self._renderer:
            raise RuntimeError("歡迎系統尚未初始化,請先調用 initialize()")
        return self._renderer

    @property
    def cache(self) -> IWelcomeCache:
        """獲取快取服務實例"""
        if not self._cache:
            raise RuntimeError("歡迎系統尚未初始化,請先調用 initialize()")
        return self._cache

    @property
    def config(self) -> IWelcomeConfig:
        """獲取配置服務實例"""
        if not self._config:
            raise RuntimeError("歡迎系統尚未初始化,請先調用 initialize()")
        return self._config

    async def _get_welcome_channel(self, guild_id: int) -> discord.TextChannel | None:
        """
        取得設定的歡迎頻道

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            discord.TextChannel | None: 歡迎頻道,如果未設定或找不到則為 None
        """
        try:
            settings = await self.db.get_settings(guild_id)
            channel_id = settings.get("channel_id")

            if not channel_id:
                return None

            channel = self.bot.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                return None

            return channel

        except Exception as e:
            logger.error(f"獲取歡迎頻道失敗 - 伺服器 {guild_id}: {e}")
            return None

    async def _generate_welcome_image(
        self, guild_id: int, member: discord.Member, force_refresh: bool = False
    ) -> io.BytesIO | None:
        """
        生成歡迎圖片

        Args:
            guild_id: Discord 伺服器 ID
            member: Discord 成員物件
            force_refresh: 是否強制重新生成,忽略快取

        Returns:
            io.BytesIO | None: 生成的圖片,如果失敗則為 None
        """
        try:
            # 檢查快取
            if not force_refresh:
                cached = self.cache.get(guild_id)
                if cached:
                    logger.debug(f"使用快取的歡迎圖片:伺服器 {guild_id}")
                    return cached

            # 取得設定
            settings = await self.db.get_settings(guild_id)
            bg_path = await self.db.get_background_path(guild_id)

            # 如果有背景圖片,確保路徑正確
            if bg_path:
                bg_path = os.path.join(
                    self.config.background_dir, os.path.basename(bg_path)
                )
                if not os.path.exists(bg_path):
                    bg_path = None

            # 生成圖片
            image = await self.renderer.generate_welcome_image(
                member, settings, bg_path
            )

            # 快取圖片
            if image:
                self.cache.set(guild_id, image)
                # 重新取得一份,因為 set 操作會修改原始資料
                return self.cache.get(guild_id)

            return None

        except Exception as e:
            logger.error(f"生成歡迎圖片失敗 - 伺服器 {guild_id}, 成員 {member.id}: {e}")
            return None

    def _safe_int(self, value: str, default: int = 0) -> int:
        """
        安全地將字串轉換為整數

        Args:
            value: 要轉換的字串
            default: 轉換失敗時的預設值

        Returns:
            int: 轉換後的整數
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def clear_image_cache(self, guild_id: int | None = None) -> None:
        """
        清除圖片快取

        Args:
            guild_id: 要清除的伺服器 ID,如果為 None 則清除所有快取
        """
        self.cache.clear(guild_id)

    async def send_welcome_message(
        self, member: discord.Member, channel: discord.TextChannel | None = None
    ) -> bool:
        """
        發送歡迎訊息

        Args:
            member: 新加入的成員
            channel: 指定的發送頻道,如果為 None 則使用設定的頻道

        Returns:
            bool: 是否成功發送
        """
        guild_id = member.guild.id

        # 如果沒有指定頻道,使用設定的頻道
        if channel is None:
            channel = await self._get_welcome_channel(guild_id)
            if channel is None:
                logger.debug(f"伺服器 {guild_id} 未設定歡迎頻道")
                return False

        try:
            # 取得設定
            settings = await self.db.get_settings(guild_id)

            # 生成圖片
            image = await self._generate_welcome_image(guild_id, member)

            # 渲染訊息
            message = settings.get(
                "message", "歡迎 {member.mention} 加入 {guild.name}!"
            )
            rendered_message = self.renderer.render_message(
                member, member.guild, channel, message
            )

            # 發送訊息
            if image:
                await channel.send(
                    content=rendered_message,
                    file=discord.File(fp=image, filename="welcome.png"),
                )
            else:
                await channel.send(content=rendered_message)

            logger.info(f"已發送歡迎訊息:伺服器 {guild_id},成員 {member.id}")
            return True

        except Exception:
            logger.error(
                f"發送歡迎訊息失敗:伺服器 {guild_id},成員 {member.id}", exc_info=True
            )
            return False

    async def handle_background_upload(
        self, interaction: discord.Interaction, attachment: discord.Attachment
    ) -> bool:
        """
        處理背景圖片上傳

        Args:
            interaction: Discord 互動物件
            attachment: 上傳的附件

        Returns:
            bool: 是否成功上傳
        """
        guild_id = interaction.guild_id
        if not guild_id:
            return False

        try:
            # 檢查檔案類型
            if not attachment.content_type or not attachment.content_type.startswith(
                ("image/png", "image/jpeg")
            ):
                await interaction.response.send_message(
                    "❌ 只接受 PNG 或 JPG 格式的圖片", ephemeral=True
                )
                return False

            # 檢查檔案大小
            if attachment.size > 5 * 1024 * 1024:  # 5MB
                await interaction.response.send_message(
                    "❌ 圖片大小不能超過 5MB", ephemeral=True
                )
                return False

            # 下載圖片
            image_data = await attachment.read()

            # 儲存圖片
            filename = f"bg_{guild_id}_{attachment.filename}"
            file_path = os.path.join(self.config.background_dir, filename)

            with open(file_path, "wb") as f:
                f.write(image_data)

            # 更新資料庫
            await self.db.update_welcome_background(guild_id, file_path)

            # 清除快取
            self.clear_image_cache(guild_id)

            logger.info(f"已上傳背景圖片:伺服器 {guild_id},檔案 {filename}")
            return True

        except Exception:
            logger.error(f"上傳背景圖片失敗:伺服器 {guild_id}", exc_info=True)
            return False

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """
        成員加入事件處理

        Args:
            member: 新加入的成員
        """
        await self.send_welcome_message(member)

    @app_commands.command(
        name="歡迎訊息設定", description="設定歡迎訊息的所有內容和樣式"
    )
    @app_commands.guild_only()
    @app_commands.check(is_allowed)
    async def welcome_settings_command(self, interaction: discord.Interaction) -> None:
        """
        歡迎訊息設定指令

        Args:
            interaction: Discord 互動物件
        """
        if not interaction.guild_id or not interaction.guild:
            await interaction.response.send_message(
                "❌ 此功能只能在伺服器中使用", ephemeral=True
            )
            return

        # 取得設定
        settings = await self.db.get_settings(interaction.guild_id)

        # 建立設定面板
        from ..panel.embeds.settings_embed import build_settings_embed

        embed = await build_settings_embed(self, interaction.guild, settings)

        # 建立視圖
        view = SettingsView(self)

        # 發送面板
        await interaction.response.send_message(embed=embed, view=view)

        # 取得面板訊息
        panel_msg = await interaction.original_response()
        view.panel_msg = panel_msg

    @app_commands.command(
        name="預覽歡迎訊息", description="預覽目前設定的歡迎訊息圖片效果"
    )
    @app_commands.guild_only()
    async def preview_welcome_message(self, interaction: discord.Interaction) -> None:
        """
        預覽歡迎訊息指令

        Args:
            interaction: Discord 互動物件
        """
        if not interaction.guild_id or not interaction.guild:
            await interaction.response.send_message(
                "❌ 此功能只能在伺服器中使用", ephemeral=True
            )
            return

        # 確保使用者是成員物件
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ 無法取得成員資訊", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        # 生成預覽圖片
        member = interaction.user
        image = await self._generate_welcome_image(
            interaction.guild_id, member, force_refresh=True
        )

        if image:
            # 取得設定
            settings = await self.db.get_settings(interaction.guild_id)

            # 渲染訊息
            message = settings.get(
                "message", "歡迎 {member.mention} 加入 {guild.name}!"
            )

            # 確保頻道是文字頻道
            channel = None
            if isinstance(interaction.channel, discord.TextChannel):
                channel = interaction.channel

            rendered_message = self.renderer.render_message(
                member, interaction.guild, channel, message
            )

            await interaction.followup.send(
                content=f"**預覽效果**\n{rendered_message}",
                file=discord.File(fp=image, filename="welcome_preview.png"),
            )
        else:
            await interaction.followup.send("❌ 生成預覽圖片失敗")
