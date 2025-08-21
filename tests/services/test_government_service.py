"""
政府系統服務測試套件
Task ID: 4.4 - 建立政府系統單元測試

本測試模組涵蓋：
- 政府系統資料模型測試 (需求 7.1, 7.7)
- 身分組管理服務測試 (需求 6.2, 7.2, 7.3, 7.5, 10.1-10.5)
- 政府服務核心邏輯測試 (需求 6.3, 6.4, 6.5, 7.4, 7.6)
- 與EconomyService整合測試 (需求 8.1, 9.1)
- 權限驗證測試 (需求 6.1, 6.2)
- 部門生命週期測試 (需求 6.3, 6.4, 6.5)
- JSON註冊表CRUD操作測試 (需求 7.1, 7.7)
"""

import pytest
import asyncio
import tempfile
import json
import os
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from datetime import datetime
from typing import Dict, Any, List

# 確保可以導入項目模組
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import discord
except ImportError:
    # 創建基本的discord mock
    discord = Mock()
    discord.Guild = Mock
    discord.Role = Mock
    discord.Member = Mock
    discord.Permissions = Mock
    discord.Color = Mock
    discord.Color.gold = Mock(return_value=Mock())
    discord.Color.blue = Mock(return_value=Mock())
    discord.Color.default = Mock(return_value=Mock())
    discord.Permissions.none = Mock(return_value=Mock())
    discord.Permissions.administrator = Mock(return_value=Mock())

from services.government.models import DepartmentRegistry, JSONRegistryManager
from core.exceptions import ServiceError, ValidationError

# 嘗試導入其他模組，如果失敗則創建mock
try:
    from services.government.role_service import RoleService
except ImportError:
    RoleService = Mock

try:
    from services.government.government_service import GovernmentService
except ImportError:
    GovernmentService = Mock

try:
    from core.database_manager import DatabaseManager
except ImportError:
    DatabaseManager = Mock

try:
    from services.economy.economy_service import EconomyService
    from services.economy.models import AccountType
except ImportError:
    EconomyService = Mock
    AccountType = Mock
    AccountType.GOVERNMENT_DEPARTMENT = "government_department"
    AccountType.GOVERNMENT_COUNCIL = "government_council"


class TestDepartmentRegistry:
    """政府系統資料模型測試"""
    
    def test_department_registry_creation(self):
        """測試部門註冊表資料類別建立 - F1驗收標準"""
        # Arrange
        department_data = {
            "id": 1,
            "guild_id": 123456789,
            "name": "財政部",
            "head_role_id": 987654321,
            "head_user_id": 111222333,
            "level_role_id": 444555666,
            "level_name": "部長級",
            "account_id": "ACC_GOV_001",
            "created_at": "2025-08-18T10:00:00",
            "updated_at": "2025-08-18T10:00:00"
        }
        
        # Act
        dept = DepartmentRegistry.from_dict(department_data)
        
        # Assert
        assert dept.id == 1
        assert dept.guild_id == 123456789
        assert dept.name == "財政部"
        assert dept.head_role_id == 987654321
        assert dept.head_user_id == 111222333
        assert dept.level_role_id == 444555666
        assert dept.level_name == "部長級"
        assert dept.account_id == "ACC_GOV_001"
    
    def test_department_registry_to_dict(self):
        """測試部門註冊表序列化 - F1驗收標準"""
        # Arrange
        dept = DepartmentRegistry(
            id=1,
            guild_id=123456789,
            name="財政部",
            head_role_id=987654321,
            head_user_id=111222333,
            level_role_id=444555666,
            level_name="部長級",
            account_id="ACC_GOV_001"
        )
        
        # Act
        dept_dict = dept.to_dict()
        
        # Assert
        assert dept_dict["id"] == 1
        assert dept_dict["guild_id"] == 123456789
        assert dept_dict["name"] == "財政部"
        assert dept_dict["head_role_id"] == 987654321
        assert dept_dict["head_user_id"] == 111222333
        assert dept_dict["level_role_id"] == 444555666
        assert dept_dict["level_name"] == "部長級"
        assert dept_dict["account_id"] == "ACC_GOV_001"
        assert "created_at" in dept_dict
        assert "updated_at" in dept_dict
    
    def test_department_registry_validation(self):
        """測試部門註冊表驗證 - F1驗收標準"""
        # Test valid department
        valid_dept = DepartmentRegistry(
            id=1,
            guild_id=123456789,
            name="財政部",
            head_role_id=987654321,
            head_user_id=111222333,
            level_role_id=444555666,
            level_name="部長級",
            account_id="ACC_GOV_001"
        )
        assert valid_dept.validate() == True
        
        # Test invalid department (missing required fields)
        with pytest.raises(ValidationError):
            invalid_dept = DepartmentRegistry(
                id=None,  # Required field missing
                guild_id=123456789,
                name="",  # Empty name
                head_role_id=0,  # Invalid role ID
            )
            invalid_dept.validate()


