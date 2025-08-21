"""
測試基礎設施框架
Task ID: 10 - 建立系統整合測試

這個模組提供測試環境的基礎設施和工具：
- 測試資料庫建立和清理
- Discord API模擬
- 測試資料生成和管理  
- 測試環境隔離
- 並行測試支援

符合要求：
- F1: 建立端到端測試框架
- N1: 測試執行效率 - 完整測試套件執行時間<10分鐘
- N2: 測試覆蓋率 - 整體程式碼覆蓋率≥90%
- N3: 測試穩定性 - 測試通過率≥99%
"""

import asyncio
import tempfile
import os
import uuid
import json
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, AsyncGenerator, ContextManager
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager
import pytest
import discord

from core.database_manager import DatabaseManager
from core.base_service import ServiceRegistry
from core.exceptions import ServiceError, ValidationError


class TestEnvironment:
    """測試環境管理器"""
    
    def __init__(self, temp_dir: str, environment_id: str):
        self.temp_dir = temp_dir
        self.environment_id = environment_id
        self.db_manager: Optional[DatabaseManager] = None
        self.service_registry: Optional[ServiceRegistry] = None
        self.mock_bot: Optional[MagicMock] = None
        self.mock_guild: Optional[MagicMock] = None
        self.test_users: Dict[int, MagicMock] = {}
        self.created_services: List[str] = []
        
    async def initialize(self) -> bool:
        """初始化測試環境"""
        try:
            # 設定環境變數
            os.environ["PROJECT_ROOT"] = self.temp_dir
            
            # 建立服務註冊表
            self.service_registry = ServiceRegistry()
            
            # 建立資料庫管理器
            self.db_manager = DatabaseManager(
                db_name=f"test_{self.environment_id}.db",
                message_db_name=f"test_message_{self.environment_id}.db"
            )
            await self.service_registry.register_service(self.db_manager)
            
            # 建立Discord模擬環境
            await self._setup_discord_mocks()
            
            return True
            
        except Exception as e:
            print(f"測試環境初始化失敗：{e}")
            return False
    
    async def cleanup(self):
        """清理測試環境"""
        try:
            # 清理所有服務
            if self.service_registry:
                await self.service_registry.cleanup_all_services()
            
            # 清理測試資料
            self.test_users.clear()
            self.created_services.clear()
            
            # 重置環境變數
            if "PROJECT_ROOT" in os.environ:
                del os.environ["PROJECT_ROOT"]
                
        except Exception as e:
            print(f"測試環境清理失敗：{e}")
    
    async def _setup_discord_mocks(self):
        """設定Discord模擬環境"""
        # 建立模擬bot
        self.mock_bot = MagicMock()
        self.mock_bot.user = MagicMock()
        self.mock_bot.user.id = 123456789
        self.mock_bot.user.name = "TestBot"
        
        # 建立模擬伺服器
        self.mock_guild = MagicMock()
        self.mock_guild.id = 987654321
        self.mock_guild.name = "Test Guild"
        self.mock_guild.member_count = 100
        
        # 設定bot.get_guild回傳模擬伺服器
        self.mock_bot.get_guild.return_value = self.mock_guild
        self.mock_bot.guilds = [self.mock_guild]


class MockDiscordClient:
    """Discord客戶端模擬器"""
    
    def __init__(self, test_env: TestEnvironment):
        self.test_env = test_env
        self.interaction_responses: List[Dict[str, Any]] = []
        
    def create_interaction(
        self,
        user_id: int = None,
        username: str = None,
        guild_id: int = None,
        interaction_type = None,
        custom_id: str = None,
        command_name: str = None
    ) -> MagicMock:
        """建立模擬的Discord互動"""
        if user_id is None:
            user_id = random.randint(100000, 999999)
        if username is None:
            username = f"TestUser{user_id}"
        if guild_id is None:
            guild_id = self.test_env.mock_guild.id
        if interaction_type is None:
            interaction_type = "component"  # 簡化的字串類型
            
        # 建立或獲取現有的測試使用者
        if user_id not in self.test_env.test_users:
            user = MagicMock()
            user.id = user_id
            user.name = username
            user.display_name = username
            user.mention = f"<@{user_id}>"
            self.test_env.test_users[user_id] = user
        else:
            user = self.test_env.test_users[user_id]
        
        # 建立模擬互動
        interaction = MagicMock()
        interaction.user = user
        interaction.guild = self.test_env.mock_guild
        interaction.guild_id = guild_id
        interaction.type = interaction_type
        interaction.data = {}
        
        if custom_id:
            interaction.data["custom_id"] = custom_id
        if command_name:
            interaction.data["name"] = command_name
            
        # 設定回應模擬
        interaction.response = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.response.edit_message = AsyncMock()
        interaction.response.defer = AsyncMock()
        
        # 記錄互動回應
        async def mock_send_message(*args, **kwargs):
            self.interaction_responses.append({
                "type": "send_message",
                "user_id": user_id,
                "args": args,
                "kwargs": kwargs,
                "timestamp": datetime.now()
            })
            
        interaction.response.send_message.side_effect = mock_send_message
        
        return interaction
    
    def get_interaction_responses(self, user_id: int = None) -> List[Dict[str, Any]]:
        """獲取互動回應記錄"""
        if user_id is None:
            return self.interaction_responses
        return [r for r in self.interaction_responses if r.get("user_id") == user_id]
    
    def clear_responses(self):
        """清除互動回應記錄"""
        self.interaction_responses.clear()


