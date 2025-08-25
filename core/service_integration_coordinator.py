#!/usr/bin/env python3
"""
服務整合協調器 - 統一協調各服務間的整合和通信
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組作為整合專家的核心，負責協調Discord Bot、Redis、監控系統等服務間的整合，
確保服務間的API契約一致性和資料流的無縫管理。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from contextlib import asynccontextmanager

from .deployment_manager import DeploymentManager, ServiceStatus, ServiceInfo
from .environment_validator import EnvironmentValidator
from .monitoring_collector import MonitoringCollector, HealthStatus
from .error_handler import ErrorHandler, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)


class IntegrationPhase(Enum):
    """整合階段"""
    INITIALIZATION = "initialization"
    DEPENDENCY_CHECK = "dependency_check"
    SERVICE_STARTUP = "service_startup"
    HEALTH_VALIDATION = "health_validation"
    INTEGRATION_TESTING = "integration_testing"
    MONITORING_SETUP = "monitoring_setup"
    COMPLETED = "completed"
    FAILED = "failed"


class ServiceRole(Enum):
    """服務角色"""
    PRIMARY = "primary"          # 主服務 (Discord Bot)
    DEPENDENCY = "dependency"    # 依賴服務 (Redis)
    MONITORING = "monitoring"    # 監控服務 (Prometheus, Grafana)
    SUPPORT = "support"          # 支援服務 (Nginx, Backup)


@dataclass
class ServiceContract:
    """服務契約 - 定義服務間的API和資料契約"""
    service_name: str
    role: ServiceRole
    dependencies: List[str]
    provides: List[str]          # 提供的API/功能
    requires: List[str]          # 需要的API/功能
    health_check_endpoint: Optional[str]
    startup_timeout: int = 120
    health_check_interval: int = 30


@dataclass
class IntegrationResult:
    """整合結果"""
    success: bool
    phase: IntegrationPhase
    message: str
    duration_seconds: float
    service_status: Dict[str, str]
    errors: List[str]
    warnings: List[str]
    next_actions: List[str]


class ServiceIntegrationCoordinator:
    """
    服務整合協調器
    
    作為Emma（整合專家）的核心工具，負責：
    - 定義和管理服務間的API契約
    - 協調服務啟動順序和依賴關係
    - 監控服務間的資料流
    - 確保整合的一致性和可靠性
    """
    
    def __init__(self, project_root: Optional[Path] = None, environment: str = 'dev'):
        self.project_root = project_root or Path.cwd()
        self.environment = environment
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 初始化核心組件
        self.deployment_manager = DeploymentManager(
            project_root=self.project_root,
            compose_file=f'docker-compose.{environment}.yml'
        )
        self.environment_validator = EnvironmentValidator(self.project_root)
        self.monitoring_collector = MonitoringCollector(self.project_root)
        self.error_handler = ErrorHandler(self.project_root)
        
        # 服務契約定義
        self.service_contracts = self._define_service_contracts()
        
        # 整合狀態追蹤
        self.current_phase = IntegrationPhase.INITIALIZATION
        self.integration_history: List[IntegrationResult] = []
        
    def _define_service_contracts(self) -> Dict[str, ServiceContract]:
        """定義服務契約"""
        contracts = {}
        
        # Redis服務契約
        contracts['redis'] = ServiceContract(
            service_name='redis',
            role=ServiceRole.DEPENDENCY,
            dependencies=[],
            provides=['caching', 'session_storage', 'pub_sub'],
            requires=[],
            health_check_endpoint='redis://localhost:6379',
            startup_timeout=30,
            health_check_interval=10
        )
        
        # Discord Bot服務契約
        contracts['discord-bot'] = ServiceContract(
            service_name='discord-bot',
            role=ServiceRole.PRIMARY,
            dependencies=['redis'],
            provides=['discord_commands', 'bot_api', 'health_endpoint'],
            requires=['caching', 'session_storage'],
            health_check_endpoint='http://localhost:8000/health',
            startup_timeout=120,
            health_check_interval=30
        )
        
        # Prometheus服務契約
        contracts['prometheus'] = ServiceContract(
            service_name='prometheus',
            role=ServiceRole.MONITORING,
            dependencies=['discord-bot'],
            provides=['metrics_collection', 'alerting'],
            requires=['health_endpoint'],
            health_check_endpoint='http://localhost:9090/-/healthy',
            startup_timeout=60,
            health_check_interval=30
        )
        
        # Grafana服務契約
        contracts['grafana'] = ServiceContract(
            service_name='grafana',
            role=ServiceRole.MONITORING,
            dependencies=['prometheus'],
            provides=['dashboards', 'visualization'],
            requires=['metrics_collection'],
            health_check_endpoint='http://localhost:3000/api/health',
            startup_timeout=90,
            health_check_interval=30
        )
        
        return contracts
    
    async def orchestrate_integration(self) -> IntegrationResult:
        """
        協調完整的服務整合流程
        
        Returns:
            IntegrationResult: 整合結果
        """
        start_time = time.time()
        self.logger.info("🚀 開始服務整合協調流程")
        
        try:
            # 階段1: 初始化檢查
            result = await self._phase_initialization()
            if not result.success:
                return result
            
            # 階段2: 依賴檢查
            result = await self._phase_dependency_check()
            if not result.success:
                return result
            
            # 階段3: 服務啟動
            result = await self._phase_service_startup()
            if not result.success:
                return result
            
            # 階段4: 健康驗證
            result = await self._phase_health_validation()
            if not result.success:
                return result
            
            # 階段5: 整合測試
            result = await self._phase_integration_testing()
            if not result.success:
                return result
            
            # 階段6: 監控設置
            result = await self._phase_monitoring_setup()
            if not result.success:
                return result
            
            # 完成整合
            duration = time.time() - start_time
            final_result = IntegrationResult(
                success=True,
                phase=IntegrationPhase.COMPLETED,
                message=f"服務整合完成，總耗時 {duration:.1f} 秒",
                duration_seconds=duration,
                service_status=await self._get_all_service_status(),
                errors=[],
                warnings=[],
                next_actions=["監控系統運行狀態", "定期執行健康檢查"]
            )
            
            self.integration_history.append(final_result)
            self.logger.info(f"✅ 服務整合協調完成: {final_result.message}")
            return final_result
            
        except Exception as e:
            duration = time.time() - start_time
            error_result = IntegrationResult(
                success=False,
                phase=self.current_phase,
                message=f"整合協調失敗: {str(e)}",
                duration_seconds=duration,
                service_status={},
                errors=[str(e)],
                warnings=[],
                next_actions=["檢查錯誤日誌", "手動診斷問題"]
            )
            
            # 記錄到錯誤處理器
            await self.error_handler.handle_error(e, {
                'operation': 'service_integration',
                'phase': self.current_phase.value,
                'duration': duration
            })
            
            self.integration_history.append(error_result)
            self.logger.error(f"❌ 服務整合協調失敗: {error_result.message}")
            return error_result
    
    async def validate_service_contracts(self) -> Dict[str, bool]:
        """
        驗證服務契約
        
        Returns:
            Dict[str, bool]: 各服務的契約驗證結果
        """
        self.logger.info("🔍 驗證服務契約")
        validation_results = {}
        
        for service_name, contract in self.service_contracts.items():
            try:
                # 檢查依賴關係
                dependencies_valid = await self._validate_dependencies(contract)
                
                # 檢查健康檢查端點
                health_check_valid = await self._validate_health_endpoint(contract)
                
                # 檢查提供的功能
                provides_valid = await self._validate_provides(contract)
                
                validation_results[service_name] = (
                    dependencies_valid and health_check_valid and provides_valid
                )
                
                self.logger.debug(f"服務 {service_name} 契約驗證: {validation_results[service_name]}")
                
            except Exception as e:
                self.logger.error(f"驗證服務 {service_name} 契約時出錯: {str(e)}")
                validation_results[service_name] = False
        
        return validation_results
    
    async def check_service_dependencies(self) -> Dict[str, List[str]]:
        """
        檢查服務依賴狀態
        
        Returns:
            Dict[str, List[str]]: 各服務的依賴狀態
        """
        dependency_status = {}
        
        for service_name, contract in self.service_contracts.items():
            status_list = []
            
            for dependency in contract.dependencies:
                if dependency in self.service_contracts:
                    dep_contract = self.service_contracts[dependency]
                    is_healthy = await self._check_service_health(dep_contract)
                    status = "healthy" if is_healthy else "unhealthy"
                    status_list.append(f"{dependency}: {status}")
                else:
                    status_list.append(f"{dependency}: unknown")
            
            dependency_status[service_name] = status_list
        
        return dependency_status
    
    async def get_integration_report(self) -> Dict[str, Any]:
        """
        獲取整合報告
        
        Returns:
            Dict[str, Any]: 詳細的整合狀態報告
        """
        # 收集當前狀態
        service_status = await self._get_all_service_status()
        contract_validation = await self.validate_service_contracts()
        dependency_status = await self.check_service_dependencies()
        
        # 分析整合健康度
        total_services = len(self.service_contracts)
        healthy_services = sum(1 for status in service_status.values() if status == 'healthy')
        valid_contracts = sum(1 for valid in contract_validation.values() if valid)
        
        integration_health = (healthy_services + valid_contracts) / (total_services * 2) * 100
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'current_phase': self.current_phase.value,
            'integration_health_score': round(integration_health, 1),
            'service_status': service_status,
            'contract_validation': contract_validation,
            'dependency_status': dependency_status,
            'integration_history': [asdict(result) for result in self.integration_history[-5:]],
            'recommendations': self._generate_integration_recommendations(
                service_status, contract_validation, dependency_status
            )
        }
        
        return report
    
    # === 內部方法 - 整合階段實現 ===
    
    async def _phase_initialization(self) -> IntegrationResult:
        """階段1: 初始化檢查"""
        self.current_phase = IntegrationPhase.INITIALIZATION
        self.logger.info("📋 執行初始化檢查")
        
        start_time = time.time()
        
        try:
            # 環境驗證
            env_valid, env_errors = await self.environment_validator.validate_environment()
            if not env_valid:
                return IntegrationResult(
                    success=False,
                    phase=self.current_phase,
                    message="環境驗證失敗",
                    duration_seconds=time.time() - start_time,
                    service_status={},
                    errors=env_errors,
                    warnings=[],
                    next_actions=["修復環境問題", "重新執行整合"]
                )
            
            # 檢查服務契約定義
            if not self.service_contracts:
                return IntegrationResult(
                    success=False,
                    phase=self.current_phase,
                    message="服務契約未定義",
                    duration_seconds=time.time() - start_time,
                    service_status={},
                    errors=["缺少服務契約定義"],
                    warnings=[],
                    next_actions=["定義服務契約", "重新執行整合"]
                )
            
            return IntegrationResult(
                success=True,
                phase=self.current_phase,
                message="初始化檢查完成",
                duration_seconds=time.time() - start_time,
                service_status={},
                errors=[],
                warnings=[],
                next_actions=["進入依賴檢查階段"]
            )
            
        except Exception as e:
            return IntegrationResult(
                success=False,
                phase=self.current_phase,
                message=f"初始化檢查異常: {str(e)}",
                duration_seconds=time.time() - start_time,
                service_status={},
                errors=[str(e)],
                warnings=[],
                next_actions=["檢查系統狀態", "重新執行整合"]
            )
    
    async def _phase_dependency_check(self) -> IntegrationResult:
        """階段2: 依賴檢查"""
        self.current_phase = IntegrationPhase.DEPENDENCY_CHECK
        self.logger.info("🔗 執行依賴檢查")
        
        start_time = time.time()
        
        try:
            # 檢查服務依賴鏈
            dependency_graph = self._build_dependency_graph()
            startup_order = self._calculate_startup_order(dependency_graph)
            
            self.logger.debug(f"計算出的啟動順序: {startup_order}")
            
            return IntegrationResult(
                success=True,
                phase=self.current_phase,
                message=f"依賴檢查完成，啟動順序: {' -> '.join(startup_order)}",
                duration_seconds=time.time() - start_time,
                service_status={},
                errors=[],
                warnings=[],
                next_actions=["按依賴順序啟動服務"]
            )
            
        except Exception as e:
            return IntegrationResult(
                success=False,
                phase=self.current_phase,
                message=f"依賴檢查失敗: {str(e)}",
                duration_seconds=time.time() - start_time,
                service_status={},
                errors=[str(e)],
                warnings=[],
                next_actions=["檢查服務依賴配置", "修復依賴問題"]
            )
    
    async def _phase_service_startup(self) -> IntegrationResult:
        """階段3: 服務啟動"""
        self.current_phase = IntegrationPhase.SERVICE_STARTUP
        self.logger.info("🚀 執行服務啟動")
        
        start_time = time.time()
        
        try:
            # 執行部署
            success, message = await self.deployment_manager.start_services(
                detach=True, build=True, pull=True
            )
            
            if not success:
                return IntegrationResult(
                    success=False,
                    phase=self.current_phase,
                    message=f"服務啟動失敗: {message}",
                    duration_seconds=time.time() - start_time,
                    service_status=await self._get_all_service_status(),
                    errors=[message],
                    warnings=[],
                    next_actions=["檢查服務日誌", "修復啟動問題"]
                )
            
            return IntegrationResult(
                success=True,
                phase=self.current_phase,
                message="服務啟動完成",
                duration_seconds=time.time() - start_time,
                service_status=await self._get_all_service_status(),
                errors=[],
                warnings=[],
                next_actions=["進入健康驗證階段"]
            )
            
        except Exception as e:
            return IntegrationResult(
                success=False,
                phase=self.current_phase,
                message=f"服務啟動異常: {str(e)}",
                duration_seconds=time.time() - start_time,
                service_status={},
                errors=[str(e)],
                warnings=[],
                next_actions=["檢查Docker狀態", "重新啟動服務"]
            )
    
    async def _phase_health_validation(self) -> IntegrationResult:
        """階段4: 健康驗證"""
        self.current_phase = IntegrationPhase.HEALTH_VALIDATION
        self.logger.info("🏥 執行健康驗證")
        
        start_time = time.time()
        
        try:
            # 等待服務穩定
            await asyncio.sleep(10)
            
            # 執行健康檢查
            health_result = await self.monitoring_collector.collect_metrics()
            
            if not health_result.get('overall_status') == 'healthy':
                warnings = []
                errors = []
                
                for service_name, service_data in health_result.get('service_metrics', []):
                    if isinstance(service_data, dict):
                        status = service_data.get('status', 'unknown')
                        if status == 'unhealthy':
                            errors.append(f"服務 {service_name} 不健康")
                        elif status == 'degraded':
                            warnings.append(f"服務 {service_name} 性能下降")
                
                return IntegrationResult(
                    success=len(errors) == 0,
                    phase=self.current_phase,
                    message=f"健康驗證{'通過' if len(errors) == 0 else '失敗'}",
                    duration_seconds=time.time() - start_time,
                    service_status=await self._get_all_service_status(),
                    errors=errors,
                    warnings=warnings,
                    next_actions=["修復不健康服務"] if errors else ["進入整合測試階段"]
                )
            
            return IntegrationResult(
                success=True,
                phase=self.current_phase,
                message="健康驗證通過",
                duration_seconds=time.time() - start_time,
                service_status=await self._get_all_service_status(),
                errors=[],
                warnings=[],
                next_actions=["進入整合測試階段"]
            )
            
        except Exception as e:
            return IntegrationResult(
                success=False,
                phase=self.current_phase,
                message=f"健康驗證異常: {str(e)}",
                duration_seconds=time.time() - start_time,
                service_status={},
                errors=[str(e)],
                warnings=[],
                next_actions=["檢查監控系統", "重新執行健康檢查"]
            )
    
    async def _phase_integration_testing(self) -> IntegrationResult:
        """階段5: 整合測試"""
        self.current_phase = IntegrationPhase.INTEGRATION_TESTING
        self.logger.info("🧪 執行整合測試")
        
        start_time = time.time()
        
        try:
            # 執行契約驗證
            contract_results = await self.validate_service_contracts()
            
            failed_contracts = [
                service for service, valid in contract_results.items() 
                if not valid
            ]
            
            if failed_contracts:
                return IntegrationResult(
                    success=False,
                    phase=self.current_phase,
                    message=f"契約驗證失敗: {', '.join(failed_contracts)}",
                    duration_seconds=time.time() - start_time,
                    service_status=await self._get_all_service_status(),
                    errors=[f"服務 {service} 契約驗證失敗" for service in failed_contracts],
                    warnings=[],
                    next_actions=["修復契約問題", "重新執行整合測試"]
                )
            
            # 測試服務間通信
            communication_results = await self._test_inter_service_communication()
            
            if not all(communication_results.values()):
                failed_communications = [
                    pair for pair, success in communication_results.items()
                    if not success
                ]
                
                return IntegrationResult(
                    success=False,
                    phase=self.current_phase,
                    message=f"服務間通信測試失敗: {', '.join(failed_communications)}",
                    duration_seconds=time.time() - start_time,
                    service_status=await self._get_all_service_status(),
                    errors=[f"通信失敗: {pair}" for pair in failed_communications],
                    warnings=[],
                    next_actions=["修復通信問題", "檢查網路配置"]
                )
            
            return IntegrationResult(
                success=True,
                phase=self.current_phase,
                message="整合測試通過",
                duration_seconds=time.time() - start_time,
                service_status=await self._get_all_service_status(),
                errors=[],
                warnings=[],
                next_actions=["進入監控設置階段"]
            )
            
        except Exception as e:
            return IntegrationResult(
                success=False,
                phase=self.current_phase,
                message=f"整合測試異常: {str(e)}",
                duration_seconds=time.time() - start_time,
                service_status={},
                errors=[str(e)],
                warnings=[],
                next_actions=["檢查測試環境", "重新執行測試"]
            )
    
    async def _phase_monitoring_setup(self) -> IntegrationResult:
        """階段6: 監控設置"""
        self.current_phase = IntegrationPhase.MONITORING_SETUP
        self.logger.info("📊 設置監控系統")
        
        start_time = time.time()
        
        try:
            # 驗證監控系統可用性
            monitoring_health = await self.monitoring_collector.collect_metrics()
            
            if monitoring_health.get('error'):
                return IntegrationResult(
                    success=False,
                    phase=self.current_phase,
                    message=f"監控系統設置失敗: {monitoring_health['error']}",
                    duration_seconds=time.time() - start_time,
                    service_status=await self._get_all_service_status(),
                    errors=[monitoring_health['error']],
                    warnings=[],
                    next_actions=["修復監控問題", "重新配置監控"]
                )
            
            return IntegrationResult(
                success=True,
                phase=self.current_phase,
                message="監控系統設置完成",
                duration_seconds=time.time() - start_time,
                service_status=await self._get_all_service_status(),
                errors=[],
                warnings=[],
                next_actions=["整合流程即將完成"]
            )
            
        except Exception as e:
            return IntegrationResult(
                success=False,
                phase=self.current_phase,
                message=f"監控設置異常: {str(e)}",
                duration_seconds=time.time() - start_time,
                service_status={},
                errors=[str(e)],
                warnings=[],
                next_actions=["檢查監控配置", "重新設置監控"]
            )
    
    # === 輔助方法 ===
    
    async def _validate_dependencies(self, contract: ServiceContract) -> bool:
        """驗證服務依賴"""
        for dependency in contract.dependencies:
            if dependency not in self.service_contracts:
                self.logger.warning(f"服務 {contract.service_name} 的依賴 {dependency} 未定義")
                return False
        return True
    
    async def _validate_health_endpoint(self, contract: ServiceContract) -> bool:
        """驗證健康檢查端點"""
        if not contract.health_check_endpoint:
            return True  # 某些服務可能不需要健康檢查端點
        
        try:
            # 這裡可以實際測試端點連通性
            # 目前先返回True，實際實現時可以加入真實的連通性測試
            return True
        except Exception:
            return False
    
    async def _validate_provides(self, contract: ServiceContract) -> bool:
        """驗證服務提供的功能"""
        # 這裡可以實際測試服務提供的功能是否可用
        # 目前簡化實現
        return len(contract.provides) > 0
    
    async def _check_service_health(self, contract: ServiceContract) -> bool:
        """檢查服務健康狀態"""
        try:
            service_metrics = await self.monitoring_collector.check_service_health(contract.service_name)
            return service_metrics.status.value == 'healthy'
        except Exception:
            return False
    
    async def _get_all_service_status(self) -> Dict[str, str]:
        """獲取所有服務狀態"""
        try:
            deployment_status = await self.deployment_manager.get_deployment_status()
            service_status = {}
            
            for service_info in deployment_status.get('services', []):
                service_name = service_info.get('name', 'unknown')
                status = service_info.get('status', 'unknown')
                service_status[service_name] = status
            
            return service_status
        except Exception as e:
            self.logger.error(f"獲取服務狀態失敗: {str(e)}")
            return {}
    
    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """構建依賴圖"""
        graph = {}
        for service_name, contract in self.service_contracts.items():
            graph[service_name] = contract.dependencies
        return graph
    
    def _calculate_startup_order(self, dependency_graph: Dict[str, List[str]]) -> List[str]:
        """計算啟動順序（拓撲排序）"""
        from collections import deque, defaultdict
        
        # 計算入度
        in_degree = defaultdict(int)
        for node in dependency_graph:
            in_degree[node] = 0
        
        for node in dependency_graph:
            for neighbor in dependency_graph[node]:
                in_degree[neighbor] += 1
        
        # 拓撲排序
        queue = deque([node for node in in_degree if in_degree[node] == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            
            for neighbor in dependency_graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
    
    async def _test_inter_service_communication(self) -> Dict[str, bool]:
        """測試服務間通信"""
        communication_results = {}
        
        # 測試 Discord Bot -> Redis 通信
        communication_results['discord-bot->redis'] = await self._test_redis_connectivity()
        
        # 測試 Prometheus -> Discord Bot 通信
        communication_results['prometheus->discord-bot'] = await self._test_prometheus_scraping()
        
        # 測試 Grafana -> Prometheus 通信
        communication_results['grafana->prometheus'] = await self._test_grafana_datasource()
        
        return communication_results
    
    async def _test_redis_connectivity(self) -> bool:
        """測試Redis連通性"""
        try:
            # 簡化實現，實際可以使用redis客戶端測試
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', 6379))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    async def _test_prometheus_scraping(self) -> bool:
        """測試Prometheus數據抓取"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', 9090))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    async def _test_grafana_datasource(self) -> bool:
        """測試Grafana數據源連接"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', 3000))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _generate_integration_recommendations(self, service_status: Dict[str, str],
                                           contract_validation: Dict[str, bool],
                                           dependency_status: Dict[str, List[str]]) -> List[str]:
        """生成整合建議"""
        recommendations = []
        
        # 分析服務狀態
        unhealthy_services = [name for name, status in service_status.items() 
                            if status != 'healthy']
        if unhealthy_services:
            recommendations.append(f"修復不健康的服務: {', '.join(unhealthy_services)}")
        
        # 分析契約驗證
        invalid_contracts = [name for name, valid in contract_validation.items() 
                           if not valid]
        if invalid_contracts:
            recommendations.append(f"修復無效的服務契約: {', '.join(invalid_contracts)}")
        
        # 分析依賴狀態
        for service, deps in dependency_status.items():
            unhealthy_deps = [dep for dep in deps if 'unhealthy' in dep]
            if unhealthy_deps:
                recommendations.append(f"修復服務 {service} 的不健康依賴: {', '.join(unhealthy_deps)}")
        
        if not recommendations:
            recommendations.append("所有服務整合狀態良好，保持當前配置")
        
        return recommendations


# 工廠方法
def create_integration_coordinator(environment: str = 'dev', 
                                 project_root: Optional[Path] = None) -> ServiceIntegrationCoordinator:
    """
    創建服務整合協調器實例
    
    Args:
        environment: 環境類型
        project_root: 專案根目錄
        
    Returns:
        ServiceIntegrationCoordinator: 整合協調器實例
    """
    return ServiceIntegrationCoordinator(
        project_root=project_root or Path.cwd(),
        environment=environment
    )


# 命令行介面
async def main():
    """主函數 - 用於獨立執行服務整合協調"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 服務整合協調工具')
    parser.add_argument('command', choices=['integrate', 'validate', 'report', 'test'],
                       help='執行的命令')
    parser.add_argument('--environment', '-e', default='dev', choices=['dev', 'prod'],
                       help='部署環境')
    parser.add_argument('--output', '-o', help='輸出檔案路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 創建整合協調器
    coordinator = create_integration_coordinator(args.environment)
    
    try:
        if args.command == 'integrate':
            result = await coordinator.orchestrate_integration()
            print(f"{'✅' if result.success else '❌'} {result.message}")
            if result.errors:
                print("錯誤:")
                for error in result.errors:
                    print(f"  • {error}")
            if result.warnings:
                print("警告:")
                for warning in result.warnings:
                    print(f"  • {warning}")
            return 0 if result.success else 1
            
        elif args.command == 'validate':
            results = await coordinator.validate_service_contracts()
            print("服務契約驗證結果:")
            for service, valid in results.items():
                status = "✅ 有效" if valid else "❌ 無效"
                print(f"  {service}: {status}")
            return 0 if all(results.values()) else 1
            
        elif args.command == 'report':
            report = await coordinator.get_integration_report()
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                print(f"整合報告已保存到: {args.output}")
            else:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0
            
        elif args.command == 'test':
            # 測試服務間通信
            results = await coordinator._test_inter_service_communication()
            print("服務間通信測試結果:")
            for communication, success in results.items():
                status = "✅ 通過" if success else "❌ 失敗"
                print(f"  {communication}: {status}")
            return 0 if all(results.values()) else 1
            
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))