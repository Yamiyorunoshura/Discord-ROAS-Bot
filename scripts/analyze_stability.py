#!/usr/bin/env python3
"""
穩定性分析器
Task ID: T5 - Discord testing: dpytest and random interactions

分析多次執行的測試結果，檢測flaky測試和穩定性問題。
"""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
import logging
from datetime import datetime
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class StabilityAnalyzer:
    """穩定性分析器"""
    
    def __init__(self, input_dir: Path, output_path: Path):
        self.input_dir = input_dir
        self.output_path = output_path
        
    def analyze(self) -> Dict[str, Any]:
        """執行穩定性分析"""
        
        # 收集所有穩定性測試結果檔案
        stability_files = self._find_stability_files()
        
        if not stability_files:
            logger.warning("No stability test files found")
            return {"status": "no_data", "analysis": {}}
        
        # 解析測試結果
        all_results = self._parse_stability_results(stability_files)
        
        # 執行分析
        analysis = self._perform_analysis(all_results)
        
        # 生成報告
        report = self._generate_report(analysis, stability_files)
        
        # 保存報告
        self._save_report(report)
        
        return report
    
    def _find_stability_files(self) -> List[Path]:
        """查找穩定性測試結果檔案"""
        files = []
        
        # 查找符合模式的檔案
        patterns = [
            "stability-run-*.xml",
            "stability_*.xml", 
            "*stability*.xml"
        ]
        
        for pattern in patterns:
            files.extend(self.input_dir.glob(pattern))
        
        # 排序以確保一致的處理順序
        return sorted(files)
    
    def _parse_stability_results(self, files: List[Path]) -> List[Dict[str, Any]]:
        """解析穩定性測試結果"""
        all_results = []
        
        for file_path in files:
            try:
                results = self._parse_single_result_file(file_path)
                results["source_file"] = str(file_path)
                all_results.append(results)
                
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                continue
        
        return all_results
    
    def _parse_single_result_file(self, file_path: Path) -> Dict[str, Any]:
        """解析單個結果檔案"""
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            results = {
                "run_info": {
                    "timestamp": root.get("timestamp", "unknown"),
                    "tests": int(root.get("tests", 0)),
                    "failures": int(root.get("failures", 0)),
                    "errors": int(root.get("errors", 0)),
                    "time": float(root.get("time", 0))
                },
                "testcases": []
            }
            
            # 解析測試案例
            for testcase in root.findall('.//testcase'):
                case_info = {
                    "name": testcase.get("name", "unknown"),
                    "classname": testcase.get("classname", "unknown"),
                    "time": float(testcase.get("time", 0)),
                    "status": "passed"  # 預設為通過
                }
                
                # 檢查失敗或錯誤
                if testcase.find("failure") is not None:
                    failure = testcase.find("failure")
                    case_info["status"] = "failed"
                    case_info["failure_type"] = failure.get("type", "unknown")
                    case_info["failure_message"] = failure.get("message", "")
                    
                elif testcase.find("error") is not None:
                    error = testcase.find("error")
                    case_info["status"] = "error"
                    case_info["error_type"] = error.get("type", "unknown")
                    case_info["error_message"] = error.get("message", "")
                
                elif testcase.find("skipped") is not None:
                    case_info["status"] = "skipped"
                    case_info["skip_reason"] = testcase.find("skipped").get("message", "")
                
                results["testcases"].append(case_info)
            
            return results
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error in {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error parsing {file_path}: {e}")
            raise
    
    def _perform_analysis(self, all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """執行詳細分析"""
        
        if not all_results:
            return {"status": "no_data"}
        
        # 收集所有測試的執行記錄
        test_records = defaultdict(list)  # test_key -> [run_records]
        
        for run_idx, result in enumerate(all_results):
            for testcase in result["testcases"]:
                test_key = f"{testcase['classname']}::{testcase['name']}"
                test_records[test_key].append({
                    "run": run_idx + 1,
                    "status": testcase["status"],
                    "time": testcase["time"],
                    "details": testcase.get("failure_message") or testcase.get("error_message", "")
                })
        
        # 分析每個測試的穩定性
        analysis = {
            "total_runs": len(all_results),
            "total_unique_tests": len(test_records),
            "test_analysis": {},
            "flaky_tests": [],
            "consistent_failures": [],
            "performance_issues": [],
            "summary": {}
        }
        
        # 分析每個測試
        for test_key, records in test_records.items():
            test_analysis = self._analyze_single_test(test_key, records)
            analysis["test_analysis"][test_key] = test_analysis
            
            # 分類問題測試
            if test_analysis["is_flaky"]:
                analysis["flaky_tests"].append({
                    "test": test_key,
                    "success_rate": test_analysis["success_rate"],
                    "failure_pattern": test_analysis["failure_pattern"]
                })
            
            if test_analysis["always_fails"]:
                analysis["consistent_failures"].append({
                    "test": test_key,
                    "failure_reason": test_analysis["common_failure_reason"]
                })
            
            if test_analysis["has_performance_issues"]:
                analysis["performance_issues"].append({
                    "test": test_key,
                    "avg_time": test_analysis["avg_execution_time"],
                    "max_time": test_analysis["max_execution_time"]
                })
        
        # 生成摘要
        analysis["summary"] = self._generate_summary(analysis)
        
        return analysis
    
    def _analyze_single_test(self, test_key: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析單個測試的穩定性"""
        
        total_runs = len(records)
        statuses = [r["status"] for r in records]
        times = [r["time"] for r in records]
        
        # 計算成功率
        success_count = statuses.count("passed")
        success_rate = success_count / total_runs if total_runs > 0 else 0
        
        # 判斷是否為flaky測試（有時成功，有時失敗）
        unique_statuses = set(statuses)
        is_flaky = len(unique_statuses) > 1 and "passed" in unique_statuses
        
        # 判斷是否總是失敗
        always_fails = success_count == 0 and total_runs > 0
        
        # 分析失敗模式
        failures = [r for r in records if r["status"] != "passed"]
        failure_reasons = [f["details"] for f in failures if f["details"]]
        common_failure_reason = None
        
        if failure_reasons:
            # 找出最常見的失敗原因
            reason_counts = Counter(failure_reasons)
            if reason_counts:
                common_failure_reason = reason_counts.most_common(1)[0][0]
        
        # 分析效能
        avg_time = sum(times) / len(times) if times else 0
        max_time = max(times) if times else 0
        min_time = min(times) if times else 0
        
        # 判斷效能問題（平均時間超過30秒或最大時間超過60秒）
        has_performance_issues = avg_time > 30 or max_time > 60
        
        return {
            "total_runs": total_runs,
            "success_count": success_count,
            "success_rate": success_rate,
            "is_flaky": is_flaky,
            "always_fails": always_fails,
            "failure_pattern": dict(Counter(statuses)),
            "common_failure_reason": common_failure_reason,
            "avg_execution_time": avg_time,
            "max_execution_time": max_time,
            "min_execution_time": min_time,
            "has_performance_issues": has_performance_issues,
            "execution_records": records
        }
    
    def _generate_summary(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成分析摘要"""
        
        total_tests = analysis["total_unique_tests"]
        flaky_count = len(analysis["flaky_tests"])
        consistent_failure_count = len(analysis["consistent_failures"])
        performance_issue_count = len(analysis["performance_issues"])
        
        # 計算整體穩定性分數 (0-100)
        if total_tests > 0:
            stability_score = max(0, 100 - (
                (flaky_count * 30) +  # flaky測試扣30分
                (consistent_failure_count * 50) +  # 持續失敗扣50分
                (performance_issue_count * 10)  # 效能問題扣10分
            ) / total_tests)
        else:
            stability_score = 100
        
        return {
            "total_tests": total_tests,
            "total_runs": analysis["total_runs"],
            "flaky_tests_count": flaky_count,
            "consistent_failures_count": consistent_failure_count,
            "performance_issues_count": performance_issue_count,
            "stability_score": round(stability_score, 2),
            "stability_grade": self._get_stability_grade(stability_score),
            "recommendations": self._generate_recommendations(analysis)
        }
    
    def _get_stability_grade(self, score: float) -> str:
        """根據穩定性分數給予等級"""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "B+"
        elif score >= 80:
            return "B"
        elif score >= 75:
            return "C+"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def _generate_recommendations(self, analysis: Dict[str, Any]]) -> List[str]:
        """生成改進建議"""
        recommendations = []
        
        if analysis["flaky_tests"]:
            recommendations.append(f"修復 {len(analysis['flaky_tests'])} 個不穩定測試，這些測試會間歇性失敗")
        
        if analysis["consistent_failures"]:
            recommendations.append(f"解決 {len(analysis['consistent_failures'])} 個持續失敗的測試")
        
        if analysis["performance_issues"]:
            recommendations.append(f"優化 {len(analysis['performance_issues'])} 個效能問題測試")
        
        # 根據穩定性分數給出建議
        score = analysis["summary"]["stability_score"]
        if score < 80:
            recommendations.append("整體測試穩定性需要顯著改善")
        elif score < 90:
            recommendations.append("測試穩定性有改善空間")
        
        if not recommendations:
            recommendations.append("測試穩定性良好，保持現狀")
        
        return recommendations
    
    def _generate_report(self, analysis: Dict[str, Any], source_files: List[Path]) -> Dict[str, Any]:
        """生成完整報告"""
        
        return {
            "generated_at": datetime.now().isoformat(),
            "analysis_metadata": {
                "source_files": [str(f) for f in source_files],
                "analyzer_version": "1.0.0"
            },
            "stability_analysis": analysis
        }
    
    def _save_report(self, report: Dict[str, Any]):
        """保存分析報告"""
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Stability analysis report saved to: {self.output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            raise


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="Analyze test stability from multiple test runs")
    parser.add_argument("--input-dir", required=True,
                       help="Directory containing stability test result files")
    parser.add_argument("--output", required=True,
                       help="Output path for stability analysis JSON report")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    
    # 執行分析
    try:
        analyzer = StabilityAnalyzer(
            input_dir=Path(args.input_dir),
            output_path=Path(args.output)
        )
        
        report = analyzer.analyze()
        
        if report.get("status") == "no_data":
            print("⚠️ No stability test data found")
            return 0
        
        analysis = report["stability_analysis"]
        summary = analysis["summary"]
        
        print(f"📊 Stability Analysis Results:")
        print(f"   Total tests analyzed: {summary['total_tests']}")
        print(f"   Total test runs: {summary['total_runs']}")
        print(f"   Stability score: {summary['stability_score']}/100 (Grade: {summary['stability_grade']})")
        
        if analysis["flaky_tests"]:
            print(f"⚠️  Flaky tests detected: {len(analysis['flaky_tests'])}")
            
        if analysis["consistent_failures"]:
            print(f"❌ Consistent failures: {len(analysis['consistent_failures'])}")
            
        if analysis["performance_issues"]:
            print(f"🐌 Performance issues: {len(analysis['performance_issues'])}")
        
        print(f"📄 Full report saved to: {args.output}")
        
    except Exception as e:
        logger.error(f"Failed to analyze stability: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())