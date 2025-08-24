"""
Monitoring System Integration
Task ID: T2 - High Concurrency Connection Competition Fix

This module provides seamless integration between connection pool
monitoring data and the existing logging/monitoring infrastructure,
enabling unified observability and centralized monitoring.
"""

import asyncio
import json
import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Union
from contextlib import asynccontextmanager

from ..core.logging import get_logger, get_log_manager, log_context
from .connection_pool_monitor import ConnectionPoolMonitor, PoolStats, PoolEvent
from .realtime_stats_collector import RealTimeStatsCollector, AggregatedMetric
from .diagnostic_alerting_system import ConnectionPoolDiagnosticSystem, Alert
from .auto_recovery_system import AutoRecoverySystem, HealthCheckResult


@dataclass
class MonitoringIntegrationConfig:
    """Configuration for monitoring system integration"""
    
    # Logging integration
    enable_structured_logging: bool = True
    log_level: str = "INFO"
    log_to_dedicated_files: bool = True
    
    # Metrics export
    export_metrics_interval: float = 60.0
    export_to_json: bool = True
    export_directory: str = "monitoring_exports"
    
    # Alert integration
    forward_alerts_to_logging: bool = True
    alert_log_level: str = "WARNING"
    
    # Health status integration
    health_status_interval: float = 120.0
    include_detailed_diagnostics: bool = True
    
    # Performance thresholds for logging
    log_performance_threshold_ms: float = 100.0
    log_error_rate_threshold: float = 0.05
    log_utilization_threshold: float = 0.8


