"""
Auto Recovery and Health Check System
Task ID: T2 - High Concurrency Connection Competition Fix

This module provides intelligent health monitoring with automated
recovery mechanisms for connection pool issues, ensuring system
resilience and self-healing capabilities.
"""

import asyncio
import json
import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from collections import deque

from ..core.logging import get_logger
from ..db.sqlite import SQLiteConnectionFactory
from .connection_pool_monitor import ConnectionPoolMonitor, PoolStats, EventType, EventLevel
from .realtime_stats_collector import RealTimeStatsCollector, AggregatedMetric
from .diagnostic_alerting_system import ConnectionPoolDiagnosticSystem, Alert, AlertSeverity


class HealthStatus(Enum):
    """System health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """Types of recovery actions"""
    RESTART_CONNECTIONS = "restart_connections"
    CLEAR_POOL = "clear_pool"
    RESIZE_POOL = "resize_pool"
    OPTIMIZE_DATABASE = "optimize_database"
    RESET_STATISTICS = "reset_statistics"
    FORCE_CHECKPOINT = "force_checkpoint"
    RESTART_MONITORING = "restart_monitoring"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    component: str
    status: HealthStatus
    score: float  # 0.0 to 1.0
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'component': self.component,
            'status': self.status.value,
            'score': self.score,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt"""
    action: RecoveryAction
    trigger_reason: str
    timestamp: datetime
    success: bool
    duration_seconds: float
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'action': self.action.value,
            'trigger_reason': self.trigger_reason,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success,
            'duration_seconds': self.duration_seconds,
            'error_message': self.error_message,
            'details': self.details
        }


class HealthChecker(ABC):
    """Base class for health check components"""
    
    def __init__(self, name: str, check_interval: float = 30.0):
        """
        Initialize health checker
        
        Args:
            name: Name of the component being checked
            check_interval: Interval between checks in seconds
        """
        self.name = name
        self.check_interval = check_interval
        self.logger = get_logger(f"health_checker.{name}")
    
    @abstractmethod
    async def check_health(self) -> HealthCheckResult:
        """Perform health check and return result"""
        pass
    
    def calculate_status_from_score(self, score: float) -> HealthStatus:
        """Convert numeric score to status"""
        if score >= 0.9:
            return HealthStatus.HEALTHY
        elif score >= 0.7:
            return HealthStatus.WARNING
        elif score >= 0.4:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.CRITICAL


class ConnectionPoolHealthChecker(HealthChecker):
    """Health checker for connection pool"""
    
    def __init__(self, 
                 connection_factory: SQLiteConnectionFactory,
                 pool_monitor: Optional[ConnectionPoolMonitor] = None):
        """
        Initialize connection pool health checker
        
        Args:
            connection_factory: Connection factory to check
            pool_monitor: Optional pool monitor for additional metrics
        """
        super().__init__("connection_pool", 30.0)
        self.connection_factory = connection_factory
        self.pool_monitor = pool_monitor
    
    async def check_health(self) -> HealthCheckResult:
        """Check connection pool health"""
        try:
            start_time = time.time()
            score = 1.0
            issues = []
            details = {}
            
            # Test 1: Basic connectivity
            try:
                conn = self.connection_factory.get_connection()
                cursor = conn.execute("SELECT 1")
                result = cursor.fetchone()
                
                if not result or result[0] != 1:
                    score -= 0.5
                    issues.append("Basic connectivity test failed")
                
                details['connectivity_test'] = 'pass'
                
            except Exception as e:
                score -= 0.8
                issues.append(f"Connectivity failure: {e}")
                details['connectivity_test'] = 'fail'
            
            # Test 2: Connection pool statistics
            pool_stats = self.connection_factory.get_connection_stats()
            active_connections = pool_stats.get('active_connections', 0)
            total_connections = pool_stats.get('total_connections', 0)
            
            details['pool_stats'] = pool_stats
            
            # Check for excessive connections
            if total_connections > 25:  # Arbitrary threshold
                score -= 0.2
                issues.append(f"High number of connections: {total_connections}")
            
            # Test 3: Performance check
            perf_start = time.time()
            try:
                conn = self.connection_factory.get_connection()
                cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                cursor.fetchone()
                performance_time = (time.time() - perf_start) * 1000  # Convert to ms
                
                details['performance_test_ms'] = performance_time
                
                if performance_time > 100:  # Slow response
                    score -= 0.1
                    issues.append(f"Slow response time: {performance_time:.2f}ms")
                
            except Exception as e:
                score -= 0.3
                issues.append(f"Performance test failed: {e}")
                details['performance_test'] = 'fail'
            
            # Test 4: Pool monitor integration
            if self.pool_monitor:
                try:
                    current_stats = await self.pool_monitor.get_current_stats()
                    if current_stats:
                        details['pool_monitor_stats'] = current_stats.to_dict()
                        
                        # Check pool health score
                        if current_stats.pool_health_score < 0.7:
                            score -= 0.2
                            issues.append(f"Low pool health score: {current_stats.pool_health_score:.2f}")
                        
                        # Check error rate
                        if current_stats.error_rate > 0.05:  # More than 5% errors
                            score -= 0.3
                            issues.append(f"High error rate: {current_stats.error_rate:.1%}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to get pool monitor stats: {e}")
            
            # Determine final status
            total_time = time.time() - start_time
            details['check_duration_seconds'] = total_time
            
            status = self.calculate_status_from_score(score)
            message = f"Connection pool health check completed with score {score:.2f}"
            
            if issues:
                message += f". Issues: {'; '.join(issues)}"
            
            return HealthCheckResult(
                component=self.name,
                status=status,
                score=score,
                message=message,
                details=details
            )
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                score=0.0,
                message=f"Health check failed: {e}",
                details={'error': str(e)}
            )


