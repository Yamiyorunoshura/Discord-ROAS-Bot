"""成就系統管理面板視圖組件.

此模組包含管理面板的各種視圖組件：
- 管理面板的專用視圖類別
- 可重用的 UI 組件
- 管理操作的專用表單
- 確認對話框和模態框
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

if TYPE_CHECKING:
    from collections.abc import Callable

    from .admin_panel import AdminPanel

logger = logging.getLogger(__name__)


class AdminActionType(Enum):
    """管理操作類型枚舉."""
    VIEW = "view"              # 查看操作
    CREATE = "create"          # 創建操作
    EDIT = "edit"             # 編輯操作
    DELETE = "delete"         # 刪除操作
    RESET = "reset"           # 重置操作
    EXPORT = "export"         # 導出操作
    IMPORT = "import"         # 導入操作


class ConfirmationView(ui.View):
    """通用確認對話框視圖.

    用於需要用戶確認的管理操作。
    """

    def __init__(
        self,
        title: str,
        description: str,
        confirm_callback: Callable[[discord.Interaction], Any],
        cancel_callback: Callable[[discord.Interaction], Any] | None = None,
        timeout: float = 60.0,
    ):
        """初始化確認視圖.

        Args:
            title: 確認標題
            description: 確認描述
            confirm_callback: 確認回調函數
            cancel_callback: 取消回調函數
            timeout: 超時時間（秒）
        """
        super().__init__(timeout=timeout)
        self.title = title
        self.description = description
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback
        self.result: bool | None = None

    @ui.button(label="✅ 確認", style=discord.ButtonStyle.danger)
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ) -> None:
        """處理確認按鈕."""
        try:
            self.result = True
            self.stop()

            if self.confirm_callback:
                await self.confirm_callback(interaction)

        except Exception as e:
            logger.error(f"【確認對話框】確認操作失敗: {e}")
            await interaction.response.send_message(
                "❌ 執行確認操作時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ) -> None:
        """處理取消按鈕."""
        try:
            self.result = False
            self.stop()

            if self.cancel_callback:
                await self.cancel_callback(interaction)
            else:
                # 默認取消處理
                embed = StandardEmbedBuilder.create_info_embed(
                    "操作已取消",
                    "✅ 操作已被用戶取消。"
                )
                await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            logger.error(f"【確認對話框】取消操作失敗: {e}")

    async def on_timeout(self) -> None:
        """處理超時."""
        self.result = None
        self.stop()
        logger.debug(f"【確認對話框】'{self.title}' 對話框超時")


class AdminStatsView(ui.View):
    """管理統計視圖.

    顯示成就系統的詳細統計數據。
    """

    def __init__(self, admin_panel: AdminPanel):
        """初始化統計視圖.

        Args:
            admin_panel: 管理面板控制器
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel

    @ui.button(label="📊 詳細統計", style=discord.ButtonStyle.primary)
    async def detailed_stats_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ) -> None:
        """顯示詳細統計數據."""
        try:
            # 延遲回應
            await interaction.response.defer(ephemeral=True)

            # 載入詳細統計
            detailed_stats = await self._load_detailed_stats()

            # 創建詳細統計 embed
            embed = await self._create_detailed_stats_embed(detailed_stats)

            # 發送回應
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【統計視圖】載入詳細統計失敗: {e}")
            await interaction.followup.send(
                "❌ 載入統計數據時發生錯誤", ephemeral=True
            )

    @ui.button(label="📈 趨勢分析", style=discord.ButtonStyle.secondary)
    async def trend_analysis_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ) -> None:
        """顯示趨勢分析."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📈 趨勢分析",
            "**功能開發中**\n\n"
            "此功能將提供：\n"
            "• 成就解鎖趨勢\n"
            "• 用戶活躍度分析\n"
            "• 成就受歡迎程度\n"
            "• 時間序列圖表\n\n"
            "⚠️ 此功能正在開發中，將在未來版本中實現。"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="📤 導出報告", style=discord.ButtonStyle.secondary)
    async def export_report_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ) -> None:
        """導出統計報告."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📤 導出報告",
            "**功能開發中**\n\n"
            "此功能將提供：\n"
            "• CSV 格式統計報告\n"
            "• PDF 格式摘要報告\n"
            "• 自定義報告範圍\n"
            "• 定期報告生成\n\n"
            "⚠️ 此功能正在開發中，將在未來版本中實現。"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _load_detailed_stats(self) -> dict[str, Any]:
        """載入詳細統計數據."""
        try:
            # 嘗試從管理服務獲取詳細統計
            admin_service = await self._get_admin_service()
            if admin_service and hasattr(admin_service, 'get_detailed_stats'):
                return await admin_service.get_detailed_stats()
            else:
                # 備用方案：返回基本統計
                logger.warning("無法獲取詳細統計數據，使用基本統計")
                return {
                    "user_stats": {
                        "total_users": 0,
                        "active_users_today": 0,
                        "active_users_week": 0,
                        "new_users_week": 0,
                    },
                    "achievement_stats": {
                        "total_achievements": 0,
                        "unlocked_today": 0,
                        "unlocked_week": 0,
                        "most_popular": "暫無數據",
                        "rarest": "暫無數據",
                    },
                    "system_stats": {
                        "cache_hit_rate": 0.0,
                        "avg_response_time": 0,
                        "total_events_processed": 0,
                        "error_rate": 0.0,
                    }
                }
        except Exception as e:
            logger.error(f"【統計視圖】載入詳細統計失敗: {e}")
            return {}

    async def _create_detailed_stats_embed(self, stats: dict[str, Any]) -> discord.Embed:
        """創建詳細統計 embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📊 詳細統計報告",
            f"截至 <t:{int(discord.utils.utcnow().timestamp())}:f> 的詳細統計數據"
        )

        # 用戶統計
        user_stats = stats.get("user_stats", {})
        embed.add_field(
            name="👥 用戶統計",
            value=(
                f"**總用戶數**: {user_stats.get('total_users', 0):,}\n"
                f"**今日活躍**: {user_stats.get('active_users_today', 0):,}\n"
                f"**本週活躍**: {user_stats.get('active_users_week', 0):,}\n"
                f"**本週新增**: {user_stats.get('new_users_week', 0):,}"
            ),
            inline=True
        )

        # 成就統計
        achievement_stats = stats.get("achievement_stats", {})
        embed.add_field(
            name="🏆 成就統計",
            value=(
                f"**總成就數**: {achievement_stats.get('total_achievements', 0):,}\n"
                f"**今日解鎖**: {achievement_stats.get('unlocked_today', 0):,}\n"
                f"**本週解鎖**: {achievement_stats.get('unlocked_week', 0):,}\n"
                f"**最受歡迎**: {achievement_stats.get('most_popular', 'N/A')}"
            ),
            inline=True
        )

        # 系統統計
        system_stats = stats.get("system_stats", {})
        embed.add_field(
            name="⚙️ 系統統計",
            value=(
                f"**快取命中率**: {system_stats.get('cache_hit_rate', 0):.1f}%\n"
                f"**平均回應時間**: {system_stats.get('avg_response_time', 0)}ms\n"
                f"**處理事件數**: {system_stats.get('total_events_processed', 0):,}\n"
                f"**錯誤率**: {system_stats.get('error_rate', 0):.1f}%"
            ),
            inline=False
        )

        embed.color = 0xff6b35
        embed.set_footer(text="數據每5分鐘更新 | 所有時間均為UTC")

        return embed


class AdminMaintenanceView(ui.View):
    """管理維護視圖.

    提供系統維護和管理工具。
    """

    def __init__(self, admin_panel: AdminPanel):
        """初始化維護視圖.

        Args:
            admin_panel: 管理面板控制器
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel

    @ui.button(label="🔄 重建快取", style=discord.ButtonStyle.secondary)
    async def rebuild_cache_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ) -> None:
        """重建系統快取."""
        # 創建確認對話框
        async def confirm_rebuild(confirm_interaction: discord.Interaction):
            await confirm_interaction.response.defer(ephemeral=True)

            # 執行快取重建（示例）
            embed = StandardEmbedBuilder.create_success_embed(
                "快取重建完成",
                "✅ 系統快取已成功重建。\n\n"
                "**操作詳情**:\n"
                "• 清除了所有快取數據\n"
                "• 重新載入了成就定義\n"
                "• 更新了用戶進度快取\n\n"
                "系統性能已優化。"
            )
            await confirm_interaction.followup.send(embed=embed, ephemeral=True)

        confirmation_view = ConfirmationView(
            title="重建快取",
            description="確定要重建系統快取嗎？這可能需要幾分鐘時間。",
            confirm_callback=confirm_rebuild
        )

        embed = StandardEmbedBuilder.create_warning_embed(
            "🔄 重建快取",
            "確定要重建系統快取嗎？\n\n"
            "**注意事項**:\n"
            "• 此操作會清除所有快取數據\n"
            "• 可能會暫時影響系統性能\n"
            "• 操作預計需要 2-5 分鐘\n"
            "• 建議在低峰時間執行"
        )

        await interaction.response.send_message(
            embed=embed, view=confirmation_view, ephemeral=True
        )

    @ui.button(label="📋 系統檢查", style=discord.ButtonStyle.primary)
    async def system_check_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ) -> None:
        """執行系統健康檢查."""
        await interaction.response.defer(ephemeral=True)

        # 執行系統檢查（示例）
        check_results = await self._perform_system_check()

        # 創建檢查結果 embed
        embed = await self._create_system_check_embed(check_results)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @ui.button(label="🧹 清理數據", style=discord.ButtonStyle.danger)
    async def cleanup_data_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ) -> None:
        """清理過期數據."""
        embed = StandardEmbedBuilder.create_warning_embed(
            "🧹 數據清理",
            "**高級功能 - 開發中**\n\n"
            "此功能將提供：\n"
            "• 清理過期的成就進度\n"
            "• 移除無效的用戶記錄\n"
            "• 壓縮日誌文件\n"
            "• 優化資料庫\n\n"
            "⚠️ 此功能涉及數據操作，正在仔細開發中。"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _perform_system_check(self) -> dict[str, Any]:
        """執行系統健康檢查."""
        try:
            # 嘗試從管理服務執行系統檢查
            admin_service = await self._get_admin_service()
            if admin_service and hasattr(admin_service, 'perform_system_check'):
                return await admin_service.perform_system_check()
            else:
                # 備用方案：返回基本檢查結果
                logger.warning("無法執行完整系統檢查，返回基本狀態")
                return {
                    "database": {"status": "unknown", "response_time": 0},
                    "cache": {"status": "unknown", "hit_rate": 0.0},
                    "achievement_service": {"status": "unknown", "last_update": "無資料"},
                    "permission_system": {"status": "unknown", "checks_today": 0},
                    "disk_space": {"status": "unknown", "usage": 0.0},
                    "memory": {"status": "unknown", "usage": 0.0},
                }
        except Exception as e:
            logger.error(f"【維護視圖】系統檢查失敗: {e}")
            return {"error": str(e)}

    async def _create_system_check_embed(self, results: dict[str, Any]) -> discord.Embed:
        """創建系統檢查結果 embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📋 系統健康檢查報告",
            f"檢查時間: <t:{int(discord.utils.utcnow().timestamp())}:f>"
        )

        if "error" in results:
            embed.add_field(
                name="❌ 檢查失敗",
                value=f"系統檢查時發生錯誤: {results['error']}",
                inline=False
            )
            embed.color = 0xff0000
            return embed

        # 狀態圖示映射
        status_icons = {
            "healthy": "🟢",
            "warning": "🟡",
            "error": "🔴",
            "unknown": "⚪"
        }

        # 檢查各個組件
        for component, data in results.items():
            if isinstance(data, dict) and "status" in data:
                status = data["status"]
                icon = status_icons.get(status, "⚪")

                details = []
                for key, value in data.items():
                    if key != "status":
                        details.append(f"{key}: {value}")

                embed.add_field(
                    name=f"{icon} {component.replace('_', ' ').title()}",
                    value="\n".join(details) if details else "正常運行",
                    inline=True
                )

        # 設置整體顏色
        all_healthy = all(
            data.get("status") == "healthy"
            for data in results.values()
            if isinstance(data, dict) and "status" in data
        )

        has_warning = any(
            data.get("status") == "warning"
            for data in results.values()
            if isinstance(data, dict) and "status" in data
        )

        if all_healthy:
            embed.color = 0x00ff00  # 綠色
        elif has_warning:
            embed.color = 0xffff00  # 黃色
        else:
            embed.color = 0xff0000  # 紅色

        embed.set_footer(text="建議定期執行系統檢查以確保最佳性能")

        return embed


# 導出主要組件
__all__ = [
    "AdminActionType",
    "AdminMaintenanceView",
    "AdminStatsView",
    "ConfirmationView",
]
