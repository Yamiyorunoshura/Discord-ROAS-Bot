"""
企業級依賴注入容器測試套件
Discord ROAS Bot - 完整的單元測試

測試覆蓋範圍:
- 基本依賴注入功能
- 生命週期管理 (Singleton, Scoped, Transient)
- 條件注入
- 循環依賴檢測
- 性能監控
- 泛型類型支持
- 多實現選擇
- 線程安全性
- 診斷工具

作者:Discord ROAS Bot 測試工程師
版本:v2.0
"""

import asyncio
import os
import threading
import time
from typing import Any, Protocol, TypeVar
from unittest.mock import patch

import pytest

from src.core.container import (
    CircularDependencyException,
    Container,
    InjectionCondition,
    ServiceDescriptor,
    ServiceLifetime,
    ServiceNotFoundException,
    configure_container,
    get_container,
    inject,
    injectable,
    reset_container,
    scoped,
    singleton,
    transient,
    when_custom,
    when_environment,
    when_feature_flag,
)

# 測試用的接口和類型
T = TypeVar("T")


class IRepository(Protocol[T]):
    """泛型儲存庫接口"""

    def get(self, id: str) -> T: ...

    def save(self, entity: T) -> None: ...


class IUserService(Protocol):
    """用戶服務接口"""

    def get_user(self, user_id: str) -> str: ...


class ILogger(Protocol):
    """日誌接口"""

    def log(self, message: str) -> None: ...


# 測試用的實現類
class DatabaseRepository[T]:
    """數據庫儲存庫實現"""

    def __init__(self):
        self.data: dict[str, T] = {}

    def get(self, id: str) -> T:
        return self.data.get(id)

    def save(self, entity: T) -> None:
        self.data[str(id(entity))] = entity


class InMemoryRepository[T]:
    """內存儲存庫實現"""

    def __init__(self):
        self.data: dict[str, T] = {}

    def get(self, id: str) -> T:
        return self.data.get(id)

    def save(self, entity: T) -> None:
        self.data[id] = entity


class UserService:
    """用戶服務實現"""

    def __init__(self, repository: IRepository[str], logger: ILogger):
        self.repository = repository
        self.logger = logger
        self.created_at = time.time()

    def get_user(self, user_id: str) -> str:
        self.logger.log(f"Getting user: {user_id}")
        return self.repository.get(user_id)


class SimpleUserService:
    """簡單用戶服務實現(無依賴)"""

    def __init__(self):
        self.created_at = time.time()

    def get_user(self, user_id: str) -> str:
        return f"User: {user_id}"


class ConsoleLogger:
    """控制台日誌實現"""

    def __init__(self):
        self.logs: list[str] = []

    def log(self, message: str) -> None:
        self.logs.append(message)


class FileLogger:
    """文件日誌實現"""

    def __init__(self):
        self.logs: list[str] = []
        self.file_path = "/tmp/test.log"

    def log(self, message: str) -> None:
        self.logs.append(f"[FILE] {message}")


class CircularDependencyA:
    """循環依賴測試類 A"""

    def __init__(self, dep_b: "CircularDependencyB"):
        self.dep_b = dep_b


class CircularDependencyB:
    """循環依賴測試類 B"""

    def __init__(self, dep_a: CircularDependencyA):
        self.dep_a = dep_a


