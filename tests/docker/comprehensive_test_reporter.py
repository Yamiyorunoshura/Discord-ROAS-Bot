"""
強化測試覆蓋率報告系統
Task ID: T1 - Docker 測試框架建立 (測試品質提升專門化)

作為測試專家 Sophia 的專門領域實作：
- 詳細的測試覆蓋率分析和報告
- 測試品質指標監控
- 失敗測試的根因分析
- 自動化測試報告生成和上傳
"""

import json
import time
import logging
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """測試狀態枚舉"""
    PASSED = "passed"
    FAILED = "failed" 
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class CoverageMetrics:
    """測試覆蓋率指標"""
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    function_coverage: float = 0.0
    statement_coverage: float = 0.0
    total_lines: int = 0
    covered_lines: int = 0
    missing_lines: List[int] = field(default_factory=list)
    excluded_lines: List[int] = field(default_factory=list)
    
    def overall_coverage(self) -> float:
        """計算整體覆蓋率"""
        metrics = [
            self.line_coverage,
            self.branch_coverage, 
            self.function_coverage,
            self.statement_coverage
        ]
        valid_metrics = [m for m in metrics if m > 0]
        return sum(valid_metrics) / len(valid_metrics) if valid_metrics else 0.0


@dataclass
class TestFailure:
    """測試失敗資訊"""
    test_name: str
    failure_type: str
    failure_message: str
    stack_trace: str
    duration: float = 0.0
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class CoverageReporter:
    """測試覆蓋率報告器 - Sophia的品質監控專門實作"""
    
    def __init__(self, project_root: Path, test_paths: List[str] = None):
        self.project_root = Path(project_root)
        self.test_paths = test_paths or ["tests/docker/"]
        self.report_dir = self.project_root / "test-reports"
        self.report_dir.mkdir(exist_ok=True)
        
        # 確保覆蓋率工具可用
        self._ensure_coverage_tools()
    
    def _ensure_coverage_tools(self):
        """確保覆蓋率測試工具可用"""
        try:
            subprocess.run(["coverage", "--version"], 
                         check=True, capture_output=True, text=True)
            logger.info("覆蓋率工具 coverage 可用")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("覆蓋率工具 coverage 不可用，嘗試安裝...")
            try:
                subprocess.run(["pip", "install", "coverage[toml]", "pytest-cov"],
                             check=True, capture_output=True)
                logger.info("覆蓋率工具安裝完成")
            except subprocess.CalledProcessError as e:
                logger.error(f"無法安裝覆蓋率工具: {e}")
    
    def run_coverage_analysis(self, test_command: str = None) -> Dict[str, Any]:
        """執行覆蓋率分析
        
        Args:
            test_command: 自訂測試命令，預設使用 Docker 測試
            
        Returns:
            覆蓋率分析結果
        """
        if not test_command:
            test_command = self._prepare_coverage_command()
        
        logger.info(f"執行覆蓋率分析: {test_command}")
        start_time = time.time()
        
        try:
            # 清理舊的覆蓋率資料
            self._cleanup_coverage_data()
            
            # 執行覆蓋率測試
            result = subprocess.run(
                test_command.split(),
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=600  # 10 分鐘超時
            )
            
            execution_time = time.time() - start_time
            
            # 分析覆蓋率結果
            coverage_data = self._parse_coverage_data()
            
            # 生成報告
            report = {
                "execution_info": {
                    "command": test_command,
                    "execution_time_seconds": execution_time,
                    "return_code": result.returncode,
                    "timestamp": datetime.now().isoformat()
                },
                "coverage_metrics": coverage_data,
                "test_output": {
                    "stdout": result.stdout[-2000:] if result.stdout else "",  # 最後2000字符
                    "stderr": result.stderr[-2000:] if result.stderr else ""
                }
            }
            
            # 儲存報告
            self._save_coverage_report(report)
            
            logger.info(f"覆蓋率分析完成，耗時: {execution_time:.2f}s")
            return report
            
        except subprocess.TimeoutExpired:
            logger.error("覆蓋率分析超時")
            return {"error": "測試執行超時", "execution_time_seconds": time.time() - start_time}
        except Exception as e:
            logger.error(f"覆蓋率分析失敗: {str(e)}")
            return {"error": str(e), "execution_time_seconds": time.time() - start_time}
    
    def _prepare_coverage_command(self, target_paths: List[str] = None) -> str:
        """準備覆蓋率測試命令"""
        paths = target_paths or self.test_paths
        paths_str = " ".join(paths)
        
        # 構建完整的覆蓋率測試命令
        command_parts = [
            "coverage", "run",
            "--source=src/,tests/docker/",  # 指定源碼路徑
            "--omit=*/__pycache__/*,*/venv/*,*/tests/*",  # 排除特定路徑
            "--branch",  # 啟用分支覆蓋率
            "-m", "pytest",
            paths_str,
            "-v",
            "--tb=short",
            "--disable-warnings",
            "--maxfail=10"  # 最多允許10個失敗
        ]
        
        return " ".join(command_parts)
    
    def _cleanup_coverage_data(self):
        """清理舊的覆蓋率資料"""
        coverage_files = [
            ".coverage",
            ".coverage.*",
            "htmlcov/",
            "coverage.xml",
            "coverage.json"
        ]
        
        for pattern in coverage_files:
            try:
                if pattern.endswith("/"):
                    # 目錄
                    import shutil
                    path = self.project_root / pattern.rstrip("/")
                    if path.exists():
                        shutil.rmtree(path)
                else:
                    # 檔案
                    for file_path in self.project_root.glob(pattern):
                        file_path.unlink()
            except Exception as e:
                logger.debug(f"清理覆蓋率檔案時發生錯誤 {pattern}: {e}")
    
    def _parse_coverage_data(self) -> Dict[str, Any]:
        """解析覆蓋率資料"""
        coverage_data = {
            "overall_coverage": 0.0,
            "line_coverage": 0.0,
            "branch_coverage": 0.0,
            "reports_found": [],
            "detailed_coverage": {}
        }
        
        # 嘗試解析不同格式的覆蓋率報告
        try:
            # 生成 JSON 報告
            subprocess.run(
                ["coverage", "json", "-o", str(self.report_dir / "coverage.json")],
                cwd=str(self.project_root),
                capture_output=True,
                check=True
            )
            
            # 解析 JSON 報告
            json_coverage = self._parse_json_coverage()
            if json_coverage:
                coverage_data.update(json_coverage)
                coverage_data["reports_found"].append("json")
        except Exception as e:
            logger.debug(f"無法生成或解析 JSON 覆蓋率報告: {e}")
        
        try:
            # 生成 XML 報告
            subprocess.run(
                ["coverage", "xml", "-o", str(self.report_dir / "coverage.xml")],
                cwd=str(self.project_root),
                capture_output=True,
                check=True
            )
            coverage_data["reports_found"].append("xml")
        except Exception as e:
            logger.debug(f"無法生成 XML 覆蓋率報告: {e}")
        
        try:
            # 生成 HTML 報告
            subprocess.run(
                ["coverage", "html", "-d", str(self.report_dir / "htmlcov")],
                cwd=str(self.project_root),
                capture_output=True,
                check=True
            )
            coverage_data["reports_found"].append("html")
        except Exception as e:
            logger.debug(f"無法生成 HTML 覆蓋率報告: {e}")
        
        return coverage_data
    
    def _parse_json_coverage(self) -> Optional[Dict[str, Any]]:
        """解析 JSON 格式的覆蓋率報告"""
        json_file = self.report_dir / "coverage.json"
        if not json_file.exists():
            return None
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            totals = data.get("totals", {})
            
            return {
                "overall_coverage": totals.get("percent_covered", 0.0),
                "line_coverage": totals.get("percent_covered", 0.0),
                "covered_lines": totals.get("covered_lines", 0),
                "missing_lines": totals.get("missing_lines", 0),
                "total_lines": totals.get("num_statements", 0),
                "excluded_lines": totals.get("excluded_lines", 0),
                "detailed_coverage": {
                    filename: {
                        "coverage": file_data.get("summary", {}).get("percent_covered", 0.0),
                        "missing_lines": file_data.get("missing_lines", []),
                        "executed_lines": file_data.get("executed_lines", [])
                    }
                    for filename, file_data in data.get("files", {}).items()
                    if filename.startswith(("src/", "tests/docker/"))
                }
            }
        except Exception as e:
            logger.error(f"解析 JSON 覆蓋率報告失敗: {e}")
            return None
    
    def _save_coverage_report(self, report: Dict[str, Any]):
        """儲存覆蓋率報告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.report_dir / f"docker_coverage_report_{timestamp}.json"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"覆蓋率報告已儲存: {report_file}")
            
            # 同時儲存最新報告的副本
            latest_report = self.report_dir / "latest_docker_coverage_report.json"
            with open(latest_report, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"儲存覆蓋率報告失敗: {e}")
    
    def generate_summary_report(self) -> str:
        """生成覆蓋率摘要報告"""
        latest_report = self.report_dir / "latest_docker_coverage_report.json"
        
        if not latest_report.exists():
            return "沒有可用的覆蓋率報告"
        
        try:
            with open(latest_report, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            coverage_metrics = data.get("coverage_metrics", {})
            execution_info = data.get("execution_info", {})
            
            summary = f"""
