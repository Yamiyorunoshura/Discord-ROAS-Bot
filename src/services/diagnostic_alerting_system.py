"""
Connection Pool Error Diagnosis and Alerting System
Task ID: T2 - High Concurrency Connection Competition Fix

This module provides comprehensive error diagnosis, root cause analysis,
and intelligent alerting for connection pool issues with automated
recovery recommendations.
"""

import asyncio
import json
import logging
import smtplib
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Union, Set
from collections import defaultdict, deque

from ..core.logging import get_logger
from .connection_pool_monitor import ConnectionPoolMonitor, PoolEvent, EventType, EventLevel, PoolStats
from .realtime_stats_collector import RealTimeStatsCollector, AggregatedMetric


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts"""
    PERFORMANCE_DEGRADATION = "performance_degradation"
    CONNECTION_EXHAUSTION = "connection_exhaustion"
    TIMEOUT_SPIKE = "timeout_spike"
    ERROR_RATE_HIGH = "error_rate_high"
    HEALTH_SCORE_LOW = "health_score_low"
    RESOURCE_CONTENTION = "resource_contention"
    DATABASE_LOCK = "database_lock"
    MEMORY_LEAK = "memory_leak"
    SYSTEM_OVERLOAD = "system_overload"


class DiagnosisCategory(Enum):
    """Categories of diagnoses"""
    CONFIGURATION = "configuration"
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    CONCURRENCY = "concurrency"
    DATABASE = "database"
    NETWORK = "network"
    SYSTEM = "system"


@dataclass
class Diagnosis:
    """Error diagnosis with root cause analysis"""
    category: DiagnosisCategory
    issue: str
    root_cause: str
    symptoms: List[str]
    evidence: Dict[str, Any]
    confidence_score: float  # 0.0 to 1.0
    recommendations: List[str]
    severity: AlertSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'category': self.category.value,
            'issue': self.issue,
            'root_cause': self.root_cause,
            'symptoms': self.symptoms,
            'evidence': self.evidence,
            'confidence_score': self.confidence_score,
            'recommendations': self.recommendations,
            'severity': self.severity.value,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class Alert:
    """System alert with diagnosis and actions"""
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    diagnosis: Optional[Diagnosis]
    metrics: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    acknowledgments: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'alert_type': self.alert_type.value,
            'severity': self.severity.value,
            'title': self.title,
            'message': self.message,
            'diagnosis': self.diagnosis.to_dict() if self.diagnosis else None,
            'metrics': self.metrics,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved,
            'resolution_time': self.resolution_time.isoformat() if self.resolution_time else None,
            'acknowledgments': self.acknowledgments
        }
    
    def acknowledge(self, acknowledger: str) -> None:
        """Acknowledge alert"""
        if acknowledger not in self.acknowledgments:
            self.acknowledgments.append(acknowledger)
    
    def resolve(self) -> None:
        """Mark alert as resolved"""
        self.resolved = True
        self.resolution_time = datetime.now()


class DiagnosticRule(ABC):
    """Base class for diagnostic rules"""
    
    def __init__(self, name: str, category: DiagnosisCategory, confidence_threshold: float = 0.7):
        self.name = name
        self.category = category
        self.confidence_threshold = confidence_threshold
    
    @abstractmethod
    def evaluate(self, 
                stats: Optional[PoolStats], 
                metrics: Dict[str, AggregatedMetric], 
                events: List[PoolEvent]) -> Optional[Diagnosis]:
        """Evaluate rule and return diagnosis if conditions are met"""
        pass


class HighConnectionTimeoutRule(DiagnosticRule):
    """Diagnose high connection timeout rates"""
    
    def __init__(self):
        super().__init__("High Connection Timeout", DiagnosisCategory.CONCURRENCY, 0.8)
    
    def evaluate(self, stats, metrics, events) -> Optional[Diagnosis]:
        # Check for high timeout events
        timeout_events = [e for e in events if e.event_type == EventType.CONNECTION_TIMEOUT]
        total_events = len([e for e in events if e.event_type in (EventType.CONNECTION_CREATED, EventType.CONNECTION_REUSED)])
        
        if total_events == 0:
            return None
        
        timeout_rate = len(timeout_events) / total_events
        
        if timeout_rate > 0.1:  # More than 10% timeout rate
            symptoms = [
                f"High connection timeout rate: {timeout_rate:.1%}",
                f"Total timeout events in monitoring period: {len(timeout_events)}"
            ]
            
            if stats:
                symptoms.append(f"Average wait time: {stats.average_wait_time_ms:.2f}ms")
                symptoms.append(f"Pool utilization: {stats.utilization_ratio:.1%}")
            
            return Diagnosis(
                category=self.category,
                issue="High connection timeout rate detected",
                root_cause="Pool exhaustion or database contention causing connection acquisition delays",
                symptoms=symptoms,
                evidence={
                    'timeout_rate': timeout_rate,
                    'timeout_events': len(timeout_events),
                    'total_events': total_events,
                    'recent_timeouts': [e.to_dict() for e in timeout_events[-5:]]
                },
                confidence_score=min(0.95, 0.5 + timeout_rate),
                recommendations=[
                    "Increase connection pool size",
                    "Review database query performance",
                    "Implement connection pooling optimization",
                    "Consider database connection limit tuning",
                    "Add connection queue monitoring"
                ],
                severity=AlertSeverity.HIGH if timeout_rate > 0.2 else AlertSeverity.MEDIUM
            )
        
        return None


class LowHealthScoreRule(DiagnosticRule):
    """Diagnose low pool health scores"""
    
    def __init__(self):
        super().__init__("Low Health Score", DiagnosisCategory.PERFORMANCE, 0.7)
    
    def evaluate(self, stats, metrics, events) -> Optional[Diagnosis]:
        if not stats:
            return None
        
        if stats.pool_health_score < 0.6:
            symptoms = [
                f"Pool health score: {stats.pool_health_score:.2f}",
                f"Average wait time: {stats.average_wait_time_ms:.2f}ms",
                f"Pool utilization: {stats.utilization_ratio:.1%}"
            ]
            
            # Analyze contributing factors
            contributing_factors = []
            if stats.average_wait_time_ms > 100:
                contributing_factors.append("High average wait time")
            if stats.utilization_ratio > 0.8:
                contributing_factors.append("High pool utilization")
            if stats.error_rate > 0.05:
                contributing_factors.append("Elevated error rate")
            
            return Diagnosis(
                category=self.category,
                issue="Pool health score below acceptable threshold",
                root_cause="Multiple performance factors degrading pool efficiency: " + ", ".join(contributing_factors),
                symptoms=symptoms,
                evidence={
                    'health_score': stats.pool_health_score,
                    'contributing_factors': contributing_factors,
                    'utilization': stats.utilization_ratio,
                    'wait_time': stats.average_wait_time_ms,
                    'error_rate': stats.error_rate
                },
                confidence_score=0.8,
                recommendations=[
                    "Optimize connection pool configuration",
                    "Review application connection usage patterns",
                    "Implement connection lifecycle monitoring",
                    "Consider pool size adjustments",
                    "Add performance profiling"
                ],
                severity=AlertSeverity.HIGH if stats.pool_health_score < 0.4 else AlertSeverity.MEDIUM
            )
        
        return None


class DatabaseLockContentionRule(DiagnosticRule):
    """Diagnose database lock contention issues"""
    
    def __init__(self):
        super().__init__("Database Lock Contention", DiagnosisCategory.DATABASE, 0.75)
    
    def evaluate(self, stats, metrics, events) -> Optional[Diagnosis]:
        # Look for patterns indicating lock contention
        error_events = [e for e in events if e.event_type == EventType.CONNECTION_ERROR]
        
        # Check for SQLite lock errors or high wait times
        lock_indicators = 0
        lock_evidence = []
        
        if stats and stats.average_wait_time_ms > 200:
            lock_indicators += 1
            lock_evidence.append(f"High average wait time: {stats.average_wait_time_ms:.2f}ms")
        
        # Check for database-related error messages
        for event in error_events[-20:]:  # Check recent errors
            if any(keyword in str(event.event_message).lower() for keyword in ['lock', 'busy', 'blocked', 'timeout']):
                lock_indicators += 1
                lock_evidence.append(f"Database lock error: {event.event_message}")
        
        if lock_indicators >= 2:
            return Diagnosis(
                category=self.category,
                issue="Database lock contention detected",
                root_cause="Concurrent operations causing SQLite lock conflicts and blocking connection acquisition",
                symptoms=[
                    "High connection wait times",
                    "Database lock errors in event log",
                    "Potential write-write conflicts"
                ] + lock_evidence,
                evidence={
                    'lock_indicators': lock_indicators,
                    'lock_evidence': lock_evidence,
                    'recent_errors': len(error_events),
                    'avg_wait_time': stats.average_wait_time_ms if stats else None
                },
                confidence_score=0.75,
                recommendations=[
                    "Enable WAL mode for better concurrency",
                    "Optimize transaction scope and duration",
                    "Implement proper retry mechanisms",
                    "Consider read-write separation",
                    "Add database performance monitoring"
                ],
                severity=AlertSeverity.HIGH
            )
        
        return None


class ConnectionPoolDiagnosticEngine:
    """
    Advanced diagnostic engine for connection pool issues
    
    Analyzes patterns, correlates events, and provides actionable insights
    with automated root cause analysis.
    """
    
    def __init__(self, pool_name: str = "default"):
        """
        Initialize diagnostic engine
        
        Args:
            pool_name: Name of the connection pool
        """
        self.pool_name = pool_name
        self.logger = get_logger(f"diagnostic_engine.{pool_name}")
        
        # Diagnostic rules
        self._rules: List[DiagnosticRule] = []
        self._initialize_rules()
        
        # Diagnosis history
        self._diagnosis_history: deque = deque(maxlen=1000)
        self._diagnosis_lock = threading.RLock()
        
        self.logger.info(f"Diagnostic engine initialized with {len(self._rules)} rules")
    
    def _initialize_rules(self) -> None:
        """Initialize diagnostic rules"""
        self._rules.extend([
            HighConnectionTimeoutRule(),
            LowHealthScoreRule(),
            DatabaseLockContentionRule()
        ])
    
    def add_rule(self, rule: DiagnosticRule) -> None:
        """Add custom diagnostic rule"""
        self._rules.append(rule)
        self.logger.info(f"Added diagnostic rule: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove diagnostic rule by name"""
        for i, rule in enumerate(self._rules):
            if rule.name == rule_name:
                del self._rules[i]
                self.logger.info(f"Removed diagnostic rule: {rule_name}")
                return True
        return False
    
    def diagnose(self, 
                stats: Optional[PoolStats],
                metrics: Dict[str, AggregatedMetric],
                events: List[PoolEvent]) -> List[Diagnosis]:
        """
        Perform comprehensive diagnosis
        
        Args:
            stats: Current pool statistics
            metrics: Aggregated metrics
            events: Recent events
            
        Returns:
            List of diagnoses ordered by confidence score
        """
        diagnoses = []
        
        for rule in self._rules:
            try:
                diagnosis = rule.evaluate(stats, metrics, events)
                if diagnosis:
                    diagnoses.append(diagnosis)
                    
            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule.name}: {e}")
        
        # Sort by confidence score (highest first)
        diagnoses.sort(key=lambda d: d.confidence_score, reverse=True)
        
        # Store in history
        with self._diagnosis_lock:
            self._diagnosis_history.extend(diagnoses)
        
        if diagnoses:
            self.logger.info(f"Generated {len(diagnoses)} diagnoses")
        
        return diagnoses
    
    def get_diagnosis_history(self, hours: int = 24) -> List[Diagnosis]:
        """Get diagnosis history"""
        since = datetime.now() - timedelta(hours=hours)
        
        with self._diagnosis_lock:
            return [d for d in self._diagnosis_history if d.timestamp >= since]


