#!/usr/bin/env python3
"""
系統整合驗證腳本
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個腳本驗證整個智能部署和管理系統的完整性，
確保所有整合組件能夠正確協作和互操作。
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import logging
import json

# 添加核心模組到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.service_integration_coordinator import ServiceIntegrationCoordinator
from core.api_contracts import IntegrationContractValidator
from core.service_startup_orchestrator import ServiceStartupOrchestrator
from core.unified_health_checker import UnifiedHealthChecker
from core.unified_logging_integration import create_logger, get_log_handler
from core.integration_test_suite import IntegrationTestSuite
from scripts.smart_deployment import SmartDeployment

logger = logging.getLogger(__name__)


class SystemIntegrationValidator:
    """系統整合驗證器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.validation_logger = create_logger("system-validation", "integration")
        self.validation_results = {}
    
    async def run_complete_validation(self) -> Dict[str, Any]:
        """執行完整的系統整合驗證"""
        self.validation_logger.info("🔍 開始系統整合驗證")
        start_time = time.time()
        
        validation_summary = {
            'validation_id': f"validation-{int(time.time())}",
            'start_time': datetime.now().isoformat(),
            'components_validated': [],
            'integration_tests': {},
            'overall_status': 'unknown',
            'recommendations': [],
            'duration_seconds': 0
        }
        
        # 驗證階段
        validation_phases = [
            ("組件初始化驗證", self._validate_component_initialization),
            ("API契約驗證", self._validate_api_contracts),
            ("服務編排驗證", self._validate_service_orchestration),
            ("健康檢查驗證", self._validate_health_checking),
            ("日誌系統驗證", self._validate_logging_system),
            ("部署系統驗證", self._validate_deployment_system),
            ("端到端整合驗證", self._validate_end_to_end_integration),
            ("性能和穩定性驗證", self._validate_performance_stability)
        ]
        
        passed_validations = 0
        total_validations = len(validation_phases)
        
        for phase_name, validation_func in validation_phases:
            self.validation_logger.info(f"執行驗證: {phase_name}")
            
            try:
                validation_result = await validation_func()
                validation_summary['integration_tests'][phase_name] = validation_result
                
                if validation_result.get('passed', False):
                    passed_validations += 1
                    self.validation_logger.info(f"✅ {phase_name} 驗證通過")
                else:
                    self.validation_logger.error(f"❌ {phase_name} 驗證失敗")
                
            except Exception as e:
                self.validation_logger.error(f"❌ {phase_name} 驗證異常", exception=e)
                validation_summary['integration_tests'][phase_name] = {
                    'passed': False,
                    'error': str(e),
                    'exception': True
                }
        
        # 計算整體結果
        success_rate = (passed_validations / total_validations) * 100
        validation_summary.update({
            'passed_validations': passed_validations,
            'total_validations': total_validations,
            'success_rate': success_rate,
            'overall_status': 'passed' if success_rate >= 80 else 'failed',
            'duration_seconds': time.time() - start_time
        })
        
        # 生成建議
        validation_summary['recommendations'] = self._generate_validation_recommendations(validation_summary)
        
        # 保存驗證報告
        await self._save_validation_report(validation_summary)
        
        return validation_summary
    
    async def _validate_component_initialization(self) -> Dict[str, Any]:
        """驗證組件初始化"""
        components_status = {}
        
        # 測試每個核心組件的初始化
        test_components = [
            ("ServiceIntegrationCoordinator", ServiceIntegrationCoordinator),
            ("IntegrationContractValidator", IntegrationContractValidator),
            ("ServiceStartupOrchestrator", ServiceStartupOrchestrator),
            ("UnifiedHealthChecker", UnifiedHealthChecker),
            ("IntegrationTestSuite", IntegrationTestSuite)
        ]
        
        for component_name, component_class in test_components:
            try:
                if component_name in ["ServiceIntegrationCoordinator", "ServiceStartupOrchestrator", "IntegrationTestSuite"]:
                    instance = component_class(self.project_root, 'dev')
                elif component_name == "UnifiedHealthChecker":
                    instance = component_class(self.project_root)
                else:
                    instance = component_class()
                
                components_status[component_name] = {
                    'initialized': True,
                    'instance_type': str(type(instance)),
                    'has_required_methods': self._check_required_methods(instance, component_name)
                }
                
            except Exception as e:
                components_status[component_name] = {
                    'initialized': False,
                    'error': str(e)
                }
        
        all_initialized = all(comp['initialized'] for comp in components_status.values())
        
        return {
            'passed': all_initialized,
            'components_status': components_status,
            'total_components': len(test_components),
            'initialized_components': sum(1 for comp in components_status.values() if comp['initialized'])
        }
    
    def _check_required_methods(self, instance, component_name: str) -> bool:
        """檢查組件是否有必要的方法"""
        required_methods = {
            'ServiceIntegrationCoordinator': ['orchestrate_integration', 'get_integration_report'],
            'IntegrationContractValidator': ['validate_all_contracts'],
            'ServiceStartupOrchestrator': ['orchestrate_startup'],
            'UnifiedHealthChecker': ['check_all_services'],
            'IntegrationTestSuite': ['run_full_integration_test']
        }
        
        if component_name not in required_methods:
            return True
        
        return all(hasattr(instance, method) for method in required_methods[component_name])
    
    async def _validate_api_contracts(self) -> Dict[str, Any]:
        """驗證API契約系統"""
        try:
            contract_validator = IntegrationContractValidator()
            
            # 驗證所有契約
            contract_results = contract_validator.validate_all_contracts()
            
            # 分析結果
            valid_contracts = 0
            total_contracts = len(contract_results)
            
            for service, result in contract_results.items():
                if isinstance(result, dict) and result.get('endpoints_valid', False):
                    valid_contracts += 1
            
            return {
                'passed': valid_contracts == total_contracts,
                'contract_results': contract_results,
                'valid_contracts': valid_contracts,
                'total_contracts': total_contracts,
                'validation_details': {
                    service: result.get('issues', []) if isinstance(result, dict) else str(result)
                    for service, result in contract_results.items()
                }
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e)
            }
    
    async def _validate_service_orchestration(self) -> Dict[str, Any]:
        """驗證服務編排系統"""
        try:
            orchestrator = ServiceStartupOrchestrator(self.project_root, 'dev')
            
            # 測試服務編排（模擬模式）
            test_services = ['redis', 'discord-bot']
            orchestration_result = await orchestrator.orchestrate_startup(test_services)
            
            return {
                'passed': orchestration_result.success,
                'orchestration_success': orchestration_result.success,
                'startup_order': orchestration_result.startup_order,
                'total_duration': orchestration_result.total_duration,
                'service_results_count': len(orchestration_result.service_results),
                'failed_services': orchestration_result.failed_services,
                'recommendations': orchestration_result.recommendations
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e)
            }
    
    async def _validate_health_checking(self) -> Dict[str, Any]:
        """驗證健康檢查系統"""
        try:
            health_checker = UnifiedHealthChecker(self.project_root)
            
            # 執行健康檢查
            health_report = await health_checker.check_all_services()
            
            return {
                'passed': True,  # 健康檢查系統本身工作正常就算通過
                'health_report_generated': True,
                'overall_status': health_report.overall_status.value,
                'health_score': health_report.health_score,
                'services_checked': len(health_report.service_results),
                'response_time_stats': health_report.response_time_stats,
                'has_recommendations': len(health_report.recommendations) > 0
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e)
            }
    
    async def _validate_logging_system(self) -> Dict[str, Any]:
        """驗證日誌系統"""
        try:
            # 創建測試日誌器
            test_logger = create_logger("validation-test", "logging")
            
            # 測試日誌記錄
            with test_logger.context("validation-test") as ctx:
                test_logger.info("驗證測試資訊日誌")
                test_logger.warning("驗證測試警告日誌")
                test_logger.error("驗證測試錯誤日誌", error_code="VALIDATION-001")
            
            # 等待日誌處理
            await asyncio.sleep(2)
            
            # 檢查日誌處理器狀態
            log_handler = get_log_handler()
            stats = log_handler.get_stats()
            
            return {
                'passed': True,  # 能創建日誌器並記錄日誌就算通過
                'test_logs_recorded': 3,
                'log_handler_stats': stats,
                'thread_active': stats.get('thread_alive', False),
                'buffer_size': stats.get('buffer_size', 0)
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e)
            }
    
    async def _validate_deployment_system(self) -> Dict[str, Any]:
        """驗證部署系統"""
        try:
            # 創建智能部署實例
            smart_deployment = SmartDeployment(
                project_root=self.project_root,
                environment='dev',
                dry_run=True  # 模擬運行
            )
            
            # 執行模擬部署
            deployment_report = await smart_deployment.deploy()
            
            return {
                'passed': deployment_report['status'] in ['success', 'pending'],
                'deployment_system_available': True,
                'deployment_report_generated': True,
                'phases_executed': len(deployment_report.get('phases', {})),
                'dry_run_successful': deployment_report.get('status') != 'failed'
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e)
            }
    
    async def _validate_end_to_end_integration(self) -> Dict[str, Any]:
        """驗證端到端整合"""
        try:
            # 使用整合協調器
            coordinator = ServiceIntegrationCoordinator(self.project_root, 'dev')
            
            # 執行整合
            integration_result = await coordinator.orchestrate_integration()
            
            # 獲取整合報告
            integration_report = await coordinator.get_integration_report()
            
            return {
                'passed': integration_result.success,
                'integration_success': integration_result.success,
                'integration_phase': integration_result.phase.value,
                'duration_seconds': integration_result.duration_seconds,
                'service_status': integration_result.service_status,
                'integration_health_score': integration_report.get('integration_health_score', 0),
                'contract_validation': integration_report.get('contract_validation', {}),
                'errors': integration_result.errors,
                'warnings': integration_result.warnings
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e)
            }
    
    async def _validate_performance_stability(self) -> Dict[str, Any]:
        """驗證性能和穩定性"""
        try:
            # 運行快速性能測試
            start_time = time.time()
            
            # 測試多個組件的並發初始化
            tasks = [
                self._performance_test_health_check(),
                self._performance_test_contract_validation(),
                self._performance_test_logging()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            total_time = time.time() - start_time
            successful_tests = sum(1 for result in results if not isinstance(result, Exception))
            
            return {
                'passed': successful_tests >= len(tasks) * 0.8,  # 80%成功率
                'total_performance_time': total_time,
                'successful_tests': successful_tests,
                'total_tests': len(tasks),
                'performance_acceptable': total_time < 30,  # 30秒內完成
                'test_results': [
                    result if not isinstance(result, Exception) else {'error': str(result)}
                    for result in results
                ]
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e)
            }
    
    async def _performance_test_health_check(self) -> Dict[str, Any]:
        """性能測試：健康檢查"""
        start_time = time.time()
        
        health_checker = UnifiedHealthChecker(self.project_root)
        
        # 執行多次健康檢查測試性能
        for i in range(3):
            await health_checker.check_all_services()
        
        return {
            'test_type': 'health_check_performance',
            'iterations': 3,
            'total_time': time.time() - start_time,
            'avg_time_per_check': (time.time() - start_time) / 3
        }
    
    async def _performance_test_contract_validation(self) -> Dict[str, Any]:
        """性能測試：契約驗證"""
        start_time = time.time()
        
        validator = IntegrationContractValidator()
        
        # 執行多次契約驗證測試性能
        for i in range(5):
            validator.validate_all_contracts()
        
        return {
            'test_type': 'contract_validation_performance',
            'iterations': 5,
            'total_time': time.time() - start_time,
            'avg_time_per_validation': (time.time() - start_time) / 5
        }
    
    async def _performance_test_logging(self) -> Dict[str, Any]:
        """性能測試：日誌系統"""
        start_time = time.time()
        
        test_logger = create_logger("performance-test", "logging")
        
        # 記錄大量日誌測試性能
        for i in range(50):
            test_logger.info(f"性能測試日誌 #{i}")
        
        # 等待處理
        await asyncio.sleep(1)
        
        return {
            'test_type': 'logging_performance',
            'log_count': 50,
            'total_time': time.time() - start_time,
            'logs_per_second': 50 / (time.time() - start_time)
        }
    
    def _generate_validation_recommendations(self, validation_summary: Dict[str, Any]) -> List[str]:
        """生成驗證建議"""
        recommendations = []
        
        success_rate = validation_summary.get('success_rate', 0)
        
        if success_rate >= 90:
            recommendations.append("系統整合驗證優秀，所有組件協作良好")
        elif success_rate >= 80:
            recommendations.append("系統整合驗證良好，部分項目需要關注")
        else:
            recommendations.append("系統整合驗證需要改進，存在關鍵問題")
        
        # 檢查失敗的驗證
        failed_validations = []
        for test_name, result in validation_summary.get('integration_tests', {}).items():
            if not result.get('passed', False):
                failed_validations.append(test_name)
        
        if failed_validations:
            recommendations.append(f"需要修復的驗證項目: {', '.join(failed_validations)}")
        
        # 性能建議
        duration = validation_summary.get('duration_seconds', 0)
        if duration > 60:
            recommendations.append("驗證時間較長，建議優化組件初始化速度")
        
        return recommendations
    
    async def _save_validation_report(self, validation_summary: Dict[str, Any]) -> None:
        """保存驗證報告"""
        report_file = self.project_root / 'logs' / f"system-validation-{validation_summary['validation_id']}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(validation_summary, f, indent=2, ensure_ascii=False, default=str)
        
        self.validation_logger.info(f"驗證報告已保存到: {report_file}")


