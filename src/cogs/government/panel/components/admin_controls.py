"""Admin control components.

管理員控制組件,提供部門管理和角色調整功能.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from src.cogs.government.service import GovernmentService

logger = logging.getLogger(__name__)


class AdminControls:
    """管理員控制工廠類別."""

    @staticmethod
    def create_manage_button() -> discord.ui.Button:
        """創建管理按鈕."""
        return discord.ui.Button(
            label="管理",
            style=discord.ButtonStyle.danger,
            custom_id="roas_gov_manage",
            row=3,

        )

    @staticmethod
    def create_sync_roles_button() -> discord.ui.Button:
        """創建同步角色按鈕."""
        return discord.ui.Button(
            label="同步角色",
            style=discord.ButtonStyle.secondary,
            custom_id="roas_gov_sync_roles",
            row=3,

        )


class AdminManageModal(discord.ui.Modal):
    """管理員管理模態框."""

    def __init__(
        self, government_service: GovernmentService, guild_id: int, admin_id: int
    ):
        """初始化管理模態框.

        Args:
            government_service: 政府服務實例
            guild_id: 伺服器 ID
            admin_id: 管理員 ID
        """
        super().__init__(title="⚙️ 部門管理", timeout=300.0)

        self.service = government_service
        self.guild_id = guild_id
        self.admin_id = admin_id
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 操作類型選擇
        self.action_input = discord.ui.TextInput(
            label="操作類型",
            placeholder="create/update/delete/assign",
            min_length=4,
            max_length=10,
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(self.action_input)

        # 部門名稱
        self.department_input = discord.ui.TextInput(
            label="部門名稱",
            placeholder="要操作的部門名稱",
            min_length=1,
            max_length=50,
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(self.department_input)

        # 使用者 ID(用於指派)
        self.user_input = discord.ui.TextInput(
            label="使用者 ID(可選)",
            placeholder="用於角色指派的使用者 ID",
            min_length=0,
            max_length=20,
            style=discord.TextStyle.short,
            required=False,
        )
        self.add_item(self.user_input)

        # 附加參數
        self.params_input = discord.ui.TextInput(
            label="附加參數(可選)",
            placeholder="JSON 格式的附加參數,如描述等",
            style=discord.TextStyle.paragraph,
            required=False,
        )
        self.add_item(self.params_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理管理操作提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            action = self.action_input.value.strip().lower()
            department_name = self.department_input.value.strip()
            user_id_str = self.user_input.value.strip()
            params_str = self.params_input.value.strip()

            # 解析附加參數
            params = {}
            if params_str:
                try:
                    params = json.loads(params_str)
                except json.JSONDecodeError:
                    await interaction.followup.send(
                        "❌ 附加參數格式錯誤,請使用有效的 JSON 格式", ephemeral=True
                    )
                    return

            # 處理使用者 ID
            user_id = None
            if user_id_str:
                try:
                    user_id = int(user_id_str)
                except ValueError:
                    await interaction.followup.send(
                        "❌ 使用者 ID 格式錯誤", ephemeral=True
                    )
                    return

            # 執行對應操作
            result = await self._execute_action(
                action, department_name, user_id, params, interaction
            )

            if result:
                embed = discord.Embed(
                    title="✅ 操作成功",
                    description=f"成功執行 `{action}` 操作",
                    color=discord.Color.green(),
                )

                if isinstance(result, dict):
                    for key, value in result.items():
                        embed.add_field(name=key, value=str(value), inline=True)

                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"管理操作失敗: {e}")
            await interaction.followup.send(f"❌ 操作失敗: {e!s}", ephemeral=True)

    async def _execute_action(
        self,
        action: str,
        department_name: str,
        user_id: int | None,
        params: dict[str, Any],
        interaction: discord.Interaction,
    ) -> Any:
        """執行管理操作.

        Args:
            action: 操作類型
            department_name: 部門名稱
            user_id: 使用者 ID
            params: 附加參數
            interaction: Discord 互動

        Returns:
            操作結果
        """
        if action == "create":
            return await self._create_department(department_name, params, interaction)
        elif action == "update":
            return await self._update_department(department_name, params, interaction)
        elif action == "delete":
            return await self._delete_department(department_name, params, interaction)
        elif action == "assign":
            return await self._assign_role(department_name, user_id, interaction)
        else:
            raise ValueError(f"不支援的操作類型: {action}")

    async def _create_department(
        self, name: str, params: dict[str, Any], interaction: discord.Interaction
    ) -> dict[str, Any]:
        """創建部門."""
        description = params.get("description", "")
        parent_name = params.get("parent", "")
        auto_create_role = params.get("auto_create_role", True)

        # 查找上級部門
        parent_id = None
        if parent_name:
            departments = await self.service.get_departments_by_guild(self.guild_id)
            for dept in departments:
                if dept.name == parent_name:
                    parent_id = dept.id
                    break

            if not parent_id:
                raise ValueError(f"上級部門 '{parent_name}' 不存在")

        # 創建部門
        department = await self.service.create_department(
            guild_id=self.guild_id,
            name=name,
            description=description,
            parent_id=parent_id,
            actor_id=self.admin_id,
            auto_create_role=auto_create_role,
        )

        return {
            "部門 ID": str(department.id)[:8],
            "部門名稱": department.name,
            "角色 ID": department.role_id or "無",
        }

    async def _update_department(
        self, name: str, params: dict[str, Any], interaction: discord.Interaction
    ) -> dict[str, Any]:
        """更新部門."""
        # 查找部門
        departments = await self.service.get_departments_by_guild(self.guild_id)
        department = None
        for dept in departments:
            if dept.name == name:
                department = dept
                break

        if not department:
            raise ValueError(f"部門 '{name}' 不存在")

        # 更新部門(這裡需要實作 update_department 方法)
        # 暫時返回基本資訊
        return {"部門 ID": str(department.id)[:8], "狀態": "已更新(功能開發中)"}

    async def _delete_department(
        self, name: str, params: dict[str, Any], interaction: discord.Interaction
    ) -> dict[str, Any]:
        """刪除部門."""
        # 查找部門
        departments = await self.service.get_departments_by_guild(self.guild_id)
        department = None
        for dept in departments:
            if dept.name == name:
                department = dept
                break

        if not department:
            raise ValueError(f"部門 '{name}' 不存在")

        force = params.get("force", False)
        delete_role = params.get("delete_role", True)

        # 刪除部門
        success = await self.service.delete_department(
            department.id, actor_id=self.admin_id, force=force, delete_role=delete_role
        )

        return {"部門名稱": name, "刪除結果": "成功" if success else "失敗"}

    async def _assign_role(
        self,
        department_name: str,
        user_id: int | None,
        interaction: discord.Interaction,
    ) -> dict[str, Any]:
        """指派角色."""
        if not user_id:
            raise ValueError("需要提供使用者 ID")

        # 查找部門
        departments = await self.service.get_departments_by_guild(self.guild_id)
        department = None
        for dept in departments:
            if dept.name == department_name:
                department = dept
                break

        if not department:
            raise ValueError(f"部門 '{department_name}' 不存在")

        if not department.role_id:
            raise ValueError(f"部門 '{department_name}' 沒有關聯的 Discord 角色")

        # 獲取成員和角色
        guild = interaction.guild
        if not guild:
            raise ValueError("無法獲取伺服器資訊")

        member = guild.get_member(user_id)
        if not member:
            raise ValueError(f"找不到使用者 ID: {user_id}")

        role = guild.get_role(department.role_id)
        if not role:
            raise ValueError(f"找不到角色 ID: {department.role_id}")

        # 指派角色
        await member.add_roles(
            role, reason=f"管理員 {interaction.user} 透過政府面板指派"
        )

        return {
            "使用者": member.display_name,
            "部門": department_name,
            "角色": role.name,
            "狀態": "已指派",
        }
