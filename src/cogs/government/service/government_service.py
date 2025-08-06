"""Government Service for Discord ROAS Bot v2.0.

此模組提供政府系統的業務邏輯服務,支援:
- 部門和角色的完整 CRUD 操作
- Discord 角色自動創建和同步
- 事件驅動的變更通知
- 權限驗證和安全檢查
- 事務性操作和回滾機制
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import discord

from src.cogs.core.event_bus import EventPriority, publish_event
from src.cogs.government.database import (
    CircularReferenceError,
    DepartmentNotFoundError,
    DuplicateDepartmentError,
    GovernmentRepository,
)
from src.core.database.postgresql import get_db_session

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from discord.ext import commands

    from src.core.database.models import Department

logger = logging.getLogger(__name__)


class GovernmentServiceError(Exception):
    """政府服務錯誤基礎類別."""

    pass


class DiscordPermissionError(GovernmentServiceError):
    """Discord 權限錯誤."""

    pass


class RoleSyncError(GovernmentServiceError):
    """角色同步錯誤."""

    pass


class FileSyncError(GovernmentServiceError):
    """檔案同步錯誤."""

    pass


class DepartmentChangedEvent:
    """部門變更事件模型."""

    def __init__(
        self,
        action: str,  # 'created', 'updated', 'deleted'
        department_id: str,
        guild_id: int,
        department_name: str,
        role_id: int | None = None,
        changes: dict[str, Any] | None = None,
        actor_id: int | None = None,
    ):
        self.action = action
        self.department_id = department_id
        self.guild_id = guild_id
        self.department_name = department_name
        self.role_id = role_id
        self.changes = changes or {}
        self.actor_id = actor_id
        self.timestamp = datetime.utcnow().isoformat()


class GovernmentService:
    """政府系統服務類別.

    提供完整の政府部門管理業務邏輯,包括 Discord 角色同步和事件發佈.
    """

    def __init__(self, bot: commands.Bot):
        """初始化政府服務.

        Args:
            bot: Discord Bot 實例
        """
        self.bot = bot
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 配置
        self.departments_file_path = Path("config/departments.json")
        self.role_name_prefix = "[部門]"
        self.auto_create_roles = True
        self.auto_sync_permissions = True

        # 同步鎖,防止並發操作衝突
        self._sync_lock = asyncio.Lock()

    async def create_department(
        self,
        guild_id: int,
        name: str,
        description: str | None = None,
        parent_id: uuid.UUID | None = None,
        permissions: dict[str, Any] | None = None,
        actor_id: int | None = None,
        auto_create_role: bool = True,
    ) -> Department:
        """創建新部門.

        Args:
            guild_id: Discord 伺服器 ID
            name: 部門名稱
            description: 部門描述
            parent_id: 上級部門 ID
            permissions: 權限設置
            actor_id: 執行者 ID
            auto_create_role: 是否自動創建 Discord 角色

        Returns:
            創建的部門實例
        """

        async with self._sync_lock:
            try:
                async with get_db_session() as session:
                    repo = GovernmentRepository(session)

                    # 驗證父部門
                    if parent_id:
                        parent_dept = await repo.get_department_by_id(parent_id)
                        if not parent_dept or parent_dept.guild_id != guild_id:
                            raise ValueError(
                                f"上級部門不存在或不屬於此伺服器: {parent_id}"
                            )

                    # 創建 Discord 角色(如果需要)
                    role_id = None
                    if auto_create_role and self.auto_create_roles:
                        role_id = await self._create_discord_role(
                            guild_id, name, permissions or {}
                        )

                    # 創建部門記錄
                    department = await repo.create_department(
                        guild_id=guild_id,
                        name=name,
                        description=description,
                        parent_id=parent_id,
                        role_id=role_id,
                        permissions=permissions or {},
                        extra_data={
                            "created_by": actor_id,
                            "auto_role_created": role_id is not None,
                        },
                    )

                    await repo.commit()

                    # 同步到檔案
                    await self._sync_to_file(guild_id)

                    # 發佈事件
                    await self._publish_department_changed_event(
                        DepartmentChangedEvent(
                            action="created",
                            department_id=str(department.id),
                            guild_id=guild_id,
                            department_name=name,
                            role_id=role_id,
                            actor_id=actor_id,
                        )
                    )

                    self.logger.info(
                        f"部門創建成功: guild_id={guild_id}, name='{name}', "
                        f"role_id={role_id}, actor_id={actor_id}"
                    )

                    return department

            except (DuplicateDepartmentError, ValueError):
                raise
            except Exception as e:
                self.logger.error(f"創建部門失敗: {e}")
                raise GovernmentServiceError(f"創建部門失敗: {e}") from e

    async def update_department(
        self,
        department_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        parent_id: uuid.UUID | None = None,
        permissions: dict[str, Any] | None = None,
        actor_id: int | None = None,
        sync_role: bool = True,
    ) -> Department:
        """更新部門資訊.

        Args:
            department_id: 部門 ID
            name: 新名稱
            description: 新描述
            parent_id: 新上級部門 ID
            permissions: 新權限設定
            actor_id: 執行者 ID
            sync_role: 是否同步 Discord 角色

        Returns:
            更新後的部門記錄

        Raises:
            DepartmentNotFoundError: 當部門不存在時
            CircularReferenceError: 當父部門會造成循環引用時
        """
        async with self._sync_lock:
            try:
                async with get_db_session() as session:
                    repo = GovernmentRepository(session)

                    # 取得原始部門資料
                    original_dept = await repo.get_department_by_id(department_id)
                    if not original_dept:
                        raise DepartmentNotFoundError(f"部門不存在: {department_id}")

                    # 記錄變更
                    changes = {}
                    if name and name != original_dept.name:
                        changes["name"] = {"old": original_dept.name, "new": name}
                    if (
                        description is not None
                        and description != original_dept.description
                    ):
                        changes["description"] = {
                            "old": original_dept.description,
                            "new": description,
                        }
                    if parent_id is not None and parent_id != original_dept.parent_id:
                        changes["parent_id"] = {
                            "old": str(original_dept.parent_id)
                            if original_dept.parent_id
                            else None,
                            "new": str(parent_id) if parent_id else None,
                        }
                    if (
                        permissions is not None
                        and permissions != original_dept.permissions
                    ):
                        changes["permissions"] = {
                            "old": original_dept.permissions,
                            "new": permissions,
                        }

                    # 更新部門
                    updated_dept = await repo.update_department(
                        department_id=department_id,
                        name=name,
                        description=description,
                        parent_id=parent_id,
                        permissions=permissions,
                        extra_data={
                            **original_dept.extra_data,
                            "last_modified_by": actor_id,
                            "last_modified_at": datetime.utcnow().isoformat(),
                        },
                    )

                    # 同步 Discord 角色(如果需要)
                    if sync_role and updated_dept.role_id and (name or permissions):
                        await self._update_discord_role(
                            original_dept.guild_id,
                            updated_dept.role_id,
                            name or original_dept.name,
                            permissions or original_dept.permissions,
                        )

                    await repo.commit()

                    # 同步到檔案
                    await self._sync_to_file(original_dept.guild_id)

                    # 發佈事件
                    if changes:
                        await self._publish_department_changed_event(
                            DepartmentChangedEvent(
                                action="updated",
                                department_id=str(department_id),
                                guild_id=original_dept.guild_id,
                                department_name=updated_dept.name,
                                role_id=updated_dept.role_id,
                                changes=changes,
                                actor_id=actor_id,
                            )
                        )

                    self.logger.info(
                        f"部門更新成功: department_id={department_id}, "
                        f"changes={changes}, actor_id={actor_id}"
                    )

                    return updated_dept

            except (DepartmentNotFoundError, CircularReferenceError):
                raise
            except Exception as e:
                self.logger.error(f"更新部門失敗: {e}")
                raise GovernmentServiceError(f"更新部門失敗: {e}") from e

    async def delete_department(
        self,
        department_id: uuid.UUID,
        actor_id: int | None = None,
        force: bool = False,
        delete_role: bool = True,
    ) -> bool:
        """刪除部門.

        Args:
            department_id: 部門 ID
            actor_id: 執行者 ID
            force: 是否強制刪除(即使有子部門)
            delete_role: 是否同時刪除 Discord 角色

        Returns:
            是否成功刪除

        Raises:
            DepartmentNotFoundError: 當部門不存在時
            ValueError: 當部門有子部門且未強制刪除時
        """
        async with self._sync_lock:
            try:
                async with get_db_session() as session:
                    repo = GovernmentRepository(session)

                    # 取得部門資料
                    department = await repo.get_department_by_id(department_id)
                    if not department:
                        raise DepartmentNotFoundError(f"部門不存在: {department_id}")

                    guild_id = department.guild_id
                    dept_name = department.name
                    role_id = department.role_id

                    # 刪除部門
                    success = await repo.delete_department(department_id, force)

                    if success:
                        # 刪除 Discord 角色(如果需要)
                        if delete_role and role_id:
                            await self._delete_discord_role(guild_id, role_id)

                        await repo.commit()

                        # 同步到檔案
                        await self._sync_to_file(guild_id)

                        # 發佈事件
                        await self._publish_department_changed_event(
                            DepartmentChangedEvent(
                                action="deleted",
                                department_id=str(department_id),
                                guild_id=guild_id,
                                department_name=dept_name,
                                role_id=role_id,
                                actor_id=actor_id,
                            )
                        )

                        self.logger.info(
                            f"部門刪除成功: department_id={department_id}, "
                            f"force={force}, actor_id={actor_id}"
                        )

                    return success

            except (DepartmentNotFoundError, ValueError):
                raise
            except Exception as e:
                self.logger.error(f"刪除部門失敗: {e}")
                raise GovernmentServiceError(f"刪除部門失敗: {e}") from e

    async def get_department_by_id(self, department_id: uuid.UUID) -> Department | None:
        """根據 ID 取得部門."""
        try:
            async with get_db_session() as session:
                repo = GovernmentRepository(session)
                return await repo.get_department_by_id(department_id)
        except Exception as e:
            self.logger.error(f"取得部門失敗: {e}")
            raise GovernmentServiceError(f"取得部門失敗: {e}") from e

    async def get_departments_by_guild(
        self, guild_id: int, include_inactive: bool = False
    ) -> Sequence[Department]:
        """取得伺服器的所有部門."""
        try:
            async with get_db_session() as session:
                repo = GovernmentRepository(session)
                return await repo.get_departments_by_guild(guild_id, include_inactive)
        except Exception as e:
            self.logger.error(f"取得伺服器部門失敗: {e}")
            raise GovernmentServiceError(f"取得伺服器部門失敗: {e}") from e

    async def get_department_hierarchy(
        self, guild_id: int, department_id: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        """取得部門階層結構."""
        try:
            async with get_db_session() as session:
                repo = GovernmentRepository(session)
                return await repo.get_department_hierarchy(guild_id, department_id)
        except Exception as e:
            self.logger.error(f"取得部門階層失敗: {e}")
            raise GovernmentServiceError(f"取得部門階層失敗: {e}") from e

    async def sync_roles_for_guild(self, guild_id: int) -> dict[str, Any]:
        """同步伺服器的所有部門角色.

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            同步結果統計
        """
        async with self._sync_lock:
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    raise ValueError(f"伺服器不存在: {guild_id}")

                departments = await self.get_departments_by_guild(guild_id)

                results = {
                    "total_departments": len(departments),
                    "roles_created": 0,
                    "roles_updated": 0,
                    "roles_deleted": 0,
                    "errors": [],
                }

                for dept in departments:
                    try:
                        if dept.role_id:
                            # 檢查角色是否存在
                            role = guild.get_role(dept.role_id)
                            if role:
                                # 更新角色
                                expected_name = f"{self.role_name_prefix} {dept.name}"
                                if role.name != expected_name:
                                    await role.edit(name=expected_name)
                                    results["roles_updated"] += 1
                            else:
                                # 角色已被刪除,清除記錄
                                await self._clear_department_role(dept.id)
                        else:
                            # 創建新角色
                            role_id = await self._create_discord_role(
                                guild_id, dept.name, dept.permissions
                            )
                            await self._update_department_role(dept.id, role_id)
                            results["roles_created"] += 1

                    except Exception as e:
                        error_msg = f"部門 {dept.name} 角色同步失敗: {e}"
                        results["errors"].append(error_msg)
                        self.logger.warning(error_msg)

                self.logger.info(f"伺服器角色同步完成: {guild_id}, 結果: {results}")
                return results

            except Exception as e:
                self.logger.error(f"伺服器角色同步失敗: {e}")
                raise RoleSyncError(f"伺服器角色同步失敗: {e}") from e

    async def _create_discord_role(
        self, guild_id: int, dept_name: str, permissions: dict[str, Any]
    ) -> int:
        """創建 Discord 角色."""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise DiscordPermissionError(f"無法存取伺服器: {guild_id}")

            # 檢查 Bot 權限
            if not guild.me.guild_permissions.manage_roles:
                raise DiscordPermissionError("Bot 沒有管理角色權限")

            role_name = f"{self.role_name_prefix} {dept_name}"

            # 轉換權限
            discord_permissions = await self._convert_permissions(permissions)

            role = await guild.create_role(
                name=role_name,
                permissions=discord_permissions,
                mentionable=True,
                reason=f"政府系統自動創建部門角色: {dept_name}",
            )

            self.logger.info(f"Discord 角色創建成功: {role.name} (ID: {role.id})")
            return role.id

        except discord.Forbidden:
            raise DiscordPermissionError("Bot 權限不足,無法創建角色") from None
        except Exception as e:
            raise RoleSyncError(f"創建 Discord 角色失敗: {e}") from e

    async def _update_discord_role(
        self, guild_id: int, role_id: int, dept_name: str, permissions: dict[str, Any]
    ) -> None:
        """更新 Discord 角色."""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return

            role = guild.get_role(role_id)
            if not role:
                return

            role_name = f"{self.role_name_prefix} {dept_name}"
            discord_permissions = await self._convert_permissions(permissions)

            await role.edit(
                name=role_name,
                permissions=discord_permissions,
                reason=f"政府系統同步部門角色: {dept_name}",
            )

            self.logger.info(f"Discord 角色更新成功: {role.name}")

        except discord.Forbidden:
            self.logger.warning(f"權限不足,無法更新角色: {role_id}")
        except Exception as e:
            self.logger.error(f"更新 Discord 角色失敗: {e}")

    async def _delete_discord_role(self, guild_id: int, role_id: int) -> None:
        """刪除 Discord 角色."""
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return

            role = guild.get_role(role_id)
            if not role:
                return

            await role.delete(reason="政府系統刪除部門角色")
            self.logger.info(f"Discord 角色刪除成功: {role.name}")

        except discord.Forbidden:
            self.logger.warning(f"權限不足,無法刪除角色: {role_id}")
        except Exception as e:
            self.logger.error(f"刪除 Discord 角色失敗: {e}")

    async def _convert_permissions(
        self, permissions: dict[str, Any]
    ) -> discord.Permissions:
        """轉換權限設定為 Discord 權限."""
        # 基礎權限
        perms = discord.Permissions.none()

        # 根據政府系統權限映射 Discord 權限
        permission_mapping = {
            "manage_currency": ["manage_messages", "send_messages"],
            "view_economy": ["read_message_history"],
            "manage_departments": ["manage_roles", "manage_channels"],
            "manage_members": ["kick_members", "ban_members"],
            "create_reports": ["attach_files", "embed_links"],
            "view_reports": ["read_message_history"],
            "view_activity": ["read_message_history"],
        }

        for perm, enabled in permissions.items():
            if enabled and perm in permission_mapping:
                for discord_perm in permission_mapping[perm]:
                    if hasattr(perms, discord_perm):
                        setattr(perms, discord_perm, True)

        # 所有部門都有基本權限
        perms.send_messages = True
        perms.read_messages = True
        perms.read_message_history = True

        return perms

    async def _update_department_role(
        self, department_id: uuid.UUID, role_id: int
    ) -> None:
        """更新部門的角色 ID."""
        try:
            async with get_db_session() as session:
                repo = GovernmentRepository(session)
                await repo.update_department(department_id, role_id=role_id)
                await repo.commit()
        except Exception as e:
            self.logger.error(f"更新部門角色 ID 失敗: {e}")

    async def _clear_department_role(self, department_id: uuid.UUID) -> None:
        """清除部門的角色 ID."""
        try:
            async with get_db_session() as session:
                repo = GovernmentRepository(session)
                await repo.update_department(department_id, role_id=None)
                await repo.commit()
        except Exception as e:
            self.logger.error(f"清除部門角色 ID 失敗: {e}")

    async def _sync_to_file(self, guild_id: int) -> None:
        """同步部門資料到檔案."""
        try:
            departments = await self.get_departments_by_guild(guild_id)

            file_data = {
                "guild_id": guild_id,
                "last_sync": datetime.utcnow().isoformat(),
                "departments": [],
            }

            for dept in departments:
                dept_data = {
                    "id": str(dept.id),
                    "name": dept.name,
                    "description": dept.description,
                    "parent_id": str(dept.parent_id) if dept.parent_id else None,
                    "role_id": dept.role_id,
                    "permissions": dept.permissions,
                    "display_order": dept.display_order,
                    "is_active": dept.is_active,
                }
                file_data["departments"].append(dept_data)

            # 確保目錄存在
            self.departments_file_path.parent.mkdir(parents=True, exist_ok=True)

            # 寫入檔案
            self.departments_file_path.write_text(
                json.dumps(file_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            self.logger.debug(f"部門資料同步到檔案完成: {guild_id}")

        except Exception as e:
            self.logger.error(f"同步到檔案失敗: {e}")
            raise FileSyncError(f"同步到檔案失敗: {e}") from e

    async def _publish_department_changed_event(
        self, event_data: DepartmentChangedEvent
    ) -> None:
        """發佈部門變更事件."""
        try:
            await publish_event(
                event_type="DepartmentChangedEvent",
                data={
                    "action": event_data.action,
                    "department_id": event_data.department_id,
                    "guild_id": event_data.guild_id,
                    "department_name": event_data.department_name,
                    "role_id": event_data.role_id,
                    "changes": event_data.changes,
                    "actor_id": event_data.actor_id,
                    "timestamp": event_data.timestamp,
                },
                source="government_service",
                priority=EventPriority.HIGH,
            )

            self.logger.debug(
                f"部門變更事件已發佈: {event_data.action} - {event_data.department_name}"
            )

        except Exception as e:
            self.logger.warning(f"發佈部門變更事件失敗: {e}")

    async def get_department_statistics(self, guild_id: int) -> dict[str, Any]:
        """取得部門統計資料."""
        try:
            async with get_db_session() as session:
                repo = GovernmentRepository(session)
                return await repo.get_department_statistics(guild_id)
        except Exception as e:
            self.logger.error(f"取得部門統計失敗: {e}")
            raise GovernmentServiceError(f"取得部門統計失敗: {e}") from e

    async def bulk_update_display_order(
        self, department_orders: list[tuple[uuid.UUID, int]]
    ) -> int:
        """批量更新部門顯示順序."""
        try:
            async with get_db_session() as session:
                repo = GovernmentRepository(session)
                updated_count = await repo.bulk_update_display_order(department_orders)
                await repo.commit()
                return updated_count
        except Exception as e:
            self.logger.error(f"批量更新顯示順序失敗: {e}")
            raise GovernmentServiceError(f"批量更新顯示順序失敗: {e}") from e


__all__ = [
    "DepartmentChangedEvent",
    "DiscordPermissionError",
    "FileSyncError",
    "GovernmentService",
    "GovernmentServiceError",
    "RoleSyncError",
]
