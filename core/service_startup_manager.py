"""
服務啟動管理器
Task ID: 9 - 重構現有模組以符合新架構

這個模組提供統一的服務啟動和依賴注入管理：
- 服務發現和自動註冊
- 依賴順序解析
- 批次初始化和清理
- 健康檢查和監控
- 錯誤恢復機制
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type, Any, Set
from datetime import datetime

from core.base_service import BaseService, service_registry
from core.database_manager import get_database_manager
from core.exceptions import ServiceError, handle_errors

logger = logging.getLogger('core.service_startup_manager')


class ServiceStartupManager:
    """
    服務啟動管理器
    
    負責協調所有服務的啟動、依賴注入和生命週期管理
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化服務啟動管理器
        
        參數：
            config: 配置參數
        """
        self.config = config or {}
        
        # 從配置獲取參數
        self.init_timeout = self.config.get('service_init_timeout', 30)
        self.cleanup_timeout = self.config.get('service_cleanup_timeout', 15)
        self.batch_size = self.config.get('service_batch_size', 5)
        self.health_check_interval = self.config.get('service_health_check_interval', 300)
        
        # 服務發現註冊表
        self.discovered_services: Dict[str, Type[BaseService]] = {}
        self.service_instances: Dict[str, BaseService] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}
        
        # 狀態追蹤
        self.initialization_started = False
        self.initialization_completed = False
        self.startup_time: Optional[datetime] = None
        
        logger.info("服務啟動管理器已初始化")
    
    def register_service_type(self, service_type: Type[BaseService], name: Optional[str] = None) -> str:
        """
        註冊服務類型
        
        參數：
            service_type: 服務類型
            name: 服務名稱，如果不提供則使用類別名稱
            
        返回：
            服務名稱
        """
        service_name = name or service_type.__name__
        
        if service_name in self.discovered_services:
            logger.warning(f"服務類型 {service_name} 已經註冊，將覆蓋")
        
        self.discovered_services[service_name] = service_type
        self.dependency_graph[service_name] = set()
        
        logger.info(f"註冊服務類型：{service_name}")
        return service_name
    
    def add_service_dependency(self, service_name: str, dependency_name: str):
        """
        添加服務依賴關係
        
        參數：
            service_name: 服務名稱
            dependency_name: 依賴的服務名稱
        """
        if service_name not in self.dependency_graph:
            self.dependency_graph[service_name] = set()
        
        self.dependency_graph[service_name].add(dependency_name)
        logger.debug(f"添加服務依賴：{service_name} -> {dependency_name}")
    
    def get_initialization_order(self) -> List[str]:
        """
        根據依賴關係計算服務初始化順序（拓撲排序）
        
        返回：
            按初始化順序排列的服務名稱列表
        """
        # 計算入度
        in_degree = {name: 0 for name in self.discovered_services.keys()}
        
        for service_name, deps in self.dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[service_name] += 1
        
        # 拓撲排序
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            # 移除當前節點的所有邊
            for service_name, deps in self.dependency_graph.items():
                if current in deps:
                    in_degree[service_name] -= 1
                    if in_degree[service_name] == 0:
                        queue.append(service_name)
        
        if len(result) != len(self.discovered_services):
            cycle_services = [name for name, degree in in_degree.items() if degree > 0]
            raise ServiceError(
                f"服務依賴關係中存在循環依賴：{cycle_services}",
                service_name="ServiceStartupManager",
                operation="get_initialization_order"
            )
        
        return result
    
    @handle_errors(log_errors=True)
    async def initialize_all_services(self) -> bool:
        """
        初始化所有已發現的服務
        
        返回：
            是否全部初始化成功
        """
        if self.initialization_started:
            logger.warning("服務初始化已經開始，跳過重複初始化")
            return self.initialization_completed
        
        self.initialization_started = True
        self.startup_time = datetime.now()
        
        try:
            logger.info("開始初始化所有服務...")
            
            # 確保資料庫管理器優先初始化
            db_manager = await get_database_manager()
            if not db_manager.is_initialized:
                logger.error("資料庫管理器初始化失敗")
                return False
            
            # 獲取初始化順序
            initialization_order = self.get_initialization_order()
            logger.info(f"服務初始化順序：{' -> '.join(initialization_order)}")
            
            # 批次初始化服務
            success_count = 0
            total_count = len(initialization_order)
            
            for i, service_name in enumerate(initialization_order):
                logger.info(f"初始化服務 {i+1}/{total_count}：{service_name}")
                
                try:
                    # 創建服務實例
                    service_type = self.discovered_services[service_name]
                    service_instance = await self._create_service_instance(service_type, service_name)
                    
                    if service_instance:
                        # 註冊到全域服務註冊表
                        await service_registry.register_service(service_instance, service_name)
                        
                        # 初始化服務
                        success = await service_instance.initialize()
                        
                        if success:
                            self.service_instances[service_name] = service_instance
                            success_count += 1
                            logger.info(f"服務 {service_name} 初始化成功")
                        else:
                            logger.error(f"服務 {service_name} 初始化失敗")
                            return False
                    else:
                        logger.error(f"創建服務實例失敗：{service_name}")
                        return False
                
                except Exception as e:
                    logger.exception(f"初始化服務 {service_name} 時發生錯誤")
                    return False
            
            self.initialization_completed = (success_count == total_count)
            
            if self.initialization_completed:
                elapsed = (datetime.now() - self.startup_time).total_seconds()
                logger.info(f"所有服務初始化完成，耗時 {elapsed:.2f} 秒")
            else:
                logger.error(f"服務初始化不完整：{success_count}/{total_count} 成功")
            
            return self.initialization_completed
            
        except Exception as e:
            logger.exception("服務初始化過程中發生未預期錯誤")
            return False
    
    async def _create_service_instance(self, service_type: Type[BaseService], service_name: str) -> Optional[BaseService]:
        """
        創建服務實例
        
        參數：
            service_type: 服務類型
            service_name: 服務名稱
            
        返回：
            服務實例
        """
        try:
            # 獲取資料庫管理器
            db_manager = await get_database_manager()
            
            # 根據服務類型創建實例
            if service_name == "ActivityService":
                from services.activity import ActivityService
                config = {
                    'fonts_dir': self.config.get('fonts_dir', 'fonts'),
                    'default_font': self.config.get('default_font', 'fonts/NotoSansCJKtc-Regular.otf')
                }
                return ActivityService(db_manager, config)
            
            elif service_name == "WelcomeService":
                from services.welcome import WelcomeService
                config = {
                    'bg_dir': self.config.get('bg_dir', 'data/backgrounds'),
                    'fonts_dir': self.config.get('fonts_dir', 'fonts'),
                    'default_font': self.config.get('default_font', 'fonts/NotoSansCJKtc-Regular.otf')
                }
                return WelcomeService(db_manager, config)
            
            elif service_name == "MessageService":
                from services.message import MessageService
                config = {
                    'fonts_dir': self.config.get('fonts_dir', 'fonts'),
                    'default_font': self.config.get('default_font', 'fonts/NotoSansCJKtc-Regular.otf')
                }
                return MessageService(db_manager, config)
            
            else:
                # 通用服務創建（假設服務接受 DatabaseManager）
                try:
                    return service_type(db_manager)
                except TypeError:
                    # 如果服務不需要 DatabaseManager
                    return service_type()
            
        except Exception as e:
            logger.exception(f"創建服務實例失敗：{service_name}")
            return None
    
    @handle_errors(log_errors=True)
    async def cleanup_all_services(self) -> None:
        """
        清理所有服務
        """
        if not self.initialization_completed:
            logger.info("服務未完全初始化，跳過清理")
            return
        
        logger.info("開始清理所有服務...")
        
        try:
            # 按初始化順序的反向清理
            cleanup_order = list(reversed(list(self.service_instances.keys())))
            
            for service_name in cleanup_order:
                try:
                    service = self.service_instances.get(service_name)
                    if service and service.is_initialized:
                        logger.info(f"清理服務：{service_name}")
                        await asyncio.wait_for(service.cleanup(), timeout=self.cleanup_timeout)
                        logger.info(f"服務 {service_name} 已清理")
                
                except asyncio.TimeoutError:
                    logger.warning(f"服務 {service_name} 清理超時")
                except Exception as e:
                    logger.error(f"清理服務 {service_name} 時發生錯誤：{e}")
            
            # 清理全域服務註冊表
            await service_registry.cleanup_all_services()
            
            # 重置狀態
            self.service_instances.clear()
            self.initialization_completed = False
            self.initialization_started = False
            
            logger.info("所有服務清理完成")
            
        except Exception as e:
            logger.exception("服務清理過程中發生錯誤")
    
    async def get_service_health_status(self) -> Dict[str, Any]:
        """
        獲取所有服務的健康狀態
        
        返回：
            服務健康狀態報告
        """
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "startup_manager": {
                "initialized": self.initialization_completed,
                "startup_time": self.startup_time.isoformat() if self.startup_time else None,
                "service_count": len(self.service_instances)
            },
            "services": {}
        }
        
        for service_name, service in self.service_instances.items():
            try:
                service_health = await service.health_check()
                health_report["services"][service_name] = service_health
            except Exception as e:
                health_report["services"][service_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return health_report
    
    def get_startup_summary(self) -> Dict[str, Any]:
        """
        獲取啟動摘要資訊
        
        返回：
            啟動摘要
        """
        elapsed_time = None
        if self.startup_time:
            elapsed_time = (datetime.now() - self.startup_time).total_seconds()
        
        return {
            "initialized": self.initialization_completed,
            "started": self.initialization_started,
            "startup_time": self.startup_time.isoformat() if self.startup_time else None,
            "elapsed_seconds": elapsed_time,
            "discovered_services": len(self.discovered_services),
            "active_services": len(self.service_instances),
            "service_names": list(self.service_instances.keys())
        }


# 全域服務啟動管理器實例
startup_manager = None


async def get_startup_manager(config: Optional[Dict[str, Any]] = None) -> ServiceStartupManager:
    """
    獲取全域服務啟動管理器實例
    
    參數：
        config: 配置參數
        
    返回：
        服務啟動管理器實例
    """
    global startup_manager
    if not startup_manager:
        startup_manager = ServiceStartupManager(config)
        
        # 自動發現和註冊常用服務類型
        try:
            from services.activity import ActivityService
            startup_manager.register_service_type(ActivityService, "ActivityService")
        except ImportError:
            pass
        
        try:
            from services.welcome import WelcomeService
            startup_manager.register_service_type(WelcomeService, "WelcomeService")
        except ImportError:
            pass
        
        try:
            from services.message import MessageService
            startup_manager.register_service_type(MessageService, "MessageService")
        except ImportError:
            pass
        
        try:
            from services.achievement import AchievementService
            startup_manager.register_service_type(AchievementService, "AchievementService")
        except ImportError:
            pass
        
        try:
            from services.economy import EconomyService
            startup_manager.register_service_type(EconomyService, "EconomyService")
        except ImportError:
            pass
        
        try:
            from services.government import GovernmentService
            startup_manager.register_service_type(GovernmentService, "GovernmentService")
        except ImportError:
            pass
        
        logger.info(f"服務發現完成，找到 {len(startup_manager.discovered_services)} 個服務類型")
    
    return startup_manager
