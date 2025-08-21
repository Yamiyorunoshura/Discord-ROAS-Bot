"""
pytest配置文件
Task ID: 4 - 實作政府系統核心功能

設置測試環境，包括Python路徑配置和共享fixture
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# 獲取項目根目錄
project_root = Path(__file__).parent.absolute()

# 確保項目根目錄在Python路徑的最前面
project_root_str = str(project_root)
if project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)

# 設置環境變數
os.environ["PYTHONPATH"] = project_root_str

# 修復Discord.py在Python 3.10中的類型註解問題
try:
    # 在導入Discord之前修補類型問題
    import discord.app_commands
    
    # 保存原始Command類別
    OriginalCommand = discord.app_commands.Command
    
    # 創建一個新的Command類，支援Python 3.10的類型註解
    class PatchedCommand(OriginalCommand):
        @classmethod
        def __class_getitem__(cls, item):
            """允許類型註解subscript操作"""
            return cls
    
    # 替換原始Command類別
    discord.app_commands.Command = PatchedCommand
    
    # 同時需要修補可能導致問題的其他類別
    # 確保在hybrid.py導入之前Command已經是可訂閱的
    print("🔧 Discord.py類型註解問題已修復")
    
except ImportError:
    # 如果Discord還沒安裝，跳過修復
    pass
except Exception as e:
    print(f"⚠️ Discord.py修復失敗: {e}")

# 確保所有必要的typing功能都可用
import typing
if hasattr(typing, 'get_origin'):
    # Python 3.8+ 的現代typing特性已可用
    pass
else:
    # 為舊版本提供回退支援
    try:
        from typing_extensions import get_origin, get_args
        typing.get_origin = get_origin
        typing.get_args = get_args
    except ImportError:
        # 如果typing_extensions也不可用，提供基本實現
        def get_origin(tp):
            return getattr(tp, '__origin__', None)
        def get_args(tp):
            return getattr(tp, '__args__', ())
        typing.get_origin = get_origin
        typing.get_args = get_args

# 驗證模組可以匯入
try:
    import services
    print(f"✅ Services module imported from: {services.__file__ if hasattr(services, '__file__') else 'built-in'}")
except ImportError as e:
    print(f"❌ Failed to import services: {e}")

print(f"🏠 Project root: {project_root}")
print(f"🐍 Python path (first 3): {sys.path[:3]}")
print(f"📁 PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")

# === 增強的測試基礎設施支援 ===
# Task ID: 10 - 建立系統整合測試
import pytest
import asyncio
import tempfile
import uuid
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta

# 導入測試基礎設施模組
try:
    from tests.test_infrastructure import (
        TestEnvironment,
        MockDiscordClient, 
        TestDataGenerator,
        create_test_environment,
        setup_service_integration
    )
    print("✅ 測試基礎設施模組載入成功")
except ImportError as e:
    print(f"⚠️ 測試基礎設施模組載入失敗: {e}")


# === 全域測試配置 ===
# 設定測試標記
pytest_plugins = ['pytest_asyncio']

def pytest_configure(config):
    """配置pytest"""
    # 註冊自定義標記
    config.addinivalue_line("markers", "integration: 整合測試標記")
    config.addinivalue_line("markers", "performance: 效能測試標記") 
    config.addinivalue_line("markers", "load: 負載測試標記")
    config.addinivalue_line("markers", "e2e: 端到端測試標記")
    config.addinivalue_line("markers", "cross_system: 跨系統測試標記")


def pytest_collection_modifyitems(config, items):
    """修改測試項目收集"""
    # 為整合測試添加slow標記
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(pytest.mark.slow)
        if "performance" in item.keywords:
            item.add_marker(pytest.mark.slow)
        if "load" in item.keywords:
            item.add_marker(pytest.mark.slow)


# === 全域Fixture ===
@pytest.fixture(scope="session")
def event_loop():
    """為整個測試會話提供事件循環"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
async def isolated_test_environment():
    """提供隔離的測試環境"""
    async with create_test_environment() as env:
        yield env


@pytest.fixture
async def mock_discord_client(isolated_test_environment):
    """提供Discord客戶端模擬器"""
    return MockDiscordClient(isolated_test_environment)


