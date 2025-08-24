"""
跨平台測試模組單元測試
Task ID: T1 - Docker 測試框架建立 (測試策略部分)

針對跨平台測試功能的單元測試，包括：
- CrossPlatformTester 類別功能測試  
- 平台配置測試
- 測試結果收集和報告生成測試
- CI/CD 整合功能測試
"""

import pytest
import json
import platform
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any, List

# 測試目標模組
from .test_cross_platform import (
    CrossPlatformTester, 
    SupportedPlatform,
    PlatformConfig, 
    TestResult as CrossPlatformTestResult
)
from .ci_integration import (
    CoverageReporter,
    TestFailureNotifier,
    CIIntegration
)
from .comprehensive_test_reporter import (
    CoverageMetrics,
    TestStatus,
    TestFailure
)
from .conftest import DockerTestFixture, DockerTestLogger


@pytest.mark.unit
class TestSupportedPlatform:
    """SupportedPlatform 枚舉測試"""
    
    def test_platform_values(self):
        """測試平台值定義"""
        assert SupportedPlatform.WINDOWS.value == "windows"
        assert SupportedPlatform.LINUX.value == "linux"
        assert SupportedPlatform.MACOS.value == "darwin"
    
    def test_get_current_platform(self):
        """測試取得當前平台"""
        with patch('platform.system') as mock_system:
            # 測試 Windows
            mock_system.return_value = "Windows"
            assert SupportedPlatform.get_current_platform() == SupportedPlatform.WINDOWS
            
            # 測試 Linux
            mock_system.return_value = "Linux"
            assert SupportedPlatform.get_current_platform() == SupportedPlatform.LINUX
            
            # 測試 macOS
            mock_system.return_value = "Darwin"
            assert SupportedPlatform.get_current_platform() == SupportedPlatform.MACOS
    
    def test_get_current_platform_unsupported(self):
        """測試不支援的平台"""
        with patch('platform.system') as mock_system:
            mock_system.return_value = "FreeBSD"
            with pytest.raises(ValueError, match="不支援的平台"):
                SupportedPlatform.get_current_platform()


@pytest.mark.unit
class TestTestResult:
    """TestResult 資料類別測試"""
    
    def test_test_result_creation(self):
        """測試測試結果創建"""
        result = CrossPlatformTestResult(
            test_name="test_example",
            platform="linux",
            success=True,
            duration_seconds=1.5,
            error_message="test error"
        )
        
        assert result.test_name == "test_example"
        assert result.platform == "linux"
        assert result.success is True
        assert result.duration_seconds == 1.5
        assert result.error_message == "test error"
        assert result.timestamp  # 應該自動設置時間戳
    
    def test_test_result_timestamp_auto_set(self):
        """測試時間戳自動設置"""
        result = CrossPlatformTestResult(
            test_name="test_example",
            platform="linux", 
            success=True,
            duration_seconds=1.0
        )
        
        assert result.timestamp
        # 驗證時間戳格式 (ISO8601)
        from datetime import datetime
        parsed_time = datetime.fromisoformat(result.timestamp)
        assert parsed_time


@pytest.mark.unit
class TestPlatformConfig:
    """PlatformConfig 資料類別測試"""
    
    def test_windows_config_post_init(self):
        """測試 Windows 配置後初始化"""
        config = PlatformConfig(platform=SupportedPlatform.WINDOWS)
        
        assert config.platform == SupportedPlatform.WINDOWS
        assert config.shell_command == ['cmd', '/c']
        assert config.path_separator == "\\"
        assert config.line_ending == "\r\n"
        assert isinstance(config.environment_vars, dict)
    
    def test_unix_config_post_init(self):
        """測試 Unix-like 配置後初始化"""
        config = PlatformConfig(platform=SupportedPlatform.LINUX)
        
        assert config.platform == SupportedPlatform.LINUX
        assert config.shell_command == ['sh', '-c']
        assert config.path_separator == "/"
        assert config.line_ending == "\n"
        assert isinstance(config.environment_vars, dict)


