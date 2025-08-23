"""
身分組管理服務
Task ID: 4 - 實作政府系統核心功能

這個模組提供Discord身分組管理功能，包括：
- 身分組建立和階層管理
- 常任理事身分組自動建立
- 部門身分組建立和配置
- 身分組權限和階層設定
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

import discord
from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError, ValidationError, handle_errors


class RoleService(BaseService):
    """
    身分組管理服務
    
    提供Discord身分組的建立、管理和階層設定功能
    """
    
    def __init__(self):
        super().__init__("RoleService")
        self.db_manager: Optional[DatabaseManager] = None
        self._role_cache: Dict[int, Dict[str, discord.Role]] = {}
        self._operation_lock = asyncio.Lock()
    
    async def _initialize(self) -> bool:
        """初始化身分組服務"""
        try:
            # 獲取資料庫管理器依賴
            self.db_manager = self.get_dependency("database_manager")
            if not self.db_manager or not self.db_manager.is_initialized:
                self.logger.error("資料庫管理器依賴不可用")
                return False
            
            self.logger.info("身分組管理服務初始化完成")
            return True
            
        except Exception as e:
            self.logger.exception(f"身分組管理服務初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理身分組服務資源"""
        self._role_cache.clear()
        self.db_manager = None
        self.logger.info("身分組管理服務已清理")
    
    async def has_permission(
        self,
        user_id: int,
        guild_id: int,
        permission: str
    ) -> bool:
        """
        檢查使用者是否具有指定權限
        
        參數：
            user_id: 使用者ID
            guild_id: 伺服器ID
            permission: 權限名稱
            
        返回：
            是否具有權限
        """
        try:
            # 獲取Discord客戶端
            discord_client = self.get_dependency("discord_client")
            if not discord_client:
                self.logger.error("無法獲取Discord客戶端進行權限檢查")
                return False
            
            guild = discord_client.get_guild(guild_id)
            if not guild:
                self.logger.warning(f"找不到伺服器 {guild_id}")
                return False
            
            member = guild.get_member(user_id)
            if not member:
                self.logger.warning(f"在伺服器 {guild_id} 中找不到用戶 {user_id}")
                return False
            
            # 檢查權限
            if permission == "administrator":
                return member.guild_permissions.administrator or member.id == guild.owner_id
            
            elif permission == "manage_achievements":
                # 成就管理權限：管理員、伺服器擁有者、或有管理身分組權限的使用者
                if member.guild_permissions.administrator or member.id == guild.owner_id:
                    return True
                if member.guild_permissions.manage_roles:
                    return True
                # 檢查是否有常任理事身分組
                council_role = discord.utils.get(guild.roles, name="常任理事")
                if council_role and council_role in member.roles:
                    return True
                return False
            
            elif permission == "manage_roles":
                return member.guild_permissions.manage_roles or member.guild_permissions.administrator or member.id == guild.owner_id
            
            elif permission == "manage_guild":
                return member.guild_permissions.manage_guild or member.guild_permissions.administrator or member.id == guild.owner_id
            
            else:
                # 未知權限，預設拒絕
                self.logger.warning(f"未知權限：{permission}")
                return False
                
        except Exception as e:
            self.logger.error(f"權限檢查時發生錯誤：{e}")
            return False
    
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
        # 身分組管理需要管理員權限
        role_management_actions = [
            "create_role", "delete_role", "modify_role",
            "assign_role", "remove_role", "manage_hierarchy"
        ]
        
        if action in role_management_actions:
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
                
                # 檢查是否有管理身分組權限
                if member.guild_permissions.manage_roles:
                    self.logger.debug(f"用戶 {user_id} 具有管理身分組權限")
                    return True
                
                # 檢查是否有常任理事身分組（常任理事可以管理身分組）
                council_role = discord.utils.get(guild.roles, name="常任理事")
                if council_role and council_role in member.roles:
                    self.logger.debug(f"用戶 {user_id} 具有常任理事身分組")
                    return True
                
                self.logger.warning(f"用戶 {user_id} 沒有執行 {action} 的權限")
                return False
                
            except Exception as e:
                self.logger.error(f"權限驗證時發生錯誤：{e}")
                return False
        
        # 非身分組管理操作允許所有用戶
        return True
    
    @handle_errors(log_errors=True)
    async def create_role_if_not_exists(
        self,
        guild: discord.Guild,
        name: str,
        **kwargs
    ) -> discord.Role:
        """
        建立身分組（如果不存在）
        
        參數：
            guild: Discord伺服器
            name: 身分組名稱
            **kwargs: 身分組配置參數
            
        返回：
            身分組物件
            
        拋出：
            ServiceError: 建立失敗時
        """
        async with self._operation_lock:
            try:
                # 檢查身分組是否已存在
                existing_role = discord.utils.get(guild.roles, name=name)
                if existing_role:
                    self.logger.debug(f"身分組 {name} 已存在，返回現有身分組")
                    return existing_role
                
                # 建立新身分組
                self.logger.info(f"在伺服器 {guild.name} 中建立身分組：{name}")
                
                # 設定預設權限
                permissions = kwargs.get('permissions', discord.Permissions.none())
                color = kwargs.get('color', discord.Color.default())
                mentionable = kwargs.get('mentionable', False)
                hoist = kwargs.get('hoist', True)
                
                role = await guild.create_role(
                    name=name,
                    permissions=permissions,
                    color=color,
                    mentionable=mentionable,
                    hoist=hoist,
                    reason=f"政府系統自動建立：{name}"
                )
                
                # 更新快取
                if guild.id not in self._role_cache:
                    self._role_cache[guild.id] = {}
                self._role_cache[guild.id][name] = role
                
                self.logger.info(f"身分組 {name} 建立成功，ID：{role.id}")
                return role
                
            except discord.HTTPException as e:
                raise ServiceError(
                    f"Discord API錯誤：{e}",
                    service_name=self.name,
                    operation="create_role",
                    details={"guild_id": guild.id, "role_name": name}
                )
            
            except Exception as e:
                raise ServiceError(
                    f"建立身分組失敗：{e}",
                    service_name=self.name,
                    operation="create_role",
                    details={"guild_id": guild.id, "role_name": name}
                )
    
    @handle_errors(log_errors=True)
    async def ensure_council_role(self, guild: discord.Guild) -> discord.Role:
        """
        確保常任理事身分組存在
        
        參數：
            guild: Discord伺服器
            
        返回：
            常任理事身分組
        """
        self.logger.info(f"確保伺服器 {guild.name} 的常任理事身分組存在")
        
        council_role = await self.create_role_if_not_exists(
            guild,
            "常任理事",
            permissions=discord.Permissions(
                administrator=True,
                manage_guild=True,
                manage_roles=True,
                manage_channels=True,
                manage_messages=True,
                mention_everyone=True
            ),
            color=discord.Color.gold(),
            hoist=True,
            mentionable=True
        )
        
        # 將常任理事身分組移動到高位置
        try:
            if council_role.position < len(guild.roles) - 5:  # 避免移動到最高位置
                await council_role.edit(position=len(guild.roles) - 2)
        except discord.HTTPException as e:
            self.logger.warning(f"無法調整常任理事身分組位置：{e}")
        
        return council_role
    
    @handle_errors(log_errors=True)
    async def create_department_roles(
        self,
        guild: discord.Guild,
        department_data: Dict[str, Any]
    ) -> Dict[str, discord.Role]:
        """
        建立部門相關身分組
        
        參數：
            guild: Discord伺服器
            department_data: 部門資料
            
        返回：
            包含部門身分組的字典
        """
        department_name = department_data.get("name", "")
        level_name = department_data.get("level_name", "")
        
        if not department_name:
            raise ValidationError("部門名稱不能為空")
        
        self.logger.info(f"為部門 {department_name} 建立身分組")
        
        roles = {}
        
        # 建立部門負責人身分組
        head_role_name = f"{department_name}部長"
        head_role = await self.create_role_if_not_exists(
            guild,
            head_role_name,
            permissions=discord.Permissions(
                manage_messages=True,
                manage_threads=True,
                moderate_members=True,
                manage_events=True
            ),
            color=discord.Color.blue(),
            hoist=True,
            mentionable=True
        )
        roles["head_role"] = head_role
        
        # 建立級別身分組（如果指定）
        if level_name:
            level_role = await self.create_role_if_not_exists(
                guild,
                level_name,
                permissions=discord.Permissions(
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    use_external_emojis=True
                ),
                color=self._get_level_color(level_name),
                hoist=True,
                mentionable=True
            )
            roles["level_role"] = level_role
        
        # 設定身分組階層
        await self._setup_department_hierarchy(guild, roles, department_data)
        
        return roles
    
    def _get_level_color(self, level_name: str) -> discord.Color:
        """
        根據級別名稱獲取身分組顏色
        
        參數：
            level_name: 級別名稱
            
        返回：
            Discord顏色
        """
        level_colors = {
            "部長級": discord.Color.dark_blue(),
            "副部長級": discord.Color.blue(),
            "司長級": discord.Color.green(),
            "副司長級": discord.Color.dark_green(),
            "科長級": discord.Color.orange(),
            "副科長級": discord.Color.dark_orange(),
            "科員級": discord.Color.light_grey()
        }
        
        return level_colors.get(level_name, discord.Color.default())
    
    async def _setup_department_hierarchy(
        self,
        guild: discord.Guild,
        roles: Dict[str, discord.Role],
        department_data: Dict[str, Any]
    ):
        """
        設定部門身分組階層
        
        參數：
            guild: Discord伺服器
            roles: 部門身分組字典
            department_data: 部門資料
        """
        try:
            # 獲取常任理事身分組作為參考
            council_role = discord.utils.get(guild.roles, name="常任理事")
            
            if council_role and "head_role" in roles:
                # 部門負責人身分組應該在常任理事之下
                target_position = max(1, council_role.position - 1)
                await roles["head_role"].edit(position=target_position)
            
            if "level_role" in roles and "head_role" in roles:
                # 級別身分組應該在部門負責人之下
                target_position = max(1, roles["head_role"].position - 1)
                await roles["level_role"].edit(position=target_position)
        
        except discord.HTTPException as e:
            self.logger.warning(f"設定身分組階層時發生錯誤：{e}")
    
    @handle_errors(log_errors=True)
    async def assign_role_to_user(
        self,
        guild: discord.Guild,
        user: discord.Member,
        role: discord.Role,
        reason: Optional[str] = None
    ) -> bool:
        """
        為使用者指派身分組
        
        參數：
            guild: Discord伺服器
            user: 使用者
            role: 身分組
            reason: 指派原因
            
        返回：
            是否成功
        """
        try:
            if role in user.roles:
                self.logger.debug(f"使用者 {user} 已擁有身分組 {role.name}")
                return True
            
            await user.add_roles(role, reason=reason or "政府系統自動指派")
            self.logger.info(f"為使用者 {user} 指派身分組 {role.name}")
            return True
            
        except discord.HTTPException as e:
            self.logger.error(f"指派身分組失敗：{e}")
            raise ServiceError(
                f"指派身分組失敗：{e}",
                service_name=self.name,
                operation="assign_role"
            )
    
    @handle_errors(log_errors=True)
    async def remove_role_from_user(
        self,
        guild: discord.Guild,
        user: discord.Member,
        role: discord.Role,
        reason: Optional[str] = None
    ) -> bool:
        """
        移除使用者的身分組
        
        參數：
            guild: Discord伺服器
            user: 使用者
            role: 身分組
            reason: 移除原因
            
        返回：
            是否成功
        """
        try:
            if role not in user.roles:
                self.logger.debug(f"使用者 {user} 沒有身分組 {role.name}")
                return True
            
            await user.remove_roles(role, reason=reason or "政府系統自動移除")
            self.logger.info(f"移除使用者 {user} 的身分組 {role.name}")
            return True
            
        except discord.HTTPException as e:
            self.logger.error(f"移除身分組失敗：{e}")
            raise ServiceError(
                f"移除身分組失敗：{e}",
                service_name=self.name,
                operation="remove_role"
            )
    
    @handle_errors(log_errors=True) 
    async def delete_role(
        self,
        guild: discord.Guild,
        role: discord.Role,
        reason: Optional[str] = None
    ) -> bool:
        """
        刪除身分組
        
        參數：
            guild: Discord伺服器
            role: 要刪除的身分組
            reason: 刪除原因
            
        返回：
            是否成功
        """
        try:
            await role.delete(reason=reason or "政府系統自動刪除")
            
            # 清理快取
            if guild.id in self._role_cache:
                for name, cached_role in list(self._role_cache[guild.id].items()):
                    if cached_role.id == role.id:
                        del self._role_cache[guild.id][name]
                        break
            
            self.logger.info(f"身分組 {role.name} 已刪除")
            return True
            
        except discord.HTTPException as e:
            self.logger.error(f"刪除身分組失敗：{e}")
            raise ServiceError(
                f"刪除身分組失敗：{e}",
                service_name=self.name,
                operation="delete_role"
            )
    
    async def get_role_by_name(
        self,
        guild: discord.Guild,
        name: str
    ) -> Optional[discord.Role]:
        """
        根據名稱獲取身分組
        
        參數：
            guild: Discord伺服器
            name: 身分組名稱
            
        返回：
            身分組物件或None
        """
        # 先查快取
        if guild.id in self._role_cache and name in self._role_cache[guild.id]:
            cached_role = self._role_cache[guild.id][name]
            # 驗證快取的身分組是否仍然存在
            if discord.utils.get(guild.roles, id=cached_role.id):
                return cached_role
            else:
                # 清理無效快取
                del self._role_cache[guild.id][name]
        
        # 從伺服器搜尋
        role = discord.utils.get(guild.roles, name=name)
        
        # 更新快取
        if role:
            if guild.id not in self._role_cache:
                self._role_cache[guild.id] = {}
            self._role_cache[guild.id][name] = role
        
        return role
    
    async def list_department_roles(
        self,
        guild: discord.Guild,
        department_name: str
    ) -> List[discord.Role]:
        """
        獲取部門相關的所有身分組
        
        參數：
            guild: Discord伺服器
            department_name: 部門名稱
            
        返回：
            部門身分組列表
        """
        department_roles = []
        
        # 搜尋相關身分組
        patterns = [
            f"{department_name}部長",
            f"{department_name}副部長",
            f"{department_name}司長",
            f"{department_name}科長"
        ]
        
        for pattern in patterns:
            role = await self.get_role_by_name(guild, pattern)
            if role:
                department_roles.append(role)
        
        return department_roles
    
    async def cleanup_department_roles(
        self,
        guild: discord.Guild,
        department_name: str
    ) -> bool:
        """
        清理部門相關身分組
        
        參數：
            guild: Discord伺服器
            department_name: 部門名稱
            
        返回：
            是否成功
        """
        try:
            department_roles = await self.list_department_roles(guild, department_name)
            
            for role in department_roles:
                await self.delete_role(
                    guild, 
                    role, 
                    reason=f"部門 {department_name} 已解散"
                )
            
            self.logger.info(f"部門 {department_name} 的所有身分組已清理")
            return True
            
        except Exception as e:
            self.logger.error(f"清理部門身分組失敗：{e}")
            return False