@pytest.fixture
async def test_data_factory(isolated_test_environment):
    """提供測試資料生成器"""
    return TestDataGenerator(isolated_test_environment)


@pytest.fixture
async def full_system_integration(isolated_test_environment):
    """提供完整系統整合環境"""
    services = await setup_service_integration(
        isolated_test_environment,
        ["achievement", "economy", "government", "activity", "welcome", "message"]
    )
    return {
        "environment": isolated_test_environment,
        "services": services,
        "db_manager": isolated_test_environment.db_manager,
        "service_registry": isolated_test_environment.service_registry
    }


@pytest.fixture
async def cross_system_test_setup(full_system_integration, test_data_factory):
    """跨系統測試設定"""
    integration = full_system_integration
    data_factory = test_data_factory
    
    # 建立測試資料
    test_users = await data_factory.create_test_users(10)
    test_achievements = await data_factory.create_test_achievements(5)
    test_departments = await data_factory.create_test_government_departments(3)
    
    return {
        **integration,
        "test_data": {
            "users": test_users,
            "achievements": test_achievements,
            "departments": test_departments
        },
        "data_factory": data_factory
    }


# === 效能測試工具 ===
@pytest.fixture
def performance_monitor():
    """效能監控工具"""
    class PerformanceMonitor:
        def __init__(self):
            self.measurements = []
            
        def start_measurement(self, operation_name: str):
            return {
                "operation": operation_name,
                "start_time": datetime.now(),
                "start_memory": self._get_memory_usage()
            }
            
        def end_measurement(self, measurement: dict):
            measurement["end_time"] = datetime.now()
            measurement["end_memory"] = self._get_memory_usage()
            measurement["duration_ms"] = (
                measurement["end_time"] - measurement["start_time"]
            ).total_seconds() * 1000
            measurement["memory_delta"] = (
                measurement["end_memory"] - measurement["start_memory"]
            )
            self.measurements.append(measurement)
            return measurement
            
        def _get_memory_usage(self):
            try:
                import psutil
                process = psutil.Process()
                return process.memory_info().rss / 1024 / 1024  # MB
            except ImportError:
                return 0
                
        def get_stats(self):
            if not self.measurements:
                return {}
                
            durations = [m["duration_ms"] for m in self.measurements]
            return {
                "count": len(self.measurements),
                "avg_duration_ms": sum(durations) / len(durations),
                "max_duration_ms": max(durations),
                "min_duration_ms": min(durations),
                "total_duration_ms": sum(durations)
            }
    
    return PerformanceMonitor()


# === 負載測試工具 ===
@pytest.fixture
def load_test_runner():
    """負載測試執行器"""
    class LoadTestRunner:
        def __init__(self):
            self.results = []
            
        async def run_concurrent_operations(
            self,
            operation_func,
            concurrent_count: int = 10,
            operations_per_user: int = 5,
            **kwargs
        ):
            """執行並發操作"""
            tasks = []
            
            for user_id in range(concurrent_count):
                for op_id in range(operations_per_user):
                    task = asyncio.create_task(
                        self._run_single_operation(
                            operation_func,
                            user_id=user_id,
                            operation_id=op_id,
                            **kwargs
                        )
                    )
                    tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 分析結果
            successful = [r for r in results if not isinstance(r, Exception)]
            failed = [r for r in results if isinstance(r, Exception)]
            
            self.results.append({
                "timestamp": datetime.now(),
                "concurrent_count": concurrent_count,
                "operations_per_user": operations_per_user,
                "total_operations": len(tasks),
                "successful": len(successful),
                "failed": len(failed),
                "success_rate": len(successful) / len(tasks) * 100,
                "failures": failed[:5]  # 只保留前5個錯誤
            })
            
            return self.results[-1]
            
        async def _run_single_operation(self, operation_func, user_id, operation_id, **kwargs):
            """執行單個操作"""
            try:
                start_time = datetime.now()
                result = await operation_func(user_id=user_id, operation_id=operation_id, **kwargs)
                end_time = datetime.now()
                
                return {
                    "user_id": user_id,
                    "operation_id": operation_id,
                    "duration_ms": (end_time - start_time).total_seconds() * 1000,
                    "result": result,
                    "success": True
                }
            except Exception as e:
                return e
    
    return LoadTestRunner()


print("🧪 增強測試基礎設施配置完成")