@pytest.mark.unit
class TestCrossPlatformTester:
    """CrossPlatformTester 類別測試"""
    
    @pytest.fixture
    def mock_docker_fixture(self):
        """模擬 Docker 測試夾具"""
        fixture = Mock(spec=DockerTestFixture)
        fixture.client = Mock()
        return fixture
    
    @pytest.fixture
    def mock_logger(self):
        """模擬測試日誌記錄器"""
        return Mock(spec=DockerTestLogger)
    
    @pytest.fixture
    def cross_platform_tester(self, mock_docker_fixture, mock_logger):
        """CrossPlatformTester 實例"""
        with patch('tests.docker.test_cross_platform.DOCKER_AVAILABLE', True):
            return CrossPlatformTester(mock_docker_fixture, mock_logger)
    
    def test_initialization(self, cross_platform_tester):
        """測試初始化"""
        assert cross_platform_tester.docker_fixture
        assert cross_platform_tester.logger
        assert cross_platform_tester.current_platform in SupportedPlatform
        assert len(cross_platform_tester.platform_configs) == 3
        assert cross_platform_tester.test_results == []
    
    def test_supports_windows_containers(self, cross_platform_tester):
        """測試 Windows 容器支援檢查"""
        # 模擬支援 Windows 容器
        cross_platform_tester.docker_fixture.client.info.return_value = {
            'OSType': 'windows'
        }
        assert cross_platform_tester._supports_windows_containers() is True
        
        # 模擬不支援 Windows 容器
        cross_platform_tester.docker_fixture.client.info.return_value = {
            'OSType': 'linux'
        }
        assert cross_platform_tester._supports_windows_containers() is False
    
    def test_get_testable_platforms(self, cross_platform_tester):
        """測試取得可測試平台列表"""
        with patch.object(cross_platform_tester, 'current_platform', SupportedPlatform.LINUX):
            platforms = cross_platform_tester._get_testable_platforms()
            assert SupportedPlatform.LINUX in platforms
            assert SupportedPlatform.MACOS in platforms  # Linux 可以測試 macOS 配置
        
        with patch.object(cross_platform_tester, 'current_platform', SupportedPlatform.WINDOWS):
            platforms = cross_platform_tester._get_testable_platforms()
            assert platforms == [SupportedPlatform.WINDOWS]
    
    def test_prepare_container_config(self, cross_platform_tester):
        """測試準備容器配置"""
        config = PlatformConfig(platform=SupportedPlatform.LINUX)
        image_name = "test-image"
        
        container_config = cross_platform_tester._prepare_container_config(config, image_name)
        
        assert container_config['image'] == image_name
        assert 'ENVIRONMENT' in container_config['environment']
        assert 'PLATFORM_TEST' in container_config['environment']
        assert container_config['environment']['PLATFORM_TEST'] == 'true'
        assert container_config['memory_limit'] == '512m'
        assert container_config['cpu_limit'] == '0.5'
    
    def test_get_platform_test_commands_linux(self, cross_platform_tester):
        """測試 Linux 平台測試命令生成"""
        config = PlatformConfig(platform=SupportedPlatform.LINUX)
        commands = cross_platform_tester._get_platform_test_commands(config)
        
        assert 'platform.system()' in commands
        assert 'platform.machine()' in commands
        assert 'Unix-like compatibility test passed' in commands
    
    def test_get_platform_test_commands_windows(self, cross_platform_tester):
        """測試 Windows 平台測試命令生成"""
        config = PlatformConfig(platform=SupportedPlatform.WINDOWS)
        commands = cross_platform_tester._get_platform_test_commands(config)
        
        assert 'platform.system()' in commands
        assert 'platform.machine()' in commands
        assert 'Windows compatibility test passed' in commands
    
    def test_verify_platform_test_result_success(self, cross_platform_tester):
        """測試平台測試結果驗證 - 成功情況"""
        # 模擬成功的容器
        mock_container = Mock()
        mock_container.attrs = {'State': {'ExitCode': 0}}
        
        # 模擬日誌包含所需內容
        with patch('tests.docker.test_cross_platform.get_container_logs') as mock_get_logs:
            mock_get_logs.return_value = """
            Platform: Linux
            Architecture: x86_64
            Python version: 3.9.0
            Environment PLATFORM: linux
            Unix-like compatibility test passed
            """
            
            config = PlatformConfig(platform=SupportedPlatform.LINUX)
            result = cross_platform_tester._verify_platform_test_result(mock_container, config)
            
            assert result is True
    
    def test_verify_platform_test_result_failure(self, cross_platform_tester):
        """測試平台測試結果驗證 - 失敗情況"""
        # 模擬失敗的容器
        mock_container = Mock()
        mock_container.attrs = {'State': {'ExitCode': 1}}
        
        config = PlatformConfig(platform=SupportedPlatform.LINUX)
        result = cross_platform_tester._verify_platform_test_result(mock_container, config)
        
        assert result is False
    
    def test_generate_platform_report(self, cross_platform_tester):
        """測試平台報告生成"""
        # 添加一些測試結果
        test_results = [
            CrossPlatformTestResult("test1", "linux", True, 1.0),
            CrossPlatformTestResult("test2", "linux", False, 2.0, error_message="test error")
        ]
        
        report_json = cross_platform_tester.generate_platform_report(test_results)
        
        # 驗證報告格式
        assert report_json
        report = json.loads(report_json)
        
        # 驗證報告結構
        assert 'report_metadata' in report
        assert 'test_summary' in report
        assert 'platform_results' in report
        assert 'recommendations' in report
        assert 'quality_gates' in report
        
        # 驗證測試摘要
        summary = report['test_summary']
        assert summary['total_tests'] == 2
        assert summary['passed_tests'] == 1
        assert summary['failed_tests'] == 1
        assert summary['success_rate_percent'] == 50.0
    
    def test_generate_recommendations(self, cross_platform_tester):
        """測試建議生成"""
        # 測試有失敗結果的情況
        failed_results = [
            CrossPlatformTestResult("test1", "linux", False, 1.0, error_message="error")
        ]
        
        recommendations = cross_platform_tester._generate_recommendations(failed_results)
        
        assert len(recommendations) > 0
        assert any("失敗" in rec for rec in recommendations)
        
        # 測試執行時間過長的情況
        slow_results = [
            CrossPlatformTestResult("test1", "linux", True, 65.0)  # 超過 60 秒
        ]
        
        recommendations = cross_platform_tester._generate_recommendations(slow_results)
        
        assert any("執行時間" in rec for rec in recommendations)
    
    def test_evaluate_quality_gates(self, cross_platform_tester):
        """測試品質門檻評估"""
        # 測試高成功率情況
        good_results = [
            CrossPlatformTestResult("test1", "linux", True, 30.0),
            CrossPlatformTestResult("test2", "linux", True, 40.0)
        ]
        
        gates = cross_platform_tester._evaluate_quality_gates(good_results)
        
        assert gates['success_rate']['value'] == 100.0
        assert gates['success_rate']['passed'] is True
        assert gates['max_execution_time']['passed'] is True
        assert gates['overall_passed'] is True
        
        # 測試低成功率情況
        bad_results = [
            CrossPlatformTestResult("test1", "linux", True, 30.0),
            CrossPlatformTestResult("test2", "linux", False, 40.0)
        ]
        
        gates = cross_platform_tester._evaluate_quality_gates(bad_results)
        
        assert gates['success_rate']['value'] == 50.0
        assert gates['success_rate']['passed'] is False
        assert gates['overall_passed'] is False


