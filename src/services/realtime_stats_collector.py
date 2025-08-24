"""
Real-time Statistics Collection System
Task ID: T2 - High Concurrency Connection Competition Fix

This module provides real-time statistics collection and aggregation
for connection pool metrics, supporting high-frequency data collection
with minimal performance impact.
"""

import asyncio
import time
import threading
from typing import Dict, List, Optional, Callable, Any, NamedTuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
from contextlib import contextmanager
from enum import Enum
import statistics

from ..core.logging import get_logger
from .connection_pool_monitor import ConnectionPoolMonitor, PoolStats, EventType, EventLevel


class MetricType(Enum):
    """Types of metrics that can be collected"""
    COUNTER = "counter"           # Cumulative value (e.g., total requests)
    GAUGE = "gauge"              # Point-in-time value (e.g., active connections)
    HISTOGRAM = "histogram"      # Distribution of values (e.g., response times)
    TIMER = "timer"             # Time duration measurements


class TimeWindow(Enum):
    """Time window sizes for aggregation"""
    SECOND = 1
    MINUTE = 60
    FIVE_MINUTES = 300
    HOUR = 3600
    DAY = 86400


@dataclass
class MetricSample:
    """Individual metric sample"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass 
class AggregatedMetric:
    """Aggregated metric over a time window"""
    name: str
    metric_type: MetricType
    window: TimeWindow
    timestamp: float
    count: int
    sum: float
    min: float
    max: float
    avg: float
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)


class MetricCollector:
    """
    High-performance metric collector for real-time statistics
    
    Collects metrics with minimal overhead and provides
    configurable aggregation windows.
    """
    
    def __init__(self, name: str, metric_type: MetricType, max_samples: int = 10000):
        """
        Initialize metric collector
        
        Args:
            name: Metric name
            metric_type: Type of metric
            max_samples: Maximum number of samples to keep in memory
        """
        self.name = name
        self.metric_type = metric_type
        self.max_samples = max_samples
        
        # Sample storage
        self._samples: deque = deque(maxlen=max_samples)
        self._samples_lock = threading.RLock()
        
        # Current values for gauges
        self._current_value: Optional[float] = None
        self._counter_value: float = 0.0
        
        # Labels
        self._default_labels: Dict[str, str] = {}
    
    def record(self, value: float, labels: Optional[Dict[str, str]] = None, timestamp: Optional[float] = None) -> None:
        """Record a metric sample"""
        if timestamp is None:
            timestamp = time.time()
        
        sample_labels = {**self._default_labels}
        if labels:
            sample_labels.update(labels)
        
        sample = MetricSample(timestamp, value, sample_labels)
        
        with self._samples_lock:
            # Update current values based on metric type
            if self.metric_type == MetricType.GAUGE:
                self._current_value = value
            elif self.metric_type == MetricType.COUNTER:
                self._counter_value += value
            
            # Store sample
            self._samples.append(sample)
    
    def increment(self, delta: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment counter (for COUNTER metrics)"""
        if self.metric_type != MetricType.COUNTER:
            raise ValueError("Increment only supported for COUNTER metrics")
        self.record(delta, labels)
    
    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set gauge value (for GAUGE metrics)"""
        if self.metric_type != MetricType.GAUGE:
            raise ValueError("Set only supported for GAUGE metrics")
        self.record(value, labels)
    
    def time(self, labels: Optional[Dict[str, str]] = None):
        """Context manager for timing operations (for TIMER/HISTOGRAM metrics)"""
        if self.metric_type not in (MetricType.TIMER, MetricType.HISTOGRAM):
            raise ValueError("Time only supported for TIMER/HISTOGRAM metrics")
        
        @contextmanager
        def timer():
            start_time = time.time()
            try:
                yield
            finally:
                duration = (time.time() - start_time) * 1000  # Convert to milliseconds
                self.record(duration, labels)
        
        return timer()
    
    def get_samples(self, since: Optional[float] = None) -> List[MetricSample]:
        """Get samples since timestamp"""
        with self._samples_lock:
            if since is None:
                return list(self._samples)
            
            return [s for s in self._samples if s.timestamp >= since]
    
    def get_current_value(self) -> Optional[float]:
        """Get current value for gauges"""
        if self.metric_type == MetricType.GAUGE:
            return self._current_value
        elif self.metric_type == MetricType.COUNTER:
            return self._counter_value
        return None
    
    def aggregate(self, window: TimeWindow, since: Optional[float] = None) -> Optional[AggregatedMetric]:
        """Aggregate samples over time window"""
        if since is None:
            since = time.time() - window.value
        
        samples = self.get_samples(since)
        if not samples:
            return None
        
        values = [s.value for s in samples]
        
        # Calculate aggregations
        count = len(values)
        sum_val = sum(values)
        min_val = min(values)
        max_val = max(values)
        avg_val = sum_val / count
        
        # Calculate percentiles for histogram/timer metrics
        p50, p95, p99 = 0.0, 0.0, 0.0
        if self.metric_type in (MetricType.HISTOGRAM, MetricType.TIMER) and values:
            sorted_values = sorted(values)
            p50 = statistics.median(sorted_values)
            p95 = sorted_values[int(0.95 * len(sorted_values))] if len(sorted_values) > 1 else sorted_values[0]
            p99 = sorted_values[int(0.99 * len(sorted_values))] if len(sorted_values) > 1 else sorted_values[0]
        
        return AggregatedMetric(
            name=self.name,
            metric_type=self.metric_type,
            window=window,
            timestamp=time.time(),
            count=count,
            sum=sum_val,
            min=min_val,
            max=max_val,
            avg=avg_val,
            p50=p50,
            p95=p95,
            p99=p99,
            labels=samples[0].labels if samples else {}
        )
    
    def clear(self) -> None:
        """Clear all samples"""
        with self._samples_lock:
            self._samples.clear()
            self._current_value = None
            self._counter_value = 0.0


class RealTimeStatsCollector:
    """
    Real-time statistics collection system
    
    Manages multiple metric collectors and provides aggregated views
    of system performance with minimal overhead.
    """
    
    def __init__(self, 
                 pool_name: str = "default",
                 collection_interval: float = 1.0,
                 enable_auto_collection: bool = True):
        """
        Initialize real-time stats collector
        
        Args:
            pool_name: Name of the connection pool
            collection_interval: Interval between automatic collections (seconds)
            enable_auto_collection: Enable automatic metric collection
        """
        self.pool_name = pool_name
        self.collection_interval = collection_interval
        self.enable_auto_collection = enable_auto_collection
        
        # Initialize logger
        self.logger = get_logger(f"stats_collector.{pool_name}")
        
        # Metric collectors
        self._collectors: Dict[str, MetricCollector] = {}
        self._collectors_lock = threading.RLock()
        
        # Collection state
        self._collecting = False
        self._collection_task: Optional[asyncio.Task] = None
        self._collection_callbacks: List[Callable[[Dict[str, AggregatedMetric]], None]] = []
        
        # Initialize default metrics
        self._initialize_default_metrics()
        
        self.logger.info(f"Real-time stats collector initialized for pool '{pool_name}'")
    
    def _initialize_default_metrics(self) -> None:
        """Initialize default connection pool metrics"""
        # Connection metrics
        self.register_metric("connections.active", MetricType.GAUGE)
        self.register_metric("connections.idle", MetricType.GAUGE)
        self.register_metric("connections.pending", MetricType.GAUGE)
        self.register_metric("connections.total", MetricType.GAUGE)
        
        # Request metrics
        self.register_metric("requests.total", MetricType.COUNTER)
        self.register_metric("requests.successful", MetricType.COUNTER)
        self.register_metric("requests.failed", MetricType.COUNTER)
        self.register_metric("requests.duration", MetricType.HISTOGRAM)
        
        # Pool metrics
        self.register_metric("pool.utilization", MetricType.GAUGE)
        self.register_metric("pool.health_score", MetricType.GAUGE)
        self.register_metric("pool.wait_time", MetricType.HISTOGRAM)
        
        # System metrics
        self.register_metric("system.memory_usage", MetricType.GAUGE)
        self.register_metric("system.cpu_usage", MetricType.GAUGE)
    
    def register_metric(self, name: str, metric_type: MetricType, max_samples: int = 10000) -> MetricCollector:
        """Register a new metric collector"""
        with self._collectors_lock:
            if name in self._collectors:
                return self._collectors[name]
            
            collector = MetricCollector(name, metric_type, max_samples)
            self._collectors[name] = collector
            
            self.logger.debug(f"Registered metric: {name} ({metric_type.value})")
            return collector
    
    def get_metric(self, name: str) -> Optional[MetricCollector]:
        """Get metric collector by name"""
        with self._collectors_lock:
            return self._collectors.get(name)
    
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a metric value"""
        collector = self.get_metric(name)
        if collector:
            collector.record(value, labels)
        else:
            self.logger.warning(f"Metric not found: {name}")
    
    def increment_counter(self, name: str, delta: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric"""
        collector = self.get_metric(name)
        if collector and collector.metric_type == MetricType.COUNTER:
            collector.increment(delta, labels)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric"""
        collector = self.get_metric(name)
        if collector and collector.metric_type == MetricType.GAUGE:
            collector.set(value, labels)
    
    def time_operation(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager for timing operations"""
        collector = self.get_metric(name)
        if collector and collector.metric_type in (MetricType.TIMER, MetricType.HISTOGRAM):
            return collector.time(labels)
        else:
            # Return no-op context manager if metric not found
            @contextmanager
            def noop():
                yield
            return noop()
    
    def collect_pool_stats(self, stats: PoolStats) -> None:
        """Collect statistics from pool stats object"""
        # Connection metrics
        self.set_gauge("connections.active", stats.active_connections)
        self.set_gauge("connections.idle", stats.idle_connections)
        self.set_gauge("connections.pending", stats.pending_connections)
        self.set_gauge("connections.total", stats.active_connections + stats.idle_connections)
        
        # Pool metrics
        self.set_gauge("pool.utilization", stats.utilization_ratio)
        self.set_gauge("pool.health_score", stats.pool_health_score)
        
        # Request metrics (increment by new requests since last collection)
        # Note: This requires tracking previous values to calculate deltas
        self.record_metric("requests.duration", stats.average_wait_time_ms)
        self.record_metric("pool.wait_time", stats.average_wait_time_ms)
        
        # System metrics
        self.set_gauge("system.memory_usage", stats.memory_usage_bytes)
        self.set_gauge("system.cpu_usage", stats.cpu_usage_percent)
    
    def get_aggregated_metrics(self, window: TimeWindow = TimeWindow.MINUTE) -> Dict[str, AggregatedMetric]:
        """Get aggregated metrics for all collectors"""
        aggregated = {}
        
        with self._collectors_lock:
            for name, collector in self._collectors.items():
                metric = collector.aggregate(window)
                if metric:
                    aggregated[name] = metric
        
        return aggregated
    
    def get_current_snapshot(self) -> Dict[str, float]:
        """Get current snapshot of all metrics"""
        snapshot = {}
        
        with self._collectors_lock:
            for name, collector in self._collectors.items():
                value = collector.get_current_value()
                if value is not None:
                    snapshot[name] = value
        
        return snapshot
    
    def add_collection_callback(self, callback: Callable[[Dict[str, AggregatedMetric]], None]) -> None:
        """Add callback for collection events"""
        self._collection_callbacks.append(callback)
    
    def remove_collection_callback(self, callback: Callable[[Dict[str, AggregatedMetric]], None]) -> None:
        """Remove collection callback"""
        if callback in self._collection_callbacks:
            self._collection_callbacks.remove(callback)
    
    async def start_collection(self) -> None:
        """Start automatic metric collection"""
        if self._collecting or not self.enable_auto_collection:
            return
        
        self._collecting = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        
        self.logger.info("Started real-time stats collection")
    
    async def stop_collection(self) -> None:
        """Stop automatic metric collection"""
        if not self._collecting:
            return
        
        self._collecting = False
        
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
            self._collection_task = None
        
        self.logger.info("Stopped real-time stats collection")
    
    async def _collection_loop(self) -> None:
        """Main collection loop"""
        while self._collecting:
            try:
                # Collect aggregated metrics
                aggregated = self.get_aggregated_metrics(TimeWindow.MINUTE)
                
                # Notify callbacks
                for callback in self._collection_callbacks:
                    try:
                        callback(aggregated)
                    except Exception as e:
                        self.logger.error(f"Error in collection callback: {e}")
                
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in collection loop: {e}")
                await asyncio.sleep(self.collection_interval)
    
    def clear_all_metrics(self) -> None:
        """Clear all metric data"""
        with self._collectors_lock:
            for collector in self._collectors.values():
                collector.clear()
        
        self.logger.info("Cleared all metrics")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        summary = {
            'pool_name': self.pool_name,
            'collection_interval': self.collection_interval,
            'collecting': self._collecting,
            'metrics': {}
        }
        
        # Get current snapshot
        snapshot = self.get_current_snapshot()
        
        # Get aggregated data for different windows
        minute_data = self.get_aggregated_metrics(TimeWindow.MINUTE)
        hour_data = self.get_aggregated_metrics(TimeWindow.HOUR)
        
        with self._collectors_lock:
            for name, collector in self._collectors.items():
                metric_info = {
                    'type': collector.metric_type.value,
                    'current': snapshot.get(name),
                    'sample_count': len(collector._samples),
                    'minute_avg': minute_data.get(name).avg if minute_data.get(name) else None,
                    'hour_avg': hour_data.get(name).avg if hour_data.get(name) else None
                }
                summary['metrics'][name] = metric_info
        
        return summary


class ConnectionPoolStatsIntegrator:
    """
    Integrator that connects connection pool monitoring with real-time stats collection
    
    Provides seamless integration between pool monitoring and metrics collection.
    """
    
    def __init__(self, 
                 pool_monitor: ConnectionPoolMonitor,
                 stats_collector: RealTimeStatsCollector):
        """
        Initialize integrator
        
        Args:
            pool_monitor: Connection pool monitor instance
            stats_collector: Real-time stats collector instance
        """
        self.pool_monitor = pool_monitor
        self.stats_collector = stats_collector
        self.logger = get_logger("pool_stats_integrator")
        
        # Set up integration
        self._setup_integration()
    
    def _setup_integration(self) -> None:
        """Set up integration between monitor and collector"""
        # Add event handler for pool events
        self.pool_monitor.add_event_handler(self._handle_pool_event)
        
        # Add collection callback for aggregated metrics
        self.stats_collector.add_collection_callback(self._handle_collected_metrics)
        
        self.logger.info("Pool stats integration set up")
    
    def _handle_pool_event(self, event) -> None:
        """Handle pool monitor events"""
        # Convert events to metrics
        if event.event_type == EventType.CONNECTION_CREATED:
            self.stats_collector.increment_counter("connections.created")
        elif event.event_type == EventType.CONNECTION_DESTROYED:
            self.stats_collector.increment_counter("connections.destroyed")
        elif event.event_type == EventType.CONNECTION_TIMEOUT:
            self.stats_collector.increment_counter("connections.timeouts")
        elif event.event_type == EventType.CONNECTION_ERROR:
            self.stats_collector.increment_counter("connections.errors")
        elif event.event_type == EventType.PERFORMANCE_ALERT:
            self.stats_collector.increment_counter("alerts.performance")
    
    def _handle_collected_metrics(self, aggregated_metrics: Dict[str, AggregatedMetric]) -> None:
        """Handle collected aggregated metrics"""
        # Log performance summary
        if "requests.duration" in aggregated_metrics:
            duration_metric = aggregated_metrics["requests.duration"]
            self.logger.info(
                f"Request performance - Avg: {duration_metric.avg:.2f}ms, "
                f"P95: {duration_metric.p95:.2f}ms, P99: {duration_metric.p99:.2f}ms"
            )
        
        if "pool.utilization" in aggregated_metrics:
            util_metric = aggregated_metrics["pool.utilization"]
            self.logger.info(f"Pool utilization - Avg: {util_metric.avg:.1%}")


# Factory functions
def create_stats_collector(pool_name: str = "default",
                          collection_interval: float = 1.0,
                          enable_auto_collection: bool = True) -> RealTimeStatsCollector:
    """Create a real-time stats collector"""
    return RealTimeStatsCollector(pool_name, collection_interval, enable_auto_collection)


def create_integrated_monitoring(db_path: str,
                               pool_name: str = "default",
                               monitoring_interval: float = 60.0,
                               collection_interval: float = 1.0) -> tuple[ConnectionPoolMonitor, RealTimeStatsCollector, ConnectionPoolStatsIntegrator]:
    """
    Create integrated monitoring solution
    
    Returns:
        Tuple of (pool_monitor, stats_collector, integrator)
    """
    # Import here to avoid circular imports
    from .connection_pool_monitor import create_pool_monitor
    
    pool_monitor = create_pool_monitor(db_path, pool_name, monitoring_interval)
    stats_collector = create_stats_collector(pool_name, collection_interval)
    integrator = ConnectionPoolStatsIntegrator(pool_monitor, stats_collector)
    
    return pool_monitor, stats_collector, integrator