class TestServiceDescriptor:
    """服務描述符測試"""

    def test_basic_descriptor_creation(self):
        """測試基本服務描述符創建"""
        descriptor = ServiceDescriptor(
            service_type=IUserService,
            implementation=UserService,
            lifetime=ServiceLifetime.TRANSIENT,
        )

        assert descriptor.service_type == IUserService
        assert descriptor.implementation == UserService
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT
        assert descriptor.factory is None
        assert descriptor.tags == []
        assert descriptor.priority == 0
        assert descriptor.access_count == 0
        assert descriptor.last_accessed is None
        assert descriptor.created_at is None

    def test_descriptor_with_tags_and_priority(self):
        """測試帶標籤和優先級的服務描述符"""
        tags = ["database", "primary"]
        descriptor = ServiceDescriptor(
            service_type=IRepository,
            implementation=DatabaseRepository,
            lifetime=ServiceLifetime.SINGLETON,
            tags=tags,
            priority=10,
        )

        assert descriptor.tags == tags
        assert descriptor.priority == 10

    def test_descriptor_with_conditional_rules(self):
        """測試帶條件規則的服務描述符"""
        rules = [
            when_environment("ENV", "production"),
            when_feature_flag("new_feature", True),
        ]

        descriptor = ServiceDescriptor(
            service_type=ILogger,
            implementation=FileLogger,
            lifetime=ServiceLifetime.SINGLETON,
            conditional_rules=rules,
        )

        assert len(descriptor.conditional_rules) == 2
        assert (
            descriptor.conditional_rules[0].condition_type
            == InjectionCondition.ENVIRONMENT
        )
        assert (
            descriptor.conditional_rules[1].condition_type
            == InjectionCondition.FEATURE_FLAG
        )

    def test_matches_conditions_environment(self):
        """測試環境變數條件匹配"""
        rule = when_environment("TEST_ENV", "test")
        descriptor = ServiceDescriptor(
            service_type=ILogger, implementation=ConsoleLogger, conditional_rules=[rule]
        )

        # 設置環境變數
        with patch.dict(os.environ, {"TEST_ENV": "test"}):
            assert descriptor.matches_conditions({}) is True

        with patch.dict(os.environ, {"TEST_ENV": "production"}):
            assert descriptor.matches_conditions({}) is False

        # 清理環境變數
        if "TEST_ENV" in os.environ:
            del os.environ["TEST_ENV"]

    def test_matches_conditions_feature_flag(self):
        """測試功能開關條件匹配"""
        rule = when_feature_flag("new_ui", True)
        descriptor = ServiceDescriptor(
            service_type=ILogger, implementation=ConsoleLogger, conditional_rules=[rule]
        )

        context = {"feature_flags": {"new_ui": True}}
        assert descriptor.matches_conditions(context) is True

        context = {"feature_flags": {"new_ui": False}}
        assert descriptor.matches_conditions(context) is False

        context = {"feature_flags": {}}
        assert descriptor.matches_conditions(context) is False

    def test_matches_conditions_custom(self):
        """測試自定義條件匹配"""

        def custom_condition():
            return True

        rule = when_custom(custom_condition)
        descriptor = ServiceDescriptor(
            service_type=ILogger, implementation=ConsoleLogger, conditional_rules=[rule]
        )

        assert descriptor.matches_conditions({}) is True

        # 測試失敗條件
        def failing_condition():
            return False

        rule = when_custom(failing_condition)
        descriptor.conditional_rules = [rule]

        assert descriptor.matches_conditions({}) is False

    def test_update_access_stats(self):
        """測試訪問統計更新"""
        descriptor = ServiceDescriptor(
            service_type=ILogger, implementation=ConsoleLogger
        )

        initial_time = time.time()
        descriptor.update_access_stats()

        assert descriptor.access_count == 1
        assert descriptor.last_accessed >= initial_time

        descriptor.update_access_stats()
        assert descriptor.access_count == 2


