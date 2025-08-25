#!/usr/bin/env python3
"""
服務整合測試套件
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個測試套件驗證所有服務整合功能，包括API契約、服務啟動編排、
健康檢查、日誌整合和錯誤處理機制。
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import sys
import os

# 添加核心模組到路徑
sys.path.insert(0, str(Path(__file__).parent))

from service_integration_coordinator import ServiceIntegrationCoordinator
from api_contracts import IntegrationContractValidator
from service_startup_orchestrator import ServiceStartupOrchestrator
from unified_health_checker import UnifiedHealthChecker
from unified_logging_integration import UnifiedLogHandler, create_logger
from deployment_manager import DeploymentManager
from environment_validator import EnvironmentValidator

logger = logging.getLogger(__name__)


class IntegrationTestSuite:
    """服務整合測試套件"""
    
    def __init__(self, project_root: Path, environment: str = 'dev'):
        self.project_root = project_root
        self.environment = environment
        self.logger = create_logger("integration-test", "test-suite")
        
        # 測試結果
        self.test_results: Dict[str, Dict[str, Any]] = {}
        
        # 初始化組件
        self.coordinator = ServiceIntegrationCoordinator(project_root, environment)
        self.contract_validator = IntegrationContractValidator()
        self.startup_orchestrator = ServiceStartupOrchestrator(project_root, environment)
        self.health_checker = UnifiedHealthChecker(project_root)
        self.log_handler = UnifiedLogHandler.get_instance()
        self.deployment_manager = DeploymentManager(project_root, f'docker-compose.{environment}.yml')
        self.environment_validator = EnvironmentValidator(project_root)
    
    async def run_full_integration_test(self) -> Dict[str, Any]:
        """執行完整的整合測試"""
        self.logger.info("🚀 開始完整服務整合測試")
        start_time = time.time()
        
        test_summary = {
            'start_time': datetime.now().isoformat(),
            'test_results': {},
            'overall_success': False,
            'duration_seconds': 0,
            'recommendations': []
        }
        
        # 測試階段
        test_phases = [
            ("環境驗證測試", self._test_environment_validation),
            ("API契約測試", self._test_api_contracts),
            ("服務啟動編排測試", self._test_startup_orchestration),
            ("健康檢查整合測試", self._test_health_check_integration),
            ("日誌整合測試", self._test_logging_integration),
            ("端到端整合測試", self._test_end_to_end_integration),
            ("錯誤恢復測試", self._test_error_recovery),
            ("性能基準測試", self._test_performance_benchmarks)
        ]
        
        passed_tests = 0
        total_tests = len(test_phases)
        
        for phase_name, test_function in test_phases:
            self.logger.info(f"執行測試階段: {phase_name}")
            
            try:
                phase_result = await test_function()
                test_summary['test_results'][phase_name] = phase_result
                
                if phase_result.get('success', False):
                    passed_tests += 1
                    self.logger.info(f"✅ {phase_name} 通過")
                else:
                    self.logger.error(f"❌ {phase_name} 失敗: {phase_result.get('error', '未知錯誤')}")
                
            except Exception as e:
                self.logger.error(f"❌ {phase_name} 異常: {str(e)}", exception=e)
                test_summary['test_results'][phase_name] = {
                    'success': False,
                    'error': str(e),
                    'phase': phase_name
                }
        
        # 計算總體結果
        total_duration = time.time() - start_time
        test_summary['duration_seconds'] = total_duration
        test_summary['overall_success'] = passed_tests == total_tests
        test_summary['passed_tests'] = passed_tests
        test_summary['total_tests'] = total_tests
        test_summary['success_rate'] = (passed_tests / total_tests) * 100
        
        # 生成建議
        test_summary['recommendations'] = self._generate_test_recommendations(test_summary)
        
        self.logger.info(f"整合測試完成: {passed_tests}/{total_tests} 通過 ({test_summary['success_rate']:.1f}%)")
        return test_summary
    
    async def _test_environment_validation(self) -> Dict[str, Any]:
        """測試環境驗證"""
        try:
            # 執行環境檢查
            validation_success, validation_errors = await self.environment_validator.validate_environment()
            
            # 生成環境報告
            report = self.environment_validator.generate_report()
            
            return {
                'success': validation_success,
                'validation_errors': validation_errors,
                'system_info': report.system_info,
                'total_validations': len(report.validation_results),
                'passed_validations': len([r for r in report.validation_results if r.passed]),
                'recommendations': report.recommendations
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': 'environment_validation'
            }
    
    async def _test_api_contracts(self) -> Dict[str, Any]:
        """測試API契約"""
        try:
            # 驗證所有契約
            contract_results = self.contract_validator.validate_all_contracts()
            
            # 分析結果
            all_valid = True
            total_checks = 0
            passed_checks = 0
            
            for service, result in contract_results.items():
                if isinstance(result, dict) and 'endpoints_valid' in result:
                    total_checks += 1
                    if result['endpoints_valid']:
                        passed_checks += 1
                    else:
                        all_valid = False
            
            return {
                'success': all_valid,
                'contract_results': contract_results,
                'total_checks': total_checks,
                'passed_checks': passed_checks,
                'validation_summary': {
                    service: result.get('issues', []) if isinstance(result, dict) else str(result)
                    for service, result in contract_results.items()
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': 'api_contracts'
            }
    
    async def _test_startup_orchestration(self) -> Dict[str, Any]:
        """測試服務啟動編排"""
        try:
            # 執行啟動編排（模擬模式）
            result = await self.startup_orchestrator.orchestrate_startup(['redis', 'discord-bot'])
            
            return {
                'success': result.success,
                'startup_order': result.startup_order,
                'total_duration': result.total_duration,
                'failed_services': result.failed_services,
                'service_results': {
                    name: {
                        'success': sr.success,
                        'duration': sr.duration_seconds,
                        'attempts': sr.attempts,
                        'phase': sr.phase.value
                    }
                    for name, sr in result.service_results.items()
                },
                'recommendations': result.recommendations
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': 'startup_orchestration'
            }
    
    async def _test_health_check_integration(self) -> Dict[str, Any]:
        """測試健康檢查整合"""
        try:
            # 執行健康檢查
            health_report = await self.health_checker.check_all_services()
            
            return {
                'success': health_report.overall_status.value in ['healthy', 'degraded'],
                'overall_status': health_report.overall_status.value,
                'health_score': health_report.health_score,
                'service_count': len(health_report.service_results),
                'healthy_services': len([
                    s for s in health_report.service_results.values() 
                    if s.status.value == 'healthy'
                ]),
                'critical_issues': health_report.critical_issues,
                'warnings': health_report.warnings,
                'recommendations': health_report.recommendations,
                'response_time_stats': health_report.response_time_stats
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': 'health_check_integration'
            }
    
    async def _test_logging_integration(self) -> Dict[str, Any]:
        """測試日誌整合"""
        try:
            # 測試日誌記錄
            test_logger = create_logger("integration-test", "logging-test")
            
            # 記錄測試日誌
            with test_logger.context("logging-test") as ctx:
                test_logger.info("測試資訊日誌", tags={'test': 'logging'})
                test_logger.warning("測試警告日誌", tags={'test': 'logging'})
                test_logger.error("測試錯誤日誌", error_code="TEST-001", tags={'test': 'logging'})
            
            # 等待日誌處理
            await asyncio.sleep(2)
            
            # 獲取日誌統計
            log_stats = self.log_handler.get_stats()
            
            # 分析測試日誌
            analysis_report = self.log_handler.analyze_logs(hours=1)
            
            return {
                'success': True,
                'log_stats': log_stats,
                'analysis_report': {
                    'total_logs': analysis_report.total_logs,
                    'log_level_distribution': analysis_report.log_level_distribution,
                    'recommendations': analysis_report.recommendations
                },
                'test_logs_recorded': 3
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': 'logging_integration'
            }
    
    async def _test_end_to_end_integration(self) -> Dict[str, Any]:
        """測試端到端整合"""
        try:
            # 執行完整的整合協調
            integration_result = await self.coordinator.orchestrate_integration()
            
            # 獲取整合報告
            integration_report = await self.coordinator.get_integration_report()
            
            return {
                'success': integration_result.success,
                'integration_phase': integration_result.phase.value,
                'duration': integration_result.duration_seconds,
                'service_status': integration_result.service_status,
                'integration_health_score': integration_report['integration_health_score'],
                'contract_validation': integration_report['contract_validation'],
                'dependency_status': integration_report['dependency_status'],
                'recommendations': integration_report['recommendations'],
                'errors': integration_result.errors,
                'warnings': integration_result.warnings
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': 'end_to_end_integration'
            }
    
    async def _test_error_recovery(self) -> Dict[str, Any]:
        """測試錯誤恢復"""
        try:
            # 模擬錯誤情況
            test_error = Exception("模擬整合測試錯誤")
            error_context = {
                'operation': 'integration_test',
                'component': 'error_recovery_test',
                'test_scenario': 'simulated_error'
            }
            
            # 執行錯誤處理
            recovery_action = await self.coordinator.error_handler.handle_error(test_error, error_context)
            
            # 生成錯誤報告
            error_report = await self.coordinator.error_handler.generate_error_report(hours=1)
            
            return {
                'success': True,
                'recovery_action_type': recovery_action.action_type,
                'recovery_description': recovery_action.description,
                'error_report_summary': {
                    'total_errors': error_report.total_errors,
                    'resolution_success_rate': error_report.resolution_success_rate,
                    'recommendations': error_report.recommendations
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': 'error_recovery'
            }
    
    async def _test_performance_benchmarks(self) -> Dict[str, Any]:
        """測試性能基準"""
        try:
            # 記錄基準測試開始時間
            benchmark_start = time.time()
            
            # 並行執行多個操作來測試性能
            tasks = [
                self._benchmark_health_check(),
                self._benchmark_logging(),
                self._benchmark_contract_validation(),
            ]
            
            benchmark_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            total_benchmark_time = time.time() - benchmark_start
            
            # 分析結果
            successful_benchmarks = sum(1 for result in benchmark_results if not isinstance(result, Exception))
            
            return {
                'success': successful_benchmarks >= len(tasks) * 0.8,  # 至少80%成功
                'total_benchmark_time': total_benchmark_time,
                'benchmark_results': [
                    result if not isinstance(result, Exception) else {'error': str(result)}
                    for result in benchmark_results
                ],
                'successful_benchmarks': successful_benchmarks,
                'total_benchmarks': len(tasks),
                'performance_score': (successful_benchmarks / len(tasks)) * 100
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'phase': 'performance_benchmarks'
            }
    
    async def _benchmark_health_check(self) -> Dict[str, Any]:
        """健康檢查性能基準"""
        start_time = time.time()
        
        # 執行多次健康檢查
        iterations = 5
        total_checks = 0
        successful_checks = 0
        
        for i in range(iterations):
            try:
                report = await self.health_checker.check_all_services()
                total_checks += len(report.service_results)
                successful_checks += len([s for s in report.service_results.values() if s.status.value != 'unknown'])
            except Exception:
                pass
        
        duration = time.time() - start_time
        
        return {
            'benchmark_type': 'health_check',
            'iterations': iterations,
            'total_duration': duration,
            'avg_duration_per_iteration': duration / iterations,
            'total_checks': total_checks,
            'successful_checks': successful_checks,
            'success_rate': (successful_checks / total_checks) * 100 if total_checks > 0 else 0
        }
    
    async def _benchmark_logging(self) -> Dict[str, Any]:
        """日誌記錄性能基準"""
        start_time = time.time()
        
        # 記錄大量日誌
        test_logger = create_logger("benchmark", "logging")
        log_count = 100
        
        for i in range(log_count):
            test_logger.info(f"基準測試日誌 #{i}", tags={'benchmark': 'logging'})
        
        # 等待日誌處理
        await asyncio.sleep(1)
        
        duration = time.time() - start_time
        
        return {
            'benchmark_type': 'logging',
            'log_count': log_count,
            'total_duration': duration,
            'logs_per_second': log_count / duration,
            'avg_time_per_log': (duration / log_count) * 1000  # 毫秒
        }
    
    async def _benchmark_contract_validation(self) -> Dict[str, Any]:
        """契約驗證性能基準"""
        start_time = time.time()
        
        # 執行多次契約驗證
        iterations = 10
        
        for i in range(iterations):
            self.contract_validator.validate_all_contracts()
        
        duration = time.time() - start_time
        
        return {
            'benchmark_type': 'contract_validation',
            'iterations': iterations,
            'total_duration': duration,
            'avg_duration_per_iteration': duration / iterations
        }
    
    def _generate_test_recommendations(self, test_summary: Dict[str, Any]) -> List[str]:
        """生成測試建議"""
        recommendations = []
        
        success_rate = test_summary.get('success_rate', 0)
        
        if success_rate < 50:
            recommendations.append("整合測試成功率過低，需要全面檢查系統配置")
        elif success_rate < 80:
            recommendations.append("部分整合測試失敗，建議檢查失敗的測試項目")
        else:
            recommendations.append("整合測試表現良好")
        
        # 檢查特定測試失敗
        test_results = test_summary.get('test_results', {})
        
        failed_tests = [
            test_name for test_name, result in test_results.items()
            if not result.get('success', False)
        ]
        
        if failed_tests:
            recommendations.append(f"重點檢查失敗的測試: {', '.join(failed_tests)}")
        
        # 性能相關建議
        performance_result = test_results.get('性能基準測試', {})
        if performance_result.get('success') and performance_result.get('performance_score', 0) < 80:
            recommendations.append("系統性能有待提升，考慮優化慢速組件")
        
        return recommendations


async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 服務整合測試套件')
    parser.add_argument('--environment', '-e', default='dev', choices=['dev', 'prod'],
                       help='測試環境')
    parser.add_argument('--output', '-o', help='測試報告輸出路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    parser.add_argument('--quick', '-q', action='store_true', help='快速測試（跳過性能基準）')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 確定專案根目錄
    project_root = Path.cwd()
    
    print("🧪 ROAS Bot v2.4.3 服務整合測試套件")
    print(f"專案根目錄: {project_root}")
    print(f"測試環境: {args.environment}")
    print(f"開始時間: {datetime.now()}")
    print("="*60)
    
    try:
        # 創建測試套件
        test_suite = IntegrationTestSuite(project_root, args.environment)
        
        # 執行完整測試
        test_summary = await test_suite.run_full_integration_test()
        
        # 輸出結果
        success_rate = test_summary['success_rate']
        print(f"\n{'='*60}")
        print("📊 測試結果摘要")
        print(f"{'='*60}")
        print(f"整體狀態: {'✅ 通過' if test_summary['overall_success'] else '❌ 失敗'}")
        print(f"成功率: {success_rate:.1f}% ({test_summary['passed_tests']}/{test_summary['total_tests']})")
        print(f"總耗時: {test_summary['duration_seconds']:.1f} 秒")
        
        # 測試詳情
        print(f"\n測試詳情:")
        for test_name, result in test_summary['test_results'].items():
            status = "✅" if result.get('success', False) else "❌"
            print(f"  {status} {test_name}")
            if not result.get('success', False) and result.get('error'):
                print(f"    錯誤: {result['error']}")
        
        # 建議
        if test_summary['recommendations']:
            print(f"\n💡 建議:")
            for rec in test_summary['recommendations']:
                print(f"  • {rec}")
        
        # 保存報告
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(test_summary, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n📄 測試報告已保存到: {args.output}")
        
        return 0 if test_summary['overall_success'] else 1
        
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 測試執行失敗: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))