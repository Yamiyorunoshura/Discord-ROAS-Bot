"""
活躍度面板界面管理器
- 處理界面渲染和更新
- 提供統一的界面設計標準
- 實現響應式界面設計
"""

import logging
from datetime import datetime

import discord

from ....core.base_cog import StandardEmbedBuilder
from .data_manager import DataManager
from .permission_manager import PermissionManager

logger = logging.getLogger("activity_meter")


class UIManager:
    """
    界面管理器

    功能:
    - 處理界面渲染和更新
    - 提供統一的界面設計標準
    - 實現響應式界面設計
    """

    def __init__(
        self, data_manager: DataManager, permission_manager: PermissionManager
    ):
        """
        初始化界面管理器

        Args:
            data_manager: 數據管理器
            permission_manager: 權限管理器
        """
        self.data_manager = data_manager
        self.permission_manager = permission_manager

    async def render_current_page(
        self, page_name: str, guild_id: int, user: discord.Member
    ) -> discord.Embed:
        """
        渲染當前頁面 - 修復版本

        Args:
            page_name: 頁面名稱
            guild_id: 伺服器 ID
            user: 用戶

        Returns:
            discord.Embed: 頁面嵌入
        """
        try:
            # 檢查權限
            if not self.permission_manager.can_access_page(user, page_name):
                return self._create_permission_error_embed(page_name)

            # 頁面渲染器映射
            page_renderers = {
                "settings": self._render_settings_page,
                "preview": self._render_preview_page,
                "stats": self._render_stats_page,
                "history": self._render_history_page,
            }

            renderer = page_renderers.get(page_name)
            if renderer:
                return await renderer(guild_id, user)

            return self._create_error_embed(f"未知頁面: {page_name}")

        except Exception as e:
            logger.error(f"渲染頁面失敗: {e}")
            return self._create_error_embed(f"頁面載入失敗: {e!s}")

    async def handle_error(
        self, interaction: discord.Interaction, error_type: str, context: str
    ):
        """
        統一錯誤處理機制 - 修復版本

        Args:
            interaction: Discord 互動
            error_type: 錯誤類型
            context: 錯誤上下文
        """
        try:
            error_message = self._get_error_message(error_type, context)

            # 發送錯誤訊息
            await interaction.response.send_message(error_message, ephemeral=True)

            # 記錄錯誤日誌
            logger.error(f"Panel error: {error_type} - {context}")

        except Exception as e:
            logger.error(f"錯誤處理失敗: {e}")
            # 發送通用錯誤訊息
            await interaction.response.send_message(
                "❌ 發生未預期的錯誤,請稍後再試", ephemeral=True
            )

    def _get_error_message(self, error_type: str, context: str) -> str:
        """
        獲取錯誤訊息

        Args:
            error_type: 錯誤類型
            context: 錯誤上下文

        Returns:
            str: 用戶友好的錯誤訊息
        """
        error_messages = {
            "page_switch_failed": f"❌ 頁面切換失敗:{context}",
            "time_format_error": "❌ 時間格式錯誤,請使用 HH:MM 格式",
            "permission_denied": "❌ 權限不足,需要管理伺服器權限",
            "database_error": f"❌ 數據庫操作失敗:{context}",
            "render_error": f"❌ 頁面渲染失敗:{context}",
            "unknown_error": f"❌ 未知錯誤:{context}",
        }

        return error_messages.get(error_type, f"❌ 錯誤:{context}")

    async def _render_settings_page(
        self, guild_id: int, user: discord.Member
    ) -> discord.Embed:
        """渲染設定頁面"""
        settings = await self.data_manager.get_settings(guild_id)

        embed = discord.Embed(
            title="⚙️ 活躍度系統設定",
            description="管理活躍度系統的各項設定",
            color=discord.Color.blue(),
        )

        # 添加設定項目
        embed.add_field(
            name="📊 活躍度增益",
            value=f"`{settings.get('activity_gain', 5.0)}` 分/訊息",
            inline=True,
        )

        embed.add_field(
            name="⏰ 自動播報時間",
            value=f"`{settings.get('report_hour', 21)}:00`",
            inline=True,
        )

        embed.add_field(
            name="🔄 系統狀態",
            value="✅ 啟用中" if settings.get("system_enabled", True) else "❌ 已停用",
            inline=True,
        )

        # 顯示頻道設定
        channel_id = settings.get("channel_id")
        if channel_id:
            channel = user.guild.get_channel(channel_id)
            embed.add_field(
                name="📢 播報頻道",
                value=channel.mention if channel else "頻道已刪除",
                inline=False,
            )
        else:
            embed.add_field(name="📢 播報頻道", value="未設定", inline=False)

        embed.set_footer(text="活躍度系統 • 設定面板")

        return embed

    async def _render_preview_page(
        self, guild_id: int, user: discord.Member
    ) -> discord.Embed:
        """渲染預覽頁面"""
        rankings = await self.data_manager.get_rankings(guild_id, "daily")

        embed = discord.Embed(
            title="📊 排行榜預覽",
            description="這是自動播報排行榜的預覽效果",
            color=discord.Color.green(),
        )

        if not rankings:
            embed.add_field(
                name="📭 尚無資料",
                value="今天還沒有人發送訊息,無法顯示排行榜",
                inline=False,
            )
        else:
            # 生成排行榜
            lines = []
            for rank, data in enumerate(rankings, 1):
                user_id = data["user_id"]
                msg_cnt = data["msg_cnt"]

                member = user.guild.get_member(user_id)
                name = member.display_name if member else f"<@{user_id}>"

                lines.append(f"`#{rank:2}` {name:<20} ‧ 今日 {msg_cnt} 則")

            embed.description = "\n".join(lines)

        # 顯示播報頻道資訊
        settings = await self.data_manager.get_settings(guild_id)
        channel_id = settings.get("channel_id")

        if channel_id:
            channel = user.guild.get_channel(channel_id)
            embed.add_field(
                name="📢 自動播報頻道",
                value=channel.mention if channel else "找不到頻道",
                inline=False,
            )
        else:
            embed.add_field(
                name="📢 自動播報頻道",
                value="尚未設定,使用設定頁面來設定",
                inline=False,
            )

        embed.set_footer(
            text=f"活躍度系統 • 預覽面板 • {datetime.now().strftime('%Y-%m-%d')}"
        )

        return embed

    async def _render_stats_page(
        self, guild_id: int, user: discord.Member
    ) -> discord.Embed:
        """渲染統計頁面"""
        stats = await self.data_manager.get_stats(guild_id)

        embed = discord.Embed(
            title="📈 活躍度系統統計",
            description="伺服器活躍度統計資訊",
            color=discord.Color.gold(),
        )

        # 顯示今日排行榜
        today_text = "今天還沒有人發送訊息"
        if stats.get("today_rankings"):
            today_lines = []
            for rank, data in enumerate(stats["today_rankings"], 1):
                user_id = data["user_id"]
                msg_cnt = data["msg_cnt"]

                member = user.guild.get_member(user_id)
                name = member.display_name if member else f"<@{user_id}>"

                today_lines.append(f"`#{rank}` {name} - {msg_cnt} 則")

            today_text = "\n".join(today_lines)

        embed.add_field(name="🔹 今日排行", value=today_text, inline=True)

        # 顯示昨日排行榜
        yesterday_text = "昨天沒有記錄"
        if stats.get("yesterday_rankings"):
            yesterday_lines = []
            for rank, data in enumerate(stats["yesterday_rankings"], 1):
                user_id = data["user_id"]
                msg_cnt = data["msg_cnt"]

                member = user.guild.get_member(user_id)
                name = member.display_name if member else f"<@{user_id}>"

                yesterday_lines.append(f"`#{rank}` {name} - {msg_cnt} 則")

            yesterday_text = "\n".join(yesterday_lines)

        embed.add_field(name="🔹 昨日排行", value=yesterday_text, inline=True)

        # 顯示總體統計
        total_messages = stats.get("total_messages", 0)
        active_users = stats.get("active_users", 0)

        embed.add_field(
            name="📊 總體統計",
            value=f"總訊息數:{total_messages}\n活躍用戶:{active_users}",
            inline=False,
        )

        embed.set_footer(text=f"活躍度系統 • 統計面板 • {stats.get('date', '')}")

        return embed

    async def _render_history_page(
        self, _guild_id: int, user: discord.Member
    ) -> discord.Embed:
        """渲染歷史頁面"""
        embed = discord.Embed(
            title="📜 活躍度歷史記錄",
            description=f"顯示 {user.guild.name} 的活躍度歷史記錄",
            color=discord.Color.purple(),
        )

        # 暫時顯示佔位符內容
        embed.add_field(
            name="📜 歷史記錄", value="歷史記錄功能將在後續版本中實現", inline=False
        )

        embed.set_footer(text="活躍度系統 • 歷史面板")

        return embed

    def _create_permission_error_embed(self, page_name: str) -> discord.Embed:
        """創建權限錯誤嵌入"""
        return StandardEmbedBuilder.create_error_embed(
            "權限不足", f"您沒有權限訪問「{page_name}」頁面"
        )

    def _create_error_embed(self, message: str) -> discord.Embed:
        """創建錯誤嵌入"""
        return StandardEmbedBuilder.create_error_embed("頁面載入失敗", message)

    def get_available_pages(self, user: discord.Member) -> list[str]:
        """
        獲取用戶可訪問的頁面列表

        Args:
            user: Discord 成員

        Returns:
            List[str]: 可訪問的頁面列表
        """
        available_pages = []

        for page in ["settings", "preview", "stats", "history"]:
            if self.permission_manager.can_access_page(user, page):
                available_pages.append(page)

        return available_pages
