"""
🎯 PermissionSystem - 權限分層架構
- 實現系統管理員、開發者、測試者、普通用戶四級權限設計
- 提供不同操作類型的權限檢查機制
- 支援權限繼承和委派機制
- 實現權限審計和日誌記錄
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("permission_system")

class UserRole(Enum):
    """用戶角色枚舉"""
    ADMIN = "admin"           # 系統管理員
    DEVELOPER = "developer"   # 開發者
    TESTER = "tester"         # 測試者
    USER = "user"             # 普通用戶

class ActionType(Enum):
    """操作類型枚舉"""
    READ = "read"             # 讀取操作
    WRITE = "write"           # 寫入操作
    ADMIN = "admin"           # 管理操作
    TEST = "test"             # 測試操作
    DELETE = "delete"         # 刪除操作
    CONFIGURE = "configure"   # 配置操作

@dataclass
class Permission:
    """權限數據結構"""
    role: UserRole
    action_type: ActionType
    resource: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None

@dataclass
class PermissionCheck:
    """權限檢查結果"""
    allowed: bool
    reason: str = ""
    required_role: Optional[UserRole] = None
    audit_log: Optional[Dict[str, Any]] = None

class PermissionSystem:
    """
    權限分層架構系統
    - 實現四級權限設計
    - 提供權限檢查機制
    - 支援權限繼承和委派
    """
    
    def __init__(self):
        """初始化權限系統"""
        self.roles = {
            UserRole.ADMIN: {
                "permissions": [ActionType.READ, ActionType.WRITE, ActionType.ADMIN, ActionType.TEST, ActionType.DELETE, ActionType.CONFIGURE],
                "description": "系統管理員 - 擁有所有權限",
                "inherits_from": None
            },
            UserRole.DEVELOPER: {
                "permissions": [ActionType.READ, ActionType.WRITE, ActionType.TEST, ActionType.CONFIGURE],
                "description": "開發者 - 擁有開發和測試權限",
                "inherits_from": UserRole.USER
            },
            UserRole.TESTER: {
                "permissions": [ActionType.READ, ActionType.TEST],
                "description": "測試者 - 擁有讀取和測試權限",
                "inherits_from": UserRole.USER
            },
            UserRole.USER: {
                "permissions": [ActionType.READ],
                "description": "普通用戶 - 只有讀取權限",
                "inherits_from": None
            }
        }
        
        # 權限檢查統計
        self.check_count = 0
        self.denied_count = 0
        self.audit_logs = []
        
        logger.info("✅ PermissionSystem 初始化成功")
    
    def check_permission(self, user_role: UserRole, action_type: ActionType, resource: str = None, context: Dict[str, Any] = None) -> PermissionCheck:
        """
        檢查權限
        
        Args:
            user_role: 用戶角色
            action_type: 操作類型
            resource: 資源名稱
            context: 上下文信息
            
        Returns:
            PermissionCheck: 權限檢查結果
        """
        start_time = time.time()
        self.check_count += 1
        
        try:
            # 獲取用戶的有效權限
            effective_permissions = self._get_effective_permissions(user_role)
            
            # 檢查是否有權限
            allowed = action_type in effective_permissions
            
            # 記錄審計日誌
            audit_log = self._create_audit_log(user_role, action_type, resource, context, allowed, time.time() - start_time)
            self.audit_logs.append(audit_log)
            
            if not allowed:
                self.denied_count += 1
                required_role = self._get_required_role_for_action(action_type)
                return PermissionCheck(
                    allowed=False,
                    reason=f"權限不足，需要 {required_role.value} 角色",
                    required_role=required_role,
                    audit_log=audit_log
                )
            
            return PermissionCheck(
                allowed=True,
                reason="權限檢查通過",
                audit_log=audit_log
            )
            
        except Exception as e:
            logger.error(f"❌ 權限檢查失敗: {e}")
            return PermissionCheck(
                allowed=False,
                reason=f"權限檢查錯誤: {str(e)}"
            )
    
    def _get_effective_permissions(self, user_role: UserRole) -> Set[ActionType]:
        """
        獲取用戶的有效權限（包括繼承的權限）
        
        Args:
            user_role: 用戶角色
            
        Returns:
            Set[ActionType]: 有效權限集合
        """
        permissions = set()
        current_role = user_role
        
        while current_role:
            role_config = self.roles.get(current_role)
            if role_config:
                permissions.update(role_config["permissions"])
                current_role = role_config["inherits_from"]
            else:
                break
        
        return permissions
    
    def _get_required_role_for_action(self, action_type: ActionType) -> UserRole:
        """
        獲取執行特定操作所需的最低角色
        
        Args:
            action_type: 操作類型
            
        Returns:
            UserRole: 所需的最低角色
        """
        # 按權限等級排序角色
        role_hierarchy = [UserRole.USER, UserRole.TESTER, UserRole.DEVELOPER, UserRole.ADMIN]
        
        for role in role_hierarchy:
            role_config = self.roles.get(role)
            if role_config and action_type in role_config["permissions"]:
                return role
        
        return UserRole.ADMIN  # 默認需要管理員權限
    
    def _create_audit_log(self, user_role: UserRole, action_type: ActionType, resource: str, context: Dict[str, Any], allowed: bool, execution_time: float) -> Dict[str, Any]:
        """
        創建審計日誌
        
        Args:
            user_role: 用戶角色
            action_type: 操作類型
            resource: 資源名稱
            context: 上下文信息
            allowed: 是否允許
            execution_time: 執行時間
            
        Returns:
            Dict[str, Any]: 審計日誌
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "user_role": user_role.value,
            "action_type": action_type.value,
            "resource": resource,
            "context": context,
            "allowed": allowed,
            "execution_time": execution_time,
            "check_id": self.check_count
        }
    
    def add_role(self, role_name: str, permissions: List[ActionType], description: str = "", inherits_from: UserRole = None) -> bool:
        """
        添加新角色
        
        Args:
            role_name: 角色名稱
            permissions: 權限列表
            description: 角色描述
            inherits_from: 繼承自的角色
            
        Returns:
            bool: 添加是否成功
        """
        try:
            # 創建新的角色枚舉值
            new_role = UserRole(role_name)
            
            self.roles[new_role] = {
                "permissions": permissions,
                "description": description,
                "inherits_from": inherits_from
            }
            
            logger.info(f"✅ 新角色已添加: {role_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加角色失敗: {role_name}, 錯誤: {e}")
            return False
    
    def remove_role(self, role_name: str) -> bool:
        """
        移除角色
        
        Args:
            role_name: 角色名稱
            
        Returns:
            bool: 移除是否成功
        """
        try:
            role = UserRole(role_name)
            if role in self.roles:
                del self.roles[role]
                logger.info(f"✅ 角色已移除: {role_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ 移除角色失敗: {role_name}, 錯誤: {e}")
            return False
    
    def update_role_permissions(self, role_name: str, permissions: List[ActionType]) -> bool:
        """
        更新角色權限
        
        Args:
            role_name: 角色名稱
            permissions: 新的權限列表
            
        Returns:
            bool: 更新是否成功
        """
        try:
            role = UserRole(role_name)
            if role in self.roles:
                self.roles[role]["permissions"] = permissions
                logger.info(f"✅ 角色權限已更新: {role_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ 更新角色權限失敗: {role_name}, 錯誤: {e}")
            return False
    
    def get_role_info(self, role_name: str) -> Optional[Dict[str, Any]]:
        """
        獲取角色信息
        
        Args:
            role_name: 角色名稱
            
        Returns:
            Optional[Dict[str, Any]]: 角色信息
        """
        try:
            role = UserRole(role_name)
            return self.roles.get(role)
        except:
            return None
    
    def get_all_roles(self) -> Dict[str, Dict[str, Any]]:
        """
        獲取所有角色信息
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有角色信息
        """
        return {role.value: config for role, config in self.roles.items()}
    
    def get_permission_stats(self) -> Dict[str, Any]:
        """
        獲取權限檢查統計
        
        Returns:
            Dict[str, Any]: 權限檢查統計
        """
        total_checks = self.check_count
        denied_checks = self.denied_count
        allowed_checks = total_checks - denied_checks
        
        return {
            "total_checks": total_checks,
            "allowed_checks": allowed_checks,
            "denied_checks": denied_checks,
            "denial_rate": (denied_checks / total_checks * 100) if total_checks > 0 else 0,
            "roles_count": len(self.roles)
        }
    
    def get_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        獲取審計日誌
        
        Args:
            limit: 返回的日誌數量限制
            
        Returns:
            List[Dict[str, Any]]: 審計日誌列表
        """
        return self.audit_logs[-limit:] if self.audit_logs else []
    
    def clear_audit_logs(self):
        """清除審計日誌"""
        self.audit_logs.clear()
        logger.info("✅ 審計日誌已清除")
    
    def export_permission_matrix(self) -> Dict[str, Any]:
        """
        導出權限矩陣
        
        Returns:
            Dict[str, Any]: 權限矩陣
        """
        matrix = {}
        
        for role, config in self.roles.items():
            matrix[role.value] = {
                "description": config["description"],
                "permissions": [perm.value for perm in config["permissions"]],
                "inherits_from": config["inherits_from"].value if config["inherits_from"] else None
            }
        
        return matrix
    
    def validate_permission_hierarchy(self) -> Dict[str, Any]:
        """
        驗證權限層次結構
        
        Returns:
            Dict[str, Any]: 驗證結果
        """
        issues = []
        
        for role, config in self.roles.items():
            # 檢查繼承循環
            if config["inherits_from"]:
                current = config["inherits_from"]
                visited = {role}
                
                while current and current in self.roles:
                    if current in visited:
                        issues.append(f"循環繼承檢測到: {role.value} -> {current.value}")
                        break
                    visited.add(current)
                    current = self.roles[current]["inherits_from"]
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "roles_count": len(self.roles)
        }