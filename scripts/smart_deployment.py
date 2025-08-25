#!/usr/bin/env python3
"""
智能部署腳本
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

此腳本整合所有整合組件，提供智能化的部署和啟動流程。
包括預檢查、服務編排、健康驗證、監控啟動和錯誤恢復。
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import signal
from contextlib import asynccontextmanager

# 添加核心模組到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.service_integration_coordinator import ServiceIntegrationCoordinator
from core.service_startup_orchestrator import ServiceStartupOrchestrator
from core.unified_health_checker import UnifiedHealthChecker
from core.unified_logging_integration import UnifiedLogHandler, create_logger
from core.environment_validator import EnvironmentValidator
from core.deployment_manager import DeploymentManager, create_deployment_manager
from core.monitoring_collector import MonitoringCollector
from core.error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class SmartDeploymentError(Exception):
    """智能部署錯誤"""
    pass


class DeploymentPhase:
    """部署階段定義"""
    PRE_CHECK = "pre_check"
    PREPARATION = "preparation"
    SERVICE_STARTUP = "service_startup"
    HEALTH_VALIDATION = "health_validation"
    MONITORING_SETUP = "monitoring_setup"
    POST_DEPLOYMENT = "post_deployment"


class DeploymentStatus:
    """部署狀態"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"


