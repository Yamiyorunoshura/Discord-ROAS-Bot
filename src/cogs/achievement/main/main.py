"""成就系統主 Cog 類別.

實作 `/成就` 主指令和 Discord 互動處理。
該模組提供：
- Slash Command 註冊和處理
- 依賴注入整合
- 錯誤處理和日誌記錄
- 面板系統啟動
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from src.cogs.core.base_cog import BaseCog, StandardEmbedBuilder
from src.core.database import get_database_pool

from ..services.service_container import AchievementServiceContainer

if TYPE_CHECKING:
    from discord.ext import commands

    from ..services.achievement_service import AchievementService
    from ..services.admin_permission_service import AdminPermissionService

logger = logging.getLogger(__name__)


class AchievementCog(BaseCog):
    """成就系統主 Cog 類別.

    負責處理成就系統的 Discord 互動功能：
    - 註冊和處理 `/成就` 主指令
    - 初始化面板系統
    - 整合依賴注入容器
    - 統一錯誤處理
    """

    def __init__(self, bot: commands.Bot):
        """初始化成就系統主 Cog.

        Args:
            bot: Discord 機器人實例
        """
        super().__init__(bot)
        self.achievement_service: AchievementService | None = None
        self.admin_permission_service: AdminPermissionService | None = None
        self._service_container: AchievementServiceContainer | None = None

    async def initialize(self) -> None:
        """初始化成就系統服務和依賴."""
        try:
            # 獲取資料庫連線池
            database_pool = await get_database_pool("achievement")

            # 初始化服務容器（傳入 bot 實例以支援事件監聽）
            self._service_container = AchievementServiceContainer(database_pool, self.bot)
            await self._service_container._initialize_services()

            # 註冊服務到全域容器
            await self._register_services()

            # 解析核心服務
            self.achievement_service = self._service_container.achievement_service
            self.admin_permission_service = self._service_container.admin_permission_service

            # 初始化通知系統整合
            await self._initialize_notification_system()

            logger.info("【成就系統】主 Cog 初始化完成")

        except Exception as e:
            logger.error(f"【成就系統】主 Cog 初始化失敗: {e}")
            raise

    async def _initialize_notification_system(self) -> None:
        """初始化通知系統整合."""
        try:
            # 導入通知整合模組
            from .notification_integration import initialize_notification_integration

            # 為每個已連接的伺服器初始化通知系統
            for guild in self.bot.guilds:
                try:
                    await initialize_notification_integration(
                        guild_id=guild.id,
                        bot=self.bot,
                        repository=self._service_container.repository,
                        achievement_awarder=self._service_container.achievement_awarder
                    )
                    logger.debug(f"【通知系統】伺服器 {guild.id} 初始化完成")

                except Exception as e:
                    logger.error(f"【通知系統】伺服器 {guild.id} 初始化失敗: {e}")

            logger.info("【通知系統】整合初始化完成")

        except Exception as e:
            logger.error(f"【通知系統】整合初始化失敗: {e}")
            # 通知系統失敗不應該阻止整個成就系統的運行

    async def _register_services(self) -> None:
        """註冊成就系統服務到全域依賴容器."""
        try:
            # 註冊成就服務
            self.register_instance(
                type(self._service_container.achievement_service),
                self._service_container.achievement_service
            )

            # 註冊其他核心服務
            self.register_instance(
                type(self._service_container.repository),
                self._service_container.repository
            )

            # 註冊進度追蹤器和觸發引擎
            self.register_instance(
                type(self._service_container.progress_tracker),
                self._service_container.progress_tracker
            )

            self.register_instance(
                type(self._service_container.trigger_engine),
                self._service_container.trigger_engine
            )

            logger.debug("【成就系統】服務註冊完成")

        except Exception as e:
            logger.error(f"【成就系統】服務註冊失敗: {e}")
            raise

    @app_commands.command(name="成就", description="開啟成就系統主面板")
    async def achievement_command(self, interaction: discord.Interaction) -> None:
        """成就系統主指令.

        開啟成就系統主面板，提供：
        - 我的成就查看
        - 成就瀏覽
        - 排行榜功能

        Args:
            interaction: Discord 互動物件
        """
        # 權限檢查
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ 此指令只能在伺服器中使用",
                ephemeral=True
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ 無法獲取用戶資訊",
                ephemeral=True
            )
            return

        try:
            # 延遲回應給面板載入時間
            await interaction.response.defer(ephemeral=True)

            # 導入並建立面板
            from ..panel.achievement_panel import AchievementPanel

            panel = AchievementPanel(
                bot=self.bot,
                achievement_service=self.achievement_service,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id
            )

            # 啟動面板
            await panel.start(interaction)

        except Exception as e:
            logger.error(f"【成就系統】主指令執行失敗: {e}")

            # 發送錯誤回應
            embed = StandardEmbedBuilder.create_error_embed(
                "載入失敗",
                f"成就系統暫時無法使用，請稍後再試。\\n錯誤：{str(e)[:100]}"
            )

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as send_error:
                logger.error(f"【成就系統】發送錯誤訊息失敗: {send_error}")

    @app_commands.command(name="成就管理", description="開啟成就系統管理面板（僅限管理員）")
    async def achievement_admin_command(self, interaction: discord.Interaction) -> None:
        """成就系統管理指令.

        提供管理員專用的成就系統管理面板，包含：
        - 系統概覽和統計
        - 成就管理功能（Story 4.2）
        - 用戶管理功能（Story 4.3）
        - 系統設定功能

        Args:
            interaction: Discord 互動物件
        """
        # 基本檢查
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ 此指令只能在伺服器中使用",
                ephemeral=True
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ 無法獲取用戶資訊",
                ephemeral=True
            )
            return

        try:
            # 延遲回應給權限檢查和面板載入時間
            await interaction.response.defer(ephemeral=True)

            # 權限檢查
            if not self.admin_permission_service:
                raise RuntimeError("管理員權限服務未初始化")

            permission_result = await self.admin_permission_service.check_admin_permission(
                user=interaction.user,
                action="開啟成就管理面板",
                context={
                    "command": "成就管理",
                    "guild_name": interaction.guild.name,
                }
            )

            # 如果權限檢查失敗，處理拒絕情況
            if not permission_result.allowed:
                await self.admin_permission_service.handle_permission_denied(
                    interaction, permission_result, "使用成就管理面板"
                )
                return

            # 權限檢查通過，創建並啟動管理面板
            from ..panel.admin_panel import AdminPanel

            admin_panel = AdminPanel(
                bot=self.bot,
                achievement_service=self.achievement_service,
                admin_permission_service=self.admin_permission_service,
                guild_id=interaction.guild.id,
                admin_user_id=interaction.user.id,
            )

            # 啟動管理面板
            await admin_panel.start(interaction)

            logger.info(
                f"【成就管理】管理員 {interaction.user.id} 成功存取管理面板"
            )

        except Exception as e:
            logger.error(f"【成就管理】管理指令執行失敗: {e}")

            # 發送錯誤回應
            embed = StandardEmbedBuilder.create_error_embed(
                "管理面板載入失敗",
                f"成就管理面板暫時無法使用，請稍後再試。\n錯誤：{str(e)[:100]}"
            )

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as send_error:
                logger.error(f"【成就管理】發送錯誤訊息失敗: {send_error}")

    async def cleanup(self) -> None:
        """清理資源."""
        try:
            # 關閉通知系統
            await self._cleanup_notification_system()

            # 清理服務容器
            if self._service_container:
                await self._service_container._cleanup_services()

            await super().cleanup()
            logger.info("【成就系統】主 Cog 清理完成")
        except Exception as e:
            logger.error(f"【成就系統】主 Cog 清理失敗: {e}")

    async def _cleanup_notification_system(self) -> None:
        """清理通知系統整合."""
        try:
            from .notification_integration import get_notification_manager

            # 取得通知管理器並關閉所有服務
            manager = await get_notification_manager()
            await manager.shutdown_all()

            logger.info("【通知系統】整合清理完成")

        except Exception as e:
            logger.error(f"【通知系統】整合清理失敗: {e}")


async def setup(bot: commands.Bot) -> None:
    """載入成就系統 Cog.

    Args:
        bot: Discord 機器人實例
    """
    try:
        # 創建成就系統 Cog 實例
        achievement_cog = AchievementCog(bot)
        
        # 初始化成就系統服務
        await achievement_cog.initialize()
        
        # 添加到 bot
        await bot.add_cog(achievement_cog)
        
        logger.info("【成就系統】Cog 載入完成")
    except Exception as e:
        logger.error(f"【成就系統】Cog 載入失敗: {e}")
        raise
