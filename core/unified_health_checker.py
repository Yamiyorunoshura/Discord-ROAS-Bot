#!/usr/bin/env python3
"""
統一健康檢查系統 - 整合各服務的健康檢查機制
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組實現了統一的健康檢查系統，整合Discord Bot、Redis、Prometheus、Grafana等
所有服務的健康檢查，提供端到端的健康狀態監控和診斷功能。
"""

import asyncio
import aiohttp
import aioredis
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from contextlib import asynccontextmanager
import socket
import subprocess

from .api_contracts import HealthCheckResponse, create_standard_health_response
from .monitoring_collector import HealthStatus
from .error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class HealthCheckType(Enum):
    """健康檢查類型"""
    HTTP = "http"
    REDIS = "redis"
    TCP = "tcp"
    COMMAND = "command"
    CUSTOM = "custom"


class HealthGrade(Enum):
    """健康等級"""
    EXCELLENT = "excellent"     # 100% 健康
    GOOD = "good"              # 80-99% 健康
    WARNING = "warning"         # 60-79% 健康
    CRITICAL = "critical"       # 40-59% 健康
    FAILING = "failing"         # <40% 健康


@dataclass
class HealthCheckConfig:
    """健康檢查配置"""
    service_name: str
    check_type: HealthCheckType
    endpoint: str
    timeout: int = 10
    interval: int = 30
    retries: int = 3
    expected_response: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    custom_checker: Optional[Callable] = None


@dataclass
class HealthCheckResult:
    """健康檢查結果"""
    service_name: str
    status: HealthStatus
    response_time_ms: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    consecutive_failures: int = 0


@dataclass
class SystemHealthReport:
    """系統健康報告"""
    timestamp: datetime
    overall_status: HealthStatus
    overall_grade: HealthGrade
    health_score: float  # 0-100
    service_results: Dict[str, HealthCheckResult]
    critical_issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    uptime_seconds: float
    response_time_stats: Dict[str, float]