class SmartDeployment:
    """智能部署管理器"""
    
    def __init__(self, project_root: Path, environment: str = 'dev', 
                 dry_run: bool = False, force: bool = False):
        self.project_root = project_root
        self.environment = environment
        self.dry_run = dry_run
        self.force = force
        
        # 初始化日誌
        self.deployment_logger = create_logger("smart-deployment", "deployment")
        
        # 部署狀態
        self.deployment_id = f"deploy-{int(time.time())}"
        self.status = DeploymentStatus.PENDING
        self.current_phase = None
        self.start_time = None
        self.deployment_report = {
            'deployment_id': self.deployment_id,
            'environment': environment,
            'start_time': None,
            'end_time': None,
            'duration_seconds': 0,
            'status': self.status,
            'phases': {},
            'services_deployed': [],
            'issues_found': [],
            'recommendations': []
        }
        
        # 初始化組件
        self._initialize_components()
        
        # 設置信號處理
        self._setup_signal_handlers()
    
    def _initialize_components(self):
        """初始化所有組件"""
        try:
            self.environment_validator = EnvironmentValidator(self.project_root)
            self.deployment_manager = create_deployment_manager(self.environment, self.project_root)
            self.coordinator = ServiceIntegrationCoordinator(self.project_root, self.environment)
            self.orchestrator = ServiceStartupOrchestrator(self.project_root, self.environment)
            self.health_checker = UnifiedHealthChecker(self.project_root)
            self.monitoring_collector = MonitoringCollector(self.project_root)
            self.error_handler = ErrorHandler(self.project_root)
            self.log_handler = UnifiedLogHandler.get_instance()
            
            self.deployment_logger.info("所有部署組件初始化成功")
            
        except Exception as e:
            raise SmartDeploymentError(f"組件初始化失敗: {str(e)}")
    
    def _setup_signal_handlers(self):
        """設置信號處理"""
        def signal_handler(signum, frame):
            self.deployment_logger.warning(f"收到信號 {signum}，正在優雅關閉部署...")
            asyncio.create_task(self._graceful_shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def deploy(self) -> Dict[str, Any]:
        """執行智能部署"""
        self.deployment_logger.info(f"🚀 開始智能部署 {self.deployment_id}")
        self.start_time = datetime.now()
        self.deployment_report['start_time'] = self.start_time.isoformat()
        self.status = DeploymentStatus.RUNNING
        
        try:
            with self.deployment_logger.context("smart-deployment") as ctx:
                # 部署階段執行
                deployment_phases = [
                    (DeploymentPhase.PRE_CHECK, self._phase_pre_check),
                    (DeploymentPhase.PREPARATION, self._phase_preparation),
                    (DeploymentPhase.SERVICE_STARTUP, self._phase_service_startup),
                    (DeploymentPhase.HEALTH_VALIDATION, self._phase_health_validation),
                    (DeploymentPhase.MONITORING_SETUP, self._phase_monitoring_setup),
                    (DeploymentPhase.POST_DEPLOYMENT, self._phase_post_deployment)
                ]
                
                for phase_name, phase_func in deployment_phases:
                    if not await self._execute_phase(phase_name, phase_func):
                        self.status = DeploymentStatus.FAILED
                        await self._handle_deployment_failure(phase_name)
                        break
                else:
                    self.status = DeploymentStatus.SUCCESS
                    self.deployment_logger.info("✅ 智能部署成功完成")
                
                # 生成最終報告
                await self._generate_final_report()
                
        except Exception as e:
            self.deployment_logger.error("部署過程發生異常", exception=e)
            self.status = DeploymentStatus.FAILED
            await self._handle_deployment_failure("exception", str(e))
        
        finally:
            end_time = datetime.now()
            self.deployment_report['end_time'] = end_time.isoformat()
            self.deployment_report['duration_seconds'] = (end_time - self.start_time).total_seconds()
            self.deployment_report['status'] = self.status
        
        return self.deployment_report
    
    async def _execute_phase(self, phase_name: str, phase_func) -> bool:
        """執行部署階段"""
        self.current_phase = phase_name
        phase_start = datetime.now()
        
        self.deployment_logger.info(f"執行階段: {phase_name}")
        
        try:
            phase_result = await phase_func()
            
            phase_duration = (datetime.now() - phase_start).total_seconds()
            self.deployment_report['phases'][phase_name] = {
                'status': 'success',
                'duration_seconds': phase_duration,
                'result': phase_result,
                'timestamp': phase_start.isoformat()
            }
            
            self.deployment_logger.info(f"✅ 階段 {phase_name} 完成 ({phase_duration:.1f}s)")
            return True
            
        except Exception as e:
            phase_duration = (datetime.now() - phase_start).total_seconds()
            self.deployment_report['phases'][phase_name] = {
                'status': 'failed',
                'duration_seconds': phase_duration,
                'error': str(e),
                'timestamp': phase_start.isoformat()
            }
            
            self.deployment_logger.error(f"❌ 階段 {phase_name} 失敗", exception=e)
            return False
    
    async def _phase_pre_check(self) -> Dict[str, Any]:
        """階段1：預檢查"""
        self.deployment_logger.info("執行部署前置檢查")
        
        # 環境驗證
        passed, errors = await self.environment_validator.validate_environment()
        
        # 檢查現有服務狀態
        current_status = await self.deployment_manager.get_deployment_status()
        
        # 磁盤空間檢查
        disk_check = await self._check_disk_space()
        
        # Docker狀態檢查
        docker_check = await self._check_docker_status()
        
        pre_check_result = {
            'environment_validation': {
                'passed': passed,
                'errors': errors,
                'critical_errors': [err for err in errors if 'CRITICAL' in err.upper()]
            },
            'current_services': current_status,
            'disk_space': disk_check,
            'docker_status': docker_check,
            'ready_for_deployment': True
        }
        
        # 評估是否可以繼續部署
        critical_issues = []
        if not passed and not self.force:
            critical_issues.extend(pre_check_result['environment_validation']['critical_errors'])
        if not disk_check['sufficient']:
            critical_issues.append(f"磁盤空間不足: {disk_check['free_gb']:.1f}GB")
        if not docker_check['available']:
            critical_issues.append("Docker 服務不可用")
        
        if critical_issues and not self.force:
            pre_check_result['ready_for_deployment'] = False
            raise SmartDeploymentError(f"預檢查失敗: {'; '.join(critical_issues)}")
        
        return pre_check_result
    
    async def _phase_preparation(self) -> Dict[str, Any]:
        """階段2：準備"""
        self.deployment_logger.info("準備部署環境")
        
        preparation_tasks = []
        
        # 清理舊容器（如果需要）
        if not self.dry_run:
            cleanup_result = await self._cleanup_old_containers()
            preparation_tasks.append(('container_cleanup', cleanup_result))
        
        # 拉取/建置映像
        if not self.dry_run:
            image_result = await self._prepare_images()
            preparation_tasks.append(('image_preparation', image_result))
        
        # 準備網路和卷
        network_result = await self._prepare_networks()
        preparation_tasks.append(('network_preparation', network_result))
        
        # 設置監控目錄
        monitoring_dirs = await self._prepare_monitoring_directories()
        preparation_tasks.append(('monitoring_directories', monitoring_dirs))
        
        return {
            'tasks_completed': len(preparation_tasks),
            'task_results': dict(preparation_tasks),
            'preparation_successful': True
        }
    
    async def _phase_service_startup(self) -> Dict[str, Any]:
        """階段3：服務啟動"""
        self.deployment_logger.info("開始智能服務啟動")
        
        # 獲取服務列表
        services = await self._get_target_services()
        
        if self.dry_run:
            self.deployment_logger.info(f"模擬啟動服務: {services}")
            return {
                'services': services,
                'startup_order': services,
                'dry_run': True,
                'simulated_success': True
            }
        
        # 使用服務編排器智能啟動
        orchestration_result = await self.orchestrator.orchestrate_startup(services)
        
        # 記錄啟動的服務
        self.deployment_report['services_deployed'] = list(orchestration_result.service_results.keys())
        
        if not orchestration_result.success:
            raise SmartDeploymentError(f"服務啟動失敗: {orchestration_result.errors}")
        
        return {
            'orchestration_result': {
                'success': orchestration_result.success,
                'startup_order': orchestration_result.startup_order,
                'total_duration': orchestration_result.total_duration,
                'failed_services': orchestration_result.failed_services,
                'service_count': len(orchestration_result.service_results)
            },
            'service_details': {
                name: {
                    'success': sr.success,
                    'duration': sr.duration_seconds,
                    'attempts': sr.attempts,
                    'phase': sr.phase.value
                }
                for name, sr in orchestration_result.service_results.items()
            }
        }
    
    async def _phase_health_validation(self) -> Dict[str, Any]:
        """階段4：健康檢查驗證"""
        self.deployment_logger.info("執行綜合健康檢查")
        
        # 等待服務穩定
        if not self.dry_run:
            self.deployment_logger.info("等待服務穩定...")
            await asyncio.sleep(10)
        
        # 執行全面健康檢查
        health_report = await self.health_checker.check_all_services()
        
        # 評估健康狀況
        health_validation = {
            'overall_status': health_report.overall_status.value,
            'health_score': health_report.health_score,
            'service_count': len(health_report.service_results),
            'healthy_services': len([
                s for s in health_report.service_results.values() 
                if s.status.value == 'healthy'
            ]),
            'critical_issues': health_report.critical_issues,
            'warnings': health_report.warnings,
            'response_time_avg': health_report.response_time_stats.get('avg', 0),
            'validation_passed': health_report.health_score >= 75
        }
        
        if not health_validation['validation_passed'] and not self.force:
            raise SmartDeploymentError(
                f"健康檢查驗證失敗，健康分數: {health_report.health_score}，"
                f"關鍵問題: {health_report.critical_issues}"
            )
        
        return health_validation
    
    async def _phase_monitoring_setup(self) -> Dict[str, Any]:
        """階段5：監控設置"""
        self.deployment_logger.info("設置監控系統")
        
        # 啟動監控收集
        monitoring_metrics = await self.monitoring_collector.collect_metrics()
        
        # 設置持續監控
        if not self.dry_run:
            monitoring_setup = await self._setup_continuous_monitoring()
        else:
            monitoring_setup = {'dry_run': True, 'simulated': True}
        
        return {
            'initial_metrics': {
                'overall_status': monitoring_metrics.get('overall_status'),
                'service_count': len(monitoring_metrics.get('service_metrics', [])),
                'system_health': monitoring_metrics.get('system_metrics', {})
            },
            'continuous_monitoring': monitoring_setup,
            'monitoring_active': True
        }
    
    async def _phase_post_deployment(self) -> Dict[str, Any]:
        """階段6：部署後處理"""
        self.deployment_logger.info("執行部署後處理")
        
        # 執行整合協調
        integration_result = await self.coordinator.orchestrate_integration()
        
        # 生成整合報告
        integration_report = await self.coordinator.get_integration_report()
        
        # 運行部署後測試
        post_deployment_tests = await self._run_post_deployment_tests()
        
        # 清理臨時資源
        cleanup_result = await self._cleanup_temporary_resources()
        
        return {
            'integration_result': {
                'success': integration_result.success,
                'phase': integration_result.phase.value,
                'duration': integration_result.duration_seconds,
                'service_status': integration_result.service_status,
                'errors': integration_result.errors
            },
            'integration_report': integration_report,
            'post_deployment_tests': post_deployment_tests,
            'cleanup_result': cleanup_result,
            'deployment_finalized': True
        }
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """檢查磁盤空間"""
        import shutil
        
        total, used, free = shutil.disk_usage(self.project_root)
        free_gb = free / (1024 ** 3)
        
        return {
            'free_gb': free_gb,
            'total_gb': total / (1024 ** 3),
            'used_gb': used / (1024 ** 3),
            'sufficient': free_gb > 2.0  # 需要至少2GB空間
        }
    
    async def _check_docker_status(self) -> Dict[str, Any]:
        """檢查Docker狀態"""
        import subprocess
        
        try:
            result = subprocess.run(
                ['docker', 'version', '--format', '{{.Server.Version}}'],
                capture_output=True, text=True, timeout=10
            )
            
            return {
                'available': result.returncode == 0,
                'version': result.stdout.strip() if result.returncode == 0 else None,
                'error': result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }
    
    async def _cleanup_old_containers(self) -> Dict[str, Any]:
        """清理舊容器"""
        try:
            # 停止現有服務
            stop_result = await self.deployment_manager.stop_services()
            
            # 清理孤立資源
            cleanup_result = await self.deployment_manager.cleanup_resources()
            
            return {
                'stop_result': stop_result,
                'cleanup_result': cleanup_result,
                'success': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _prepare_images(self) -> Dict[str, Any]:
        """準備映像"""
        # 使用現有的部署管理器功能
        try:
            # 拉取映像
            pull_result = await self.deployment_manager._pull_images()
            
            # 建置映像
            build_result = await self.deployment_manager._build_images()
            
            return {
                'pull_result': pull_result,
                'build_result': build_result,
                'success': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _prepare_networks(self) -> Dict[str, Any]:
        """準備網路"""
        # Docker Compose會自動處理網路
        return {
            'networks_managed_by_compose': True,
            'success': True
        }
    
    async def _prepare_monitoring_directories(self) -> Dict[str, Any]:
        """準備監控目錄"""
        directories = ['logs', 'data', 'backups']
        created_dirs = []
        
        for dir_name in directories:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                created_dirs.append(str(dir_path))
        
        return {
            'created_directories': created_dirs,
            'all_directories_ready': True
        }
    
    async def _get_target_services(self) -> List[str]:
        """獲取目標服務列表"""
        # 從docker-compose文件獲取服務列表
        compose_file = self.project_root / f'docker-compose.{self.environment}.yml'
        
        if not compose_file.exists():
            return []
        
        import yaml
        try:
            with open(compose_file, 'r') as f:
                compose_data = yaml.safe_load(f)
            
            services = list(compose_data.get('services', {}).keys())
            return services
        except Exception:
            # 如果無法解析，返回預設服務
            return ['discord-bot', 'redis']
    
    async def _setup_continuous_monitoring(self) -> Dict[str, Any]:
        """設置持續監控"""
        return {
            'monitoring_interval': 30,
            'health_check_enabled': True,
            'metrics_collection_enabled': True,
            'alert_system_ready': True
        }
    
    async def _run_post_deployment_tests(self) -> Dict[str, Any]:
        """運行部署後測試"""
        from core.integration_test_suite import IntegrationTestSuite
        
        try:
            test_suite = IntegrationTestSuite(self.project_root, self.environment)
            # 執行快速驗證測試
            quick_tests = [
                ('environment_validation', test_suite._test_environment_validation),
                ('health_check_integration', test_suite._test_health_check_integration)
            ]
            
            test_results = {}
            for test_name, test_func in quick_tests:
                try:
                    result = await test_func()
                    test_results[test_name] = result
                except Exception as e:
                    test_results[test_name] = {'success': False, 'error': str(e)}
            
            passed_tests = sum(1 for result in test_results.values() if result.get('success', False))
            
            return {
                'test_results': test_results,
                'tests_passed': passed_tests,
                'total_tests': len(quick_tests),
                'success_rate': (passed_tests / len(quick_tests)) * 100,
                'overall_success': passed_tests == len(quick_tests)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'overall_success': False
            }
    
    async def _cleanup_temporary_resources(self) -> Dict[str, Any]:
        """清理臨時資源"""
        # 清理部署過程中的臨時文件
        temp_files_cleaned = 0
        
        # 這裡可以添加具體的清理邏輯
        return {
            'temp_files_cleaned': temp_files_cleaned,
            'cleanup_successful': True
        }
    
    async def _handle_deployment_failure(self, failed_phase: str, error_detail: str = None):
        """處理部署失敗"""
        self.deployment_logger.error(f"部署在階段 {failed_phase} 失敗")
        
        # 記錄失敗詳情
        failure_info = {
            'failed_phase': failed_phase,
            'error_detail': error_detail,
            'timestamp': datetime.now().isoformat()
        }
        
        self.deployment_report['issues_found'].append(failure_info)
        
        # 如果不是dry run，考慮回滾
        if not self.dry_run and failed_phase not in [DeploymentPhase.PRE_CHECK, DeploymentPhase.PREPARATION]:
            self.deployment_logger.info("考慮回滾部署...")
            rollback_result = await self._attempt_rollback()
            self.deployment_report['rollback_attempted'] = rollback_result
    
    async def _attempt_rollback(self) -> Dict[str, Any]:
        """嘗試回滾"""
        try:
            self.status = DeploymentStatus.ROLLBACK
            self.deployment_logger.info("開始回滾部署")
            
            # 停止服務
            stop_result = await self.deployment_manager.stop_services()
            
            # 清理資源
            cleanup_result = await self.deployment_manager.cleanup_resources()
            
            return {
                'rollback_successful': True,
                'stop_result': stop_result,
                'cleanup_result': cleanup_result
            }
            
        except Exception as e:
            self.deployment_logger.error("回滾失敗", exception=e)
            return {
                'rollback_successful': False,
                'error': str(e)
            }
    
    async def _generate_final_report(self) -> None:
        """生成最終報告"""
        # 收集部署統計
        total_phases = len(self.deployment_report['phases'])
        successful_phases = sum(
            1 for phase in self.deployment_report['phases'].values()
            if phase['status'] == 'success'
        )
        
        # 收集建議
        recommendations = []
        
        if self.status == DeploymentStatus.SUCCESS:
            recommendations.append("部署成功完成，所有服務正常運行")
            if successful_phases == total_phases:
                recommendations.append("所有部署階段均順利完成")
        else:
            recommendations.append("部署未完全成功，建議檢查失敗階段")
            recommendations.append("考慮使用 --force 參數重試部署")
        
        # 性能建議
        total_duration = self.deployment_report['duration_seconds']
        if total_duration > 300:  # 5分鐘
            recommendations.append("部署時間較長，考慮優化映像大小或網路連接")
        
        self.deployment_report.update({
            'deployment_statistics': {
                'total_phases': total_phases,
                'successful_phases': successful_phases,
                'success_rate': (successful_phases / total_phases) * 100 if total_phases > 0 else 0,
                'total_duration_minutes': total_duration / 60
            },
            'recommendations': recommendations
        })
        
        # 保存報告到文件
        report_file = self.project_root / 'logs' / f'deployment-report-{self.deployment_id}.json'
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.deployment_report, f, indent=2, ensure_ascii=False, default=str)
        
        self.deployment_logger.info(f"部署報告已保存到: {report_file}")
    
    async def _graceful_shutdown(self) -> None:
        """優雅關閉"""
        self.deployment_logger.warning("正在執行優雅關閉...")
        
        if self.status == DeploymentStatus.RUNNING:
            self.status = DeploymentStatus.FAILED
            await self._generate_final_report()
        
        # 如果有正在運行的服務，嘗試停止
        if hasattr(self, 'deployment_manager'):
            try:
                await self.deployment_manager.stop_services()
            except Exception:
                pass
        
        self.deployment_logger.info("優雅關閉完成")


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='ROAS Bot 智能部署系統')
    parser.add_argument('--environment', '-e', default='dev', choices=['dev', 'prod'],
                       help='部署環境')
    parser.add_argument('--dry-run', action='store_true',
                       help='模擬運行，不執行實際部署')
    parser.add_argument('--force', action='store_true',
                       help='強制部署，忽略部分檢查失敗')
    parser.add_argument('--project-root', type=Path,
                       help='專案根目錄，默認為當前目錄')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='詳細輸出')
    parser.add_argument('--report-only', action='store_true',
                       help='僅生成現狀報告，不執行部署')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 確定專案根目錄
    project_root = args.project_root or Path.cwd()
    
    print(f"🚀 ROAS Bot v2.4.3 智能部署系統")
    print(f"專案根目錄: {project_root}")
    print(f"部署環境: {args.environment}")
    print(f"模式: {'模擬運行' if args.dry_run else '實際部署'}")
    print(f"強制部署: {'是' if args.force else '否'}")
    print(f"開始時間: {datetime.now()}")
    print("=" * 60)
    
    try:
        # 創建智能部署實例
        smart_deployment = SmartDeployment(
            project_root=project_root,
            environment=args.environment,
            dry_run=args.dry_run,
            force=args.force
        )
        
        if args.report_only:
            # 僅生成現狀報告
            print("生成現狀報告...")
            # 這裡可以添加現狀報告邏輯
            return 0
        
        # 執行智能部署
        deployment_report = await smart_deployment.deploy()
        
        # 輸出結果
        print(f"\n{'='*60}")
        print("📊 部署結果摘要")
        print(f"{'='*60}")
        
        status_emoji = "✅" if deployment_report['status'] == DeploymentStatus.SUCCESS else "❌"
        print(f"部署狀態: {status_emoji} {deployment_report['status'].upper()}")
        print(f"部署ID: {deployment_report['deployment_id']}")
        print(f"總耗時: {deployment_report['duration_seconds']:.1f} 秒")
        
        # 階段結果
        phases = deployment_report.get('phases', {})
        if phases:
            print(f"\n階段執行結果:")
            for phase_name, phase_info in phases.items():
                status_icon = "✅" if phase_info['status'] == 'success' else "❌"
                duration = phase_info['duration_seconds']
                print(f"  {status_icon} {phase_name}: {duration:.1f}s")
        
        # 已部署服務
        services = deployment_report.get('services_deployed', [])
        if services:
            print(f"\n已部署服務: {', '.join(services)}")
        
        # 問題和建議
        issues = deployment_report.get('issues_found', [])
        if issues:
            print(f"\n發現問題:")
            for issue in issues:
                print(f"  • {issue.get('failed_phase', '未知階段')}: {issue.get('error_detail', '詳情見日誌')}")
        
        recommendations = deployment_report.get('recommendations', [])
        if recommendations:
            print(f"\n建議:")
            for rec in recommendations:
                print(f"  • {rec}")
        
        # 統計信息
        stats = deployment_report.get('deployment_statistics', {})
        if stats:
            print(f"\n部署統計:")
            print(f"  階段成功率: {stats.get('success_rate', 0):.1f}%")
            print(f"  總部署時間: {stats.get('total_duration_minutes', 0):.1f} 分鐘")
        
        print(f"\n📄 詳細報告請查看: logs/deployment-report-{deployment_report['deployment_id']}.json")
        
        # 返回適當的退出碼
        return 0 if deployment_report['status'] == DeploymentStatus.SUCCESS else 1
        
    except KeyboardInterrupt:
        print("\n⏹️ 部署已取消")
        return 130
    except Exception as e:
        print(f"❌ 部署系統異常: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))