class TestContainer:
    """容器測試"""

    @pytest.fixture
    def container(self):
        """創建測試容器"""
        return Container()

    def test_container_initialization(self, container):
        """測試容器初始化"""
        assert container._settings is not None
        assert container._logger is not None
        assert len(container._services) >= 3  # 核心服務數量
        assert container._metrics.total_injections == 0

    def test_register_and_get_transient_service(self, container):
        """測試註冊和獲取瞬時性服務"""
        container.register_transient(ILogger, ConsoleLogger)

        instance1 = container.get(ILogger)
        instance2 = container.get(ILogger)

        assert isinstance(instance1, ConsoleLogger)
        assert isinstance(instance2, ConsoleLogger)
        assert instance1 is not instance2  # 不同實例

    def test_register_and_get_singleton_service(self, container):
        """測試註冊和獲取單例服務"""
        container.register_singleton(ILogger, ConsoleLogger)

        instance1 = container.get(ILogger)
        instance2 = container.get(ILogger)

        assert isinstance(instance1, ConsoleLogger)
        assert isinstance(instance2, ConsoleLogger)
        assert instance1 is instance2  # 相同實例

    def test_register_and_get_scoped_service(self, container):
        """測試註冊和獲取作用域服務"""
        container.register_scoped(ILogger, ConsoleLogger)

        # 同一作用域內應該是相同實例
        instance1 = container.get(ILogger, scope="request1")
        instance2 = container.get(ILogger, scope="request1")
        assert instance1 is instance2

        # 不同作用域內應該是不同實例
        instance3 = container.get(ILogger, scope="request2")
        assert instance1 is not instance3

    def test_register_factory_service(self, container):
        """測試註冊工廠服務"""

        def logger_factory() -> ILogger:
            return ConsoleLogger()

        container.register_factory(ILogger, logger_factory, ServiceLifetime.SINGLETON)

        instance = container.get(ILogger)
        assert isinstance(instance, ConsoleLogger)

    def test_dependency_injection(self, container):
        """測試自動依賴注入"""
        container.register_singleton(ILogger, ConsoleLogger)
        container.register_transient(IRepository, DatabaseRepository)
        container.register_transient(IUserService, UserService)

        user_service = container.get(IUserService)

        assert isinstance(user_service, UserService)
        assert isinstance(user_service.repository, DatabaseRepository)
        assert isinstance(user_service.logger, ConsoleLogger)

    def test_circular_dependency_detection(self, container):
        """測試循環依賴檢測"""
        container.register_transient(CircularDependencyA)
        container.register_transient(CircularDependencyB)

        with pytest.raises(CircularDependencyException) as exc_info:
            container.get(CircularDependencyA)

        assert "循環依賴" in str(exc_info.value)
        assert container._metrics.circular_dependencies_detected > 0

    def test_service_not_found_exception(self, container):
        """測試服務未找到異常"""
        with pytest.raises(ServiceNotFoundException) as exc_info:
            container.get(IUserService)

        assert "服務未註冊" in str(exc_info.value)
        assert container._metrics.failed_injections > 0

    def test_conditional_injection_environment(self, container):
        """測試基於環境變數的條件注入"""
        # 註冊兩個不同的日誌實現
        container.register_singleton(
            ILogger,
            FileLogger,
            conditional_rules=[when_environment("LOG_TYPE", "file")],
        )
        container.register_singleton(
            ILogger,
            ConsoleLogger,
            conditional_rules=[when_environment("LOG_TYPE", "console")],
        )

        # 測試文件日誌
        with patch.dict(os.environ, {"LOG_TYPE": "file"}):
            logger = container.get(ILogger)
            assert isinstance(logger, FileLogger)

        # 重置容器狀態
        container.clear_scoped()
        container._singletons.clear()

        # 測試控制台日誌
        with patch.dict(os.environ, {"LOG_TYPE": "console"}):
            logger = container.get(ILogger)
            assert isinstance(logger, ConsoleLogger)

    def test_conditional_injection_feature_flag(self, container):
        """測試基於功能開關的條件注入"""
        container.register_singleton(
            ILogger,
            FileLogger,
            conditional_rules=[when_feature_flag("advanced_logging", True)],
        )
        container.register_singleton(
            ILogger,
            ConsoleLogger,
            conditional_rules=[when_feature_flag("advanced_logging", False)],
        )

        # 啟用高級日誌
        container.set_injection_context({"feature_flags": {"advanced_logging": True}})
        logger = container.get(ILogger)
        assert isinstance(logger, FileLogger)

        # 重置狀態
        container.clear_scoped()
        container._singletons.clear()

        # 禁用高級日誌
        container.set_injection_context({"feature_flags": {"advanced_logging": False}})
        logger = container.get(ILogger)
        assert isinstance(logger, ConsoleLogger)

    def test_multiple_implementations_with_priority(self, container):
        """測試多實現選擇(基於優先級)"""
        # 註冊多個實現,優先級不同
        container.register_singleton(ILogger, ConsoleLogger, priority=1)
        container.register_singleton(ILogger, FileLogger, priority=10)  # 更高優先級

        logger = container.get(ILogger)
        assert isinstance(logger, FileLogger)  # 應該選擇高優先級的

    def test_service_with_tags(self, container):
        """測試帶標籤的服務"""
        container.register_singleton(ILogger, ConsoleLogger, tags=["console", "debug"])
        container.register_singleton(ILogger, FileLogger, tags=["file", "production"])

        # 按標籤過濾
        logger = container.get(ILogger, tags=["production"])
        assert isinstance(logger, FileLogger)

        # 重置狀態
        container.clear_scoped()
        container._singletons.clear()

        logger = container.get(ILogger, tags=["debug"])
        assert isinstance(logger, ConsoleLogger)

    def test_scope_management(self, container):
        """測試作用域管理"""
        container.register_scoped(ILogger, ConsoleLogger)

        with container.create_scope("test_scope") as scope_name:
            logger1 = container.get(ILogger, scope=scope_name)
            logger2 = container.get(ILogger, scope=scope_name)
            assert logger1 is logger2

        # 作用域銷毀後應該被清理
        assert scope_name not in container._scoped_instances

    def test_clear_scoped_specific(self, container):
        """測試清除特定作用域"""
        container.register_scoped(ILogger, ConsoleLogger)

        # 創建兩個作用域
        container.get(ILogger, scope="scope1")
        container.get(ILogger, scope="scope2")

        assert "scope1" in container._scoped_instances
        assert "scope2" in container._scoped_instances

        # 清除特定作用域
        container.clear_scoped("scope1")

        assert "scope1" not in container._scoped_instances
        assert "scope2" in container._scoped_instances

    def test_clear_scoped_all(self, container):
        """測試清除所有作用域"""
        container.register_scoped(ILogger, ConsoleLogger)

        container.get(ILogger, scope="scope1")
        container.get(ILogger, scope="scope2")

        container.clear_scoped()  # 清除所有

        assert len(container._scoped_instances) == 0

    def test_is_registered(self, container):
        """測試服務註冊檢查"""
        assert not container.is_registered(IUserService)

        container.register_transient(IUserService, SimpleUserService)
        assert container.is_registered(IUserService)

    def test_get_services_by_tag(self, container):
        """測試根據標籤獲取服務"""
        container.register_singleton(ILogger, ConsoleLogger, tags=["console"])
        container.register_singleton(IUserService, SimpleUserService, tags=["simple"])

        console_services = container.get_services_by_tag("console")
        assert ILogger in console_services
        assert IUserService not in console_services

    def test_unregister_service(self, container):
        """測試取消註冊服務"""
        container.register_singleton(ILogger, ConsoleLogger)
        assert container.is_registered(ILogger)

        # 創建實例
        logger = container.get(ILogger)
        assert logger is not None

        # 取消註冊
        result = container.unregister(ILogger)
        assert result is True
        assert not container.is_registered(ILogger)

        # 實例應該被清理
        assert ILogger not in container._singletons

    def test_get_registration_info(self, container):
        """測試獲取註冊信息"""
        container.register_singleton(ILogger, ConsoleLogger, tags=["test"], priority=5)
        container.register_transient(IUserService, SimpleUserService)

        info = container.get_registration_info()

        assert "total_services" in info
        assert "total_types" in info
        assert "services" in info
        assert info["total_services"] >= 2
        assert "ILogger" in info["services"]
        assert "IUserService" in info["services"]

        # 檢查詳細信息
        logger_info = info["services"]["ILogger"][0]
        assert logger_info["lifetime"] == "singleton"
        assert logger_info["tags"] == ["test"]
        assert logger_info["priority"] == 5

    def test_performance_metrics(self, container):
        """測試性能指標"""
        container.register_transient(ILogger, ConsoleLogger)

        # 執行一些操作
        for _ in range(10):
            container.get(ILogger)

        metrics = container.get_performance_metrics()

        assert metrics.total_injections >= 10
        assert metrics.avg_injection_time > 0
        assert metrics.max_injection_time > 0
        assert metrics.min_injection_time > 0
        assert metrics.failed_injections == 0

    def test_reset_metrics(self, container):
        """測試重置性能指標"""
        container.register_transient(ILogger, ConsoleLogger)
        container.get(ILogger)

        # 重置前應該有數據
        metrics = container.get_performance_metrics()
        assert metrics.total_injections > 0

        # 重置
        container.reset_metrics()

        # 重置後應該清空
        metrics = container.get_performance_metrics()
        assert metrics.total_injections == 0
        assert metrics.avg_injection_time == 0
        assert metrics.max_injection_time == 0

    def test_create_child_container(self, container):
        """測試創建子容器"""
        container.register_singleton(ILogger, ConsoleLogger)
        container.set_injection_context({"test": "value"})

        child = container.create_child_container()

        # 子容器應該繼承父容器的註冊
        assert child.is_registered(ILogger)

        # 子容器應該繼承父容器的上下文
        assert child.get_injection_context()["test"] == "value"

        # 子容器和父容器應該是不同的實例
        assert child is not container

    def test_validate_dependencies_success(self, container):
        """測試依賴驗證(成功情況)"""
        container.register_singleton(ILogger, ConsoleLogger)
        container.register_transient(IRepository, DatabaseRepository)
        container.register_transient(IUserService, UserService)

        errors = container.validate_dependencies()

        # 核心服務可能有一些驗證問題,但我們註冊的服務應該沒問題
        user_service_errors = [e for e in errors if "UserService" in e]
        assert len(user_service_errors) == 0

    def test_validate_dependencies_failure(self, container):
        """測試依賴驗證(失敗情況)"""
        # 註冊有依賴的服務,但不註冊其依賴
        container.register_transient(IUserService, UserService)

        errors = container.validate_dependencies()

        # 應該有依賴未註冊的錯誤
        user_service_errors = [e for e in errors if "UserService" in e]
        assert len(user_service_errors) > 0

    def test_event_handling(self, container):
        """測試事件處理"""
        events = []

        def event_handler(**kwargs):
            events.append(kwargs)

        # 添加事件處理器
        container.add_event_handler("service_registered", event_handler)
        container.add_event_handler("service_resolved", event_handler)

        # 觸發事件
        container.register_singleton(ILogger, ConsoleLogger)
        container.get(ILogger)

        # 驗證事件被觸發
        assert len(events) >= 2
        assert any(e.get("service_type") == ILogger for e in events)


