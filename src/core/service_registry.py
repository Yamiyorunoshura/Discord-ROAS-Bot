"""
服務註冊機制
Task ID: 1 - 核心架構和基礎設施建置

這個模組提供統一的服務註冊機制，包括：
- 擴展現有ServiceRegistry以支援新的服務類型
- 部署服務(DeploymentService)註冊和管理
- 子機器人服務(SubBotService)註冊和管理  
- AI服務(AIService)註冊和管理
- 服務健康狀態監控和報告
- 動態服務註冊和解除註冊
- 服務間依賴關係管理
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Type, TypeVar
from datetime import datetime

# 導入現有的基礎服務架構
from core.base_service import (
    ServiceRegistry as BaseServiceRegistry,
    BaseService, 
    ServiceType,
    service_registry as global_service_registry
)
from src.core.service_lifecycle import (
    ServiceLifecycleManager,
    ServiceStatus,
    HealthStatus,
    lifecycle_manager as global_lifecycle_manager
)

logger = logging.getLogger('core.service_registry')

T = TypeVar('T', bound='BaseService')


class ExtendedServiceRegistry(BaseServiceRegistry):
    """
    擴展的服務註冊機制
    
    在原有ServiceRegistry基礎上增加對v2.4.4新服務類型的特殊支援：
    - DeploymentService（部署服務）
    - SubBotService（子機器人服務）
    - AIService（AI服務）
    
    同時整合服務生命週期管理器，提供更完善的服務狀態監控
    """
    
    def __init__(self, lifecycle_manager: Optional[ServiceLifecycleManager] = None):
        """
        初始化擴展的服務註冊機制
        
        參數：
            lifecycle_manager: 服務生命週期管理器實例
        """
        super().__init__()
        self.lifecycle_manager = lifecycle_manager or global_lifecycle_manager
        
        # 服務類型計數器，用於統計
        self._service_type_counts: Dict[ServiceType, int] = {
            service_type: 0 for service_type in ServiceType
        }
        
        # 服務啟動歷史記錄
        self._service_registration_history: List[Dict[str, Any]] = []
        
        # 服務依賴關係圖
        self._service_dependencies: Dict[str, List[str]] = {}
        self._dependent_services: Dict[str, List[str]] = {}
        
        # 服務優先級管理
        self._service_priorities: Dict[str, int] = {}
        
        # 自動恢復配置
        self._auto_recovery_enabled: Dict[str, bool] = {}
        self._recovery_strategies: Dict[str, str] = {}
        
    async def register_service(
        self, 
        service: BaseService, 
        name: Optional[str] = None,
        force_reregister: bool = False,
        dependencies: Optional[List[str]] = None,
        priority: int = 100,
        auto_recovery: bool = True,
        recovery_strategy: str = 'restart'
    ) -> str:
        """
        擴展的服務註冊方法
        
        在基礎註冊功能上增加生命週期管理器整合和依賴管理
        
        參數：
            service: 服務實例
            name: 服務名稱
            force_reregister: 是否強制重新註冊
            dependencies: 服務依賴列表
            priority: 服務啟動優先級（數字越小優先級越高）
            auto_recovery: 是否啟用自動恢復
            recovery_strategy: 恢復策略（'restart', 'recreate', 'manual'）
        """
        # 驗證依賴服務是否存在
        if dependencies:
            await self._validate_dependencies(dependencies)
        
        # 調用基類註冊方法
        service_name = await super().register_service(service, name, force_reregister)
        
        # 向生命週期管理器註冊服務
        self.lifecycle_manager.register_service(service_name, service)
        
        # 設置服務依賴關係
        if dependencies:
            await self._setup_service_dependencies(service_name, dependencies)
        
        # 設置服務配置
        self._service_priorities[service_name] = priority
        self._auto_recovery_enabled[service_name] = auto_recovery
        self._recovery_strategies[service_name] = recovery_strategy
        
        # 更新服務類型計數
        service_type = getattr(service, 'service_metadata', {}).get('service_type', ServiceType.BASE)
        if service_type in self._service_type_counts:
            self._service_type_counts[service_type] += 1
        else:
            # 如果是新的服務類型，初始化計數器
            self._service_type_counts[service_type] = 1
        
        # 記錄註冊歷史
        self._service_registration_history.append({
            'service_name': service_name,
            'service_type': service_type.value if isinstance(service_type, ServiceType) else str(service_type),
            'dependencies': dependencies or [],
            'priority': priority,
            'auto_recovery': auto_recovery,
            'registered_at': datetime.now().isoformat(),
            'action': 'registered'
        })
        
        logger.info(f"服務 {service_name} 已註冊並整合到生命週期管理器（優先級: {priority}，依賴: {dependencies or 'None'}）")
        return service_name
    
    async def unregister_service(self, name: str, force: bool = False) -> bool:
        """
        擴展的服務解除註冊方法
        
        在基礎解除註冊功能上增加生命週期管理器整合和依賴檢查
        
        參數：
            name: 服務名稱
            force: 是否強制解除註冊（忽略依賴檢查）
        """
        # 檢查是否有其他服務依賴此服務
        if not force and name in self._dependent_services:
            dependent_list = self._dependent_services[name]
            if dependent_list:
                active_dependents = [dep for dep in dependent_list if dep in self._services]
                if active_dependents:
                    logger.error(f"無法解除註冊服務 {name}，因為有其他服務依賴它: {active_dependents}")
                    return False
        
        # 獲取服務信息用於計數器更新
        service = self.get_service(name)
        service_type = None
        if service and hasattr(service, 'service_metadata'):
            service_type = service.service_metadata.get('service_type', ServiceType.BASE)
        
        # 調用基類解除註冊方法
        success = await super().unregister_service(name)
        
        if success:
            # 從生命週期管理器取消註冊
            self.lifecycle_manager.unregister_service(name)
            
            # 清理依賴關係
            await self._cleanup_service_dependencies(name)
            
            # 清理服務配置
            self._service_priorities.pop(name, None)
            self._auto_recovery_enabled.pop(name, None)
            self._recovery_strategies.pop(name, None)
            
            # 更新服務類型計數
            if service_type and service_type in self._service_type_counts:
                self._service_type_counts[service_type] = max(0, self._service_type_counts[service_type] - 1)
            elif service_type:
                # 如果是未知的服務類型，記錄但不出錯
                logger.warning(f"嘗試解除註冊未知服務類型: {service_type}")
            
            # 記錄解除註冊歷史
            self._service_registration_history.append({
                'service_name': name,
                'service_type': service_type.value if isinstance(service_type, ServiceType) else str(service_type),
                'unregistered_at': datetime.now().isoformat(),
                'action': 'unregistered'
            })
            
            logger.info(f"服務 {name} 已解除註冊並從生命週期管理器移除")
        
        return success
    
    # ========== 依賴關係管理方法 ==========
    
    async def _validate_dependencies(self, dependencies: List[str]) -> None:
        """
        驗證服務依賴是否存在
        
        Args:
            dependencies: 依賴服務名稱列表
        """
        missing_deps = []
        for dep in dependencies:
            if dep not in self._services:
                missing_deps.append(dep)
        
        if missing_deps:
            raise ValueError(f"缺少依賴服務: {missing_deps}")
    
    async def _setup_service_dependencies(self, service_name: str, dependencies: List[str]) -> None:
        """
        建立服務依賴關係
        
        Args:
            service_name: 服務名稱
            dependencies: 依賴服務列表
        """
        self._service_dependencies[service_name] = dependencies.copy()
        
        # 建立反向依賴關係
        for dep in dependencies:
            if dep not in self._dependent_services:
                self._dependent_services[dep] = []
            if service_name not in self._dependent_services[dep]:
                self._dependent_services[dep].append(service_name)
        
        logger.debug(f"已建立服務 {service_name} 的依賴關係: {dependencies}")
    
    async def _cleanup_service_dependencies(self, service_name: str) -> None:
        """
        清理服務的依賴關係
        
        Args:
            service_name: 服務名稱
        """
        # 清理該服務的依賴列表
        if service_name in self._service_dependencies:
            dependencies = self._service_dependencies[service_name]
            for dep in dependencies:
                if dep in self._dependent_services:
                    if service_name in self._dependent_services[dep]:
                        self._dependent_services[dep].remove(service_name)
                    # 如果沒有其他服務依賴此服務，清理空列表
                    if not self._dependent_services[dep]:
                        del self._dependent_services[dep]
            
            del self._service_dependencies[service_name]
        
        # 清理被此服務依賴的關係
        if service_name in self._dependent_services:
            del self._dependent_services[service_name]
    
    def get_service_dependencies(self, service_name: str) -> List[str]:
        """
        獲取服務的依賴列表
        
        Args:
            service_name: 服務名稱
            
        Returns:
            依賴服務名稱列表
        """
        return self._service_dependencies.get(service_name, [])
    
    def get_dependent_services(self, service_name: str) -> List[str]:
        """
        獲取依賴此服務的服務列表
        
        Args:
            service_name: 服務名稱
            
        Returns:
            依賴此服務的服務名稱列表
        """
        return self._dependent_services.get(service_name, [])
    
    async def start_service_with_dependencies(self, service_name: str) -> bool:
        """
        按依賴順序啟動服務
        
        Args:
            service_name: 服務名稱
            
        Returns:
            是否啟動成功
        """
        try:
            # 獲取啟動順序
            startup_order = await self._calculate_startup_order([service_name])
            
            # 按順序啟動服務
            for svc_name in startup_order:
                if svc_name not in self._services:
                    logger.error(f"服務 {svc_name} 不存在，無法啟動")
                    return False
                
                service = self._services[svc_name]
                if hasattr(service, 'start') and not service.is_initialized:
                    try:
                        await service.start()
                        self.lifecycle_manager.update_service_status(
                            svc_name, 
                            ServiceStatus.RUNNING,
                            "服務已按依賴順序啟動"
                        )
                    except Exception as e:
                        logger.error(f"啟動服務 {svc_name} 失敗: {e}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"按依賴順序啟動服務失敗: {e}")
            return False
    
    async def stop_service_with_dependents(self, service_name: str, force: bool = False) -> bool:
        """
        停止服務及所有依賴它的服務
        
        Args:
            service_name: 服務名稱
            force: 是否強制停止
            
        Returns:
            是否停止成功
        """
        try:
            # 獲取需要停止的服務列表（包含所有依賴者）
            services_to_stop = await self._calculate_shutdown_order(service_name)
            
            # 按順序停止服務
            for svc_name in services_to_stop:
                if svc_name not in self._services:
                    continue
                
                service = self._services[svc_name]
                if hasattr(service, 'stop') and service.is_initialized:
                    try:
                        await service.stop()
                        self.lifecycle_manager.update_service_status(
                            svc_name,
                            ServiceStatus.STOPPED,
                            "服務已按依賴順序停止"
                        )
                    except Exception as e:
                        if not force:
                            logger.error(f"停止服務 {svc_name} 失敗: {e}")
                            return False
                        else:
                            logger.warning(f"強制停止模式下忽略服務 {svc_name} 停止錯誤: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"按依賴順序停止服務失敗: {e}")
            return False
    
    async def _calculate_startup_order(self, target_services: List[str]) -> List[str]:
        """
        計算服務啟動順序（拓撲排序）
        
        Args:
            target_services: 目標服務列表
            
        Returns:
            按依賴順序排列的服務名稱列表
        """
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(service_name: str):
            if service_name in temp_visited:
                raise ValueError(f"檢測到循環依賴: {service_name}")
            if service_name in visited:
                return
            
            temp_visited.add(service_name)
            dependencies = self._service_dependencies.get(service_name, [])
            for dep in dependencies:
                visit(dep)
            
            temp_visited.remove(service_name)
            visited.add(service_name)
            order.append(service_name)
        
        for service in target_services:
            if service not in visited:
                visit(service)
        
        return order
    
    async def _calculate_shutdown_order(self, service_name: str) -> List[str]:
        """
        計算服務停止順序（依賴者優先）
        
        Args:
            service_name: 目標服務名稱
            
        Returns:
            按停止順序排列的服務名稱列表
        """
        to_stop = set()
        
        def collect_dependents(svc_name: str):
            to_stop.add(svc_name)
            dependents = self._dependent_services.get(svc_name, [])
            for dep in dependents:
                if dep not in to_stop:
                    collect_dependents(dep)
        
        collect_dependents(service_name)
        
        # 按優先級排序（依賴者先停止）
        ordered_list = list(to_stop)
        ordered_list.sort(key=lambda x: self._service_priorities.get(x, 100), reverse=True)
        
        return ordered_list
    
    async def register_deployment_service(
        self, 
        service: BaseService,
        deployment_mode: str,
        name: Optional[str] = None,
        environment_config: Optional[Dict[str, Any]] = None,
        auto_restart: bool = True
    ) -> str:
        """
        註冊部署服務
        
        參數：
            service: 部署服務實例
            deployment_mode: 部署模式 ('docker', 'uv', 'fallback')
            name: 服務名稱
            environment_config: 環境配置
            auto_restart: 是否自動重啟
            
        返回：
            服務名稱
        """
        # 先使用基類方法設置基本元數據
        service_name = await super().register_deployment_service(service, deployment_mode, name)
        
        # 擴展元數據，增加部署服務特定配置
        if hasattr(service, 'service_metadata'):
            service.service_metadata.update({
                'environment_config': environment_config or {},
                'auto_restart': auto_restart,
                'deployment_capabilities': {
                    'docker_support': deployment_mode == 'docker',
                    'uv_support': deployment_mode == 'uv',
                    'fallback_mode': deployment_mode == 'fallback'
                },
                'registration_timestamp': datetime.now().isoformat()
            })
        
        # 在生命週期管理器中設置特殊狀態監控
        self.lifecycle_manager.update_service_status(
            service_name, 
            ServiceStatus.CREATED,
            f"部署服務已註冊（模式: {deployment_mode}）"
        )
        
        logger.info(f"部署服務 {service_name} 註冊完成，模式: {deployment_mode}")
        return service_name
    
    async def register_sub_bot_service(
        self,
        service: BaseService,
        bot_id: str,
        target_channels: List[str],
        name: Optional[str] = None,
        ai_integration: bool = False,
        rate_limit_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        註冊子機器人服務
        
        參數：
            service: 子機器人服務實例
            bot_id: 子機器人ID
            target_channels: 目標頻道列表
            name: 服務名稱
            ai_integration: 是否集成AI功能
            rate_limit_config: 速率限制配置
            
        返回：
            服務名稱
        """
        # 先使用基類方法設置基本元數據
        service_name = await super().register_sub_bot_service(service, bot_id, target_channels, name)
        
        # 擴展元數據，增加子機器人特定配置
        if hasattr(service, 'service_metadata'):
            service.service_metadata.update({
                'ai_integration': ai_integration,
                'rate_limit_config': rate_limit_config or {
                    'messages_per_minute': 10,
                    'burst_limit': 5
                },
                'channel_permissions': {
                    channel: {'read': True, 'write': True} 
                    for channel in target_channels
                },
                'bot_capabilities': {
                    'message_handling': True,
                    'command_processing': True,
                    'ai_responses': ai_integration
                },
                'registration_timestamp': datetime.now().isoformat()
            })
        
        # 設置生命週期管理器狀態
        self.lifecycle_manager.update_service_status(
            service_name,
            ServiceStatus.CREATED, 
            f"子機器人服務已註冊（Bot ID: {bot_id}, 頻道數: {len(target_channels)}）"
        )
        
        logger.info(f"子機器人服務 {service_name} 註冊完成，Bot ID: {bot_id}")
        return service_name
    
    async def register_ai_service(
        self,
        service: BaseService,
        provider: str,
        models: List[str],
        name: Optional[str] = None,
        quota_config: Optional[Dict[str, Any]] = None,
        security_level: str = 'standard'
    ) -> str:
        """
        註冊AI服務
        
        參數：
            service: AI服務實例
            provider: AI提供商 ('openai', 'anthropic', 'google')
            models: 支援的模型列表
            name: 服務名稱
            quota_config: 配額配置
            security_level: 安全等級 ('basic', 'standard', 'high')
            
        返回：
            服務名稱
        """
        # 先使用基類方法設置基本元數據
        service_name = await super().register_ai_service(service, provider, models, name)
        
        # 擴展元數據，增加AI服務特定配置
        if hasattr(service, 'service_metadata'):
            service.service_metadata.update({
                'quota_config': quota_config or {
                    'daily_requests': 1000,
                    'monthly_cost_limit': 100.0
                },
                'security_level': security_level,
                'content_filtering': {
                    'enabled': security_level in ['standard', 'high'],
                    'strict_mode': security_level == 'high'
                },
                'model_capabilities': {
                    model: {'text_generation': True, 'conversation': True}
                    for model in models
                },
                'performance_metrics': {
                    'average_response_time': 0.0,
                    'success_rate': 100.0,
                    'total_requests': 0
                },
                'registration_timestamp': datetime.now().isoformat()
            })
        
        # 設置生命週期管理器狀態
        self.lifecycle_manager.update_service_status(
            service_name,
            ServiceStatus.CREATED,
            f"AI服務已註冊（提供商: {provider}, 模型數: {len(models)}）"
        )
        
        logger.info(f"AI服務 {service_name} 註冊完成，提供商: {provider}")
        return service_name
    
    # ========== 擴展的健康狀態和監控方法 ==========
    
    async def get_service_health_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        獲取服務健康狀態（擴展版本）
        
        整合生命週期管理器的健康檢查結果
        """
        if service_name:
            # 先獲取基礎健康狀態
            try:
                base_health = await super().get_service_health_status(service_name)
            except Exception as e:
                logger.warning(f"獲取基礎健康狀態失敗: {e}")
                # 如果基礎方法失敗，創建一個基本的健康狀態
                service = self.get_service(service_name)
                if service:
                    base_health = await service.health_check()
                else:
                    base_health = {
                        "service_name": service_name,
                        "status": "not_found",
                        "message": f"服務 {service_name} 不存在"
                    }
            
            # 從生命週期管理器獲取詳細健康信息
            lifecycle_health = self.lifecycle_manager.get_service_health(service_name)
            lifecycle_status = self.lifecycle_manager.get_service_status(service_name)
            
            if lifecycle_health:
                base_health.update({
                    'lifecycle_status': lifecycle_status.value if lifecycle_status else 'unknown',
                    'last_health_check': lifecycle_health.last_check.isoformat(),
                    'health_check_response_time': lifecycle_health.response_time,
                    'error_count': lifecycle_health.error_count,
                    'health_message': lifecycle_health.message
                })
            
            return base_health
        else:
            # 獲取所有服務的健康狀態
            try:
                all_health = await super().get_service_health_status()
            except Exception as e:
                logger.warning(f"獲取所有服務健康狀態失敗: {e}")
                # 如果基礎方法失敗，創建基本的健康狀態報告
                all_health = {
                    "timestamp": datetime.now().isoformat(),
                    "total_services": len(self._services),
                    "services": {}
                }
                
                for name, service in self._services.items():
                    try:
                        health_info = await service.health_check()
                        all_health["services"][name] = health_info
                    except Exception as service_error:
                        all_health["services"][name] = {
                            "service_name": name,
                            "status": "error",
                            "error": str(service_error)
                        }
            
            # 添加生命週期管理器的統計信息
            lifecycle_status = self.lifecycle_manager.get_all_services_status()
            
            all_health['lifecycle_summary'] = {
                'total_monitored_services': len(lifecycle_status),
                'healthy_services': sum(1 for s in lifecycle_status.values() 
                                      if s['health']['status'] == 'healthy'),
                'unhealthy_services': sum(1 for s in lifecycle_status.values()
                                        if s['health']['status'] == 'unhealthy'),
                'service_type_distribution': dict(self._service_type_counts)
            }
            
            return all_health
    
    def get_service_registration_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        獲取服務註冊歷史記錄
        
        參數：
            limit: 返回記錄數限制
            
        返回：
            註冊歷史記錄列表
        """
        # 按時間倒序排序
        sorted_history = sorted(
            self._service_registration_history, 
            key=lambda x: x.get('registered_at', x.get('unregistered_at', '')), 
            reverse=True
        )
        
        return sorted_history[:limit]
    
    def get_service_type_statistics(self) -> Dict[str, Any]:
        """
        獲取服務類型統計信息
        
        返回：
            服務類型統計字典
        """
        total_services = sum(self._service_type_counts.values())
        
        return {
            'total_services': total_services,
            'type_distribution': {
                service_type.value: count 
                for service_type, count in self._service_type_counts.items()
            },
            'new_service_types_v2_4_4': {
                'deployment_services': self._service_type_counts.get(ServiceType.DEPLOYMENT, 0),
                'sub_bot_services': self._service_type_counts.get(ServiceType.SUB_BOT, 0),
                'ai_services': self._service_type_counts.get(ServiceType.AI_SERVICE, 0)
            },
            'statistics_timestamp': datetime.now().isoformat()
        }
    
    async def perform_full_system_health_check(self) -> Dict[str, Any]:
        """
        執行完整的系統健康檢查
        
        返回：
            完整的系統健康狀態報告
        """
        logger.info("開始執行完整系統健康檢查...")
        
        # 觸發所有服務的健康檢查
        health_check_tasks = []
        for service_name in self.list_services():
            task = asyncio.create_task(
                self.lifecycle_manager.perform_health_check(service_name)
            )
            health_check_tasks.append((service_name, task))
        
        # 等待所有健康檢查完成
        health_results = {}
        for service_name, task in health_check_tasks:
            try:
                health_info = await task
                health_results[service_name] = {
                    'status': health_info.status.value,
                    'response_time': health_info.response_time,
                    'error_count': health_info.error_count,
                    'message': health_info.message,
                    'last_check': health_info.last_check.isoformat()
                }
            except Exception as e:
                health_results[service_name] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # 生成綜合報告
        healthy_count = sum(1 for result in health_results.values() 
                          if result.get('status') == 'healthy')
        total_count = len(health_results)
        
        system_health = {
            'overall_status': 'healthy' if healthy_count == total_count else 'degraded',
            'total_services': total_count,
            'healthy_services': healthy_count,
            'unhealthy_services': total_count - healthy_count,
            'health_percentage': (healthy_count / total_count * 100) if total_count > 0 else 0,
            'services': health_results,
            'system_statistics': self.get_service_type_statistics(),
            'check_timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"系統健康檢查完成：{healthy_count}/{total_count} 服務健康")
        return system_health
    
    # ========== 強化的服務發現和動態註冊機制 ==========
    
    async def discover_services(self, discovery_paths: List[str] = None) -> Dict[str, Any]:
        """
        自動發現可用的服務
        
        Args:
            discovery_paths: 搜索路徑列表
            
        Returns:
            發現的服務資訊字典
        """
        discovered_services = {
            'deployment_services': [],
            'sub_bot_services': [],
            'ai_services': [],
            'other_services': []
        }
        
        try:
            # 預設搜索路徑
            if discovery_paths is None:
                discovery_paths = [
                    'src/services',
                    'services',
                    'plugins'
                ]
            
            import os
            import importlib.util
            
            for search_path in discovery_paths:
                if not os.path.exists(search_path):
                    continue
                
                for root, dirs, files in os.walk(search_path):
                    for file in files:
                        if file.endswith('.py') and not file.startswith('__'):
                            try:
                                module_path = os.path.join(root, file)
                                service_info = await self._analyze_service_module(module_path)
                                
                                if service_info:
                                    service_type = service_info.get('type', 'other')
                                    if service_type == 'deployment':
                                        discovered_services['deployment_services'].append(service_info)
                                    elif service_type == 'sub_bot':
                                        discovered_services['sub_bot_services'].append(service_info)
                                    elif service_type == 'ai_service':
                                        discovered_services['ai_services'].append(service_info)
                                    else:
                                        discovered_services['other_services'].append(service_info)
                                        
                            except Exception as e:
                                logger.debug(f"分析服務模組失敗 {file}: {e}")
                                continue
            
            total_discovered = sum(len(services) for services in discovered_services.values())
            logger.info(f"服務發現完成，總共找到 {total_discovered} 個潛在服務")
            
            return discovered_services
            
        except Exception as e:
            logger.error(f"服務發現過程失敗: {e}")
            return discovered_services
    
    async def _analyze_service_module(self, module_path: str) -> Optional[Dict[str, Any]]:
        """
        分析服務模組，提取服務資訊
        
        Args:
            module_path: 模組文件路徑
            
        Returns:
            服務資訊字典或None
        """
        try:
            import ast
            import inspect
            
            with open(module_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 分析AST查找服務類別
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # 檢查是否繼承自BaseService
                    base_names = []
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            base_names.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            base_names.append(base.attr)
                    
                    if 'BaseService' in base_names:
                        service_info = {
                            'name': node.name,
                            'module_path': module_path,
                            'type': self._determine_service_type(node.name, content),
                            'discovered_at': datetime.now().isoformat()
                        }
                        
                        return service_info
            
            return None
            
        except Exception as e:
            logger.debug(f"分析服務模組失敗 {module_path}: {e}")
            return None
    
    def _determine_service_type(self, class_name: str, content: str) -> str:
        """
        根據類別名稱和內容確定服務類型
        
        Args:
            class_name: 類別名稱
            content: 文件內容
            
        Returns:
            服務類型字符串
        """
        class_name_lower = class_name.lower()
        content_lower = content.lower()
        
        # 檢查部署服務特徵
        deployment_keywords = ['deployment', 'deploy', 'docker', 'environment']
        if any(keyword in class_name_lower for keyword in deployment_keywords):
            return 'deployment'
        
        # 檢查子機器人服務特徵
        subbot_keywords = ['subbot', 'sub_bot', 'bot', 'discord']
        if any(keyword in class_name_lower for keyword in subbot_keywords):
            return 'sub_bot'
        
        # 檢查AI服務特徵
        ai_keywords = ['ai', 'llm', 'openai', 'anthropic', 'chat', 'conversation']
        if any(keyword in class_name_lower for keyword in ai_keywords):
            return 'ai_service'
        
        # 檢查內容中的特徵關鍵字
        if any(keyword in content_lower for keyword in deployment_keywords):
            return 'deployment'
        elif any(keyword in content_lower for keyword in subbot_keywords):
            return 'sub_bot'
        elif any(keyword in content_lower for keyword in ai_keywords):
            return 'ai_service'
        
        return 'other'
    
    async def auto_register_discovered_services(
        self, 
        discovered_services: Dict[str, Any],
        auto_start: bool = False
    ) -> Dict[str, bool]:
        """
        自動註冊發現的服務
        
        Args:
            discovered_services: 發現的服務字典
            auto_start: 是否自動啟動服務
            
        Returns:
            註冊結果字典
        """
        registration_results = {}
        
        try:
            # 按優先級順序註冊服務
            service_order = [
                ('deployment_services', 10),
                ('ai_services', 20), 
                ('sub_bot_services', 30),
                ('other_services', 40)
            ]
            
            for service_type, default_priority in service_order:
                services = discovered_services.get(service_type, [])
                
                for service_info in services:
                    try:
                        # 動態導入服務模組
                        service_instance = await self._create_service_instance(service_info)
                        
                        if service_instance:
                            # 註冊服務
                            service_name = await self.register_service(
                                service=service_instance,
                                name=service_info['name'],
                                priority=default_priority,
                                auto_recovery=True
                            )
                            
                            registration_results[service_info['name']] = True
                            logger.info(f"自動註冊服務成功: {service_name}")
                            
                            # 如果需要自動啟動
                            if auto_start and hasattr(service_instance, 'start'):
                                try:
                                    await service_instance.start()
                                    logger.info(f"自動啟動服務成功: {service_name}")
                                except Exception as e:
                                    logger.warning(f"自動啟動服務失敗 {service_name}: {e}")
                        else:
                            registration_results[service_info['name']] = False
                            
                    except Exception as e:
                        logger.error(f"註冊服務失敗 {service_info['name']}: {e}")
                        registration_results[service_info['name']] = False
            
            successful_registrations = sum(1 for result in registration_results.values() if result)
            logger.info(f"自動註冊完成，成功註冊 {successful_registrations} 個服務")
            
            return registration_results
            
        except Exception as e:
            logger.error(f"自動註冊服務過程失敗: {e}")
            return registration_results
    
    async def _create_service_instance(self, service_info: Dict[str, Any]):
        """
        創建服務實例
        
        Args:
            service_info: 服務資訊字典
            
        Returns:
            服務實例或None
        """
        try:
            import importlib.util
            import os
            
            module_path = service_info['module_path']
            module_name = os.path.splitext(os.path.basename(module_path))[0]
            
            # 動態導入模組
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # 查找服務類別
                service_class = getattr(module, service_info['name'], None)
                
                if service_class:
                    # 創建服務實例
                    service_instance = service_class()
                    return service_instance
            
            return None
            
        except Exception as e:
            logger.error(f"創建服務實例失敗 {service_info['name']}: {e}")
            return None
    
    def get_service_discovery_stats(self) -> Dict[str, Any]:
        """
        獲取服務發現統計資訊
        
        Returns:
            統計資訊字典
        """
        return {
            'total_registered_services': len(self._services),
            'service_type_distribution': dict(self._service_type_counts),
            'services_with_dependencies': len(self._service_dependencies),
            'services_with_auto_recovery': sum(1 for enabled in self._auto_recovery_enabled.values() if enabled),
            'active_dependency_relationships': sum(len(deps) for deps in self._service_dependencies.values()),
            'registration_history_size': len(self._service_registration_history),
            'last_discovery_time': datetime.now().isoformat()
        }
    # ========== 安全和資料庫代理協調 ==========
    
    async def validate_service_security(
        self,
        service_name: str,
        security_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        驗證服務的安全性
        
        Args:
            service_name: 服務名稱
            security_context: 安全上下文
            
        Returns:
            安全檢查結果
        """
        try:
            service = self.get_service(service_name)
            if not service:
                return {
                    'valid': False,
                    'reason': '服務不存在',
                    'security_level': 'unknown'
                }
            
            security_result = {
                'valid': True,
                'security_level': 'basic',
                'checks_passed': [],
                'warnings': [],
                'timestamp': datetime.now().isoformat()
            }
            
            # 檢查服務類型特定的安全要求
            service_type = getattr(service, 'service_metadata', {}).get('service_type')
            
            if service_type == 'deployment':
                await self._validate_deployment_security(service, security_result)
            elif service_type == 'sub_bot':
                await self._validate_subbot_security(service, security_result)
            elif service_type == 'ai_service':
                await self._validate_ai_security(service, security_result)
            
            # 通用安全檢查
            await self._validate_general_security(service, security_result)
            
            return security_result
            
        except Exception as e:
            logger.error(f"安全驗證失敗 {service_name}: {e}")
            return {
                'valid': False,
                'reason': f'安全驗證異常: {str(e)}',
                'security_level': 'error'
            }
    
    async def _validate_deployment_security(self, service, security_result: Dict[str, Any]) -> None:
        """驗證部署服務安全性"""
        # 檢查環境配置安全性
        if hasattr(service, 'config'):
            config = service.config
            if config.get('docker_timeout', 0) > 600:  # 10分鐘超時
                security_result['warnings'].append("部署超時設置過長可能影響安全")
            
            security_result['checks_passed'].append("部署配置檢查")
        
        security_result['security_level'] = 'standard'
    
    async def _validate_subbot_security(self, service, security_result: Dict[str, Any]) -> None:
        """驗證子機器人服務安全性"""
        # 檢查Token加密
        if hasattr(service, '_encryption_key') and service._encryption_key:
            security_result['checks_passed'].append("Token加密檢查")
        else:
            security_result['warnings'].append("Token加密密鑰未設置")
        
        # 檢查速率限制
        if hasattr(service, 'config'):
            rate_limit = service.config.get('default_rate_limit', 0)
            if rate_limit <= 0:
                security_result['warnings'].append("未設置速率限制")
            else:
                security_result['checks_passed'].append("速率限制檢查")
        
        security_result['security_level'] = 'high' if not security_result['warnings'] else 'standard'
    
    async def _validate_ai_security(self, service, security_result: Dict[str, Any]) -> None:
        """驗證AI服務安全性"""
        # 檢查內容過濾
        if hasattr(service, 'config'):
            content_filter = service.config.get('content_filter_enabled', False)
            if content_filter:
                security_result['checks_passed'].append("內容過濾檢查")
            else:
                security_result['warnings'].append("內容過濾未啟用")
        
        # 檢查配額管理
        if hasattr(service, 'config'):
            cost_tracking = service.config.get('cost_tracking_enabled', False)
            if cost_tracking:
                security_result['checks_passed'].append("成本追蹤檢查")
            else:
                security_result['warnings'].append("成本追蹤未啟用")
        
        security_result['security_level'] = 'high' if len(security_result['checks_passed']) >= 2 else 'standard'
    
    async def _validate_general_security(self, service, security_result: Dict[str, Any]) -> None:
        """通用安全檢查"""
        # 檢查服務是否有權限驗證方法
        if hasattr(service, '_validate_permissions'):
            security_result['checks_passed'].append("權限驗證機制檢查")
        else:
            security_result['warnings'].append("缺少權限驗證機制")
    
    async def sync_service_state_to_database(
        self,
        service_name: str,
        force_update: bool = False
    ) -> bool:
        """
        同步服務狀態到資料庫
        
        Args:
            service_name: 服務名稱
            force_update: 是否強制更新
            
        Returns:
            是否同步成功
        """
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                logger.warning(f"無法獲取資料庫管理器，跳過服務狀態同步: {service_name}")
                return False
            
            service = self.get_service(service_name)
            if not service:
                return False
            
            # 獲取服務狀態和健康資訊
            status = self.lifecycle_manager.get_service_status(service_name)
            health = self.lifecycle_manager.get_service_health(service_name)
            
            # 獲取服務元數據
            metadata = getattr(service, 'service_metadata', {})
            
            # 將資訊存儲到資料庫
            await db_manager.execute(
                """
                INSERT OR REPLACE INTO service_registry 
                (service_name, service_type, status, health_status, metadata, 
                 last_health_check, response_time, error_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    service_name,
                    metadata.get('service_type', 'unknown'),
                    status.value if status else 'unknown',
                    health.status.value if health else 'unknown',
                    json.dumps(metadata, ensure_ascii=False),
                    health.last_check.isoformat() if health else datetime.now().isoformat(),
                    health.response_time if health else 0.0,
                    health.error_count if health else 0,
                    datetime.now().isoformat()
                )
            )
            
            logger.debug(f"已同步服務狀態到資料庫: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"同步服務狀態到資料庫失敗 {service_name}: {e}")
            return False
    
    async def batch_sync_services_to_database(self) -> Dict[str, bool]:
        """
        批量同步所有服務狀態到資料庫
        
        Returns:
            同步結果字典
        """
        sync_results = {}
        
        for service_name in self.list_services():
            try:
                success = await self.sync_service_state_to_database(service_name)
                sync_results[service_name] = success
            except Exception as e:
                logger.error(f"同步服務失敗 {service_name}: {e}")
                sync_results[service_name] = False
        
        successful_syncs = sum(1 for success in sync_results.values() if success)
        logger.info(f"批量同步完成，成功同步 {successful_syncs}/{len(sync_results)} 個服務")
        
        return sync_results
    
    async def restore_services_from_database(self) -> Dict[str, bool]:
        """
        從資料庫恢復服務狀態
        
        Returns:
            恢復結果字典
        """
        restore_results = {}
        
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                logger.warning("無法獲取資料庫管理器，跳過服務恢復")
                return restore_results
            
            # 獲取資料庫中的服務記錄
            services_data = await db_manager.fetchall(
                "SELECT * FROM service_registry ORDER BY updated_at DESC"
            )
            
            for service_data in services_data:
                service_name = service_data['service_name']
                try:
                    # 檢查服務是否已註冊
                    if service_name in self._services:
                        # 更新狀態
                        status = ServiceStatus(service_data['status'])
                        self.lifecycle_manager.update_service_status(
                            service_name, 
                            status,
                            "從資料庫恢復狀態"
                        )
                        
                        restore_results[service_name] = True
                        logger.debug(f"已恢復服務狀態: {service_name}")
                    else:
                        logger.debug(f"服務未註冊，跳過恢復: {service_name}")
                        restore_results[service_name] = False
                        
                except Exception as e:
                    logger.error(f"恢復服務狀態失敗 {service_name}: {e}")
                    restore_results[service_name] = False
            
            successful_restores = sum(1 for success in restore_results.values() if success)
            logger.info(f"服務恢復完成，成功恢復 {successful_restores}/{len(restore_results)} 個服務")
            
            return restore_results
            
        except Exception as e:
            logger.error(f"從資料庫恢復服務失敗: {e}")
            return restore_results
        """
        啟動服務生命週期監控
        """
        if not self.lifecycle_manager._running:
            await self.lifecycle_manager.start()
            logger.info("服務生命週期監控已啟動")
        else:
            logger.info("服務生命週期監控已在運行")
    
    async def stop_service_lifecycle_monitoring(self) -> None:
        """
        停止服務生命週期監控
        """
        if self.lifecycle_manager._running:
            await self.lifecycle_manager.stop()
            logger.info("服務生命週期監控已停止")
        else:
            logger.info("服務生命週期監控未在運行")
    
    def get_lifecycle_events(
        self, 
        service_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        獲取生命週期事件記錄
        """
        events = self.lifecycle_manager.get_lifecycle_events(service_name, limit)
        
        return [
            {
                'service_name': event.service_name,
                'event_type': event.event_type,
                'timestamp': event.timestamp.isoformat(),
                'old_status': event.old_status.value if event.old_status else None,
                'new_status': event.new_status.value if event.new_status else None,
                'message': event.message,
                'metadata': event.metadata
            }
            for event in events
        ]


# 創建全域擴展服務註冊表實例
extended_service_registry = ExtendedServiceRegistry(global_lifecycle_manager)

# 提供向後相容性的別名
ServiceRegistry = ExtendedServiceRegistry
service_registry = extended_service_registry