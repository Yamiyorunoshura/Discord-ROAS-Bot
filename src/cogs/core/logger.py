"""
統一日誌記錄機制
- 提供標準化的日誌記錄器
- 支援日誌輪轉和清理
- 統一的日誌格式
- 性能監控和分析工具
- 健康檢查和報告
"""

import asyncio
import logging
import logging.handlers
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil

# 常數定義
MAX_PERFORMANCE_ISSUES = 5
DEFAULT_LOG_ANALYSIS_HOURS = 24
HIGH_CPU_THRESHOLD = 80
CRITICAL_MEMORY_THRESHOLD = 90
HIGH_CPU_RECOMMENDATION_THRESHOLD = 70
HIGH_MEMORY_RECOMMENDATION_THRESHOLD = 80
SLOW_RESPONSE_TIME_THRESHOLD = 1000


@dataclass
class PerformanceMetrics:
    """性能指標數據類"""

    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_usage_mb: float
    response_time_ms: float | None = None
    active_connections: int | None = None
    error_rate: float | None = None

class PerformanceMonitor:
    """性能監控器"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.response_times: deque = deque(maxlen=100)  # 最近100次響應時間
        self.start_time = time.time()

    def record_metrics(
        self,
        response_time_ms: float | None = None,
        active_connections: int | None = None,
        error_rate: float | None = None,
    ):
        """記錄性能指標"""
        try:
            # 獲取系統資源使用情況
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_usage_mb = memory.used / (1024 * 1024)

            # 記錄響應時間
            if response_time_ms is not None:
                self.response_times.append(response_time_ms)

            # 創建性能指標
            metrics = PerformanceMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_usage_mb=memory_usage_mb,
                response_time_ms=response_time_ms,
                active_connections=active_connections,
                error_rate=error_rate,
            )

            self.metrics_history.append(metrics)

        except Exception:
            # 性能監控不應該影響主要功能
            pass

    def get_average_response_time(self) -> float:
        """獲取平均響應時間"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    def get_uptime_seconds(self) -> float:
        """獲取運行時間(秒)"""
        return time.time() - self.start_time

    def get_performance_summary(self) -> dict[str, Any]:
        """獲取性能摘要"""
        if not self.metrics_history:
            return {"error": "沒有性能數據"}

        recent_metrics = list(self.metrics_history)[-10:]  # 最近10條記錄

        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory_mb = sum(m.memory_usage_mb for m in recent_metrics) / len(
            recent_metrics
        )

        return {
            "uptime_seconds": self.get_uptime_seconds(),
            "average_cpu_percent": round(avg_cpu, 2),
            "average_memory_percent": round(avg_memory, 2),
            "average_memory_usage_mb": round(avg_memory_mb, 2),
            "average_response_time_ms": round(self.get_average_response_time(), 2),
            "total_metrics_recorded": len(self.metrics_history),
            "latest_timestamp": recent_metrics[-1].timestamp.isoformat()
            if recent_metrics
            else None,
        }