class UnifiedHealthChecker:
    """
    統一健康檢查系統
    
    功能：
    - 統一管理所有服務的健康檢查
    - 提供多種檢查類型（HTTP、Redis、TCP等）
    - 智能故障檢測和診斷
    - 生成綜合健康報告
    - 支持自訂檢查邏輯
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 錯誤處理器
        self.error_handler = ErrorHandler(self.project_root)
        
        # 健康檢查配置
        self.health_configs = self._define_health_checks()
        
        # 健康狀態追蹤
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.failure_counts: Dict[str, int] = {}
        self.last_check_times: Dict[str, datetime] = {}
        
        # 系統啟動時間
        self.system_start_time = time.time()
        
        # HTTP會話
        self.http_session: Optional[aiohttp.ClientSession] = None
    
    def _define_health_checks(self) -> List[HealthCheckConfig]:
        """定義健康檢查配置"""
        configs = []
        
        # Discord Bot HTTP健康檢查
        configs.append(HealthCheckConfig(
            service_name="discord-bot",
            check_type=HealthCheckType.HTTP,
            endpoint="http://localhost:8000/health",
            timeout=10,
            interval=30,
            retries=3,
            headers={"Accept": "application/json"}
        ))
        
        # Redis健康檢查
        configs.append(HealthCheckConfig(
            service_name="redis",
            check_type=HealthCheckType.REDIS,
            endpoint="redis://localhost:6379",
            timeout=5,
            interval=15,
            retries=3
        ))
        
        # Prometheus健康檢查
        configs.append(HealthCheckConfig(
            service_name="prometheus",
            check_type=HealthCheckType.HTTP,
            endpoint="http://localhost:9090/-/healthy",
            timeout=10,
            interval=30,
            retries=3
        ))
        
        # Grafana健康檢查
        configs.append(HealthCheckConfig(
            service_name="grafana",
            check_type=HealthCheckType.HTTP,
            endpoint="http://localhost:3000/api/health",
            timeout=10,
            interval=30,
            retries=3,
            headers={"Accept": "application/json"}
        ))
        
        # Docker服務檢查
        configs.append(HealthCheckConfig(
            service_name="docker",
            check_type=HealthCheckType.COMMAND,
            endpoint="docker info",
            timeout=15,
            interval=60,
            retries=2
        ))
        
        return configs
    
    async def __aenter__(self):
        """異步上下文管理器進入"""
        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器退出"""
        if self.http_session:
            await self.http_session.close()
    
    async def check_all_services(self) -> SystemHealthReport:
        """
        檢查所有服務健康狀態
        
        Returns:
            SystemHealthReport: 系統健康報告
        """
        self.logger.info("🏥 開始統一健康檢查")
        
        async with self:
            # 並行執行所有健康檢查
            check_tasks = []
            for config in self.health_configs:
                task = asyncio.create_task(self._perform_health_check(config))
                check_tasks.append(task)
            
            # 等待所有檢查完成
            results = await asyncio.gather(*check_tasks, return_exceptions=True)
            
            # 處理結果
            service_results = {}
            for i, result in enumerate(results):
                config = self.health_configs[i]
                if isinstance(result, HealthCheckResult):
                    service_results[config.service_name] = result
                    self._update_health_history(config.service_name, result)
                else:
                    # 處理異常
                    self.logger.error(f"健康檢查異常 {config.service_name}: {result}")
                    error_result = HealthCheckResult(
                        service_name=config.service_name,
                        status=HealthStatus.UNKNOWN,
                        response_time_ms=0,
                        timestamp=datetime.now(),
                        error_message=str(result)
                    )
                    service_results[config.service_name] = error_result
        
        # 生成系統健康報告
        report = self._generate_health_report(service_results)
        
        self.logger.info(f"健康檢查完成: {report.overall_status.value} (分數: {report.health_score:.1f})")
        return report
    
    async def check_service(self, service_name: str) -> Optional[HealthCheckResult]:
        """
        檢查特定服務健康狀態
        
        Args:
            service_name: 服務名稱
            
        Returns:
            Optional[HealthCheckResult]: 健康檢查結果
        """
        # 找到對應的配置
        config = None
        for c in self.health_configs:
            if c.service_name == service_name:
                config = c
                break
        
        if not config:
            self.logger.warning(f"未找到服務 {service_name} 的健康檢查配置")
            return None
        
        async with self:
            return await self._perform_health_check(config)
    
    async def _perform_health_check(self, config: HealthCheckConfig) -> HealthCheckResult:
        """執行健康檢查"""
        start_time = time.time()
        attempts = 0
        last_error = None
        
        while attempts < config.retries:
            attempts += 1
            
            try:
                if config.check_type == HealthCheckType.HTTP:
                    result = await self._check_http_health(config)
                elif config.check_type == HealthCheckType.REDIS:
                    result = await self._check_redis_health(config)
                elif config.check_type == HealthCheckType.TCP:
                    result = await self._check_tcp_health(config)
                elif config.check_type == HealthCheckType.COMMAND:
                    result = await self._check_command_health(config)
                elif config.check_type == HealthCheckType.CUSTOM:
                    result = await self._check_custom_health(config)
                else:
                    raise ValueError(f"不支援的健康檢查類型: {config.check_type}")
                
                # 檢查成功
                response_time = (time.time() - start_time) * 1000
                result.response_time_ms = response_time
                result.timestamp = datetime.now()
                
                # 重置失敗計數
                self.failure_counts[config.service_name] = 0
                
                return result
                
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"服務 {config.service_name} 健康檢查失敗 (嘗試 {attempts}/{config.retries}): {str(e)}")
                
                if attempts < config.retries:
                    await asyncio.sleep(1)  # 重試前等待
        
        # 所有嘗試都失敗
        response_time = (time.time() - start_time) * 1000
        consecutive_failures = self.failure_counts.get(config.service_name, 0) + 1
        self.failure_counts[config.service_name] = consecutive_failures
        
        return HealthCheckResult(
            service_name=config.service_name,
            status=HealthStatus.UNHEALTHY,
            response_time_ms=response_time,
            timestamp=datetime.now(),
            error_message=last_error,
            consecutive_failures=consecutive_failures
        )
    
    async def _check_http_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """HTTP健康檢查"""
        if not self.http_session:
            raise RuntimeError("HTTP會話未初始化")
        
        async with self.http_session.get(
            config.endpoint,
            headers=config.headers,
            timeout=aiohttp.ClientTimeout(total=config.timeout)
        ) as response:
            
            status = HealthStatus.HEALTHY if response.status == 200 else HealthStatus.UNHEALTHY
            
            # 嘗試解析JSON回應
            details = {}
            try:
                if response.content_type == 'application/json':
                    response_data = await response.json()
                    details['response_data'] = response_data
                else:
                    response_text = await response.text()
                    details['response_text'] = response_text[:200]  # 限制長度
            except Exception:
                pass
            
            details['status_code'] = response.status
            details['content_type'] = response.content_type
            
            return HealthCheckResult(
                service_name=config.service_name,
                status=status,
                response_time_ms=0,  # 將在外層設置
                timestamp=datetime.now(),
                details=details
            )
    
    async def _check_redis_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Redis健康檢查"""
        try:
            # 解析Redis URL
            import urllib.parse
            parsed = urllib.parse.urlparse(config.endpoint)
            host = parsed.hostname or 'localhost'
            port = parsed.port or 6379
            
            # 連接Redis
            redis = aioredis.from_url(config.endpoint, decode_responses=True)
            
            # 執行PING命令
            pong = await redis.ping()
            
            # 獲取Redis資訊
            info = await redis.info()
            
            await redis.close()
            
            details = {
                'ping_response': pong,
                'version': info.get('redis_version'),
                'uptime_seconds': info.get('uptime_in_seconds'),
                'connected_clients': info.get('connected_clients'),
                'used_memory': info.get('used_memory_human'),
                'role': info.get('role')
            }
            
            status = HealthStatus.HEALTHY if pong == 'PONG' else HealthStatus.UNHEALTHY
            
            return HealthCheckResult(
                service_name=config.service_name,
                status=status,
                response_time_ms=0,
                timestamp=datetime.now(),
                details=details
            )
            
        except Exception as e:
            raise Exception(f"Redis健康檢查失敗: {str(e)}")
    
    async def _check_tcp_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """TCP端口健康檢查"""
        # 解析endpoint
        if '://' in config.endpoint:
            import urllib.parse
            parsed = urllib.parse.urlparse(config.endpoint)
            host = parsed.hostname or 'localhost'
            port = parsed.port
        else:
            # 假設格式為 host:port
            parts = config.endpoint.split(':')
            host = parts[0] if len(parts) > 1 else 'localhost'
            port = int(parts[1]) if len(parts) > 1 else int(parts[0])
        
        if not port:
            raise ValueError(f"無法解析端口: {config.endpoint}")
        
        # TCP連接測試
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=config.timeout
            )
            writer.close()
            await writer.wait_closed()
            
            return HealthCheckResult(
                service_name=config.service_name,
                status=HealthStatus.HEALTHY,
                response_time_ms=0,
                timestamp=datetime.now(),
                details={'host': host, 'port': port, 'connection': 'successful'}
            )
            
        except Exception as e:
            raise Exception(f"TCP連接失敗: {host}:{port} - {str(e)}")
    
    async def _check_command_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """命令執行健康檢查"""
        try:
            process = await asyncio.create_subprocess_shell(
                config.endpoint,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=config.timeout
            )
            
            success = process.returncode == 0
            status = HealthStatus.HEALTHY if success else HealthStatus.UNHEALTHY
            
            details = {
                'return_code': process.returncode,
                'stdout': stdout.decode()[:500],  # 限制輸出長度
                'stderr': stderr.decode()[:500] if stderr else None
            }
            
            return HealthCheckResult(
                service_name=config.service_name,
                status=status,
                response_time_ms=0,
                timestamp=datetime.now(),
                details=details,
                error_message=stderr.decode() if stderr and not success else None
            )
            
        except asyncio.TimeoutError:
            raise Exception(f"命令執行超時: {config.endpoint}")
        except Exception as e:
            raise Exception(f"命令執行失敗: {str(e)}")
    
    async def _check_custom_health(self, config: HealthCheckConfig) -> HealthCheckResult:
        """自訂健康檢查"""
        if not config.custom_checker:
            raise ValueError("自訂健康檢查需要提供custom_checker函數")
        
        try:
            result = await config.custom_checker(config)
            if not isinstance(result, HealthCheckResult):
                raise ValueError("custom_checker必須返回HealthCheckResult")
            return result
        except Exception as e:
            raise Exception(f"自訂健康檢查失敗: {str(e)}")
    
    def _update_health_history(self, service_name: str, result: HealthCheckResult) -> None:
        """更新健康檢查歷史"""
        if service_name not in self.health_history:
            self.health_history[service_name] = []
        
        history = self.health_history[service_name]
        history.append(result)
        
        # 保留最近100次記錄
        if len(history) > 100:
            history.pop(0)
        
        self.last_check_times[service_name] = result.timestamp
    
    def _generate_health_report(self, service_results: Dict[str, HealthCheckResult]) -> SystemHealthReport:
        """生成系統健康報告"""
        timestamp = datetime.now()
        uptime_seconds = time.time() - self.system_start_time
        
        # 計算整體健康狀態和分數
        health_scores = []
        critical_issues = []
        warnings = []
        response_times = []
        
        for service_name, result in service_results.items():
            # 計算服務健康分數
            service_score = self._calculate_service_score(service_name, result)
            health_scores.append(service_score)
            
            # 收集響應時間
            if result.response_time_ms > 0:
                response_times.append(result.response_time_ms)
            
            # 分析問題
            if result.status == HealthStatus.UNHEALTHY:
                critical_issues.append(f"服務 {service_name} 不健康: {result.error_message or '未知錯誤'}")
            elif result.status == HealthStatus.DEGRADED:
                warnings.append(f"服務 {service_name} 性能下降")
            elif result.consecutive_failures > 0:
                warnings.append(f"服務 {service_name} 有間歇性問題")
        
        # 計算整體健康分數
        overall_score = sum(health_scores) / len(health_scores) if health_scores else 0
        
        # 確定整體狀態和等級
        overall_status = self._determine_overall_status(service_results)
        overall_grade = self._determine_health_grade(overall_score)
        
        # 計算響應時間統計
        response_time_stats = {}
        if response_times:
            response_time_stats = {
                'min': min(response_times),
                'max': max(response_times),
                'avg': sum(response_times) / len(response_times),
                'count': len(response_times)
            }
        
        # 生成建議
        recommendations = self._generate_health_recommendations(
            service_results, critical_issues, warnings, overall_score
        )
        
        return SystemHealthReport(
            timestamp=timestamp,
            overall_status=overall_status,
            overall_grade=overall_grade,
            health_score=overall_score,
            service_results=service_results,
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations,
            uptime_seconds=uptime_seconds,
            response_time_stats=response_time_stats
        )
    
    def _calculate_service_score(self, service_name: str, result: HealthCheckResult) -> float:
        """計算服務健康分數"""
        base_score = 0
        
        # 基礎分數（根據當前狀態）
        if result.status == HealthStatus.HEALTHY:
            base_score = 100
        elif result.status == HealthStatus.DEGRADED:
            base_score = 70
        elif result.status == HealthStatus.UNHEALTHY:
            base_score = 30
        else:  # UNKNOWN
            base_score = 50
        
        # 根據歷史表現調整分數
        history = self.health_history.get(service_name, [])
        if len(history) >= 5:
            recent_results = history[-5:]
            healthy_count = sum(1 for r in recent_results if r.status == HealthStatus.HEALTHY)
            stability_factor = healthy_count / len(recent_results)
            base_score *= stability_factor
        
        # 根據響應時間調整分數
        if result.response_time_ms > 0:
            if result.response_time_ms > 5000:  # 5秒以上
                base_score *= 0.8
            elif result.response_time_ms > 2000:  # 2秒以上
                base_score *= 0.9
        
        # 根據連續失敗次數調整分數
        if result.consecutive_failures > 0:
            penalty = min(result.consecutive_failures * 10, 50)
            base_score = max(base_score - penalty, 0)
        
        return max(0, min(100, base_score))
    
    def _determine_overall_status(self, service_results: Dict[str, HealthCheckResult]) -> HealthStatus:
        """確定整體健康狀態"""
        if not service_results:
            return HealthStatus.UNKNOWN
        
        unhealthy_count = 0
        degraded_count = 0
        healthy_count = 0
        
        for result in service_results.values():
            if result.status == HealthStatus.UNHEALTHY:
                unhealthy_count += 1
            elif result.status == HealthStatus.DEGRADED:
                degraded_count += 1
            elif result.status == HealthStatus.HEALTHY:
                healthy_count += 1
        
        total = len(service_results)
        
        # 如果有關鍵服務不健康，整體狀態為不健康
        critical_services = ['discord-bot', 'redis']
        for service_name in critical_services:
            if (service_name in service_results and 
                service_results[service_name].status == HealthStatus.UNHEALTHY):
                return HealthStatus.UNHEALTHY
        
        # 基於比例確定狀態
        if unhealthy_count > total * 0.3:  # 超過30%不健康
            return HealthStatus.UNHEALTHY
        elif unhealthy_count > 0 or degraded_count > total * 0.2:  # 有不健康或超過20%性能下降
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _determine_health_grade(self, score: float) -> HealthGrade:
        """確定健康等級"""
        if score >= 95:
            return HealthGrade.EXCELLENT
        elif score >= 80:
            return HealthGrade.GOOD
        elif score >= 60:
            return HealthGrade.WARNING
        elif score >= 40:
            return HealthGrade.CRITICAL
        else:
            return HealthGrade.FAILING
    
    def _generate_health_recommendations(self, service_results: Dict[str, HealthCheckResult],
                                       critical_issues: List[str], warnings: List[str],
                                       overall_score: float) -> List[str]:
        """生成健康建議"""
        recommendations = []
        
        if critical_issues:
            recommendations.append(f"立即處理 {len(critical_issues)} 個關鍵問題")
            
            # 針對特定服務的建議
            for service_name, result in service_results.items():
                if result.status == HealthStatus.UNHEALTHY:
                    if service_name == 'redis':
                        recommendations.append("檢查Redis服務是否運行，確認連接配置")
                    elif service_name == 'discord-bot':
                        recommendations.append("檢查Discord Bot配置，確認Token有效性")
                    elif service_name == 'prometheus':
                        recommendations.append("檢查Prometheus配置文件和存儲權限")
                    elif service_name == 'grafana':
                        recommendations.append("檢查Grafana數據源配置")
        
        if warnings:
            recommendations.append(f"注意 {len(warnings)} 個警告狀況")
        
        if overall_score < 80:
            recommendations.append("系統整體健康狀況需要改善")
            
            # 分析響應時間問題
            slow_services = [
                name for name, result in service_results.items()
                if result.response_time_ms > 3000
            ]
            if slow_services:
                recommendations.append(f"優化響應慢的服務: {', '.join(slow_services)}")
        
        if not recommendations:
            recommendations.append("系統運行狀況良好，繼續保持")
        
        return recommendations
    
    def get_health_trends(self, service_name: str, hours: int = 24) -> Dict[str, Any]:
        """獲取健康趨勢數據"""
        if service_name not in self.health_history:
            return {'error': f'服務 {service_name} 無歷史數據'}
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_results = [
            result for result in self.health_history[service_name]
            if result.timestamp >= cutoff_time
        ]
        
        if not recent_results:
            return {'error': f'服務 {service_name} 在過去 {hours} 小時內無數據'}
        
        # 計算統計數據
        healthy_count = sum(1 for r in recent_results if r.status == HealthStatus.HEALTHY)
        total_checks = len(recent_results)
        availability = (healthy_count / total_checks) * 100
        
        response_times = [r.response_time_ms for r in recent_results if r.response_time_ms > 0]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'service_name': service_name,
            'time_range_hours': hours,
            'total_checks': total_checks,
            'healthy_checks': healthy_count,
            'availability_percent': availability,
            'average_response_time_ms': avg_response_time,
            'last_check': recent_results[-1].timestamp.isoformat(),
            'status_distribution': self._calculate_status_distribution(recent_results)
        }
    
    def _calculate_status_distribution(self, results: List[HealthCheckResult]) -> Dict[str, int]:
        """計算狀態分布"""
        distribution = {
            'healthy': 0,
            'degraded': 0,
            'unhealthy': 0,
            'unknown': 0
        }
        
        for result in results:
            status = result.status.value
            if status in distribution:
                distribution[status] += 1
        
        return distribution


# 工廠方法和工具函數
def create_health_checker(project_root: Optional[Path] = None) -> UnifiedHealthChecker:
    """創建統一健康檢查器"""
    return UnifiedHealthChecker(project_root=project_root or Path.cwd())


async def quick_health_check() -> SystemHealthReport:
    """快速健康檢查"""
    async with create_health_checker() as checker:
        return await checker.check_all_services()


# 命令行介面
async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 統一健康檢查工具')
    parser.add_argument('command', choices=['check', 'report', 'service', 'trends'],
                       help='執行的命令')
    parser.add_argument('--service', '-s', help='指定服務名稱')
    parser.add_argument('--hours', type=int, default=24, help='趨勢分析時間範圍（小時）')
    parser.add_argument('--output', '-o', help='輸出檔案路徑')
    parser.add_argument('--format', choices=['json', 'text'], default='text', help='輸出格式')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        checker = create_health_checker()
        
        if args.command == 'check':
            report = await checker.check_all_services()
            
            if args.format == 'json':
                output = {
                    'timestamp': report.timestamp.isoformat(),
                    'overall_status': report.overall_status.value,
                    'overall_grade': report.overall_grade.value,
                    'health_score': report.health_score,
                    'service_results': {
                        name: {
                            'status': result.status.value,
                            'response_time_ms': result.response_time_ms,
                            'error_message': result.error_message
                        }
                        for name, result in report.service_results.items()
                    },
                    'critical_issues': report.critical_issues,
                    'warnings': report.warnings,
                    'recommendations': report.recommendations
                }
                
                if args.output:
                    with open(args.output, 'w', encoding='utf-8') as f:
                        json.dump(output, f, indent=2, ensure_ascii=False)
                else:
                    print(json.dumps(output, indent=2, ensure_ascii=False))
            
            else:  # text format
                status_icons = {
                    'healthy': '✅',
                    'degraded': '⚠️', 
                    'unhealthy': '❌',
                    'unknown': '❓'
                }
                
                grade_icons = {
                    'excellent': '🌟',
                    'good': '👍',
                    'warning': '⚠️',
                    'critical': '🚨',
                    'failing': '💀'
                }
                
                print(f"\n{'='*60}")
                print("🏥 ROAS Bot v2.4.3 系統健康報告")
                print(f"{'='*60}")
                print(f"檢查時間: {report.timestamp}")
                print(f"系統運行時間: {report.uptime_seconds/3600:.1f} 小時")
                print(f"整體狀態: {status_icons.get(report.overall_status.value, '❓')} {report.overall_status.value.upper()}")
                print(f"健康等級: {grade_icons.get(report.overall_grade.value, '❓')} {report.overall_grade.value.upper()}")
                print(f"健康分數: {report.health_score:.1f}/100")
                
                print(f"\n服務狀態:")
                for service_name, result in report.service_results.items():
                    icon = status_icons.get(result.status.value, '❓')
                    print(f"  {icon} {service_name}: {result.status.value}")
                    if result.response_time_ms > 0:
                        print(f"     響應時間: {result.response_time_ms:.0f}ms")
                    if result.error_message:
                        print(f"     錯誤: {result.error_message}")
                
                if report.response_time_stats:
                    print(f"\n響應時間統計:")
                    stats = report.response_time_stats
                    print(f"  最小值: {stats['min']:.0f}ms")
                    print(f"  最大值: {stats['max']:.0f}ms")
                    print(f"  平均值: {stats['avg']:.0f}ms")
                
                if report.critical_issues:
                    print(f"\n🚨 關鍵問題:")
                    for issue in report.critical_issues:
                        print(f"  • {issue}")
                
                if report.warnings:
                    print(f"\n⚠️ 警告:")
                    for warning in report.warnings:
                        print(f"  • {warning}")
                
                if report.recommendations:
                    print(f"\n💡 建議:")
                    for rec in report.recommendations:
                        print(f"  • {rec}")
            
            return 0 if report.overall_status in [HealthStatus.HEALTHY] else 1
            
        elif args.command == 'service':
            if not args.service:
                print("❌ 請指定服務名稱 (--service)")
                return 1
                
            result = await checker.check_service(args.service)
            if not result:
                print(f"❌ 未找到服務: {args.service}")
                return 1
            
            status_icon = {'healthy': '✅', 'degraded': '⚠️', 'unhealthy': '❌', 'unknown': '❓'}
            icon = status_icon.get(result.status.value, '❓')
            
            print(f"{icon} {args.service}: {result.status.value}")
            print(f"檢查時間: {result.timestamp}")
            if result.response_time_ms > 0:
                print(f"響應時間: {result.response_time_ms:.0f}ms")
            if result.error_message:
                print(f"錯誤信息: {result.error_message}")
            if result.details:
                print(f"詳細信息: {result.details}")
            
            return 0 if result.status == HealthStatus.HEALTHY else 1
            
        elif args.command == 'trends':
            if not args.service:
                print("❌ 請指定服務名稱 (--service)")
                return 1
            
            trends = checker.get_health_trends(args.service, args.hours)
            
            if 'error' in trends:
                print(f"❌ {trends['error']}")
                return 1
            
            print(f"\n📊 服務 {args.service} 趨勢分析 (過去 {args.hours} 小時)")
            print(f"總檢查次數: {trends['total_checks']}")
            print(f"健康檢查次數: {trends['healthy_checks']}")
            print(f"可用性: {trends['availability_percent']:.1f}%")
            print(f"平均響應時間: {trends['average_response_time_ms']:.0f}ms")
            print(f"最後檢查: {trends['last_check']}")
            
            print(f"\n狀態分布:")
            for status, count in trends['status_distribution'].items():
                print(f"  {status}: {count}")
            
            return 0
            
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))