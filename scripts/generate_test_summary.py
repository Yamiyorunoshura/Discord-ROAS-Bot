#!/usr/bin/env python3
"""
面板功能驗證測試總結生成器
專案: Discord ROAS Bot v2.3.1
Story: 1.3.panel-functionality-verification
"""

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


class TestSummaryGenerator:
    """測試總結報告生成器"""

    def __init__(self):
        self.report_dir = Path("test_reports/panel_verification")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
    def load_coverage_data(self):
        """載入覆蓋率數據"""
        coverage_file = self.report_dir / "coverage.json"
        if coverage_file.exists():
            with open(coverage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
        
    def load_junit_results(self, filename):
        """載入 JUnit XML 測試結果"""
        junit_file = self.report_dir / filename
        if not junit_file.exists():
            return {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0}
            
        try:
            tree = ET.parse(junit_file)
            root = tree.getroot()
            
            # 解析測試統計
            total_tests = int(root.get('tests', 0))
            failures = int(root.get('failures', 0))
            errors = int(root.get('errors', 0))
            skipped = int(root.get('skipped', 0))
            passed = total_tests - failures - errors - skipped
            
            return {
                "total": total_tests,
                "passed": passed,
                "failed": failures,
                "skipped": skipped,
                "errors": errors,
                "success_rate": (passed / total_tests * 100) if total_tests > 0 else 0
            }
        except Exception as e:
            print(f"解析 {filename} 時發生錯誤: {e}")
            return {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    
    def load_benchmark_data(self):
        """載入基準測試數據"""
        benchmark_file = self.report_dir / "benchmark.json"
        if benchmark_file.exists():
            with open(benchmark_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
        
    def generate_summary_report(self):
        """生成總結報告"""
        # 載入各種測試數據
        coverage_data = self.load_coverage_data()
        unit_results = self.load_junit_results("unit_tests.xml")
        integration_results = self.load_junit_results("integration_tests.xml")
        regression_results = self.load_junit_results("regression_tests.xml")
        performance_results = self.load_junit_results("performance_tests.xml")
        emoji_results = self.load_junit_results("emoji_verification_tests.xml")
        benchmark_data = self.load_benchmark_data()
        
        # 計算總體統計
        total_tests = (
            unit_results["total"] + 
            integration_results["total"] + 
            regression_results["total"] + 
            performance_results["total"] +
            emoji_results["total"]
        )
        
        total_passed = (
            unit_results["passed"] + 
            integration_results["passed"] + 
            regression_results["passed"] + 
            performance_results["passed"] +
            emoji_results["passed"]
        )
        
        total_failed = (
            unit_results["failed"] + 
            integration_results["failed"] + 
            regression_results["failed"] + 
            performance_results["failed"] +
            emoji_results["failed"]
        )
        
        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # 生成 Markdown 報告
        report_content = self._generate_markdown_report(
            coverage_data, unit_results, integration_results, 
            regression_results, performance_results, emoji_results,
            benchmark_data, total_tests, total_passed, total_failed, overall_success_rate
        )
        
        # 保存報告
        report_file = self.report_dir / "test_summary.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
            
        print(f"✅ 測試總結報告已生成: {report_file}")
        return report_file
        
    def _generate_markdown_report(self, coverage_data, unit_results, integration_results, 
                                  regression_results, performance_results, emoji_results,
                                  benchmark_data, total_tests, total_passed, total_failed, 
                                  overall_success_rate):
        """生成 Markdown 格式的報告"""
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report = f"""# 面板功能驗證測試報告

**專案**: Discord ROAS Bot v2.3.1  
**Story**: 1.3.panel-functionality-verification  
**生成時間**: {timestamp}  
**執行者**: Dev Agent James  

---

## 📊 測試總覽

| 指標 | 數值 | 狀態 |
|------|------|------|
| 總測試數 | {total_tests} | {'✅' if total_tests > 0 else '⚠️'} |
| 通過測試 | {total_passed} | {'✅' if total_passed == total_tests else '⚠️'} |
| 失敗測試 | {total_failed} | {'✅' if total_failed == 0 else '❌'} |
| 成功率 | {overall_success_rate:.1f}% | {'✅' if overall_success_rate >= 95 else '❌' if overall_success_rate < 85 else '⚠️'} |

## 📋 測試類別結果

### 🔬 單元測試 (Unit Tests)
| 項目 | 結果 |
|------|------|
| 總數 | {unit_results['total']} |
| 通過 | {unit_results['passed']} |
| 失敗 | {unit_results['failed']} |
| 跳過 | {unit_results['skipped']} |
| 錯誤 | {unit_results['errors']} |
| 成功率 | {unit_results.get('success_rate', 0):.1f}% |

### 🔗 整合測試 (Integration Tests)  
| 項目 | 結果 |
|------|------|
| 總數 | {integration_results['total']} |
| 通過 | {integration_results['passed']} |
| 失敗 | {integration_results['failed']} |
| 成功率 | {integration_results.get('success_rate', 0):.1f}% |

### 🔄 回歸測試 (Regression Tests)
| 項目 | 結果 |
|------|------|
| 總數 | {regression_results['total']} |
| 通過 | {regression_results['passed']} |
| 失敗 | {regression_results['failed']} |
| 成功率 | {regression_results.get('success_rate', 0):.1f}% |

### ⚡ 性能測試 (Performance Tests)
| 項目 | 結果 |
|------|------|
| 總數 | {performance_results['total']} |
| 通過 | {performance_results['passed']} |
| 失敗 | {performance_results['failed']} |
| 成功率 | {performance_results.get('success_rate', 0):.1f}% |

### 🎭 表情符號驗證測試
| 項目 | 結果 |
|------|------|
| 總數 | {emoji_results['total']} |
| 通過 | {emoji_results['passed']} |
| 失敗 | {emoji_results['failed']} |
| 成功率 | {emoji_results.get('success_rate', 0):.1f}% |

"""

        # 添加覆蓋率信息
        if coverage_data:
            try:
                total_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
                report += f"""## 📈 程式碼覆蓋率

| 指標 | 結果 | 狀態 |
|------|------|------|
| 總覆蓋率 | {total_coverage:.1f}% | {'✅' if total_coverage >= 85 else '❌' if total_coverage < 70 else '⚠️'} |
| 目標覆蓋率 | 85% | {'✅' if total_coverage >= 85 else '❌'} |

### 詳細覆蓋率報告
- HTML 報告: `htmlcov/panel/index.html`
- JSON 報告: `test_reports/panel_verification/coverage.json`

"""
            except Exception:
                report += "## 📈 程式碼覆蓋率\n無法解析覆蓋率數據\n\n"
        
        # 添加基準測試信息
        if benchmark_data:
            report += """## ⏱️ 性能基準測試

基準測試已執行，詳細結果請查看 `test_reports/panel_verification/benchmark.json`

"""

        # 添加 Acceptance Criteria 驗證
        report += f"""## ✅ Acceptance Criteria 驗證

### AC1: 所有面板功能正常運作
- 單元測試通過率: {unit_results.get('success_rate', 0):.1f}%
- 狀態: {'✅ 通過' if unit_results.get('success_rate', 0) >= 95 else '❌ 未通過'}

### AC2: 無表情符號相關錯誤  
- 表情符號驗證測試: {emoji_results['passed']}/{emoji_results['total']}
- 狀態: {'✅ 通過' if emoji_results['failed'] == 0 else '❌ 未通過'}

### AC3: 必要的表情符號正確顯示
- 功能性表情符號測試通過
- 狀態: {'✅ 通過' if emoji_results.get('success_rate', 0) >= 95 else '❌ 未通過'}

### AC4: 進行完整的回歸測試
- 回歸測試通過率: {regression_results.get('success_rate', 0):.1f}%  
- 狀態: {'✅ 通過' if regression_results.get('success_rate', 0) >= 95 else '❌ 未通過'}

### AC5: 確認系統穩定性
- 性能測試通過率: {performance_results.get('success_rate', 0):.1f}%
- 狀態: {'✅ 通過' if performance_results.get('success_rate', 0) >= 95 else '❌ 未通過'}

## 📁 測試產物

### 測試報告文件
- 單元測試: `test_reports/panel_verification/unit_tests.xml`
- 整合測試: `test_reports/panel_verification/integration_tests.xml`  
- 回歸測試: `test_reports/panel_verification/regression_tests.xml`
- 性能測試: `test_reports/panel_verification/performance_tests.xml`
- 表情符號驗證: `test_reports/panel_verification/emoji_verification_tests.xml`

### 覆蓋率報告
- HTML: `htmlcov/panel/index.html`
- JSON: `test_reports/panel_verification/coverage.json`

### 性能基準
- JSON: `test_reports/panel_verification/benchmark.json`

## 🎯 結論

總體測試結果: {'✅ **通過**' if overall_success_rate >= 95 and total_failed == 0 else '❌ **需要修復**' if overall_success_rate < 85 else '⚠️ **部分通過**'}

### 建議後續動作
"""

        if overall_success_rate >= 95 and total_failed == 0:
            report += """
- ✅ 所有測試通過，面板功能驗證成功
- ✅ 可以標記 Story 1.3 為完成狀態  
- ✅ 進行最終的手動驗證測試
"""
        elif total_failed > 0:
            report += f"""
- ❌ 有 {total_failed} 個測試失敗，需要修復
- ❌ 檢查測試失敗原因並修復問題
- ❌ 重新執行測試套件
"""
        else:
            report += """
- ⚠️ 測試結果部分通過，需要改進
- ⚠️ 檢查跳過的測試是否需要實現
- ⚠️ 提升測試覆蓋率
"""

        report += f"""
---
*報告自動生成於 {timestamp} by Dev Agent James*
"""

        return report


def main():
    """主函數"""
    print("🔄 生成面板功能驗證測試總結報告...")
    
    generator = TestSummaryGenerator()
    report_file = generator.generate_summary_report()
    
    print(f"✅ 報告生成完成: {report_file}")
    print("📋 請檢查測試結果並根據建議採取後續行動")


if __name__ == "__main__":
    main()