class LoggingIntegrator:
    """
    Integrator for connection pool monitoring with application logging
    
    Bridges connection pool events and metrics with the existing
    logging infrastructure for unified observability.
    """
    
    def __init__(self, config: MonitoringIntegrationConfig):
        """
        Initialize logging integrator
        
        Args:
            config: Integration configuration
        """
        self.config = config
        self.logger = get_logger("pool_monitoring_integration")
        self.log_manager = get_log_manager()
        
        # Create dedicated loggers for monitoring data
        if config.log_to_dedicated_files:
            self.pool_logger = self.log_manager.create_logger(
                "connection_pool_monitor",
                "connection_pool.log",
                config.log_level,
                "json" if config.enable_structured_logging else "standard"
            )
            
            self.metrics_logger = self.log_manager.create_logger(
                "pool_metrics",
                "pool_metrics.log",
                config.log_level,
                "json"
            )
            
            self.health_logger = self.log_manager.create_logger(
                "pool_health",
                "pool_health.log",
                config.log_level,
                "json"
            )
        else:
            self.pool_logger = self.logger
            self.metrics_logger = self.logger
            self.health_logger = self.logger
        
        # Integration state
        self._event_handlers_registered = False
        
        self.logger.info("Logging integrator initialized")
    
    def register_with_monitor(self, pool_monitor: ConnectionPoolMonitor):
        """Register event handlers with pool monitor"""
        if self._event_handlers_registered:
            return
        
        pool_monitor.add_event_handler(self._handle_pool_event)
        self._event_handlers_registered = True
        
        self.logger.info("Registered event handlers with pool monitor")
    
    def _handle_pool_event(self, event: PoolEvent):
        """Handle pool events for logging integration"""
        
        # Determine log level based on event level and type
        log_level = self._get_log_level_for_event(event)
        
        # Create structured log data
        log_data = {
            'event_type': event.event_type.value,
            'event_level': event.event_level.value,
            'pool_name': event.pool_name,
            'message': event.event_message,
            'timestamp': event.timestamp.isoformat(),
            'thread_id': event.thread_id,
            'duration_ms': event.duration_ms
        }
        
        if event.event_data:
            log_data['event_data'] = event.event_data
        
        if event.error_code:
            log_data['error_code'] = event.error_code
        
        # Log with context
        with log_context(component="connection_pool", pool_name=event.pool_name):
            if self.config.enable_structured_logging:
                # Log structured data
                self.pool_logger.log(
                    getattr(logging, log_level),
                    "Connection pool event",
                    extra=log_data
                )
            else:
                # Log formatted message
                message = f"[{event.event_type.value}] {event.event_message}"
                if event.duration_ms:
                    message += f" (duration: {event.duration_ms:.2f}ms)"
                
                self.pool_logger.log(getattr(logging, log_level), message)
    
    def _get_log_level_for_event(self, event: PoolEvent) -> str:
        """Determine appropriate log level for event"""
        level_mapping = {
            'DEBUG': 'DEBUG',
            'INFO': 'INFO',
            'WARN': 'WARNING',
            'ERROR': 'ERROR',
            'CRITICAL': 'CRITICAL'
        }
        return level_mapping.get(event.event_level.value, 'INFO')
    
    def log_pool_statistics(self, stats: PoolStats):
        """Log pool statistics"""
        
        # Check if performance logging threshold is met
        should_log_performance = (
            stats.average_wait_time_ms > self.config.log_performance_threshold_ms or
            stats.error_rate > self.config.log_error_rate_threshold or
            stats.utilization_ratio > self.config.log_utilization_threshold
        )
        
        if should_log_performance or self.config.log_level == 'DEBUG':
            log_data = {
                'pool_name': stats.pool_name,
                'active_connections': stats.active_connections,
                'idle_connections': stats.idle_connections,
                'utilization_ratio': stats.utilization_ratio,
                'average_wait_time_ms': stats.average_wait_time_ms,
                'max_wait_time_ms': stats.max_wait_time_ms,
                'success_rate': stats.success_rate,
                'error_rate': stats.error_rate,
                'pool_health_score': stats.pool_health_score,
                'timestamp': stats.timestamp.isoformat()
            }
            
            log_level = 'WARNING' if should_log_performance else 'INFO'
            
            with log_context(component="connection_pool_stats", pool_name=stats.pool_name):
                if self.config.enable_structured_logging:
                    self.metrics_logger.log(
                        getattr(logging, log_level),
                        "Connection pool statistics",
                        extra=log_data
                    )
                else:
                    message = (f"Pool stats - Active: {stats.active_connections}, "
                             f"Utilization: {stats.utilization_ratio:.1%}, "
                             f"Wait time: {stats.average_wait_time_ms:.1f}ms, "
                             f"Health: {stats.pool_health_score:.2f}")
                    
                    self.metrics_logger.log(getattr(logging, log_level), message)
    
    def log_aggregated_metrics(self, metrics: Dict[str, AggregatedMetric]):
        """Log aggregated metrics"""
        if not metrics:
            return
        
        for metric_name, metric in metrics.items():
            log_data = {
                'metric_name': metric_name,
                'metric_type': metric.metric_type.value,
                'window': metric.window.value,
                'count': metric.count,
                'sum': metric.sum,
                'avg': metric.avg,
                'min': metric.min,
                'max': metric.max,
                'timestamp': metric.timestamp
            }
            
            if metric.metric_type.value in ['histogram', 'timer']:
                log_data.update({
                    'p50': metric.p50,
                    'p95': metric.p95,
                    'p99': metric.p99
                })
            
            with log_context(component="pool_metrics", metric=metric_name):
                self.metrics_logger.info(
                    f"Aggregated metric: {metric_name}",
                    extra=log_data if self.config.enable_structured_logging else {}
                )
    
    def log_alert(self, alert: Alert):
        """Log alert information"""
        if not self.config.forward_alerts_to_logging:
            return
        
        log_level = self._get_log_level_for_alert(alert)
        
        log_data = {
            'alert_id': alert.id,
            'alert_type': alert.alert_type.value,
            'severity': alert.severity.value,
            'title': alert.title,
            'message': alert.message,
            'resolved': alert.resolved,
            'timestamp': alert.timestamp.isoformat()
        }
        
        if alert.diagnosis:
            log_data['diagnosis'] = {
                'category': alert.diagnosis.category.value,
                'root_cause': alert.diagnosis.root_cause,
                'confidence_score': alert.diagnosis.confidence_score,
                'recommendations': alert.diagnosis.recommendations[:3]  # Limit recommendations
            }
        
        with log_context(component="pool_alerts", alert_id=alert.id):
            if self.config.enable_structured_logging:
                self.health_logger.log(
                    getattr(logging, log_level),
                    f"Connection pool alert: {alert.title}",
                    extra=log_data
                )
            else:
                message = f"[{alert.severity.value.upper()}] {alert.title}: {alert.message}"
                if alert.diagnosis:
                    message += f" (Root cause: {alert.diagnosis.root_cause})"
                
                self.health_logger.log(getattr(logging, log_level), message)
    
    def _get_log_level_for_alert(self, alert: Alert) -> str:
        """Determine log level for alert"""
        severity_mapping = {
            'low': 'INFO',
            'medium': 'WARNING',
            'high': 'ERROR',
            'critical': 'CRITICAL'
        }
        return severity_mapping.get(alert.severity.value, self.config.alert_log_level)
    
    def log_health_status(self, health_results: List[HealthCheckResult]):
        """Log health check results"""
        for result in health_results:
            log_data = {
                'component': result.component,
                'status': result.status.value,
                'score': result.score,
                'message': result.message,
                'timestamp': result.timestamp.isoformat()
            }
            
            if self.config.include_detailed_diagnostics and result.details:
                log_data['details'] = result.details
            
            # Determine log level based on health status
            if result.status.value in ['critical']:
                log_level = 'ERROR'
            elif result.status.value in ['degraded']:
                log_level = 'WARNING'
            elif result.status.value in ['warning']:
                log_level = 'INFO'
            else:
                log_level = 'DEBUG'
            
            with log_context(component="pool_health", health_component=result.component):
                if self.config.enable_structured_logging:
                    self.health_logger.log(
                        getattr(logging, log_level),
                        f"Health check: {result.component} - {result.status.value}",
                        extra=log_data
                    )
                else:
                    message = f"Health check [{result.component}]: {result.status.value} (score: {result.score:.2f}) - {result.message}"
                    self.health_logger.log(getattr(logging, log_level), message)