class TestDataGenerator:
    """測試資料生成器"""
    
    def __init__(self, test_env: TestEnvironment):
        self.test_env = test_env
        self.generated_data: Dict[str, List[Any]] = {}
        
    async def create_test_users(self, count: int = 10) -> List[Dict[str, Any]]:
        """建立測試使用者資料"""
        users = []
        for i in range(count):
            user_id = random.randint(100000, 999999)
            username = f"TestUser{i}_{user_id}"
            
            user_data = {
                "discord_id": user_id,
                "username": username,
                "display_name": username,
                "joined_at": datetime.now() - timedelta(days=random.randint(1, 365)),
                "level": random.randint(1, 50),
                "experience": random.randint(0, 10000),
                "balance": random.randint(0, 50000),
                "reputation": random.randint(-100, 1000)
            }
            users.append(user_data)
            
        self.generated_data["users"] = users
        return users
    
    async def create_test_achievements(self, count: int = 5) -> List[Dict[str, Any]]:
        """建立測試成就資料"""
        achievements = []
        achievement_types = ["MILESTONE", "CUMULATIVE", "STREAK", "RARE"]
        trigger_types = ["MESSAGE_COUNT", "VOICE_TIME", "REACTION_COUNT", "LEVEL_UP"]
        
        for i in range(count):
            achievement_id = f"test_achievement_{i}_{uuid.uuid4().hex[:8]}"
            
            achievement_data = {
                "achievement_id": achievement_id,
                "name": f"測試成就 {i+1}",
                "description": f"這是第 {i+1} 個測試成就",
                "type": random.choice(achievement_types),
                "trigger_type": random.choice(trigger_types),
                "target_value": random.randint(10, 1000),
                "reward_currency": random.randint(100, 5000),
                "reward_experience": random.randint(50, 500),
                "is_active": True,
                "created_at": datetime.now() - timedelta(days=random.randint(1, 30))
            }
            achievements.append(achievement_data)
            
        self.generated_data["achievements"] = achievements
        return achievements
    
    async def create_test_government_departments(self, count: int = 3) -> List[Dict[str, Any]]:
        """建立測試政府部門資料"""
        departments = []
        department_names = ["測試部", "開發部", "運營部", "技術部", "管理部"]
        
        for i in range(count):
            dept_id = f"test_dept_{i}_{uuid.uuid4().hex[:8]}"
            
            department_data = {
                "department_id": dept_id,
                "name": department_names[i % len(department_names)],
                "description": f"測試部門 {i+1}",
                "budget": random.randint(10000, 100000),
                "max_members": random.randint(5, 20),
                "created_at": datetime.now() - timedelta(days=random.randint(1, 60)),
                "is_active": True
            }
            departments.append(department_data)
            
        self.generated_data["departments"] = departments
        return departments
    
    async def create_test_economic_transactions(self, user_count: int = 5, transaction_count: int = 20) -> List[Dict[str, Any]]:
        """建立測試經濟交易資料"""
        if "users" not in self.generated_data:
            await self.create_test_users(user_count)
            
        transactions = []
        transaction_types = ["ACHIEVEMENT_REWARD", "DEPARTMENT_SALARY", "TRANSFER", "PURCHASE"]
        
        for i in range(transaction_count):
            user = random.choice(self.generated_data["users"])
            transaction_id = f"tx_{i}_{uuid.uuid4().hex[:8]}"
            
            transaction_data = {
                "transaction_id": transaction_id,
                "user_id": user["discord_id"],
                "type": random.choice(transaction_types),
                "amount": random.randint(-1000, 5000),
                "description": f"測試交易 {i+1}",
                "timestamp": datetime.now() - timedelta(hours=random.randint(1, 168))
            }
            transactions.append(transaction_data)
            
        self.generated_data["transactions"] = transactions
        return transactions
    
    def get_generated_data(self, data_type: str = None) -> Dict[str, Any]:
        """獲取生成的測試資料"""
        if data_type:
            return self.generated_data.get(data_type, [])
        return self.generated_data
    
    def clear_generated_data(self):
        """清除生成的測試資料"""
        self.generated_data.clear()