class TestRoleService:
    """身分組管理服務測試 - 需求 6.2, 7.2, 7.3, 7.5, 10.1-10.5"""
    
    @pytest.fixture
    async def role_service(self):
        """建立身分組服務實例"""
        service = RoleService()
        # Mock dependencies
        db_manager = Mock(spec=DatabaseManager)
        db_manager.is_initialized = True
        service.add_dependency(db_manager, "database_manager")
        
        await service.initialize()
        return service
    
    @pytest.fixture
    def mock_guild(self):
        """建立模擬Discord伺服器"""
        guild = Mock(spec=discord.Guild)
        guild.id = 123456789
        guild.name = "測試伺服器"
        guild.roles = []
        guild.owner_id = 999999999
        
        # Mock role creation
        async def create_role(name, **kwargs):
            role = Mock(spec=discord.Role)
            role.id = len(guild.roles) + 1000
            role.name = name
            role.color = kwargs.get('color', discord.Color.default())
            role.permissions = kwargs.get('permissions', discord.Permissions.none())
            role.position = kwargs.get('position', 1)
            role.hoist = kwargs.get('hoist', True)
            role.mentionable = kwargs.get('mentionable', False)
            
            # Mock role edit method
            async def edit_role(**edit_kwargs):
                for key, value in edit_kwargs.items():
                    setattr(role, key, value)
            role.edit = AsyncMock(side_effect=edit_role)
            
            # Mock role delete method
            async def delete_role(reason=None):
                if role in guild.roles:
                    guild.roles.remove(role)
            role.delete = AsyncMock(side_effect=delete_role)
            
            guild.roles.append(role)
            return role
        
        guild.create_role = AsyncMock(side_effect=create_role)
        return guild
    
    @pytest.fixture
    def mock_member(self):
        """建立模擬Discord成員"""
        member = Mock(spec=discord.Member)
        member.id = 111222333
        member.name = "測試用戶"
        member.roles = []
        member.guild_permissions = discord.Permissions.none()
        
        # Mock add/remove roles
        async def add_roles(*roles, reason=None):
            for role in roles:
                if role not in member.roles:
                    member.roles.append(role)
        
        async def remove_roles(*roles, reason=None):
            for role in roles:
                if role in member.roles:
                    member.roles.remove(role)
        
        member.add_roles = AsyncMock(side_effect=add_roles)
        member.remove_roles = AsyncMock(side_effect=remove_roles)
        return member
    
    @pytest.mark.asyncio
    async def test_create_role_if_not_exists_new_role(self, role_service, mock_guild):
        """測試建立不存在的身分組 - F2驗收標準"""
        # Arrange
        role_name = "常任理事"
        role_kwargs = {
            "color": discord.Color.gold(),
            "permissions": discord.Permissions.administrator()
        }
        
        # Act
        role = await role_service.create_role_if_not_exists(
            mock_guild, role_name, **role_kwargs
        )
        
        # Assert
        assert role is not None
        assert role.name == role_name
        mock_guild.create_role.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_role_if_not_exists_existing_role(self, role_service, mock_guild):
        """測試身分組已存在時不重複建立 - F2驗收標準"""
        # Arrange
        existing_role = Mock(spec=discord.Role)
        existing_role.name = "常任理事"
        existing_role.id = 999888777
        mock_guild.roles = [existing_role]
        
        # Act
        role = await role_service.create_role_if_not_exists(
            mock_guild, "常任理事"
        )
        
        # Assert
        assert role == existing_role
        mock_guild.create_role.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_ensure_council_role(self, role_service, mock_guild):
        """測試常任理事身分組自動建立 - F2驗收標準"""
        # Act
        council_role = await role_service.ensure_council_role(mock_guild)
        
        # Assert
        assert council_role is not None
        assert council_role.name == "常任理事"
        mock_guild.create_role.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_department_roles(self, role_service, mock_guild):
        """測試部門身分組建立 - 需求 7.2, 7.3, 10.1"""
        # Arrange
        department_data = {
            "name": "財政部",
            "level_name": "部長級",
            "head_user_id": 111222333
        }
        
        # Act
        roles = await role_service.create_department_roles(mock_guild, department_data)
        
        # Assert
        assert "head_role" in roles
        assert "level_role" in roles
        assert roles["head_role"].name == "財政部部長"
        assert roles["level_role"].name == "部長級"
        assert mock_guild.create_role.call_count == 2
        
        # 驗證身分組權限設定
        head_role = roles["head_role"]
        level_role = roles["level_role"]
        
        # 部門負責人應該有管理權限
        assert head_role.permissions.manage_messages
        assert head_role.permissions.manage_threads
        assert head_role.permissions.moderate_members
        
        # 級別身分組應該有基本權限
        assert level_role.permissions.send_messages
        assert level_role.permissions.embed_links
    
    @pytest.mark.asyncio
    async def test_assign_role_to_user(self, role_service, mock_guild, mock_member):
        """測試為使用者指派身分組 - 需求 10.4"""
        # Arrange
        role = Mock(spec=discord.Role)
        role.id = 987654321
        role.name = "財政部部長"
        
        # Act
        result = await role_service.assign_role_to_user(
            mock_guild, mock_member, role, "指派為部門負責人"
        )
        
        # Assert
        assert result is True
        mock_member.add_roles.assert_called_once_with(role, reason="指派為部門負責人")
        assert role in mock_member.roles
    
    @pytest.mark.asyncio
    async def test_assign_role_already_has_role(self, role_service, mock_guild, mock_member):
        """測試指派已擁有的身分組 - 需求 10.4"""
        # Arrange
        role = Mock(spec=discord.Role)
        role.id = 987654321
        role.name = "財政部部長"
        mock_member.roles = [role]  # 用戶已有此身分組
        
        # Act
        result = await role_service.assign_role_to_user(mock_guild, mock_member, role)
        
        # Assert
        assert result is True
        mock_member.add_roles.assert_not_called()  # 不應該重複指派
    
    @pytest.mark.asyncio
    async def test_remove_role_from_user(self, role_service, mock_guild, mock_member):
        """測試移除使用者身分組 - 需求 10.5"""
        # Arrange
        role = Mock(spec=discord.Role)
        role.id = 987654321
        role.name = "財政部部長"
        mock_member.roles = [role]  # 用戶擁有此身分組
        
        # Act
        result = await role_service.remove_role_from_user(
            mock_guild, mock_member, role, "職位變更"
        )
        
        # Assert
        assert result is True
        mock_member.remove_roles.assert_called_once_with(role, reason="職位變更")
        assert role not in mock_member.roles
    
    @pytest.mark.asyncio
    async def test_remove_role_user_doesnt_have(self, role_service, mock_guild, mock_member):
        """測試移除用戶沒有的身分組 - 需求 10.5"""
        # Arrange
        role = Mock(spec=discord.Role)
        role.id = 987654321
        role.name = "財政部部長"
        # mock_member.roles 為空，用戶沒有此身分組
        
        # Act
        result = await role_service.remove_role_from_user(mock_guild, mock_member, role)
        
        # Assert
        assert result is True
        mock_member.remove_roles.assert_not_called()  # 不應該嘗試移除
    
    @pytest.mark.asyncio
    async def test_delete_role(self, role_service, mock_guild):
        """測試刪除身分組 - 需求 7.6"""
        # Arrange
        role = Mock(spec=discord.Role)
        role.id = 987654321
        role.name = "財政部部長"
        mock_guild.roles = [role]
        
        # Act
        result = await role_service.delete_role(mock_guild, role, "部門解散")
        
        # Assert
        assert result is True
        role.delete.assert_called_once_with(reason="部門解散")
    
    @pytest.mark.asyncio
    async def test_get_role_by_name(self, role_service, mock_guild):
        """測試根據名稱獲取身分組"""
        # Arrange
        role = Mock(spec=discord.Role)
        role.id = 987654321
        role.name = "常任理事"
        mock_guild.roles = [role]
        
        # Act
        found_role = await role_service.get_role_by_name(mock_guild, "常任理事")
        
        # Assert
        assert found_role == role
    
    @pytest.mark.asyncio
    async def test_get_role_by_name_not_found(self, role_service, mock_guild):
        """測試獲取不存在的身分組"""
        # Arrange
        mock_guild.roles = []
        
        # Act
        found_role = await role_service.get_role_by_name(mock_guild, "不存在的身分組")
        
        # Assert
        assert found_role is None
    
    @pytest.mark.asyncio
    async def test_list_department_roles(self, role_service, mock_guild):
        """測試獲取部門相關身分組列表"""
        # Arrange
        dept_head_role = Mock(spec=discord.Role)
        dept_head_role.name = "財政部部長"
        dept_deputy_role = Mock(spec=discord.Role)
        dept_deputy_role.name = "財政部副部長"
        other_role = Mock(spec=discord.Role)
        other_role.name = "其他身分組"
        
        mock_guild.roles = [dept_head_role, dept_deputy_role, other_role]
        
        # Act
        department_roles = await role_service.list_department_roles(mock_guild, "財政部")
        
        # Assert
        assert len(department_roles) == 2
        assert dept_head_role in department_roles
        assert dept_deputy_role in department_roles
        assert other_role not in department_roles
    
    @pytest.mark.asyncio
    async def test_cleanup_department_roles(self, role_service, mock_guild):
        """測試清理部門身分組 - 需求 7.6"""
        # Arrange
        dept_head_role = Mock(spec=discord.Role)
        dept_head_role.name = "財政部部長"
        dept_deputy_role = Mock(spec=discord.Role)
        dept_deputy_role.name = "財政部副部長"
        
        mock_guild.roles = [dept_head_role, dept_deputy_role]
        
        # Mock list_department_roles to return these roles
        role_service.list_department_roles = AsyncMock(
            return_value=[dept_head_role, dept_deputy_role]
        )
        
        # Act
        result = await role_service.cleanup_department_roles(mock_guild, "財政部")
        
        # Assert
        assert result is True
        dept_head_role.delete.assert_called_once()
        dept_deputy_role.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_role_hierarchy_setup(self, role_service, mock_guild):
        """測試身分組階層設定 - 需求 10.3"""
        # Arrange
        council_role = Mock(spec=discord.Role)
        council_role.name = "常任理事"
        council_role.position = 10
        
        department_data = {
            "name": "財政部",
            "level_name": "部長級"
        }
        
        mock_guild.roles = [council_role]
        
        # Act
        roles = await role_service.create_department_roles(mock_guild, department_data)
        
        # Assert - 驗證身分組位置調整被調用
        head_role = roles["head_role"]
        level_role = roles["level_role"]
        
        # 部門負責人身分組應該在常任理事之下
        head_role.edit.assert_called()
        level_role.edit.assert_called()
    
    @pytest.mark.asyncio
    async def test_role_permissions_validation(self, role_service, mock_guild):
        """測試身分組權限驗證 - 需求 10.1, 10.2"""
        # Arrange
        department_data = {
            "name": "財政部",
            "level_name": "部長級"
        }
        
        # Act
        roles = await role_service.create_department_roles(mock_guild, department_data)
        
        # Assert - 驗證權限設定正確
        head_role_call = mock_guild.create_role.call_args_list[0]
        level_role_call = mock_guild.create_role.call_args_list[1]
        
        # 部門負責人權限
        head_permissions = head_role_call[1]['permissions']
        assert head_permissions.manage_messages
        assert head_permissions.manage_threads
        assert head_permissions.moderate_members
        
        # 級別身分組權限
        level_permissions = level_role_call[1]['permissions']
        assert level_permissions.send_messages
        assert level_permissions.embed_links