class TestThreadSafety:
    """線程安全性測試"""

    @pytest.fixture
    def container(self):
        """創建測試容器"""
        return Container()

    def test_concurrent_singleton_creation(self, container):
        """測試並發單例創建"""
        container.register_singleton(ILogger, ConsoleLogger)

        instances = []

        def get_service():
            instance = container.get(ILogger)
            instances.append(instance)

        # 創建多個線程並發獲取服務
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_service)
            threads.append(thread)
            thread.start()

        # 等待所有線程完成
        for thread in threads:
            thread.join()

        # 所有實例應該是同一個
        assert len({id(instance) for instance in instances}) == 1

    def test_concurrent_registration(self, container):
        """測試並發註冊"""

        def register_service(index):
            service_type = type(f"TestService{index}", (), {})
            container.register_transient(service_type, service_type)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=register_service, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # 所有服務都應該被註冊
        info = container.get_registration_info()
        assert info["total_services"] >= 10


class TestDecorators:
    """裝飾器測試"""

    def setup_method(self):
        """每個測試方法前重置容器"""
        reset_container()

    def test_injectable_decorator(self):
        """測試 injectable 裝飾器"""

        @injectable(lifetime=ServiceLifetime.SINGLETON)
        class TestService:
            def __init__(self):
                self.value = "test"

        container = get_container()
        instance1 = container.get(TestService)
        instance2 = container.get(TestService)

        assert instance1 is instance2
        assert instance1.value == "test"

    def test_singleton_decorator(self):
        """測試 singleton 裝飾器"""

        @singleton()
        class SingletonService:
            def __init__(self):
                self.created_at = time.time()

        container = get_container()
        instance1 = container.get(SingletonService)
        instance2 = container.get(SingletonService)

        assert instance1 is instance2

    def test_scoped_decorator(self):
        """測試 scoped 裝飾器"""

        @scoped()
        class ScopedService:
            def __init__(self):
                self.created_at = time.time()

        container = get_container()

        with container.create_scope() as scope:
            instance1 = container.get(ScopedService, scope=scope)
            instance2 = container.get(ScopedService, scope=scope)
            assert instance1 is instance2

    def test_transient_decorator(self):
        """測試 transient 裝飾器"""

        @transient()
        class TransientService:
            def __init__(self):
                self.created_at = time.time()

        container = get_container()
        instance1 = container.get(TransientService)
        instance2 = container.get(TransientService)

        assert instance1 is not instance2

    def test_inject_decorator_simple(self):
        """測試簡單依賴注入裝飾器"""

        @singleton()
        class LoggerService:
            def log(self, msg: str):
                return f"LOG: {msg}"

        @inject
        def process_data(data: str, logger: LoggerService) -> str:
            logger.log(f"Processing {data}")
            return f"Processed: {data}"

        result = process_data("test_data")
        assert result == "Processed: test_data"

    def test_inject_decorator_with_manual_args(self):
        """測試手動參數與注入參數混合"""

        @singleton()
        class ConfigService:
            def get_setting(self, key: str) -> str:
                return f"setting_{key}"

        @inject
        def process_with_config(
            data: str, config: ConfigService, multiplier: int = 1
        ) -> str:
            setting = config.get_setting("test")
            return f"{data}_{setting}_{multiplier}"

        # 自動注入 config,手動提供 multiplier
        result = process_with_config("data", multiplier=5)
        assert result == "data_setting_test_5"

    def test_inject_decorator_async(self):
        """測試異步函數依賴注入"""

        @singleton()
        class AsyncService:
            async def process(self, value: str) -> str:
                return f"async_{value}"

        @inject
        async def async_handler(data: str, service: AsyncService) -> str:
            result = await service.process(data)
            return result

        async def run_test():
            result = await async_handler("test")
            assert result == "async_test"

        asyncio.run(run_test())


