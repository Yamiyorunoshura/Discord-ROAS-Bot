#!/usr/bin/env python3
"""
服務啟動編排器 - 智能管理服務啟動順序和依賴關係
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組實現了智能的服務啟動編排，基於服務依賴關係自動計算最優啟動順序，
並提供健康檢查、重試機制和故障恢復功能。
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from contextlib import asynccontextmanager

from .deployment_manager import DeploymentManager, ServiceStatus, ServiceInfo
from .monitoring_collector import MonitoringCollector
from .error_handler import ErrorHandler
from .api_contracts import ServiceContract, ServiceRole

logger = logging.getLogger(__name__)


class StartupPhase(Enum):
    """啟動階段"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    STARTING = "starting"
    HEALTH_CHECK = "health_check"
    READY = "ready"
    FAILED = "failed"
    TIMEOUT = "timeout"


class DependencyType(Enum):
    """依賴類型"""
    HARD = "hard"        # 硬依賴：必須等待依賴服務完全啟動
    SOFT = "soft"        # 軟依賴：可以並行啟動，但會檢查依賴狀態
    OPTIONAL = "optional" # 可選依賴：依賴服務失敗不影響自身啟動


@dataclass
class ServiceDependency:
    """服務依賴定義"""
    dependent_service: str      # 依賴的服務
    dependency_service: str     # 被依賴的服務
    dependency_type: DependencyType
    wait_timeout: int = 120     # 等待超時時間（秒）
    health_check_required: bool = True
    retry_attempts: int = 3


@dataclass
class StartupEvent:
    """啟動事件"""
    service_name: str
    phase: StartupPhase
    timestamp: datetime
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StartupResult:
    """啟動結果"""
    service_name: str
    success: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    phase: StartupPhase
    attempts: int
    errors: List[str] = field(default_factory=list)
    events: List[StartupEvent] = field(default_factory=list)


@dataclass
class OrchestrationResult:
    """編排結果"""
    success: bool
    total_duration: float
    startup_order: List[str]
    service_results: Dict[str, StartupResult]
    failed_services: List[str]
    timeline: List[StartupEvent]
    recommendations: List[str] = field(default_factory=list)


