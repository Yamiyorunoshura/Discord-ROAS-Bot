"""Government Repository for Discord ROAS Bot v2.0.

此模組提供政府系統的 Repository 實作,支援:
- 部門的完整 CRUD 操作
- 階層結構查詢和管理
- Discord 角色同步追蹤
- 部門成員管理
- 批量操作和回滾機制
- 查詢優化和快取策略
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import joinedload, selectinload

from src.core.database.models import Department, DepartmentAccount
from src.core.database.postgresql import BaseRepository

logger = logging.getLogger(__name__)


class GovernmentRepositoryError(Exception):
    """政府系統 Repository 錯誤基礎類別."""

    pass


class DepartmentNotFoundError(GovernmentRepositoryError):
    """部門不存在錯誤."""

    pass


class CircularReferenceError(GovernmentRepositoryError):
    """循環引用錯誤."""

    pass


class DuplicateDepartmentError(GovernmentRepositoryError):
    """重複部門名稱錯誤."""

    pass


class GovernmentRepository(BaseRepository):
    """政府系統 Repository 實作.

    提供完整的政府部門管理功能,包括階層結構、角色同步和成員管理.
    """

    async def create_department(
        self,
        guild_id: int,
        name: str,
        description: str | None = None,
        parent_id: uuid.UUID | None = None,
        role_id: int | None = None,
        permissions: dict[str, Any] | None = None,
        extra_data: dict[str, Any] | None = None,
        display_order: int = 0,
    ) -> Department:
        """創建新部門.

        Args:
            guild_id: Discord 伺服器 ID
            name: 部門名稱
            description: 部門描述
            parent_id: 上級部門 ID
            role_id: 對應的 Discord 角色 ID
            permissions: 權限設定
            extra_data: 額外資料
            display_order: 顯示順序

        Returns:
            創建的部門記錄

        Raises:
            DuplicateDepartmentError: 當部門名稱重複時
            CircularReferenceError: 當父部門會造成循環引用時
            Exception: 當資料庫操作失敗時
        """
        try:
            # 檢查名稱是否重複
            existing = await self._get_department_by_name(guild_id, name)
            if existing:
                raise DuplicateDepartmentError(f"部門名稱 '{name}' 已存在")

            # 檢查父部門是否存在且無循環引用
            if parent_id:
                parent = await self.get_department_by_id(parent_id)
                if not parent or parent.guild_id != guild_id:
                    raise ValueError(f"上級部門不存在: {parent_id}")

            # 創建部門
            department = Department(
                guild_id=guild_id,
                name=name,
                description=description,
                parent_id=parent_id,
                role_id=role_id,
                permissions=permissions or {},
                extra_data=extra_data or {},
                display_order=display_order,
                is_active=True,
            )

            self.session.add(department)
            await self.flush()
            await self.refresh(department)

            logger.info(
                f"部門創建成功: guild_id={guild_id}, name='{name}', "
                f"parent_id={parent_id}, role_id={role_id}"
            )

            return department

        except (DuplicateDepartmentError, ValueError):
            await self.rollback()
            raise
        except Exception as e:
            await self.rollback()
            logger.error(f"創建部門失敗: guild_id={guild_id}, name='{name}', error={e}")
            raise

    async def get_department_by_id(self, department_id: uuid.UUID) -> Department | None:
        """根據 ID 取得部門.

        Args:
            department_id: 部門 ID

        Returns:
            部門記錄,如不存在則返回 None
        """
        try:
            result = await self.session.execute(
                select(Department)
                .options(
                    selectinload(Department.children),
                    joinedload(Department.parent),
                    selectinload(Department.accounts),
                )
                .where(Department.id == department_id, Department.is_active)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"取得部門失敗: department_id={department_id}, error={e}")
            raise

    async def _get_department_by_name(
        self, guild_id: int, name: str
    ) -> Department | None:
        """根據名稱取得部門(內部方法)."""
        try:
            result = await self.session.execute(
                select(Department).where(
                    Department.guild_id == guild_id,
                    Department.name == name,
                    Department.is_active,
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(
                f"根據名稱取得部門失敗: guild_id={guild_id}, name='{name}', error={e}"
            )
            raise

    async def get_departments_by_guild(
        self, guild_id: int, include_inactive: bool = False
    ) -> Sequence[Department]:
        """取得伺服器的所有部門.

        Args:
            guild_id: Discord 伺服器 ID
            include_inactive: 是否包含非活躍部門

        Returns:
            部門列表,按 display_order 排序
        """
        try:
            query = select(Department).where(Department.guild_id == guild_id)

            if not include_inactive:
                query = query.where(Department.is_active)

            query = query.options(
                selectinload(Department.children),
                joinedload(Department.parent),
                selectinload(Department.accounts),
            ).order_by(Department.display_order, Department.name)

            result = await self.session.execute(query)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"取得伺服器部門失敗: guild_id={guild_id}, error={e}")
            raise

    async def get_root_departments(self, guild_id: int) -> Sequence[Department]:
        """取得根級部門(沒有上級部門的部門).

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            根級部門列表
        """
        try:
            result = await self.session.execute(
                select(Department)
                .where(
                    Department.guild_id == guild_id,
                    Department.parent_id.is_(None),
                    Department.is_active,
                )
                .options(
                    selectinload(Department.children),
                    selectinload(Department.accounts),
                )
                .order_by(Department.display_order, Department.name)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"取得根級部門失敗: guild_id={guild_id}, error={e}")
            raise

    async def get_department_hierarchy(
        self, guild_id: int, department_id: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        """取得部門階層結構.

        Args:
            guild_id: Discord 伺服器 ID
            department_id: 特定部門 ID,如為 None 則返回完整階層

        Returns:
            階層結構數據
        """
        try:
            if department_id:
                # 取得特定部門的階層
                root_dept = await self.get_department_by_id(department_id)
                if not root_dept or root_dept.guild_id != guild_id:
                    return []

                return [await self._build_department_tree(root_dept)]
            else:
                # 取得完整階層
                root_departments = await self.get_root_departments(guild_id)
                return [
                    await self._build_department_tree(dept) for dept in root_departments
                ]

        except Exception as e:
            logger.error(
                f"取得部門階層失敗: guild_id={guild_id}, "
                f"department_id={department_id}, error={e}"
            )
            raise

    async def _build_department_tree(self, department: Department) -> dict[str, Any]:
        """建構部門樹狀結構(遞歸方法)."""
        children = []
        for child in department.children:
            if child.is_active:
                children.append(await self._build_department_tree(child))

        return {
            "id": str(department.id),
            "name": department.name,
            "description": department.description,
            "role_id": department.role_id,
            "permissions": department.permissions,
            "display_order": department.display_order,
            "member_count": len([acc for acc in department.accounts if acc.is_active]),
            "children": children,
        }

    async def update_department(
        self,
        department_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        parent_id: uuid.UUID | None = None,
        role_id: int | None = None,
        permissions: dict[str, Any] | None = None,
        extra_data: dict[str, Any] | None = None,
        display_order: int | None = None,
    ) -> Department:
        """更新部門資訊.

        Args:
            department_id: 部門 ID
            name: 新名稱
            description: 新描述
            parent_id: 新上級部門 ID
            role_id: 新 Discord 角色 ID
            permissions: 新權限設定
            extra_data: 新額外資料
            display_order: 新顯示順序

        Returns:
            更新後的部門記錄

        Raises:
            DepartmentNotFoundError: 當部門不存在時
            DuplicateDepartmentError: 當新名稱重複時
            CircularReferenceError: 當新父部門會造成循環引用時
        """
        try:
            department = await self.get_department_by_id(department_id)
            if not department:
                raise DepartmentNotFoundError(f"部門不存在: {department_id}")

            if name and name != department.name:
                existing = await self._get_department_by_name(department.guild_id, name)
                if existing:
                    raise DuplicateDepartmentError(f"部門名稱 '{name}' 已存在")
                department.name = name

            if (
                parent_id is not None
                and parent_id != department.parent_id
                and parent_id
            ):
                if await self._would_create_cycle(department_id, parent_id):
                    raise CircularReferenceError("會造成循環引用")
                department.parent_id = parent_id

            # 更新其他欄位
            if description is not None:
                department.description = description
            if role_id is not None:
                department.role_id = role_id
            if permissions is not None:
                department.permissions = permissions
            if extra_data is not None:
                department.extra_data = extra_data
            if display_order is not None:
                department.display_order = display_order

            await self.flush()
            await self.refresh(department)

            logger.info(f"部門更新成功: department_id={department_id}")
            return department

        except (
            DepartmentNotFoundError,
            DuplicateDepartmentError,
            CircularReferenceError,
        ):
            await self.rollback()
            raise
        except Exception as e:
            await self.rollback()
            logger.error(f"更新部門失敗: department_id={department_id}, error={e}")
            raise

    async def _would_create_cycle(
        self, department_id: uuid.UUID, new_parent_id: uuid.UUID
    ) -> bool:
        """檢查是否會造成循環引用."""
        current_id = new_parent_id
        visited = set()

        while current_id:
            if current_id == department_id:
                return True
            if current_id in visited:
                break
            visited.add(current_id)

            parent = await self.get_department_by_id(current_id)
            current_id = parent.parent_id if parent else None

        return False

    async def delete_department(
        self, department_id: uuid.UUID, force: bool = False
    ) -> bool:
        """刪除部門(軟刪除).

        Args:
            department_id: 部門 ID
            force: 是否強制刪除(即使有子部門)

        Returns:
            是否成功刪除

        Raises:
            DepartmentNotFoundError: 當部門不存在時
            ValueError: 當部門有子部門且未強制刪除時
        """
        try:
            department = await self.get_department_by_id(department_id)
            if not department:
                raise DepartmentNotFoundError(f"部門不存在: {department_id}")

            # 檢查是否有子部門
            if not force and department.children:
                active_children = [
                    child for child in department.children if child.is_active
                ]
                if active_children:
                    raise ValueError("部門有子部門,無法刪除")

            if force:
                await self._recursive_soft_delete(department)
            else:
                department.is_active = False

            await self.flush()

            logger.info(f"部門刪除成功: department_id={department_id}, force={force}")
            return True

        except (DepartmentNotFoundError, ValueError):
            await self.rollback()
            raise
        except Exception as e:
            await self.rollback()
            logger.error(f"刪除部門失敗: department_id={department_id}, error={e}")
            raise

    async def _recursive_soft_delete(self, department: Department) -> None:
        """遞歸軟刪除部門及其子部門."""
        department.is_active = False

        for child in department.children:
            if child.is_active:
                await self._recursive_soft_delete(child)

    async def get_departments_by_role_id(
        self, guild_id: int, role_id: int
    ) -> Sequence[Department]:
        """根據 Discord 角色 ID 取得部門.

        Args:
            guild_id: Discord 伺服器 ID
            role_id: Discord 角色 ID

        Returns:
            關聯的部門列表
        """
        try:
            result = await self.session.execute(
                select(Department).where(
                    Department.guild_id == guild_id,
                    Department.role_id == role_id,
                    Department.is_active,
                )
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(
                f"根據角色 ID 取得部門失敗: guild_id={guild_id}, "
                f"role_id={role_id}, error={e}"
            )
            raise

    async def get_department_statistics(self, guild_id: int) -> dict[str, Any]:
        """取得部門統計資料.

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            統計資料字典
        """
        try:
            # 基本統計
            dept_result = await self.session.execute(
                select(
                    func.count(Department.id).label("total_departments"),
                    func.count(Department.role_id).label("departments_with_roles"),
                ).where(
                    Department.guild_id == guild_id,
                    Department.is_active,
                )
            )
            dept_stats = dept_result.first()

            # 成員統計
            member_result = await self.session.execute(
                select(func.count(DepartmentAccount.user_id)).where(
                    DepartmentAccount.department_id.in_(
                        select(Department.id).where(
                            Department.guild_id == guild_id,
                            Department.is_active,
                        )
                    ),
                    DepartmentAccount.is_active,
                )
            )
            total_members = member_result.scalar() or 0

            # 階層深度統計
            max_depth = await self._calculate_max_depth(guild_id)

            return {
                "guild_id": guild_id,
                "total_departments": dept_stats.total_departments or 0,
                "departments_with_roles": dept_stats.departments_with_roles or 0,
                "total_members": total_members,
                "max_hierarchy_depth": max_depth,
                "last_updated": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"取得部門統計失敗: guild_id={guild_id}, error={e}")
            raise

    async def _calculate_max_depth(self, guild_id: int) -> int:
        """計算部門階層的最大深度."""
        try:
            # 使用遞歸 CTE 計算深度
            result = await self.session.execute(
                text("""
                    WITH RECURSIVE dept_depth AS (
                        -- 根級部門(深度 1)
                        SELECT id, parent_id, 1 as depth
                        FROM department
                        WHERE guild_id = :guild_id
                        AND parent_id IS NULL
                        AND is_active = true

                        UNION ALL

                        -- 子部門(深度 = 父部門深度 + 1)
                        SELECT d.id, d.parent_id, dd.depth + 1
                        FROM department d
                        INNER JOIN dept_depth dd ON d.parent_id = dd.id
                        WHERE d.guild_id = :guild_id
                        AND d.is_active = true
                    )
                    SELECT COALESCE(MAX(depth), 0) as max_depth
                    FROM dept_depth
                """),
                {"guild_id": guild_id},
            )
            return result.scalar() or 0

        except Exception as e:
            logger.error(f"計算最大深度失敗: guild_id={guild_id}, error={e}")
            return 0

    async def bulk_update_display_order(
        self, department_orders: list[tuple[uuid.UUID, int]]
    ) -> int:
        """批量更新部門顯示順序.

        Args:
            department_orders: (部門ID, 新順序) 的列表

        Returns:
            更新的部門數量
        """
        try:
            updated_count = 0

            for department_id, new_order in department_orders:
                result = await self.session.execute(
                    update(Department)
                    .where(Department.id == department_id)
                    .values(display_order=new_order)
                )
                updated_count += result.rowcount

            await self.flush()

            logger.info(f"批量更新顯示順序成功: 更新了 {updated_count} 個部門")
            return updated_count

        except Exception as e:
            await self.rollback()
            logger.error(f"批量更新顯示順序失敗: {e}")
            raise


__all__ = [
    "CircularReferenceError",
    "DepartmentNotFoundError",
    "DuplicateDepartmentError",
    "GovernmentRepository",
    "GovernmentRepositoryError",
]
