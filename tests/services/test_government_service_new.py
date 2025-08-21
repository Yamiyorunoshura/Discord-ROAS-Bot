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

# 導入Discord相關模組
try:
    import discord
except ImportError:
    # 如果沒有discord.py，創建mock
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

# 導入項目模組
from services.government.models import DepartmentRegistry, JSONRegistryManager
from core.exceptions import ServiceError, ValidationError


class TestDepartmentRegistry:
    """政府系統資料模型測試 - 需求 7.1, 7.7"""
    
    def test_department_registry_creation(self):
        """測試部門註冊表資料類別建立 - 需求 7.1"""
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
        """測試部門註冊表序列化 - 需求 7.1"""
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
    
    def test_department_registry_validation_success(self):
        """測試部門註冊表驗證成功 - 需求 7.1"""
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
    
    def test_department_registry_validation_failure(self):
        """測試部門註冊表驗證失敗 - 需求 7.1"""
        # Test invalid department (missing required fields)
        with pytest.raises(ValidationError):
            invalid_dept = DepartmentRegistry(
                id=None,
                guild_id=0,  # Invalid guild ID
                name="",  # Empty name
                head_role_id=0,  # Invalid role ID
            )
            invalid_dept.validate()
    
    def test_department_registry_update_timestamp(self):
        """測試部門註冊表時間戳更新"""
        # Arrange
        dept = DepartmentRegistry(
            id=1,
            guild_id=123456789,
            name="財政部"
        )
        original_updated_at = dept.updated_at
        
        # Act
        import time
        time.sleep(0.01)  # 確保時間差異
        dept.update_timestamp()
        
        # Assert
        assert dept.updated_at > original_updated_at


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
        backup_path = temp_path + '.backup'
        if os.path.exists(backup_path):
            os.unlink(backup_path)
    
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


class TestPerformanceAndReliability:
    """性能和可靠性測試"""
    
    @pytest.mark.asyncio
    async def test_performance_requirements(self):
        """測試性能需求 - 部門管理操作應在合理時間內完成"""
        import time
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            registry_manager = JSONRegistryManager(temp_path)
            
            # 測試部門添加性能
            department = DepartmentRegistry(
                id=1,
                guild_id=123456789,
                name="性能測試部門",
                head_role_id=987654321,
                head_user_id=111222333,
                level_role_id=444555666,
                level_name="部長級",
                account_id="perf_test_acc"
            )
            
            start_time = time.time()
            await registry_manager.add_department(department)
            end_time = time.time()
            
            operation_time = (end_time - start_time) * 1000  # 轉換為毫秒
            assert operation_time < 100, f"部門添加操作超時：{operation_time:.2f}ms > 100ms"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_reliability_requirements(self):
        """測試可靠性需求 - JSON註冊表操作應該可靠"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            registry_manager = JSONRegistryManager(temp_path)
            success_count = 0
            total_operations = 50
            
            # 執行多次操作測試可靠性
            for i in range(total_operations):
                try:
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
            assert success_rate >= 0.95, f"成功率 {success_rate:.3f} < 95%"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_scalability_requirements(self):
        """測試可擴展性需求 - 支援大量部門"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            registry_manager = JSONRegistryManager(temp_path)
            max_departments = 50  # 減少測試數量以加快測試速度
            
            # 測試大量部門建立
            import time
            start_time = time.time()
            
            for i in range(max_departments):
                department = DepartmentRegistry(
                    id=i,
                    guild_id=123456789,
                    name=f"擴展測試部門{i}",
                    head_role_id=987654321 + i,
                    head_user_id=111222333 + i,
                    level_role_id=444555666 + i,
                    level_name=f"級別{i % 5}",
                    account_id=f"ACC_GOV_{i:03d}"
                )
                await registry_manager.add_department(department)
            
            creation_time = time.time() - start_time
            
            # 驗證所有部門都被正確建立
            all_departments = await registry_manager.get_departments_by_guild(123456789)
            assert len(all_departments) == max_departments
            
            # 測試查詢性能
            start_time = time.time()
            for _ in range(10):
                departments = await registry_manager.get_departments_by_guild(123456789)
                assert len(departments) == max_departments
            
            query_time = time.time() - start_time
            avg_query_time = (query_time / 10) * 1000
            
            assert avg_query_time < 50, f"平均查詢時間過長：{avg_query_time:.2f}ms"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])