class AlertManager:
    """
    Alert management system with intelligent filtering and routing
    
    Manages alert lifecycle, deduplication, and notification routing
    with configurable escalation policies.
    """
    
    def __init__(self, pool_name: str = "default"):
        """Initialize alert manager"""
        self.pool_name = pool_name
        self.logger = get_logger(f"alert_manager.{pool_name}")
        
        # Alert storage
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: deque = deque(maxlen=10000)
        self._alerts_lock = threading.RLock()
        
        # Notification handlers
        self._notification_handlers: List[Callable[[Alert], None]] = []
        
        # Alert suppression
        self._suppression_rules: Dict[AlertType, timedelta] = {
            AlertType.PERFORMANCE_DEGRADATION: timedelta(minutes=5),
            AlertType.CONNECTION_EXHAUSTION: timedelta(minutes=2),
            AlertType.TIMEOUT_SPIKE: timedelta(minutes=3),
            AlertType.ERROR_RATE_HIGH: timedelta(minutes=5),
        }
        
        # Alert counters for rate limiting
        self._alert_counts: defaultdict = defaultdict(int)
        self._last_alert_time: defaultdict = defaultdict(lambda: datetime.min)
        
        self.logger.info("Alert manager initialized")
    
    def create_alert(self,
                    alert_type: AlertType,
                    severity: AlertSeverity,
                    title: str,
                    message: str,
                    diagnosis: Optional[Diagnosis] = None,
                    metrics: Optional[Dict[str, Any]] = None) -> Optional[Alert]:
        """
        Create and process new alert
        
        Args:
            alert_type: Type of alert
            severity: Alert severity
            title: Alert title
            message: Alert message
            diagnosis: Associated diagnosis
            metrics: Relevant metrics
            
        Returns:
            Created alert or None if suppressed
        """
        # Check suppression rules
        if self._should_suppress_alert(alert_type):
            self.logger.debug(f"Alert suppressed: {alert_type.value}")
            return None
        
        # Create alert
        alert_id = f"{alert_type.value}_{int(time.time())}"
        alert = Alert(
            id=alert_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            diagnosis=diagnosis,
            metrics=metrics or {}
        )
        
        with self._alerts_lock:
            self._active_alerts[alert_id] = alert
            self._alert_history.append(alert)
        
        # Update counters
        self._alert_counts[alert_type] += 1
        self._last_alert_time[alert_type] = datetime.now()
        
        # Send notifications
        self._send_notifications(alert)
        
        self.logger.info(f"Created {severity.value} alert: {title}")
        return alert
    
    def resolve_alert(self, alert_id: str, resolver: str = "system") -> bool:
        """Resolve an alert"""
        with self._alerts_lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.resolve()
                alert.acknowledge(resolver)
                del self._active_alerts[alert_id]
                
                self.logger.info(f"Resolved alert: {alert.title}")
                return True
        
        return False
    
    def acknowledge_alert(self, alert_id: str, acknowledger: str) -> bool:
        """Acknowledge an alert"""
        with self._alerts_lock:
            if alert_id in self._active_alerts:
                self._active_alerts[alert_id].acknowledge(acknowledger)
                self.logger.info(f"Alert acknowledged by {acknowledger}: {alert_id}")
                return True
        
        return False
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get active alerts"""
        with self._alerts_lock:
            alerts = list(self._active_alerts.values())
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history"""
        since = datetime.now() - timedelta(hours=hours)
        
        with self._alerts_lock:
            return [a for a in self._alert_history if a.timestamp >= since]
    
    def add_notification_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add notification handler"""
        self._notification_handlers.append(handler)
    
    def remove_notification_handler(self, handler: Callable[[Alert], None]) -> None:
        """Remove notification handler"""
        if handler in self._notification_handlers:
            self._notification_handlers.remove(handler)
    
    def _should_suppress_alert(self, alert_type: AlertType) -> bool:
        """Check if alert should be suppressed"""
        if alert_type not in self._suppression_rules:
            return False
        
        last_time = self._last_alert_time[alert_type]
        suppression_window = self._suppression_rules[alert_type]
        
        return datetime.now() - last_time < suppression_window
    
    def _send_notifications(self, alert: Alert) -> None:
        """Send alert notifications"""
        for handler in self._notification_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error(f"Error sending notification: {e}")
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary"""
        with self._alerts_lock:
            active_by_severity = defaultdict(int)
            for alert in self._active_alerts.values():
                active_by_severity[alert.severity.value] += 1
            
            return {
                'active_alerts': len(self._active_alerts),
                'active_by_severity': dict(active_by_severity),
                'total_alerts_24h': len(self.get_alert_history(24)),
                'alert_counts': dict(self._alert_counts)
            }