class MetricsExporter:
    """
    Exports monitoring metrics to external formats and systems
    
    Provides export capabilities for metrics data in various formats
    for integration with external monitoring tools.
    """
    
    def __init__(self, config: MonitoringIntegrationConfig):
        """Initialize metrics exporter"""
        self.config = config
        self.logger = get_logger("metrics_exporter")
        
        # Export state
        self._export_active = False
        self._export_task: Optional[asyncio.Task] = None
        
        # Create export directory
        import os
        os.makedirs(config.export_directory, exist_ok=True)
        
        self.logger.info("Metrics exporter initialized")
    
    async def start_export(self, stats_collector: RealTimeStatsCollector):
        """Start automated metrics export"""
        if self._export_active:
            return
        
        self._export_active = True
        self._export_task = asyncio.create_task(self._export_loop(stats_collector))
        
        self.logger.info("Started automated metrics export")
    
    async def stop_export(self):
        """Stop automated metrics export"""
        if not self._export_active:
            return
        
        self._export_active = False
        
        if self._export_task:
            self._export_task.cancel()
            try:
                await self._export_task
            except asyncio.CancelledError:
                pass
            self._export_task = None
        
        self.logger.info("Stopped automated metrics export")
    
    async def _export_loop(self, stats_collector: RealTimeStatsCollector):
        """Main export loop"""
        while self._export_active:
            try:
                await self._export_metrics(stats_collector)
                await asyncio.sleep(self.config.export_metrics_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in metrics export loop: {e}")
                await asyncio.sleep(self.config.export_metrics_interval)
    
    async def _export_metrics(self, stats_collector: RealTimeStatsCollector):
        """Export current metrics"""
        try:
            # Get metrics summary
            metrics_summary = stats_collector.get_metrics_summary()
            current_snapshot = stats_collector.get_current_snapshot()
            
            timestamp = datetime.now()
            
            # Create export data
            export_data = {
                'timestamp': timestamp.isoformat(),
                'pool_name': metrics_summary['pool_name'],
                'collection_interval': metrics_summary['collection_interval'],
                'collecting': metrics_summary['collecting'],
                'current_values': current_snapshot,
                'metrics_summary': metrics_summary['metrics']
            }
            
            if self.config.export_to_json:
                await self._export_to_json(export_data, timestamp)
            
            self.logger.debug(f"Exported metrics for pool: {metrics_summary['pool_name']}")
            
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}")
    
    async def _export_to_json(self, data: Dict[str, Any], timestamp: datetime):
        """Export metrics to JSON file"""
        try:
            filename = f"metrics_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = f"{self.config.export_directory}/{filename}"
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
        except Exception as e:
            self.logger.error(f"Failed to export to JSON: {e}")


