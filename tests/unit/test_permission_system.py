"""
🧪 PermissionSystem 測試
- 測試權限分層架構功能
- 驗證四級權限設計
- 測試權限檢查機制
- 驗證權限繼承和審計功能
"""

import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict, List

from cogs.core.permission_system import (
    PermissionSystem, UserRole, ActionType, Permission, PermissionCheck
)

class TestPermissionSystem:
    """PermissionSystem 測試類"""
    
    @pytest.fixture
    def permission_system(self):
        """建立測試用權限系統"""
        return PermissionSystem()
    
    def test_initialization(self, permission_system):
        """測試初始化"""
        assert len(permission_system.roles) == 4  # 4個預設角色
        assert UserRole.ADMIN in permission_system.roles
        assert UserRole.DEVELOPER in permission_system.roles
        assert UserRole.TESTER in permission_system.roles
        assert UserRole.USER in permission_system.roles
        assert permission_system.check_count == 0
        assert permission_system.denied_count == 0
        assert permission_system.audit_logs == []
    
    def test_check_permission_admin_all_actions(self, permission_system):
        """測試管理員所有操作權限"""
        # 管理員應該有所有權限
        for action_type in ActionType:
            result = permission_system.check_permission(UserRole.ADMIN, action_type)
            assert result.allowed is True
            assert result.reason == "權限檢查通過"
            assert result.audit_log is not None
    
    def test_check_permission_developer_actions(self, permission_system):
        """測試開發者權限"""
        # 開發者應該有讀取、寫入、測試、配置權限
        allowed_actions = [ActionType.READ, ActionType.WRITE, ActionType.TEST, ActionType.CONFIGURE]
        denied_actions = [ActionType.ADMIN, ActionType.DELETE]
        
        for action_type in allowed_actions:
            result = permission_system.check_permission(UserRole.DEVELOPER, action_type)
            assert result.allowed is True
        
        for action_type in denied_actions:
            result = permission_system.check_permission(UserRole.DEVELOPER, action_type)
            assert result.allowed is False
            assert "權限不足" in result.reason
    
    def test_check_permission_tester_actions(self, permission_system):
        """測試測試者權限"""
        # 測試者應該只有讀取和測試權限
        allowed_actions = [ActionType.READ, ActionType.TEST]
        denied_actions = [ActionType.WRITE, ActionType.ADMIN, ActionType.DELETE, ActionType.CONFIGURE]
        
        for action_type in allowed_actions:
            result = permission_system.check_permission(UserRole.TESTER, action_type)
            assert result.allowed is True
        
        for action_type in denied_actions:
            result = permission_system.check_permission(UserRole.TESTER, action_type)
            assert result.allowed is False
            assert "權限不足" in result.reason
    
    def test_check_permission_user_actions(self, permission_system):
        """測試普通用戶權限"""
        # 普通用戶應該只有讀取權限
        allowed_actions = [ActionType.READ]
        denied_actions = [ActionType.WRITE, ActionType.ADMIN, ActionType.TEST, ActionType.DELETE, ActionType.CONFIGURE]
        
        for action_type in allowed_actions:
            result = permission_system.check_permission(UserRole.USER, action_type)
            assert result.allowed is True
        
        for action_type in denied_actions:
            result = permission_system.check_permission(UserRole.USER, action_type)
            assert result.allowed is False
            assert "權限不足" in result.reason
    
    def test_check_permission_with_resource(self, permission_system):
        """測試帶資源的權限檢查"""
        result = permission_system.check_permission(
            UserRole.DEVELOPER, 
            ActionType.READ, 
            resource="activity_data"
        )
        
        assert result.allowed is True
        assert result.audit_log is not None
        assert result.audit_log["resource"] == "activity_data"
    
    def test_check_permission_with_context(self, permission_system):
        """測試帶上下文的權限檢查"""
        context = {"guild_id": "123456789", "user_id": "987654321"}
        
        result = permission_system.check_permission(
            UserRole.ADMIN, 
            ActionType.WRITE, 
            context=context
        )
        
        assert result.allowed is True
        assert result.audit_log is not None
        assert result.audit_log["context"] == context
    
    def test_get_effective_permissions(self, permission_system):
        """測試獲取有效權限"""
        # 管理員應該有所有權限
        admin_permissions = permission_system._get_effective_permissions(UserRole.ADMIN)
        assert len(admin_permissions) == 6  # 所有6種操作類型
        
        # 開發者應該有4種權限
        developer_permissions = permission_system._get_effective_permissions(UserRole.DEVELOPER)
        assert len(developer_permissions) == 4
        
        # 測試者應該有2種權限
        tester_permissions = permission_system._get_effective_permissions(UserRole.TESTER)
        assert len(tester_permissions) == 2
        
        # 普通用戶應該有1種權限
        user_permissions = permission_system._get_effective_permissions(UserRole.USER)
        assert len(user_permissions) == 1
    
    def test_get_required_role_for_action(self, permission_system):
        """測試獲取操作所需的最低角色"""
        # 讀取操作需要用戶角色
        required_role = permission_system._get_required_role_for_action(ActionType.READ)
        assert required_role == UserRole.USER
        
        # 測試操作需要測試者角色
        required_role = permission_system._get_required_role_for_action(ActionType.TEST)
        assert required_role == UserRole.TESTER
        
        # 寫入操作需要開發者角色
        required_role = permission_system._get_required_role_for_action(ActionType.WRITE)
        assert required_role == UserRole.DEVELOPER
        
        # 管理操作需要管理員角色
        required_role = permission_system._get_required_role_for_action(ActionType.ADMIN)
        assert required_role == UserRole.ADMIN
    
    def test_add_role(self, permission_system):
        """測試添加新角色"""
        result = permission_system.add_role(
            "moderator",
            [ActionType.READ, ActionType.WRITE, ActionType.DELETE],
            "版主 - 擁有管理權限",
            UserRole.USER
        )
        
        assert result is True
        assert UserRole("moderator") in permission_system.roles
        
        # 驗證新角色的權限
        moderator_permissions = permission_system._get_effective_permissions(UserRole("moderator"))
        assert ActionType.READ in moderator_permissions
        assert ActionType.WRITE in moderator_permissions
        assert ActionType.DELETE in moderator_permissions
    
    def test_remove_role(self, permission_system):
        """測試移除角色"""
        # 先添加一個角色
        permission_system.add_role("temp_role", [ActionType.READ], "臨時角色")
        
        # 移除角色
        result = permission_system.remove_role("temp_role")
        assert result is True
        assert UserRole("temp_role") not in permission_system.roles
    
    def test_remove_nonexistent_role(self, permission_system):
        """測試移除不存在的角色"""
        result = permission_system.remove_role("nonexistent_role")
        assert result is False
    
    def test_update_role_permissions(self, permission_system):
        """測試更新角色權限"""
        # 更新開發者角色權限
        new_permissions = [ActionType.READ, ActionType.WRITE]
        result = permission_system.update_role_permissions("developer", new_permissions)
        
        assert result is True
        
        # 驗證權限已更新
        developer_permissions = permission_system._get_effective_permissions(UserRole.DEVELOPER)
        assert len(developer_permissions) == 2
        assert ActionType.READ in developer_permissions
        assert ActionType.WRITE in developer_permissions
    
    def test_update_nonexistent_role_permissions(self, permission_system):
        """測試更新不存在角色的權限"""
        result = permission_system.update_role_permissions("nonexistent_role", [ActionType.READ])
        assert result is False
    
    def test_get_role_info(self, permission_system):
        """測試獲取角色信息"""
        role_info = permission_system.get_role_info("admin")
        
        assert role_info is not None
        assert "description" in role_info
        assert "permissions" in role_info
        assert "inherits_from" in role_info
        assert role_info["description"] == "系統管理員 - 擁有所有權限"
    
    def test_get_nonexistent_role_info(self, permission_system):
        """測試獲取不存在角色的信息"""
        role_info = permission_system.get_role_info("nonexistent_role")
        assert role_info is None
    
    def test_get_all_roles(self, permission_system):
        """測試獲取所有角色信息"""
        all_roles = permission_system.get_all_roles()
        
        assert len(all_roles) == 4  # 4個預設角色
        assert "admin" in all_roles
        assert "developer" in all_roles
        assert "tester" in all_roles
        assert "user" in all_roles
    
    def test_get_permission_stats(self, permission_system):
        """測試獲取權限檢查統計"""
        # 執行一些權限檢查
        permission_system.check_permission(UserRole.ADMIN, ActionType.READ)
        permission_system.check_permission(UserRole.USER, ActionType.ADMIN)  # 會被拒絕
        
        stats = permission_system.get_permission_stats()
        
        assert stats["total_checks"] == 2
        assert stats["allowed_checks"] == 1
        assert stats["denied_checks"] == 1
        assert stats["denial_rate"] == 50.0
        assert stats["roles_count"] == 4
    
    def test_get_audit_logs(self, permission_system):
        """測試獲取審計日誌"""
        # 執行一些權限檢查
        permission_system.check_permission(UserRole.ADMIN, ActionType.READ)
        permission_system.check_permission(UserRole.USER, ActionType.ADMIN)
        
        logs = permission_system.get_audit_logs()
        
        assert len(logs) == 2
        assert all("timestamp" in log for log in logs)
        assert all("user_role" in log for log in logs)
        assert all("action_type" in log for log in logs)
        assert all("allowed" in log for log in logs)
    
    def test_get_audit_logs_with_limit(self, permission_system):
        """測試帶限制的審計日誌獲取"""
        # 執行多個權限檢查
        for i in range(10):
            permission_system.check_permission(UserRole.ADMIN, ActionType.READ)
        
        logs = permission_system.get_audit_logs(limit=5)
        assert len(logs) == 5
    
    def test_clear_audit_logs(self, permission_system):
        """測試清除審計日誌"""
        # 執行一些權限檢查
        permission_system.check_permission(UserRole.ADMIN, ActionType.READ)
        
        # 清除日誌
        permission_system.clear_audit_logs()
        
        assert len(permission_system.audit_logs) == 0
    
    def test_export_permission_matrix(self, permission_system):
        """測試導出權限矩陣"""
        matrix = permission_system.export_permission_matrix()
        
        assert "admin" in matrix
        assert "developer" in matrix
        assert "tester" in matrix
        assert "user" in matrix
        
        # 驗證管理員權限
        admin_info = matrix["admin"]
        assert admin_info["description"] == "系統管理員 - 擁有所有權限"
        assert len(admin_info["permissions"]) == 6
        assert admin_info["inherits_from"] is None
    
    def test_validate_permission_hierarchy(self, permission_system):
        """測試驗證權限層次結構"""
        validation = permission_system.validate_permission_hierarchy()
        
        assert validation["valid"] is True
        assert len(validation["issues"]) == 0
        assert validation["roles_count"] == 4
    
    def test_validate_permission_hierarchy_with_circular_inheritance(self, permission_system):
        """測試循環繼承的權限層次結構"""
        # 創建循環繼承
        permission_system.roles[UserRole.DEVELOPER]["inherits_from"] = UserRole.TESTER
        permission_system.roles[UserRole.TESTER]["inherits_from"] = UserRole.DEVELOPER
        
        validation = permission_system.validate_permission_hierarchy()
        
        assert validation["valid"] is False
        assert len(validation["issues"]) > 0
        assert "循環繼承" in validation["issues"][0]

