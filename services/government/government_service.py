"""
政府服務核心邏輯
Task ID: 4 - 實作政府系統核心功能

這個模組提供政府系統的核心業務邏輯，包括：
- 部門管理：建立、更新、刪除部門
- 與身分組管理服務整合
- 與經濟系統整合以支援部門帳戶
- 部門註冊表CRUD操作
- 常任理事會權限驗證
"""

import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

import discord
from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError, ValidationError, handle_errors
from services.economy.economy_service import EconomyService
from services.economy.models import AccountType
from .models import DepartmentRegistry, JSONRegistryManager, get_migration_scripts
from .role_service import RoleService


class GovernmentService(BaseService):
    """
    政府系統核心服務
    
    提供完整的政府部門管理功能，整合身分組管理和經濟系統
    """
    
    def __init__(self, registry_file: Optional[str] = None):
        super().__init__("GovernmentService")
        
        # 服務依賴
        self.db_manager: Optional[DatabaseManager] = None
        self.role_service: Optional[RoleService] = None
        self.economy_service: Optional[EconomyService] = None
        
        # JSON註冊表管理器
        # 防禦：避免外部錯誤傳入非路徑物件（例如 DatabaseManager）
        if registry_file is not None and not isinstance(registry_file, (str, Path)):
            self.logger.warning(
                f"收到無效的 registry_file 參數（{type(registry_file).__name__}），改用預設路徑"
            )
            self._registry_file = "data/government_registry.json"
        else:
            self._registry_file = registry_file or "data/government_registry.json"
        self._registry_manager: Optional[JSONRegistryManager] = None
        
        # 併發控制
        self._operation_lock = asyncio.Lock()
        
        # 快取
        self._department_cache: Dict[int, List[DepartmentRegistry]] = {}
        self._cache_timeout = 300  # 5分鐘快取過期
    
    async def _initialize(self) -> bool:
        """初始化政府服務"""
        try:
            # 獲取依賴服務
            self.db_manager = self.get_dependency("database_manager")
            if not self.db_manager or not self.db_manager.is_initialized:
                self.logger.error("資料庫管理器依賴不可用")
                return False
            
            self.role_service = self.get_dependency("role_service")
            if not self.role_service or not self.role_service.is_initialized:
                self.logger.error("身分組服務依賴不可用")
                return False
            
            self.economy_service = self.get_dependency("economy_service")
            if not self.economy_service or not self.economy_service.is_initialized:
                self.logger.error("經濟服務依賴不可用")
                return False
            
            # 初始化JSON註冊表管理器（再度防禦型檢查，避免屬性被意外覆蓋）
            registry_path: Union[str, Path]
            if isinstance(self._registry_file, (str, Path)):
                registry_path = self._registry_file
            else:
                self.logger.warning(
                    f"_registry_file 非字串/路徑型別（{type(self._registry_file).__name__}），改用預設路徑"
                )
                registry_path = "data/government_registry.json"
            self._registry_manager = JSONRegistryManager(registry_path)
            
            # 註冊資料庫遷移
            await self._register_migrations()
            
            # 應用遷移
            migration_result = await self.db_manager.migration_manager.apply_migrations()
            if not migration_result:
                self.logger.error("政府系統遷移應用失敗")
                return False
            
            # 確保JSON註冊表檔案存在
            await self._registry_manager.read_registry()
            
            self.logger.info("政府系統服務初始化完成")
            return True
            
        except Exception as e:
            self.logger.exception(f"政府系統服務初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理政府服務資源"""
        self._department_cache.clear()
        self.db_manager = None
        self.role_service = None
        self.economy_service = None
        self._registry_manager = None
        self.logger.info("政府系統服務已清理")
    
    async def _validate_permissions(
        self,
        user_id: int,
        guild_id: Optional[int],
        action: str
    ) -> bool:
        """
        驗證使用者權限
        
        參數：
            user_id: 使用者ID
            guild_id: 伺服器ID
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        # 政府管理操作需要常任理事或管理員權限
        government_actions = [
            "create_department", "update_department", "delete_department",
            "manage_department_roles", "assign_department_head"
        ]
        
        if action in government_actions:
            # 實際權限檢查邏輯 - Task ID: 4
            if not guild_id:
                self.logger.warning(f"權限驗證失敗：缺少伺服器ID，用戶：{user_id}，動作：{action}")
                return False
            
            try:
                # 從依賴服務獲取Discord bot客戶端
                discord_client = self.get_dependency("discord_client")
                if not discord_client:
                    self.logger.error("無法獲取Discord客戶端進行權限驗證")
                    return False
                
                guild = discord_client.get_guild(guild_id)
                if not guild:
                    self.logger.warning(f"找不到伺服器 {guild_id}")
                    return False
                
                member = guild.get_member(user_id)
                if not member:
                    self.logger.warning(f"在伺服器 {guild_id} 中找不到用戶 {user_id}")
                    return False
                
                # 檢查是否為伺服器管理員
                if member.guild_permissions.administrator:
                    self.logger.debug(f"用戶 {user_id} 具有管理員權限")
                    return True
                
                # 檢查是否為伺服器所有者
                if member.id == guild.owner_id:
                    self.logger.debug(f"用戶 {user_id} 是伺服器所有者")
                    return True
                
                # 檢查是否有常任理事身分組
                council_role = discord.utils.get(guild.roles, name="常任理事")
                if council_role and council_role in member.roles:
                    self.logger.debug(f"用戶 {user_id} 具有常任理事身分組")
                    return True
                
                # 對於部門特定操作，檢查是否為該部門負責人
                if action in ["update_department", "delete_department"]:
                    # 這需要額外的部門ID參數，目前先通過常規權限檢查
                    pass
                
                self.logger.warning(f"用戶 {user_id} 沒有執行 {action} 的權限")
                return False
                
            except Exception as e:
                self.logger.error(f"權限驗證時發生錯誤：{e}")
                return False
        
        # 非政府管理操作允許所有用戶
        return True
    
    async def validate_permissions(
        self,
        user_id: int,
        guild_id: Optional[int],
        action: str
    ) -> bool:
        """
        公共權限驗證方法
        
        這是BasePanel期望的公共接口，用於政府系統權限驗證
        
        參數：
            user_id: 使用者ID
            guild_id: 伺服器ID
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        return await self._validate_permissions(user_id, guild_id, action)
    
    async def _register_migrations(self):
        """註冊政府系統資料庫遷移"""
        try:
            migrations = get_migration_scripts()
            for migration in migrations:
                self.db_manager.migration_manager.add_migration(
                    version=migration["version"],
                    description=migration["description"],
                    up_sql=migration["sql"],
                    down_sql=""  # 簡化版本，不提供回滾
                )
            
            self.logger.info("政府系統資料庫遷移已註冊")
            
        except Exception as e:
            self.logger.error(f"註冊政府系統遷移失敗：{e}")
            raise
    
    @handle_errors(log_errors=True)
    async def create_department(
        self,
        guild: discord.Guild,
        department_data: Dict[str, Any]
    ) -> int:
        """
        建立新部門
        
        參數：
            guild: Discord伺服器
            department_data: 部門資料
            
        返回：
            部門ID
            
        拋出：
            ServiceError: 建立失敗時
            ValidationError: 資料無效時
        """
        async with self._operation_lock:
            try:
                # 驗證部門資料
                if not department_data.get("name"):
                    raise ValidationError("部門名稱不能為空")
                
                department_name = department_data["name"].strip()
                head_user_id = department_data.get("head_user_id")
                level_name = department_data.get("level_name", "")
                
                self.logger.info(f"開始建立部門：{department_name}")
                
                # 檢查部門是否已存在
                existing_dept = await self._get_department_by_name(guild.id, department_name)
                if existing_dept:
                    raise ServiceError(
                        f"部門 {department_name} 已存在",
                        service_name=self.name,
                        operation="create_department"
                    )
                
                # 1. 建立部門身分組
                role_data = {
                    "name": department_name,
                    "level_name": level_name,
                    "head_user_id": head_user_id
                }
                
                roles = await self.role_service.create_department_roles(guild, role_data)
                
                # 2. 建立部門帳戶
                account = await self.economy_service.create_account(
                    guild_id=guild.id,
                    account_type=AccountType.GOVERNMENT_DEPARTMENT,
                    user_id=None,  # 政府帳戶不需要user_id
                    initial_balance=0.0
                )
                account_id = account.id
                
                # 3. 將資料寫入資料庫
                insert_sql = """
                    INSERT INTO government_departments 
                    (guild_id, name, head_role_id, head_user_id, level_role_id, level_name, account_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                now = datetime.now()
                params = (
                    guild.id,
                    department_name,
                    roles.get("head_role").id if roles.get("head_role") else None,
                    head_user_id,
                    roles.get("level_role").id if roles.get("level_role") else None,
                    level_name,
                    account_id,
                    now,
                    now
                )
                
                department_id = await self.db_manager.execute(insert_sql, params)
                
                # 4. 建立部門註冊表記錄
                department_registry = DepartmentRegistry(
                    id=department_id,
                    guild_id=guild.id,
                    name=department_name,
                    head_role_id=roles.get("head_role").id if roles.get("head_role") else None,
                    head_user_id=head_user_id,
                    level_role_id=roles.get("level_role").id if roles.get("level_role") else None,
                    level_name=level_name,
                    account_id=account_id,
                    created_at=now,
                    updated_at=now
                )
                
                await self._registry_manager.add_department(department_registry)
                
                # 5. 指派部門負責人身分組
                if head_user_id and roles.get("head_role"):
                    try:
                        member = guild.get_member(head_user_id)
                        if member:
                            await self.role_service.assign_role_to_user(
                                guild, member, roles["head_role"],
                                reason=f"指派為 {department_name} 部門負責人"
                            )
                    except Exception as e:
                        self.logger.warning(f"指派部門負責人身分組失敗：{e}")
                
                # 清理快取
                if guild.id in self._department_cache:
                    del self._department_cache[guild.id]
                
                self.logger.info(f"部門 {department_name} 建立成功，ID：{department_id}")
                return department_id
                
            except (ValidationError, ServiceError):
                raise
            
            except Exception as e:
                self.logger.exception(f"建立部門時發生錯誤")
                raise ServiceError(
                    f"建立部門失敗：{e}",
                    service_name=self.name,
                    operation="create_department"
                )
    
    @handle_errors(log_errors=True)
    async def update_department(
        self,
        department_id: int,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新部門資訊
        
        參數：
            department_id: 部門ID
            updates: 要更新的欄位
            
        返回：
            是否成功
        """
        async with self._operation_lock:
            try:
                # 獲取現有部門資料
                department = await self._get_department_by_id(department_id)
                if not department:
                    raise ServiceError(
                        f"找不到ID為 {department_id} 的部門",
                        service_name=self.name,
                        operation="update_department"
                    )
                
                # 建立更新SQL
                update_fields = []
                params = []
                
                for field, value in updates.items():
                    if field in ["name", "head_user_id", "level_name"]:
                        update_fields.append(f"{field} = ?")
                        params.append(value)
                
                if not update_fields:
                    return True  # 沒有要更新的欄位
                
                update_fields.append("updated_at = ?")
                params.append(datetime.now())
                params.append(department_id)
                
                update_sql = f"""
                    UPDATE government_departments 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """
                
                result = await self.db_manager.execute(update_sql, params)
                
                # 更新JSON註冊表
                await self._registry_manager.update_department(department_id, updates)
                
                # 清理快取
                if department["guild_id"] in self._department_cache:
                    del self._department_cache[department["guild_id"]]
                
                self.logger.info(f"部門 {department_id} 更新成功")
                return result
                
            except ServiceError:
                raise
            
            except Exception as e:
                self.logger.exception(f"更新部門時發生錯誤")
                raise ServiceError(
                    f"更新部門失敗：{e}",
                    service_name=self.name,
                    operation="update_department"
                )
    
    @handle_errors(log_errors=True)
    async def delete_department(
        self,
        guild: discord.Guild,
        department_id: int
    ) -> bool:
        """
        刪除部門
        
        參數：
            guild: Discord伺服器
            department_id: 部門ID
            
        返回：
            是否成功
        """
        async with self._operation_lock:
            try:
                # 獲取部門資料
                department = await self._get_department_by_id(department_id)
                if not department:
                    raise ServiceError(
                        f"找不到ID為 {department_id} 的部門",
                        service_name=self.name,
                        operation="delete_department"
                    )
                
                department_name = department["name"]
                account_id = department.get("account_id")
                
                self.logger.info(f"開始刪除部門：{department_name}")
                
                # 1. 清理部門身分組
                try:
                    await self.role_service.cleanup_department_roles(guild, department_name)
                except Exception as e:
                    self.logger.warning(f"清理部門身分組時發生錯誤：{e}")
                
                # 2. 刪除部門帳戶（如果存在）
                if account_id:
                    try:
                        account = await self.economy_service.get_account(account_id)
                        if account:
                            # 將餘額轉回理事會帳戶
                            if account.balance > 0:
                                council_account_id = f"gov_council_{guild.id}"
                                council_account = await self.economy_service.get_account(council_account_id)
                                if council_account:
                                    await self.economy_service.transfer(
                                        from_account_id=account_id,
                                        to_account_id=council_account_id,
                                        amount=account.balance,
                                        reason=f"部門{department_name}解散，餘額歸還理事會"
                                    )
                            
                            # 停用帳戶（而非刪除）
                            # 注意：EconomyService可能沒有delete_account方法，所以我們先將餘額轉移
                            
                    except Exception as e:
                        self.logger.warning(f"處理部門帳戶時發生錯誤：{e}")
                
                # 3. 從資料庫刪除
                delete_sql = "DELETE FROM government_departments WHERE id = ?"
                await self.db_manager.execute(delete_sql, (department_id,))
                
                # 4. 從JSON註冊表移除
                await self._registry_manager.remove_department(department_id)
                
                # 清理快取
                if department["guild_id"] in self._department_cache:
                    del self._department_cache[department["guild_id"]]
                
                self.logger.info(f"部門 {department_name} 刪除成功")
                return True
                
            except ServiceError:
                raise
            
            except Exception as e:
                self.logger.exception(f"刪除部門時發生錯誤")
                raise ServiceError(
                    f"刪除部門失敗：{e}",
                    service_name=self.name,
                    operation="delete_department"
                )
    
    async def get_department_registry(self, guild_id: int) -> List[Dict[str, Any]]:
        """
        獲取伺服器的部門註冊表
        
        參數：
            guild_id: 伺服器ID
            
        返回：
            部門列表
        """
        try:
            # 先檢查快取
            if guild_id in self._department_cache:
                cached_data = self._department_cache[guild_id]
                if cached_data:  # 簡化的快取驗證，實際應該檢查時間戳
                    return [dept.to_dict() for dept in cached_data]
            
            # 從JSON註冊表讀取
            departments = await self._registry_manager.get_departments_by_guild(guild_id)
            
            # 更新快取
            self._department_cache[guild_id] = departments
            
            return [dept.to_dict() for dept in departments]
            
        except Exception as e:
            self.logger.error(f"獲取部門註冊表失敗：{e}")
            return []
    
    async def get_department_by_id(self, department_id: int) -> Optional[Dict[str, Any]]:
        """
        根據ID獲取部門資訊
        
        參數：
            department_id: 部門ID
            
        返回：
            部門資訊或None
        """
        department = await self._get_department_by_id(department_id)
        return department
    
    async def _get_department_by_id(self, department_id: int) -> Optional[Dict[str, Any]]:
        """內部方法：根據ID獲取部門資訊"""
        try:
            select_sql = "SELECT * FROM government_departments WHERE id = ?"
            result = await self.db_manager.fetchone(select_sql, (department_id,))
            return dict(result) if result else None
            
        except Exception as e:
            self.logger.error(f"查詢部門資料失敗：{e}")
            return None
    
    async def _get_department_by_name(
        self, 
        guild_id: int, 
        name: str
    ) -> Optional[Dict[str, Any]]:
        """內部方法：根據名稱獲取部門資訊"""
        try:
            select_sql = "SELECT * FROM government_departments WHERE guild_id = ? AND name = ?"
            result = await self.db_manager.fetchone(select_sql, (guild_id, name))
            return dict(result) if result else None
            
        except Exception as e:
            self.logger.error(f"查詢部門資料失敗：{e}")
            return None
    
    async def ensure_council_infrastructure(self, guild: discord.Guild) -> bool:
        """
        確保常任理事會基礎設施存在
        
        參數：
            guild: Discord伺服器
            
        返回：
            是否成功
        """
        try:
            # 確保常任理事身分組存在
            council_role = await self.role_service.ensure_council_role(guild)
            
            # 確保理事會帳戶存在
            try:
                council_account_id = f"gov_council_{guild.id}"
                council_account = await self.economy_service.get_account(council_account_id)
                
                if not council_account:
                    council_account = await self.economy_service.create_account(
                        guild_id=guild.id,
                        account_type=AccountType.GOVERNMENT_COUNCIL,
                        user_id=None,
                        initial_balance=1000000.0  # 理事會初始資金
                    )
            
            except Exception as e:
                self.logger.warning(f"建立理事會帳戶時發生錯誤：{e}")
            
            self.logger.info(f"伺服器 {guild.name} 的常任理事會基礎設施已確保")
            return True
            
        except Exception as e:
            self.logger.error(f"確保常任理事會基礎設施失敗：{e}")
            return False