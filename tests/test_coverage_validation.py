"""
測試覆蓋率驗證和報告機制
Task ID: 10 - 建立系統整合測試

這個模組提供測試覆蓋率的驗證和報告功能：
- 確保整體程式碼覆蓋率≥90%
- 核心業務邏輯覆蓋率≥95%
- 建立覆蓋率報告機制
- 識別未覆蓋的關鍵程式碼
- 提供覆蓋率改進建議

符合要求：
- N2: 測試覆蓋率達到高品質標準
- 建立覆蓋率報告和監控機制
"""

import pytest
import os
import subprocess
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CoverageThreshold:
    """覆蓋率門檻定義"""
    module_path: str
    min_line_coverage: float
    min_branch_coverage: float
    is_core_module: bool
    description: str


@dataclass
class CoverageReport:
    """覆蓋率報告"""
    timestamp: datetime
    overall_line_coverage: float
    overall_branch_coverage: float
    total_lines: int
    covered_lines: int
    total_branches: int
    covered_branches: int
    module_reports: List[Dict[str, Any]]
    uncovered_critical_lines: List[Dict[str, Any]]
    recommendations: List[str]
    meets_thresholds: bool


class CoverageValidator:
    """測試覆蓋率驗證器"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.coverage_thresholds = self._setup_coverage_thresholds()
        self.reports: List[CoverageReport] = []
        
    def _setup_coverage_thresholds(self) -> Dict[str, CoverageThreshold]:
        """設定覆蓋率門檻"""
        return {
            # 核心模組 - 要求更高覆蓋率
            "core": CoverageThreshold(
                module_path="core/",
                min_line_coverage=95.0,
                min_branch_coverage=90.0,
                is_core_module=True,
                description="核心基礎架構模組"
            ),
            
            # 服務模組 - 核心業務邏輯
            "services": CoverageThreshold(
                module_path="services/",
                min_line_coverage=95.0,
                min_branch_coverage=92.0,
                is_core_module=True,
                description="業務邏輯服務模組"
            ),
            
            # 面板模組 - UI互動邏輯
            "panels": CoverageThreshold(
                module_path="panels/",
                min_line_coverage=90.0,
                min_branch_coverage=85.0,
                is_core_module=False,
                description="使用者介面面板模組"
            ),
            
            # Cogs模組 - Discord整合
            "cogs": CoverageThreshold(
                module_path="cogs/",
                min_line_coverage=85.0,
                min_branch_coverage=80.0,
                is_core_module=False,
                description="Discord Cogs模組"
            ),
            
            # 腳本模組 - 工具和遷移
            "scripts": CoverageThreshold(
                module_path="scripts/",
                min_line_coverage=80.0,
                min_branch_coverage=75.0,
                is_core_module=False,
                description="工具和遷移腳本"
            )
        }
    
    async def run_coverage_analysis(
        self,
        test_path: str = "tests/",
        include_integration: bool = True,
        include_performance: bool = False
    ) -> CoverageReport:
        """執行覆蓋率分析"""
        
        # 建立覆蓋率執行命令
        coverage_cmd = self._build_coverage_command(test_path, include_integration, include_performance)
        
        try:
            # 執行測試和覆蓋率收集
            print("🧪 執行測試並收集覆蓋率資料...")
            result = subprocess.run(
                coverage_cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600  # 10分鐘超時
            )
            
            if result.returncode != 0:
                print(f"⚠️ 測試執行有警告或錯誤：\n{result.stderr}")
            
            # 生成覆蓋率報告
            coverage_data = await self._parse_coverage_data()
            
            # 分析未覆蓋的關鍵程式碼
            uncovered_critical = await self._identify_uncovered_critical_code(coverage_data)
            
            # 生成建議
            recommendations = await self._generate_coverage_recommendations(coverage_data, uncovered_critical)
            
            # 檢查是否符合門檻
            meets_thresholds = self._check_coverage_thresholds(coverage_data)
            
            # 建立報告
            report = CoverageReport(
                timestamp=datetime.now(),
                overall_line_coverage=coverage_data.get("overall_line_coverage", 0),
                overall_branch_coverage=coverage_data.get("overall_branch_coverage", 0),
                total_lines=coverage_data.get("total_lines", 0),
                covered_lines=coverage_data.get("covered_lines", 0),
                total_branches=coverage_data.get("total_branches", 0),
                covered_branches=coverage_data.get("covered_branches", 0),
                module_reports=coverage_data.get("module_reports", []),
                uncovered_critical_lines=uncovered_critical,
                recommendations=recommendations,
                meets_thresholds=meets_thresholds
            )
            
            self.reports.append(report)
            return report
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("覆蓋率分析超時")
        except Exception as e:
            raise RuntimeError(f"覆蓋率分析失敗：{e}")
    
    def _build_coverage_command(self, test_path: str, include_integration: bool, include_performance: bool) -> List[str]:
        """建立覆蓋率執行命令"""
        cmd = [
            "python", "-m", "pytest",
            test_path,
            "--cov=services",
            "--cov=panels", 
            "--cov=cogs",
            "--cov=core",
            "--cov-report=xml:coverage.xml",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-branch",
            "-v"
        ]
        
        # 條件性包含測試類型
        if not include_integration:
            cmd.extend(["-m", "not integration"])
        
        if not include_performance:
            cmd.extend(["-m", "not performance and not load"])
        
        return cmd
    
    async def _parse_coverage_data(self) -> Dict[str, Any]:
        """解析覆蓋率資料"""
        coverage_file = self.project_root / "coverage.xml"
        
        if not coverage_file.exists():
            raise FileNotFoundError("找不到覆蓋率報告檔案 coverage.xml")
        
        try:
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            # 解析總體覆蓋率
            coverage = root.find('coverage')
            if coverage is not None:
                line_rate = float(coverage.get('line-rate', 0)) * 100
                branch_rate = float(coverage.get('branch-rate', 0)) * 100
                lines_covered = int(coverage.get('lines-covered', 0))
                lines_valid = int(coverage.get('lines-valid', 0))
                branches_covered = int(coverage.get('branches-covered', 0))
                branches_valid = int(coverage.get('branches-valid', 0))
            else:
                line_rate = branch_rate = 0
                lines_covered = lines_valid = branches_covered = branches_valid = 0
            
            # 解析模組覆蓋率
            module_reports = []
            packages = root.findall('.//package')
            
            for package in packages:
                package_name = package.get('name', 'unknown')
                
                # 計算套件覆蓋率
                classes = package.findall('classes/class')
                package_lines_covered = package_lines_valid = 0
                package_branches_covered = package_branches_valid = 0
                
                for cls in classes:
                    cls_line_rate = float(cls.get('line-rate', 0))
                    cls_branch_rate = float(cls.get('branch-rate', 0))
                    
                    # 計算行數（簡化估算）
                    lines = cls.findall('lines/line')
                    cls_lines_valid = len(lines)
                    cls_lines_covered = int(cls_lines_valid * cls_line_rate)
                    
                    package_lines_valid += cls_lines_valid
                    package_lines_covered += cls_lines_covered
                
                if package_lines_valid > 0:
                    package_line_rate = (package_lines_covered / package_lines_valid) * 100
                else:
                    package_line_rate = 0
                
                module_reports.append({
                    "module_name": package_name,
                    "line_coverage": package_line_rate,
                    "branch_coverage": 0,  # 分支覆蓋率需要更詳細的解析
                    "lines_covered": package_lines_covered,
                    "lines_total": package_lines_valid,
                    "file_count": len(classes)
                })
            
            return {
                "overall_line_coverage": line_rate,
                "overall_branch_coverage": branch_rate,
                "total_lines": lines_valid,
                "covered_lines": lines_covered,
                "total_branches": branches_valid,
                "covered_branches": branches_covered,
                "module_reports": module_reports
            }
            
        except ET.ParseError as e:
            raise RuntimeError(f"解析覆蓋率XML失敗：{e}")
    
    async def _identify_uncovered_critical_code(self, coverage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """識別未覆蓋的關鍵程式碼"""
        uncovered_critical = []
        
        # 分析核心模組的未覆蓋程式碼
        for module_report in coverage_data.get("module_reports", []):
            module_name = module_report["module_name"]
            line_coverage = module_report["line_coverage"]
            
            # 檢查是否為核心模組且覆蓋率不足
            for threshold_name, threshold in self.coverage_thresholds.items():
                if threshold.module_path in module_name and threshold.is_core_module:
                    if line_coverage < threshold.min_line_coverage:
                        uncovered_critical.append({
                            "module_name": module_name,
                            "current_coverage": line_coverage,
                            "required_coverage": threshold.min_line_coverage,
                            "coverage_gap": threshold.min_line_coverage - line_coverage,
                            "priority": "high" if threshold.is_core_module else "medium",
                            "description": threshold.description
                        })
        
        # 按優先順序排序
        uncovered_critical.sort(key=lambda x: (x["priority"] == "high", x["coverage_gap"]), reverse=True)
        
        return uncovered_critical[:10]  # 返回前10個最關鍵的
    
    async def _generate_coverage_recommendations(
        self,
        coverage_data: Dict[str, Any],
        uncovered_critical: List[Dict[str, Any]]
    ) -> List[str]:
        """生成覆蓋率改進建議"""
        recommendations = []
        
        overall_coverage = coverage_data.get("overall_line_coverage", 0)
        
        # 總體覆蓋率建議
        if overall_coverage < 90:
            recommendations.append(
                f"整體覆蓋率 {overall_coverage:.1f}% 低於目標 90%，建議優先增加測試覆蓋率"
            )
        
        # 核心模組建議
        if uncovered_critical:
            recommendations.append(
                f"發現 {len(uncovered_critical)} 個核心模組覆蓋率不足，建議優先處理"
            )
            
            for critical in uncovered_critical[:3]:  # 前3個最重要的
                recommendations.append(
                    f"模組 {critical['module_name']} 覆蓋率 {critical['current_coverage']:.1f}% "
                    f"低於要求 {critical['required_coverage']:.1f}%，需要增加 {critical['coverage_gap']:.1f}% 覆蓋率"
                )
        
        # 分支覆蓋率建議
        branch_coverage = coverage_data.get("overall_branch_coverage", 0)
        if branch_coverage < 85:
            recommendations.append(
                f"分支覆蓋率 {branch_coverage:.1f}% 偏低，建議增加條件分支和錯誤處理測試"
            )
        
        # 模組特定建議
        module_reports = coverage_data.get("module_reports", [])
        low_coverage_modules = [m for m in module_reports if m["line_coverage"] < 80]
        
        if low_coverage_modules:
            recommendations.append(
                f"有 {len(low_coverage_modules)} 個模組覆蓋率低於 80%，建議檢查測試完整性"
            )
        
        return recommendations
    
    def _check_coverage_thresholds(self, coverage_data: Dict[str, Any]) -> bool:
        """檢查是否符合覆蓋率門檻"""
        overall_coverage = coverage_data.get("overall_line_coverage", 0)
        
        # 檢查總體門檻
        if overall_coverage < 90:
            return False
        
        # 檢查模組門檻
        module_reports = coverage_data.get("module_reports", [])
        
        for module_report in module_reports:
            module_name = module_report["module_name"]
            line_coverage = module_report["line_coverage"]
            
            for threshold_name, threshold in self.coverage_thresholds.items():
                if threshold.module_path in module_name:
                    if line_coverage < threshold.min_line_coverage:
                        return False
        
        return True
    
    def generate_coverage_html_report(self, report: CoverageReport) -> str:
        """生成HTML格式的覆蓋率報告"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Discord機器人系統整合測試覆蓋率報告</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
                .summary { display: flex; justify-content: space-around; margin: 20px 0; }
                .metric { text-align: center; padding: 15px; background-color: #e9e9e9; border-radius: 5px; }
                .metric.good { background-color: #d4edda; }
                .metric.warning { background-color: #fff3cd; }
                .metric.danger { background-color: #f8d7da; }
                .module-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                .module-table th, .module-table td { border: 1px solid #ddd; padding: 12px; text-align: left; }
                .module-table th { background-color: #f2f2f2; }
                .recommendations { background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
                .critical-issues { background-color: #fff0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Discord機器人系統整合測試覆蓋率報告</h1>
                <p>生成時間：{timestamp}</p>
                <p>整體狀態：<strong style="color: {status_color}">{status}</strong></p>
            </div>
            
            <div class="summary">
                <div class="metric {line_coverage_class}">
                    <h3>行覆蓋率</h3>
                    <div style="font-size: 2em; font-weight: bold;">{line_coverage:.1f}%</div>
                    <div>{covered_lines}/{total_lines} 行</div>
                </div>
                <div class="metric {branch_coverage_class}">
                    <h3>分支覆蓋率</h3>
                    <div style="font-size: 2em; font-weight: bold;">{branch_coverage:.1f}%</div>
                    <div>{covered_branches}/{total_branches} 分支</div>
                </div>
            </div>
            
            <h2>模組覆蓋率詳情</h2>
            <table class="module-table">
                <thead>
                    <tr>
                        <th>模組名稱</th>
                        <th>行覆蓋率</th>
                        <th>覆蓋行數/總行數</th>
                        <th>檔案數量</th>
                        <th>狀態</th>
                    </tr>
                </thead>
                <tbody>
                    {module_rows}
                </tbody>
            </table>
            
            {critical_section}
            
            <div class="recommendations">
                <h2>改進建議</h2>
                <ul>
                    {recommendations}
                </ul>
            </div>
        </body>
        </html>
        """
        
        # 判斷覆蓋率等級
        def get_coverage_class(coverage):
            if coverage >= 90:
                return "good"
            elif coverage >= 80:
                return "warning"
            else:
                return "danger"
        
        # 生成模組行
        module_rows = ""
        for module in report.module_reports:
            coverage = module["line_coverage"]
            status = "✅ 良好" if coverage >= 90 else "⚠️ 需改進" if coverage >= 80 else "❌ 不足"
            module_rows += f"""
                <tr>
                    <td>{module['module_name']}</td>
                    <td>{coverage:.1f}%</td>
                    <td>{module['lines_covered']}/{module['lines_total']}</td>
                    <td>{module['file_count']}</td>
                    <td>{status}</td>
                </tr>
            """
        
        # 生成關鍵問題區塊
        critical_section = ""
        if report.uncovered_critical_lines:
            critical_items = ""
            for critical in report.uncovered_critical_lines:
                critical_items += f"""
                    <li><strong>{critical['module_name']}</strong>: 
                        當前 {critical['current_coverage']:.1f}%, 
                        要求 {critical['required_coverage']:.1f}%, 
                        差距 {critical['coverage_gap']:.1f}%
                    </li>
                """
            
            critical_section = f"""
                <div class="critical-issues">
                    <h2>關鍵覆蓋率問題</h2>
                    <ul>{critical_items}</ul>
                </div>
            """
        
        # 生成建議列表
        recommendations_html = ""
        for rec in report.recommendations:
            recommendations_html += f"<li>{rec}</li>"
        
        return html_template.format(
            timestamp=report.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            status="通過" if report.meets_thresholds else "未通過",
            status_color="green" if report.meets_thresholds else "red",
            line_coverage=report.overall_line_coverage,
            line_coverage_class=get_coverage_class(report.overall_line_coverage),
            branch_coverage=report.overall_branch_coverage,
            branch_coverage_class=get_coverage_class(report.overall_branch_coverage),
            covered_lines=report.covered_lines,
            total_lines=report.total_lines,
            covered_branches=report.covered_branches,
            total_branches=report.total_branches,
            module_rows=module_rows,
            critical_section=critical_section,
            recommendations=recommendations_html
        )
    
    def save_report(self, report: CoverageReport, output_dir: str = "coverage_reports") -> str:
        """儲存覆蓋率報告"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp_str = report.timestamp.strftime("%Y%m%d_%H%M%S")
        
        # 儲存JSON報告
        json_file = output_path / f"coverage_report_{timestamp_str}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": report.timestamp.isoformat(),
                "overall_line_coverage": report.overall_line_coverage,
                "overall_branch_coverage": report.overall_branch_coverage,
                "total_lines": report.total_lines,
                "covered_lines": report.covered_lines,
                "total_branches": report.total_branches,
                "covered_branches": report.covered_branches,
                "module_reports": report.module_reports,
                "uncovered_critical_lines": report.uncovered_critical_lines,
                "recommendations": report.recommendations,
                "meets_thresholds": report.meets_thresholds
            }, f, indent=2, ensure_ascii=False)
        
        # 儲存HTML報告
        html_file = output_path / f"coverage_report_{timestamp_str}.html"
        html_content = self.generate_coverage_html_report(report)
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(html_file)


# 測試用例
class TestCoverageValidation:
    """測試覆蓋率驗證測試"""
    
    @pytest.mark.coverage
    @pytest.mark.asyncio
    async def test_overall_coverage_validation(self):
        """測試整體覆蓋率驗證"""
        validator = CoverageValidator()
        
        # 執行覆蓋率分析
        report = await validator.run_coverage_analysis(
            test_path="tests/",
            include_integration=True,
            include_performance=False  # 排除效能測試以節省時間
        )
        
        # 驗證覆蓋率要求
        assert report.overall_line_coverage >= 90.0, (
            f"整體行覆蓋率 {report.overall_line_coverage:.1f}% 低於要求的 90%"
        )
        
        # 驗證核心模組覆蓋率
        core_modules = [m for m in report.module_reports if any(
            core_path in m["module_name"] 
            for core_path in ["core/", "services/"]
        )]
        
        for module in core_modules:
            assert module["line_coverage"] >= 95.0, (
                f"核心模組 {module['module_name']} 覆蓋率 {module['line_coverage']:.1f}% "
                f"低於要求的 95%"
            )
        
        # 驗證關鍵問題不超過允許數量
        assert len(report.uncovered_critical_lines) <= 5, (
            f"發現 {len(report.uncovered_critical_lines)} 個關鍵覆蓋率問題，超過允許的 5 個"
        )
        
        # 生成並儲存報告
        report_file = validator.save_report(report)
        assert os.path.exists(report_file), "覆蓋率報告檔案應該被建立"
        
        print(f"✅ 覆蓋率驗證完成")
        print(f"   - 整體行覆蓋率：{report.overall_line_coverage:.1f}%")
        print(f"   - 整體分支覆蓋率：{report.overall_branch_coverage:.1f}%")
        print(f"   - 符合門檻：{'是' if report.meets_thresholds else '否'}")
        print(f"   - 關鍵問題：{len(report.uncovered_critical_lines)} 個")
        print(f"   - 報告檔案：{report_file}")
    
    @pytest.mark.coverage
    @pytest.mark.asyncio 
    async def test_core_module_coverage_validation(self):
        """測試核心模組覆蓋率驗證"""
        validator = CoverageValidator()
        
        # 僅執行核心模組測試
        report = await validator.run_coverage_analysis(
            test_path="tests/test_base_service.py tests/test_database_manager.py tests/test_exceptions.py",
            include_integration=False,
            include_performance=False
        )
        
        # 檢查核心模組
        core_modules = [m for m in report.module_reports if "core" in m["module_name"]]
        
        assert len(core_modules) > 0, "應該找到核心模組的覆蓋率資料"
        
        for module in core_modules:
            # 核心模組要求更高的覆蓋率
            assert module["line_coverage"] >= 95.0, (
                f"核心模組 {module['module_name']} 覆蓋率不足：{module['line_coverage']:.1f}%"
            )
        
        print(f"✅ 核心模組覆蓋率驗證完成，檢查了 {len(core_modules)} 個核心模組")
    
    @pytest.mark.coverage
    @pytest.mark.asyncio
    async def test_service_module_coverage_validation(self):
        """測試服務模組覆蓋率驗證"""
        validator = CoverageValidator()
        
        # 執行服務模組測試
        report = await validator.run_coverage_analysis(
            test_path="tests/services/",
            include_integration=False,
            include_performance=False
        )
        
        # 檢查服務模組
        service_modules = [m for m in report.module_reports if "services" in m["module_name"]]
        
        assert len(service_modules) > 0, "應該找到服務模組的覆蓋率資料"
        
        for module in service_modules:
            # 服務模組是核心業務邏輯，要求高覆蓋率
            assert module["line_coverage"] >= 90.0, (
                f"服務模組 {module['module_name']} 覆蓋率不足：{module['line_coverage']:.1f}%"
            )
        
        print(f"✅ 服務模組覆蓋率驗證完成，檢查了 {len(service_modules)} 個服務模組")


# 覆蓋率測試執行腳本
async def run_full_coverage_analysis():
    """執行完整覆蓋率分析"""
    validator = CoverageValidator()
    
    print("🧪 開始執行完整覆蓋率分析...")
    
    # 執行所有測試的覆蓋率分析
    report = await validator.run_coverage_analysis(
        test_path="tests/",
        include_integration=True,
        include_performance=True
    )
    
    # 輸出結果
    print("\n📊 覆蓋率分析結果：")
    print(f"   整體行覆蓋率：{report.overall_line_coverage:.1f}%")
    print(f"   整體分支覆蓋率：{report.overall_branch_coverage:.1f}%")
    print(f"   符合門檻要求：{'✅ 是' if report.meets_thresholds else '❌ 否'}")
    
    if report.uncovered_critical_lines:
        print(f"\n⚠️ 發現 {len(report.uncovered_critical_lines)} 個關鍵覆蓋率問題：")
        for critical in report.uncovered_critical_lines[:5]:
            print(f"   - {critical['module_name']}: {critical['current_coverage']:.1f}% "
                  f"(要求 {critical['required_coverage']:.1f}%)")
    
    if report.recommendations:
        print(f"\n💡 改進建議：")
        for rec in report.recommendations[:5]:
            print(f"   - {rec}")
    
    # 儲存報告
    report_file = validator.save_report(report)
    print(f"\n📄 詳細報告已儲存至：{report_file}")
    
    return report


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_full_coverage_analysis())