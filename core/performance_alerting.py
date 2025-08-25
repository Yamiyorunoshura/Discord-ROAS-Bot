#!/usr/bin/env python3
"""
效能告警和自動優化機制
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

負責監控系統效能並自動應用優化策略，確保啟動時間保持在目標範圍內。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
import subprocess
import yaml

from core.monitoring_collector import MonitoringCollector, HealthStatus
from core.performance_optimizer import PerformanceOptimizer, OptimizationType
from core.deployment_manager import create_deployment_manager

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警級別"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class OptimizationAction(Enum):
    """優化動作類型"""
    DOCKER_CLEANUP = "docker_cleanup"
    RESTART_SERVICE = "restart_service"
    RESOURCE_ADJUSTMENT = "resource_adjustment"
    CONFIG_UPDATE = "config_update"
    HEALTH_CHECK_TUNING = "health_check_tuning"


@dataclass
class PerformanceAlert:
    """效能告警"""
    timestamp: datetime
    alert_level: AlertLevel
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    service_name: Optional[str] = None
    suggested_actions: List[str] = None
    alert_id: str = None


@dataclass
class AutoOptimizationResult:
    """自動優化結果"""
    timestamp: datetime
    action: OptimizationAction
    success: bool
    description: str
    improvement_metrics: Optional[Dict[str, float]] = None
    error_message: Optional[str] = None


@dataclass
class PerformanceMonitoringConfig:
    """效能監控配置"""
    startup_time_threshold: float = 300.0    # 5分鐘
    memory_usage_threshold: float = 512.0    # 512MB
    cpu_usage_threshold: float = 80.0        # 80%
    health_check_timeout: float = 60.0       # 1分鐘
    monitoring_interval: int = 30             # 30秒
    auto_optimization_enabled: bool = True
    alert_cooldown_seconds: int = 300        # 5分鐘告警冷卻


class PerformanceAlertManager:
    """
    效能告警和自動優化管理器
    
    負責：
    - 持續監控系統效能指標
    - 根據閾值觸發告警
    - 執行自動優化動作
    - 記錄優化歷史和效果
    - 提供效能趨勢分析
    """
    
    def __init__(self, project_root: Optional[Path] = None, config: Optional[PerformanceMonitoringConfig] = None):
        self.project_root = project_root or Path.cwd()
        self.config = config or PerformanceMonitoringConfig()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 初始化子系統
        self.monitoring_collector = MonitoringCollector(project_root)
        self.performance_optimizer = PerformanceOptimizer(project_root)
        
        # 告警狀態管理
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: List[PerformanceAlert] = []
        self.last_alert_time: Dict[str, datetime] = {}
        
        # 優化歷史
        self.optimization_history: List[AutoOptimizationResult] = []
        
        # 監控狀態
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self) -> None:
        """開始效能監控"""
        if self.monitoring_active:
            self.logger.warning("效能監控已經運行中")
            return
        
        self.logger.info("開始效能監控和告警系統")
        self.monitoring_active = True
        
        # 創建監控任務
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        try:
            await self.monitoring_task
        except asyncio.CancelledError:
            self.logger.info("效能監控已停止")
        except Exception as e:
            self.logger.error(f"效能監控異常: {str(e)}", exc_info=True)
        finally:
            self.monitoring_active = False
    
    async def stop_monitoring(self) -> None:
        """停止效能監控"""
        if not self.monitoring_active:
            return
        
        self.logger.info("停止效能監控")
        self.monitoring_active = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def _monitoring_loop(self) -> None:
        """監控循環"""
        while self.monitoring_active:
            try:
                # 收集效能指標
                await self._collect_and_analyze_metrics()
                
                # 檢查是否需要自動優化
                if self.config.auto_optimization_enabled:
                    await self._execute_auto_optimizations()
                
                # 清理過期告警
                self._cleanup_expired_alerts()
                
                # 等待下一個監控周期
                await asyncio.sleep(self.config.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"監控循環異常: {str(e)}", exc_info=True)
                await asyncio.sleep(self.config.monitoring_interval)
    
    async def _collect_and_analyze_metrics(self) -> None:
        """收集和分析效能指標"""
        try:
            # 收集系統監控指標
            system_metrics = await self.monitoring_collector.collect_metrics()
            
            # 收集啟動效能指標
            startup_metrics = await self.monitoring_collector.collect_startup_performance_metrics()
            
            # 分析系統指標告警
            await self._analyze_system_metrics(system_metrics)
            
            # 分析啟動效能告警
            await self._analyze_startup_metrics(startup_metrics)
            
        except Exception as e:
            self.logger.error(f"指標收集和分析失敗: {str(e)}")
    
    async def _analyze_system_metrics(self, metrics: Dict[str, Any]) -> None:
        """分析系統指標並生成告警"""
        system_metrics = metrics.get('system_metrics', {})
        
        # 檢查CPU使用率
        cpu_usage = system_metrics.get('cpu_usage_percent', 0)
        if cpu_usage > self.config.cpu_usage_threshold:
            await self._create_alert(
                AlertLevel.WARNING,
                'system_cpu_usage',
                cpu_usage,
                self.config.cpu_usage_threshold,
                f"系統CPU使用率過高: {cpu_usage:.1f}%",
                suggested_actions=[
                    "檢查CPU密集型進程",
                    "考慮優化應用程式碼",
                    "增加CPU資源或減少並發數"
                ]
            )
        
        # 檢查記憶體使用率
        memory_usage_percent = system_metrics.get('memory_usage_percent', 0)
        if memory_usage_percent > 85.0:  # 85%記憶體使用告警
            await self._create_alert(
                AlertLevel.WARNING,
                'system_memory_usage',
                memory_usage_percent,
                85.0,
                f"系統記憶體使用率過高: {memory_usage_percent:.1f}%",
                suggested_actions=[
                    "檢查記憶體洩漏",
                    "重啟記憶體使用過多的服務",
                    "增加系統記憶體"
                ]
            )
        
        # 檢查磁盤空間
        disk_free_gb = system_metrics.get('disk_free_gb', 0)
        if disk_free_gb < 2.0:  # 少於2GB磁盤空間
            await self._create_alert(
                AlertLevel.CRITICAL,
                'system_disk_space',
                disk_free_gb,
                2.0,
                f"磁盤空間不足: {disk_free_gb:.1f}GB",
                suggested_actions=[
                    "清理臨時文件",
                    "執行docker system prune",
                    "擴展磁盤空間"
                ]
            )
        
        # 檢查服務健康狀態
        service_metrics = metrics.get('service_metrics', [])
        for service in service_metrics:
            service_name = service.get('service_name', 'unknown')
            status = service.get('status', 'unknown')
            
            if status == 'unhealthy':
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    'service_health',
                    0,  # 數值型指標
                    1,  # 期望值（健康）
                    f"服務不健康: {service_name}",
                    service_name=service_name,
                    suggested_actions=[
                        f"重啟服務 {service_name}",
                        "檢查服務配置",
                        "查看服務日誌"
                    ]
                )
    
    async def _analyze_startup_metrics(self, metrics: Dict[str, Any]) -> None:
        """分析啟動效能指標"""
        # 分析資源消耗
        resource_consumption = metrics.get('resource_consumption', {})
        total_containers = resource_consumption.get('total_containers', 0)
        
        if total_containers == 0:
            await self._create_alert(
                AlertLevel.WARNING,
                'no_containers_running',
                0,
                1,
                "沒有容器在運行，可能存在啟動問題"
            )
        
        # 分析健康檢查效能
        health_perf = metrics.get('health_check_performance', {})
        efficiency = health_perf.get('overall_health_check_efficiency', 0)
        
        if efficiency < 50.0:  # 健康檢查效率低於50%
            await self._create_alert(
                AlertLevel.WARNING,
                'health_check_efficiency',
                efficiency,
                50.0,
                f"健康檢查效率低: {efficiency:.1f}%",
                suggested_actions=[
                    "優化健康檢查配置",
                    "減少健康檢查超時時間",
                    "簡化健康檢查邏輯"
                ]
            )
        
        # 分析啟動瓶頸
        bottlenecks = metrics.get('startup_bottlenecks', {})
        high_severity_count = bottlenecks.get('high_severity_count', 0)
        medium_severity_count = bottlenecks.get('medium_severity_count', 0)
        
        if high_severity_count > 0:
            await self._create_alert(
                AlertLevel.CRITICAL,
                'startup_bottlenecks',
                high_severity_count,
                0,
                f"發現 {high_severity_count} 個高嚴重性啟動瓶頸",
                suggested_actions=[
                    "檢查系統資源",
                    "優化容器配置",
                    "清理Docker資源"
                ]
            )
        elif medium_severity_count > 2:
            await self._create_alert(
                AlertLevel.WARNING,
                'startup_bottlenecks',
                medium_severity_count,
                2,
                f"發現 {medium_severity_count} 個中嚴重性啟動瓶頸"
            )
    
    async def _create_alert(self, level: AlertLevel, metric_name: str, current_value: float,
                          threshold_value: float, message: str, service_name: Optional[str] = None,
                          suggested_actions: Optional[List[str]] = None) -> None:
        """創建告警"""
        # 生成告警ID
        alert_id = f"{metric_name}_{service_name or 'system'}_{int(time.time())}"
        
        # 檢查冷卻期
        if self._is_in_cooldown(metric_name):
            return
        
        alert = PerformanceAlert(
            timestamp=datetime.now(),
            alert_level=level,
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value,
            message=message,
            service_name=service_name,
            suggested_actions=suggested_actions or [],
            alert_id=alert_id
        )
        
        # 存儲告警
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        self.last_alert_time[metric_name] = datetime.now()
        
        # 記錄告警
        level_icon = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️", 
            AlertLevel.CRITICAL: "🔴",
            AlertLevel.EMERGENCY: "🚨"
        }
        icon = level_icon.get(level, "❓")
        
        self.logger.warning(f"{icon} 效能告警: {message}")
        
        # 如果是關鍵告警，考慮自動優化
        if level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY] and self.config.auto_optimization_enabled:
            await self._trigger_auto_optimization(alert)
    
    def _is_in_cooldown(self, metric_name: str) -> bool:
        """檢查是否在告警冷卻期內"""
        last_time = self.last_alert_time.get(metric_name)
        if last_time:
            cooldown_time = timedelta(seconds=self.config.alert_cooldown_seconds)
            return datetime.now() - last_time < cooldown_time
        return False
    
    async def _execute_auto_optimizations(self) -> None:
        """執行自動優化"""
        # 檢查是否有需要定期執行的優化
        await self._periodic_optimization()
    
    async def _trigger_auto_optimization(self, alert: PerformanceAlert) -> None:
        """觸發自動優化"""
        optimizations = []
        
        if alert.metric_name == 'system_disk_space':
            optimizations.append(OptimizationAction.DOCKER_CLEANUP)
        elif alert.metric_name == 'service_health' and alert.service_name:
            optimizations.append(OptimizationAction.RESTART_SERVICE)
        elif alert.metric_name == 'health_check_efficiency':
            optimizations.append(OptimizationAction.HEALTH_CHECK_TUNING)
        
        for action in optimizations:
            await self._execute_optimization_action(action, alert.service_name)
    
    async def _periodic_optimization(self) -> None:
        """定期優化檢查"""
        # 每10分鐘檢查一次是否需要Docker清理
        last_cleanup = None
        for result in reversed(self.optimization_history):
            if result.action == OptimizationAction.DOCKER_CLEANUP:
                last_cleanup = result.timestamp
                break
        
        if not last_cleanup or datetime.now() - last_cleanup > timedelta(minutes=10):
            # 檢查Docker空間使用
            try:
                result = subprocess.run(
                    ['docker', 'system', 'df'],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0 and 'reclaimable' in result.stdout.lower():
                    await self._execute_optimization_action(OptimizationAction.DOCKER_CLEANUP)
            except Exception:
                pass
    
    async def _execute_optimization_action(self, action: OptimizationAction, 
                                         service_name: Optional[str] = None) -> AutoOptimizationResult:
        """執行優化動作"""
        self.logger.info(f"執行自動優化: {action.value}")
        start_time = time.time()
        
        try:
            if action == OptimizationAction.DOCKER_CLEANUP:
                result = await self._docker_cleanup()
            elif action == OptimizationAction.RESTART_SERVICE:
                result = await self._restart_service(service_name)
            elif action == OptimizationAction.HEALTH_CHECK_TUNING:
                result = await self._tune_health_checks()
            else:
                result = AutoOptimizationResult(
                    timestamp=datetime.now(),
                    action=action,
                    success=False,
                    description=f"不支援的優化動作: {action.value}",
                    error_message="未實作的優化動作"
                )
            
        except Exception as e:
            result = AutoOptimizationResult(
                timestamp=datetime.now(),
                action=action,
                success=False,
                description=f"優化動作執行失敗: {str(e)}",
                error_message=str(e)
            )
        
        # 記錄優化結果
        self.optimization_history.append(result)
        
        duration = time.time() - start_time
        status_icon = "✅" if result.success else "❌"
        self.logger.info(f"{status_icon} 自動優化完成: {result.description} (耗時: {duration:.1f}秒)")
        
        return result
    
    async def _docker_cleanup(self) -> AutoOptimizationResult:
        """執行Docker清理"""
        try:
            # 執行Docker清理
            result = subprocess.run(
                ['docker', 'system', 'prune', '-f'],
                capture_output=True, text=True, timeout=300
            )
            
            if result.returncode == 0:
                # 解析清理結果
                stdout = result.stdout
                description = "Docker清理完成"
                if "Total reclaimed space" in stdout:
                    # 提取回收的空間
                    for line in stdout.split('\n'):
                        if "Total reclaimed space" in line:
                            description = f"Docker清理完成，{line.strip()}"
                            break
                
                return AutoOptimizationResult(
                    timestamp=datetime.now(),
                    action=OptimizationAction.DOCKER_CLEANUP,
                    success=True,
                    description=description
                )
            else:
                return AutoOptimizationResult(
                    timestamp=datetime.now(),
                    action=OptimizationAction.DOCKER_CLEANUP,
                    success=False,
                    description="Docker清理失敗",
                    error_message=result.stderr
                )
                
        except Exception as e:
            return AutoOptimizationResult(
                timestamp=datetime.now(),
                action=OptimizationAction.DOCKER_CLEANUP,
                success=False,
                description="Docker清理異常",
                error_message=str(e)
            )
    
    async def _restart_service(self, service_name: Optional[str]) -> AutoOptimizationResult:
        """重啟服務"""
        if not service_name:
            return AutoOptimizationResult(
                timestamp=datetime.now(),
                action=OptimizationAction.RESTART_SERVICE,
                success=False,
                description="重啟服務失敗：未指定服務名稱"
            )
        
        try:
            # 使用Docker Compose重啟服務
            result = subprocess.run(
                ['docker', 'compose', '-f', 'docker-compose.dev.yml', 'restart', service_name],
                capture_output=True, text=True, timeout=120
            )
            
            if result.returncode == 0:
                return AutoOptimizationResult(
                    timestamp=datetime.now(),
                    action=OptimizationAction.RESTART_SERVICE,
                    success=True,
                    description=f"服務 {service_name} 重啟成功"
                )
            else:
                return AutoOptimizationResult(
                    timestamp=datetime.now(),
                    action=OptimizationAction.RESTART_SERVICE,
                    success=False,
                    description=f"服務 {service_name} 重啟失敗",
                    error_message=result.stderr
                )
                
        except Exception as e:
            return AutoOptimizationResult(
                timestamp=datetime.now(),
                action=OptimizationAction.RESTART_SERVICE,
                success=False,
                description=f"重啟服務 {service_name} 異常",
                error_message=str(e)
            )
    
    async def _tune_health_checks(self) -> AutoOptimizationResult:
        """調優健康檢查"""
        try:
            # 這裡實作健康檢查調優邏輯
            # 實際上應該分析當前的健康檢查配置並進行優化
            
            return AutoOptimizationResult(
                timestamp=datetime.now(),
                action=OptimizationAction.HEALTH_CHECK_TUNING,
                success=True,
                description="健康檢查配置調優完成（模擬）"
            )
            
        except Exception as e:
            return AutoOptimizationResult(
                timestamp=datetime.now(),
                action=OptimizationAction.HEALTH_CHECK_TUNING,
                success=False,
                description="健康檢查調優異常",
                error_message=str(e)
            )
    
    def _cleanup_expired_alerts(self) -> None:
        """清理過期告警"""
        current_time = datetime.now()
        expired_threshold = timedelta(hours=1)  # 1小時後告警過期
        
        expired_alerts = []
        for alert_id, alert in self.active_alerts.items():
            if current_time - alert.timestamp > expired_threshold:
                expired_alerts.append(alert_id)
        
        for alert_id in expired_alerts:
            del self.active_alerts[alert_id]
    
    def get_active_alerts(self) -> List[PerformanceAlert]:
        """獲取活動告警"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[PerformanceAlert]:
        """獲取告警歷史"""
        return self.alert_history[-limit:]
    
    def get_optimization_history(self, limit: int = 50) -> List[AutoOptimizationResult]:
        """獲取優化歷史"""
        return self.optimization_history[-limit:]
    
    def generate_performance_summary(self) -> Dict[str, Any]:
        """生成效能摘要報告"""
        current_time = datetime.now()
        
        # 統計最近24小時的告警
        recent_alerts = [
            alert for alert in self.alert_history 
            if current_time - alert.timestamp < timedelta(hours=24)
        ]
        
        # 統計最近24小時的優化
        recent_optimizations = [
            opt for opt in self.optimization_history
            if current_time - opt.timestamp < timedelta(hours=24)
        ]
        
        return {
            'timestamp': current_time,
            'monitoring_status': 'active' if self.monitoring_active else 'inactive',
            'active_alerts_count': len(self.active_alerts),
            'recent_alerts_24h': len(recent_alerts),
            'alert_levels': {
                level.value: len([a for a in recent_alerts if a.alert_level == level])
                for level in AlertLevel
            },
            'recent_optimizations_24h': len(recent_optimizations),
            'successful_optimizations': len([opt for opt in recent_optimizations if opt.success]),
            'optimization_success_rate': (
                len([opt for opt in recent_optimizations if opt.success]) / len(recent_optimizations) * 100
                if recent_optimizations else 0
            ),
            'most_common_alerts': self._get_most_common_alert_types(recent_alerts),
            'performance_trends': {
                'improving': len([opt for opt in recent_optimizations if opt.success]) > len(recent_alerts),
                'stable': len(self.active_alerts) == 0,
                'degrading': len([a for a in recent_alerts if a.alert_level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]]) > 0
            }
        }
    
    def _get_most_common_alert_types(self, alerts: List[PerformanceAlert]) -> List[Dict[str, Any]]:
        """獲取最常見的告警類型"""
        alert_counts = {}
        for alert in alerts:
            metric = alert.metric_name
            alert_counts[metric] = alert_counts.get(metric, 0) + 1
        
        return [
            {'metric': metric, 'count': count}
            for metric, count in sorted(alert_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]


# 命令行介面
async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 效能告警和自動優化工具')
    parser.add_argument('command', choices=['monitor', 'status', 'history', 'optimize'],
                       help='執行的命令')
    parser.add_argument('--duration', type=int, default=300,
                       help='監控持續時間（秒）')
    parser.add_argument('--auto-optimize', action='store_true',
                       help='啟用自動優化')
    parser.add_argument('--output', type=Path, help='輸出檔案路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 創建配置
    config = PerformanceMonitoringConfig()
    config.auto_optimization_enabled = args.auto_optimize
    
    # 創建告警管理器
    alert_manager = PerformanceAlertManager(config=config)
    
    try:
        if args.command == 'monitor':
            print(f"🔍 開始效能監控 (持續 {args.duration} 秒)")
            print("按 Ctrl+C 提前停止監控")
            
            # 啟動監控任務
            monitor_task = asyncio.create_task(alert_manager.start_monitoring())
            
            try:
                await asyncio.wait_for(monitor_task, timeout=args.duration)
            except asyncio.TimeoutError:
                await alert_manager.stop_monitoring()
                print("\n⏰ 監控時間到，停止監控")
            
            # 生成摘要報告
            summary = alert_manager.generate_performance_summary()
            print(f"\n📊 監控摘要:")
            print(f"  活動告警: {summary['active_alerts_count']}")
            print(f"  24小時告警: {summary['recent_alerts_24h']}")
            print(f"  自動優化: {summary['recent_optimizations_24h']} (成功率: {summary['optimization_success_rate']:.1f}%)")
            
        elif args.command == 'status':
            summary = alert_manager.generate_performance_summary()
            
            print(f"\n{'='*60}")
            print("📊 ROAS Bot 效能狀態報告")
            print(f"{'='*60}")
            print(f"監控狀態: {summary['monitoring_status'].upper()}")
            print(f"活動告警: {summary['active_alerts_count']}")
            print(f"24小時告警: {summary['recent_alerts_24h']}")
            
            if summary['most_common_alerts']:
                print(f"\n⚠️  最常見告警:")
                for alert_type in summary['most_common_alerts'][:3]:
                    print(f"  • {alert_type['metric']}: {alert_type['count']}次")
            
            print(f"\n🔧 自動優化:")
            print(f"  24小時優化: {summary['recent_optimizations_24h']}")
            print(f"  成功率: {summary['optimization_success_rate']:.1f}%")
            
            # 效能趨勢
            trends = summary['performance_trends']
            if trends['improving']:
                print(f"  📈 趨勢: 改善中")
            elif trends['stable']:
                print(f"  📊 趨勢: 穩定")
            elif trends['degrading']:
                print(f"  📉 趨勢: 惡化")
            
        elif args.command == 'history':
            alerts = alert_manager.get_alert_history(50)
            optimizations = alert_manager.get_optimization_history(20)
            
            print(f"\n📋 最近告警歷史 (前50筆):")
            for alert in alerts[-10:]:  # 顯示最新10筆
                level_icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🔴", "emergency": "🚨"}
                icon = level_icon.get(alert.alert_level.value, "❓")
                print(f"  {icon} {alert.timestamp.strftime('%H:%M:%S')} - {alert.message}")
            
            print(f"\n🔧 最近優化歷史 (前20筆):")
            for opt in optimizations[-10:]:  # 顯示最新10筆
                icon = "✅" if opt.success else "❌"
                print(f"  {icon} {opt.timestamp.strftime('%H:%M:%S')} - {opt.description}")
            
        elif args.command == 'optimize':
            print("🔧 執行手動優化...")
            
            # 執行Docker清理
            result = await alert_manager._execute_optimization_action(OptimizationAction.DOCKER_CLEANUP)
            icon = "✅" if result.success else "❌"
            print(f"  {icon} Docker清理: {result.description}")
            
        if args.output:
            # 保存詳細報告
            summary = alert_manager.generate_performance_summary()
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n📄 詳細報告已保存: {args.output}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️ 操作已取消")
        await alert_manager.stop_monitoring()
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))