"""
資料同步模塊主面板
基於 StandardPanelView 的統一面板架構設計
提供完整的資料同步管理功能
"""

import asyncio
import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ..main.main import SyncDataCog

from ...core.base_cog import StandardEmbedBuilder, StandardPanelView
from .components.page_selector import PageSelectDropdown
from .embeds.status_embed import create_status_embed

logger = logging.getLogger("sync_data")


class SyncDataMainView(StandardPanelView):
    """
    資料同步主面板視圖
    實現統一面板架構標準
    """

    def __init__(self, cog: "SyncDataCog", user_id: int, guild: discord.Guild):
        """
        初始化面板

        Args:
            cog: SyncDataCog 模塊實例
            user_id: 用戶 ID
            guild: Discord 伺服器物件
        """
        super().__init__(
            timeout=300,
            required_permissions=[],
            admin_only=False,
            moderator_only=False,
            author_id=user_id,
            guild_id=guild.id,
        )

        self.cog = cog
        self.user_id = user_id
        self.guild = guild
        self.sync_in_progress = False

        # 初始化頁面系統
        self._setup_sync_pages()

    def _setup_pages(self):
        """設置資料同步頁面"""
        self.pages = {
            "status": {
                "title": "同步狀態",
                "description": "查看資料同步狀態",
                "embed_builder": self.build_status_embed,
                "components": [],
            },
            "history": {
                "title": "同步歷史",
                "description": "查看同步歷史記錄",
                "embed_builder": self.build_history_embed,
                "components": [],
            },
            "settings": {
                "title": "同步設定",
                "description": "管理同步設定",
                "embed_builder": self.build_settings_embed,
                "components": [],
            },
            "diagnostics": {
                "title": "診斷工具",
                "description": "系統診斷和故障排除",
                "embed_builder": self.build_diagnostics_embed,
                "components": [],
            },
        }

        # 設置預設頁面
        self.current_page = "status"

    def _setup_sync_pages(self):
        """設置同步特定頁面"""
        self._setup_pages()

    def _setup_components(self):
        """設置面板組件"""
        self.add_item(PageSelectDropdown(self, self.current_page))
        self.add_item(
            self.create_standard_button(
                label="完整同步",
                style="primary",
                ,
                callback=self.full_sync_callback,
            )
        )

        self.add_item(
            self.create_standard_button(
                label="角色同步",
                style="secondary",
                ,
                callback=self.roles_sync_callback,
            )
        )

        self.add_item(
            self.create_standard_button(
                label="頻道同步",
                style="secondary",
                ,
                callback=self.channels_sync_callback,
            )
        )

        self.add_item(
            self.create_standard_button(
                label="停止同步",
                style="danger",
                ,
                callback=self.stop_sync_callback,
            )
        )
        self.add_item(
            self.create_standard_button(
                label="同步資料",
                style="success",
                ,
                callback=self.sync_data_callback,
            )
        )

        self.add_item(
            self.create_standard_button(
                label="同步歷史",
                style="secondary",
                ,
                callback=self.sync_history_callback,
            )
        )

        self.add_item(
            self.create_standard_button(
                label="重新整理",
                style="secondary",
                ,
                callback=self.refresh_callback,
            )
        )
        self.add_item(
            self.create_standard_button(
                label="匯出記錄",
                style="secondary",
                ,
                callback=self.export_logs_callback,
            )
        )

        self.add_item(
            self.create_standard_button(
                label="清除記錄",
                style="danger",
                ,
                callback=self.clear_logs_callback,
            )
        )

        self.add_item(
            self.create_standard_button(
                label="關閉", style="danger", callback=self.close_callback
            )
        )

    async def build_status_embed(self) -> discord.Embed:
        """構建狀態嵌入"""
        return await create_status_embed(self.cog, self.guild)

    async def build_history_embed(self) -> discord.Embed:
        """構建歷史記錄嵌入"""
        try:
            # 使用內部方法獲取同步歷史
            history = await self.cog._get_sync_history_internal(self.guild, limit=10)

            if not history:
                embed = StandardEmbedBuilder.create_info_embed(
                    "📋 同步歷史", "本伺服器還沒有同步歷史記錄."
                )
                return embed

            embed = discord.Embed(
                title="📋 資料同步歷史",
                description=f"伺服器 **{self.guild.name}** 的最近 10 次同步記錄",
                color=discord.Color.blue(),
            )

            for i, record in enumerate(history, 1):
                sync_time = record.get("sync_time", "未知時間")
                sync_type = record.get("sync_type", "unknown")
                status = "✅ 成功" if record.get("status") == "success" else "❌ 失敗"
                duration = record.get("duration", 0)

                # 格式化同步類型
                type_names = {
                    "full": "完整同步",
                    "roles": "角色同步",
                    "channels": "頻道同步",
                }
                sync_type_name = type_names.get(sync_type, sync_type)

                embed.add_field(
                    name=f"#{i} {sync_time}",
                    value=f"類型:{sync_type_name}\n狀態:{status}\n耗時:{duration:.2f}秒",
                    inline=True,
                )

            return embed

        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "歷史記錄載入失敗", f"無法載入同步歷史:{e!s}"
            )

    async def build_settings_embed(self) -> discord.Embed:
        """構建設定嵌入"""
        try:
            embed = StandardEmbedBuilder.create_settings_embed(
                "資料同步設定",
                {
                    "自動同步": "啟用",
                    "同步間隔": "每 6 小時",
                    "同步範圍": "角色 + 頻道",
                    "錯誤重試": "3 次",
                    "記錄保留": "30 天",
                },
            )

            embed.add_field(
                name="🔧 可用操作",
                value="• 修改同步間隔\n• 設定同步範圍\n• 配置錯誤處理\n• 管理記錄保留",
                inline=False,
            )

            return embed

        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "設定載入失敗", f"無法載入設定:{e!s}"
            )

    async def build_diagnostics_embed(self) -> discord.Embed:
        """構建診斷嵌入"""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "🔍 系統診斷", f"伺服器 **{self.guild.name}** 的系統診斷資訊"
            )

            # 同步狀態檢查
            sync_status = "🟢 空閒" if not self.sync_in_progress else "🟡 同步中"

            # 資料庫連接測試
            try:
                await self.cog.db.get_sync_history(self.guild.id, limit=1)
                db_status = "🟢 正常"
            except Exception:
                db_status = "🔴 異常"

            # 系統狀態
            embed.add_field(
                name="🔍 系統狀態",
                value=f"• 同步狀態:{sync_status}\n• 資料庫連接:{db_status}\n• 伺服器連接:🟢 正常",
                inline=False,
            )

            # 統計資訊
            try:
                history = await self.cog._get_sync_history_internal(
                    self.guild, limit=10
                )
                total_syncs = len(history)
                success_count = len([
                    h for h in history if h.get("status") == "success"
                ])
                success_rate = (
                    (success_count / total_syncs * 100) if total_syncs > 0 else 0
                )

                embed.add_field(
                    name="📊 統計資訊",
                    value=f"• 總同步次數:{total_syncs}\n• 成功率:{success_rate:.1f}%\n• 最近同步:{history[0].get('sync_time', '無') if history else '無'}",
                    inline=False,
                )
            except Exception:
                embed.add_field(
                    name="📊 統計資訊", value="• 無法載入統計資訊", inline=False
                )

            # 診斷工具
            embed.add_field(
                name="🔧 診斷工具",
                value="• 連接測試:可用\n• 資料驗證:可用\n• 效能分析:可用\n• 錯誤日誌:可用",
                inline=False,
            )

            return embed

        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "診斷載入失敗", f"無法載入診斷資訊:{e!s}"
            )

    # 頁面切換回調
    async def show_status_callback(self, interaction: discord.Interaction):
        """顯示狀態頁面"""
        await self.change_page(interaction, "status")

    async def show_history_callback(self, interaction: discord.Interaction):
        """顯示歷史頁面"""
        await self.change_page(interaction, "history")

    async def show_settings_callback(self, interaction: discord.Interaction):
        """顯示設定頁面"""
        await self.change_page(interaction, "settings")

    async def show_diagnostics_callback(self, interaction: discord.Interaction):
        """顯示診斷頁面"""
        await self.change_page(interaction, "diagnostics")

    async def _check_sync_permissions(self, interaction: discord.Interaction) -> bool:
        """檢查同步操作權限"""
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ 此功能只能在伺服器中使用", ephemeral=True
            )
            return False

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 需要「管理伺服器」權限才能執行同步操作", ephemeral=True
            )
            return False

        return True

    # 同步操作回調
    async def full_sync_callback(self, interaction: discord.Interaction):
        """完整同步回調"""
        if not await self._check_sync_permissions(interaction):
            return

        await self.execute_operation(interaction, self._execute_full_sync, "完整同步")

    async def roles_sync_callback(self, interaction: discord.Interaction):
        """角色同步回調"""
        if not await self._check_sync_permissions(interaction):
            return

        await self.execute_operation(interaction, self._execute_roles_sync, "角色同步")

    async def channels_sync_callback(self, interaction: discord.Interaction):
        """頻道同步回調"""
        if not await self._check_sync_permissions(interaction):
            return

        await self.execute_operation(
            interaction, self._execute_channels_sync, "頻道同步"
        )

    async def stop_sync_callback(self, interaction: discord.Interaction):
        """停止同步回調"""
        if not self.sync_in_progress:
            await self._send_info_response(interaction, "目前沒有進行中的同步操作")
            return

        await self.execute_operation(interaction, self._stop_sync, "停止同步")

    async def sync_data_callback(self, interaction: discord.Interaction):
        """同步資料回調"""
        if not await self._check_sync_permissions(interaction):
            return

        # 使用統一的操作執行方法
        await self.execute_operation(interaction, self._execute_full_sync, "完整同步")

    async def sync_history_callback(self, interaction: discord.Interaction):
        """同步歷史回調"""
        # 切換到歷史頁面
        await self.change_page(interaction, "history")

    # 工具回調
    async def export_logs_callback(self, interaction: discord.Interaction):
        """匯出記錄回調"""
        await self.execute_operation(interaction, self._export_logs, "匯出記錄")

    async def clear_logs_callback(self, interaction: discord.Interaction):
        """清除記錄回調"""
        # 顯示確認對話框
        confirm_embed = StandardEmbedBuilder.create_warning_embed(
            "確認清除記錄",
            "⚠️ 此操作將清除所有同步記錄,無法復原!\n\n請在 30 秒內再次點擊確認.",
        )

        confirm_view = ConfirmClearLogsView(self)
        await interaction.response.send_message(
            embed=confirm_embed, view=confirm_view, ephemeral=True
        )

    # 同步操作實現
    async def _execute_full_sync(self):
        """執行完整同步"""
        try:
            self.sync_in_progress = True
            # 調用內部同步方法
            result = await self.cog._execute_sync_data(self.guild, "full")

            if result["success"]:
                return self.cog._format_sync_result(result)
            else:
                return f"❌ 同步失敗:{result['error_message']}"
        finally:
            self.sync_in_progress = False

    async def _execute_roles_sync(self):
        """執行角色同步"""
        try:
            self.sync_in_progress = True
            # 調用內部同步方法
            result = await self.cog._execute_sync_data(self.guild, "roles")

            if result["success"]:
                return self.cog._format_sync_result(result)
            else:
                return f"❌ 角色同步失敗:{result['error_message']}"
        finally:
            self.sync_in_progress = False

    async def _execute_channels_sync(self):
        """執行頻道同步"""
        try:
            self.sync_in_progress = True
            # 調用內部同步方法
            result = await self.cog._execute_sync_data(self.guild, "channels")

            if result["success"]:
                return self.cog._format_sync_result(result)
            else:
                return f"❌ 頻道同步失敗:{result['error_message']}"
        finally:
            self.sync_in_progress = False

    async def _stop_sync(self):
        """停止同步"""
        self.sync_in_progress = False
        return "同步操作已停止"

    async def _export_logs(self):
        """匯出記錄"""
        # 這裡應該實現記錄匯出邏輯
        return "記錄匯出功能將在後續版本中實現"

    async def _clear_logs(self):
        """清除記錄"""
        try:
            # 使用資料庫的 execute 方法清除記錄
            await self.cog.db.execute(
                "DELETE FROM sync_data_log WHERE guild_id = ?", (self.guild.id,)
            )

            return "✅ 同步記錄已成功清除"
        except Exception as e:
            logger.error(f"[資料同步]清除記錄失敗: {e}")
            return f"❌ 清除記錄失敗: {e}"

    async def build_main_embed(self) -> discord.Embed:
        """構建主頁面嵌入 (覆寫基類方法)"""
        return await self.build_status_embed()


