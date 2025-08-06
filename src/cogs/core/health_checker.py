"""
系統健康檢查模塊
- 實現系統健康檢查
- 添加模塊狀態監控
- 實現自動故障檢測
- 添加健康報告功能
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import psutil

from .logger import get_logger_manager

# 健康檢查常數
HIGH_LATENCY_THRESHOLD = 1000  # 毫秒


class HealthStatus(Enum):
    """健康狀態枚舉"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康檢查結果"""

    name: str
    status: HealthStatus
    message: str
    details: dict[str, Any]
    timestamp: datetime
    response_time_ms: float | None = None


@dataclass
class ModuleStatus:
    """模塊狀態"""

    name: str
    status: HealthStatus
    last_check: datetime
    error_count: int = 0
    warning_count: int = 0
    uptime_seconds: float = 0
    last_error: str | None = None


class HealthChecker:
    """系統健康檢查器"""

    def __init__(self, check_interval: int = 300):  # 5分鐘檢查一次
        self.check_interval = check_interval
        self.logger = get_logger_manager().get_logger("health_checker")

        # 健康檢查函數註冊表
        self.health_checks: dict[str, Callable] = {}

        # 模塊狀態追蹤
        self.module_statuses: dict[str, ModuleStatus] = {}

        # 系統指標歷史
        self.system_metrics_history: list[dict[str, Any]] = []

        # 健康檢查結果歷史
        self.health_history: list[HealthCheckResult] = []

        # 故障檢測閾值
        self.thresholds = {
            "cpu_warning": 70.0,
            "cpu_critical": 90.0,
            "memory_warning": 80.0,
            "memory_critical": 95.0,
            "disk_warning": 85.0,
            "disk_critical": 95.0,
            "response_time_warning": 1000.0,  # ms
            "response_time_critical": 5000.0,  # ms
            "error_rate_warning": 0.05,  # 5%
            "error_rate_critical": 0.15,  # 15%
        }

        # 啟動時間
        self.start_time = time.time()

        # 註冊預設健康檢查
        self._register_default_checks()

    def _register_default_checks(self):
        """註冊預設健康檢查"""
        self.register_health_check("system_resources", self._check_system_resources)
        self.register_health_check("disk_space", self._check_disk_space)
        self.register_health_check("bot_connection", self._check_bot_connection)
        self.register_health_check(
            "database_connection", self._check_database_connection
        )
        self.register_health_check("log_analysis", self._check_log_analysis)

    def register_health_check(self, name: str, check_function: Callable):
        """
        註冊健康檢查函數

        Args:
            name: 檢查名稱
            check_function: 檢查函數,應返回 HealthCheckResult
        """
        self.health_checks[name] = check_function
        self.logger.info(f"註冊健康檢查: {name}")

    def register_module(self, name: str):
        """
        註冊模塊狀態追蹤

        Args:
            name: 模塊名稱
        """
        self.module_statuses[name] = ModuleStatus(
            name=name,
            status=HealthStatus.UNKNOWN,
            last_check=datetime.utcnow(),
            uptime_seconds=time.time() - self.start_time,
        )
        self.logger.info(f"註冊模塊狀態追蹤: {name}")

    def update_module_status(
        self, name: str, status: HealthStatus, message: str | None = None
    ):
        """
        更新模塊狀態

        Args:
            name: 模塊名稱
            status: 健康狀態
            message: 狀態訊息
        """
        if name not in self.module_statuses:
            self.register_module(name)

        module = self.module_statuses[name]
        module.status = status
        module.last_check = datetime.utcnow()

        if status == HealthStatus.WARNING:
            module.warning_count += 1
        elif status in [HealthStatus.CRITICAL, HealthStatus.UNKNOWN]:
            module.error_count += 1
            if message:
                module.last_error = message

        self.logger.debug(f"模塊 {name} 狀態更新: {status.value}")

    async def _check_system_resources(self) -> HealthCheckResult:
        """檢查系統資源使用情況"""
        start_time = time.time()

        try:
            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)

            # 記憶體使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # 判斷狀態
            status = HealthStatus.HEALTHY
            messages = []

            if cpu_percent >= self.thresholds["cpu_critical"]:
                status = HealthStatus.CRITICAL
                messages.append(f"CPU 使用率過高: {cpu_percent:.1f}%")
            elif cpu_percent >= self.thresholds["cpu_warning"]:
                status = HealthStatus.WARNING
                messages.append(f"CPU 使用率較高: {cpu_percent:.1f}%")

            if memory_percent >= self.thresholds["memory_critical"]:
                status = HealthStatus.CRITICAL
                messages.append(f"記憶體使用率過高: {memory_percent:.1f}%")
            elif memory_percent >= self.thresholds["memory_warning"]:
                status = HealthStatus.WARNING
                messages.append(f"記憶體使用率較高: {memory_percent:.1f}%")

            message = "; ".join(messages) if messages else "系統資源使用正常"

            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "memory_used_gb": round(memory.used / (1024**3), 2),
            }

            response_time = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name="system_resources",
                status=status,
                message=message,
                details=details,
                timestamp=datetime.utcnow(),
                response_time_ms=response_time,
            )

        except Exception as e:
            return HealthCheckResult(
                name="system_resources",
                status=HealthStatus.CRITICAL,
                message=f"系統資源檢查失敗: {e!s}",
                details={"error": str(e)},
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def _check_disk_space(self) -> HealthCheckResult:
        """檢查磁碟空間"""
        start_time = time.time()

        try:
            disk_usage = psutil.disk_usage("/")
            disk_percent = (disk_usage.used / disk_usage.total) * 100

            status = HealthStatus.HEALTHY
            message = f"磁碟使用率: {disk_percent:.1f}%"

            if disk_percent >= self.thresholds["disk_critical"]:
                status = HealthStatus.CRITICAL
                message = f"磁碟空間嚴重不足: {disk_percent:.1f}%"
            elif disk_percent >= self.thresholds["disk_warning"]:
                status = HealthStatus.WARNING
                message = f"磁碟空間不足: {disk_percent:.1f}%"

            details = {
                "disk_percent": disk_percent,
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
            }

            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                details=details,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.CRITICAL,
                message=f"磁碟空間檢查失敗: {e!s}",
                details={"error": str(e)},
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def _check_bot_connection(self) -> HealthCheckResult:
        """檢查機器人連線狀態"""
        start_time = time.time()

        try:
            # 這裡需要從外部傳入 bot 實例,暫時使用模擬檢查
            # 實際實現中應該檢查 bot.is_ready(), bot.latency 等

            # 模擬檢查
            is_connected = True  # 應該從 bot 實例獲取
            latency_ms = 50.0  # 應該從 bot.latency 獲取

            status = HealthStatus.HEALTHY
            message = f"機器人連線正常,延遲: {latency_ms:.1f}ms"

            if not is_connected:
                status = HealthStatus.CRITICAL
                message = "機器人未連線到 Discord"
            elif latency_ms > HIGH_LATENCY_THRESHOLD:
                status = HealthStatus.WARNING
                message = f"機器人延遲較高: {latency_ms:.1f}ms"

            details = {
                "is_connected": is_connected,
                "latency_ms": latency_ms,
                "uptime_seconds": time.time() - self.start_time,
            }

            return HealthCheckResult(
                name="bot_connection",
                status=status,
                message=message,
                details=details,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return HealthCheckResult(
                name="bot_connection",
                status=HealthStatus.CRITICAL,
                message=f"機器人連線檢查失敗: {e!s}",
                details={"error": str(e)},
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def _check_database_connection(self) -> HealthCheckResult:
        """檢查資料庫連線"""
        start_time = time.time()

        try:
            # 這裡應該實際測試資料庫連線
            # 暫時使用模擬檢查

            # 模擬資料庫連線測試
            await asyncio.sleep(0.1)  # 模擬連線時間

            status = HealthStatus.HEALTHY
            message = "資料庫連線正常"

            details = {
                "connection_pool_size": 5,  # 應該從實際連線池獲取
                "active_connections": 2,  # 應該從實際連線池獲取
                "response_time_ms": (time.time() - start_time) * 1000,
            }

            return HealthCheckResult(
                name="database_connection",
                status=status,
                message=message,
                details=details,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return HealthCheckResult(
                name="database_connection",
                status=HealthStatus.CRITICAL,
                message=f"資料庫連線檢查失敗: {e!s}",
                details={"error": str(e)},
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def _check_log_analysis(self) -> HealthCheckResult:
        """檢查日誌分析結果"""
        start_time = time.time()

        try:
            logger_manager = get_logger_manager()
            health_report = logger_manager.analyze_logs(hours=1)

            status = HealthStatus.HEALTHY
            message = "日誌分析正常"

            # 檢查是否有問題
            if health_report.get("overall_status") == "warning":
                status = HealthStatus.WARNING
                message = (
                    f"日誌中發現問題: {len(health_report.get('issues', []))} 個問題"
                )

            total_errors = sum(
                analysis.get("error_count", 0)
                for analysis in health_report.get("log_files", {}).values()
                if isinstance(analysis, dict)
            )

            details = {
                "total_errors_last_hour": total_errors,
                "log_files_analyzed": len(health_report.get("log_files", {})),
                "issues_found": len(health_report.get("issues", [])),
                "overall_log_status": health_report.get("overall_status", "unknown"),
            }

            return HealthCheckResult(
                name="log_analysis",
                status=status,
                message=message,
                details=details,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return HealthCheckResult(
                name="log_analysis",
                status=HealthStatus.WARNING,
                message=f"日誌分析檢查失敗: {e!s}",
                details={"error": str(e)},
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def run_all_checks(self) -> list[HealthCheckResult]:
        """執行所有健康檢查"""
        results = []

        for name, check_function in self.health_checks.items():
            try:
                self.logger.debug(f"執行健康檢查: {name}")
                result = await check_function()
                results.append(result)

                # 記錄到歷史
                self.health_history.append(result)

                # 保持歷史記錄在合理範圍內
                MAX_HISTORY_SIZE = 1000
                TRIM_TO_SIZE = 500
                if len(self.health_history) > MAX_HISTORY_SIZE:
                    self.health_history = self.health_history[-TRIM_TO_SIZE:]

            except Exception as e:
                self.logger.error(f"健康檢查 {name} 執行失敗: {e}")
                error_result = HealthCheckResult(
                    name=name,
                    status=HealthStatus.CRITICAL,
                    message=f"檢查執行失敗: {e!s}",
                    details={"error": str(e)},
                    timestamp=datetime.utcnow(),
                )
                results.append(error_result)

        return results

    def get_overall_status(self, results: list[HealthCheckResult]) -> HealthStatus:
        """根據檢查結果計算整體狀態"""
        if not results:
            return HealthStatus.UNKNOWN

        statuses = [result.status for result in results]

        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses or HealthStatus.UNKNOWN in statuses:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY

    def generate_health_report(
        self, results: list[HealthCheckResult]
    ) -> dict[str, Any]:
        """生成健康報告"""
        overall_status = self.get_overall_status(results)

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": overall_status.value,
            "uptime_seconds": time.time() - self.start_time,
            "checks": {},
            "modules": {},
            "summary": {
                "total_checks": len(results),
                "healthy": 0,
                "warning": 0,
                "critical": 0,
                "unknown": 0,
            },
            "recommendations": [],
        }

        # 處理檢查結果
        for result in results:
            report["checks"][result.name] = {
                "status": result.status.value,
                "message": result.message,
                "details": result.details,
                "response_time_ms": result.response_time_ms,
                "timestamp": result.timestamp.isoformat(),
            }

            # 統計狀態
            report["summary"][result.status.value] += 1

        # 處理模塊狀態
        for name, module in self.module_statuses.items():
            report["modules"][name] = {
                "status": module.status.value,
                "last_check": module.last_check.isoformat(),
                "error_count": module.error_count,
                "warning_count": module.warning_count,
                "uptime_seconds": module.uptime_seconds,
                "last_error": module.last_error,
            }

        # 生成建議
        report["recommendations"] = self._generate_recommendations(results)

        return report

    def _generate_recommendations(self, results: list[HealthCheckResult]) -> list[str]:
        """根據檢查結果生成建議"""
        recommendations = []

        for result in results:
            if result.status == HealthStatus.CRITICAL:
                if result.name == "system_resources":
                    if "CPU" in result.message:
                        recommendations.append(
                            "檢查 CPU 使用率過高的進程,考慮優化或重啟"
                        )
                    if "記憶體" in result.message:
                        recommendations.append("檢查記憶體使用情況,可能存在記憶體洩漏")
                elif result.name == "disk_space":
                    recommendations.append("清理磁碟空間,刪除不必要的文件")
                elif result.name == "bot_connection":
                    recommendations.append("檢查網路連線,考慮重啟機器人")
                elif result.name == "database_connection":
                    recommendations.append("檢查資料庫服務狀態,確認連線配置")

            elif result.status == HealthStatus.WARNING:
                if result.name == "system_resources":
                    recommendations.append("監控系統資源使用情況,考慮優化性能")
                elif result.name == "log_analysis":
                    recommendations.append("檢查日誌中的錯誤和警告訊息")

        # 如果沒有具體建議,提供通用建議
        if not recommendations:
            if any(
                r.status in [HealthStatus.CRITICAL, HealthStatus.WARNING]
                for r in results
            ):
                recommendations.append("系統存在一些問題,建議檢查詳細報告")
            else:
                recommendations.append("系統運行正常,無特殊建議")

        return recommendations

    async def start_monitoring(self):
        """啟動健康監控"""
        self.logger.info("啟動健康監控系統")

        while True:
            try:
                # 執行健康檢查
                results = await self.run_all_checks()

                # 生成報告
                report = self.generate_health_report(results)

                # 記錄整體狀態
                overall_status = HealthStatus(report["overall_status"])
                if overall_status == HealthStatus.CRITICAL:
                    self.logger.critical(f"系統健康檢查: {overall_status.value}")
                elif overall_status == HealthStatus.WARNING:
                    self.logger.warning(f"系統健康檢查: {overall_status.value}")
                else:
                    self.logger.info(f"系統健康檢查: {overall_status.value}")

                # 等待下次檢查
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                self.logger.error(f"健康監控執行失敗: {e}")
                await asyncio.sleep(60)  # 錯誤時縮短等待時間

    def get_health_summary(self) -> dict[str, Any]:
        """獲取健康狀態摘要"""
        if not self.health_history:
            return {"error": "沒有健康檢查歷史"}

        recent_results = [
            r
            for r in self.health_history
            if r.timestamp > datetime.utcnow() - timedelta(hours=1)
        ]

        if not recent_results:
            return {"error": "最近一小時沒有健康檢查數據"}

        latest_report = self.generate_health_report(
            recent_results[-10:]
        )  # 最近10次檢查

        return {
            "latest_status": latest_report["overall_status"],
            "uptime_hours": round((time.time() - self.start_time) / 3600, 2),
            "total_checks_last_hour": len(recent_results),
            "recent_summary": latest_report["summary"],
            "active_modules": len(self.module_statuses),
            "last_check": recent_results[-1].timestamp.isoformat()
            if recent_results
            else None,
        }


class HealthCheckerManager:
    """健康檢查器管理器"""

    def __init__(self):
        self._health_checker: HealthChecker | None = None

    def get_health_checker(self) -> HealthChecker:
        """獲取健康檢查器實例"""
        if self._health_checker is None:
            self._health_checker = HealthChecker()
        return self._health_checker


# 全域管理器實例
_health_checker_manager = HealthCheckerManager()


def get_health_checker() -> HealthChecker:
    """
    獲取全域健康檢查器實例

    Returns:
        HealthChecker: 健康檢查器實例
    """
    return _health_checker_manager.get_health_checker()


async def start_health_monitoring():
    """啟動健康監控的便捷函數"""
    checker = get_health_checker()
    await checker.start_monitoring()
