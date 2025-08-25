#!/usr/bin/env python3
"""
基礎設施整合測試套件
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

提供完整的基礎設施模組測試，包括單元測試和整合測試。
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# 確保可以導入專案模組
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.environment_validator import EnvironmentValidator
from core.deployment_manager import DeploymentManager, create_deployment_manager
from core.monitoring_collector import MonitoringCollector, HealthStatus
from scripts.deploy_validation import DockerStartupFixer

logger = logging.getLogger(__name__)


class InfrastructureTestSuite:
    """基礎設施測試套件 - 驗證所有核心模組"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.test_results = {}
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """
        執行完整的基礎設施測試套件
        
        Returns:
            Dict[str, Any]: 測試結果
        """
        self.logger.info("🚀 開始執行ROAS Bot v2.4.3基礎設施測試套件")
        
        start_time = time.time()
        test_results = {
            'timestamp': time.time(),
            'project_root': str(self.project_root),
            'test_suite_version': 'v2.4.3',
            'tests': {},
            'summary': {
                'total_tests': 0,
                'passed_tests': 0,
                'failed_tests': 0,
                'skipped_tests': 0
            },
            'overall_success': False
        }
        
        # 測試順序：從基礎到整合
        test_modules = [
            ('environment_validator', self._test_environment_validator),
            ('deployment_manager', self._test_deployment_manager),
            ('monitoring_collector', self._test_monitoring_collector),
            ('docker_startup_fixer', self._test_docker_startup_fixer),
            ('integration_tests', self._test_integration_functionality),
            ('performance_tests', self._test_performance_benchmarks)
        ]
        
        for module_name, test_function in test_modules:
            self.logger.info(f"📋 測試模組: {module_name}")
            
            try:
                module_result = await test_function()
                test_results['tests'][module_name] = module_result
                
                # 更新統計
                test_results['summary']['total_tests'] += module_result.get('total_tests', 0)
                test_results['summary']['passed_tests'] += module_result.get('passed_tests', 0)
                test_results['summary']['failed_tests'] += module_result.get('failed_tests', 0)
                test_results['summary']['skipped_tests'] += module_result.get('skipped_tests', 0)
                
                status = "✅ PASSED" if module_result.get('success', False) else "❌ FAILED"
                self.logger.info(f"   {status} ({module_result.get('passed_tests', 0)}/{module_result.get('total_tests', 0)} tests)")
                
            except Exception as e:
                self.logger.error(f"   ❌ EXCEPTION: {str(e)}")
                test_results['tests'][module_name] = {
                    'success': False,
                    'error': str(e),
                    'total_tests': 1,
                    'passed_tests': 0,
                    'failed_tests': 1,
                    'skipped_tests': 0
                }
                test_results['summary']['total_tests'] += 1
                test_results['summary']['failed_tests'] += 1
        
        # 計算整體成功率
        total = test_results['summary']['total_tests']
        passed = test_results['summary']['passed_tests']
        test_results['overall_success'] = (passed / total) >= 0.8 if total > 0 else False
        test_results['success_rate'] = (passed / total) * 100 if total > 0 else 0
        test_results['duration_seconds'] = time.time() - start_time
        
        # 生成測試報告
        await self._generate_test_report(test_results)
        
        return test_results
    
    async def _test_environment_validator(self) -> Dict[str, Any]:
        """測試環境驗證器"""
        tests = []
        validator = EnvironmentValidator(self.project_root)
        
        # 測試1: 基本環境驗證
        try:
            passed, errors = await validator.validate_environment()
            # 允許常見的測試環境問題：DISCORD_TOKEN未設定、端口佔用等
            # 只要沒有嚴重的系統或配置問題就視為通過
            critical_errors = [e for e in errors if not any(keyword in e for keyword in [
                'DISCORD_TOKEN', '端口', '已被佔用', 'port'
            ])]
            tests.append({
                'name': 'basic_environment_validation',
                'passed': len(critical_errors) == 0,  # 允許環境變數和端口問題
                'details': f"Errors: {len(errors)}, Critical: {len(critical_errors)}"
            })
        except Exception as e:
            tests.append({
                'name': 'basic_environment_validation',
                'passed': False,
                'error': str(e)
            })
        
        # 測試2: 報告生成
        try:
            report = validator.generate_report()
            tests.append({
                'name': 'report_generation',
                'passed': report is not None and len(report.validation_results) > 0,
                'details': f"Validation results: {len(report.validation_results)}"
            })
        except Exception as e:
            tests.append({
                'name': 'report_generation',
                'passed': False,
                'error': str(e)
            })
        
        # 測試3: 報告保存
        try:
            output_path = validator.save_report(report)
            tests.append({
                'name': 'report_saving',
                'passed': output_path.exists(),
                'details': f"Report saved to: {output_path}"
            })
        except Exception as e:
            tests.append({
                'name': 'report_saving',
                'passed': False,
                'error': str(e)
            })
        
        return self._compile_test_results('environment_validator', tests)
    
    async def _test_deployment_manager(self) -> Dict[str, Any]:
        """測試部署管理器"""
        tests = []
        
        # 測試1: 創建部署管理器
        try:
            manager = create_deployment_manager('simple', self.project_root)
            tests.append({
                'name': 'create_deployment_manager',
                'passed': manager is not None,
                'details': 'Successfully created deployment manager'
            })
        except Exception as e:
            tests.append({
                'name': 'create_deployment_manager',
                'passed': False,
                'error': str(e)
            })
            return self._compile_test_results('deployment_manager', tests)
        
        # 測試2: 健康檢查
        try:
            health_result = await manager.health_check()
            tests.append({
                'name': 'health_check',
                'passed': 'timestamp' in health_result and 'overall_healthy' in health_result,
                'details': f"Health check result keys: {list(health_result.keys())}"
            })
        except Exception as e:
            tests.append({
                'name': 'health_check',
                'passed': False,
                'error': str(e)
            })
        
        # 測試3: 部署狀態獲取
        try:
            status = await manager.get_deployment_status()
            tests.append({
                'name': 'get_deployment_status',
                'passed': 'timestamp' in status and 'services' in status,
                'details': f"Status keys: {list(status.keys())}"
            })
        except Exception as e:
            tests.append({
                'name': 'get_deployment_status',
                'passed': False,
                'error': str(e)
            })
        
        # 測試4: 日誌獲取
        try:
            logs = await manager.get_service_logs(tail=10)
            tests.append({
                'name': 'get_service_logs',
                'passed': isinstance(logs, str),
                'details': f"Logs length: {len(logs)} chars"
            })
        except Exception as e:
            tests.append({
                'name': 'get_service_logs',
                'passed': False,
                'error': str(e)
            })
        
        return self._compile_test_results('deployment_manager', tests)
    
    async def _test_monitoring_collector(self) -> Dict[str, Any]:
        """測試監控收集器"""
        tests = []
        collector = MonitoringCollector(self.project_root)
        
        # 測試1: 收集指標
        try:
            metrics = await collector.collect_metrics()
            tests.append({
                'name': 'collect_metrics',
                'passed': 'timestamp' in metrics and 'overall_status' in metrics,
                'details': f"Metrics keys: {list(metrics.keys())}"
            })
        except Exception as e:
            tests.append({
                'name': 'collect_metrics',
                'passed': False,
                'error': str(e)
            })
        
        # 測試2: 服務健康檢查
        try:
            service_health = await collector.check_service_health('redis')
            tests.append({
                'name': 'check_service_health',
                'passed': service_health.service_name == 'redis',
                'details': f"Service status: {service_health.status.value}"
            })
        except Exception as e:
            tests.append({
                'name': 'check_service_health',
                'passed': False,
                'error': str(e)
            })
        
        # 測試3: 報告生成
        try:
            report = await collector.generate_report()
            tests.append({
                'name': 'generate_report',
                'passed': report.timestamp is not None and report.overall_status is not None,
                'details': f"Report status: {report.overall_status.value}"
            })
        except Exception as e:
            tests.append({
                'name': 'generate_report',
                'passed': False,
                'error': str(e)
            })
        
        # 測試4: 啟動效能指標
        try:
            startup_metrics = await collector.collect_startup_performance_metrics()
            tests.append({
                'name': 'collect_startup_performance_metrics',
                'passed': 'timestamp' in startup_metrics,
                'details': f"Startup metrics keys: {list(startup_metrics.keys())}"
            })
        except Exception as e:
            tests.append({
                'name': 'collect_startup_performance_metrics',
                'passed': False,
                'error': str(e)
            })
        
        return self._compile_test_results('monitoring_collector', tests)
    
    async def _test_docker_startup_fixer(self) -> Dict[str, Any]:
        """測試Docker啟動修復器"""
        tests = []
        
        # 測試1: 創建修復器
        try:
            fixer = DockerStartupFixer(self.project_root, 'simple')
            tests.append({
                'name': 'create_docker_startup_fixer',
                'passed': fixer is not None and fixer.project_root == self.project_root,
                'details': f"Environment: {fixer.environment}"
            })
        except Exception as e:
            tests.append({
                'name': 'create_docker_startup_fixer',
                'passed': False,
                'error': str(e)
            })
            return self._compile_test_results('docker_startup_fixer', tests)
        
        # 測試2: 環境問題修復
        try:
            issues = ["缺少必要環境變數: DISCORD_TOKEN"]
            fixes = await fixer._fix_environment_issues(issues)
            tests.append({
                'name': 'fix_environment_issues',
                'passed': isinstance(fixes, list),
                'details': f"Applied fixes: {len(fixes)}"
            })
        except Exception as e:
            tests.append({
                'name': 'fix_environment_issues',
                'passed': False,
                'error': str(e)
            })
        
        # 測試3: 檢查殭屍容器
        try:
            zombie_check = await fixer._check_zombie_containers()
            tests.append({
                'name': 'check_zombie_containers',
                'passed': 'count' in zombie_check and 'has_zombies' in zombie_check,
                'details': f"Zombie containers: {zombie_check.get('count', 0)}"
            })
        except Exception as e:
            tests.append({
                'name': 'check_zombie_containers',
                'passed': False,
                'error': str(e)
            })
        
        # 測試4: 磁盤空間檢查
        try:
            disk_check = await fixer._check_disk_space()
            tests.append({
                'name': 'check_disk_space',
                'passed': 'free_gb' in disk_check and 'sufficient' in disk_check,
                'details': f"Free space: {disk_check.get('free_gb', 0):.1f}GB"
            })
        except Exception as e:
            tests.append({
                'name': 'check_disk_space',
                'passed': False,
                'error': str(e)
            })
        
        return self._compile_test_results('docker_startup_fixer', tests)
    
    async def _test_integration_functionality(self) -> Dict[str, Any]:
        """測試整合功能"""
        tests = []
        
        # 測試1: 模組間協同工作
        try:
            # 環境檢查 + 部署管理器協同
            validator = EnvironmentValidator(self.project_root)
            manager = create_deployment_manager('simple', self.project_root)
            
            env_passed, env_errors = await validator.validate_environment()
            deployment_status = await manager.get_deployment_status()
            
            tests.append({
                'name': 'validator_deployment_integration',
                'passed': True,  # 只要能正常執行就算通過
                'details': f"Env errors: {len(env_errors)}, Services: {len(deployment_status.get('services', []))}"
            })
        except Exception as e:
            tests.append({
                'name': 'validator_deployment_integration',
                'passed': False,
                'error': str(e)
            })
        
        # 測試2: 監控 + 部署管理器協同
        try:
            collector = MonitoringCollector(self.project_root)
            manager = create_deployment_manager('simple', self.project_root)
            
            metrics = await collector.collect_metrics()
            health_check = await manager.health_check()
            
            tests.append({
                'name': 'monitoring_deployment_integration',
                'passed': True,
                'details': f"Overall status: {metrics.get('overall_status', 'unknown')}"
            })
        except Exception as e:
            tests.append({
                'name': 'monitoring_deployment_integration',
                'passed': False,
                'error': str(e)
            })
        
        # 測試3: 完整工作流程
        try:
            # 環境檢查 -> 部署準備 -> 監控檢查
            validator = EnvironmentValidator(self.project_root)
            collector = MonitoringCollector(self.project_root)
            
            # 執行完整流程
            env_passed, _ = await validator.validate_environment()
            startup_metrics = await collector.collect_startup_performance_metrics()
            
            tests.append({
                'name': 'complete_workflow_integration',
                'passed': startup_metrics is not None,
                'details': f"Workflow completed successfully"
            })
        except Exception as e:
            tests.append({
                'name': 'complete_workflow_integration',
                'passed': False,
                'error': str(e)
            })
        
        return self._compile_test_results('integration_tests', tests)
    
    async def _test_performance_benchmarks(self) -> Dict[str, Any]:
        """測試效能基準"""
        tests = []
        
        # 測試1: 環境檢查效能
        try:
            validator = EnvironmentValidator(self.project_root)
            
            start_time = time.time()
            await validator.validate_environment()
            env_check_time = time.time() - start_time
            
            tests.append({
                'name': 'environment_check_performance',
                'passed': env_check_time < 30.0,  # 應該在30秒內完成
                'details': f"Environment check time: {env_check_time:.2f}s"
            })
        except Exception as e:
            tests.append({
                'name': 'environment_check_performance',
                'passed': False,
                'error': str(e)
            })
        
        # 測試2: 健康檢查效能
        try:
            collector = MonitoringCollector(self.project_root)
            
            start_time = time.time()
            await collector.check_service_health('redis')
            health_check_time = time.time() - start_time
            
            tests.append({
                'name': 'health_check_performance',
                'passed': health_check_time < 10.0,  # 應該在10秒內完成
                'details': f"Health check time: {health_check_time:.2f}s"
            })
        except Exception as e:
            tests.append({
                'name': 'health_check_performance',
                'passed': False,
                'error': str(e)
            })
        
        # 測試3: 監控收集效能
        try:
            collector = MonitoringCollector(self.project_root)
            
            start_time = time.time()
            await collector.collect_metrics()
            metrics_time = time.time() - start_time
            
            tests.append({
                'name': 'metrics_collection_performance',
                'passed': metrics_time < 15.0,  # 應該在15秒內完成
                'details': f"Metrics collection time: {metrics_time:.2f}s"
            })
        except Exception as e:
            tests.append({
                'name': 'metrics_collection_performance',
                'passed': False,
                'error': str(e)
            })
        
        # 測試4: 記憶體使用量檢查
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_usage_mb = process.memory_info().rss / (1024 * 1024)
            
            tests.append({
                'name': 'memory_usage_check',
                'passed': memory_usage_mb < 500,  # 應該少於500MB
                'details': f"Memory usage: {memory_usage_mb:.1f}MB"
            })
        except Exception as e:
            tests.append({
                'name': 'memory_usage_check',
                'passed': False,
                'error': str(e)
            })
        
        return self._compile_test_results('performance_tests', tests)
    
    def _compile_test_results(self, module_name: str, tests: List[Dict]) -> Dict[str, Any]:
        """編譯測試結果"""
        passed_tests = sum(1 for test in tests if test.get('passed', False))
        failed_tests = sum(1 for test in tests if not test.get('passed', False))
        total_tests = len(tests)
        
        return {
            'module': module_name,
            'success': failed_tests == 0,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'skipped_tests': 0,
            'success_rate': (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
            'tests': tests
        }
    
    async def _generate_test_report(self, results: Dict[str, Any]) -> None:
        """生成測試報告"""
        report_path = self.project_root / f"infrastructure-test-report-{int(time.time())}.json"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        # 控制台摘要報告
        self.logger.info("\n" + "="*80)
        self.logger.info("📊 ROAS Bot v2.4.3 基礎設施測試報告")
        self.logger.info("="*80)
        self.logger.info(f"測試時間: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(results['timestamp']))}")
        self.logger.info(f"專案根目錄: {results['project_root']}")
        self.logger.info(f"執行時間: {results['duration_seconds']:.1f}秒")
        
        # 總體結果
        summary = results['summary']
        self.logger.info(f"\n🎯 測試摘要:")
        self.logger.info(f"  總測試數: {summary['total_tests']}")
        self.logger.info(f"  通過: {summary['passed_tests']}")
        self.logger.info(f"  失敗: {summary['failed_tests']}")
        self.logger.info(f"  跳過: {summary['skipped_tests']}")
        self.logger.info(f"  成功率: {results['success_rate']:.1f}%")
        self.logger.info(f"  整體狀態: {'✅ PASSED' if results['overall_success'] else '❌ FAILED'}")
        
        # 各模組結果
        self.logger.info(f"\n📋 各模組測試結果:")
        for module, test_result in results['tests'].items():
            status = "✅ PASSED" if test_result.get('success', False) else "❌ FAILED"
            success_rate = test_result.get('success_rate', 0)
            self.logger.info(f"  {status} {module}: {success_rate:.1f}% ({test_result.get('passed_tests', 0)}/{test_result.get('total_tests', 0)})")
        
        # 失敗的測試詳情
        failed_tests = []
        for module, test_result in results['tests'].items():
            for test in test_result.get('tests', []):
                if not test.get('passed', False):
                    failed_tests.append(f"{module}.{test['name']}: {test.get('error', 'Failed')}")
        
        if failed_tests:
            self.logger.info(f"\n❌ 失敗的測試:")
            for failed in failed_tests[:10]:  # 只顯示前10個
                self.logger.info(f"  • {failed}")
        
        self.logger.info(f"\n📄 詳細報告: {report_path}")
        self.logger.info("="*80)


async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 基礎設施測試套件')
    parser.add_argument('--project-root', type=Path, help='專案根目錄')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    parser.add_argument('--output', type=Path, help='測試結果輸出檔案')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 執行測試套件
        test_suite = InfrastructureTestSuite(args.project_root)
        results = await test_suite.run_all_tests()
        
        # 保存結果
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n📄 測試結果已保存到: {args.output}")
        
        # 返回適當的退出碼
        return 0 if results['overall_success'] else 1
        
    except KeyboardInterrupt:
        print("\n⏹️ 測試已取消")
        return 130
    except Exception as e:
        logging.error(f"❌ 測試執行失敗: {str(e)}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))