class DatabaseHealthChecker(HealthChecker):
    """Health checker for database integrity and performance"""
    
    def __init__(self, connection_factory: SQLiteConnectionFactory):
        """Initialize database health checker"""
        super().__init__("database", 60.0)
        self.connection_factory = connection_factory
    
    async def check_health(self) -> HealthCheckResult:
        """Check database health"""
        try:
            score = 1.0
            issues = []
            details = {}
            
            conn = self.connection_factory.get_connection()
            
            # Test 1: Database integrity check
            try:
                cursor = conn.execute("PRAGMA integrity_check")
                integrity_result = cursor.fetchone()
                
                if integrity_result and integrity_result[0] != 'ok':
                    score -= 0.5
                    issues.append(f"Database integrity issue: {integrity_result[0]}")
                
                details['integrity_check'] = integrity_result[0] if integrity_result else 'unknown'
                
            except Exception as e:
                score -= 0.6
                issues.append(f"Integrity check failed: {e}")
                details['integrity_check'] = 'failed'
            
            # Test 2: WAL mode check
            try:
                cursor = conn.execute("PRAGMA journal_mode")
                journal_mode = cursor.fetchone()
                
                details['journal_mode'] = journal_mode[0] if journal_mode else 'unknown'
                
                if not journal_mode or journal_mode[0].lower() != 'wal':
                    score -= 0.1
                    issues.append(f"Not using WAL mode: {journal_mode[0] if journal_mode else 'unknown'}")
                
            except Exception as e:
                self.logger.warning(f"Failed to check journal mode: {e}")
            
            # Test 3: Database size and fragmentation
            try:
                cursor = conn.execute("PRAGMA page_count")
                page_count = cursor.fetchone()
                cursor = conn.execute("PRAGMA page_size")
                page_size = cursor.fetchone()
                cursor = conn.execute("PRAGMA freelist_count")
                freelist_count = cursor.fetchone()
                
                if page_count and page_size and freelist_count:
                    total_pages = page_count[0]
                    free_pages = freelist_count[0]
                    fragmentation = (free_pages / total_pages) if total_pages > 0 else 0
                    
                    details['database_stats'] = {
                        'page_count': total_pages,
                        'page_size': page_size[0],
                        'free_pages': free_pages,
                        'fragmentation_ratio': fragmentation,
                        'size_bytes': total_pages * page_size[0]
                    }
                    
                    # High fragmentation warning
                    if fragmentation > 0.2:  # More than 20% fragmentation
                        score -= 0.1
                        issues.append(f"High database fragmentation: {fragmentation:.1%}")
                
            except Exception as e:
                self.logger.warning(f"Failed to get database stats: {e}")
            
            # Test 4: Foreign key constraints
            try:
                cursor = conn.execute("PRAGMA foreign_keys")
                fk_enabled = cursor.fetchone()
                
                details['foreign_keys_enabled'] = bool(fk_enabled[0]) if fk_enabled else False
                
                if not fk_enabled or not fk_enabled[0]:
                    score -= 0.05
                    issues.append("Foreign key constraints not enabled")
                
            except Exception as e:
                self.logger.warning(f"Failed to check foreign keys: {e}")
            
            # Determine status
            status = self.calculate_status_from_score(score)
            message = f"Database health check completed with score {score:.2f}"
            
            if issues:
                message += f". Issues: {'; '.join(issues)}"
            
            return HealthCheckResult(
                component=self.name,
                status=status,
                score=score,
                message=message,
                details=details
            )
            
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.CRITICAL,
                score=0.0,
                message=f"Database health check failed: {e}",
                details={'error': str(e)}
            )