class LogAnalyzer:
    """日誌分析器"""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.error_patterns = {
            "database": ["database", "connection", "timeout", "lock"],
            "network": ["network", "http", "connection", "timeout"],
            "permission": ["permission", "forbidden", "unauthorized"],
            "memory": ["memory", "outofmemory", "allocation"],
            "discord": ["discord", "gateway", "ratelimit"],
        }

    def analyze_log_file(self, filename: str, hours: int = 24) -> dict[str, Any]:
        """分析指定日誌文件"""
        log_path = self.logs_dir / filename
        if not log_path.exists():
            return {"error": f"日誌文件 {filename} 不存在"}

        datetime.utcnow() - timedelta(hours=hours)

        analysis = {
            "total_lines": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "error_categories": defaultdict(int),
            "recent_errors": [],
            "performance_issues": [],
        }

        try:
            with log_path.open(encoding="utf-8") as f:
                for line in f:
                    analysis["total_lines"] += 1

                    # 解析日誌等級
                    if "ERROR" in line:
                        analysis["error_count"] += 1
                        self._categorize_error(line, analysis["error_categories"])

                        # 收集最近的錯誤
                        MAX_RECENT_ERRORS = 10
                        if len(analysis["recent_errors"]) < MAX_RECENT_ERRORS:
                            analysis["recent_errors"].append(line.strip())

                    elif "WARNING" in line:
                        analysis["warning_count"] += 1
                    elif "INFO" in line:
                        analysis["info_count"] += 1

                    # 檢測性能問題
                    if (
                        any(
                            keyword in line.lower()
                            for keyword in ["slow", "timeout", "memory", "cpu"]
                        )
                        and len(analysis["performance_issues"]) < MAX_PERFORMANCE_ISSUES
                    ):
                        analysis["performance_issues"].append(line.strip())

        except Exception as e:
            analysis["error"] = f"分析失敗: {e!s}"

        return analysis

    def _categorize_error(self, log_line: str, categories: dict[str, int]):
        """將錯誤分類"""
        line_lower = log_line.lower()

        for category, keywords in self.error_patterns.items():
            if any(keyword in line_lower for keyword in keywords):
                categories[category] += 1
                return

        categories["other"] += 1

    def generate_health_report(self) -> dict[str, Any]:
        """生成健康檢查報告"""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "log_files": {},
            "overall_status": "healthy",
            "issues": [],
            "recommendations": [],
        }

        # 分析所有日誌文件
        for log_file in self.logs_dir.glob("*.log"):
            analysis = self.analyze_log_file(log_file.name, hours=1)
            report["log_files"][log_file.name] = analysis

            # 檢查健康狀況
            ERROR_THRESHOLD = 10
            if analysis.get("error_count", 0) > ERROR_THRESHOLD:  # 1小時內超過10個錯誤
                report["overall_status"] = "warning"
                report["issues"].append(
                    f"{log_file.name}: 錯誤率過高 ({analysis['error_count']} 錯誤/小時)"
                )

            if analysis.get("performance_issues"):
                report["overall_status"] = "warning"
                report["issues"].append(f"{log_file.name}: 檢測到性能問題")

        # 生成建議
        if report["overall_status"] == "warning":
            report["recommendations"].extend(
                ["檢查錯誤日誌中的具體問題", "監控系統資源使用情況", "考慮重啟相關服務"]
            )

        return report

