"""
政府系統資料模型
Task ID: 4 - 實作政府系統核心功能

這個模組定義了政府系統的資料模型，包括：
- DepartmentRegistry：部門註冊表資料類別
- JSON註冊表的讀寫機制
- 資料驗證和序列化功能
- 資料庫表格結構定義
"""

import json
import asyncio
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from core.exceptions import ValidationError, ServiceError


@dataclass
class DepartmentRegistry:
    """
    部門註冊表資料類別
    
    包含政府部門的完整資訊，支援資料庫存儲和JSON序列化
    """
    id: Optional[int] = None
    guild_id: int = 0
    name: str = ""
    head_role_id: Optional[int] = None
    head_user_id: Optional[int] = None
    level_role_id: Optional[int] = None
    level_name: str = ""
    account_id: Optional[str] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """初始化後處理"""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DepartmentRegistry":
        """
        從字典建立部門註冊表實例
        
        參數：
            data: 包含部門資訊的字典
            
        返回：
            DepartmentRegistry實例
        """
        # 處理datetime字段
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        轉換為字典格式
        
        返回：
            包含部門資訊的字典
        """
        data = asdict(self)
        
        # 處理datetime字段序列化
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            data["updated_at"] = self.updated_at.isoformat()
        
        return data
    
    def validate(self) -> bool:
        """
        驗證部門資料有效性
        
        返回：
            是否有效
            
        拋出：
            ValidationError: 當資料無效時
        """
        errors = []
        
        # 檢查必要欄位
        if not self.guild_id or self.guild_id <= 0:
            errors.append("guild_id必須為正整數")
        
        if not self.name or not self.name.strip():
            errors.append("部門名稱不能為空")
        
        if len(self.name) > 100:
            errors.append("部門名稱不能超過100個字符")
        
        if self.level_name and len(self.level_name) > 50:
            errors.append("級別名稱不能超過50個字符")
        
        # 檢查ID欄位
        if self.head_role_id is not None and self.head_role_id <= 0:
            errors.append("head_role_id必須為正整數")
        
        if self.head_user_id is not None and self.head_user_id <= 0:
            errors.append("head_user_id必須為正整數")
        
        if self.level_role_id is not None and self.level_role_id <= 0:
            errors.append("level_role_id必須為正整數")
        
        if errors:
            raise ValidationError(
                message=f"部門資料驗證失敗：{'; '.join(errors)}",
                field="department_data",
                value=str(self.__dict__),
                expected="有效的部門資料"
            )
        
        return True
    
    def update_timestamp(self):
        """更新時間戳"""
        self.updated_at = datetime.now()


class JSONRegistryManager:
    """
    JSON註冊表管理器
    
    提供原子性的JSON檔案讀寫操作，支援併發控制和錯誤恢復
    """
    
    def __init__(self, file_path: Union[str, Path]):
        """
        初始化管理器
        
        參數：
            file_path: JSON檔案路徑
        """
        self.file_path = Path(file_path)
        self.backup_path = self.file_path.with_suffix('.json.backup')
        self._lock = asyncio.Lock()
    
    async def read_registry(self) -> Dict[str, Any]:
        """
        讀取註冊表
        
        返回：
            註冊表資料
            
        拋出：
            ServiceError: 讀取失敗時
        """
        async with self._lock:
            try:
                if not self.file_path.exists() or self.file_path.stat().st_size == 0:
                    # 建立初始檔案
                    initial_data = {
                        "departments": [],
                        "metadata": {
                            "version": "1.0",
                            "created_at": datetime.now().isoformat(),
                            "last_updated": datetime.now().isoformat()
                        }
                    }
                    await self._write_file_sync(self.file_path, initial_data)
                    return initial_data
                
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        # 空文件，返回初始資料
                        initial_data = {
                            "departments": [],
                            "metadata": {
                                "version": "1.0",
                                "created_at": datetime.now().isoformat(),
                                "last_updated": datetime.now().isoformat()
                            }
                        }
                        await self._write_file_sync(self.file_path, initial_data)
                        return initial_data
                    return json.loads(content)
                    
            except json.JSONDecodeError as e:
                # 嘗試從備份恢復
                if self.backup_path.exists():
                    try:
                        with open(self.backup_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            data = json.loads(content)
                        
                        # 恢復主檔案
                        await self._write_file(self.file_path, data)
                        return data
                        
                    except Exception:
                        pass
                
                raise ServiceError(
                    f"JSON註冊表讀取失敗：{e}",
                    service_name="JSONRegistryManager",
                    operation="read"
                )
            
            except Exception as e:
                raise ServiceError(
                    f"讀取註冊表時發生錯誤：{e}",
                    service_name="JSONRegistryManager",
                    operation="read"
                )
    
    async def write_registry(self, data: Dict[str, Any]) -> bool:
        """
        寫入註冊表（原子性操作）
        
        參數：
            data: 要寫入的資料
            
        返回：
            是否成功
            
        拋出：
            ServiceError: 寫入失敗時
        """
        async with self._lock:
            try:
                # 更新元資料
                if "metadata" not in data:
                    data["metadata"] = {}
                
                data["metadata"]["last_updated"] = datetime.now().isoformat()
                
                # 建立備份
                if self.file_path.exists():
                    try:
                        current_data = await self.read_registry()
                        await self._write_file(self.backup_path, current_data)
                    except Exception:
                        pass  # 備份失敗不應阻止主要操作
                
                # 原子性寫入
                await self._write_file(self.file_path, data)
                return True
                
            except Exception as e:
                raise ServiceError(
                    f"寫入註冊表時發生錯誤：{e}",
                    service_name="JSONRegistryManager",
                    operation="write"
                )
    
    async def add_department(self, department: DepartmentRegistry) -> bool:
        """
        添加部門到註冊表
        
        參數：
            department: 部門資料
            
        返回：
            是否成功
        """
        department.validate()
        
        # 先讀取資料，然後在鎖內進行檢查和寫入
        async with self._lock:
            # 重新讀取以確保最新資料
            if not self.file_path.exists() or self.file_path.stat().st_size == 0:
                data = {
                    "departments": [],
                    "metadata": {
                        "version": "1.0",
                        "created_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat()
                    }
                }
            else:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        data = {
                            "departments": [],
                            "metadata": {
                                "version": "1.0",
                                "created_at": datetime.now().isoformat(),
                                "last_updated": datetime.now().isoformat()
                            }
                        }
                    else:
                        data = json.loads(content)
            
            # 檢查部門是否已存在
            for existing_dept in data.get("departments", []):
                if (existing_dept.get("guild_id") == department.guild_id and 
                    existing_dept.get("name") == department.name):
                    raise ServiceError(
                        f"部門 {department.name} 在伺服器 {department.guild_id} 中已存在",
                        service_name="JSONRegistryManager",
                        operation="add_department"
                    )
            
            data.setdefault("departments", []).append(department.to_dict())
            return await self._write_file_sync(self.file_path, data)
    
    async def update_department(self, department_id: int, updates: Dict[str, Any]) -> bool:
        """
        更新部門資訊
        
        參數：
            department_id: 部門ID
            updates: 要更新的欄位
            
        返回：
            是否成功
        """
        data = await self.read_registry()
        
        for dept_data in data.get("departments", []):
            if dept_data.get("id") == department_id:
                dept_data.update(updates)
                dept_data["updated_at"] = datetime.now().isoformat()
                return await self.write_registry(data)
        
        raise ServiceError(
            f"找不到ID為 {department_id} 的部門",
            service_name="JSONRegistryManager",
            operation="update_department"
        )
    
    async def remove_department(self, department_id: int) -> bool:
        """
        從註冊表移除部門
        
        參數：
            department_id: 部門ID
            
        返回：
            是否成功
        """
        data = await self.read_registry()
        
        departments = data.get("departments", [])
        original_count = len(departments)
        
        data["departments"] = [
            dept for dept in departments 
            if dept.get("id") != department_id
        ]
        
        if len(data["departments"]) == original_count:
            raise ServiceError(
                f"找不到ID為 {department_id} 的部門",
                service_name="JSONRegistryManager",
                operation="remove_department"
            )
        
        return await self.write_registry(data)
    
    async def get_departments_by_guild(self, guild_id: int) -> List[DepartmentRegistry]:
        """
        獲取指定伺服器的所有部門
        
        參數：
            guild_id: 伺服器ID
            
        返回：
            部門列表
        """
        data = await self.read_registry()
        
        departments = []
        for dept_data in data.get("departments", []):
            if dept_data.get("guild_id") == guild_id:
                departments.append(DepartmentRegistry.from_dict(dept_data))
        
        return departments
    
    async def _write_file_sync(self, file_path: Path, data: Dict[str, Any]) -> bool:
        """
        同步寫入檔案（在鎖內使用）
        
        參數：
            file_path: 檔案路徑
            data: 要寫入的資料
            
        返回：
            是否成功
        """
        temp_path = file_path.with_suffix('.tmp')
        
        try:
            # 確保目錄存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 更新元資料
            if "metadata" not in data:
                data["metadata"] = {}
            data["metadata"]["last_updated"] = datetime.now().isoformat()
            
            # 寫入臨時檔案
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 原子性移動
            temp_path.replace(file_path)
            return True
            
        except Exception as e:
            # 清理臨時檔案
            if temp_path.exists():
                temp_path.unlink()
            raise ServiceError(
                f"寫入註冊表時發生錯誤：{e}",
                service_name="JSONRegistryManager",
                operation="write"
            )


# 資料庫表格結構定義
DATABASE_SCHEMA = {
    "government_departments": """
        CREATE TABLE IF NOT EXISTS government_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            head_role_id INTEGER,
            head_user_id INTEGER,
            level_role_id INTEGER,
            level_name TEXT,
            account_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES economy_accounts(account_id),
            UNIQUE(guild_id, name)
        )
    """,
    
    "government_departments_indexes": [
        "CREATE INDEX IF NOT EXISTS idx_gov_dept_guild_id ON government_departments(guild_id)",
        "CREATE INDEX IF NOT EXISTS idx_gov_dept_name ON government_departments(guild_id, name)",
        "CREATE INDEX IF NOT EXISTS idx_gov_dept_head_role ON government_departments(head_role_id)",
        "CREATE INDEX IF NOT EXISTS idx_gov_dept_account ON government_departments(account_id)"
    ]
}


def get_migration_scripts() -> List[Dict[str, Any]]:
    """
    獲取政府系統資料庫遷移腳本
    
    返回：
        遷移腳本列表
    """
    return [
        {
            "version": "003",
            "name": "create_government_tables",
            "description": "建立政府系統相關表格",
            "sql": DATABASE_SCHEMA["government_departments"]
        },
        {
            "version": "004", 
            "name": "add_government_indexes",
            "description": "添加政府系統索引以優化查詢性能",
            "sql": ";\n".join(DATABASE_SCHEMA["government_departments_indexes"])
        }
    ]