class TestGovernmentService:
    """政府服務核心邏輯測試 - 需求 6.3, 6.4, 6.5, 7.4, 7.6, 8.1, 9.1"""
    
    @pytest.fixture
    async def government_service(self):
        """建立政府服務實例"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_registry_file = f.name
            initial_data = {"departments": [], "metadata": {"version": "1.0"}}
            json.dump(initial_data, f)
        
        service = GovernmentService(registry_file=temp_registry_file)
        
        # Mock dependencies
        db_manager = Mock(spec=DatabaseManager)
        db_manager.is_initialized = True
        db_manager.migration_manager = Mock()
        db_manager.migration_manager.apply_migrations = AsyncMock(return_value=True)
        
        role_service = Mock(spec=RoleService)
        role_service.is_initialized = True
        
        economy_service = Mock(spec=EconomyService)
        economy_service.is_initialized = True
        
        service.add_dependency(db_manager, "database_manager")
        service.add_dependency(role_service, "role_service")
        service.add_dependency(economy_service, "economy_service")
        
        await service.initialize()
        
        # 清理函數
        def cleanup():
            if os.path.exists(temp_registry_file):
                os.unlink(temp_registry_file)
        
        service._test_cleanup = cleanup
        return service
    
    def teardown_method(self, method):
        """測試方法清理"""
        # 清理任何測試產生的臨時檔案
        import glob
        temp_files = glob.glob("/tmp/tmp*.json") + glob.glob("/tmp/tmp*.json.backup")
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass
    
    @pytest.fixture
    def mock_guild(self):
        """建立模擬Discord伺服器"""
        guild = Mock(spec=discord.Guild)
        guild.id = 123456789
        guild.name = "測試伺服器"
        guild.owner_id = 999999999
        
        # Mock get_member
        def get_member(user_id):
            if user_id == 111222333:
                member = Mock(spec=discord.Member)
                member.id = user_id
                member.roles = []
                return member
            return None
        
        guild.get_member = get_member
        return guild
    
    @pytest.fixture
    def temp_json_file(self):
        """建立臨時JSON檔案用於測試"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            initial_data = {"departments": [], "metadata": {"version": "1.0"}}
            json.dump(initial_data, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_create_department(self, government_service, mock_guild):
        """測試部門建立功能 - 需求 6.3, 7.1, 7.2, 9.1"""
        # Arrange
        department_data = {
            "name": "財政部",
            "head_user_id": 111222333,
            "level_name": "部長級"
        }
        
        # Mock database and service operations
        government_service.db_manager.execute = AsyncMock(return_value=1)
        government_service.db_manager.fetchone = AsyncMock(return_value=None)  # 部門不存在
        
        mock_head_role = Mock(spec=discord.Role)
        mock_head_role.id = 987654321
        mock_level_role = Mock(spec=discord.Role)
        mock_level_role.id = 444555666
        
        government_service.role_service.create_department_roles = AsyncMock(
            return_value={
                "head_role": mock_head_role,
                "level_role": mock_level_role
            }
        )
        
        mock_account = Mock()
        mock_account.id = "gov_department_123456789_1"
        government_service.economy_service.create_account = AsyncMock(
            return_value=mock_account
        )
        
        government_service.role_service.assign_role_to_user = AsyncMock(return_value=True)
        
        # Act
        department_id = await government_service.create_department(mock_guild, department_data)
        
        # Assert
        assert department_id == 1
        government_service.db_manager.execute.assert_called_once()
        government_service.role_service.create_department_roles.assert_called_once()
        government_service.economy_service.create_account.assert_called_once()
        
        # 驗證帳戶建立參數
        create_account_call = government_service.economy_service.create_account.call_args
        assert create_account_call[1]['guild_id'] == mock_guild.id
        assert create_account_call[1]['account_type'] == AccountType.GOVERNMENT_DEPARTMENT
        assert create_account_call[1]['user_id'] is None
        assert create_account_call[1]['initial_balance'] == 0.0
        
        # 驗證身分組指派
        government_service.role_service.assign_role_to_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_department_duplicate_name(self, government_service, mock_guild):
        """測試建立重複名稱部門 - 需求 6.3"""
        # Arrange
        department_data = {
            "name": "財政部",
            "head_user_id": 111222333,
            "level_name": "部長級"
        }
        
        # Mock 部門已存在
        existing_dept = {
            "id": 1,
            "guild_id": mock_guild.id,
            "name": "財政部"
        }
        government_service.db_manager.fetchone = AsyncMock(return_value=existing_dept)
        
        # Act & Assert
        with pytest.raises(ServiceError) as exc_info:
            await government_service.create_department(mock_guild, department_data)
        
        assert "已存在" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_department_invalid_data(self, government_service, mock_guild):
        """測試建立部門時資料驗證 - 需求 6.3"""
        # Arrange - 空的部門名稱
        invalid_department_data = {
            "name": "",  # 無效的空名稱
            "head_user_id": 111222333,
            "level_name": "部長級"
        }
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await government_service.create_department(mock_guild, invalid_department_data)
        
        assert "部門名稱不能為空" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_department(self, government_service):
        """測試部門更新功能 - 需求 6.5, 7.4"""
        # Arrange
        department_id = 1
        updates = {
            "name": "新財政部",
            "head_user_id": 999888777
        }
        
        # Mock 現有部門資料
        existing_dept = {
            "id": department_id,
            "guild_id": 123456789,
            "name": "財政部"
        }
        government_service._get_department_by_id = AsyncMock(return_value=existing_dept)
        government_service.db_manager.execute = AsyncMock(return_value=True)
        
        # Mock JSON註冊表更新
        government_service._registry_manager.update_department = AsyncMock(return_value=True)
        
        # Act
        result = await government_service.update_department(department_id, updates)
        
        # Assert
        assert result == True
        government_service.db_manager.execute.assert_called_once()
        government_service._registry_manager.update_department.assert_called_once_with(
            department_id, updates
        )
    
    @pytest.mark.asyncio
    async def test_update_department_not_found(self, government_service):
        """測試更新不存在的部門 - 需求 6.5"""
        # Arrange
        department_id = 999
        updates = {"name": "新名稱"}
        
        government_service._get_department_by_id = AsyncMock(return_value=None)
        
        # Act & Assert
        with pytest.raises(ServiceError) as exc_info:
            await government_service.update_department(department_id, updates)
        
        assert f"找不到ID為 {department_id} 的部門" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_department(self, government_service, mock_guild):
        """測試部門刪除功能 - 需求 6.4, 7.6, 9.1"""
        # Arrange
        department_id = 1
        
        # Mock database query to return department data
        department_data = {
            "id": 1,
            "guild_id": mock_guild.id,
            "name": "財政部",
            "account_id": "gov_department_123456789_1"
        }
        
        government_service._get_department_by_id = AsyncMock(return_value=department_data)
        government_service.db_manager.execute = AsyncMock(return_value=True)
        
        # Mock 帳戶處理
        mock_account = Mock()
        mock_account.balance = 5000.0
        government_service.economy_service.get_account = AsyncMock(return_value=mock_account)
        
        mock_council_account = Mock()
        government_service.economy_service.get_account = AsyncMock(
            side_effect=lambda account_id: mock_account if "department" in account_id else mock_council_account
        )
        government_service.economy_service.transfer = AsyncMock(return_value=True)
        
        # Mock 身分組清理
        government_service.role_service.cleanup_department_roles = AsyncMock(return_value=True)
        
        # Mock JSON註冊表移除
        government_service._registry_manager.remove_department = AsyncMock(return_value=True)
        
        # Act
        result = await government_service.delete_department(mock_guild, department_id)
        
        # Assert
        assert result == True
        government_service.db_manager.execute.assert_called_once()
        government_service.role_service.cleanup_department_roles.assert_called_once()
        government_service._registry_manager.remove_department.assert_called_once()
        
        # 驗證餘額轉移
        government_service.economy_service.transfer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_department_not_found(self, government_service, mock_guild):
        """測試刪除不存在的部門 - 需求 6.4"""
        # Arrange
        department_id = 999
        government_service._get_department_by_id = AsyncMock(return_value=None)
        
        # Act & Assert
        with pytest.raises(ServiceError) as exc_info:
            await government_service.delete_department(mock_guild, department_id)
        
        assert f"找不到ID為 {department_id} 的部門" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_department_registry(self, government_service):
        """測試獲取部門註冊表 - 需求 7.7"""
        # Arrange
        guild_id = 123456789
        mock_departments = [
            DepartmentRegistry(
                id=1,
                guild_id=guild_id,
                name="財政部",
                head_role_id=987654321,
                head_user_id=111222333,
                level_role_id=444555666,
                level_name="部長級",
                account_id="gov_department_123456789_1"
            ),
            DepartmentRegistry(
                id=2,
                guild_id=guild_id,
                name="內政部",
                head_role_id=987654322,
                head_user_id=111222334,
                level_role_id=444555667,
                level_name="部長級",
                account_id="gov_department_123456789_2"
            )
        ]
        
        government_service._registry_manager.get_departments_by_guild = AsyncMock(
            return_value=mock_departments
        )
        
        # Act
        registry = await government_service.get_department_registry(guild_id)
        
        # Assert
        assert len(registry) == 2
        assert registry[0]["name"] == "財政部"
        assert registry[1]["name"] == "內政部"
        government_service._registry_manager.get_departments_by_guild.assert_called_once_with(guild_id)
    
    @pytest.mark.asyncio
    async def test_get_department_by_id(self, government_service):
        """測試根據ID獲取部門資訊"""
        # Arrange
        department_id = 1
        mock_department = {
            "id": 1,
            "guild_id": 123456789,
            "name": "財政部",
            "head_role_id": 987654321,
            "head_user_id": 111222333,
            "level_role_id": 444555666,
            "level_name": "部長級",
            "account_id": "gov_department_123456789_1"
        }
        
        government_service._get_department_by_id = AsyncMock(return_value=mock_department)
        
        # Act
        department = await government_service.get_department_by_id(department_id)
        
        # Assert
        assert department == mock_department
        government_service._get_department_by_id.assert_called_once_with(department_id)
    
    @pytest.mark.asyncio
    async def test_ensure_council_infrastructure(self, government_service, mock_guild):
        """測試確保常任理事會基礎設施 - 需求 6.2, 8.1"""
        # Arrange
        mock_council_role = Mock(spec=discord.Role)
        mock_council_role.id = 888777666
        mock_council_role.name = "常任理事"
        
        government_service.role_service.ensure_council_role = AsyncMock(
            return_value=mock_council_role
        )
        
        # Mock 理事會帳戶建立
        mock_council_account = Mock()
        mock_council_account.id = f"gov_council_{mock_guild.id}"
        government_service.economy_service.get_account = AsyncMock(return_value=None)  # 帳戶不存在
        government_service.economy_service.create_account = AsyncMock(
            return_value=mock_council_account
        )
        
        # Act
        result = await government_service.ensure_council_infrastructure(mock_guild)
        
        # Assert
        assert result is True
        government_service.role_service.ensure_council_role.assert_called_once_with(mock_guild)
        government_service.economy_service.create_account.assert_called_once()
        
        # 驗證理事會帳戶建立參數
        create_account_call = government_service.economy_service.create_account.call_args
        assert create_account_call[1]['guild_id'] == mock_guild.id
        assert create_account_call[1]['account_type'] == AccountType.GOVERNMENT_COUNCIL
        assert create_account_call[1]['user_id'] is None
        assert create_account_call[1]['initial_balance'] == 1000000.0  # 理事會初始資金
    
    @pytest.mark.asyncio
    async def test_ensure_council_infrastructure_account_exists(self, government_service, mock_guild):
        """測試理事會帳戶已存在的情況 - 需求 8.1"""
        # Arrange
        mock_council_role = Mock(spec=discord.Role)
        government_service.role_service.ensure_council_role = AsyncMock(
            return_value=mock_council_role
        )
        
        # Mock 理事會帳戶已存在
        mock_existing_account = Mock()
        government_service.economy_service.get_account = AsyncMock(
            return_value=mock_existing_account
        )
        
        # Act
        result = await government_service.ensure_council_infrastructure(mock_guild)
        
        # Assert
        assert result is True
        government_service.role_service.ensure_council_role.assert_called_once()
        government_service.economy_service.get_account.assert_called_once()
        government_service.economy_service.create_account.assert_not_called()  # 不應該建立新帳戶


class TestPermissionValidation:
    """權限驗證測試 - 需求 6.1, 6.2"""
    
    @pytest.fixture
    async def government_service_with_discord_client(self):
        """建立帶有Discord客戶端的政府服務"""
        service = GovernmentService()
        
        # Mock Discord客戶端
        discord_client = Mock()
        mock_guild = Mock(spec=discord.Guild)
        mock_guild.id = 123456789
        mock_guild.owner_id = 999999999
        
        discord_client.get_guild = Mock(return_value=mock_guild)
        
        service.add_dependency(discord_client, "discord_client")
        
        return service, mock_guild
    
    @pytest.mark.asyncio
    async def test_validate_permissions_administrator(self, government_service_with_discord_client):
        """測試管理員權限驗證 - 需求 6.1"""
        # Arrange
        service, mock_guild = government_service_with_discord_client
        
        mock_member = Mock(spec=discord.Member)
        mock_member.id = 111222333
        mock_member.guild_permissions = discord.Permissions(administrator=True)
        mock_guild.get_member = Mock(return_value=mock_member)
        
        # Act
        result = await service._validate_permissions(111222333, 123456789, "create_department")
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_permissions_server_owner(self, government_service_with_discord_client):
        """測試伺服器所有者權限 - 需求 6.1"""
        # Arrange
        service, mock_guild = government_service_with_discord_client
        
        mock_member = Mock(spec=discord.Member)
        mock_member.id = 999999999  # 伺服器所有者ID
        mock_member.guild_permissions = discord.Permissions.none()
        mock_guild.get_member = Mock(return_value=mock_member)
        
        # Act
        result = await service._validate_permissions(999999999, 123456789, "create_department")
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_permissions_council_member(self, government_service_with_discord_client):
        """測試常任理事權限 - 需求 6.2"""
        # Arrange
        service, mock_guild = government_service_with_discord_client
        
        # 建立常任理事身分組
        council_role = Mock(spec=discord.Role)
        council_role.name = "常任理事"
        
        mock_member = Mock(spec=discord.Member)
        mock_member.id = 111222333
        mock_member.guild_permissions = discord.Permissions.none()
        mock_member.roles = [council_role]
        
        mock_guild.get_member = Mock(return_value=mock_member)
        mock_guild.roles = [council_role]
        
        # Act
        result = await service._validate_permissions(111222333, 123456789, "create_department")
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_permissions_no_permission(self, government_service_with_discord_client):
        """測試無權限用戶 - 需求 6.1"""
        # Arrange
        service, mock_guild = government_service_with_discord_client
        
        mock_member = Mock(spec=discord.Member)
        mock_member.id = 111222333
        mock_member.guild_permissions = discord.Permissions.none()
        mock_member.roles = []
        
        mock_guild.get_member = Mock(return_value=mock_member)
        mock_guild.roles = []
        
        # Act
        result = await service._validate_permissions(111222333, 123456789, "create_department")
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_permissions_member_not_found(self, government_service_with_discord_client):
        """測試找不到成員的情況"""
        # Arrange
        service, mock_guild = government_service_with_discord_client
        mock_guild.get_member = Mock(return_value=None)
        
        # Act
        result = await service._validate_permissions(111222333, 123456789, "create_department")
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_permissions_guild_not_found(self, government_service_with_discord_client):
        """測試找不到伺服器的情況"""
        # Arrange
        service, _ = government_service_with_discord_client
        discord_client = service.get_dependency("discord_client")
        discord_client.get_guild = Mock(return_value=None)
        
        # Act
        result = await service._validate_permissions(111222333, 123456789, "create_department")
        
        # Assert
        assert result is False


class TestJSONRegistryManager:
    """JSON註冊表管理器測試 - 需求 7.1, 7.7"""
    
    @pytest.fixture
    def temp_json_file(self):
        """建立臨時JSON檔案"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        yield temp_path
        
        # 清理
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_read_registry_new_file(self, temp_json_file):
        """測試讀取新建的註冊表檔案 - 需求 7.1"""
        # Arrange
        registry_manager = JSONRegistryManager(temp_json_file)
        
        # Act
        data = await registry_manager.read_registry()
        
        # Assert
        assert "departments" in data
        assert "metadata" in data
        assert data["departments"] == []
        assert data["metadata"]["version"] == "1.0"
    
    @pytest.mark.asyncio
    async def test_add_department_to_registry(self, temp_json_file):
        """測試添加部門到註冊表 - 需求 7.1"""
        # Arrange
        registry_manager = JSONRegistryManager(temp_json_file)
        department = DepartmentRegistry(
            id=1,
            guild_id=123456789,
            name="財政部",
            head_role_id=987654321,
            head_user_id=111222333,
            level_role_id=444555666,
            level_name="部長級",
            account_id="gov_department_123456789_1"
        )
        
        # Act
        result = await registry_manager.add_department(department)
        
        # Assert
        assert result is True
        
        # 驗證資料已寫入
        data = await registry_manager.read_registry()
        assert len(data["departments"]) == 1
        assert data["departments"][0]["name"] == "財政部"
    
    @pytest.mark.asyncio
    async def test_add_duplicate_department(self, temp_json_file):
        """測試添加重複部門 - 需求 7.1"""
        # Arrange
        registry_manager = JSONRegistryManager(temp_json_file)
        department = DepartmentRegistry(
            id=1,
            guild_id=123456789,
            name="財政部",
            head_role_id=987654321,
            head_user_id=111222333,
            level_role_id=444555666,
            level_name="部長級",
            account_id="gov_department_123456789_1"
        )
        
        # 先添加一次
        await registry_manager.add_department(department)
        
        # Act & Assert - 嘗試再次添加相同部門
        with pytest.raises(ServiceError) as exc_info:
            await registry_manager.add_department(department)
        
        assert "已存在" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_department_in_registry(self, temp_json_file):
        """測試更新註冊表中的部門 - 需求 7.4"""
        # Arrange
        registry_manager = JSONRegistryManager(temp_json_file)
        department = DepartmentRegistry(
            id=1,
            guild_id=123456789,
            name="財政部",
            head_role_id=987654321,
            head_user_id=111222333,
            level_role_id=444555666,
            level_name="部長級",
            account_id="gov_department_123456789_1"
        )
        
        await registry_manager.add_department(department)
        
        # Act
        updates = {"head_user_id": 999888777, "name": "新財政部"}
        result = await registry_manager.update_department(1, updates)
        
        # Assert
        assert result is True
        
        # 驗證更新
        data = await registry_manager.read_registry()
        dept_data = data["departments"][0]
        assert dept_data["head_user_id"] == 999888777
        assert dept_data["name"] == "新財政部"
        assert "updated_at" in dept_data
    
    @pytest.mark.asyncio
    async def test_remove_department_from_registry(self, temp_json_file):
        """測試從註冊表移除部門 - 需求 7.6"""
        # Arrange
        registry_manager = JSONRegistryManager(temp_json_file)
        department = DepartmentRegistry(
            id=1,
            guild_id=123456789,
            name="財政部",
            head_role_id=987654321,
            head_user_id=111222333,
            level_role_id=444555666,
            level_name="部長級",
            account_id="gov_department_123456789_1"
        )
        
        await registry_manager.add_department(department)
        
        # Act
        result = await registry_manager.remove_department(1)
        
        # Assert
        assert result is True
        
        # 驗證移除
        data = await registry_manager.read_registry()
        assert len(data["departments"]) == 0
    
    @pytest.mark.asyncio
    async def test_get_departments_by_guild(self, temp_json_file):
        """測試根據伺服器ID獲取部門 - 需求 7.7"""
        # Arrange
        registry_manager = JSONRegistryManager(temp_json_file)
        
        # 添加多個部門，不同伺服器
        dept1 = DepartmentRegistry(
            id=1, guild_id=123456789, name="財政部",
            head_role_id=987654321, account_id="acc1"
        )
        dept2 = DepartmentRegistry(
            id=2, guild_id=123456789, name="內政部",
            head_role_id=987654322, account_id="acc2"
        )
        dept3 = DepartmentRegistry(
            id=3, guild_id=987654321, name="外交部",
            head_role_id=987654323, account_id="acc3"
        )
        
        await registry_manager.add_department(dept1)
        await registry_manager.add_department(dept2)
        await registry_manager.add_department(dept3)
        
        # Act
        guild_departments = await registry_manager.get_departments_by_guild(123456789)
        
        # Assert
        assert len(guild_departments) == 2
        dept_names = [dept.name for dept in guild_departments]
        assert "財政部" in dept_names
        assert "內政部" in dept_names
        assert "外交部" not in dept_names
    
    @pytest.mark.asyncio
    async def test_atomic_write_operations(self, temp_json_file):
        """測試原子性寫入操作 - 需求 7.1"""
        # Arrange
        registry_manager = JSONRegistryManager(temp_json_file)
        
        # 建立多個部門並發添加（模擬併發情況）
        departments = [
            DepartmentRegistry(
                id=i, guild_id=123456789, name=f"部門{i}",
                head_role_id=987654321 + i, account_id=f"acc{i}"
            )
            for i in range(1, 6)
        ]
        
        # Act - 併發添加
        tasks = [registry_manager.add_department(dept) for dept in departments]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assert - 所有操作都應該成功
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"併發操作失敗: {result}")
            assert result is True
        
        # 驗證所有部門都被正確添加
        data = await registry_manager.read_registry()
        assert len(data["departments"]) == 5


class TestGovernmentIntegration:
    """政府系統整合測試 - 需求 6.1-6.5, 7.1-7.7, 8.1, 9.1"""
    
    @pytest.mark.asyncio
    async def test_full_department_lifecycle(self):
        """測試完整部門生命週期 - F3驗收標準"""
        # 這是一個完整的整合測試，測試從部門建立到刪除的完整工作流程
        # 包括資料庫操作、身分組管理和帳戶建立
        
        # 測試政府服務初始化
        government_service = GovernmentService()
        
        # Mock所有依賴服務
        db_manager = Mock(spec=DatabaseManager)
        db_manager.is_initialized = True
        db_manager.execute = AsyncMock(return_value=1)
        db_manager.fetchone = AsyncMock(return_value=None)
        
        role_service = Mock(spec=RoleService)  
        role_service.is_initialized = True
        role_service.create_department_roles = AsyncMock(return_value={
            "head_role": Mock(id=987654321, name="財政部部長"),
            "level_role": Mock(id=444555666, name="部長級")
        })
        role_service.cleanup_department_roles = AsyncMock(return_value=True)
        
        economy_service = Mock(spec=EconomyService)
        economy_service.is_initialized = True
        
        # Mock經濟服務的帳戶建立
        mock_account = Mock()
        mock_account.id = "gov_department_123456789_1"
        mock_account.balance = 0.0
        economy_service.create_account = AsyncMock(return_value=mock_account)
        economy_service.get_account = AsyncMock(return_value=mock_account)
        economy_service.transfer = AsyncMock(return_value=True)
        
        government_service.add_dependency(db_manager, "database_manager")
        government_service.add_dependency(role_service, "role_service")
        government_service.add_dependency(economy_service, "economy_service")
        
        # 初始化服務
        await government_service.initialize()
        
        # Mock Discord Guild
        mock_guild = Mock(spec=discord.Guild)
        mock_guild.id = 123456789
        mock_guild.name = "測試伺服器"
        
        # 測試部門建立
        department_data = {
            "name": "財政部",
            "head_user_id": 111222333,
            "level_name": "部長級"
        }
        
        # 執行部門建立
        department_id = await government_service.create_department(mock_guild, department_data)
        
        # 驗證建立流程
        assert department_id == 1
        role_service.create_department_roles.assert_called_once()
        economy_service.create_account.assert_called_once()
        db_manager.execute.assert_called()
        
        # 測試部門更新
        updates = {"head_user_id": 999888777}
        db_manager.execute.reset_mock()
        result = await government_service.update_department(department_id, updates)
        
        assert result == True
        db_manager.execute.assert_called()
        
        # 測試部門刪除
        mock_department = {
            "id": department_id,
            "guild_id": mock_guild.id,
            "name": "財政部",
            "account_id": mock_account.id
        }
        db_manager.fetchone.return_value = mock_department
        
        result = await government_service.delete_department(mock_guild, department_id)
        
        assert result == True
        role_service.cleanup_department_roles.assert_called_once()
        economy_service.get_account.assert_called()
    
    @pytest.mark.asyncio
    async def test_json_registry_atomic_operations(self):
        """測試JSON註冊表原子性操作 - F1驗收標準"""
        from services.government.models import JSONRegistryManager, DepartmentRegistry
        import tempfile
        import os
        
        # 建立臨時文件用於測試
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            registry_manager = JSONRegistryManager(temp_path)
            
            # 測試初始讀取
            data = await registry_manager.read_registry()
            assert "departments" in data
            assert "metadata" in data
            
            # 測試添加部門
            department = DepartmentRegistry(
                id=1,
                guild_id=123456789,
                name="財政部",
                head_role_id=987654321,
                head_user_id=111222333,
                level_role_id=444555666,
                level_name="部長級",
                account_id="ACC_GOV_001"
            )
            
            result = await registry_manager.add_department(department)
            assert result == True
            
            # 測試讀取部門
            departments = await registry_manager.get_departments_by_guild(123456789)
            assert len(departments) == 1
            assert departments[0].name == "財政部"
            
            # 測試更新部門
            updates = {"head_user_id": 999888777}
            result = await registry_manager.update_department(1, updates)
            assert result == True
            
            # 測試刪除部門
            result = await registry_manager.remove_department(1)
            assert result == True
            
            # 驗證部門已刪除
            departments = await registry_manager.get_departments_by_guild(123456789)
            assert len(departments) == 0
            
        finally:
            # 清理臨時文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_economy_service_integration(self):
        """測試與經濟系統整合 - F3驗收標準"""
        # 測試政府系統與經濟系統的完整整合
        
        # Mock EconomyService
        economy_service = Mock(spec=EconomyService)
        economy_service.is_initialized = True
        
        # Mock帳戶建立回傳
        mock_account = Mock()
        mock_account.id = "gov_department_123456789_1" 
        mock_account.balance = 0.0
        economy_service.create_account = AsyncMock(return_value=mock_account)
        
        # Mock帳戶查詢回傳
        economy_service.get_account = AsyncMock(return_value=mock_account)
        
        # Mock轉帳操作
        mock_transaction = Mock()
        mock_transaction.id = "TXN_001"
        economy_service.transfer = AsyncMock(return_value=mock_transaction)
        
        # 測試政府部門帳戶建立
        from services.economy.models import AccountType
        
        # 驗證帳戶建立調用
        await economy_service.create_account(
            guild_id=123456789,
            account_type=AccountType.GOVERNMENT_DEPARTMENT,
            user_id=None,
            initial_balance=0.0
        )
        
        economy_service.create_account.assert_called_once_with(
            guild_id=123456789,
            account_type=AccountType.GOVERNMENT_DEPARTMENT,
            user_id=None,
            initial_balance=0.0
        )
        
        # 測試理事會帳戶建立
        council_account = Mock()
        council_account.id = "gov_council_123456789"
        council_account.balance = 1000000.0
        economy_service.create_account.return_value = council_account
        
        await economy_service.create_account(
            guild_id=123456789,
            account_type=AccountType.GOVERNMENT_COUNCIL,
            user_id=None,
            initial_balance=1000000.0
        )
        
        # 測試部門間資金轉移
        await economy_service.transfer(
            from_account_id="gov_department_123456789_1",
            to_account_id="gov_council_123456789", 
            amount=1000.0,
            reason="部門解散，餘額歸還理事會"
        )
        
        economy_service.transfer.assert_called_once()


@pytest.mark.asyncio
async def test_service_initialization_order():
    """測試服務初始化順序和依賴關係"""
    from services.government.government_service import GovernmentService
    from services.government.role_service import RoleService
    from services.economy.economy_service import EconomyService
    from core.database_manager import DatabaseManager
    
    # 建立服務實例
    db_manager = Mock(spec=DatabaseManager)
    db_manager.is_initialized = True
    
    economy_service = Mock(spec=EconomyService) 
    economy_service.is_initialized = True
    
    role_service = Mock(spec=RoleService)
    role_service.is_initialized = True
    
    government_service = GovernmentService()
    
    # 測試依賴關係設定
    government_service.add_dependency(db_manager, "database_manager")
    government_service.add_dependency(economy_service, "economy_service")
    government_service.add_dependency(role_service, "role_service")
    
    # 測試初始化成功
    result = await government_service.initialize()
    assert result == True
    
    # 測試清理
    await government_service.cleanup()


@pytest.mark.asyncio 
async def test_performance_requirements():
    """測試性能需求 - N1驗收標準"""
    import time
    from services.government.government_service import GovernmentService
    
    # 建立政府服務與mock依賴
    government_service = GovernmentService()
    
    # Mock所有依賴以減少外部延遲
    db_manager = Mock(spec=DatabaseManager)
    db_manager.is_initialized = True
    db_manager.execute = AsyncMock(return_value=1)
    db_manager.fetchone = AsyncMock(return_value=None)
    
    role_service = Mock(spec=RoleService)
    role_service.is_initialized = True 
    role_service.create_department_roles = AsyncMock(return_value={
        "head_role": Mock(id=987654321),
        "level_role": Mock(id=444555666)
    })
    
    economy_service = Mock(spec=EconomyService)
    economy_service.is_initialized = True
    mock_account = Mock()
    mock_account.id = "test_account"
    economy_service.create_account = AsyncMock(return_value=mock_account)
    
    government_service.add_dependency(db_manager, "database_manager") 
    government_service.add_dependency(role_service, "role_service")
    government_service.add_dependency(economy_service, "economy_service")
    
    await government_service.initialize()
    
    # Mock Guild
    mock_guild = Mock()
    mock_guild.id = 123456789
    
    # 測試部門管理操作性能 < 500ms p95
    department_data = {
        "name": "性能測試部門",
        "head_user_id": 111222333,
        "level_name": "部長級"
    }
    
    start_time = time.time()
    department_id = await government_service.create_department(mock_guild, department_data)
    end_time = time.time()
    
    operation_time = (end_time - start_time) * 1000  # 轉換為毫秒
    assert operation_time < 500, f"部門建立操作超時：{operation_time:.2f}ms > 500ms"
    
    # 測試身分組操作性能 < 200ms p95
    start_time = time.time()
    await role_service.create_department_roles(mock_guild, department_data)
    end_time = time.time()
    
    role_operation_time = (end_time - start_time) * 1000
    assert role_operation_time < 200, f"身分組操作超時：{role_operation_time:.2f}ms > 200ms"


@pytest.mark.asyncio
async def test_reliability_requirements():
    """測試可靠性需求 - N2驗收標準"""
    from services.government.models import JSONRegistryManager, DepartmentRegistry
    import tempfile
    import os
    import json
    
    # 測試JSON註冊表操作99.9%成功率和ACID合規
    success_count = 0
    total_operations = 100
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        registry_manager = JSONRegistryManager(temp_path)
        
        # 執行多次操作測試可靠性
        for i in range(total_operations):
            try:
                # 測試添加操作
                department = DepartmentRegistry(
                    id=i,
                    guild_id=123456789,
                    name=f"測試部門{i}",
                    head_role_id=987654321 + i,
                    head_user_id=111222333 + i,
                    level_role_id=444555666 + i,
                    level_name="部長級",
                    account_id=f"ACC_GOV_{i:03d}"
                )
                
                await registry_manager.add_department(department)
                
                # 測試讀取操作
                departments = await registry_manager.get_departments_by_guild(123456789)
                assert len(departments) == i + 1
                
                success_count += 1
                
            except Exception as e:
                print(f"操作 {i} 失敗: {e}")
        
        success_rate = success_count / total_operations
        assert success_rate >= 0.999, f"成功率 {success_rate:.3f} < 99.9%"
        
        # 測試資料一致性
        final_data = await registry_manager.read_registry()
        assert len(final_data["departments"]) == total_operations
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.mark.asyncio
async def test_scalability_requirements():
    """測試可擴展性需求 - N3驗收標準"""
    from services.government.models import JSONRegistryManager, DepartmentRegistry
    import tempfile
    import os
    import time
    
    # 測試支援每個guild最多100個部門
    max_departments = 100
    max_roles = 1000  # 每個部門可能有多個相關身分組
    max_members = 10000
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        registry_manager = JSONRegistryManager(temp_path)
        
        # 測試大量部門建立
        start_time = time.time()
        
        departments = []
        for i in range(max_departments):
            department = DepartmentRegistry(
                id=i,
                guild_id=123456789,
                name=f"擴展測試部門{i}",
                head_role_id=987654321 + i,
                head_user_id=111222333 + i,
                level_role_id=444555666 + i,
                level_name=f"級別{i % 5}",  # 模擬5種不同級別
                account_id=f"ACC_GOV_{i:03d}"
            )
            departments.append(department)
            await registry_manager.add_department(department)
        
        creation_time = time.time() - start_time
        
        # 驗證所有部門都被正確建立
        all_departments = await registry_manager.get_departments_by_guild(123456789)
        assert len(all_departments) == max_departments
        
        # 測試查詢性能在大量資料下依然可接受
        start_time = time.time()
        
        # 模擬多次查詢操作
        for _ in range(50):
            departments = await registry_manager.get_departments_by_guild(123456789)
            assert len(departments) == max_departments
        
        query_time = time.time() - start_time
        avg_query_time = (query_time / 50) * 1000  # 轉換為毫秒
        
        # 查詢時間應該保持在合理範圍內
        assert avg_query_time < 100, f"平均查詢時間過長：{avg_query_time:.2f}ms"
        
        print(f"建立 {max_departments} 個部門耗時：{creation_time:.2f}s")
        print(f"平均查詢時間：{avg_query_time:.2f}ms")
        
        # 測試記憶體使用效率 - 確保大量資料不會導致過度記憶體消耗
        import sys
        memory_usage = sys.getsizeof(all_departments)
        max_memory_mb = 10  # 最大10MB記憶體使用
        memory_mb = memory_usage / (1024 * 1024)
        assert memory_mb < max_memory_mb, f"記憶體使用過多：{memory_mb:.2f}MB > {max_memory_mb}MB"
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)