class DiscordBotLogger:
    """Discord 機器人日誌管理器"""

    # 日誌格式
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
    SIMPLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # 日誌配置
    DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5MB
    DEFAULT_BACKUP_COUNT = 3
    DEFAULT_LEVEL = logging.INFO

    def __init__(self, logs_dir: str = "logs"):
        """
        初始化日誌管理器

        Args:
            logs_dir: 日誌目錄路徑
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

        # 已創建的日誌記錄器緩存
        self._loggers: dict[str, logging.Logger] = {}

        # 性能監控器
        self.performance_monitor = PerformanceMonitor()

        # 日誌分析器
        self.log_analyzer = LogAnalyzer(self.logs_dir)

        # 設置根日誌記錄器
        self._setup_root_logger()

        # 啟動性能監控任務
        self._start_performance_monitoring()

    def _setup_root_logger(self):
        """設置根日誌記錄器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.DEFAULT_LEVEL)

        # 避免重複添加處理器
        if not root_logger.handlers:
            # 控制台處理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(self._get_formatter(simple=True))
            root_logger.addHandler(console_handler)

    def _get_formatter(self, simple: bool = False) -> logging.Formatter:
        """
        獲取日誌格式器

        Args:
            simple: 是否使用簡化格式

        Returns:
            logging.Formatter: 日誌格式器
        """
        format_string = self.SIMPLE_FORMAT if simple else self.LOG_FORMAT
        return logging.Formatter(fmt=format_string, datefmt=self.DATE_FORMAT)

    def _create_file_handler(
        self,
        filename: str,
        max_bytes: int | None = None,
        backup_count: int | None = None,
        detailed: bool = True,
    ) -> logging.handlers.RotatingFileHandler:
        """
        創建文件處理器

        Args:
            filename: 日誌文件名
            max_bytes: 最大文件大小
            backup_count: 備份文件數量
            detailed: 是否使用詳細格式

        Returns:
            logging.handlers.RotatingFileHandler: 文件處理器
        """
        file_path = self.logs_dir / filename

        handler = logging.handlers.RotatingFileHandler(
            file_path,
            encoding="utf-8",
            maxBytes=max_bytes or self.DEFAULT_MAX_BYTES,
            backupCount=backup_count or self.DEFAULT_BACKUP_COUNT,
        )

        handler.setFormatter(self._get_formatter(simple=not detailed))
        return handler

    def _start_performance_monitoring(self):
        """啟動性能監控"""

        async def monitor_loop():
            while True:
                try:
                    self.performance_monitor.record_metrics()
                    await asyncio.sleep(60)  # 每分鐘記錄一次
                except Exception:
                    await asyncio.sleep(60)

        # 在事件循環中啟動監控任務
        try:
            loop = (
                asyncio.get_running_loop()
                if asyncio.get_event_loop_policy().get_event_loop().is_running()
                else asyncio.new_event_loop()
            )
            loop.create_task(monitor_loop())
        except RuntimeError:
            # 如果沒有事件循環,跳過性能監控
            pass

    def get_logger(
        self,
        name: str,
        filename: str | None = None,
        level: int | None = None,
        max_bytes: int | None = None,
        backup_count: int | None = None,
        detailed: bool = True,
    ) -> logging.Logger:
        """
        獲取或創建日誌記錄器

        Args:
            name: 日誌記錄器名稱
            filename: 日誌文件名(如果為 None,則使用 name.log)
            level: 日誌等級
            max_bytes: 最大文件大小
            backup_count: 備份文件數量
            detailed: 是否使用詳細格式

        Returns:
            logging.Logger: 日誌記錄器
        """
        # 如果已存在,直接返回
        if name in self._loggers:
            return self._loggers[name]

        # 創建新的日誌記錄器
        logger = logging.getLogger(name)
        logger.setLevel(level or self.DEFAULT_LEVEL)

        # 避免重複添加處理器
        if not logger.handlers:
            # 文件處理器
            if filename is None:
                filename = f"{name}.log"

            file_handler = self._create_file_handler(
                filename, max_bytes, backup_count, detailed
            )
            logger.addHandler(file_handler)

        # 緩存日誌記錄器
        self._loggers[name] = logger
        return logger

    def create_module_logger(self, module_name: str, **kwargs) -> logging.Logger:
        """
        為模塊創建專用日誌記錄器

        Args:
            module_name: 模塊名稱
            **kwargs: 其他參數

        Returns:
            logging.Logger: 模塊日誌記錄器
        """
        return self.get_logger(module_name, **kwargs)

    def log_startup(
        self, module_name: str, message: str, duration_ms: float | None = None
    ):
        """
        記錄模塊啟動信息

        Args:
            module_name: 模塊名稱
            message: 啟動信息
            duration_ms: 啟動耗時(毫秒)
        """
        logger = self.get_logger(module_name)
        if duration_ms is not None:
            logger.info(f"🚀 {message} (耗時: {duration_ms:.2f}ms)")
            self.performance_monitor.record_metrics(response_time_ms=duration_ms)
        else:
            logger.info(f"🚀 {message}")

    def log_shutdown(self, module_name: str, message: str):
        """
        記錄模塊關閉信息

        Args:
            module_name: 模塊名稱
            message: 關閉信息
        """
        logger = self.get_logger(module_name)
        logger.info(f"🛑 {message}")

    def log_error(
        self,
        module_name: str,
        error: Exception,
        context: str = "",
        tracking_id: str | None = None,
    ):
        """
        記錄錯誤信息

        Args:
            module_name: 模塊名稱
            error: 錯誤對象
            context: 上下文信息
            tracking_id: 追蹤碼
        """
        logger = self.get_logger(module_name)

        error_msg = f"❌ {context}: {error}" if context else f"❌ {error}"
        if tracking_id:
            error_msg += f" (追蹤碼: {tracking_id})"

        logger.error(error_msg, exc_info=True)

    def log_warning(self, module_name: str, message: str):
        """
        記錄警告信息

        Args:
            module_name: 模塊名稱
            message: 警告信息
        """
        logger = self.get_logger(module_name)
        logger.warning(f"⚠️ {message}")

    def log_debug(self, module_name: str, message: str):
        """
        記錄調試信息

        Args:
            module_name: 模塊名稱
            message: 調試信息
        """
        logger = self.get_logger(module_name)
        logger.debug(f"🔍 {message}")

    def log_performance(
        self,
        module_name: str,
        operation: str,
        duration_ms: float,
        additional_metrics: dict[str, Any | None] | None = None,
    ):
        """
        記錄性能信息

        Args:
            module_name: 模塊名稱
            operation: 操作名稱
            duration_ms: 耗時(毫秒)
            additional_metrics: 額外指標
        """
        logger = self.get_logger(module_name)

        perf_msg = f"⏱️ {operation} 耗時: {duration_ms:.2f}ms"
        if additional_metrics:
            perf_msg += f" | 額外指標: {additional_metrics}"

        # 根據耗時判斷日誌等級
        WARNING_THRESHOLD = 5000  # 5秒
        INFO_THRESHOLD = 1000     # 1秒
        if duration_ms > WARNING_THRESHOLD:
            logger.warning(perf_msg)
        elif duration_ms > INFO_THRESHOLD:
            logger.info(perf_msg)
        else:
            logger.debug(perf_msg)

        # 記錄到性能監控
        self.performance_monitor.record_metrics(response_time_ms=duration_ms)

    def cleanup_old_logs(self, days: int = 7):
        """
        清理舊日誌文件

        Args:
            days: 保留天數
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        cleaned_count = 0

        for log_file in self.logs_dir.glob("*.log.*"):  # 備份日誌文件
            try:
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_date:
                    log_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                self.log_error("logger", e, f"清理日誌文件 {log_file} 失敗")

        if cleaned_count > 0:
            self.log_startup("logger", f"清理了 {cleaned_count} 個舊日誌文件")

    def get_log_stats(self) -> dict[str, Any]:
        """
        獲取日誌統計信息

        Returns:
            Dict[str, Any]: 日誌統計信息
        """
        stats = {
            "logs_directory": str(self.logs_dir),
            "active_loggers": len(self._loggers),
            "logger_names": list(self._loggers.keys()),
            "log_files": [],
            "total_size_mb": 0,
            "performance_summary": self.performance_monitor.get_performance_summary(),
        }

        # 統計日誌文件
        for log_file in self.logs_dir.glob("*.log*"):
            try:
                file_size = log_file.stat().st_size
                stats["log_files"].append(
                    {
                        "name": log_file.name,
                        "size_mb": round(file_size / (1024 * 1024), 2),
                        "modified": datetime.fromtimestamp(
                            log_file.stat().st_mtime
                        ).isoformat(),
                    }
                )
                stats["total_size_mb"] += file_size / (1024 * 1024)
            except Exception:
                pass

        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        return stats

    def analyze_logs(self, hours: int = DEFAULT_LOG_ANALYSIS_HOURS) -> dict[str, Any]:  # noqa: ARG002
        """
        分析日誌內容

        Args:
            hours: 分析最近多少小時的日誌

        Returns:
            Dict[str, Any]: 分析結果
        """
        # TODO: 未來可能會用到 hours 參數來限制分析時間範圍
        return self.log_analyzer.generate_health_report()

    def get_health_status(self) -> dict[str, Any]:
        """
        獲取系統健康狀態

        Returns:
            Dict[str, Any]: 健康狀態報告
        """
        health_report = self.log_analyzer.generate_health_report()
        performance_summary = self.performance_monitor.get_performance_summary()

        # 整合健康狀態
        overall_status = "healthy"

        if health_report.get("overall_status") == "warning":
            overall_status = "warning"

        # 檢查性能指標
        if performance_summary.get("average_cpu_percent", 0) > HIGH_CPU_THRESHOLD:
            overall_status = "warning"

        if performance_summary.get("average_memory_percent", 0) > CRITICAL_MEMORY_THRESHOLD:
            overall_status = "critical"

        return {
            "overall_status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "log_analysis": health_report,
            "performance": performance_summary,
            "recommendations": self._generate_recommendations(
                health_report, performance_summary
            ),
        }

    def _generate_recommendations(
        self, log_analysis: dict[str, Any], performance: dict[str, Any]
    ) -> list[str]:
        """生成系統建議"""
        recommendations = []

        if performance.get("average_cpu_percent", 0) > HIGH_CPU_RECOMMENDATION_THRESHOLD:
            recommendations.append("CPU 使用率較高,建議檢查是否有性能瓶頸")

        if performance.get("average_memory_percent", 0) > HIGH_MEMORY_RECOMMENDATION_THRESHOLD:
            recommendations.append("記憶體使用率較高,建議檢查記憶體洩漏")

        if performance.get("average_response_time_ms", 0) > SLOW_RESPONSE_TIME_THRESHOLD:
            recommendations.append("響應時間較慢,建議優化處理邏輯")

        if log_analysis.get("issues"):
            recommendations.append("檢測到日誌異常,請查看詳細錯誤信息")

        if not recommendations:
            recommendations.append("系統運行正常,無特殊建議")

        return recommendations

class LoggerManager:
    """日誌管理器管理器"""

    def __init__(self):
        self._logger_manager: DiscordBotLogger | None = None

    def get_logger_manager(self) -> DiscordBotLogger:
        """獲取日誌管理器實例"""
        if self._logger_manager is None:
            self._logger_manager = DiscordBotLogger()
        return self._logger_manager

# 全域管理器實例
_logger_manager_instance = LoggerManager()

def get_logger_manager() -> DiscordBotLogger:
    """
    獲取全域日誌管理器實例

    Returns:
        DiscordBotLogger: 日誌管理器實例
    """
    return _logger_manager_instance.get_logger_manager()

def setup_module_logger(module_name: str, **kwargs) -> logging.Logger:
    """
    為模塊設置日誌記錄器的便捷函數

    Args:
        module_name: 模塊名稱
        **kwargs: 其他參數

    Returns:
        logging.Logger: 日誌記錄器
    """
    manager = get_logger_manager()
    return manager.create_module_logger(module_name, **kwargs)
