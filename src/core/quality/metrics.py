"""品質指標收集模組

提供型別覆蓋率監控、趨勢分析和指標收集功能。
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = [
    "QualityMetrics",
    "QualityMetricsCollector"
]


@dataclass
class QualityMetrics:
    """品質指標資料結構"""
    timestamp: datetime
    project_path: str
    type_coverage: float
    mypy_error_count: int
    ruff_error_count: int
    total_files: int
    checked_files: int
    execution_time: float
    git_commit_hash: str | None = None
    branch_name: str | None = None


class QualityMetricsCollector:
    """品質指標收集器
    
    負責收集、存儲和分析品質指標資料。
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """初始化指標收集器
        
        Args:
            db_path: 資料庫路徑
        """
        self.db_path = db_path or Path("quality_metrics.db")
        self._init_database()

    def _init_database(self) -> None:
        """初始化資料庫表結構"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quality_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    type_coverage REAL NOT NULL,
                    mypy_error_count INTEGER NOT NULL,
                    ruff_error_count INTEGER NOT NULL,
                    total_files INTEGER NOT NULL,
                    checked_files INTEGER NOT NULL,
                    execution_time REAL NOT NULL,
                    git_commit_hash TEXT,
                    branch_name TEXT
                )
            """)

            # 創建索引以提升查詢效能
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON quality_metrics(timestamp)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_project_path 
                ON quality_metrics(project_path)
            """)

    def collect_metrics(
        self,
        project_path: str,
        type_coverage: float,
        mypy_error_count: int,
        ruff_error_count: int,
        total_files: int,
        checked_files: int,
        execution_time: float
    ) -> QualityMetrics:
        """收集品質指標
        
        Args:
            project_path: 專案路徑
            type_coverage: 型別覆蓋率
            mypy_error_count: mypy 錯誤數量
            ruff_error_count: ruff 錯誤數量
            total_files: 總檔案數
            checked_files: 已檢查檔案數
            execution_time: 執行時間
            
        Returns:
            品質指標物件
        """
        # 獲取 Git 資訊
        git_info = self._get_git_info()

        metrics = QualityMetrics(
            timestamp=datetime.now(),
            project_path=project_path,
            type_coverage=type_coverage,
            mypy_error_count=mypy_error_count,
            ruff_error_count=ruff_error_count,
            total_files=total_files,
            checked_files=checked_files,
            execution_time=execution_time,
            git_commit_hash=git_info.get("commit_hash"),
            branch_name=git_info.get("branch_name")
        )

        # 存儲到資料庫
        self._store_metrics(metrics)

        return metrics
    def _store_metrics(self, metrics: QualityMetrics) -> None:
        """存儲指標到資料庫
        
        Args:
            metrics: 品質指標
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO quality_metrics (
                    timestamp, project_path, type_coverage,
                    mypy_error_count, ruff_error_count,
                    total_files, checked_files, execution_time,
                    git_commit_hash, branch_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.timestamp.isoformat(),
                metrics.project_path,
                metrics.type_coverage,
                metrics.mypy_error_count,
                metrics.ruff_error_count,
                metrics.total_files,
                metrics.checked_files,
                metrics.execution_time,
                metrics.git_commit_hash,
                metrics.branch_name
            ))

    def get_coverage_trend(
        self,
        project_path: str,
        days: int = 30
    ) -> list[dict[str, Any]]:
        """獲取型別覆蓋率趨勢
        
        Args:
            project_path: 專案路徑
            days: 天數範圍
            
        Returns:
            趨勢資料清單
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"""
                SELECT 
                    timestamp,
                    type_coverage,
                    mypy_error_count,
                    ruff_error_count,
                    git_commit_hash
                FROM quality_metrics
                WHERE project_path = ?
                  AND datetime(timestamp) >= datetime('now', '-{days} days')
                ORDER BY timestamp DESC
            """, (project_path,))

            return [dict(row) for row in cursor.fetchall()]

    def get_latest_metrics(self, project_path: str) -> QualityMetrics | None:
        """獲取最新的品質指標
        
        Args:
            project_path: 專案路徑
            
        Returns:
            最新的品質指標或 None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM quality_metrics
                WHERE project_path = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (project_path,))

            row = cursor.fetchone()
            if row:
                return QualityMetrics(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    project_path=row["project_path"],
                    type_coverage=row["type_coverage"],
                    mypy_error_count=row["mypy_error_count"],
                    ruff_error_count=row["ruff_error_count"],
                    total_files=row["total_files"],
                    checked_files=row["checked_files"],
                    execution_time=row["execution_time"],
                    git_commit_hash=row["git_commit_hash"],
                    branch_name=row["branch_name"]
                )
            return None
    def generate_coverage_report(
        self,
        project_path: str
    ) -> dict[str, Any]:
        """生成型別覆蓋率趨勢報告
        
        Args:
            project_path: 專案路徑
            
        Returns:
            覆蓋率報告
        """
        # 獲取最近 30 天的趨勢
        trend_data = self.get_coverage_trend(project_path, days=30)

        if not trend_data:
            return {
                "error": "No coverage data available",
                "project_path": project_path
            }

        # 計算統計資料
        coverages = [data["type_coverage"] for data in trend_data]
        latest = trend_data[0]
        oldest = trend_data[-1] if len(trend_data) > 1 else latest

        coverage_change = latest["type_coverage"] - oldest["type_coverage"]
        avg_coverage = sum(coverages) / len(coverages)
        max_coverage = max(coverages)
        min_coverage = min(coverages)

        return {
            "project_path": project_path,
            "current_coverage": latest["type_coverage"],
            "coverage_change_30_days": coverage_change,
            "average_coverage": avg_coverage,
            "max_coverage": max_coverage,
            "min_coverage": min_coverage,
            "total_measurements": len(trend_data),
            "latest_errors": {
                "mypy": latest["mypy_error_count"],
                "ruff": latest["ruff_error_count"]
            },
            "trend_data": trend_data[:10],  # 最近 10 次測量
            "report_timestamp": datetime.now().isoformat()
        }

    def get_quality_summary(self, project_path: str) -> dict[str, Any]:
        """獲取品質摘要統計
        
        Args:
            project_path: 專案路徑
            
        Returns:
            品質摘要
        """
        latest = self.get_latest_metrics(project_path)
        if not latest:
            return {"error": "No metrics available"}

        # 獲取 7 天趨勢進行比較
        trend_7d = self.get_coverage_trend(project_path, days=7)

        improvement_7d = 0.0
        if len(trend_7d) > 1:
            improvement_7d = trend_7d[0]["type_coverage"] - trend_7d[-1]["type_coverage"]

        # 品質等級評估
        quality_grade = self._calculate_quality_grade(latest)

        return {
            "current_metrics": asdict(latest),
            "quality_grade": quality_grade,
            "improvement_7_days": improvement_7d,
            "meets_target": latest.type_coverage >= 95.0,
            "error_free": latest.mypy_error_count == 0 and latest.ruff_error_count == 0,
            "summary_timestamp": datetime.now().isoformat()
        }

    def _calculate_quality_grade(self, metrics: QualityMetrics) -> str:
        """計算品質等級
        
        Args:
            metrics: 品質指標
            
        Returns:
            品質等級 (A+, A, B+, B, C, D, F)
        """
        coverage = metrics.type_coverage
        total_errors = metrics.mypy_error_count + metrics.ruff_error_count

        if coverage >= 98 and total_errors == 0:
            return "A+"
        elif coverage >= 95 and total_errors <= 2:
            return "A"
        elif coverage >= 90 and total_errors <= 5:
            return "B+"
        elif coverage >= 85 and total_errors <= 10:
            return "B"
        elif coverage >= 75 and total_errors <= 20:
            return "C"
        elif coverage >= 60:
            return "D"
        else:
            return "F"
    def _get_git_info(self) -> dict[str, str | None]:
        """獲取 Git 資訊
        
        Returns:
            包含 commit hash 和 branch name 的字典
        """
        import subprocess

        git_info: dict[str, str | None] = {"commit_hash": None, "branch_name": None}

        try:
            # 獲取當前 commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_info["commit_hash"] = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        try:
            # 獲取當前分支名稱
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_info["branch_name"] = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return git_info