@pytest.mark.unit  
class TestCoverageMetrics:
    """CoverageMetrics 資料類別測試"""
    
    def test_coverage_metrics_creation(self):
        """測試覆蓋率指標創建"""
        metrics = CoverageMetrics(
            line_coverage=85.5,
            branch_coverage=78.2,
            function_coverage=92.1,
            statement_coverage=87.3,
            total_lines=1000,
            covered_lines=855,
            total_branches=200,
            covered_branches=156,
            total_functions=50,
            covered_functions=46
        )
        
        assert metrics.line_coverage == 85.5
        assert metrics.branch_coverage == 78.2
        assert metrics.total_lines == 1000
        assert metrics.covered_lines == 855
        assert metrics.timestamp  # 自動設置
    
    def test_overall_coverage_calculation(self):
        """測試整體覆蓋率計算"""
        metrics = CoverageMetrics(
            line_coverage=80.0,     # 權重 0.4
            branch_coverage=70.0,   # 權重 0.3
            function_coverage=90.0, # 權重 0.2
            statement_coverage=85.0, # 權重 0.1
            total_lines=100,
            covered_lines=80,
            total_branches=50,
            covered_branches=35,
            total_functions=10,
            covered_functions=9
        )
        
        expected = 80.0 * 0.4 + 70.0 * 0.3 + 90.0 * 0.2 + 85.0 * 0.1
        assert metrics.overall_coverage == expected


