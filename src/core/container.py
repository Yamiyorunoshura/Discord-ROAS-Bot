"""企業級依賴注入容器 for Discord ROAS Bot"""

from __future__ import annotations

import asyncio
import inspect
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    get_type_hints,
)

from src.core.config import Settings, get_settings
from src.core.logger import BotLogger, get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

# 導入整合的服務模組
try:
    import os
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.cogs.core.cache_manager import MultiLevelCache, get_global_cache_manager
    from src.cogs.core.health_checker import HealthChecker, get_health_checker
except ImportError:
    # 如果無法導入舊模組,使用佔位符
    MultiLevelCache = None
    get_global_cache_manager = None
    HealthChecker = None
    get_health_checker = None

T = TypeVar("T")
P = TypeVar("P")


class ServiceLifetime(Enum):
    """服務生命週期枚舉"""

    SINGLETON = "singleton"  # 單例:整個應用程序生命週期內只有一個實例
    TRANSIENT = "transient"  # 暫時性:每次請求都創建新實例
    SCOPED = "scoped"  # 作用域:在特定範圍內是單例


class InjectionCondition(Enum):
    """條件注入類型"""

    ENVIRONMENT = "environment"  # 基於環境變數
    FEATURE_FLAG = "feature_flag"  # 基於功能開關
    CUSTOM = "custom"  # 自定義條件


@dataclass
class ConditionalRule:
    """條件注入規則"""

    condition_type: InjectionCondition
    key: str
    expected_value: Any
    condition_func: Callable[[], bool] | None = None


@dataclass
class PerformanceMetrics:
    """效能指標"""

    total_injections: int = 0
    avg_injection_time: float = 0.0
    max_injection_time: float = 0.0
    min_injection_time: float = float("inf")
    failed_injections: int = 0
    circular_dependencies_detected: int = 0


class ContainerException(Exception):
    """容器基礎異常"""

    pass


class ServiceNotFoundException(ContainerException):
    """服務未找到異常"""

    pass


class CircularDependencyException(ContainerException):
    """循環依賴異常"""

    pass


class ConditionalInjectionException(ContainerException):
    """條件注入異常"""

    pass


class ServiceDescriptor:
    """服務描述符 - 描述服務註冊信息"""

    def __init__(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | T,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        factory: Callable[..., T] | None = None,
        conditional_rules: list[ConditionalRule] | None = None,
        tags: list[str] | None = None,
        priority: int = 0,
    ):
        """初始化服務描述符

        Args:
            service_type: 服務接口/類型
            implementation: 實現類、工廠函數或實例
            lifetime: 服務生命週期
            factory: 可選的工廠函數
            conditional_rules: 條件注入規則
            tags: 服務標籤
            priority: 服務優先級(用於多實現選擇)
        """
        self.service_type = service_type
        self.implementation = implementation
        self.lifetime = lifetime
        self.factory = factory
        self.conditional_rules = conditional_rules or []
        self.tags = tags or []
        self.priority = priority
        self.instance: T | None = None
        self.created_at: float | None = None
        self.access_count: int = 0
        self.last_accessed: float | None = None

    def matches_conditions(self, context: dict[str, Any]) -> bool:
        """檢查是否符合條件注入規則"""
        if not self.conditional_rules:
            return True

        for rule in self.conditional_rules:
            if rule.condition_type == InjectionCondition.ENVIRONMENT:
                import os

                env_value = os.getenv(rule.key)
                if env_value != str(rule.expected_value):
                    return False
            elif rule.condition_type == InjectionCondition.FEATURE_FLAG:
                feature_flags = context.get("feature_flags", {})
                if feature_flags.get(rule.key) != rule.expected_value:
                    return False
            elif rule.condition_type == InjectionCondition.CUSTOM:
                if rule.condition_func and not rule.condition_func():
                    return False

        return True

    def update_access_stats(self):
        """更新訪問統計"""
        self.access_count += 1
        self.last_accessed = time.time()


