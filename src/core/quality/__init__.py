"""品質保證服務模組

提供程式碼品質檢查、型別檢查、和品質門檻控制功能。
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

__all__ = [
    "QualityAssuranceService",
    "QualityCheckResult",
    "QualityCheckStatus"
]


class QualityCheckStatus(Enum):
    """品質檢查狀態"""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    FAILED = "failed"


@dataclass
class QualityCheckResult:
    """品質檢查結果"""
    status: QualityCheckStatus
    mypy_errors: list[str]
    ruff_errors: list[str]
    type_coverage: float
    total_files: int
    checked_files: int
    error_count: int
    warning_count: int
    execution_time: float
    details: dict[str, Any]


class QualityAssuranceService:
    """品質保證服務
    
    負責執行 mypy 和 ruff 分析，生成品質報告，強制品質門檻控制。
    """

    def __init__(
        self,
        mypy_config_path: Path | None = None,
        ruff_config_path: Path | None = None
    ) -> None:
        """初始化品質保證服務
        
        Args:
            mypy_config_path: mypy 配置檔案路徑
            ruff_config_path: ruff 配置檔案路徑
        """
        self.project_root = Path.cwd()
        self.mypy_config = mypy_config_path or self.project_root / "quality" / "mypy.ini"
        self.ruff_config = ruff_config_path or self.project_root / "pyproject.toml"

    async def run_quality_checks(
        self,
        target_path: str,
        rules: list[str] | None = None
    ) -> QualityCheckResult:
        """執行完整靜態分析
        
        Args:
            target_path: 目標檢查路徑
            rules: 特定規則清單（可選）
            
        Returns:
            品質檢查結果
        """
        import time
        start_time = time.time()

        # 並行執行 mypy 和 ruff 檢查
        mypy_task = self._run_mypy_check(target_path, rules)
        ruff_task = self._run_ruff_check(target_path, rules)

        try:
            mypy_result, ruff_result = await asyncio.gather(
                mypy_task, ruff_task
            )
        except Exception as e:
            # 如果有任務失敗，使用錯誤結果
            mypy_result = {"return_code": -1, "error": True, "stderr": str(e), "tool": "mypy"}
            ruff_result = {"return_code": -1, "error": True, "stderr": str(e), "tool": "ruff"}

        # 計算型別覆蓋率
        type_coverage = await self._calculate_type_coverage(target_path)

        execution_time = time.time() - start_time

        # 彙總結果
        return self._aggregate_results(
            mypy_result, ruff_result, type_coverage, execution_time
        )
    async def _run_mypy_check(
        self,
        target_path: str,
        rules: list[str] | None = None
    ) -> dict[str, Any]:
        """執行 mypy 型別檢查
        
        Args:
            target_path: 檢查目標路徑
            rules: 特定規則
            
        Returns:
            mypy 檢查結果
        """
        cmd = [
            "mypy",
            "--config-file", str(self.mypy_config),
            "--show-error-codes",
            "--show-column-numbers",
            "--pretty",
            target_path
        ]

        if rules:
            for rule in rules:
                cmd.extend(["--enable-error-code", rule])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )

            stdout, stderr = await process.communicate()

            return {
                "return_code": process.returncode,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
                "tool": "mypy"
            }

        except Exception as e:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "tool": "mypy",
                "error": True
            }

    async def _run_ruff_check(
        self,
        target_path: str,
        rules: list[str] | None = None
    ) -> dict[str, Any]:
        """執行 ruff 程式碼檢查
        
        Args:
            target_path: 檢查目標路徑
            rules: 特定規則
            
        Returns:
            ruff 檢查結果
        """
        cmd = [
            "ruff", "check",
            "--config", str(self.ruff_config),
            "--output-format", "json",
            target_path
        ]

        if rules:
            cmd.extend(["--select", ",".join(rules)])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )

            stdout, stderr = await process.communicate()

            return {
                "return_code": process.returncode,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
                "tool": "ruff"
            }

        except Exception as e:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "tool": "ruff",
                "error": True
            }
    async def _calculate_type_coverage(self, target_path: str) -> float:
        """計算型別覆蓋率
        
        Args:
            target_path: 目標路徑
            
        Returns:
            型別覆蓋率百分比
        """
        try:
            # 使用 mypy 的 --any-exprs-report 來計算覆蓋率
            cmd = [
                "mypy",
                "--config-file", str(self.mypy_config),
                "--any-exprs-report", "/tmp/mypy_coverage",
                "--no-error-summary",
                target_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )

            await process.communicate()

            # 解析覆蓋率報告
            coverage_file = Path("/tmp/mypy_coverage/any-exprs.txt")
            if coverage_file.exists():
                content = coverage_file.read_text()
                # 簡化的覆蓋率計算邏輯
                lines = content.strip().split('\n')
                if lines and len(lines) > 1:
                    # 假設最後一行包含總覆蓋率資訊
                    total_exprs = len([l for l in lines if l.strip()])
                    typed_exprs = len([l for l in lines if 'Any' not in l])
                    return (typed_exprs / total_exprs * 100) if total_exprs > 0 else 0.0

            # 降級方案：基於檔案和函數統計
            return await self._estimate_type_coverage(target_path)

        except Exception:
            # 如果計算失敗，使用估算方法
            return await self._estimate_type_coverage(target_path)

    async def _estimate_type_coverage(self, target_path: str) -> float:
        """估算型別覆蓋率（降級方案）
        
        Args:
            target_path: 目標路徑
            
        Returns:
            估算的型別覆蓋率
        """
        import re
        from pathlib import Path

        total_functions = 0
        typed_functions = 0

        target = Path(target_path)
        if target.is_file():
            files = [target] if target.suffix == '.py' else []
        else:
            files = list(target.rglob('*.py'))

        for file_path in files:
            try:
                content = file_path.read_text(encoding='utf-8')

                # 找到所有函數定義
                func_pattern = re.compile(r'def\s+\w+\s*\([^)]*\)(?:\s*->\s*[^:]+)?:')
                functions = func_pattern.findall(content)

                total_functions += len(functions)

                # 計算有型別註解的函數
                typed_pattern = re.compile(r'def\s+\w+\s*\([^)]*:\s*\w+[^)]*\)(?:\s*->\s*[^:]+)?:')
                typed_functions += len(typed_pattern.findall(content))

            except Exception:
                continue

        return (typed_functions / total_functions * 100) if total_functions > 0 else 0.0
    def _aggregate_results(
        self,
        mypy_result: dict[str, Any],
        ruff_result: dict[str, Any],
        type_coverage: float,
        execution_time: float
    ) -> QualityCheckResult:
        """彙總檢查結果
        
        Args:
            mypy_result: mypy 檢查結果
            ruff_result: ruff 檢查結果
            type_coverage: 型別覆蓋率
            execution_time: 執行時間
            
        Returns:
            彙總的品質檢查結果
        """
        # 處理 mypy 錯誤
        mypy_errors = []
        if isinstance(mypy_result, dict) and mypy_result.get("stdout"):
            mypy_errors = [
                line.strip() for line in mypy_result["stdout"].split('\n')
                if line.strip() and 'error:' in line
            ]

        # 處理 ruff 錯誤
        ruff_errors = []
        if isinstance(ruff_result, dict) and ruff_result.get("stdout"):
            try:
                ruff_data = json.loads(ruff_result["stdout"])
                ruff_errors = [
                    f"{item['filename']}:{item['location']['row']}:{item['location']['column']}: {item['code']} {item['message']}"
                    for item in ruff_data
                ]
            except (json.JSONDecodeError, KeyError):
                ruff_errors = [ruff_result.get("stderr", "Unknown ruff error")]

        # 確定整體狀態
        error_count = len(mypy_errors) + len(ruff_errors)

        if error_count == 0:
            status = QualityCheckStatus.SUCCESS
        elif error_count <= 5:
            status = QualityCheckStatus.WARNING
        else:
            status = QualityCheckStatus.ERROR

        # 如果有執行錯誤，狀態為 FAILED
        if (isinstance(mypy_result, dict) and mypy_result.get("error")) or \
           (isinstance(ruff_result, dict) and ruff_result.get("error")):
            status = QualityCheckStatus.FAILED

        return QualityCheckResult(
            status=status,
            mypy_errors=mypy_errors,
            ruff_errors=ruff_errors,
            type_coverage=type_coverage,
            total_files=0,  # 需要實際計算
            checked_files=0,  # 需要實際計算
            error_count=error_count,
            warning_count=0,  # 可以進一步細分
            execution_time=execution_time,
            details={
                "mypy_result": mypy_result,
                "ruff_result": ruff_result,
                "coverage_details": {"type_coverage": type_coverage}
            }
        )
    def generate_quality_report(
        self,
        results: QualityCheckResult,
        format: str = "json"
    ) -> dict[str, Any]:
        """生成包含型別覆蓋率的品質報告
        
        Args:
            results: 品質檢查結果
            format: 報告格式 ("json", "text", "html")
            
        Returns:
            格式化的品質報告
        """
        report = {
            "summary": {
                "status": results.status.value,
                "type_coverage": results.type_coverage,
                "error_count": results.error_count,
                "warning_count": results.warning_count,
                "execution_time": results.execution_time,
                "timestamp": self._get_timestamp()
            },
            "mypy": {
                "errors": results.mypy_errors,
                "error_count": len(results.mypy_errors)
            },
            "ruff": {
                "errors": results.ruff_errors,
                "error_count": len(results.ruff_errors)
            },
            "coverage": {
                "type_coverage_percentage": results.type_coverage,
                "total_files": results.total_files,
                "checked_files": results.checked_files
            },
            "details": results.details
        }

        if format == "text":
            return self._format_text_report(report)
        elif format == "html":
            return self._format_html_report(report)
        else:
            return report

    def enforce_quality_gates(
        self,
        results: QualityCheckResult,
        strict: bool = True
    ) -> bool:
        """嚴格模式下零型別錯誤才通過
        
        Args:
            results: 品質檢查結果
            strict: 是否使用嚴格模式
            
        Returns:
            是否通過品質門檻
        """
        if strict:
            # 嚴格模式：零錯誤且型別覆蓋率 >= 95%
            return (
                results.error_count == 0 and
                results.type_coverage >= 95.0 and
                results.status in [QualityCheckStatus.SUCCESS, QualityCheckStatus.WARNING]
            )
        else:
            # 寬鬆模式：錯誤數量在可接受範圍內
            return (
                results.error_count <= 10 and
                results.type_coverage >= 80.0 and
                results.status != QualityCheckStatus.FAILED
            )

    def _get_timestamp(self) -> str:
        """獲取當前時間戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    def _format_text_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """格式化文字報告"""
        text_lines = [
            f"品質檢查報告 - {report['summary']['timestamp']}",
            f"狀態: {report['summary']['status']}",
            f"型別覆蓋率: {report['summary']['type_coverage']:.1f}%",
            f"錯誤數量: {report['summary']['error_count']}",
            f"執行時間: {report['summary']['execution_time']:.2f}秒",
            "",
            "Mypy 錯誤:",
            *report['mypy']['errors'],
            "",
            "Ruff 錯誤:",
            *report['ruff']['errors']
        ]

        return {"format": "text", "content": "\n".join(text_lines), "raw_data": report}

    def _format_html_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """格式化 HTML 報告"""
        # 簡化的 HTML 格式化
        html_content = f"""
        <h1>品質檢查報告</h1>
        <p>狀態: <strong>{report['summary']['status']}</strong></p>
        <p>型別覆蓋率: <strong>{report['summary']['type_coverage']:.1f}%</strong></p>
        <p>錯誤數量: <strong>{report['summary']['error_count']}</strong></p>
        <h2>詳細錯誤</h2>
        <h3>Mypy</h3>
        <ul>{''.join(f'<li>{error}</li>' for error in report['mypy']['errors'])}</ul>
        <h3>Ruff</h3>
        <ul>{''.join(f'<li>{error}</li>' for error in report['ruff']['errors'])}</ul>
        """

        return {"format": "html", "content": html_content, "raw_data": report}