@pytest.mark.unit
class TestCoverageReporter:
    """CoverageReporter 類別測試"""
    
    @pytest.fixture
    def temp_project_root(self):
        """創建臨時專案根目錄"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            yield project_root
    
    @pytest.fixture
    def coverage_reporter(self, temp_project_root):
        """CoverageReporter 實例"""
        return CoverageReporter(temp_project_root)
    
    def test_initialization(self, coverage_reporter, temp_project_root):
        """測試初始化"""
        assert coverage_reporter.project_root == temp_project_root
        assert coverage_reporter.reports_dir.exists()
        assert coverage_reporter.reports_dir.name == "test-reports"
    
    def test_prepare_coverage_command_default(self, coverage_reporter):
        """測試準備覆蓋率命令 - 預設情況"""
        cmd = coverage_reporter._prepare_coverage_command()
        
        assert "python" in cmd
        assert "-m" in cmd
        assert "pytest" in cmd
        assert "--cov=src" in cmd
        assert "--cov=tests/docker" in cmd
        assert "--cov-report=xml" in cmd
        assert "--cov-report=json" in cmd
        assert "tests/docker/" in cmd
    
    def test_prepare_coverage_command_with_paths(self, coverage_reporter):
        """測試準備覆蓋率命令 - 指定路徑"""
        test_paths = ["tests/unit/", "tests/integration/"]
        cmd = coverage_reporter._prepare_coverage_command(test_paths)
        
        assert "tests/unit/" in cmd
        assert "tests/integration/" in cmd
    
    def test_parse_coverage_data_no_reports(self, coverage_reporter):
        """測試解析覆蓋率數據 - 無報告檔案"""
        metrics = coverage_reporter._parse_coverage_data()
        
        # 應該返回預設值
        assert metrics.line_coverage == 0.0
        assert metrics.branch_coverage == 0.0
        assert metrics.total_lines == 0
        assert metrics.covered_lines == 0
    
    def test_parse_json_coverage(self, coverage_reporter, temp_project_root):
        """測試從 JSON 解析覆蓋率"""
        # 創建模擬 JSON 覆蓋率報告
        json_data = {
            "totals": {
                "percent_covered": 85.5,
                "percent_covered_branches": 78.2,
                "percent_covered_functions": 92.1,
                "num_statements": 1000,
                "covered_lines": 855,
                "num_branches": 200,
                "covered_branches": 156,
                "num_functions": 50,
                "covered_functions": 46
            }
        }
        
        json_path = coverage_reporter.reports_dir / "coverage.json"
        with open(json_path, 'w') as f:
            json.dump(json_data, f)
        
        metrics = coverage_reporter._parse_json_coverage(json_path)
        
        assert metrics.line_coverage == 85.5
        assert metrics.branch_coverage == 78.2
        assert metrics.function_coverage == 92.1
        assert metrics.total_lines == 1000
        assert metrics.covered_lines == 855
    
    def test_generate_json_report(self, coverage_reporter):
        """測試生成 JSON 報告"""
        metrics = CoverageMetrics(
            line_coverage=85.5,
            branch_coverage=78.2,
            function_coverage=92.1,
            statement_coverage=87.3,
            total_lines=1000,
            covered_lines=855,
            total_branches=200,
            covered_branches=156,
            total_functions=50,
            covered_functions=46
        )
        
        report = coverage_reporter._generate_json_report(metrics)
        
        assert report
        data = json.loads(report)
        
        assert 'report_metadata' in data
        assert 'coverage_summary' in data  
        assert 'coverage_details' in data
        assert 'quality_gates' in data
        
        assert data['coverage_summary']['line_coverage'] == 85.5
        assert data['quality_gates']['minimum_coverage'] == 90.0
    
    def test_generate_text_report(self, coverage_reporter):
        """測試生成文字報告"""
        metrics = CoverageMetrics(
            line_coverage=85.5,
            branch_coverage=78.2,
            function_coverage=92.1,
            statement_coverage=87.3,
            total_lines=1000,
            covered_lines=855,
            total_branches=200,
            covered_branches=156,
            total_functions=50,
            covered_functions=46
        )
        
        report = coverage_reporter._generate_text_report(metrics)
        
        assert "測試覆蓋率報告" in report
        assert "85.50%" in report
        assert "1000" in report
        assert "任務 ID: T1" in report
    
    def test_is_ci_environment(self, coverage_reporter):
        """測試 CI 環境檢查"""
        # 測試非 CI 環境
        with patch.dict(os.environ, {}, clear=True):
            assert coverage_reporter._is_ci_environment() is False
        
        # 測試 CI 環境
        with patch.dict(os.environ, {'CI': 'true'}):
            assert coverage_reporter._is_ci_environment() is True
        
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}):
            assert coverage_reporter._is_ci_environment() is True


@pytest.mark.unit
class TestTestFailureNotifier:
    """TestFailureNotifier 類別測試"""
    
    @pytest.fixture
    def notifier(self):
        """TestFailureNotifier 實例"""
        return TestFailureNotifier()
    
    def test_initialization(self, notifier):
        """測試初始化"""
        assert notifier.notifications == []
    
    def test_analyze_test_failures_all_passed(self, notifier):
        """測試分析測試失敗 - 全部通過"""
        test_results = [
            CITestResult("test1", "passed", 1.0),
            CITestResult("test2", "passed", 1.5),
            CITestResult("test3", "passed", 2.0)
        ]
        
        notifications = notifier.analyze_test_failures(test_results)
        
        assert len(notifications) == 1
        assert notifications[0].level == NotificationLevel.INFO
        assert "所有測試通過" in notifications[0].title
        assert notifications[0].details['success_rate'] == 100.0
    
    def test_analyze_test_failures_with_failures(self, notifier):
        """測試分析測試失敗 - 有失敗測試"""
        test_results = [
            CITestResult("test1", "passed", 1.0),
            CITestResult("test2", "failed", 1.5, failure_message="assertion error"),
            CITestResult("test3", "error", 2.0, error_message="runtime error")
        ]
        
        notifications = notifier.analyze_test_failures(test_results)
        
        # 應該有失敗通知
        failure_notifications = [n for n in notifications if n.level == NotificationLevel.ERROR]
        assert len(failure_notifications) > 0
        
        failure_notification = failure_notifications[0]
        assert "測試失敗警報" in failure_notification.title
        assert failure_notification.details['failed_count'] == 2
        assert failure_notification.details['total_count'] == 3
        assert failure_notification.details['success_rate'] == 33.33  # 1/3 * 100
    
    def test_analyze_test_failures_with_skipped(self, notifier):
        """測試分析測試失敗 - 有跳過測試"""
        test_results = [
            CITestResult("test1", "passed", 1.0),
            CITestResult("test2", "skipped", 0.0),
            CITestResult("test3", "skipped", 0.0),
            CITestResult("test4", "skipped", 0.0)  # 3/4 = 75% 跳過，超過 10% 閾值
        ]
        
        notifications = notifier.analyze_test_failures(test_results)
        
        # 應該有跳過警告
        skip_notifications = [n for n in notifications if n.level == NotificationLevel.WARNING]
        assert len(skip_notifications) > 0
        
        skip_notification = skip_notifications[0]
        assert "測試跳過警告" in skip_notification.title
        assert skip_notification.details['skipped_count'] == 3
        assert skip_notification.details['skip_rate'] == 75.0
    
    def test_is_ci_environment(self, notifier):
        """測試 CI 環境檢查"""
        # 測試非 CI 環境
        with patch.dict(os.environ, {}, clear=True):
            assert notifier._is_ci_environment() is False
        
        # 測試 CI 環境
        with patch.dict(os.environ, {'CI': 'true'}):
            assert notifier._is_ci_environment() is True
    
    def test_log_notification(self, notifier, caplog):
        """測試日誌通知"""
        notification = NotificationMessage(
            level=NotificationLevel.ERROR,
            title="Test Error",
            message="This is a test error message"
        )
        
        notifier._log_notification(notification)
        
        assert "Test Error" in caplog.text
        assert "This is a test error message" in caplog.text


@pytest.mark.unit
class TestCIIntegration:
    """CIIntegration 類別測試"""
    
    @pytest.fixture
    def temp_project_root(self):
        """創建臨時專案根目錄"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            yield project_root
    
    @pytest.fixture
    def ci_integration(self, temp_project_root):
        """CIIntegration 實例"""
        return CIIntegration(temp_project_root)
    
    def test_initialization(self, ci_integration, temp_project_root):
        """測試初始化"""
        assert ci_integration.project_root == temp_project_root
        assert isinstance(ci_integration.coverage_reporter, CoverageReporter)
        assert isinstance(ci_integration.failure_notifier, TestFailureNotifier)
    
    def test_configure_test_stage(self, ci_integration):
        """測試配置測試階段"""
        config = {
            'environment': {
                'TEST_ENV': 'unittest',
                'DEBUG': 'true'
            }
        }
        
        ci_integration.configure_test_stage(config)
        
        # 驗證環境變數設置
        assert os.getenv('TEST_ENV') == 'unittest'
        assert os.getenv('DEBUG') == 'true'
        
        # 驗證目錄創建
        assert (ci_integration.project_root / "test-reports").exists()
    
    @patch('subprocess.run')
    def test_run_full_test_pipeline_success(self, mock_run, ci_integration):
        """測試執行完整測試管道 - 成功情況"""
        # 模擬 pytest 成功執行
        mock_run.return_value = Mock(returncode=0, stderr="", stdout="")
        
        # 模擬覆蓋率數據
        with patch.object(ci_integration.coverage_reporter, '_parse_coverage_data') as mock_parse:
            mock_parse.return_value = CoverageMetrics(
                line_coverage=95.0,
                branch_coverage=92.0,
                function_coverage=98.0,
                statement_coverage=94.0,
                total_lines=1000,
                covered_lines=950,
                total_branches=200,
                covered_branches=184,
                total_functions=50,
                covered_functions=49
            )
            
            # 模擬無測試結果檔案（全部通過）
            with patch.object(ci_integration.failure_notifier, 'collect_test_results') as mock_collect:
                mock_collect.return_value = []
                
                result = ci_integration.run_full_test_pipeline()
                
                assert result is True
    
    @patch('subprocess.run')
    def test_run_full_test_pipeline_failure(self, mock_run, ci_integration):
        """測試執行完整測試管道 - 失敗情況"""
        # 模擬 pytest 成功執行但覆蓋率不足
        mock_run.return_value = Mock(returncode=0, stderr="", stdout="")
        
        # 模擬低覆蓋率
        with patch.object(ci_integration.coverage_reporter, '_parse_coverage_data') as mock_parse:
            mock_parse.return_value = CoverageMetrics(
                line_coverage=70.0,  # 低於 90% 門檻
                branch_coverage=65.0,
                function_coverage=75.0,
                statement_coverage=68.0,
                total_lines=1000,
                covered_lines=700,
                total_branches=200,
                covered_branches=130,
                total_functions=50,
                covered_functions=37
            )
            
            with patch.object(ci_integration.failure_notifier, 'collect_test_results') as mock_collect:
                mock_collect.return_value = []
                
                result = ci_integration.run_full_test_pipeline()
                
                assert result is False