class MonitoringSystemIntegrator:
    """
    Main integration orchestrator
    
    Coordinates all aspects of monitoring system integration,
    providing a unified interface for connecting pool monitoring
    with existing infrastructure.
    """
    
    def __init__(self, config: Optional[MonitoringIntegrationConfig] = None):
        """
        Initialize monitoring system integrator
        
        Args:
            config: Integration configuration
        """
        self.config = config or MonitoringIntegrationConfig()
        self.logger = get_logger("monitoring_integrator")
        
        # Integration components
        self.logging_integrator = LoggingIntegrator(self.config)
        self.metrics_exporter = MetricsExporter(self.config)
        
        # Monitoring components (set via integration)
        self.pool_monitor: Optional[ConnectionPoolMonitor] = None
        self.stats_collector: Optional[RealTimeStatsCollector] = None
        self.diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None
        self.recovery_system: Optional[AutoRecoverySystem] = None
        
        # Integration state
        self._integration_active = False
        self._health_logging_task: Optional[asyncio.Task] = None
        
        self.logger.info("Monitoring system integrator initialized")
    
    async def integrate_monitoring_stack(self,
                                       pool_monitor: ConnectionPoolMonitor,
                                       stats_collector: RealTimeStatsCollector,
                                       diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None,
                                       recovery_system: Optional[AutoRecoverySystem] = None):
        """
        Integrate complete monitoring stack
        
        Args:
            pool_monitor: Pool monitor instance
            stats_collector: Stats collector instance
            diagnostic_system: Optional diagnostic system
            recovery_system: Optional recovery system
        """
        
        # Store references
        self.pool_monitor = pool_monitor
        self.stats_collector = stats_collector
        self.diagnostic_system = diagnostic_system
        self.recovery_system = recovery_system
        
        # Register logging integration
        self.logging_integrator.register_with_monitor(pool_monitor)
        
        # Setup stats collection callback
        stats_collector.add_collection_callback(self._handle_collected_metrics)
        
        # Setup diagnostic system integration
        if diagnostic_system:
            diagnostic_system.alert_manager.add_notification_handler(self._handle_alert)
        
        # Start metrics export
        await self.metrics_exporter.start_export(stats_collector)
        
        # Start health status logging
        if recovery_system and self.config.health_status_interval > 0:
            self._health_logging_task = asyncio.create_task(self._health_logging_loop())
        
        self._integration_active = True
        self.logger.info("Monitoring stack integration completed")
    
    async def stop_integration(self):
        """Stop monitoring integration"""
        if not self._integration_active:
            return
        
        # Stop export
        await self.metrics_exporter.stop_export()
        
        # Stop health logging
        if self._health_logging_task:
            self._health_logging_task.cancel()
            try:
                await self._health_logging_task
            except asyncio.CancelledError:
                pass
            self._health_logging_task = None
        
        self._integration_active = False
        self.logger.info("Monitoring integration stopped")
    
    def _handle_collected_metrics(self, metrics: Dict[str, AggregatedMetric]):
        """Handle collected metrics from stats collector"""
        try:
            # Log aggregated metrics
            self.logging_integrator.log_aggregated_metrics(metrics)
            
        except Exception as e:
            self.logger.error(f"Error handling collected metrics: {e}")
    
    def _handle_alert(self, alert: Alert):
        """Handle alerts from diagnostic system"""
        try:
            # Log alert
            self.logging_integrator.log_alert(alert)
            
        except Exception as e:
            self.logger.error(f"Error handling alert: {e}")
    
    async def _health_logging_loop(self):
        """Health status logging loop"""
        while self._integration_active:
            try:
                if self.recovery_system:
                    # Get health status
                    health_results = await self.recovery_system.run_health_checks()
                    
                    # Log health status
                    self.logging_integrator.log_health_status(health_results)
                
                await asyncio.sleep(self.config.health_status_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health logging loop: {e}")
                await asyncio.sleep(self.config.health_status_interval)
    
    def log_pool_statistics(self, stats: PoolStats):
        """Manually log pool statistics"""
        self.logging_integrator.log_pool_statistics(stats)
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status"""
        return {
            'integration_active': self._integration_active,
            'config': {
                'structured_logging': self.config.enable_structured_logging,
                'metrics_export': self.config.export_to_json,
                'export_interval': self.config.export_metrics_interval,
                'health_logging_interval': self.config.health_status_interval
            },
            'components': {
                'pool_monitor': self.pool_monitor is not None,
                'stats_collector': self.stats_collector is not None,
                'diagnostic_system': self.diagnostic_system is not None,
                'recovery_system': self.recovery_system is not None
            },
            'export_active': self.metrics_exporter._export_active,
            'health_logging_active': self._health_logging_task is not None and not self._health_logging_task.done()
        }


# Factory function
def create_monitoring_integrator(config: Optional[MonitoringIntegrationConfig] = None) -> MonitoringSystemIntegrator:
    """Create monitoring system integrator"""
    return MonitoringSystemIntegrator(config)


@asynccontextmanager
async def integrated_monitoring_context(pool_monitor: ConnectionPoolMonitor,
                                      stats_collector: RealTimeStatsCollector,
                                      diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None,
                                      recovery_system: Optional[AutoRecoverySystem] = None,
                                      config: Optional[MonitoringIntegrationConfig] = None):
    """
    Context manager for integrated monitoring setup
    
    Automatically sets up and tears down monitoring integration
    """
    integrator = create_monitoring_integrator(config)
    
    try:
        await integrator.integrate_monitoring_stack(
            pool_monitor, stats_collector, diagnostic_system, recovery_system
        )
        yield integrator
    finally:
        await integrator.stop_integration()


# Default configuration factory
def create_default_integration_config() -> MonitoringIntegrationConfig:
    """Create default monitoring integration configuration"""
    return MonitoringIntegrationConfig(
        enable_structured_logging=True,
        log_to_dedicated_files=True,
        export_metrics_interval=60.0,
        export_to_json=True,
        forward_alerts_to_logging=True,
        health_status_interval=120.0
    )