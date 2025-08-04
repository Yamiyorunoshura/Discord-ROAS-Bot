"""成就系統安全操作包裝器.

此模組提供安全操作包裝功能,為所有管理操作添加:
- 二次權限驗證
- 審計日誌記錄
- 操作歷史追蹤
- 安全挑戰確認

確保所有敏感操作都有完整的安全保護.
"""

from __future__ import annotations

import logging
from datetime import datetime
from functools import wraps
from typing import TYPE_CHECKING, Any

import discord

from ..services.audit_logger import (
    AuditContext,
    AuditEventType,
    AuditLogger,
    AuditSeverity,
)
from ..services.history_manager import HistoryAction, HistoryCategory, HistoryManager
from ..services.security_validator import AuthenticationMethod

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..services.security_validator import SecurityValidator

logger = logging.getLogger(__name__)

class SecurityOperationWrapper:
    """安全操作包裝器.

    為管理操作提供統一的安全驗證、審計記錄和歷史追蹤.
    """

    def __init__(
        self,
        audit_logger: AuditLogger | None = None,
        security_validator: SecurityValidator | None = None,
        history_manager: HistoryManager | None = None,
    ):
        """初始化安全操作包裝器.

        Args:
            audit_logger: 審計日誌記錄器
            security_validator: 安全驗證器
            history_manager: 歷史管理器
        """
        self.audit_logger = audit_logger
        self.security_validator = security_validator
        self.history_manager = history_manager

    def secure_operation(
        self,
        operation_type: str,
        audit_event_type: AuditEventType,
        history_action: HistoryAction,
        history_category: HistoryCategory,
        risk_level: str = "medium",
        requires_token: bool = True,
        requires_approval: bool = False,
    ):
        """安全操作裝飾器.

        Args:
            operation_type: 操作類型
            audit_event_type: 審計事件類型
            history_action: 歷史操作動作
            history_category: 歷史操作分類
            risk_level: 風險等級
            requires_token: 是否需要安全令牌
            requires_approval: 是否需要審批
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
                operation_start = datetime.utcnow()
                operation_id = f"{operation_type}_{operation_start.timestamp()}"

                # 創建審計上下文
                context = AuditContext(
                    user_id=interaction.user.id,
                    guild_id=interaction.guild_id or 0,
                    channel_id=interaction.channel_id,
                    interaction_id=str(interaction.id),
                )

                try:
                    # 1. 安全權限檢查
                    if self.security_validator:
                        permission_result = (
                            await self.security_validator.check_permission(
                                user_id=interaction.user.id,
                                operation_type=operation_type,
                                context={
                                    "guild_id": interaction.guild_id or 0,
                                    "operation_id": operation_id,
                                    "args": args,
                                    "kwargs": kwargs,
                                },
                            )
                        )

                        if not permission_result["allowed"]:
                            # 記錄權限被拒絕的事件
                            if self.audit_logger:
                                await self.audit_logger.log_event(
                                    event_type=AuditEventType.SECURITY_VIOLATION,
                                    context=context,
                                    operation_name=f"permission_denied_{operation_type}",
                                    severity=AuditSeverity.WARNING,
                                    success=False,
                                    error_message=permission_result.get(
                                        "reason", "權限不足"
                                    ),
                                    risk_level=risk_level,
                                    metadata={
                                        "permission_result": permission_result,
                                        "required_permission": permission_result.get(
                                            "required_permission"
                                        ),
                                        "user_permission": permission_result.get(
                                            "user_permission"
                                        ),
                                    },
                                )

                            await self._handle_permission_denied(
                                interaction, permission_result
                            )
                            return

                        # 檢查是否需要安全挑戰
                        if (
                            permission_result.get("challenge_required")
                            and requires_token
                        ):
                            challenge_result = await self._handle_security_challenge(
                                interaction, operation_type, permission_result
                            )
                            if not challenge_result:
                                return

                        # 檢查是否需要審批
                        if (
                            permission_result.get("approval_required")
                            and requires_approval
                        ):
                            approval_result = await self._handle_approval_request(
                                interaction, operation_type, args, kwargs
                            )
                            if not approval_result:
                                return

                    # 2. 記錄操作開始
                    if self.audit_logger:
                        await self.audit_logger.log_event(
                            event_type=audit_event_type,
                            context=context,
                            operation_name=f"{operation_type}_started",
                            severity=AuditSeverity.INFO,
                            metadata={
                                "operation_id": operation_id,
                                "risk_level": risk_level,
                                "args_count": len(args),
                                "kwargs_keys": list(kwargs.keys()),
                            },
                        )

                    # 3. 執行實際操作
                    result = await func(self, interaction, *args, **kwargs)

                    # 4. 記錄操作成功
                    operation_end = datetime.utcnow()
                    duration_ms = (
                        operation_end - operation_start
                    ).total_seconds() * 1000

                    # 審計日誌記錄
                    if self.audit_logger:
                        await self.audit_logger.log_event(
                            event_type=audit_event_type,
                            context=context,
                            operation_name=operation_type,
                            severity=AuditSeverity.INFO,
                            success=True,
                            duration_ms=duration_ms,
                            risk_level=risk_level,
                            metadata={
                                "operation_id": operation_id,
                                "result_type": type(result).__name__,
                                "execution_time": duration_ms,
                            },
                        )

                    # 操作歷史記錄
                    if self.history_manager:
                        # 從結果中提取歷史資料
                        history_data = self._extract_history_data(result, args, kwargs)

                        await self.history_manager.record_operation(
                            action=history_action,
                            category=history_category,
                            operation_name=operation_type,
                            executor_id=interaction.user.id,
                            target_type=history_data.get("target_type", ""),
                            target_id=history_data.get("target_id", ""),
                            target_name=history_data.get("target_name", ""),
                            old_values=history_data.get("old_values", {}),
                            new_values=history_data.get("new_values", {}),
                            guild_id=interaction.guild_id or 0,
                            channel_id=interaction.channel_id,
                            affected_users=history_data.get("affected_users", []),
                            affected_achievements=history_data.get(
                                "affected_achievements", []
                            ),
                            success=True,
                            duration_ms=duration_ms,
                            risk_level=risk_level,
                            metadata={
                                "operation_id": operation_id,
                                "interaction_id": str(interaction.id),
                            },
                        )

                    return result

                except Exception as e:
                    # 5. 記錄操作失敗
                    operation_end = datetime.utcnow()
                    duration_ms = (
                        operation_end - operation_start
                    ).total_seconds() * 1000

                    # 審計日誌記錄失敗
                    if self.audit_logger:
                        await self.audit_logger.log_event(
                            event_type=audit_event_type,
                            context=context,
                            operation_name=operation_type,
                            severity=AuditSeverity.ERROR,
                            success=False,
                            error_message=str(e),
                            duration_ms=duration_ms,
                            risk_level=risk_level,
                            metadata={
                                "operation_id": operation_id,
                                "error_type": type(e).__name__,
                                "execution_time": duration_ms,
                            },
                        )

                    # 操作歷史記錄失敗
                    if self.history_manager:
                        await self.history_manager.record_operation(
                            action=history_action,
                            category=history_category,
                            operation_name=operation_type,
                            executor_id=interaction.user.id,
                            guild_id=interaction.guild_id or 0,
                            channel_id=interaction.channel_id,
                            success=False,
                            error_message=str(e),
                            duration_ms=duration_ms,
                            risk_level=risk_level,
                            metadata={
                                "operation_id": operation_id,
                                "error_details": str(e),
                            },
                        )

                    logger.error(f"[安全操作]{operation_type} 執行失敗: {e}")
                    raise

            return wrapper

        return decorator

    async def _handle_permission_denied(
        self, interaction: discord.Interaction, permission_result: dict[str, Any]
    ) -> None:
        """處理權限被拒絕."""
        reason = permission_result.get("reason", "權限不足")
        required_permission = permission_result.get("required_permission", "Unknown")
        user_permission = permission_result.get("user_permission", "Unknown")

        embed = discord.Embed(
            title="🚫 權限不足",
            description="您沒有執行此操作的權限.",
            color=discord.Color.red(),
        )

        embed.add_field(name="錯誤原因", value=f"`{reason}`", inline=False)

        embed.add_field(
            name="權限要求",
            value=f"需要權限: `{required_permission}`\n您的權限: `{user_permission}`",
            inline=False,
        )

        if permission_result.get("challenge_required"):
            embed.add_field(
                name="解決方案",
                value="請先完成安全驗證挑戰,然後重試操作.",
                inline=False,
            )
        elif permission_result.get("approval_required"):
            embed.add_field(
                name="解決方案",
                value="此操作需要管理員審批,請聯繫管理員.",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_security_challenge(
        self,
        interaction: discord.Interaction,
        operation_type: str,
        permission_result: dict[str, Any],
    ) -> bool:
        """處理安全挑戰."""
        try:
            if not self.security_validator:
                return False

            challenge_type = permission_result.get("challenge_type", "token")

            # 創建安全挑戰
            challenge = await self.security_validator.create_security_challenge(
                user_id=interaction.user.id,
                operation_type=operation_type,
                challenge_type=AuthenticationMethod(challenge_type),
            )

            # 創建挑戰模態框
            modal = SecurityChallengeModal(challenge, self.security_validator)
            await interaction.response.send_modal(modal)

            return True

        except Exception as e:
            logger.error(f"[安全操作]處理安全挑戰失敗: {e}")
            return False

    async def _handle_approval_request(
        self,
        interaction: discord.Interaction,
        operation_type: str,
        args: tuple,
        kwargs: dict,
    ) -> bool:
        """處理審批請求."""
        try:
            if not self.security_validator:
                return False

            # 請求操作審批
            approval = await self.security_validator.request_operation_approval(
                requested_by=interaction.user.id,
                operation_type=operation_type,
                operation_details={
                    "args": [str(arg) for arg in args],
                    "kwargs": {k: str(v) for k, v in kwargs.items()},
                },
                context={
                    "guild_id": interaction.guild_id or 0,
                    "channel_id": interaction.channel_id,
                    "interaction_id": str(interaction.id),
                },
            )

            embed = discord.Embed(
                title="⏳ 等待審批",
                description="您的操作需要管理員審批.",
                color=discord.Color.orange(),
            )

            embed.add_field(
                name="審批資訊",
                value=(
                    f"操作類型: `{operation_type}`\n"
                    f"風險等級: `{approval.risk_level.value}`\n"
                    f"需要審批數: `{approval.required_approvers}`\n"
                    f"請求時間: {approval.requested_at.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                inline=False,
            )

            embed.add_field(
                name="審批ID", value=f"`{approval.approval_id}`", inline=False
            )

            embed.set_footer(text="請聯繫管理員進行審批,審批後您將收到通知.")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False  # 返回 False 表示操作暫停,等待審批

        except Exception as e:
            logger.error(f"[安全操作]處理審批請求失敗: {e}")
            return False

    def _extract_history_data(
        self, result: Any, args: tuple, kwargs: dict
    ) -> dict[str, Any]:
        """從操作結果中提取歷史資料."""
        history_data = {
            "target_type": "",
            "target_id": "",
            "target_name": "",
            "old_values": {},
            "new_values": {},
            "affected_users": [],
            "affected_achievements": [],
        }

        try:
            # 根據結果類型提取資料
            if isinstance(result, dict):
                history_data.update(
                    {
                        "target_type": result.get("target_type", ""),
                        "target_id": result.get("target_id", ""),
                        "target_name": result.get("target_name", ""),
                        "old_values": result.get("old_values", {}),
                        "new_values": result.get("new_values", {}),
                        "affected_users": result.get("affected_users", []),
                        "affected_achievements": result.get(
                            "affected_achievements", []
                        ),
                    }
                )

            # 從參數中提取資料
            if args and hasattr(args[0], "user") and hasattr(args[0].user, "id"):
                history_data["affected_users"].append(args[0].user.id)

            if kwargs:
                if "user_id" in kwargs:
                    history_data["affected_users"].append(kwargs["user_id"])
                if "achievement_id" in kwargs:
                    history_data["affected_achievements"].append(
                        kwargs["achievement_id"]
                    )
                if "target_id" in kwargs:
                    history_data["target_id"] = kwargs["target_id"]
                if "target_type" in kwargs:
                    history_data["target_type"] = kwargs["target_type"]

        except Exception as e:
            logger.warning(f"[安全操作]提取歷史資料失敗: {e}")

        return history_data

class SecurityChallengeModal(discord.ui.Modal):
    """安全挑戰模態框."""

    def __init__(self, challenge, security_validator: SecurityValidator):
        """初始化安全挑戰模態框.

        Args:
            challenge: 安全挑戰物件
            security_validator: 安全驗證器
        """
        super().__init__(title="🔐 安全驗證")
        self.challenge = challenge
        self.security_validator = security_validator

        # 挑戰說明
        self.add_item(
            discord.ui.TextInput(
                label="挑戰說明",
                default=challenge.challenge_data,
                required=False,
                style=discord.TextStyle.paragraph,
                max_length=500,
            )
        )

        # 回應輸入
        self.response_input = discord.ui.TextInput(
            label="請輸入驗證碼",
            placeholder="輸入上方顯示的驗證碼...",
            max_length=100,
            required=True,
        )
        self.add_item(self.response_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理挑戰回應."""
        try:
            response = self.response_input.value.strip()

            # 驗證挑戰回應
            result = await self.security_validator.solve_security_challenge(
                challenge_id=self.challenge.challenge_id,
                response=response,
                user_id=interaction.user.id,
            )

            if result["success"]:
                embed = discord.Embed(
                    title="✅ 安全驗證成功",
                    description="您已通過安全驗證,現在可以執行操作.",
                    color=discord.Color.green(),
                )

                embed.add_field(
                    name="安全令牌", value=f"`{result['token'][:20]}...`", inline=True
                )

                embed.add_field(
                    name="有效期至", value=result["expires_at"], inline=True
                )

                embed.set_footer(text="請在令牌有效期內重新執行您的操作.")

            else:
                embed = discord.Embed(
                    title="❌ 安全驗證失敗",
                    description=f"驗證失敗: {result.get('reason', 'Unknown error')}",
                    color=discord.Color.red(),
                )

                remaining = result.get("remaining_attempts", 0)
                if remaining > 0:
                    embed.add_field(
                        name="剩餘嘗試次數", value=f"{remaining} 次", inline=True
                    )
                else:
                    embed.add_field(
                        name="注意",
                        value="已超過最大嘗試次數,請稍後重試.",
                        inline=False,
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"[安全挑戰]處理挑戰回應失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理安全驗證時發生錯誤", ephemeral=True
            )