class TestGlobalContainerFunctions:
    """全局容器函數測試"""

    def setup_method(self):
        """每個測試方法前重置容器"""
        reset_container()

    def test_get_container_singleton(self):
        """測試全局容器單例"""
        container1 = get_container()
        container2 = get_container()

        assert container1 is container2

    def test_reset_container(self):
        """測試重置容器"""
        container1 = get_container()
        reset_container()
        container2 = get_container()

        assert container1 is not container2

    def test_configure_container(self):
        """測試配置容器"""

        def configurator(container: Container):
            container.register_singleton(ILogger, ConsoleLogger)

        container = configure_container(configurator)

        assert container.is_registered(ILogger)
        logger = container.get(ILogger)
        assert isinstance(logger, ConsoleLogger)


class TestConditionalInjectionHelpers:
    """條件注入輔助函數測試"""

    def test_when_environment(self):
        """測試環境變數條件"""
        rule = when_environment("TEST_VAR", "test_value")

        assert rule.condition_type == InjectionCondition.ENVIRONMENT
        assert rule.key == "TEST_VAR"
        assert rule.expected_value == "test_value"

    def test_when_feature_flag(self):
        """測試功能開關條件"""
        rule = when_feature_flag("feature_x", True)

        assert rule.condition_type == InjectionCondition.FEATURE_FLAG
        assert rule.key == "feature_x"
        assert rule.expected_value is True

    def test_when_custom(self):
        """測試自定義條件"""

        def custom_condition():
            return True

        rule = when_custom(custom_condition)

        assert rule.condition_type == InjectionCondition.CUSTOM
        assert rule.condition_func is custom_condition


