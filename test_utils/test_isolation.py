"""
測試隔離工具
提供測試環境的完整隔離，包括資料庫和服務狀態
"""

import os
import tempfile
import shutil
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from core.service_startup_manager import get_startup_manager, reset_global_startup_manager
from core.database_manager import get_database_manager


class TestEnvironmentManager:
    """測試環境管理器，提供完整的測試隔離"""
    
    def __init__(self):
        self.temp_dir = None
        self.db_path = None
        self.original_env = {}
        self.startup_manager = None
        
    async def setup(self) -> Dict[str, Any]:
        """設置隔離的測試環境"""
        # 創建臨時目錄
        self.temp_dir = tempfile.mkdtemp(prefix="test_roas_")
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        # 保存原始環境變數
        self.original_env["DATABASE_PATH"] = os.environ.get("DATABASE_PATH")
        
        # 設置測試環境變數
        os.environ["DATABASE_PATH"] = self.db_path
        
        # 重置全局狀態
        await reset_global_startup_manager()
        
        # 初始化服務
        self.startup_manager = await get_startup_manager()
        
        # 手動確保遷移執行
        await self._ensure_migrations_applied()
        
        success = await self.startup_manager.initialize_all_services()
        
        if not success:
            raise RuntimeError("測試環境初始化失敗")
        
        # 清理所有服務的快取狀態
        await self._reset_service_caches()
        
        return {
            "startup_manager": self.startup_manager,
            "db_path": self.db_path,
            "temp_dir": self.temp_dir
        }
    
    async def _ensure_migrations_applied(self):
        """確保所有遷移都已應用"""
        try:
            # 獲取資料庫管理器
            db_manager = await get_database_manager()
            
            # 手動執行遷移
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            migration_files = [
                "001_create_economy_tables.sql",
                "002_create_core_system_tables.sql", 
                "003_create_government_tables.sql",
                "004_create_achievement_tables.sql"
            ]
            
            for migration_file in migration_files:
                migration_path = os.path.join(project_root, "scripts", "migrations", migration_file)
                if os.path.exists(migration_path):
                    with open(migration_path, 'r', encoding='utf-8') as f:
                        migration_sql = f.read()
                    
                    # 分割並執行SQL語句
                    statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
                    for statement in statements:
                        try:
                            await db_manager.execute(statement)
                        except Exception as e:
                            # 忽略已存在的錯誤
                            if "already exists" not in str(e).lower():
                                print(f"執行遷移語句失敗: {statement[:100]}... - {e}")
                    
                    print(f"已應用遷移: {migration_file}")
                
        except Exception as e:
            print(f"應用遷移失敗: {e}")
            # 不拋出異常，讓初始化繼續
    
    async def _reset_service_caches(self):
        """重置所有服務的快取狀態"""
        try:
            # 重置成就服務快取
            achievement_service = self.startup_manager.service_instances.get("AchievementService")
            if achievement_service:
                achievement_service._active_achievements_cache.clear()
                achievement_service._cache_timestamp = None
                if hasattr(achievement_service, '_event_type_cache'):
                    achievement_service._event_type_cache.clear()
                if hasattr(achievement_service, '_rate_limit_cache'):
                    achievement_service._rate_limit_cache.clear()
            
            # 重置經濟服務快取
            economy_service = self.startup_manager.service_instances.get("EconomyService")
            if economy_service and hasattr(economy_service, '_account_cache'):
                economy_service._account_cache.clear()
                
        except Exception as e:
            print(f"重置服務快取時發生錯誤：{e}")
    
    async def cleanup(self):
        """清理測試環境"""
        try:
            # 清理服務
            if self.startup_manager:
                await self.startup_manager.cleanup_all_services()
            
            # 重置全局狀態
            await reset_global_startup_manager()
            
            # 恢復環境變數
            if self.original_env.get("DATABASE_PATH") is None:
                if "DATABASE_PATH" in os.environ:
                    del os.environ["DATABASE_PATH"]
            else:
                os.environ["DATABASE_PATH"] = self.original_env["DATABASE_PATH"]
            
            # 清理臨時目錄
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                
        except Exception as e:
            print(f"清理測試環境時發生錯誤：{e}")


@asynccontextmanager
async def isolated_test_environment():
    """
    提供隔離測試環境的上下文管理器
    
    使用範例：
        async with isolated_test_environment() as env:
            startup_manager = env["startup_manager"]
            # 執行測試...
    """
    manager = TestEnvironmentManager()
    try:
        env = await manager.setup()
        # 在每個測試開始前清理資料庫和快取
        await cleanup_test_database(env["db_path"])
        await manager._reset_service_caches()  # 再次重置快取
        yield env
    finally:
        await manager.cleanup()


async def create_test_user_account(
    economy_service,
    user_id: int,
    guild_id: int,
    initial_balance: float = 0.0
) -> bool:
    """
    創建測試用戶帳戶，如果已存在則重置餘額
    
    參數：
        economy_service: 經濟服務實例
        user_id: 用戶ID
        guild_id: 伺服器ID
        initial_balance: 初始餘額
        
    返回：
        是否成功創建或重置
    """
    from services.economy.models import AccountType
    
    account_id = f"user_{user_id}_{guild_id}"
    
    try:
        # 先嘗試獲取現有帳戶
        try:
            account = await economy_service.get_account(account_id)
            if account:
                # 帳戶已存在，重置餘額
                current_balance = account.balance
                if current_balance != initial_balance:
                    if current_balance > initial_balance:
                        # 提取多餘金額
                        await economy_service.withdraw(
                            account_id, 
                            current_balance - initial_balance, 
                            "測試重置"
                        )
                    else:
                        # 添加不足金額
                        await economy_service.deposit(
                            account_id,
                            initial_balance - current_balance,
                            "測試初始化"
                        )
                print(f"已重置測試帳戶 {account_id} 餘額為 {initial_balance}")
                return True
        except Exception:
            # 帳戶不存在，創建新帳戶
            pass
        
        # 創建新帳戶
        await economy_service.create_account(
            guild_id=guild_id,
            account_type=AccountType.USER,
            user_id=user_id,
            initial_balance=initial_balance
        )
        print(f"已創建測試帳戶 {account_id} 餘額為 {initial_balance}")
        return True
        
    except Exception as e:
        print(f"創建/重置測試帳戶失敗：{e}")
        return False


async def cleanup_test_database(db_path: str):
    """
    清理測試資料庫中的所有資料
    
    參數：
        db_path: 資料庫路徑
    """
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            # 清理所有測試相關的表，按照依賴順序清理
            cleanup_order = [
                # 先清理依賴表
                "achievement_rewards_log",
                "user_badges",
                "achievement_audit_log", 
                "user_achievement_progress",
                "economy_transactions",
                "economy_audit_log",
                "user_roles",
                "role_permissions",
                # 然後清理主表
                "achievements",
                "economy_accounts",
                "government_roles"
            ]
            
            for table in cleanup_order:
                try:
                    await db.execute(f"DELETE FROM {table}")
                except Exception:
                    pass  # 表可能不存在
            
            # 重置自增ID
            reset_sequences = [
                "DELETE FROM sqlite_sequence WHERE name IN ('achievements', 'economy_accounts', 'achievement_rewards_log')"
            ]
            
            for sql in reset_sequences:
                try:
                    await db.execute(sql)
                except Exception:
                    pass  # sqlite_sequence可能不存在
            
            await db.commit()
            print(f"測試資料庫已清理：{db_path}")
    except Exception as e:
        print(f"清理資料庫失敗：{e}")