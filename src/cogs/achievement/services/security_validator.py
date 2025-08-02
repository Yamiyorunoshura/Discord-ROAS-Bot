"""成就系統安全權限驗證器.

此模組提供成就系統的安全權限驗證功能，包含：
- 二次權限驗證
- 操作權限檢查
- 安全令牌管理
- 風險操作確認

確保危險操作有足夠的安全保護措施。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """權限等級枚舉."""
    BASIC = "basic"           # 基本權限
    ELEVATED = "elevated"     # 提升權限
    ADMIN = "admin"          # 管理員權限
    SUPER_ADMIN = "super_admin"  # 超級管理員權限


class OperationRisk(Enum):
    """操作風險等級."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthenticationMethod(Enum):
    """認證方法."""
    PASSWORD = "password"
    TOKEN = "token"
    BIOMETRIC = "biometric"
    TWO_FACTOR = "two_factor"


@dataclass
class SecurityToken:
    """安全令牌."""
    token_id: str = field(default_factory=lambda: str(uuid4()))
    token_value: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    user_id: int = 0
    operation_type: str = ""
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=15))
    used: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionGrant:
    """權限授予記錄."""
    grant_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: int = 0
    permission_level: PermissionLevel = PermissionLevel.BASIC
    granted_by: int = 0
    granted_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    revoked: bool = False
    revoked_at: datetime | None = None
    revoked_by: int | None = None
    scope: set[str] = field(default_factory=set)  # 權限範圍
    conditions: dict[str, Any] = field(default_factory=dict)  # 授權條件


@dataclass
class SecurityChallenge:
    """安全挑戰."""
    challenge_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: int = 0
    operation_type: str = ""
    challenge_type: AuthenticationMethod = AuthenticationMethod.PASSWORD
    challenge_data: str = ""  # 挑戰數據（加密）
    correct_response: str = ""  # 正確回應（雜湊）
    attempts: int = 0
    max_attempts: int = 3
    solved: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=10))
    risk_level: OperationRisk = OperationRisk.MEDIUM


@dataclass
class OperationApproval:
    """操作審批."""
    approval_id: str = field(default_factory=lambda: str(uuid4()))
    operation_id: str = ""
    requested_by: int = 0
    operation_type: str = ""
    operation_details: dict[str, Any] = field(default_factory=dict)
    risk_level: OperationRisk = OperationRisk.MEDIUM

    # 審批狀態
    status: str = "pending"  # pending, approved, rejected, expired
    approved_by: int | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None

    # 時間管理
    requested_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=24))

    # 審批配置
    required_approvers: int = 1
    current_approvers: set[int] = field(default_factory=set)
    approval_notes: list[str] = field(default_factory=list)