class TestErrorHandling:
    """錯誤處理測試"""

    @pytest.fixture
    def container(self):
        """創建測試容器"""
        return Container()

    def test_service_creation_failure(self, container):
        """測試服務創建失敗"""

        class FailingService:
            def __init__(self):
                raise RuntimeError("Construction failed")

        container.register_transient(FailingService)

        # 第一次獲取應該失敗
        with pytest.raises(RuntimeError):
            container.get(FailingService)

        # 失敗計數應該增加
        metrics = container.get_performance_metrics()
        assert metrics.failed_injections > 0

    def test_invalid_dependency_type(self, container):
        """測試無效依賴類型"""

        class ServiceWithInvalidDep:
            def __init__(self, invalid_dep):  # 沒有類型提示
                self.dep = invalid_dep

        container.register_transient(ServiceWithInvalidDep)

        instance = container.get(ServiceWithInvalidDep)
        assert instance is not None


class TestRealWorldScenarios:
    """真實世界場景測試"""

    def setup_method(self):
        """每個測試方法前重置容器"""
        reset_container()

    def test_web_application_scenario(self):
        """測試Web應用程序場景"""

        # 定義服務接口
        class IDatabase(Protocol):
            def query(self, sql: str) -> list[dict]: ...

        class ICache(Protocol):
            def get(self, key: str) -> Any: ...
            def set(self, key: str, value: Any) -> None: ...

        # 實現類
        @singleton()
        class DatabaseService:
            def query(self, sql: str) -> list[dict]:
                return [{"result": "mock_data"}]

        @singleton()
        class CacheService:
            def __init__(self):
                self._cache = {}

            def get(self, key: str) -> Any:
                return self._cache.get(key)

            def set(self, key: str, value: Any) -> None:
                self._cache[key] = value

        @scoped()
        class UserRepository:
            def __init__(self, db: DatabaseService, cache: CacheService):
                self.db = db
                self.cache = cache

            def get_user(self, user_id: str) -> dict:
                # 首先檢查緩存
                cached = self.cache.get(f"user_{user_id}")
                if cached:
                    return cached

                # 從數據庫查詢
                result = self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
                user = result[0] if result else {"id": user_id, "name": "Unknown"}

                # 緩存結果
                self.cache.set(f"user_{user_id}", user)
                return user

        @transient()
        class UserController:
            def __init__(self, user_repo: UserRepository):
                self.user_repo = user_repo

            def get_user_info(self, user_id: str) -> str:
                user = self.user_repo.get_user(user_id)
                return f"User: {user['name']} (ID: {user['id']})"

        # 模擬Web請求處理
        container = get_container()

        with container.create_scope("request_1") as scope:
            controller = container.get(UserController, scope=scope)
            controller.get_user_info("123")

            # 同一請求中的另一個調用應該使用相同的repository
            controller2 = container.get(UserController, scope=scope)
            assert controller.user_repo is controller2.user_repo

        # 新請求應該有新的repository
        with container.create_scope("request_2") as scope:
            controller3 = container.get(UserController, scope=scope)
            assert controller.user_repo is not controller3.user_repo

    def test_microservice_configuration(self):
        """測試微服務配置場景"""

        # 根據環境配置不同的服務
        @injectable(
            ILogger,
            lifetime=ServiceLifetime.SINGLETON,
            conditional_rules=[when_environment("ENVIRONMENT", "production")],
        )
        class ProductionLogger:
            def log(self, message: str):
                return f"[PROD] {message}"

        @injectable(
            ILogger,
            lifetime=ServiceLifetime.SINGLETON,
            conditional_rules=[when_environment("ENVIRONMENT", "development")],
        )
        class DevelopmentLogger:
            def log(self, message: str):
                return f"[DEV] {message}"

        @injectable(
            ILogger,
            lifetime=ServiceLifetime.SINGLETON,
            priority=-1,  # 低優先級,作為默認選項
        )
        class DefaultLogger:
            def log(self, message: str):
                return f"[DEFAULT] {message}"

        container = get_container()

        # 測試生產環境
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            logger = container.get(ILogger)
            assert isinstance(logger, ProductionLogger)

        # 重置單例
        container._singletons.clear()

        # 測試開發環境
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            logger = container.get(ILogger)
            assert isinstance(logger, DevelopmentLogger)

        # 重置單例
        container._singletons.clear()

        with patch.dict(os.environ, {"ENVIRONMENT": "unknown"}):
            logger = container.get(ILogger)
            assert isinstance(logger, DefaultLogger)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