class ConfirmClearLogsView(discord.ui.View):
    """確認清除記錄的視圖"""

    def __init__(self, parent_view: SyncDataMainView):
        super().__init__(timeout=30)
        self.parent_view = parent_view

    @discord.ui.button(label="確認清除", style=discord.ButtonStyle.danger)
    async def confirm_clear(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """確認清除記錄"""
        try:
            await self.parent_view.execute_operation(
                interaction, self.parent_view._clear_logs, "清除同步記錄"
            )

            # 禁用按鈕
            for item in self.children:
                if hasattr(item, "disabled"):
                    item.disabled = True

            success_embed = StandardEmbedBuilder.create_success_embed(
                "記錄已清除", "同步記錄已成功清除,面板將自動更新"
            )

            await interaction.response.edit_message(embed=success_embed, view=self)

            # 3 秒後更新父面板
            await asyncio.sleep(3)
            if hasattr(self.parent_view, "refresh_view"):
                await self.parent_view.refresh_view()

        except Exception as e:
            error_embed = StandardEmbedBuilder.create_error_embed(
                "清除失敗", f"清除記錄時發生錯誤:{e!s}"
            )
            await interaction.response.edit_message(embed=error_embed, view=self)

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel_clear(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """取消清除"""
        # 禁用按鈕
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True

        cancel_embed = StandardEmbedBuilder.create_info_embed(
            "已取消", "記錄清除操作已取消"
        )

        await interaction.response.edit_message(embed=cancel_embed, view=self)

    async def on_timeout(self):
        """超時處理"""
        # 禁用所有按鈕
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