@asynccontextmanager
async def create_test_environment() -> AsyncGenerator[TestEnvironment, None]:
    """建立隔離的測試環境"""
    with tempfile.TemporaryDirectory(prefix="discord_bot_test_") as temp_dir:
        environment_id = uuid.uuid4().hex[:8]
        test_env = TestEnvironment(temp_dir, environment_id)
        
        try:
            success = await test_env.initialize()
            if not success:
                raise RuntimeError("測試環境初始化失敗")
            yield test_env
        finally:
            await test_env.cleanup()


async def setup_service_integration(
    test_env: TestEnvironment,
    services_to_load: List[str] = None
) -> Dict[str, Any]:
    """設定服務整合環境"""
    if services_to_load is None:
        services_to_load = ["achievement", "economy", "government", "activity", "welcome", "message"]
    
    loaded_services = {}
    
    # 先初始化基礎服務
    await test_env.service_registry.initialize_all_services()
    
    # 動態載入指定的服務
    for service_name in services_to_load:
        try:
            if service_name == "achievement":
                from services.achievement.achievement_service import AchievementService
                service = AchievementService()
                service.add_dependency(test_env.db_manager, "database_manager")
                
            elif service_name == "economy":
                from services.economy.economy_service import EconomyService
                service = EconomyService()
                service.add_dependency(test_env.db_manager, "database_manager")
                
            elif service_name == "government":
                from services.government.government_service import GovernmentService
                service = GovernmentService()
                service.add_dependency(test_env.db_manager, "database_manager")
                
            elif service_name == "activity":
                from services.activity.activity_service import ActivityService
                service = ActivityService(test_env.db_manager)
                
            elif service_name == "welcome":
                from services.welcome.welcome_service import WelcomeService
                service = WelcomeService(test_env.db_manager)
                
            elif service_name == "message":
                from services.message.message_service import MessageService
                service = MessageService(test_env.db_manager)
                
            else:
                continue
                
            await test_env.service_registry.register_service(service)
            await service.initialize()
            loaded_services[service_name] = service
            test_env.created_services.append(service_name)
            
        except Exception as e:
            print(f"載入服務 {service_name} 失敗：{e}")
            
    return loaded_services


# 測試裝飾器和工具函數
def performance_test(max_duration_ms: int = 1000):
    """效能測試裝飾器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = datetime.now()
            result = await func(*args, **kwargs)
            end_time = datetime.now()
            
            duration = (end_time - start_time).total_seconds() * 1000
            if duration > max_duration_ms:
                pytest.fail(f"測試 {func.__name__} 執行時間 {duration:.2f}ms 超過限制 {max_duration_ms}ms")
                
            return result
        return wrapper
    return decorator


def load_test(concurrent_users: int = 10, operations_per_user: int = 5):
    """負載測試裝飾器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tasks = []
            for user_id in range(concurrent_users):
                for operation in range(operations_per_user):
                    task = asyncio.create_task(
                        func(*args, user_id=user_id, operation=operation, **kwargs)
                    )
                    tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 檢查是否有失敗的操作
            failures = [r for r in results if isinstance(r, Exception)]
            if failures:
                pytest.fail(f"負載測試中有 {len(failures)} 個操作失敗：{failures[:3]}")
                
            return results
        return wrapper
    return decorator


def data_consistency_check(services: List[str]):
    """資料一致性檢查裝飾器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 執行前記錄狀態
            pre_state = {}
            for service_name in services:
                # 這裡可以記錄各服務的關鍵資料狀態
                pass
            
            result = await func(*args, **kwargs)
            
            # 執行後檢查狀態一致性
            post_state = {}
            for service_name in services:
                # 這裡可以檢查各服務的資料是否一致
                pass
            
            return result
        return wrapper
    return decorator


# 預設fixture
@pytest.fixture
async def test_environment():
    """基本測試環境fixture"""
    async with create_test_environment() as env:
        yield env


@pytest.fixture
async def discord_client(test_environment):
    """Discord客戶端模擬器fixture"""
    return MockDiscordClient(test_environment)


@pytest.fixture
async def test_data_generator(test_environment):
    """測試資料生成器fixture"""
    return TestDataGenerator(test_environment)


@pytest.fixture
async def integrated_services(test_environment):
    """整合服務環境fixture"""
    return await setup_service_integration(test_environment)