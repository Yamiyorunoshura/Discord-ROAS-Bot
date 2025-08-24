"""
併發測試覆蓋率驗證
確保併發測試覆蓋率達到 ≥ 90% 的目標
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, Any, List


class ConcurrencyTestCoverageValidator:
    """併發測試覆蓋率驗證器"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.concurrency_tests_dir = self.project_root / "tests" / "concurrency"
        self.target_modules = [
            "src/db/sqlite.py",
            "core/database_manager.py", 
            "tests/concurrency/test_connection_pool.py",
            "tests/concurrency/test_advanced_scenarios.py"
        ]
        
    def run_coverage_analysis(self) -> Dict[str, Any]:
        """執行覆蓋率分析"""
        print("🔍 執行併發測試覆蓋率分析...")
        
        # 設定覆蓋率命令
        coverage_cmd = [
            "python", "-m", "pytest", 
            str(self.concurrency_tests_dir),
            "--cov=src.db.sqlite",
            "--cov=core.database_manager",
            "--cov=tests.concurrency",
            "--cov-report=json",
            "--cov-report=term-missing",
            "--cov-report=html:test_reports/concurrency/coverage_html",
            "-v"
        ]
        
        try:
            # 執行測試和覆蓋率分析
            result = subprocess.run(
                coverage_cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600  # 10分鐘超時
            )
            
            coverage_data = self._parse_coverage_json()
            
            return {
                "success": result.returncode == 0,
                "coverage_data": coverage_data,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "analysis": self._analyze_coverage(coverage_data)
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Coverage analysis timed out",
                "analysis": {"overall_coverage": 0}
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "analysis": {"overall_coverage": 0}
            }
    
    def _parse_coverage_json(self) -> Dict[str, Any]:
        """解析覆蓋率JSON報告"""
        coverage_file = self.project_root / "coverage.json"
        
        if not coverage_file.exists():
            return {"files": {}, "totals": {"percent_covered": 0}}
        
        try:
            with open(coverage_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"files": {}, "totals": {"percent_covered": 0}}
    
    def _analyze_coverage(self, coverage_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析覆蓋率資料"""
        if not coverage_data or "files" not in coverage_data:
            return {
                "overall_coverage": 0,
                "target_coverage": 90,
                "meets_target": False,
                "file_coverage": {},
                "recommendations": ["無法取得覆蓋率資料，請檢查測試執行"]
            }
        
        files = coverage_data.get("files", {})
        totals = coverage_data.get("totals", {})
        overall_coverage = totals.get("percent_covered", 0)
        
        # 分析目標模組覆蓋率
        file_coverage = {}
        for target_file in self.target_modules:
            # 尋找匹配的檔案路徑
            matching_files = [
                (path, data) for path, data in files.items() 
                if target_file in path or path.endswith(target_file.replace("src/", "").replace("core/", "").replace("tests/", ""))
            ]
            
            if matching_files:
                path, data = matching_files[0]
                summary = data.get("summary", {})
                file_coverage[target_file] = {
                    "path": path,
                    "coverage": summary.get("percent_covered", 0),
                    "lines_covered": summary.get("covered_lines", 0),
                    "lines_missing": summary.get("missing_lines", 0),
                    "total_lines": summary.get("num_statements", 0)
                }
            else:
                file_coverage[target_file] = {
                    "path": "not_found",
                    "coverage": 0,
                    "error": "File not found in coverage report"
                }
        
        # 生成建議
        recommendations = self._generate_coverage_recommendations(
            overall_coverage, file_coverage
        )
        
        return {
            "overall_coverage": overall_coverage,
            "target_coverage": 90,
            "meets_target": overall_coverage >= 90,
            "file_coverage": file_coverage,
            "recommendations": recommendations,
            "total_statements": totals.get("num_statements", 0),
            "covered_statements": totals.get("covered_lines", 0),
            "missing_statements": totals.get("missing_lines", 0)
        }
    
    def _generate_coverage_recommendations(
        self, 
        overall_coverage: float, 
        file_coverage: Dict[str, Any]
    ) -> List[str]:
        """生成覆蓋率改善建議"""
        recommendations = []
        
        if overall_coverage < 90:
            recommendations.append(
                f"整體覆蓋率 {overall_coverage:.1f}% 低於目標 90%，需要增加測試"
            )
        
        # 檢查各檔案覆蓋率
        low_coverage_files = [
            (file, data) for file, data in file_coverage.items()
            if isinstance(data, dict) and data.get("coverage", 0) < 90
        ]
        
        if low_coverage_files:
            recommendations.append("以下檔案覆蓋率需要改善：")
            for file, data in low_coverage_files:
                if "error" in data:
                    recommendations.append(f"  • {file}: {data['error']}")
                else:
                    coverage = data.get("coverage", 0)
                    missing = data.get("lines_missing", 0)
                    recommendations.append(
                        f"  • {file}: {coverage:.1f}% (需要測試 {missing} 行程式碼)"
                    )
        
        if overall_coverage >= 90:
            recommendations.append("✅ 覆蓋率達標！繼續保持測試品質")
        
        # 具體改善建議
        if overall_coverage < 80:
            recommendations.extend([
                "建議增加單元測試覆蓋邊緣情況和錯誤處理",
                "為資料庫連線管理功能增加更多測試案例",
                "測試併發場景的異常處理路徑"
            ])
        elif overall_coverage < 90:
            recommendations.extend([
                "關注未測試的程式碼分支，特別是錯誤處理",
                "增加集成測試驗證完整流程"
            ])
        
        return recommendations
    
    def generate_coverage_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成覆蓋率報告"""
        if not analysis_result["success"]:
            return f"❌ 覆蓋率分析失敗: {analysis_result.get('error', '未知錯誤')}"
        
        analysis = analysis_result["analysis"]
        overall_coverage = analysis["overall_coverage"]
        meets_target = analysis["meets_target"]
        
        report = [
            "📊 T2 併發測試覆蓋率報告",
            "=" * 60,
            f"整體覆蓋率: {overall_coverage:.1f}%",
            f"目標覆蓋率: {analysis['target_coverage']}%",
            f"達標狀態: {'✅ 達標' if meets_target else '❌ 未達標'}",
            "",
            "📁 各檔案覆蓋率:",
        ]
        
        for file, data in analysis["file_coverage"].items():
            if isinstance(data, dict):
                if "error" in data:
                    report.append(f"  ❌ {file}: {data['error']}")
                else:
                    coverage = data.get("coverage", 0)
                    status = "✅" if coverage >= 90 else "⚠️" if coverage >= 80 else "❌"
                    total_lines = data.get("total_lines", 0)
                    covered_lines = data.get("lines_covered", 0)
                    report.append(
                        f"  {status} {file}: {coverage:.1f}% ({covered_lines}/{total_lines} 行)"
                    )
        
        if analysis["recommendations"]:
            report.extend([
                "",
                "💡 改善建議:",
            ])
            for rec in analysis["recommendations"]:
                if rec.startswith("  •"):
                    report.append(rec)
                else:
                    report.append(f"  • {rec}")
        
        report.extend([
            "",
            f"📈 總計: {analysis.get('covered_statements', 0)}/{analysis.get('total_statements', 0)} 程式碼行已測試",
            "=" * 60
        ])
        
        return "\n".join(report)
    
    def validate_coverage_target(self, min_coverage: float = 90.0) -> bool:
        """驗證覆蓋率是否達到目標"""
        result = self.run_coverage_analysis()
        
        if not result["success"]:
            print(f"❌ 覆蓋率檢查失敗: {result.get('error', '未知錯誤')}")
            return False
        
        analysis = result["analysis"]
        overall_coverage = analysis["overall_coverage"]
        
        # 生成並顯示報告
        report = self.generate_coverage_report(result)
        print(report)
        
        # 儲存報告
        report_file = self.project_root / "test_reports" / "concurrency" / "coverage_report.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
            f.write(f"\n\n生成時間: {json.dumps({'timestamp': str(Path(__file__).stat().st_mtime)}, ensure_ascii=False, indent=2)}")
        
        print(f"\n📄 詳細報告已儲存: {report_file}")
        
        return overall_coverage >= min_coverage


def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="併發測試覆蓋率驗證")
    parser.add_argument(
        "--project-root",
        default=".",
        help="專案根目錄"
    )
    parser.add_argument(
        "--min-coverage", 
        type=float,
        default=90.0,
        help="最小覆蓋率目標"
    )
    
    args = parser.parse_args()
    
    validator = ConcurrencyTestCoverageValidator(args.project_root)
    
    print("🔍 開始驗證 T2 併發測試覆蓋率...")
    
    success = validator.validate_coverage_target(args.min_coverage)
    
    if success:
        print(f"🎉 併發測試覆蓋率達到 {args.min_coverage}% 目標！")
        sys.exit(0)
    else:
        print(f"⚠️  併發測試覆蓋率未達到 {args.min_coverage}% 目標")
        sys.exit(1)


if __name__ == "__main__":
    main()