async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 系統整合驗證工具')
    parser.add_argument('--project-root', type=Path, help='專案根目錄')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    parser.add_argument('--output', '-o', help='輸出檔案路徑')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 確定專案根目錄
    project_root = args.project_root or Path.cwd()
    
    print(f"🔍 ROAS Bot v2.4.3 系統整合驗證")
    print(f"專案根目錄: {project_root}")
    print(f"開始時間: {datetime.now()}")
    print("=" * 60)
    
    try:
        # 執行系統整合驗證
        validator = SystemIntegrationValidator(project_root)
        validation_summary = await validator.run_complete_validation()
        
        # 輸出結果
        print(f"\\n{'='*60}")
        print("📊 系統整合驗證結果")
        print(f"{'='*60}")
        
        status_emoji = "✅" if validation_summary['overall_status'] == 'passed' else "❌"
        print(f"整體狀態: {status_emoji} {validation_summary['overall_status'].upper()}")
        print(f"成功率: {validation_summary['success_rate']:.1f}% ({validation_summary['passed_validations']}/{validation_summary['total_validations']})")
        print(f"驗證耗時: {validation_summary['duration_seconds']:.1f} 秒")
        
        # 驗證項目詳情
        print(f"\\n驗證項目結果:")
        for test_name, result in validation_summary.get('integration_tests', {}).items():
            status = "✅" if result.get('passed', False) else "❌"
            print(f"  {status} {test_name}")
            if not result.get('passed', False) and result.get('error'):
                print(f"    錯誤: {result['error']}")
        
        # 建議
        recommendations = validation_summary.get('recommendations', [])
        if recommendations:
            print(f"\\n💡 建議:")
            for rec in recommendations:
                print(f"  • {rec}")
        
        # 保存輸出
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(validation_summary, f, indent=2, ensure_ascii=False, default=str)
            print(f"\\n📄 驗證結果已保存到: {args.output}")
        
        return 0 if validation_summary['overall_status'] == 'passed' else 1
        
    except KeyboardInterrupt:
        print("\\n⏹️ 驗證已取消")
        return 130
    except Exception as e:
        print(f"❌ 驗證過程異常: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))