Docker 測試框架覆蓋率報告
========================================

執行資訊:
- 執行時間: {execution_info.get('execution_time_seconds', 0):.2f} 秒
- 執行狀態: {'成功' if execution_info.get('return_code') == 0 else '失敗'}
- 報告時間: {execution_info.get('timestamp', 'unknown')}

覆蓋率指標:
- 整體覆蓋率: {coverage_metrics.get('overall_coverage', 0):.2f}%
- 行覆蓋率: {coverage_metrics.get('line_coverage', 0):.2f}%
- 總行數: {coverage_metrics.get('total_lines', 0)}
- 已覆蓋行數: {coverage_metrics.get('covered_lines', 0)}
- 未覆蓋行數: {coverage_metrics.get('missing_lines', 0)}

品質門檻檢查:
- 覆蓋率 ≥ 90%: {'✓ 通過' if coverage_metrics.get('overall_coverage', 0) >= 90 else '✗ 未達標'}
- 執行時間 ≤ 10分鐘: {'✓ 通過' if execution_info.get('execution_time_seconds', 0) <= 600 else '✗ 超時'}

生成的報告:
{', '.join(coverage_metrics.get('reports_found', []))}
"""
            return summary
            
        except Exception as e:
            logger.error(f"生成摘要報告失敗: {e}")
            return f"生成摘要報告失敗: {str(e)}"
    
    def is_ci_environment(self) -> bool:
        """檢測是否在CI環境中運行"""
        import os
        ci_indicators = [
            'CI', 'CONTINUOUS_INTEGRATION', 'GITHUB_ACTIONS', 
            'JENKINS_URL', 'GITLAB_CI', 'TRAVIS'
        ]
        return any(os.environ.get(indicator) for indicator in ci_indicators)


class TestFailureNotifier:
    """測試失敗通知器 - Sophia的品質守門員功能"""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.notification_log = self.project_root / "test-reports" / "failure_notifications.log"
        self.notification_log.parent.mkdir(exist_ok=True)
    
    def analyze_test_failures(self, test_result_xml: Path) -> List[TestFailure]:
        """分析測試失敗資訊"""
        failures = []
        
        if not test_result_xml.exists():
            return failures
        
        try:
            tree = ET.parse(test_result_xml)
            root = tree.getroot()
            
            for testcase in root.findall('.//testcase'):
                test_name = testcase.get('name', 'unknown')
                classname = testcase.get('classname', '')
                time_taken = float(testcase.get('time', 0))
                
                # 檢查失敗
                failure = testcase.find('failure')
                error = testcase.find('error')
                
                if failure is not None:
                    failures.append(TestFailure(
                        test_name=f"{classname}::{test_name}",
                        failure_type="failure",
                        failure_message=failure.get('message', ''),
                        stack_trace=failure.text or '',
                        duration=time_taken
                    ))
                elif error is not None:
                    failures.append(TestFailure(
                        test_name=f"{classname}::{test_name}",
                        failure_type="error", 
                        failure_message=error.get('message', ''),
                        stack_trace=error.text or '',
                        duration=time_taken
                    ))
        
        except Exception as e:
            logger.error(f"分析測試失敗資訊時發生錯誤: {e}")
        
        return failures
    
    def notify_failures(self, failures: List[TestFailure]) -> bool:
        """通知測試失敗"""
        if not failures:
            self._log_notification("所有測試通過，無需通知")
            return True
        
        notification_message = self._format_failure_notification(failures)
        
        try:
            # 記錄到檔案
            self._log_notification(notification_message)
            
            # 如果在CI環境，可以發送到外部系統
            if self._is_ci_environment():
                return self._send_ci_notification(notification_message)
            
            return True
            
        except Exception as e:
            logger.error(f"發送失敗通知時發生錯誤: {e}")
            return False
    
    def _format_failure_notification(self, failures: List[TestFailure]) -> str:
        """格式化失敗通知訊息"""
        timestamp = datetime.now().isoformat()
        
        message = f"""