class ServiceStartupOrchestrator:
    """
    服務啟動編排器
    
    功能：
    - 智能計算服務啟動順序
    - 管理服務依賴關係
    - 並行啟動獨立服務
    - 健康檢查和重試機制
    - 故障恢復和回滾
    """
    
    def __init__(self, project_root: Optional[Path] = None, environment: str = 'dev'):
        self.project_root = project_root or Path.cwd()
        self.environment = environment
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 依賴管理器
        self.deployment_manager = DeploymentManager(
            project_root=self.project_root,
            compose_file=f'docker-compose.{environment}.yml'
        )
        self.monitoring_collector = MonitoringCollector(self.project_root)
        self.error_handler = ErrorHandler(self.project_root)
        
        # 服務依賴定義
        self.dependencies = self._define_service_dependencies()
        
        # 啟動配置
        self.startup_config = {
            'parallel_startup': True,
            'health_check_interval': 5,
            'max_parallel_services': 4,
            'global_timeout': 600,  # 10分鐘
            'retry_delay': 10
        }
        
        # 狀態追蹤
        self.service_phases: Dict[str, StartupPhase] = {}
        self.startup_events: List[StartupEvent] = []
        self.service_health_checks: Dict[str, Callable] = {}
    
    def _define_service_dependencies(self) -> List[ServiceDependency]:
        """定義服務依賴關係"""
        dependencies = []
        
        # Redis 作為基礎服務，無依賴
        # Discord Bot 依賴 Redis
        dependencies.append(ServiceDependency(
            dependent_service='discord-bot',
            dependency_service='redis',
            dependency_type=DependencyType.HARD,
            wait_timeout=60,
            health_check_required=True
        ))
        
        # Prometheus 依賴 Discord Bot（軟依賴）
        dependencies.append(ServiceDependency(
            dependent_service='prometheus',
            dependency_service='discord-bot',
            dependency_type=DependencyType.SOFT,
            wait_timeout=90,
            health_check_required=False  # Prometheus可以在沒有Discord Bot時啟動
        ))
        
        # Grafana 依賴 Prometheus
        dependencies.append(ServiceDependency(
            dependent_service='grafana',
            dependency_service='prometheus', 
            dependency_type=DependencyType.HARD,
            wait_timeout=120
        ))
        
        return dependencies
    
    async def orchestrate_startup(self, services: Optional[List[str]] = None) -> OrchestrationResult:
        """
        編排服務啟動
        
        Args:
            services: 要啟動的服務列表，None表示啟動所有服務
            
        Returns:
            OrchestrationResult: 編排結果
        """
        start_time = time.time()
        self.logger.info("🚀 開始服務啟動編排")
        
        try:
            # 確定要啟動的服務
            target_services = services or self._get_all_services()
            
            # 計算啟動順序
            startup_order = self._calculate_startup_order(target_services)
            self.logger.info(f"計算出的啟動順序: {' -> '.join(startup_order)}")
            
            # 初始化服務狀態
            for service in target_services:
                self.service_phases[service] = StartupPhase.PENDING
            
            # 執行啟動編排
            service_results = await self._execute_orchestration(startup_order)
            
            # 分析結果
            failed_services = [
                service for service, result in service_results.items()
                if not result.success
            ]
            
            overall_success = len(failed_services) == 0
            total_duration = time.time() - start_time
            
            # 生成建議
            recommendations = self._generate_recommendations(service_results, failed_services)
            
            result = OrchestrationResult(
                success=overall_success,
                total_duration=total_duration,
                startup_order=startup_order,
                service_results=service_results,
                failed_services=failed_services,
                timeline=self.startup_events.copy(),
                recommendations=recommendations
            )
            
            self.logger.info(f"{'✅' if overall_success else '❌'} 服務啟動編排完成，耗時 {total_duration:.1f} 秒")
            return result
            
        except Exception as e:
            total_duration = time.time() - start_time
            self.logger.error(f"服務啟動編排失敗: {str(e)}", exc_info=True)
            
            return OrchestrationResult(
                success=False,
                total_duration=total_duration,
                startup_order=[],
                service_results={},
                failed_services=[],
                timeline=self.startup_events.copy(),
                recommendations=[f"編排失敗: {str(e)}"]
            )
    
    async def _execute_orchestration(self, startup_order: List[str]) -> Dict[str, StartupResult]:
        """執行啟動編排"""
        service_results = {}
        
        # 按層級分組服務（可以並行啟動的服務）
        service_layers = self._group_services_by_layer(startup_order)
        
        for layer_index, services_in_layer in enumerate(service_layers):
            self.logger.info(f"啟動第 {layer_index + 1} 層服務: {', '.join(services_in_layer)}")
            
            # 並行啟動本層的服務
            tasks = []
            for service in services_in_layer:
                task = asyncio.create_task(self._start_service_with_dependencies(service))
                tasks.append((service, task))
            
            # 等待本層所有服務完成
            for service, task in tasks:
                try:
                    result = await task
                    service_results[service] = result
                except Exception as e:
                    self.logger.error(f"服務 {service} 啟動異常: {str(e)}")
                    service_results[service] = StartupResult(
                        service_name=service,
                        success=False,
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        duration_seconds=0,
                        phase=StartupPhase.FAILED,
                        attempts=1,
                        errors=[str(e)]
                    )
            
            # 檢查本層是否有關鍵服務失敗
            layer_critical_failures = self._check_critical_failures(services_in_layer, service_results)
            if layer_critical_failures:
                self.logger.error(f"第 {layer_index + 1} 層有關鍵服務失敗: {', '.join(layer_critical_failures)}")
                # 繼續下一層，但記錄警告
        
        return service_results
    
    async def _start_service_with_dependencies(self, service_name: str) -> StartupResult:
        """啟動服務並處理依賴"""
        start_time = datetime.now()
        attempt = 0
        max_attempts = 3
        
        self.logger.info(f"開始啟動服務: {service_name}")
        self._record_event(service_name, StartupPhase.INITIALIZING, "開始服務啟動流程")
        
        try:
            # 檢查依賴服務
            dependency_check = await self._wait_for_dependencies(service_name)
            if not dependency_check['success']:
                return StartupResult(
                    service_name=service_name,
                    success=False,
                    start_time=start_time,
                    end_time=datetime.now(),
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    phase=StartupPhase.FAILED,
                    attempts=1,
                    errors=dependency_check['errors']
                )
            
            # 重試啟動邏輯
            while attempt < max_attempts:
                attempt += 1
                self.logger.info(f"嘗試啟動服務 {service_name}（第 {attempt}/{max_attempts} 次）")
                
                try:
                    # 啟動服務
                    self.service_phases[service_name] = StartupPhase.STARTING
                    self._record_event(service_name, StartupPhase.STARTING, f"第 {attempt} 次啟動嘗試")
                    
                    success = await self._start_single_service(service_name)
                    
                    if success:
                        # 執行健康檢查
                        self.service_phases[service_name] = StartupPhase.HEALTH_CHECK
                        self._record_event(service_name, StartupPhase.HEALTH_CHECK, "執行健康檢查")
                        
                        health_ok = await self._perform_health_check(service_name)
                        
                        if health_ok:
                            self.service_phases[service_name] = StartupPhase.READY
                            self._record_event(service_name, StartupPhase.READY, "服務啟動成功")
                            
                            end_time = datetime.now()
                            return StartupResult(
                                service_name=service_name,
                                success=True,
                                start_time=start_time,
                                end_time=end_time,
                                duration_seconds=(end_time - start_time).total_seconds(),
                                phase=StartupPhase.READY,
                                attempts=attempt,
                                events=[event for event in self.startup_events if event.service_name == service_name]
                            )
                        else:
                            self.logger.warning(f"服務 {service_name} 健康檢查失敗")
                            if attempt < max_attempts:
                                await asyncio.sleep(self.startup_config['retry_delay'])
                                continue
                    else:
                        self.logger.warning(f"服務 {service_name} 啟動失敗")
                        if attempt < max_attempts:
                            await asyncio.sleep(self.startup_config['retry_delay'])
                            continue
                
                except Exception as e:
                    self.logger.error(f"服務 {service_name} 啟動異常: {str(e)}")
                    if attempt < max_attempts:
                        await asyncio.sleep(self.startup_config['retry_delay'])
                        continue
            
            # 所有嘗試都失敗
            self.service_phases[service_name] = StartupPhase.FAILED
            self._record_event(service_name, StartupPhase.FAILED, f"啟動失敗，已重試 {max_attempts} 次")
            
            return StartupResult(
                service_name=service_name,
                success=False,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                phase=StartupPhase.FAILED,
                attempts=attempt,
                errors=["多次啟動嘗試失敗"]
            )
            
        except Exception as e:
            self.service_phases[service_name] = StartupPhase.FAILED
            self._record_event(service_name, StartupPhase.FAILED, f"啟動異常: {str(e)}")
            
            return StartupResult(
                service_name=service_name,
                success=False,
                start_time=start_time,
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                phase=StartupPhase.FAILED,
                attempts=attempt,
                errors=[str(e)]
            )
    
    async def _wait_for_dependencies(self, service_name: str) -> Dict[str, Any]:
        """等待依賴服務啟動"""
        service_dependencies = [
            dep for dep in self.dependencies 
            if dep.dependent_service == service_name
        ]
        
        if not service_dependencies:
            return {'success': True, 'errors': []}
        
        self.logger.info(f"檢查服務 {service_name} 的依賴")
        
        dependency_results = []
        
        for dependency in service_dependencies:
            dep_service = dependency.dependency_service
            dep_type = dependency.dependency_type
            timeout = dependency.wait_timeout
            
            self.logger.debug(f"等待依賴服務: {dep_service} ({dep_type.value})")
            
            if dep_type == DependencyType.OPTIONAL:
                # 可選依賴，不等待
                dependency_results.append({
                    'service': dep_service,
                    'success': True,
                    'type': 'optional'
                })
                continue
            
            # 等待依賴服務啟動
            wait_start = time.time()
            success = False
            
            while time.time() - wait_start < timeout:
                if dep_service in self.service_phases:
                    if self.service_phases[dep_service] == StartupPhase.READY:
                        success = True
                        break
                    elif self.service_phases[dep_service] == StartupPhase.FAILED:
                        if dep_type == DependencyType.HARD:
                            # 硬依賴失敗，無法繼續
                            break
                        else:
                            # 軟依賴失敗，可以繼續
                            success = True
                            break
                
                # 檢查服務是否已經在運行
                try:
                    metrics = await self.monitoring_collector.check_service_health(dep_service)
                    if metrics.status.value == 'healthy':
                        success = True
                        break
                except Exception:
                    pass
                
                await asyncio.sleep(2)
            
            dependency_results.append({
                'service': dep_service,
                'success': success,
                'type': dep_type.value,
                'waited_seconds': time.time() - wait_start
            })
        
        # 分析依賴結果
        failed_hard_dependencies = [
            result['service'] for result in dependency_results
            if not result['success'] and result['type'] == 'hard'
        ]
        
        if failed_hard_dependencies:
            return {
                'success': False,
                'errors': [f"硬依賴服務失敗: {', '.join(failed_hard_dependencies)}"],
                'dependency_results': dependency_results
            }
        
        return {
            'success': True, 
            'errors': [],
            'dependency_results': dependency_results
        }
    
    async def _start_single_service(self, service_name: str) -> bool:
        """啟動單個服務"""
        try:
            # 這裡整合現有的部署管理器
            # 由於部署管理器啟動所有服務，我們需要檢查特定服務是否啟動成功
            
            # 檢查服務是否已經在運行
            status = await self.deployment_manager.get_deployment_status()
            for service_info in status.get('services', []):
                if service_info.get('name') == service_name:
                    service_status = service_info.get('status', 'unknown')
                    if service_status in ['running', 'healthy']:
                        return True
            
            # 如果服務未運行，嘗試啟動
            success, message = await self.deployment_manager.start_services()
            self.logger.debug(f"部署管理器回應: {message}")
            
            # 等待一段時間讓服務啟動
            await asyncio.sleep(5)
            
            # 再次檢查服務狀態
            status = await self.deployment_manager.get_deployment_status()
            for service_info in status.get('services', []):
                if service_info.get('name') == service_name:
                    service_status = service_info.get('status', 'unknown')
                    return service_status in ['running', 'healthy']
            
            return False
            
        except Exception as e:
            self.logger.error(f"啟動服務 {service_name} 時出錯: {str(e)}")
            return False
    
    async def _perform_health_check(self, service_name: str) -> bool:
        """執行健康檢查"""
        try:
            # 使用監控收集器檢查服務健康狀態
            metrics = await self.monitoring_collector.check_service_health(service_name)
            
            health_status = metrics.status.value
            is_healthy = health_status in ['healthy', 'running']
            
            self.logger.debug(f"服務 {service_name} 健康檢查: {health_status}")
            return is_healthy
            
        except Exception as e:
            self.logger.warning(f"服務 {service_name} 健康檢查失敗: {str(e)}")
            return False
    
    def _calculate_startup_order(self, services: List[str]) -> List[str]:
        """計算服務啟動順序（拓撲排序）"""
        # 構建依賴圖
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        # 初始化所有服務的入度為0
        for service in services:
            in_degree[service] = 0
        
        # 建立依賴關係圖
        for dependency in self.dependencies:
            if (dependency.dependent_service in services and 
                dependency.dependency_service in services and
                dependency.dependency_type == DependencyType.HARD):
                
                graph[dependency.dependency_service].append(dependency.dependent_service)
                in_degree[dependency.dependent_service] += 1
        
        # 拓撲排序
        queue = deque([service for service in services if in_degree[service] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 檢查是否有環形依賴
        if len(result) != len(services):
            remaining_services = set(services) - set(result)
            self.logger.warning(f"檢測到環形依賴或孤立服務: {remaining_services}")
            # 將剩餘服務添加到結果末尾
            result.extend(list(remaining_services))
        
        return result
    
    def _group_services_by_layer(self, startup_order: List[str]) -> List[List[str]]:
        """將服務按層級分組，同層服務可以並行啟動"""
        layers = []
        current_layer = []
        
        # 簡化實現：基於硬依賴關係分組
        processed_services = set()
        
        for service in startup_order:
            # 檢查該服務的所有硬依賴是否都已處理
            hard_dependencies = [
                dep.dependency_service for dep in self.dependencies
                if (dep.dependent_service == service and 
                    dep.dependency_type == DependencyType.HARD)
            ]
            
            dependencies_satisfied = all(
                dep in processed_services for dep in hard_dependencies
            )
            
            if dependencies_satisfied or not hard_dependencies:
                current_layer.append(service)
            else:
                # 需要新的層
                if current_layer:
                    layers.append(current_layer)
                    processed_services.update(current_layer)
                current_layer = [service]
        
        # 添加最後一層
        if current_layer:
            layers.append(current_layer)
        
        return layers
    
    def _check_critical_failures(self, services: List[str], 
                                service_results: Dict[str, StartupResult]) -> List[str]:
        """檢查關鍵服務失敗"""
        critical_services = ['redis', 'discord-bot']  # 定義關鍵服務
        
        failed_critical = []
        for service in services:
            if (service in critical_services and 
                service in service_results and 
                not service_results[service].success):
                failed_critical.append(service)
        
        return failed_critical
    
    def _record_event(self, service_name: str, phase: StartupPhase, message: str) -> None:
        """記錄啟動事件"""
        event = StartupEvent(
            service_name=service_name,
            phase=phase,
            timestamp=datetime.now(),
            message=message
        )
        self.startup_events.append(event)
    
    def _get_all_services(self) -> List[str]:
        """獲取所有服務列表"""
        services = set()
        
        # 從依賴關係中提取服務列表
        for dependency in self.dependencies:
            services.add(dependency.dependent_service)
            services.add(dependency.dependency_service)
        
        # 添加獨立服務（無依賴關係的服務）
        default_services = ['redis', 'discord-bot', 'prometheus', 'grafana']
        services.update(default_services)
        
        return list(services)
    
    def _generate_recommendations(self, service_results: Dict[str, StartupResult], 
                                failed_services: List[str]) -> List[str]:
        """生成啟動建議"""
        recommendations = []
        
        if not failed_services:
            recommendations.append("所有服務啟動成功")
            return recommendations
        
        # 分析失敗原因
        for service in failed_services:
            result = service_results.get(service)
            if result:
                if result.attempts >= 3:
                    recommendations.append(f"服務 {service} 多次重試失敗，建議檢查配置和日誌")
                
                if result.phase == StartupPhase.TIMEOUT:
                    recommendations.append(f"服務 {service} 啟動超時，考慮增加超時時間或檢查資源限制")
                
                if result.errors:
                    error_keywords = ['permission', 'network', 'memory', 'disk']
                    for keyword in error_keywords:
                        if any(keyword in error.lower() for error in result.errors):
                            recommendations.append(f"服務 {service} 遇到 {keyword} 相關問題，需要檢查系統環境")
        
        # 依賴關係建議
        for service in failed_services:
            dependencies = [
                dep.dependency_service for dep in self.dependencies
                if dep.dependent_service == service
            ]
            if dependencies:
                recommendations.append(f"檢查服務 {service} 的依賴服務是否正常: {', '.join(dependencies)}")
        
        return recommendations


# 工廠方法
def create_startup_orchestrator(environment: str = 'dev', 
                               project_root: Optional[Path] = None) -> ServiceStartupOrchestrator:
    """創建服務啟動編排器"""
    return ServiceStartupOrchestrator(
        project_root=project_root or Path.cwd(),
        environment=environment
    )


# 命令行介面
async def main():
    """主函數"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='ROAS Bot 服務啟動編排工具')
    parser.add_argument('command', choices=['start', 'plan', 'status'],
                       help='執行的命令')
    parser.add_argument('--services', nargs='+', help='指定要啟動的服務')
    parser.add_argument('--environment', '-e', default='dev', choices=['dev', 'prod'],
                       help='部署環境')
    parser.add_argument('--output', '-o', help='輸出檔案路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 創建編排器
    orchestrator = create_startup_orchestrator(args.environment)
    
    try:
        if args.command == 'start':
            result = await orchestrator.orchestrate_startup(args.services)
            
            print(f"{'✅' if result.success else '❌'} 啟動編排完成")
            print(f"總耗時: {result.total_duration:.1f} 秒")
            print(f"啟動順序: {' -> '.join(result.startup_order)}")
            
            if result.failed_services:
                print(f"失敗服務: {', '.join(result.failed_services)}")
            
            if result.recommendations:
                print("建議:")
                for rec in result.recommendations:
                    print(f"  • {rec}")
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    # 由於dataclass包含datetime，需要自訂JSON序列化
                    result_dict = {
                        'success': result.success,
                        'total_duration': result.total_duration,
                        'startup_order': result.startup_order,
                        'failed_services': result.failed_services,
                        'recommendations': result.recommendations,
                        'service_results': {
                            name: {
                                'service_name': sr.service_name,
                                'success': sr.success,
                                'duration_seconds': sr.duration_seconds,
                                'phase': sr.phase.value,
                                'attempts': sr.attempts,
                                'errors': sr.errors
                            }
                            for name, sr in result.service_results.items()
                        }
                    }
                    json.dump(result_dict, f, indent=2, ensure_ascii=False)
                print(f"結果已保存到: {args.output}")
            
            return 0 if result.success else 1
            
        elif args.command == 'plan':
            services = args.services or orchestrator._get_all_services()
            startup_order = orchestrator._calculate_startup_order(services)
            layers = orchestrator._group_services_by_layer(startup_order)
            
            print("啟動計劃:")
            print(f"服務總數: {len(services)}")
            print(f"啟動順序: {' -> '.join(startup_order)}")
            print(f"並行層級: {len(layers)}")
            
            for i, layer in enumerate(layers):
                print(f"  第 {i+1} 層: {', '.join(layer)}")
            
            return 0
            
        elif args.command == 'status':
            # 顯示當前服務狀態
            print("當前服務狀態:")
            for service in orchestrator._get_all_services():
                if service in orchestrator.service_phases:
                    phase = orchestrator.service_phases[service]
                    print(f"  {service}: {phase.value}")
                else:
                    print(f"  {service}: 未啟動")
            
            return 0
            
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))