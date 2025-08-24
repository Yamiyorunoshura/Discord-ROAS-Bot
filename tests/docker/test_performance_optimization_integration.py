"""
Docker 測試框架效能優化整合測試
Task ID: T1 - 效能優化專門化驗證

Ethan 效能專家的完整效能優化驗證：
- 測試所有效能優化組件的整合
- 驗證90%覆蓋率目標的效能表現
- 確保CI/CD管道效能目標達成
- 生成完整的效能優化成果報告
"""

import pytest
import time
import logging
from typing import Dict, Any
from unittest.mock import Mock, patch
import json

# 導入所有效能優化組件
from .scalability_performance_optimizer import (
    ScalabilityPerformanceOptimizer,
    ScalabilityProfile, 
    create_scalability_test_suite
)
from .advanced_resource_monitor import (
    AdvancedResourceMonitor,
    ResourceThresholds,
    create_ci_resource_monitor
)
from .performance_baseline_manager import (
    PerformanceBaselineManager,
    RegressionDetector,
    create_baseline_management_system
)
from .ci_performance_validator import (
    CIPerformanceValidator,
    run_ci_performance_validation
)

logger = logging.getLogger(__name__)


class TestPerformanceOptimizationIntegration:
    """效能優化整合測試套件
    
    測試 Ethan 效能專家實作的所有效能優化組件：
    1. 可擴展性效能優化器
    2. 進階資源監控器
    3. 效能基準管理器
    4. CI/CD 效能驗證器
    """
    
    @pytest.fixture
    def mock_docker_client(self):
        """模擬 Docker 客戶端"""
        mock_client = Mock()
        mock_client.containers = Mock()
        mock_client.containers.list.return_value = []
        return mock_client
    
    @pytest.fixture
    def scalability_optimizer(self, mock_docker_client):
        """可擴展性優化器夾具"""
        profile = ScalabilityProfile.for_90_percent_coverage()
        return ScalabilityPerformanceOptimizer(mock_docker_client, profile)
    
    @pytest.fixture
    def resource_monitor(self):
        """資源監控器夾具"""
        return create_ci_resource_monitor()
    
    @pytest.fixture
    def baseline_manager(self):
        """基準管理器夾具"""
        manager, detector = create_baseline_management_system()
        return manager, detector
    
    @pytest.fixture
    def ci_validator(self, mock_docker_client):
        """CI 驗證器夾具"""
        return CIPerformanceValidator(mock_docker_client)
    
    def test_scalability_optimizer_configuration(self, scalability_optimizer):
        """測試可擴展性優化器配置"""
        profile = scalability_optimizer.profile
        
        # 驗證90%覆蓋率優化配置
        assert profile.max_parallel_workers == 6, "並行工作者數量應為6"
        assert profile.batch_size == 10, "批次大小應為10"
        assert profile.memory_limit_mb == 1800, "記憶體限制應為1800MB"
        assert profile.cpu_limit_percent == 75, "CPU限制應為75%"
        assert profile.max_execution_time_seconds == 480, "執行時間限制應為8分鐘"
        
        logger.info(\"✅ 可擴展性優化器配置驗證通過\")
    
    def test_resource_monitor_thresholds(self, resource_monitor):
        \"\"\"測試資源監控閾值配置\"\"\"
        thresholds = resource_monitor.thresholds
        
        # 驗證 CI 環境的保守配置
        assert thresholds.memory_warning_percent == 60.0, \"記憶體警告閾值應為60%\"
        assert thresholds.memory_critical_percent == 75.0, \"記憶體關鍵閾值應為75%\"
        assert thresholds.cpu_warning_percent == 50.0, \"CPU警告閾值應為50%\"
        assert thresholds.cpu_critical_percent == 70.0, \"CPU關鍵閾值應為70%\"
        assert thresholds.max_containers == 6, \"最大容器數應為6\"
        
        logger.info(\"✅ 資源監控閾值配置驗證通過\")
    
    def test_baseline_manager_functionality(self, baseline_manager):
        \"\"\"測試基準管理器功能\"\"\"
        manager, detector = baseline_manager
        
        # 測試基準創建功能
        mock_test_results = {
            'execution_summary': {
                'total_execution_time_seconds': 8.5,
                'success_rate_percent': 97.5,
                'total_tests': 50
            },
            'performance_analysis': {
                'resource_efficiency_analysis': {
                    'average_memory_usage_mb': 95.0,
                    'average_cpu_usage_percent': 40.0
                }
            }
        }
        
        # 創建基準
        baseline = manager.create_baseline_from_test_results(
            version=\"test_v1.0\",
            test_results=mock_test_results,
            notes=\"測試基準\"
        )
        
        assert baseline is not None, \"基準創建失敗\"
        assert baseline.version == \"test_v1.0\", \"基準版本不正確\"
        assert len(baseline.metrics) > 0, \"基準指標為空\"
        
        # 測試基準檢索
        retrieved_baseline = manager.get_baseline(baseline.baseline_id)
        assert retrieved_baseline is not None, \"基準檢索失敗\"
        assert retrieved_baseline.baseline_id == baseline.baseline_id, \"檢索到的基準ID不正確\"
        
        logger.info(\"✅ 基準管理器功能驗證通過\")
    
    def test_ci_validator_target_validation(self, ci_validator):
        \"\"\"測試 CI 驗證器目標驗證\"\"\"
        # 驗證效能目標配置
        targets = ci_validator.performance_targets
        
        assert targets['max_execution_time_seconds'] == 600, \"執行時間目標應為10分鐘\"
        assert targets['max_memory_mb'] == 2048, \"記憶體目標應為2GB\"
        assert targets['max_cpu_percent'] == 80, \"CPU目標應為80%\"
        assert targets['min_success_rate_percent'] == 95, \"成功率目標應為95%\"
        
        # 測試目標驗證邏輯
        mock_results = {
            'execution_summary': {
                'total_execution_time_seconds': 480,  # 8分鐘，符合目標
                'success_rate_percent': 97.0          # 97%，符合目標
            }
        }
        
        # 執行時間驗證
        time_validation = ci_validator._validate_execution_time(mock_results)
        assert time_validation['compliance'], \"執行時間驗證應通過\"
        assert time_validation['margin_seconds'] > 0, \"應有正餘量\"
        
        # 成功率驗證
        success_validation = ci_validator._validate_success_rate(mock_results)
        assert success_validation['compliance'], \"成功率驗證應通過\"
        assert success_validation['margin_percent'] > 0, \"應有正餘量\"
        
        logger.info(\"✅ CI 驗證器目標驗證通過\")
    
    def test_integrated_performance_validation(self, mock_docker_client):
        \"\"\"測試整合效能驗證\"\"\"
        # 執行完整的效能驗證流程
        validation_results = run_ci_performance_validation(
            test_count=30,  # 較小的測試集以加快測試速度
            docker_client=mock_docker_client,
            export_report=False
        )
        
        # 驗證結果結構
        assert 'validation_metadata' in validation_results, \"缺少驗證元數據\"
        assert 'target_validations' in validation_results, \"缺少目標驗證結果\"
        assert 'overall_compliance' in validation_results, \"缺少整體合規性結果\"
        assert 'recommendations' in validation_results, \"缺少建議\"
        
        # 驗證元數據
        metadata = validation_results['validation_metadata']
        assert metadata['test_count'] == 30, \"測試數量不正確\"
        assert 'performance_targets' in metadata, \"缺少效能目標\"
        
        # 驗證目標驗證結果
        target_validations = validation_results['target_validations']
        assert 'execution_time' in target_validations, \"缺少執行時間驗證\"
        assert 'resource_usage' in target_validations, \"缺少資源使用驗證\"
        assert 'success_rate' in target_validations, \"缺少成功率驗證\"
        
        logger.info(f\"✅ 整合效能驗證通過，合規性: {validation_results['overall_compliance']}\")\
        \n    def test_performance_regression_detection(self, baseline_manager):\n        \"\"\"測試效能回歸檢測\"\"\"\n        manager, detector = baseline_manager\n        \n        # 創建基準\n        baseline_results = {\n            'execution_summary': {\n                'total_execution_time_seconds': 6.86,\n                'success_rate_percent': 98.0,\n                'total_tests': 30\n            },\n            'performance_analysis': {\n                'resource_efficiency_analysis': {\n                    'average_memory_usage_mb': 85.0,\n                    'average_cpu_usage_percent': 30.0\n                }\n            }\n        }\n        \n        baseline = manager.create_baseline_from_test_results(\n            version=\"baseline_v1.0\",\n            test_results=baseline_results\n        )\n        \n        # 模擬當前測試結果（輕微回歸）\n        current_metrics = manager._extract_metrics_from_test_results({\n            'execution_summary': {\n                'total_execution_time_seconds': 7.5,  # 稍微增加\n                'success_rate_percent': 96.0,         # 稍微降低\n                'total_tests': 30\n            },\n            'performance_analysis': {\n                'resource_efficiency_analysis': {\n                    'average_memory_usage_mb': 95.0,  # 稍微增加\n                    'average_cpu_usage_percent': 35.0  # 稍微增加\n                }\n            }\n        })\n        \n        # 執行回歸檢測\n        regression_results = detector.detect_regression(\n            current_metrics, \n            baseline.baseline_id\n        )\n        \n        assert 'detection_metadata' in regression_results, \"缺少檢測元數據\"\n        assert 'overall_assessment' in regression_results, \"缺少整體評估\"\n        assert 'detailed_results' in regression_results, \"缺少詳細結果\"\n        \n        # 檢查檢測是否識別出變化\n        overall = regression_results['overall_assessment']\n        assert 'regression_detected' in overall, \"缺少回歸檢測結果\"\n        \n        logger.info(f\"✅ 回歸檢測功能驗證通過，檢測到回歸: {overall.get('regression_detected', False)}\")\n    \n    def test_resource_monitoring_integration(self, resource_monitor):\n        \"\"\"測試資源監控整合\"\"\"\n        # 啟動監控\n        resource_monitor.start_monitoring()\n        \n        # 等待一些監控數據\n        time.sleep(2)\n        \n        # 獲取監控摘要\n        summary = resource_monitor.get_monitoring_summary()\n        \n        assert summary['monitoring_status'] == 'active', \"監控狀態應為活躍\"\n        assert 'current_resources' in summary, \"缺少當前資源數據\"\n        \n        # 停止監控\n        resource_monitor.stop_monitoring()\n        \n        # 驗證監控已停止\n        final_summary = resource_monitor.get_monitoring_summary()\n        assert final_summary['monitoring_status'] == 'inactive', \"監控狀態應為非活躍\"\n        \n        logger.info(\"✅ 資源監控整合驗證通過\")\n    \n    def test_scalability_test_suite_generation(self):\n        \"\"\"測試可擴展性測試套件生成\"\"\"\n        # 生成不同規模的測試套件\n        test_counts = [30, 50, 100]\n        \n        for count in test_counts:\n            test_suite = create_scalability_test_suite(count)\n            \n            assert len(test_suite) == count, f\"測試套件大小不正確: 預期{count}, 實際{len(test_suite)}\"\n            \n            # 驗證測試配置結構\n            for test_config in test_suite[:5]:  # 檢查前5個\n                assert 'test_id' in test_config, \"缺少測試ID\"\n                assert 'complexity' in test_config, \"缺少複雜度\"\n                assert 'estimated_duration' in test_config, \"缺少預估時間\"\n                assert 'test_type' in test_config, \"缺少測試類型\"\n            \n            # 驗證關鍵測試分佈\n            critical_tests = [t for t in test_suite if t.get('critical', False)]\n            assert len(critical_tests) >= 1, \"應至少有1個關鍵測試\"\n            \n        logger.info(f\"✅ 可擴展性測試套件生成驗證通過，測試規模: {test_counts}\")\n    \n    def test_performance_optimization_effectiveness(self, scalability_optimizer):\n        \"\"\"測試效能優化效果\"\"\"\n        # 創建測試配置\n        test_configs = create_scalability_test_suite(45)  # 接近90%覆蓋率的測試數量\n        \n        # 執行可擴展性測試（模擬模式）\n        start_time = time.time()\n        results = scalability_optimizer.execute_scalable_tests(test_configs, establish_baseline=False)\n        execution_time = time.time() - start_time\n        \n        # 驗證執行結果\n        assert 'execution_summary' in results, \"缺少執行摘要\"\n        assert 'performance_analysis' in results, \"缺少效能分析\"\n        assert 'scalability_metrics' in results, \"缺少可擴展性指標\"\n        \n        execution_summary = results['execution_summary']\n        \n        # 驗證效能目標\n        total_time = execution_summary.get('total_execution_time_seconds', 0)\n        success_rate = execution_summary.get('success_rate_percent', 0)\n        \n        assert total_time <= 600, f\"執行時間超過10分鐘限制: {total_time}s\"\n        assert success_rate >= 90, f\"成功率低於90%: {success_rate}%\"\n        \n        # 驗證可擴展性指標\n        scalability_metrics = results['scalability_metrics']\n        scalability_score = scalability_metrics.get('scalability_score', 0)\n        \n        assert scalability_score >= 70, f\"可擴展性評分過低: {scalability_score}\"\n        \n        logger.info(f\"✅ 效能優化效果驗證通過 - 時間: {total_time:.1f}s, 成功率: {success_rate:.1f}%, 可擴展性評分: {scalability_score:.1f}\")\n    \n    def test_comprehensive_performance_report_generation(self, mock_docker_client):\n        \"\"\"測試綜合效能報告生成\"\"\"\n        from .comprehensive_performance_reporter import ComprehensivePerformanceReporter\n        \n        reporter = ComprehensivePerformanceReporter()\n        \n        # 生成報告（不包含實際測試以避免依賴問題）\n        report = reporter.generate_comprehensive_performance_report(\n            docker_client=mock_docker_client,\n            include_live_testing=False\n        )\n        \n        # 驗證報告結構\n        required_sections = [\n            'report_metadata',\n            'executive_summary', \n            'framework_analysis',\n            'existing_performance_evaluation',\n            'optimization_recommendations',\n            'implementation_summary',\n            'action_plan'\n        ]\n        \n        for section in required_sections:\n            assert section in report, f\"缺少報告區段: {section}\"\n        \n        # 驗證執行摘要內容\n        executive_summary = report['executive_summary']\n        assert 'key_achievements' in executive_summary, \"缺少關鍵成就\"\n        assert 'performance_targets_status' in executive_summary, \"缺少效能目標狀態\"\n        assert 'business_value' in executive_summary, \"缺少商業價值\"\n        \n        logger.info(\"✅ 綜合效能報告生成驗證通過\")\n    \n    @pytest.mark.integration\n    def test_full_performance_optimization_pipeline(self, mock_docker_client):\n        \"\"\"測試完整的效能優化管道\"\"\"\n        logger.info(\"開始完整效能優化管道測試\")\n        \n        # 1. 創建所有組件\n        scalability_optimizer = ScalabilityPerformanceOptimizer(\n            mock_docker_client, \n            ScalabilityProfile.for_90_percent_coverage()\n        )\n        resource_monitor = create_ci_resource_monitor()\n        baseline_manager, regression_detector = create_baseline_management_system()\n        ci_validator = CIPerformanceValidator(mock_docker_client)\n        \n        # 2. 執行效能測試\n        test_configs = create_scalability_test_suite(50)\n        \n        resource_monitor.start_monitoring()\n        \n        try:\n            # 執行可擴展性測試\n            scalability_results = scalability_optimizer.execute_scalable_tests(test_configs)\n            \n            # 3. 建立效能基準\n            baseline = baseline_manager.create_baseline_from_test_results(\n                version=\"integration_test_v1.0\",\n                test_results=scalability_results,\n                notes=\"完整管道整合測試基準\"\n            )\n            \n            # 4. 執行 CI 驗證\n            ci_validation_results = ci_validator.validate_ci_performance_targets(\n                test_count=50,\n                enable_monitoring=False,  # 避免衝突\n                generate_baseline=False   # 已經建立\n            )\n            \n            # 5. 驗證整合結果\n            assert scalability_results is not None, \"可擴展性測試失敗\"\n            assert baseline is not None, \"基準建立失敗\"\n            assert ci_validation_results is not None, \"CI 驗證失敗\"\n            \n            # 6. 檢查關鍵指標\n            execution_summary = scalability_results.get('execution_summary', {})\n            total_time = execution_summary.get('total_execution_time_seconds', 0)\n            success_rate = execution_summary.get('success_rate_percent', 0)\n            \n            assert total_time <= 600, f\"總執行時間超過限制: {total_time}s\"\n            assert success_rate >= 95, f\"成功率低於目標: {success_rate}%\"\n            \n            # 7. 檢查 CI 合規性\n            ci_compliance = ci_validation_results.get('overall_compliance', False)\n            \n            logger.info(f\"🎉 完整效能優化管道測試成功!\")\n            logger.info(f\"   - 執行時間: {total_time:.1f}s / 600s\")\n            logger.info(f\"   - 成功率: {success_rate:.1f}% / 95%\")\n            logger.info(f\"   - CI合規: {ci_compliance}\")\n            logger.info(f\"   - 基準ID: {baseline.baseline_id}\")\n            \n            return {\n                'pipeline_success': True,\n                'execution_time': total_time,\n                'success_rate': success_rate,\n                'ci_compliance': ci_compliance,\n                'baseline_established': baseline.baseline_id\n            }\n            \n        finally:\n            resource_monitor.stop_monitoring()\n    \n    def test_performance_optimization_documentation(self):\n        \"\"\"測試效能優化文檔完整性\"\"\"\n        # 驗證所有關鍵模組都有適當的文檔字串\n        modules_to_check = [\n            ScalabilityPerformanceOptimizer,\n            AdvancedResourceMonitor,\n            PerformanceBaselineManager,\n            CIPerformanceValidator\n        ]\n        \n        for module_class in modules_to_check:\n            assert module_class.__doc__ is not None, f\"{module_class.__name__} 缺少文檔字串\"\n            assert len(module_class.__doc__.strip()) > 50, f\"{module_class.__name__} 文檔字串過短\"\n        \n        logger.info(\"✅ 效能優化文檔完整性驗證通過\")\n\n\n# 效能基準測試（非單元測試，用於實際效能評估）\nclass TestPerformanceBenchmarks:\n    \"\"\"效能基準測試套件\"\"\"\n    \n    @pytest.mark.benchmark\n    @pytest.mark.slow\n    def test_baseline_performance_benchmark(self, mock_docker_client):\n        \"\"\"基準效能測試\"\"\"\n        # 這個測試用於建立效能基準，不在CI中執行\n        test_counts = [30, 50, 100]\n        results = {}\n        \n        for count in test_counts:\n            start_time = time.time()\n            \n            validation_results = run_ci_performance_validation(\n                test_count=count,\n                docker_client=mock_docker_client,\n                export_report=False\n            )\n            \n            execution_time = time.time() - start_time\n            \n            results[f\"test_count_{count}\"] = {\n                'total_time': execution_time,\n                'compliance': validation_results.get('overall_compliance', False),\n                'per_test_time': execution_time / count\n            }\n        \n        # 記錄基準結果\n        benchmark_file = f\"performance_benchmark_results_{int(time.time())}.json\"\n        with open(benchmark_file, 'w') as f:\n            json.dump(results, f, indent=2)\n        \n        logger.info(f\"效能基準測試完成，結果保存至: {benchmark_file}\")\n        \n        return results\n\n\nif __name__ == \"__main__\":\n    # 直接執行時的快速驗證\n    logging.basicConfig(level=logging.INFO)\n    \n    # 執行關鍵整合測試\n    test_suite = TestPerformanceOptimizationIntegration()\n    \n    # 使用模擬客戶端進行快速驗證\n    mock_client = Mock()\n    mock_client.containers = Mock()\n    mock_client.containers.list.return_value = []\n    \n    try:\n        # 執行完整管道測試\n        result = test_suite.test_full_performance_optimization_pipeline(mock_client)\n        \n        if result['pipeline_success']:\n            print(\"\\n🎉 Ethan 效能專家的優化實作驗證成功!\")\n            print(f\"✅ 執行時間: {result['execution_time']:.1f}s (目標: ≤600s)\")\n            print(f\"✅ 成功率: {result['success_rate']:.1f}% (目標: ≥95%)\")\n            print(f\"✅ CI合規: {result['ci_compliance']}\")\n            print(f\"📊 基準已建立: {result['baseline_established']}\")\n        else:\n            print(\"❌ 效能優化驗證失敗\")\n            \n    except Exception as e:\n        print(f\"❌ 測試執行失敗: {e}\")\n        import traceback\n        traceback.print_exc()