class SecurityValidator:
    """安全權限驗證器.

    提供多層安全驗證和權限管理功能。
    """

    def __init__(self, audit_logger=None):
        """初始化安全驗證器.

        Args:
            audit_logger: 審計日誌記錄器
        """
        self.audit_logger = audit_logger

        # 安全令牌存儲
        self._security_tokens: dict[str, SecurityToken] = {}

        # 權限授予記錄
        self._permission_grants: dict[int, list[PermissionGrant]] = {}

        # 安全挑戰記錄
        self._security_challenges: dict[str, SecurityChallenge] = {}

        # 操作審批記錄
        self._operation_approvals: dict[str, OperationApproval] = {}

        # 風險評估規則
        self._risk_rules = self._initialize_risk_rules()

        # 統計資料
        self._stats = {
            "tokens_generated": 0,
            "tokens_validated": 0,
            "challenges_created": 0,
            "challenges_solved": 0,
            "approvals_requested": 0,
            "approvals_granted": 0,
            "permission_checks": 0,
            "security_violations": 0,
        }

        logger.info("SecurityValidator 初始化完成")

    def _initialize_risk_rules(self) -> dict[str, dict[str, Any]]:
        """初始化風險評估規則.

        Returns:
            Dict[str, Dict[str, Any]]: 風險評估規則
        """
        return {
            # 批量操作
            "bulk_grant": {
                "risk_level": OperationRisk.HIGH,
                "required_permission": PermissionLevel.ADMIN,
                "requires_approval": True,
                "approval_count": 1,
                "challenge_type": AuthenticationMethod.PASSWORD,
                "description": "批量授予成就"
            },

            "bulk_revoke": {
                "risk_level": OperationRisk.HIGH,
                "required_permission": PermissionLevel.ADMIN,
                "requires_approval": True,
                "approval_count": 1,
                "challenge_type": AuthenticationMethod.PASSWORD,
                "description": "批量撤銷成就"
            },

            "bulk_reset": {
                "risk_level": OperationRisk.CRITICAL,
                "required_permission": PermissionLevel.SUPER_ADMIN,
                "requires_approval": True,
                "approval_count": 2,
                "challenge_type": AuthenticationMethod.TWO_FACTOR,
                "description": "批量重置用戶資料"
            },

            # 單一操作
            "user_data_reset": {
                "risk_level": OperationRisk.CRITICAL,
                "required_permission": PermissionLevel.ADMIN,
                "requires_approval": True,
                "approval_count": 1,
                "challenge_type": AuthenticationMethod.PASSWORD,
                "description": "重置用戶資料"
            },

            "achievement_revoke": {
                "risk_level": OperationRisk.MEDIUM,
                "required_permission": PermissionLevel.ELEVATED,
                "requires_approval": False,
                "challenge_type": AuthenticationMethod.TOKEN,
                "description": "撤銷用戶成就"
            },

            "progress_adjust": {
                "risk_level": OperationRisk.LOW,
                "required_permission": PermissionLevel.ELEVATED,
                "requires_approval": False,
                "challenge_type": AuthenticationMethod.TOKEN,
                "description": "調整成就進度"
            },

            "achievement_grant": {
                "risk_level": OperationRisk.LOW,
                "required_permission": PermissionLevel.BASIC,
                "requires_approval": False,
                "challenge_type": AuthenticationMethod.TOKEN,
                "description": "授予用戶成就"
            },
        }

    async def check_permission(
        self,
        user_id: int,
        operation_type: str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """檢查操作權限.

        Args:
            user_id: 用戶ID
            operation_type: 操作類型
            context: 操作上下文

        Returns:
            Dict[str, Any]: 權限檢查結果
        """
        self._stats["permission_checks"] += 1

        try:
            # 獲取操作風險規則
            risk_rule = self._risk_rules.get(operation_type, {})
            required_permission = risk_rule.get("required_permission", PermissionLevel.BASIC)

            # 檢查用戶權限
            user_permission = await self._get_user_permission(user_id)
            has_permission = self._compare_permissions(user_permission, required_permission)

            # 檢查是否需要審批
            requires_approval = risk_rule.get("requires_approval", False)
            if requires_approval:
                # 檢查是否有有效的審批
                approval = await self._check_existing_approval(user_id, operation_type, context)
                if not approval:
                    return {
                        "allowed": False,
                        "reason": "requires_approval",
                        "required_permission": required_permission.value,
                        "user_permission": user_permission.value,
                        "approval_required": True,
                        "approval_count": risk_rule.get("approval_count", 1)
                    }

            # 檢查是否需要安全挑戰
            challenge_type = risk_rule.get("challenge_type")
            if has_permission and challenge_type:
                # 檢查是否有有效的令牌
                token = await self._check_valid_token(user_id, operation_type)
                if not token:
                    return {
                        "allowed": False,
                        "reason": "requires_security_challenge",
                        "required_permission": required_permission.value,
                        "user_permission": user_permission.value,
                        "challenge_type": challenge_type.value,
                        "challenge_required": True
                    }

            result = {
                "allowed": has_permission,
                "reason": "insufficient_permission" if not has_permission else "allowed",
                "required_permission": required_permission.value,
                "user_permission": user_permission.value,
                "risk_level": risk_rule.get("risk_level", OperationRisk.LOW).value,
                "approval_required": requires_approval,
                "challenge_required": challenge_type is not None
            }

            # 記錄審計日誌
            if self.audit_logger:
                from .audit_logger import AuditContext, AuditEventType, AuditSeverity

                await self.audit_logger.log_event(
                    event_type=AuditEventType.PERMISSION_CHECK,
                    context=AuditContext(user_id=user_id, guild_id=context.get("guild_id", 0)),
                    operation_name=f"permission_check_{operation_type}",
                    severity=AuditSeverity.INFO,
                    metadata={
                        "operation_type": operation_type,
                        "permission_result": result,
                        "context": context
                    }
                )

            return result

        except Exception as e:
            logger.error(f"【安全驗證】權限檢查失敗 {user_id} - {operation_type}: {e}")
            self._stats["security_violations"] += 1
            return {
                "allowed": False,
                "reason": "check_failed",
                "error": str(e)
            }

    async def _get_user_permission(self, user_id: int) -> PermissionLevel:
        """獲取用戶權限等級.

        Args:
            user_id: 用戶ID

        Returns:
            PermissionLevel: 用戶權限等級
        """
        # 檢查權限授予記錄
        user_grants = self._permission_grants.get(user_id, [])
        active_grants = [
            grant for grant in user_grants
            if not grant.revoked and
            (grant.expires_at is None or grant.expires_at > datetime.utcnow())
        ]

        if not active_grants:
            return PermissionLevel.BASIC

        # 返回最高權限等級
        max_permission = PermissionLevel.BASIC
        for grant in active_grants:
            if self._compare_permissions(grant.permission_level, max_permission):
                max_permission = grant.permission_level

        return max_permission

    def _compare_permissions(self, user_permission: PermissionLevel, required_permission: PermissionLevel) -> bool:
        """比較權限等級.

        Args:
            user_permission: 用戶權限
            required_permission: 要求權限

        Returns:
            bool: 用戶權限是否足夠
        """
        permission_hierarchy = {
            PermissionLevel.BASIC: 1,
            PermissionLevel.ELEVATED: 2,
            PermissionLevel.ADMIN: 3,
            PermissionLevel.SUPER_ADMIN: 4
        }

        user_level = permission_hierarchy[user_permission]
        required_level = permission_hierarchy[required_permission]

        return user_level >= required_level

    async def generate_security_token(
        self,
        user_id: int,
        operation_type: str,
        expires_in_minutes: int = 15,
        **metadata
    ) -> SecurityToken:
        """生成安全令牌.

        Args:
            user_id: 用戶ID
            operation_type: 操作類型
            expires_in_minutes: 過期時間（分鐘）
            **metadata: 額外元數據

        Returns:
            SecurityToken: 安全令牌
        """
        token = SecurityToken(
            user_id=user_id,
            operation_type=operation_type,
            expires_at=datetime.utcnow() + timedelta(minutes=expires_in_minutes),
            metadata=metadata
        )

        self._security_tokens[token.token_value] = token
        self._stats["tokens_generated"] += 1

        logger.info(
            "【安全驗證】生成安全令牌",
            extra={
                "token_id": token.token_id,
                "user_id": user_id,
                "operation_type": operation_type,
                "expires_at": token.expires_at.isoformat()
            }
        )

        return token

    async def validate_security_token(
        self,
        token_value: str,
        user_id: int,
        operation_type: str
    ) -> dict[str, Any]:
        """驗證安全令牌.

        Args:
            token_value: 令牌值
            user_id: 用戶ID
            operation_type: 操作類型

        Returns:
            Dict[str, Any]: 驗證結果
        """
        self._stats["tokens_validated"] += 1

        token = self._security_tokens.get(token_value)
        if not token:
            return {
                "valid": False,
                "reason": "token_not_found"
            }

        # 檢查令牌是否已使用
        if token.used:
            return {
                "valid": False,
                "reason": "token_already_used"
            }

        # 檢查令牌是否過期
        if token.expires_at < datetime.utcnow():
            return {
                "valid": False,
                "reason": "token_expired"
            }

        # 檢查用戶匹配
        if token.user_id != user_id:
            return {
                "valid": False,
                "reason": "user_mismatch"
            }

        # 檢查操作類型匹配
        if token.operation_type != operation_type:
            return {
                "valid": False,
                "reason": "operation_mismatch"
            }

        # 標記令牌為已使用
        token.used = True

        logger.info(
            "【安全驗證】令牌驗證成功",
            extra={
                "token_id": token.token_id,
                "user_id": user_id,
                "operation_type": operation_type
            }
        )

        return {
            "valid": True,
            "token": token
        }

    async def _check_valid_token(self, user_id: int, operation_type: str) -> SecurityToken | None:
        """檢查是否有有效的令牌.

        Args:
            user_id: 用戶ID
            operation_type: 操作類型

        Returns:
            Optional[SecurityToken]: 有效的令牌，如果沒有則返回None
        """
        for token in self._security_tokens.values():
            if (token.user_id == user_id and
                token.operation_type == operation_type and
                not token.used and
                token.expires_at > datetime.utcnow()):
                return token

        return None

    async def create_security_challenge(
        self,
        user_id: int,
        operation_type: str,
        challenge_type: AuthenticationMethod = AuthenticationMethod.PASSWORD
    ) -> SecurityChallenge:
        """創建安全挑戰.

        Args:
            user_id: 用戶ID
            operation_type: 操作類型
            challenge_type: 挑戰類型

        Returns:
            SecurityChallenge: 安全挑戰
        """
        # 生成挑戰數據
        challenge_data = ""
        correct_response = ""

        if challenge_type == AuthenticationMethod.PASSWORD:
            # 密碼挑戰（這裡簡化，實際應該要求用戶輸入密碼）
            challenge_data = "請輸入您的管理員密碼以確認身份"
            # 實際實現中應該從安全存儲中獲取用戶密碼雜湊
            correct_response = "placeholder_hash"

        elif challenge_type == AuthenticationMethod.TOKEN:
            # 令牌挑戰
            challenge_code = secrets.token_hex(4).upper()
            challenge_data = f"請輸入確認碼: {challenge_code}"
            correct_response = hashlib.sha256(challenge_code.encode()).hexdigest()

        elif challenge_type == AuthenticationMethod.TWO_FACTOR:
            # 雙因子認證挑戰
            challenge_data = "請輸入您的雙因子認證碼"
            correct_response = "2fa_placeholder"

        challenge = SecurityChallenge(
            user_id=user_id,
            operation_type=operation_type,
            challenge_type=challenge_type,
            challenge_data=challenge_data,
            correct_response=correct_response,
            risk_level=self._risk_rules.get(operation_type, {}).get("risk_level", OperationRisk.MEDIUM)
        )

        self._security_challenges[challenge.challenge_id] = challenge
        self._stats["challenges_created"] += 1

        logger.info(
            "【安全驗證】創建安全挑戰",
            extra={
                "challenge_id": challenge.challenge_id,
                "user_id": user_id,
                "operation_type": operation_type,
                "challenge_type": challenge_type.value
            }
        )

        return challenge

    async def solve_security_challenge(
        self,
        challenge_id: str,
        response: str,
        user_id: int
    ) -> dict[str, Any]:
        """解決安全挑戰.

        Args:
            challenge_id: 挑戰ID
            response: 用戶回應
            user_id: 用戶ID

        Returns:
            Dict[str, Any]: 挑戰結果
        """
        challenge = self._security_challenges.get(challenge_id)
        if not challenge:
            return {
                "success": False,
                "reason": "challenge_not_found"
            }

        # 檢查用戶匹配
        if challenge.user_id != user_id:
            return {
                "success": False,
                "reason": "user_mismatch"
            }

        # 檢查挑戰是否過期
        if challenge.expires_at < datetime.utcnow():
            return {
                "success": False,
                "reason": "challenge_expired"
            }

        # 檢查嘗試次數
        if challenge.attempts >= challenge.max_attempts:
            return {
                "success": False,
                "reason": "max_attempts_exceeded"
            }

        # 增加嘗試次數
        challenge.attempts += 1

        # 驗證回應
        success = False
        if challenge.challenge_type == AuthenticationMethod.TOKEN:
            # 對於令牌挑戰，比較雜湊值
            response_hash = hashlib.sha256(response.encode()).hexdigest()
            success = response_hash == challenge.correct_response
        else:
            # 其他類型的挑戰驗證
            success = response == challenge.correct_response

        if success:
            challenge.solved = True
            self._stats["challenges_solved"] += 1

            # 生成安全令牌
            token = await self.generate_security_token(
                user_id=user_id,
                operation_type=challenge.operation_type,
                expires_in_minutes=15,
                challenge_id=challenge_id
            )

            logger.info(
                "【安全驗證】安全挑戰解決成功",
                extra={
                    "challenge_id": challenge_id,
                    "user_id": user_id,
                    "operation_type": challenge.operation_type,
                    "token_generated": token.token_id
                }
            )

            return {
                "success": True,
                "token": token.token_value,
                "expires_at": token.expires_at.isoformat()
            }
        else:
            remaining_attempts = challenge.max_attempts - challenge.attempts

            logger.warning(
                "【安全驗證】安全挑戰解決失敗",
                extra={
                    "challenge_id": challenge_id,
                    "user_id": user_id,
                    "attempts": challenge.attempts,
                    "remaining_attempts": remaining_attempts
                }
            )

            return {
                "success": False,
                "reason": "incorrect_response",
                "remaining_attempts": remaining_attempts
            }

    async def request_operation_approval(
        self,
        requested_by: int,
        operation_type: str,
        operation_details: dict[str, Any],
        context: dict[str, Any]
    ) -> OperationApproval:
        """請求操作審批.

        Args:
            requested_by: 請求者ID
            operation_type: 操作類型
            operation_details: 操作詳情
            context: 操作上下文

        Returns:
            OperationApproval: 操作審批記錄
        """
        risk_rule = self._risk_rules.get(operation_type, {})
        risk_level = risk_rule.get("risk_level", OperationRisk.MEDIUM)
        required_approvers = risk_rule.get("approval_count", 1)

        approval = OperationApproval(
            operation_id=context.get("operation_id", str(uuid4())),
            requested_by=requested_by,
            operation_type=operation_type,
            operation_details=operation_details,
            risk_level=risk_level,
            required_approvers=required_approvers
        )

        self._operation_approvals[approval.approval_id] = approval
        self._stats["approvals_requested"] += 1

        # 記錄審計日誌
        if self.audit_logger:
            from .audit_logger import AuditContext, AuditEventType, AuditSeverity

            await self.audit_logger.log_event(
                event_type=AuditEventType.PERMISSION_CHECK,
                context=AuditContext(user_id=requested_by, guild_id=context.get("guild_id", 0)),
                operation_name=f"approval_requested_{operation_type}",
                severity=AuditSeverity.WARNING,
                metadata={
                    "approval_id": approval.approval_id,
                    "operation_type": operation_type,
                    "operation_details": operation_details,
                    "risk_level": risk_level.value,
                    "required_approvers": required_approvers
                }
            )

        logger.info(
            "【安全驗證】操作審批請求",
            extra={
                "approval_id": approval.approval_id,
                "requested_by": requested_by,
                "operation_type": operation_type,
                "risk_level": risk_level.value,
                "required_approvers": required_approvers
            }
        )

        return approval

    async def approve_operation(
        self,
        approval_id: str,
        approver_id: int,
        notes: str | None = None
    ) -> dict[str, Any]:
        """審批操作.

        Args:
            approval_id: 審批ID
            approver_id: 審批者ID
            notes: 審批備註

        Returns:
            Dict[str, Any]: 審批結果
        """
        approval = self._operation_approvals.get(approval_id)
        if not approval:
            return {
                "success": False,
                "reason": "approval_not_found"
            }

        # 檢查審批是否過期
        if approval.expires_at < datetime.utcnow():
            approval.status = "expired"
            return {
                "success": False,
                "reason": "approval_expired"
            }

        # 檢查是否已經審批過
        if approval.status != "pending":
            return {
                "success": False,
                "reason": f"approval_already_{approval.status}"
            }

        # 檢查審批者是否有權限
        approver_permission = await self._get_user_permission(approver_id)
        if not self._compare_permissions(approver_permission, PermissionLevel.ADMIN):
            return {
                "success": False,
                "reason": "insufficient_permission_to_approve"
            }

        # 檢查是否是自己審批自己的請求
        if approver_id == approval.requested_by:
            return {
                "success": False,
                "reason": "cannot_approve_own_request"
            }

        # 添加審批者
        approval.current_approvers.add(approver_id)
        if notes:
            approval.approval_notes.append(f"{approver_id}: {notes}")

        # 檢查是否達到所需審批數量
        if len(approval.current_approvers) >= approval.required_approvers:
            approval.status = "approved"
            approval.approved_by = approver_id
            approval.approved_at = datetime.utcnow()
            self._stats["approvals_granted"] += 1

            # 生成審批令牌
            token = await self.generate_security_token(
                user_id=approval.requested_by,
                operation_type=approval.operation_type,
                expires_in_minutes=60,  # 審批令牌有效期更長
                approval_id=approval_id
            )

            logger.info(
                "【安全驗證】操作審批完成",
                extra={
                    "approval_id": approval_id,
                    "approved_by": approver_id,
                    "requested_by": approval.requested_by,
                    "operation_type": approval.operation_type,
                    "approvers_count": len(approval.current_approvers)
                }
            )

            return {
                "success": True,
                "status": "approved",
                "token": token.token_value,
                "expires_at": token.expires_at.isoformat()
            }
        else:
            remaining_approvals = approval.required_approvers - len(approval.current_approvers)

            logger.info(
                "【安全驗證】操作部分審批",
                extra={
                    "approval_id": approval_id,
                    "approved_by": approver_id,
                    "current_approvers": len(approval.current_approvers),
                    "remaining_approvals": remaining_approvals
                }
            )

            return {
                "success": True,
                "status": "partially_approved",
                "current_approvers": len(approval.current_approvers),
                "required_approvers": approval.required_approvers,
                "remaining_approvals": remaining_approvals
            }

    async def _check_existing_approval(
        self,
        user_id: int,
        operation_type: str,
        context: dict[str, Any]
    ) -> OperationApproval | None:
        """檢查是否有現有的有效審批.

        Args:
            user_id: 用戶ID
            operation_type: 操作類型
            context: 操作上下文

        Returns:
            Optional[OperationApproval]: 有效的審批記錄
        """
        for approval in self._operation_approvals.values():
            if (approval.requested_by == user_id and
                approval.operation_type == operation_type and
                approval.status == "approved" and
                approval.expires_at > datetime.utcnow()):
                return approval

        return None

    async def grant_permission(
        self,
        user_id: int,
        permission_level: PermissionLevel,
        granted_by: int,
        expires_in_hours: int | None = None,
        scope: set[str] | None = None,
        conditions: dict[str, Any] | None = None
    ) -> PermissionGrant:
        """授予權限.

        Args:
            user_id: 用戶ID
            permission_level: 權限等級
            granted_by: 授權者ID
            expires_in_hours: 過期時間（小時）
            scope: 權限範圍
            conditions: 授權條件

        Returns:
            PermissionGrant: 權限授予記錄
        """
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        grant = PermissionGrant(
            user_id=user_id,
            permission_level=permission_level,
            granted_by=granted_by,
            expires_at=expires_at,
            scope=scope or set(),
            conditions=conditions or {}
        )

        # 添加到用戶權限記錄
        if user_id not in self._permission_grants:
            self._permission_grants[user_id] = []
        self._permission_grants[user_id].append(grant)

        logger.info(
            "【安全驗證】權限授予",
            extra={
                "grant_id": grant.grant_id,
                "user_id": user_id,
                "permission_level": permission_level.value,
                "granted_by": granted_by,
                "expires_at": expires_at.isoformat() if expires_at else None
            }
        )

        return grant

    async def revoke_permission(
        self,
        grant_id: str,
        revoked_by: int,
        reason: str | None = None
    ) -> bool:
        """撤銷權限.

        Args:
            grant_id: 權限授予ID
            revoked_by: 撤銷者ID
            reason: 撤銷原因

        Returns:
            bool: 是否成功撤銷
        """
        for user_grants in self._permission_grants.values():
            for grant in user_grants:
                if grant.grant_id == grant_id and not grant.revoked:
                    grant.revoked = True
                    grant.revoked_at = datetime.utcnow()
                    grant.revoked_by = revoked_by

                    logger.info(
                        "【安全驗證】權限撤銷",
                        extra={
                            "grant_id": grant_id,
                            "user_id": grant.user_id,
                            "revoked_by": revoked_by,
                            "reason": reason
                        }
                    )

                    return True

        return False

    async def get_security_statistics(self) -> dict[str, Any]:
        """獲取安全統計資料.

        Returns:
            Dict[str, Any]: 統計資料
        """
        # 清理過期令牌和挑戰
        await self._cleanup_expired_items()

        return {
            **self._stats,
            "active_tokens": len([t for t in self._security_tokens.values() if not t.used and t.expires_at > datetime.utcnow()]),
            "pending_approvals": len([a for a in self._operation_approvals.values() if a.status == "pending"]),
            "active_challenges": len([c for c in self._security_challenges.values() if not c.solved and c.expires_at > datetime.utcnow()]),
            "total_permission_grants": sum(len(grants) for grants in self._permission_grants.values()),
            "active_permission_grants": sum(
                len([g for g in grants if not g.revoked and (g.expires_at is None or g.expires_at > datetime.utcnow())])
                for grants in self._permission_grants.values()
            )
        }

    async def _cleanup_expired_items(self) -> None:
        """清理過期的項目."""
        now = datetime.utcnow()

        # 清理過期令牌
        expired_tokens = [
            token_value for token_value, token in self._security_tokens.items()
            if token.expires_at < now
        ]
        for token_value in expired_tokens:
            del self._security_tokens[token_value]

        # 清理過期挑戰
        expired_challenges = [
            challenge_id for challenge_id, challenge in self._security_challenges.items()
            if challenge.expires_at < now
        ]
        for challenge_id in expired_challenges:
            del self._security_challenges[challenge_id]

        # 更新過期審批狀態
        for approval in self._operation_approvals.values():
            if approval.status == "pending" and approval.expires_at < now:
                approval.status = "expired"