# 便利裝飾器函數
def secure_grant_achievement(wrapper: SecurityOperationWrapper):
    """授予成就的安全裝飾器."""
    return wrapper.secure_operation(
        operation_type="grant_achievement",
        audit_event_type=AuditEventType.ACHIEVEMENT_GRANTED,
        history_action=HistoryAction.GRANT,
        history_category=HistoryCategory.USER_ACHIEVEMENT,
        risk_level="low",
        requires_token=True,
        requires_approval=False,
    )

def secure_revoke_achievement(wrapper: SecurityOperationWrapper):
    """撤銷成就的安全裝飾器."""
    return wrapper.secure_operation(
        operation_type="revoke_achievement",
        audit_event_type=AuditEventType.ACHIEVEMENT_REVOKED,
        history_action=HistoryAction.REVOKE,
        history_category=HistoryCategory.USER_ACHIEVEMENT,
        risk_level="medium",
        requires_token=True,
        requires_approval=False,
    )

def secure_reset_user_data(wrapper: SecurityOperationWrapper):
    """重置用戶資料的安全裝飾器."""
    return wrapper.secure_operation(
        operation_type="reset_user_data",
        audit_event_type=AuditEventType.USER_DATA_RESET,
        history_action=HistoryAction.RESET,
        history_category=HistoryCategory.USER_DATA,
        risk_level="critical",
        requires_token=True,
        requires_approval=True,
    )

def secure_bulk_operation(wrapper: SecurityOperationWrapper):
    """批量操作的安全裝飾器."""
    return wrapper.secure_operation(
        operation_type="bulk_operation",
        audit_event_type=AuditEventType.BULK_GRANT,  # 會根據實際操作類型調整
        history_action=HistoryAction.UPDATE,
        history_category=HistoryCategory.USER_ACHIEVEMENT,
        risk_level="high",
        requires_token=True,
        requires_approval=True,
    )