# === 整合測試標記 ===

@pytest.mark.integration
class TestCrossPlatformIntegration:
    """跨平台測試整合測試"""
    
    def test_full_cross_platform_workflow(self):
        """測試完整跨平台工作流程"""
        # 這個測試需要實際的 Docker 環境
        pytest.skip("需要實際 Docker 環境的整合測試")
    
    def test_ci_integration_workflow(self):
        """測試 CI 整合工作流程"""
        # 這個測試需要 CI 環境設置
        pytest.skip("需要實際 CI 環境的整合測試")


# === 夾具和配置 ===

@pytest.fixture
def mock_docker_available():
    """模擬 Docker 可用"""
    with patch('tests.docker.test_cross_platform.DOCKER_AVAILABLE', True):
        yield


@pytest.fixture  
def sample_test_results():
    """提供範例測試結果"""
    return [
        CrossPlatformTestResult("test_platform_linux", "linux", True, 15.5),
        CrossPlatformTestResult("test_platform_macos", "darwin", True, 18.2),
        CrossPlatformTestResult("test_platform_windows", "windows", False, 25.1, error_message="container failed")
    ]


@pytest.fixture
def sample_coverage_metrics():
    """提供範例覆蓋率指標"""
    return CoverageMetrics(
        line_coverage=87.3,
        branch_coverage=82.1,
        function_coverage=94.2,
        statement_coverage=89.5,
        total_lines=2500,
        covered_lines=2182,
        total_branches=450,
        covered_branches=369,
        total_functions=125,
        covered_functions=118
    )