class TestUserRole:
    """UserRole 測試類"""
    
    def test_user_role_values(self):
        """測試用戶角色值"""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.DEVELOPER.value == "developer"
        assert UserRole.TESTER.value == "tester"
        assert UserRole.USER.value == "user"
    
    def test_user_role_creation(self):
        """測試用戶角色創建"""
        role = UserRole("admin")
        assert role == UserRole.ADMIN

class TestActionType:
    """ActionType 測試類"""
    
    def test_action_type_values(self):
        """測試操作類型值"""
        assert ActionType.READ.value == "read"
        assert ActionType.WRITE.value == "write"
        assert ActionType.ADMIN.value == "admin"
        assert ActionType.TEST.value == "test"
        assert ActionType.DELETE.value == "delete"
        assert ActionType.CONFIGURE.value == "configure"
    
    def test_action_type_creation(self):
        """測試操作類型創建"""
        action = ActionType("read")
        assert action == ActionType.READ

class TestPermission:
    """Permission 測試類"""
    
    def test_permission_creation(self):
        """測試權限創建"""
        permission = Permission(
            role=UserRole.ADMIN,
            action_type=ActionType.READ,
            resource="activity_data",
            conditions={"guild_id": "123456789"}
        )
        
        assert permission.role == UserRole.ADMIN
        assert permission.action_type == ActionType.READ
        assert permission.resource == "activity_data"
        assert permission.conditions == {"guild_id": "123456789"}

class TestPermissionCheck:
    """PermissionCheck 測試類"""
    
    def test_permission_check_creation(self):
        """測試權限檢查結果創建"""
        check = PermissionCheck(
            allowed=True,
            reason="權限檢查通過",
            required_role=UserRole.ADMIN,
            audit_log={"timestamp": "2024-01-01T12:00:00"}
        )
        
        assert check.allowed is True
        assert check.reason == "權限檢查通過"
        assert check.required_role == UserRole.ADMIN
        assert check.audit_log is not None