class RecoveryExecutor:
    """Executes recovery actions when health issues are detected"""
    
    def __init__(self, 
                 connection_factory: SQLiteConnectionFactory,
                 pool_monitor: Optional[ConnectionPoolMonitor] = None,
                 stats_collector: Optional[RealTimeStatsCollector] = None):
        """
        Initialize recovery executor
        
        Args:
            connection_factory: Connection factory for database operations
            pool_monitor: Optional pool monitor
            stats_collector: Optional stats collector
        """
        self.connection_factory = connection_factory
        self.pool_monitor = pool_monitor
        self.stats_collector = stats_collector
        
        self.logger = get_logger("recovery_executor")
        
        # Recovery history
        self._recovery_history: deque = deque(maxlen=1000)
        self._recovery_lock = threading.RLock()
        
        # Recovery cooldowns to prevent excessive recovery attempts
        self._recovery_cooldowns: Dict[RecoveryAction, timedelta] = {
            RecoveryAction.RESTART_CONNECTIONS: timedelta(minutes=2),
            RecoveryAction.CLEAR_POOL: timedelta(minutes=5),
            RecoveryAction.RESIZE_POOL: timedelta(minutes=10),
            RecoveryAction.OPTIMIZE_DATABASE: timedelta(hours=1),
            RecoveryAction.FORCE_CHECKPOINT: timedelta(minutes=15),
        }
        
        self._last_recovery_time: Dict[RecoveryAction, datetime] = {}
    
    async def execute_recovery(self, action: RecoveryAction, reason: str) -> RecoveryAttempt:
        """Execute recovery action"""
        
        # Check cooldown
        if self._is_recovery_on_cooldown(action):
            self.logger.info(f"Recovery action {action.value} is on cooldown")
            return RecoveryAttempt(
                action=action,
                trigger_reason=reason,
                timestamp=datetime.now(),
                success=False,
                duration_seconds=0.0,
                error_message="Recovery action on cooldown"
            )
        
        start_time = time.time()
        attempt = RecoveryAttempt(
            action=action,
            trigger_reason=reason,
            timestamp=datetime.now(),
            success=False,
            duration_seconds=0.0
        )
        
        try:
            self.logger.info(f"Executing recovery action: {action.value} - Reason: {reason}")
            
            if action == RecoveryAction.RESTART_CONNECTIONS:
                await self._restart_connections()
            elif action == RecoveryAction.CLEAR_POOL:
                await self._clear_pool()
            elif action == RecoveryAction.RESIZE_POOL:
                await self._resize_pool()
            elif action == RecoveryAction.OPTIMIZE_DATABASE:
                await self._optimize_database()
            elif action == RecoveryAction.RESET_STATISTICS:
                await self._reset_statistics()
            elif action == RecoveryAction.FORCE_CHECKPOINT:
                await self._force_checkpoint()
            elif action == RecoveryAction.RESTART_MONITORING:
                await self._restart_monitoring()
            else:
                raise ValueError(f"Unsupported recovery action: {action}")
            
            attempt.success = True
            attempt.duration_seconds = time.time() - start_time
            
            # Update cooldown
            self._last_recovery_time[action] = datetime.now()
            
            self.logger.info(f"Recovery action {action.value} completed successfully in {attempt.duration_seconds:.2f}s")
            
        except Exception as e:
            attempt.success = False
            attempt.duration_seconds = time.time() - start_time
            attempt.error_message = str(e)
            
            self.logger.error(f"Recovery action {action.value} failed: {e}")
        
        # Store attempt in history
        with self._recovery_lock:
            self._recovery_history.append(attempt)
        
        return attempt
    
    def _is_recovery_on_cooldown(self, action: RecoveryAction) -> bool:
        """Check if recovery action is on cooldown"""
        if action not in self._recovery_cooldowns:
            return False
        
        last_time = self._last_recovery_time.get(action, datetime.min)
        cooldown_period = self._recovery_cooldowns[action]
        
        return datetime.now() - last_time < cooldown_period
    
    async def _restart_connections(self):
        """Restart all connections in the pool"""
        self.connection_factory.close_all_connections()
        
        # Test new connection
        conn = self.connection_factory.get_connection()
        cursor = conn.execute("SELECT 1")
        cursor.fetchone()
    
    async def _clear_pool(self):
        """Clear connection pool and statistics"""
        self.connection_factory.close_all_connections()
        
        if self.stats_collector:
            self.stats_collector.clear_all_metrics()
    
    async def _resize_pool(self):
        """Resize connection pool (placeholder - actual implementation would depend on pool implementation)"""
        # This would require pool size configuration capability
        # For now, just restart connections
        await self._restart_connections()
    
    async def _optimize_database(self):
        """Optimize database by running VACUUM and ANALYZE"""
        conn = self.connection_factory.get_connection()
        
        # Run VACUUM to defragment
        conn.execute("VACUUM")
        
        # Run ANALYZE to update statistics
        conn.execute("ANALYZE")
        
        conn.commit()
    
    async def _reset_statistics(self):
        """Reset monitoring statistics"""
        if self.stats_collector:
            self.stats_collector.clear_all_metrics()
    
    async def _force_checkpoint(self):
        """Force WAL checkpoint"""
        conn = self.connection_factory.get_connection()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    
    async def _restart_monitoring(self):
        """Restart monitoring components"""
        if self.pool_monitor:
            await self.pool_monitor.stop_monitoring()
            await asyncio.sleep(1)  # Brief pause
            await self.pool_monitor.start_monitoring()
        
        if self.stats_collector:
            await self.stats_collector.stop_collection()
            await asyncio.sleep(1)  # Brief pause
            await self.stats_collector.start_collection()
    
    def get_recovery_history(self, hours: int = 24) -> List[RecoveryAttempt]:
        """Get recovery history"""
        since = datetime.now() - timedelta(hours=hours)
        
        with self._recovery_lock:
            return [attempt for attempt in self._recovery_history if attempt.timestamp >= since]