class Container:
    """企業級依賴注入容器

    提供完整的企業級依賴注入功能:
    - 生命週期管理(Singleton, Scoped, Transient)
    - 條件注入支援
    - 泛型類型支援
    - 循環依賴檢測
    - 效能監控和診斷
    """

    def __init__(
        self, settings: Settings | None = None, enable_diagnostics: bool = True
    ):
        """初始化容器

        Args:
            settings: 可選的設定實例
            enable_diagnostics: 是否啟用診斷功能
        """
        self._settings = settings or get_settings()
        self._logger = get_logger("container", self._settings)
        self._enable_diagnostics = enable_diagnostics

        # 服務註冊表(支援多實現)
        self._services: dict[type, list[ServiceDescriptor]] = defaultdict(list)
        self._singletons: dict[type, Any] = {}
        self._scoped_instances: dict[str, dict[type, Any]] = defaultdict(dict)

        # 循環依賴檢測
        self._building: set[type] = set()
        self._resolution_stack: list[type] = []

        # 條件注入上下文
        self._injection_context: dict[str, Any] = {}

        # 效能監控
        self._metrics = PerformanceMetrics()
        self._injection_times: list[float] = []

        # 線程安全
        self._lock = threading.RLock()

        # 事件監聽器
        self._event_handlers: dict[str, list[Callable]] = defaultdict(list)

        # 註冊核心服務
        self._register_core_services()

    def _register_core_services(self) -> None:
        """註冊核心框架服務"""
        # 註冊設定為單例
        self.register_singleton(Settings, self._settings)

        # 註冊日誌工廠
        self.register_factory(BotLogger, self._create_logger, ServiceLifetime.SINGLETON)

        # 註冊容器本身
        self.register_singleton(Container, self)

        # 註冊緩存管理器(如果可用)
        if MultiLevelCache and get_global_cache_manager:
            self.register_factory(
                MultiLevelCache,
                lambda: get_global_cache_manager(),
                ServiceLifetime.SINGLETON,
            )

        # 註冊健康檢查器(如果可用)
        if HealthChecker and get_health_checker:
            self.register_factory(
                HealthChecker, lambda: get_health_checker(), ServiceLifetime.SINGLETON
            )

    def set_injection_context(self, context: dict[str, Any]) -> None:
        """設定注入上下文"""
        with self._lock:
            self._injection_context.update(context)

    def get_injection_context(self) -> dict[str, Any]:
        """獲取注入上下文"""
        with self._lock:
            return self._injection_context.copy()

    def add_event_handler(self, event: str, handler: Callable) -> None:
        """添加事件監聽器"""
        with self._lock:
            self._event_handlers[event].append(handler)

    def _fire_event(self, event: str, **kwargs) -> None:
        """觸發事件"""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(**kwargs)
            except Exception as e:
                self._logger.warning(f"事件處理器異常: {e}")

    def _create_logger(self, name: str = "default") -> BotLogger:
        """Factory for creating loggers."""
        return get_logger(name, self._settings)

    def register_singleton(
        self,
        service_type: type[T],
        implementation: type[T] | T | None = None,
        tags: list[str] | None = None,
        conditional_rules: list[ConditionalRule] | None = None,
    ) -> Container:
        """註冊單例服務

        Args:
            service_type: 要註冊的服務類型
            implementation: 實現類或實例
            tags: 服務標籤
            conditional_rules: 條件注入規則

        Returns:
            返回自身以支援鏈式調用
        """
        if implementation is None:
            implementation = service_type

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=ServiceLifetime.SINGLETON,
            tags=tags,
            conditional_rules=conditional_rules,
        )

        with self._lock:
            self._services[service_type].append(descriptor)
            self._logger.debug(f"註冊單例服務: {service_type.__name__}")
            self._fire_event(
                "service_registered", service_type=service_type, lifetime="singleton"
            )

        return self

    def register_transient(
        self,
        service_type: type[T],
        implementation: type[T] | None = None,
        tags: list[str] | None = None,
        conditional_rules: list[ConditionalRule] | None = None,
    ) -> Container:
        """註冊暫時性服務

        Args:
            service_type: 要註冊的服務類型
            implementation: 實現類
            tags: 服務標籤
            conditional_rules: 條件注入規則

        Returns:
            返回自身以支援鏈式調用
        """
        if implementation is None:
            implementation = service_type

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=ServiceLifetime.TRANSIENT,
            tags=tags,
            conditional_rules=conditional_rules,
        )

        with self._lock:
            self._services[service_type].append(descriptor)
            self._logger.debug(f"註冊暫時性服務: {service_type.__name__}")
            self._fire_event(
                "service_registered", service_type=service_type, lifetime="transient"
            )

        return self

    def register_scoped(
        self,
        service_type: type[T],
        implementation: type[T] | None = None,
        tags: list[str] | None = None,
        conditional_rules: list[ConditionalRule] | None = None,
    ) -> Container:
        """註冊作用域服務

        Args:
            service_type: 要註冊的服務類型
            implementation: 實現類
            tags: 服務標籤
            conditional_rules: 條件注入規則

        Returns:
            返回自身以支援鏈式調用
        """
        if implementation is None:
            implementation = service_type

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=ServiceLifetime.SCOPED,
            tags=tags,
            conditional_rules=conditional_rules,
        )

        with self._lock:
            self._services[service_type].append(descriptor)
            self._logger.debug(f"註冊作用域服務: {service_type.__name__}")
            self._fire_event(
                "service_registered", service_type=service_type, lifetime="scoped"
            )

        return self

    def register_factory(
        self,
        service_type: type[T],
        factory: Callable[..., T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        tags: list[str] | None = None,
        conditional_rules: list[ConditionalRule] | None = None,
    ) -> Container:
        """註冊服務工廠

        Args:
            service_type: 要註冊的服務類型
            factory: 工廠函數
            lifetime: 服務生命週期
            tags: 服務標籤
            conditional_rules: 條件注入規則

        Returns:
            返回自身以支援鏈式調用
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=factory,
            lifetime=lifetime,
            factory=factory,
            tags=tags,
            conditional_rules=conditional_rules,
        )

        with self._lock:
            self._services[service_type].append(descriptor)
            self._logger.debug(f"註冊工廠服務: {service_type.__name__}")
            self._fire_event(
                "service_registered", service_type=service_type, lifetime=lifetime.value
            )

        return self

    def get(
        self,
        service_type: type[T],
        scope: str | None = None,
        tags: list[str] | None = None,
    ) -> T:
        """獲取服務實例

        Args:
            service_type: 要獲取的服務類型
            scope: 作用域名稱(對於 scoped 服務)
            tags: 服務標籤過濾器

        Returns:
            服務實例

        Raises:
            ServiceNotFoundException: 如果服務未註冊
            CircularDependencyException: 如果檢測到循環依賴
        """
        start_time = time.time()

        try:
            return self._get_with_metrics(service_type, scope, tags, start_time)
        except Exception as e:
            self._metrics.failed_injections += 1
            self._logger.error(f"服務獲取失敗: {service_type.__name__} - {e}")
            raise

    def _get_with_metrics(
        self,
        service_type: type[T],
        scope: str | None,
        tags: list[str] | None,
        start_time: float,
    ) -> T:
        """帶有效能監控的獲取服務"""
        # 循環依賴檢測
        if service_type in self._building:
            self._metrics.circular_dependencies_detected += 1
            dependency_chain = (
                " -> ".join([t.__name__ for t in self._resolution_stack])
                + f" -> {service_type.__name__}"
            )
            raise CircularDependencyException(f"檢測到循環依賴: {dependency_chain}")

        # 尋找符合條件的服務描述符
        descriptor = self._find_matching_descriptor(service_type, tags)
        if descriptor is None:
            raise ServiceNotFoundException(f"服務未註冊: {service_type.__name__}")

        try:
            self._building.add(service_type)
            self._resolution_stack.append(service_type)

            instance = self._resolve_service(descriptor, scope)

            # 更新效能指標
            injection_time = time.time() - start_time
            self._update_metrics(injection_time)

            # 更新服務訪問統計
            descriptor.update_access_stats()

            # 觸發事件
            self._fire_event(
                "service_resolved",
                service_type=service_type,
                instance=instance,
                injection_time=injection_time,
            )

            return instance
        finally:
            self._building.discard(service_type)
            if self._resolution_stack and self._resolution_stack[-1] == service_type:
                self._resolution_stack.pop()

    def _find_matching_descriptor(
        self, service_type: type[T], tags: list[str] | None = None
    ) -> ServiceDescriptor | None:
        """尋找符合條件的服務描述符"""
        descriptors = self._services.get(service_type, [])
        if not descriptors:
            return None

        # 過濾符合條件的服務
        matching_descriptors = []
        for descriptor in descriptors:
            # 檢查條件注入規則
            if not descriptor.matches_conditions(self._injection_context):
                continue

            # 檢查標籤過濾
            if tags and not any(tag in descriptor.tags for tag in tags):
                continue

            matching_descriptors.append(descriptor)

        if not matching_descriptors:
            return None

        # 按優先級排序,返回最高優先級的服務
        matching_descriptors.sort(key=lambda d: d.priority, reverse=True)
        return matching_descriptors[0]

    def _update_metrics(self, injection_time: float) -> None:
        """更新效能指標"""
        self._metrics.total_injections += 1
        self._injection_times.append(injection_time)

        # 保持最近 1000 次注入的時間記錄
        if len(self._injection_times) > 1000:
            self._injection_times.pop(0)

        # 更新統計數据
        self._metrics.max_injection_time = max(
            self._metrics.max_injection_time, injection_time
        )
        self._metrics.min_injection_time = min(
            self._metrics.min_injection_time, injection_time
        )

        # 計算平均時間
        self._metrics.avg_injection_time = sum(self._injection_times) / len(
            self._injection_times
        )

    def _resolve_service(
        self, descriptor: ServiceDescriptor, scope: str | None = None
    ) -> Any:
        """根據服務描述符解析服務"""
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            return self._resolve_singleton(descriptor)
        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            return self._resolve_scoped(descriptor, scope or "default")
        else:  # TRANSIENT
            return self._resolve_transient(descriptor)

    def _resolve_singleton(self, descriptor: ServiceDescriptor) -> Any:
        """解析單例服務"""
        with self._lock:
            if descriptor.service_type in self._singletons:
                return self._singletons[descriptor.service_type]

            instance = self._create_instance(descriptor)
            self._singletons[descriptor.service_type] = instance
            descriptor.instance = instance
            descriptor.created_at = time.time()

            self._logger.debug(f"創建單例實例: {descriptor.service_type.__name__}")
            return instance

    def _resolve_scoped(self, descriptor: ServiceDescriptor, scope: str) -> Any:
        """解析作用域服務"""
        with self._lock:
            scope_dict = self._scoped_instances[scope]

            if descriptor.service_type in scope_dict:
                return scope_dict[descriptor.service_type]

            instance = self._create_instance(descriptor)
            scope_dict[descriptor.service_type] = instance

            self._logger.debug(
                f"在作用域 '{scope}' 中創建實例: {descriptor.service_type.__name__}"
            )
            return instance

    def _resolve_transient(self, descriptor: ServiceDescriptor) -> Any:
        """解析暫時性服務"""
        instance = self._create_instance(descriptor)
        self._logger.debug(f"創建暫時性實例: {descriptor.service_type.__name__}")
        return instance

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create an instance based on the descriptor."""
        implementation = descriptor.implementation

        # If it's already an instance, return it
        if not (inspect.isclass(implementation) or callable(implementation)):
            return implementation

        # If it's a factory function, use it
        if descriptor.factory:
            return self._call_with_injection(descriptor.factory)

        # If it's a class, instantiate it
        if inspect.isclass(implementation):
            return self._call_with_injection(implementation)

        # If it's a callable, call it
        if callable(implementation):
            return self._call_with_injection(implementation)

        return implementation

    def _call_with_injection(self, func: Callable) -> Any:
        """Call a function with dependency injection."""
        try:
            # Get function signature
            sig = inspect.signature(func)
            type_hints = get_type_hints(func)

            # Build arguments
            kwargs = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Get type from annotation
                param_type = type_hints.get(param_name, param.annotation)

                # Skip if no type annotation
                if param_type == inspect.Parameter.empty:
                    if param.default != inspect.Parameter.empty:
                        continue  # Has default value
                    else:
                        raise ValueError(
                            f"No type annotation for parameter '{param_name}' in {func}"
                        )

                # Resolve dependency
                try:
                    kwargs[param_name] = self.get(param_type)
                except ValueError:
                    # If dependency not found and has default, skip
                    if param.default != inspect.Parameter.empty:
                        continue
                    else:
                        raise

            return func(**kwargs)

        except Exception as e:
            self._logger.error(f"Failed to create instance of {func}: {e}")
            raise

    def clear_scoped(self, scope: str | None = None) -> None:
        """清除作用域實例

        Args:
            scope: 要清除的作用域名稱,如果為 None 則清除所有作用域
        """
        with self._lock:
            if scope is None:
                self._scoped_instances.clear()
                self._logger.debug("清除所有作用域實例")
            elif scope in self._scoped_instances:
                del self._scoped_instances[scope]
                self._logger.debug(f"清除作用域 '{scope}' 的實例")

    @contextmanager
    def create_scope(self, scope_name: str | None = None):
        """創建作用域上下文管理器

        Args:
            scope_name: 作用域名稱,如果為 None 則自動生成
        """
        if scope_name is None:
            scope_name = f"scope_{id(threading.current_thread())}_{time.time()}"

        try:
            self._logger.debug(f"創建作用域: {scope_name}")
            self._fire_event("scope_created", scope_name=scope_name)
            yield scope_name
        finally:
            self.clear_scoped(scope_name)
            self._fire_event("scope_disposed", scope_name=scope_name)
            self._logger.debug(f"釋放作用域: {scope_name}")

    def is_registered(self, service_type: type, tags: list[str] | None = None) -> bool:
        """檢查服務類型是否已註冊

        Args:
            service_type: 要檢查的服務類型
            tags: 服務標籤過濾器

        Returns:
            如果已註冊則返回 True,否則返回 False
        """
        with self._lock:
            return self._find_matching_descriptor(service_type, tags) is not None

    def get_services_by_tag(self, tag: str) -> list[type]:
        """根據標籤獲取服務類型列表

        Args:
            tag: 要搜索的標籤

        Returns:
            包含該標籤的所有服務類型
        """
        result = []
        with self._lock:
            for service_type, descriptors in self._services.items():
                for descriptor in descriptors:
                    if tag in descriptor.tags:
                        result.append(service_type)
                        break
        return result

    def unregister(self, service_type: type) -> bool:
        """取消註冊服務

        Args:
            service_type: 要取消註冊的服務類型

        Returns:
            如果成功取消註冊則返回 True
        """
        with self._lock:
            if service_type in self._services:
                del self._services[service_type]

                # 清除相關實例
                if service_type in self._singletons:
                    del self._singletons[service_type]

                for scope_dict in self._scoped_instances.values():
                    if service_type in scope_dict:
                        del scope_dict[service_type]

                self._logger.debug(f"取消註冊服務: {service_type.__name__}")
                self._fire_event("service_unregistered", service_type=service_type)
                return True

        return False

    def get_registration_info(self) -> dict[str, Any]:
        """獲取已註冊服務的信息

        Returns:
            包含註冊信息的字典
        """
        info = {
            "total_services": sum(
                len(descriptors) for descriptors in self._services.values()
            ),
            "total_types": len(self._services),
            "singletons_count": len(self._singletons),
            "scoped_instances_count": sum(
                len(scope_dict) for scope_dict in self._scoped_instances.values()
            ),
            "active_scopes": list(self._scoped_instances.keys()),
            "services": {},
        }

        with self._lock:
            for service_type, descriptors in self._services.items():
                service_info = []
                for descriptor in descriptors:
                    service_info.append(
                        {
                            "lifetime": descriptor.lifetime.value,
                            "implementation": (
                                descriptor.implementation.__name__
                                if hasattr(descriptor.implementation, "__name__")
                                else str(descriptor.implementation)
                            ),
                            "tags": descriptor.tags,
                            "priority": descriptor.priority,
                            "access_count": descriptor.access_count,
                            "last_accessed": descriptor.last_accessed,
                            "created_at": descriptor.created_at,
                            "has_singleton_instance": service_type in self._singletons,
                            "conditional_rules_count": len(
                                descriptor.conditional_rules
                            ),
                        }
                    )

                info["services"][service_type.__name__] = service_info

        return info

    def get_performance_metrics(self) -> PerformanceMetrics:
        """獲取效能指標

        Returns:
            現在的效能指標
        """
        with self._lock:
            return PerformanceMetrics(
                total_injections=self._metrics.total_injections,
                avg_injection_time=self._metrics.avg_injection_time,
                max_injection_time=self._metrics.max_injection_time,
                min_injection_time=self._metrics.min_injection_time
                if self._metrics.min_injection_time != float("inf")
                else 0.0,
                failed_injections=self._metrics.failed_injections,
                circular_dependencies_detected=self._metrics.circular_dependencies_detected,
            )

    def reset_metrics(self) -> None:
        """重置效能指標"""
        with self._lock:
            self._metrics = PerformanceMetrics()
            self._injection_times.clear()
            self._logger.debug("效能指標已重置")

    def create_child_container(self) -> Container:
        """創建子容器(繼承父容器的註冊)

        Returns:
            新的子容器實例
        """
        child = Container(self._settings, self._enable_diagnostics)

        # 複製父容器的服務註冊
        with self._lock:
            for service_type, descriptors in self._services.items():
                child._services[service_type] = descriptors.copy()

        # 複製注入上下文
        child._injection_context = self._injection_context.copy()

        self._logger.debug("創建子容器")
        return child

    def validate_dependencies(self) -> list[str]:
        """驗證所有註冊服務的依賴關係

        Returns:
            驗證錯誤列表(空列表表示沒有錯誤)
        """
        errors = []

        with self._lock:
            for service_type, descriptors in self._services.items():
                for descriptor in descriptors:
                    try:
                        # 嘗試獲取服務來驗證依賴
                        if descriptor.lifetime == ServiceLifetime.SINGLETON:
                            # 對於單例服務,檢查是否能正常創建
                            if service_type not in self._singletons:
                                self.get(service_type)
                        else:
                            # 對於非單例服務,只檢查構造函數簽名
                            self._validate_constructor_dependencies(descriptor)
                    except Exception as e:
                        errors.append(f"{service_type.__name__}: {e!s}")

        return errors

    def _validate_constructor_dependencies(self, descriptor: ServiceDescriptor) -> None:
        """驗證構造函數依賴"""
        implementation = descriptor.implementation

        if descriptor.factory:
            func = descriptor.factory
        elif inspect.isclass(implementation):
            func = implementation.__init__
        else:
            return  # 無法驗證

        # 檢查構造函數參數
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = type_hints.get(param_name, param.annotation)

            if param_type != inspect.Parameter.empty and (
                not self.is_registered(param_type)
                and param.default == inspect.Parameter.empty
            ):
                raise ServiceNotFoundException(f"依賴服務未註冊: {param_type}")


# 全局容器實例
_container: Container | None = None
_container_lock = threading.RLock()


def get_container() -> Container:
    """獲取全局容器實例"""
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = Container()
    return _container


def reset_container() -> None:
    """重置全局容器(主要用於測試)"""
    global _container
    with _container_lock:
        _container = None


def configure_container(configurator: Callable[[Container], None]) -> Container:
    """配置全局容器

    Args:
        configurator: 配置函數,接收容器實例作為參數

    Returns:
        配置後的容器實例
    """
    container = get_container()
    configurator(container)
    return container


# 裝飾器和工具函數


def injectable[T](
    service_type: type[T] | None = None,
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    tags: list[str] | None = None,
    conditional_rules: list[ConditionalRule] | None = None,
) -> Callable[[type[T]], type[T]]:
    """服務註冊裝飾器

    Args:
        service_type: 服務類型(如果為 None 則使用裝飾的類型)
        lifetime: 服務生命週期
        tags: 服務標籤
        conditional_rules: 條件注入規則

    Returns:
        裝飾器函數
    """

    def decorator(cls: type[T]) -> type[T]:
        container = get_container()
        actual_service_type = service_type or cls

        if lifetime == ServiceLifetime.SINGLETON:
            container.register_singleton(
                actual_service_type, cls, tags=tags, conditional_rules=conditional_rules
            )
        elif lifetime == ServiceLifetime.SCOPED:
            container.register_scoped(
                actual_service_type, cls, tags=tags, conditional_rules=conditional_rules
            )
        else:
            container.register_transient(
                actual_service_type, cls, tags=tags, conditional_rules=conditional_rules
            )

        return cls

    return decorator


def singleton[T](
    service_type: type[T] | None = None,
    tags: list[str] | None = None,
    conditional_rules: list[ConditionalRule] | None = None,
) -> Callable[[type[T]], type[T]]:
    """單例服務註冊裝飾器"""
    return injectable(service_type, ServiceLifetime.SINGLETON, tags, conditional_rules)


def scoped[T](
    service_type: type[T] | None = None,
    tags: list[str] | None = None,
    conditional_rules: list[ConditionalRule] | None = None,
) -> Callable[[type[T]], type[T]]:
    """作用域服務註冊裝飾器"""
    return injectable(service_type, ServiceLifetime.SCOPED, tags, conditional_rules)


def transient[T](
    service_type: type[T] | None = None,
    tags: list[str] | None = None,
    conditional_rules: list[ConditionalRule] | None = None,
) -> Callable[[type[T]], type[T]]:
    """暫時性服務註冊裝飾器"""
    return injectable(service_type, ServiceLifetime.TRANSIENT, tags, conditional_rules)


def inject(func: Callable) -> Callable:
    """依賴注入裝飾器

    Args:
        func: 要注入依賴的函數

    Returns:
        包裝後的函數,自動注入依賴
    """
    container = get_container()

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 獲取函數簽名
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        # 構建注入的參數
        injected_kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name in kwargs:
                continue  # 已提供的參數

            # 從注釋中獲取類型
            param_type = type_hints.get(param_name, param.annotation)

            # 如果沒有類型注釋則跳過
            if param_type == inspect.Parameter.empty:
                continue

            # 嘗試解析依賴
            try:
                injected_kwargs[param_name] = container.get(param_type)
            except (ServiceNotFoundException, CircularDependencyException):
                # 如果依賴未找到且沒有預設值,則跳過
                if param.default == inspect.Parameter.empty:
                    continue

        # Merge provided and injected kwargs
        final_kwargs = {**injected_kwargs, **kwargs}
        return func(*args, **final_kwargs)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        # 異步函數的相同邏輯
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        injected_kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name in kwargs:
                continue

            param_type = type_hints.get(param_name, param.annotation)

            if param_type == inspect.Parameter.empty:
                continue

            try:
                injected_kwargs[param_name] = container.get(param_type)
            except (ServiceNotFoundException, CircularDependencyException):
                if param.default == inspect.Parameter.empty:
                    continue

        final_kwargs = {**injected_kwargs, **kwargs}
        return await func(*args, **final_kwargs)

    # Return appropriate wrapper based on function type
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper


# 條件注入工具函數


def when_environment(key: str, value: Any) -> ConditionalRule:
    """創建環境變數條件規則"""
    return ConditionalRule(
        condition_type=InjectionCondition.ENVIRONMENT, key=key, expected_value=value
    )


def when_feature_flag(flag_name: str, enabled: bool = True) -> ConditionalRule:
    """創建功能開關條件規則"""
    return ConditionalRule(
        condition_type=InjectionCondition.FEATURE_FLAG,
        key=flag_name,
        expected_value=enabled,
    )


def when_custom(condition_func: Callable[[], bool]) -> ConditionalRule:
    """創建自定義條件規則"""
    return ConditionalRule(
        condition_type=InjectionCondition.CUSTOM,
        key="custom",
        expected_value=True,
        condition_func=condition_func,
    )


# (為了向後兼容性,保留舊名稱)
Lifetime = ServiceLifetime


__all__ = [
    "CircularDependencyException",
    "ConditionalInjectionException",
    "ConditionalRule",
    # 核心類別
    "Container",
    # 異常類別
    "ContainerException",
    # 條件注入
    "InjectionCondition",
    "Lifetime",  # 舊名稱,向後兼容
    # 效能監控
    "PerformanceMetrics",
    "ServiceDescriptor",
    "ServiceLifetime",
    "ServiceNotFoundException",
    "configure_container",
    # 全局函數
    "get_container",
    "inject",
    # 裝飾器
    "injectable",
    "reset_container",
    "scoped",
    "singleton",
    "transient",
    "when_custom",
    # 條件注入工具
    "when_environment",
    "when_feature_flag",
]