class ConnectionPoolDiagnosticSystem:
    """
    Integrated diagnostic and alerting system
    
    Combines diagnostic engine with alert management for comprehensive
    connection pool monitoring and issue resolution.
    """
    
    def __init__(self,
                 pool_monitor: ConnectionPoolMonitor,
                 stats_collector: RealTimeStatsCollector,
                 pool_name: str = "default"):
        """
        Initialize diagnostic system
        
        Args:
            pool_monitor: Pool monitor instance
            stats_collector: Stats collector instance
            pool_name: Pool name
        """
        self.pool_name = pool_name
        self.pool_monitor = pool_monitor
        self.stats_collector = stats_collector
        
        # Initialize components
        self.diagnostic_engine = ConnectionPoolDiagnosticEngine(pool_name)
        self.alert_manager = AlertManager(pool_name)
        
        self.logger = get_logger(f"diagnostic_system.{pool_name}")
        
        # Diagnostic state
        self._diagnostic_active = False
        self._diagnostic_task: Optional[asyncio.Task] = None
        self._diagnostic_interval = 60.0  # Run diagnostics every minute
        
        # Setup default notification handlers
        self._setup_default_handlers()
        
        self.logger.info("Diagnostic system initialized")
    
    def _setup_default_handlers(self) -> None:
        """Setup default notification handlers"""
        # Console logging handler
        def console_handler(alert: Alert):
            level = {
                AlertSeverity.LOW: logging.INFO,
                AlertSeverity.MEDIUM: logging.WARNING,
                AlertSeverity.HIGH: logging.ERROR,
                AlertSeverity.CRITICAL: logging.CRITICAL
            }.get(alert.severity, logging.WARNING)
            
            self.logger.log(level, f"ALERT [{alert.severity.value.upper()}]: {alert.title} - {alert.message}")
            
            if alert.diagnosis:
                self.logger.log(level, f"Root cause: {alert.diagnosis.root_cause}")
                self.logger.log(level, f"Recommendations: {'; '.join(alert.diagnosis.recommendations[:3])}")
        
        self.alert_manager.add_notification_handler(console_handler)
    
    async def start_diagnostics(self) -> None:
        """Start automated diagnostics"""
        if self._diagnostic_active:
            return
        
        self._diagnostic_active = True
        self._diagnostic_task = asyncio.create_task(self._diagnostic_loop())
        
        self.logger.info("Started automated diagnostics")
    
    async def stop_diagnostics(self) -> None:
        """Stop automated diagnostics"""
        if not self._diagnostic_active:
            return
        
        self._diagnostic_active = False
        
        if self._diagnostic_task:
            self._diagnostic_task.cancel()
            try:
                await self._diagnostic_task
            except asyncio.CancelledError:
                pass
            self._diagnostic_task = None
        
        self.logger.info("Stopped automated diagnostics")
    
    async def run_diagnostics(self) -> List[Diagnosis]:
        """Run diagnostics manually"""
        try:
            # Get current data
            current_stats = await self.pool_monitor.get_current_stats()
            recent_events = await self.pool_monitor.get_recent_events(hours=1)
            aggregated_metrics = self.stats_collector.get_aggregated_metrics()
            
            # Run diagnostics
            diagnoses = self.diagnostic_engine.diagnose(current_stats, aggregated_metrics, recent_events)
            
            # Create alerts for significant diagnoses
            for diagnosis in diagnoses:
                if diagnosis.confidence_score >= 0.7:
                    alert_type = self._diagnosis_to_alert_type(diagnosis)
                    
                    alert = self.alert_manager.create_alert(
                        alert_type=alert_type,
                        severity=diagnosis.severity,
                        title=diagnosis.issue,
                        message=diagnosis.root_cause,
                        diagnosis=diagnosis,
                        metrics={
                            'confidence_score': diagnosis.confidence_score,
                            'category': diagnosis.category.value
                        }
                    )
                    
                    if alert:
                        self.logger.info(f"Created alert for diagnosis: {diagnosis.issue}")
            
            return diagnoses
            
        except Exception as e:
            self.logger.error(f"Error running diagnostics: {e}")
            return []
    
    async def _diagnostic_loop(self) -> None:
        """Main diagnostic loop"""
        while self._diagnostic_active:
            try:
                await self.run_diagnostics()
                await asyncio.sleep(self._diagnostic_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in diagnostic loop: {e}")
                await asyncio.sleep(self._diagnostic_interval)
    
    def _diagnosis_to_alert_type(self, diagnosis: Diagnosis) -> AlertType:
        """Convert diagnosis to alert type"""
        category_mapping = {
            DiagnosisCategory.PERFORMANCE: AlertType.PERFORMANCE_DEGRADATION,
            DiagnosisCategory.CONCURRENCY: AlertType.CONNECTION_EXHAUSTION,
            DiagnosisCategory.DATABASE: AlertType.DATABASE_LOCK,
            DiagnosisCategory.RESOURCE: AlertType.SYSTEM_OVERLOAD
        }
        
        return category_mapping.get(diagnosis.category, AlertType.PERFORMANCE_DEGRADATION)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        active_alerts = self.alert_manager.get_active_alerts()
        recent_diagnoses = self.diagnostic_engine.get_diagnosis_history(1)
        
        # Calculate health score
        health_score = 1.0
        
        # Penalize for active alerts
        critical_alerts = len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL])
        high_alerts = len([a for a in active_alerts if a.severity == AlertSeverity.HIGH])
        
        health_score -= critical_alerts * 0.3
        health_score -= high_alerts * 0.15
        health_score = max(0.0, health_score)
        
        # Determine status
        if health_score >= 0.8:
            status = "healthy"
        elif health_score >= 0.6:
            status = "warning"
        elif health_score >= 0.3:
            status = "degraded"
        else:
            status = "critical"
        
        return {
            'status': status,
            'health_score': health_score,
            'active_alerts': len(active_alerts),
            'critical_alerts': critical_alerts,
            'high_alerts': high_alerts,
            'recent_diagnoses': len(recent_diagnoses),
            'diagnostic_active': self._diagnostic_active
        }


# Factory function
def create_diagnostic_system(pool_monitor: ConnectionPoolMonitor,
                           stats_collector: RealTimeStatsCollector,
                           pool_name: str = "default") -> ConnectionPoolDiagnosticSystem:
    """Create integrated diagnostic system"""
    return ConnectionPoolDiagnosticSystem(pool_monitor, stats_collector, pool_name)