class AutoRecoverySystem:
    """
    Automated health monitoring and recovery system
    
    Continuously monitors system health and automatically
    executes recovery actions when issues are detected.
    """
    
    def __init__(self,
                 connection_factory: SQLiteConnectionFactory,
                 pool_monitor: Optional[ConnectionPoolMonitor] = None,
                 stats_collector: Optional[RealTimeStatsCollector] = None,
                 diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None):
        """
        Initialize auto recovery system
        
        Args:
            connection_factory: Connection factory
            pool_monitor: Optional pool monitor
            stats_collector: Optional stats collector
            diagnostic_system: Optional diagnostic system
        """
        self.connection_factory = connection_factory
        self.pool_monitor = pool_monitor
        self.stats_collector = stats_collector
        self.diagnostic_system = diagnostic_system
        
        self.logger = get_logger("auto_recovery_system")
        
        # Health checkers
        self._health_checkers: List[HealthChecker] = []
        self._initialize_health_checkers()
        
        # Recovery executor
        self.recovery_executor = RecoveryExecutor(
            connection_factory, pool_monitor, stats_collector
        )
        
        # Auto recovery state
        self._auto_recovery_active = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval = 30.0  # Check every 30 seconds
        
        # Health history
        self._health_history: deque = deque(maxlen=10000)
        self._health_lock = threading.RLock()
        
        # Recovery rules
        self._recovery_rules = self._initialize_recovery_rules()
        
        self.logger.info("Auto recovery system initialized")
    
    def _initialize_health_checkers(self):
        """Initialize health check components"""
        self._health_checkers = [
            ConnectionPoolHealthChecker(self.connection_factory, self.pool_monitor),
            DatabaseHealthChecker(self.connection_factory)
        ]
    
    def _initialize_recovery_rules(self) -> Dict[str, Tuple[RecoveryAction, float]]:
        """Initialize recovery rules mapping conditions to actions"""
        return {
            # Condition: (Recovery Action, Threshold Score)
            "connection_pool_critical": (RecoveryAction.RESTART_CONNECTIONS, 0.3),
            "connection_pool_degraded": (RecoveryAction.CLEAR_POOL, 0.4),
            "database_critical": (RecoveryAction.OPTIMIZE_DATABASE, 0.3),
            "database_degraded": (RecoveryAction.FORCE_CHECKPOINT, 0.5),
            "performance_issues": (RecoveryAction.RESET_STATISTICS, 0.6)
        }
    
    async def start_auto_recovery(self):
        """Start automated health monitoring and recovery"""
        if self._auto_recovery_active:
            return
        
        self._auto_recovery_active = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        self.logger.info("Started automated health monitoring and recovery")
    
    async def stop_auto_recovery(self):
        """Stop automated recovery"""
        if not self._auto_recovery_active:
            return
        
        self._auto_recovery_active = False
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        self.logger.info("Stopped automated health monitoring and recovery")
    
    async def run_health_checks(self) -> List[HealthCheckResult]:
        """Run all health checks manually"""
        results = []
        
        for checker in self._health_checkers:
            try:
                result = await checker.check_health()
                results.append(result)
                
            except Exception as e:
                self.logger.error(f"Health checker {checker.name} failed: {e}")
                results.append(HealthCheckResult(
                    component=checker.name,
                    status=HealthStatus.CRITICAL,
                    score=0.0,
                    message=f"Health checker failed: {e}"
                ))
        
        # Store results in history
        with self._health_lock:
            self._health_history.extend(results)
        
        return results
    
    async def _health_check_loop(self):
        """Main health check loop"""
        while self._auto_recovery_active:
            try:
                # Run health checks
                health_results = await self.run_health_checks()
                
                # Analyze results and trigger recovery if needed
                await self._analyze_health_and_recover(health_results)
                
                await asyncio.sleep(self._health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self._health_check_interval)
    
    async def _analyze_health_and_recover(self, health_results: List[HealthCheckResult]):
        """Analyze health results and trigger recovery if needed"""
        for result in health_results:
            # Check if recovery is needed
            recovery_needed = self._should_trigger_recovery(result)
            
            if recovery_needed:
                action, reason = recovery_needed
                
                # Execute recovery
                recovery_attempt = await self.recovery_executor.execute_recovery(action, reason)
                
                if recovery_attempt.success:
                    self.logger.info(f"Successful recovery: {action.value} for {result.component}")
                else:
                    self.logger.error(f"Failed recovery: {action.value} for {result.component}")
    
    def _should_trigger_recovery(self, result: HealthCheckResult) -> Optional[Tuple[RecoveryAction, str]]:
        """Determine if recovery should be triggered based on health result"""
        
        # Critical status always triggers recovery
        if result.status == HealthStatus.CRITICAL:
            if result.component == "connection_pool":
                return RecoveryAction.RESTART_CONNECTIONS, f"Critical connection pool health: {result.message}"
            elif result.component == "database":
                return RecoveryAction.OPTIMIZE_DATABASE, f"Critical database health: {result.message}"
        
        # Degraded status may trigger recovery
        elif result.status == HealthStatus.DEGRADED:
            if result.component == "connection_pool" and result.score < 0.5:
                return RecoveryAction.CLEAR_POOL, f"Degraded connection pool performance: {result.message}"
            elif result.component == "database" and result.score < 0.6:
                return RecoveryAction.FORCE_CHECKPOINT, f"Degraded database performance: {result.message}"
        
        return None
    
    def get_system_health_overview(self) -> Dict[str, Any]:
        """Get comprehensive system health overview"""
        # Get recent health results
        recent_results = self.get_recent_health_results(hours=1)
        
        # Calculate overall health
        if not recent_results:
            overall_status = HealthStatus.UNKNOWN
            overall_score = 0.0
        else:
            scores = [r.score for r in recent_results]
            overall_score = sum(scores) / len(scores)
            
            # Determine overall status based on worst component
            worst_status = min([r.status for r in recent_results], 
                             key=lambda s: ['healthy', 'warning', 'degraded', 'critical', 'unknown'].index(s.value))
            overall_status = worst_status
        
        # Get recovery history
        recent_recoveries = self.recovery_executor.get_recovery_history(hours=24)
        successful_recoveries = [r for r in recent_recoveries if r.success]
        failed_recoveries = [r for r in recent_recoveries if not r.success]
        
        return {
            'overall_status': overall_status.value,
            'overall_score': overall_score,
            'auto_recovery_active': self._auto_recovery_active,
            'components': {r.component: {
                'status': r.status.value,
                'score': r.score,
                'message': r.message,
                'last_check': r.timestamp.isoformat()
            } for r in recent_results},
            'recent_recoveries': {
                'total': len(recent_recoveries),
                'successful': len(successful_recoveries),
                'failed': len(failed_recoveries),
                'recent_actions': [r.action.value for r in recent_recoveries[-5:]]
            },
            'health_check_interval': self._health_check_interval
        }
    
    def get_recent_health_results(self, hours: int = 1) -> List[HealthCheckResult]:
        """Get recent health check results"""
        since = datetime.now() - timedelta(hours=hours)
        
        with self._health_lock:
            return [result for result in self._health_history if result.timestamp >= since]
    
    def add_health_checker(self, checker: HealthChecker):
        """Add custom health checker"""
        self._health_checkers.append(checker)
        self.logger.info(f"Added health checker: {checker.name}")
    
    def remove_health_checker(self, name: str) -> bool:
        """Remove health checker by name"""
        for i, checker in enumerate(self._health_checkers):
            if checker.name == name:
                del self._health_checkers[i]
                self.logger.info(f"Removed health checker: {name}")
                return True
        return False


