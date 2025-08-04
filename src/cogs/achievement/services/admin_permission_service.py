"""成就系統管理員權限服務.

此模組負責處理成就系統管理面板的權限檢查:
- 整合現有的 PermissionSystem
- 提供管理員權限檢查裝飾器
- 處理權限檢查失敗的錯誤和用戶回饋
- 記錄權限檢查的審計日誌
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

import discord

from src.cogs.core.base_cog import StandardEmbedBuilder
from src.cogs.core.permission_system import (
    ActionType,
    PermissionCheck,
    PermissionSystem,
    UserRole,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")

class AdminPermissionService:
    """成就系統管理員權限服務.

    整合現有的 PermissionSystem,為成就系統管理面板提供:
    - 嚴格的管理員權限檢查
    - 統一的錯誤處理和用戶回饋
    - 完整的審計日誌記錄
    """

    def __init__(self, permission_system: PermissionSystem | None = None):
        """初始化管理員權限服務.

        Args:
            permission_system: 權限系統實例,如果未提供將創建新實例
        """
        self._permission_system = permission_system or PermissionSystem()
        self._audit_enabled = True

    async def check_admin_permission(
        self,
        user: discord.Member,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> PermissionCheck:
        """檢查用戶是否有管理員權限.

        Args:
            user: Discord 用戶成員物件
            action: 要執行的操作
            context: 額外的上下文資訊

        Returns:
            PermissionCheck: 權限檢查結果
        """
        try:
            # 構建檢查上下文
            check_context = {
                "user_id": user.id,
                "guild_id": user.guild.id if user.guild else None,
                "action": action,
                "timestamp": discord.utils.utcnow().isoformat(),
                **(context or {}),
            }

            # 執行權限檢查 - 要求 ADMIN 角色和 ADMIN 操作權限
            result = self._permission_system.check_permission(
                user_role=UserRole.ADMIN,  # 管理面板僅限管理員
                action_type=ActionType.ADMIN,
                resource="achievement_management",
                context=check_context,
            )

            # 增強審計日誌
            if result.audit_log:
                result.audit_log.update(
                    {
                        "service": "AdminPermissionService",
                        "discord_user": {
                            "id": user.id,
                            "name": user.display_name,
                            "discriminator": user.discriminator,
                        },
                        "guild_context": {
                            "id": user.guild.id if user.guild else None,
                            "name": user.guild.name if user.guild else None,
                        },
                    }
                )

            logger.debug(
                f"[權限檢查]用戶 {user.id} 對操作 '{action}' 的檢查結果: {result.allowed}"
            )

            return result

        except Exception as e:
            logger.error(f"[權限檢查]檢查用戶 {user.id} 權限時發生錯誤: {e}")
            return PermissionCheck(
                allowed=False,
                reason=f"權限檢查系統錯誤: {e!s}",
                audit_log={
                    "error": str(e),
                    "user_id": user.id,
                    "action": action,
                    "timestamp": discord.utils.utcnow().isoformat(),
                },
            )

    def create_admin_required_embed(
        self,
        required_role: UserRole = UserRole.ADMIN,
        action: str = "使用管理面板",
    ) -> discord.Embed:
        """創建權限不足的錯誤 Embed.

        Args:
            required_role: 需要的角色
            action: 嘗試執行的操作

        Returns:
            discord.Embed: 權限錯誤 Embed
        """
        return StandardEmbedBuilder.create_error_embed(
            "權限不足",
            f"❌ 您沒有權限執行此操作\n\n"
            f"**需要權限**: {required_role.value.title()}\n"
            f"**嘗試操作**: {action}\n\n"
            f"請聯繫伺服器管理員獲取相應權限.",
        )

    async def handle_permission_denied(
        self,
        interaction: discord.Interaction,
        result: PermissionCheck,
        action: str = "使用管理面板",
    ) -> None:
        """處理權限被拒絕的情況.

        Args:
            interaction: Discord 互動物件
            result: 權限檢查結果
            action: 嘗試執行的操作
        """
        try:
            # 創建錯誤 Embed
            embed = self.create_admin_required_embed(
                required_role=result.required_role or UserRole.ADMIN,
                action=action,
            )

            # 發送錯誤回應
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

            # 記錄權限拒絕事件
            logger.warning(
                f"[權限拒絕]用戶 {interaction.user.id} 嘗試 '{action}' 但權限不足: {result.reason}"
            )

        except Exception as e:
            logger.error(f"[權限處理]處理權限拒絕回應時發生錯誤: {e}")

    def require_admin_permission(
        self,
        action: str = "管理操作",
        context_builder: Callable[[discord.Interaction], dict[str, Any]] | None = None,
    ) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T | None]]]:
        """管理員權限檢查裝飾器.

        用於裝飾需要管理員權限的 Discord 指令或互動處理函數.

        Args:
            action: 操作描述
            context_builder: 可選的上下文構建函數

        Returns:
            裝飾器函數

        Example:
            @admin_service.require_admin_permission("成就管理")
            async def admin_command(self, interaction: discord.Interaction):
                # 只有管理員可以執行的代碼
                pass
        """

        def decorator(
            func: Callable[..., Awaitable[T]],
        ) -> Callable[..., Awaitable[T | None]]:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> T | None:
                # 從參數中提取 interaction
                interaction: discord.Interaction | None = None

                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        break

                if not interaction:
                    # 嘗試從 kwargs 中獲取
                    interaction = kwargs.get("interaction")

                if not interaction:
                    logger.error(
                        f"[權限裝飾器]無法從 {func.__name__} 的參數中找到 discord.Interaction"
                    )
                    return None

                # 檢查是否在伺服器中且用戶是成員
                if not interaction.guild or not isinstance(
                    interaction.user, discord.Member
                ):
                    embed = StandardEmbedBuilder.create_error_embed(
                        "使用限制",
                        "❌ 此功能只能在伺服器中使用,且需要完整的成員身份.",
                    )

                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(embed=embed, ephemeral=True)
                        else:
                            await interaction.response.send_message(
                                embed=embed, ephemeral=True
                            )
                    except Exception as e:
                        logger.error(f"[權限裝飾器]發送使用限制訊息失敗: {e}")

                    return None

                # 構建檢查上下文
                context = {}
                if context_builder:
                    try:
                        context = context_builder(interaction)
                    except Exception as e:
                        logger.warning(f"[權限裝飾器]上下文構建失敗: {e}")

                # 執行權限檢查
                result = await self.check_admin_permission(
                    user=interaction.user,
                    action=action,
                    context=context,
                )

                # 如果權限檢查失敗,處理拒絕情況
                if not result.allowed:
                    await self.handle_permission_denied(interaction, result, action)
                    return None

                # 權限檢查通過,執行原函數
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.error(
                        f"[權限裝飾器]執行被裝飾函數 {func.__name__} 時發生錯誤: {e}"
                    )

                    # 發送執行錯誤回應
                    embed = StandardEmbedBuilder.create_error_embed(
                        "執行錯誤", f"❌ 執行操作時發生錯誤\n\n錯誤詳情: {str(e)[:200]}"
                    )

                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(embed=embed, ephemeral=True)
                        else:
                            await interaction.response.send_message(
                                embed=embed, ephemeral=True
                            )
                    except Exception as send_error:
                        logger.error(
                            f"[權限裝飾器]發送執行錯誤訊息失敗: {send_error}"
                        )

                    return None

            return wrapper

        return decorator

    def get_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """獲取權限檢查審計日誌.

        Args:
            limit: 返回的日誌數量限制

        Returns:
            審計日誌列表
        """
        return self._permission_system.get_audit_logs(limit)

    def get_permission_stats(self) -> dict[str, Any]:
        """獲取權限檢查統計數據.

        Returns:
            權限檢查統計字典
        """
        base_stats = self._permission_system.get_permission_stats()

        # 添加管理員權限服務特定的統計
        base_stats.update(
            {
                "service": "AdminPermissionService",
                "audit_enabled": self._audit_enabled,
            }
        )

        return base_stats

    async def cleanup(self) -> None:
        """清理權限服務資源."""
        try:
            if hasattr(self._permission_system, "clear_audit_logs"):
                self._permission_system.clear_audit_logs()

            logger.info("[管理員權限服務]清理完成")
        except Exception as e:
            logger.error(f"[管理員權限服務]清理時發生錯誤: {e}")

class _AdminPermissionServiceSingleton:
    """管理員權限服務單例類."""

    _instance: AdminPermissionService | None = None

    @classmethod
    def get_instance(cls) -> AdminPermissionService:
        """取得管理員權限服務實例.

        Returns:
            AdminPermissionService: 管理員權限服務實例
        """
        if cls._instance is None:
            cls._instance = AdminPermissionService()
        return cls._instance


def get_admin_permission_service() -> AdminPermissionService:
    """獲取管理員權限服務的全域實例.

    Returns:
        AdminPermissionService: 管理員權限服務實例
    """
    return _AdminPermissionServiceSingleton.get_instance()

def require_achievement_admin(
    action: str = "成就管理操作",
    context_builder: Callable[[discord.Interaction], dict[str, Any]] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T | None]]]:
    """成就系統管理員權限檢查裝飾器的便捷函數.

    這是 get_admin_permission_service().require_admin_permission() 的簡化版本.

    Args:
        action: 操作描述
        context_builder: 可選的上下文構建函數

    Returns:
        裝飾器函數

    Example:
        @require_achievement_admin("查看成就統計")
        async def view_stats_command(self, interaction: discord.Interaction):
            # 管理員專用功能
            pass
    """
    service = get_admin_permission_service()
    return service.require_admin_permission(action, context_builder)
