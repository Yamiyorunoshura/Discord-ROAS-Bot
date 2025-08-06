"""Government Cog for Discord ROAS Bot v2.0.

此模組提供政府系統的 Discord Cog 實作,支援:
- 部門管理 Slash Commands
- 權限檢查和安全驗證
- Discord 角色自動同步
- 事件監聽和處理
- 管理員面板整合
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands

from src.cogs.core.base_cog import BaseCog
from src.cogs.government.panel import GovernmentPanelView
from src.cogs.government.service import (
    GovernmentService,
    GovernmentServiceError,
    RoleSyncError,
)

from ..constants import (
    MAX_CHILDREN_DISPLAY,
    MAX_ERRORS_DISPLAY,
    MAX_PERMISSIONS_DISPLAY,
)

if TYPE_CHECKING:
    from discord.ext import commands

    from src.core.database.models import Department

logger = logging.getLogger(__name__)


class GovernmentCog(BaseCog):
    """政府系統 Cog.

    提供完整的政府部門管理功能,包括 Slash Commands 和管理員界面.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """初始化政府系統 Cog.

        Args:
            bot: Discord Bot 實例
        """
        super().__init__(bot)
        self.service = GovernmentService(bot)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def cog_load(self) -> None:
        """Cog 載入時的初始化."""
        self.logger.info("政府系統 Cog 已載入")

    async def cog_unload(self) -> None:
        """Cog 卸載時的清理."""
        self.logger.info("政府系統 Cog 已卸載")

    @app_commands.command(name="政府面板", description="開啟政府系統圖形化管理面板")
    async def government_panel(self, interaction: discord.Interaction):
        """開啟政府面板."""
        try:
            await interaction.response.defer()

            # 創建政府面板視圖
            panel_view = GovernmentPanelView(
                bot=self.bot,
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                government_service=self.service,
            )

            # 載入資料並創建初始 Embed
            await panel_view.load_data()
            embed = await panel_view.create_main_embed()

            # 發送面板
            await interaction.followup.send(embed=embed, view=panel_view)

            # 記錄使用
            self.logger.info(
                f"政府面板已開啟 - 伺服器: {interaction.guild_id}, "
                f"使用者: {interaction.user.id} ({interaction.user.display_name})"
            )

        except Exception as e:
            self.logger.error(f"開啟政府面板失敗: {e}")
            await interaction.followup.send(
                f"❌ 開啟政府面板時發生錯誤: {e!s}", ephemeral=True
            )

    @app_commands.command(name="部門資訊", description="查看部門詳細資訊")
    @app_commands.describe(dept_name="要查看的部門名稱")
    async def department_info(
        self, interaction: discord.Interaction, dept_name: str | None = None
    ):
        """查看部門詳細資訊."""
        try:
            await interaction.response.defer()

            if dept_name:
                # 查看特定部門
                departments = await self.service.get_departments_by_guild(
                    interaction.guild_id
                )

                dept = None
                for d in departments:
                    if d.name == dept_name:
                        dept = d
                        break

                if not dept:
                    await interaction.followup.send(
                        f"❌ 部門『{dept_name}』不存在!", ephemeral=True
                    )
                    return

                embed = await self._create_department_embed(dept)
                await interaction.followup.send(embed=embed)
            else:
                # 查看所有部門
                hierarchy = await self.service.get_department_hierarchy(
                    interaction.guild_id
                )

                if not hierarchy:
                    await interaction.followup.send(
                        "📋 此伺服器尚未設置任何部門", ephemeral=True
                    )
                    return

                embed = await self._create_hierarchy_embed(hierarchy)
                await interaction.followup.send(embed=embed)

        except Exception as e:
            self.logger.error(f"查看部門資訊失敗: {e}")
            await interaction.followup.send(
                f"❌ 查看部門資訊時發生錯誤: {e!s}", ephemeral=True
            )

    @app_commands.command(name="部門統計", description="查看部門統計資料")
    async def department_stats(self, interaction: discord.Interaction):
        """查看部門統計資料."""
        try:
            await interaction.response.defer()

            stats = await self.service.get_department_statistics(interaction.guild_id)

            embed = discord.Embed(
                title="📊 部門統計資料",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="部門總數",
                value=f"{stats['total_departments']} 個",
                inline=True,
            )
            embed.add_field(
                name="已關聯角色",
                value=f"{stats['departments_with_roles']} 個",
                inline=True,
            )
            embed.add_field(
                name="總成員數",
                value=f"{stats['total_members']} 人",
                inline=True,
            )
            embed.add_field(
                name="最大階層深度",
                value=f"{stats['max_hierarchy_depth']} 層",
                inline=True,
            )

            embed.set_footer(
                text=f"最後更新: {stats['last_updated'][:16].replace('T', ' ')}"
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.logger.error(f"查看部門統計失敗: {e}")
            await interaction.followup.send(
                f"❌ 查看部門統計時發生錯誤: {e!s}", ephemeral=True
            )

    # 管理員指令群組
    dept_management = app_commands.Group(
        name="部門管理", description="部門管理相關指令(需要管理員權限)"
    )

    @dept_management.command(name="創建", description="創建新部門")
    @app_commands.describe(
        name="部門名稱",
        description="部門描述",
        parent_dept="上級部門名稱(可選)",
        auto_create_role="是否自動創建 Discord 角色",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def create_department(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str | None = None,
        parent_dept: str | None = None,
        auto_create_role: bool = True,
    ):
        """創建新部門."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 檢查權限
            if not self._check_admin_permission(interaction.user):
                await interaction.followup.send(
                    "❌ 你沒有權限執行此操作!", ephemeral=True
                )
                return

            # 查找上級部門
            parent_id = None
            if parent_dept:
                departments = await self.service.get_departments_by_guild(
                    interaction.guild_id
                )

                for dept in departments:
                    if dept.name == parent_dept:
                        parent_id = dept.id
                        break

                if not parent_id:
                    await interaction.followup.send(
                        f"❌ 上級部門『{parent_dept}』不存在!", ephemeral=True
                    )
                    return

            # 創建部門
            department = await self.service.create_department(
                guild_id=interaction.guild_id,
                name=name,
                description=description,
                parent_id=parent_id,
                actor_id=interaction.user.id,
                auto_create_role=auto_create_role,
            )

            # 回應成功
            embed = discord.Embed(
                title="✅ 部門創建成功",
                description=f"部門『{name}』已成功創建",
                color=discord.Color.green(),
            )

            if department.role_id:
                role = interaction.guild.get_role(department.role_id)
                if role:
                    embed.add_field(name="關聯角色", value=role.mention, inline=True)

            if parent_dept:
                embed.add_field(name="上級部門", value=parent_dept, inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except GovernmentServiceError as e:
            await interaction.followup.send(f"❌ 創建部門失敗: {e!s}", ephemeral=True)
        except Exception as e:
            self.logger.error(f"創建部門失敗: {e}")
            await interaction.followup.send(
                f"❌ 創建部門時發生未知錯誤: {e!s}", ephemeral=True
            )

    @dept_management.command(name="刪除", description="刪除部門")
    @app_commands.describe(
        name="要刪除的部門名稱",
        force_delete="是否強制刪除(即使有子部門)",
        delete_role="是否同時刪除 Discord 角色",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def delete_department(
        self,
        interaction: discord.Interaction,
        name: str,
        force_delete: bool = False,
        delete_role: bool = True,
    ):
        """刪除部門."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 檢查權限
            if not self._check_admin_permission(interaction.user):
                await interaction.followup.send(
                    "❌ 你沒有權限執行此操作!", ephemeral=True
                )
                return

            # 查找部門
            departments = await self.service.get_departments_by_guild(
                interaction.guild_id
            )

            department = None
            for dept in departments:
                if dept.name == name:
                    department = dept
                    break

            if not department:
                await interaction.followup.send(
                    f"❌ 部門『{name}』不存在!", ephemeral=True
                )
                return

            # 確認刪除
            view = ConfirmDeletionView(
                department, force_delete, delete_role, self.service, interaction.user.id
            )

            embed = discord.Embed(
                title="⚠️ 確認刪除部門",
                description=f"你確定要刪除部門『{name}』嗎?",
                color=discord.Color.orange(),
            )

            if department.children:
                children_count = len([c for c in department.children if c.is_active])
                if children_count > 0 and not force_delete:
                    embed.add_field(
                        name="⚠️ 警告",
                        value=f"此部門有 {children_count} 個子部門,需要啟用『強制刪除』才能刪除",
                        inline=False,
                    )

            if department.role_id and delete_role:
                role = interaction.guild.get_role(department.role_id)
                if role:
                    embed.add_field(
                        name="將同時刪除角色", value=role.mention, inline=True
                    )

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            self.logger.error(f"刪除部門失敗: {e}")
            await interaction.followup.send(
                f"❌ 刪除部門時發生錯誤: {e!s}", ephemeral=True
            )

    @dept_management.command(name="同步角色", description="同步所有部門的 Discord 角色")
    @app_commands.default_permissions(manage_guild=True)
    async def sync_roles(self, interaction: discord.Interaction):
        """同步所有部門的 Discord 角色."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 檢查權限
            if not self._check_admin_permission(interaction.user):
                await interaction.followup.send(
                    "❌ 你沒有權限執行此操作!", ephemeral=True
                )
                return

            # 執行同步
            results = await self.service.sync_roles_for_guild(interaction.guild_id)

            embed = discord.Embed(
                title="🔄 角色同步完成",
                color=discord.Color.green(),
            )

            embed.add_field(
                name="總部門數", value=str(results["total_departments"]), inline=True
            )
            embed.add_field(
                name="創建角色", value=str(results["roles_created"]), inline=True
            )
            embed.add_field(
                name="更新角色", value=str(results["roles_updated"]), inline=True
            )

            if results["errors"]:
                error_text = "\n".join(
                    results["errors"][:MAX_ERRORS_DISPLAY]
                )  # 最多顯示錯誤數量
                if len(results["errors"]) > MAX_ERRORS_DISPLAY:
                    error_text += f"\n... 還有 {len(results['errors']) - MAX_ERRORS_DISPLAY} 個錯誤"

                embed.add_field(
                    name="⚠️ 錯誤", value=f"```{error_text}```", inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except RoleSyncError as e:
            await interaction.followup.send(f"❌ 角色同步失敗: {e!s}", ephemeral=True)
        except Exception as e:
            self.logger.error(f"角色同步失敗: {e}")
            await interaction.followup.send(
                f"❌ 角色同步時發生未知錯誤: {e!s}", ephemeral=True
            )

    def _check_admin_permission(self, user: discord.Member | discord.User) -> bool:
        """檢查用戶是否有管理員權限."""
        if isinstance(user, discord.Member):
            return user.guild_permissions.manage_guild
        return False

    async def _create_department_embed(self, department: Department) -> discord.Embed:
        """創建部門資訊 Embed."""
        embed = discord.Embed(
            title=f"🏛️ {department.name}",
            description=department.description or "無描述",
            color=discord.Color.blue(),
        )

        # 基本資訊
        embed.add_field(name="部門 ID", value=str(department.id)[:8], inline=True)
        embed.add_field(
            name="狀態",
            value="🟢 啟用" if department.is_active else "🔴 停用",
            inline=True,
        )

        # Discord 角色
        if department.role_id:
            guild = self.bot.get_guild(department.guild_id)
            if guild:
                role = guild.get_role(department.role_id)
                if role:
                    embed.add_field(name="關聯角色", value=role.mention, inline=True)

        # 上級部門
        if department.parent:
            embed.add_field(name="上級部門", value=department.parent.name, inline=True)

        # 子部門
        if department.children:
            active_children = [c for c in department.children if c.is_active]
            if active_children:
                children_names = [
                    c.name for c in active_children[:MAX_CHILDREN_DISPLAY]
                ]
                children_text = ", ".join(children_names)
                if len(active_children) > MAX_CHILDREN_DISPLAY:
                    children_text += f" 等 {len(active_children)} 個"
                embed.add_field(name="子部門", value=children_text, inline=False)

        # 權限
        if department.permissions:
            perms = list(department.permissions.keys())[:MAX_PERMISSIONS_DISPLAY]
            perms_text = ", ".join(perms)
            if len(department.permissions) > MAX_PERMISSIONS_DISPLAY:
                perms_text += f" 等 {len(department.permissions)} 項"
            embed.add_field(name="權限", value=perms_text, inline=False)

        return embed

    async def _create_hierarchy_embed(
        self, hierarchy: list[dict[str, Any]]
    ) -> discord.Embed:
        """創建部門階層 Embed."""
        embed = discord.Embed(
            title="🏛️ 部門階層結構",
            color=discord.Color.blue(),
        )

        def format_department_tree(dept: dict[str, Any], level: int = 0) -> str:
            indent = "　" * level
            icon = "📁" if dept["children"] else "📄"
            name = dept["name"]
            member_count = dept["member_count"]

            result = f"{indent}{icon} **{name}** ({member_count} 人)\n"

            for child in dept["children"]:
                result += format_department_tree(child, level + 1)

            return result

        hierarchy_text = ""
        for dept in hierarchy[:10]:  # 最多顯示 10 個根部門
            hierarchy_text += format_department_tree(dept)

        if hierarchy_text:
            embed.description = hierarchy_text[:4000]  # Discord 限制
        else:
            embed.description = "無部門資料"

        embed.set_footer(text=f"共 {len(hierarchy)} 個根部門")
        return embed


class ConfirmDeletionView(discord.ui.View):
    """確認刪除部門的視圖."""

    def __init__(
        self,
        department: Department,
        force: bool,
        delete_role: bool,
        service: GovernmentService,
        actor_id: int,
    ):
        super().__init__(timeout=60.0)
        self.department = department
        self.force = force
        self.delete_role = delete_role
        self.service = service
        self.actor_id = actor_id

    @discord.ui.button(label="確認刪除", style=discord.ButtonStyle.danger)
    async def confirm_delete(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        """確認刪除按鈕."""
        try:
            # 檢查權限
            if interaction.user.id != self.actor_id:
                await interaction.response.send_message(
                    "❌ 只有發起者可以確認此操作!", ephemeral=True
                )
                return

            await interaction.response.defer()

            # 執行刪除
            success = await self.service.delete_department(
                self.department.id,
                actor_id=self.actor_id,
                force=self.force,
                delete_role=self.delete_role,
            )

            if success:
                embed = discord.Embed(
                    title="✅ 部門刪除成功",
                    description=f"部門『{self.department.name}』已成功刪除",
                    color=discord.Color.green(),
                )
                await interaction.edit_original_response(embed=embed, view=None)
            else:
                await interaction.edit_original_response(
                    content="❌ 刪除失敗,請檢查條件是否滿足", view=None
                )

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ 刪除失敗: {e!s}", view=None
            )

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel_delete(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        """取消刪除按鈕."""
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "❌ 只有發起者可以取消此操作!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="取消刪除",
            description="已取消刪除操作",
            color=discord.Color.secondary(),
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_timeout(self):
        """超時處理."""
        for item in self.children:
            item.disabled = True


async def setup(bot: commands.Bot) -> None:
    """載入 Cog."""
    await bot.add_cog(GovernmentCog(bot))


async def teardown(bot: commands.Bot) -> None:
    """卸載 Cog."""
    await bot.remove_cog("GovernmentCog")