# Factory functions
def create_auto_recovery_system(connection_factory: SQLiteConnectionFactory,
                               pool_monitor: Optional[ConnectionPoolMonitor] = None,
                               stats_collector: Optional[RealTimeStatsCollector] = None,
                               diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None) -> AutoRecoverySystem:
    """Create auto recovery system"""
    return AutoRecoverySystem(connection_factory, pool_monitor, stats_collector, diagnostic_system)


async def validate_auto_recovery_system(recovery_system: AutoRecoverySystem) -> Dict[str, Any]:
    """Validate auto recovery system functionality"""
    validation_results = {
        'timestamp': datetime.now().isoformat(),
        'tests': {},
        'overall_status': 'unknown'
    }
    
    try:
        # Test health checks
        health_results = await recovery_system.run_health_checks()
        validation_results['tests']['health_checks'] = {
            'status': 'pass' if health_results else 'fail',
            'component_count': len(health_results),
            'results': [r.to_dict() for r in health_results]
        }
        
        # Test recovery executor (safe recovery action)
        recovery_attempt = await recovery_system.recovery_executor.execute_recovery(
            RecoveryAction.RESET_STATISTICS,
            "Validation test"
        )
        
        validation_results['tests']['recovery_executor'] = {
            'status': 'pass' if recovery_attempt.success else 'fail',
            'attempt': recovery_attempt.to_dict()
        }
        
        # Overall status
        test_results = [test['status'] for test in validation_results['tests'].values()]
        validation_results['overall_status'] = 'pass' if all(r == 'pass' for r in test_results) else 'fail'
        
    except Exception as e:
        validation_results['overall_status'] = 'error'
        validation_results['error'] = str(e)
    
    return validation_results