Docker 測試失敗通知
==================
時間: {timestamp}
失敗測試數量: {len(failures)}

詳細失敗資訊:
"""
        
        for i, failure in enumerate(failures, 1):
            message += f"""
{i}. 測試: {failure.test_name}
   類型: {failure.failure_type}
   訊息: {failure.failure_message}
   耗時: {failure.duration:.3f}s
   錯誤詳情: {failure.stack_trace[:200]}...
   {'='*50}
"""
        
        return message
    
    def _log_notification(self, message: str):
        """記錄通知到日誌檔案"""
        try:
            with open(self.notification_log, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.now().isoformat()}] {message}\n")
                f.write("-" * 80 + "\n")
        except Exception as e:
            logger.error(f"記錄通知失敗: {e}")
    
    def _is_ci_environment(self) -> bool:
        """檢測CI環境"""
        import os
        return bool(os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'))
    
    def _send_ci_notification(self, message: str) -> bool:
        """在CI環境中發送通知"""
        # 這裡可以整合 GitHub Actions、Slack、Email等通知機制
        logger.info("CI環境檢測到測試失敗，通知已記錄到日誌")
        return True


# === 整合的CI整合類別 ===

class CIIntegration:
    """CI/CD整合管理器 - 整合Sophia的品質控制機制到CI管道"""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.coverage_reporter = CoverageReporter(project_root)
        self.failure_notifier = TestFailureNotifier(project_root)
    
    def configure_test_stage(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """配置CI測試階段"""
        default_config = {
            "coverage_threshold": 90.0,
            "max_execution_time": 600,  # 10分鐘
            "fail_on_coverage_drop": True,
            "generate_reports": True,
            "notify_on_failure": True
        }
        
        if config:
            default_config.update(config)
        
        return default_config
    
    def run_full_test_pipeline(self) -> Dict[str, Any]:
        """執行完整的測試管道"""
        pipeline_start = time.time()
        pipeline_results = {
            "start_time": datetime.now().isoformat(),
            "coverage_analysis": {},
            "test_failures": [],
            "pipeline_success": False,
            "execution_time_seconds": 0
        }
        
        try:
            # 1. 執行覆蓋率分析
            logger.info("開始Docker測試覆蓋率分析...")
            coverage_result = self.coverage_reporter.run_coverage_analysis()
            pipeline_results["coverage_analysis"] = coverage_result
            
            # 2. 分析測試失敗
            xml_report_path = self.project_root / "test-reports" / "pytest_results.xml"
            if xml_report_path.exists():
                failures = self.failure_notifier.analyze_test_failures(xml_report_path)
                pipeline_results["test_failures"] = [
                    {
                        "test_name": f.test_name,
                        "failure_type": f.failure_type,
                        "failure_message": f.failure_message,
                        "duration": f.duration
                    }
                    for f in failures
                ]
                
                # 3. 發送失敗通知
                if failures:
                    self.failure_notifier.notify_failures(failures)
            
            # 4. 評估管道成功狀態
            coverage_success = self._evaluate_coverage_success(coverage_result)
            test_success = len(pipeline_results["test_failures"]) == 0
            
            pipeline_results["pipeline_success"] = coverage_success and test_success
            
            logger.info(f"測試管道完成，成功: {pipeline_results['pipeline_success']}")
            
        except Exception as e:
            logger.error(f"測試管道執行失敗: {e}")
            pipeline_results["error"] = str(e)
        
        finally:
            pipeline_results["execution_time_seconds"] = time.time() - pipeline_start
            pipeline_results["end_time"] = datetime.now().isoformat()
        
        return pipeline_results
    
    def _evaluate_coverage_success(self, coverage_result: Dict[str, Any]) -> bool:
        """評估覆蓋率是否達標"""
        if "error" in coverage_result:
            return False
        
        coverage_metrics = coverage_result.get("coverage_metrics", {})
        overall_coverage = coverage_metrics.get("overall_coverage", 0.0)
        
        return overall_coverage >= 90.0  # 90%覆蓋率門檻
    
    def upload_coverage_report(self, report_path: str) -> bool:
        """上傳覆蓋率報告到外部系統"""
        # 這裡可以整合 Codecov、Coveralls等服務
        logger.info(f"覆蓋率報告上傳功能準備就緒: {report_path}")
        return True