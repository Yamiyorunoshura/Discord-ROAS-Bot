"""
Concurrent Testing Infrastructure Configuration
Task ID: T2 - High Concurrency Connection Competition Fix

This module provides infrastructure configuration and setup for
comprehensive concurrent testing of connection pool performance
under various load scenarios.
"""

import asyncio
import json
import os
import tempfile
import time
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from contextlib import asynccontextmanager
import concurrent.futures
import threading
import psutil

from ..core.logging import get_logger
from ..db.sqlite import SQLiteConnectionFactory
from .connection_pool_monitor import create_pool_monitor
from .realtime_stats_collector import create_stats_collector
from .diagnostic_alerting_system import create_diagnostic_system


@dataclass
class ConcurrencyTestConfig:
    """Configuration for concurrency testing"""
    test_name: str
    worker_count: int
    duration_seconds: int
    operations_per_worker: int
    database_path: str
    
    # Connection pool configuration
    max_pool_size: int = 20
    connection_timeout_ms: int = 30000
    
    # Test parameters
    read_write_ratio: float = 0.7  # 70% reads, 30% writes
    think_time_ms: int = 10  # Delay between operations
    ramp_up_seconds: int = 5  # Gradual worker startup
    
    # Monitoring configuration
    enable_monitoring: bool = True
    monitoring_interval_seconds: float = 1.0
    detailed_logging: bool = False
    
    # Resource limits
    max_memory_mb: int = 512
    max_cpu_percent: float = 80.0
    
    # Output configuration
    results_directory: str = "test_results"
    generate_reports: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'test_name': self.test_name,
            'worker_count': self.worker_count,
            'duration_seconds': self.duration_seconds,
            'operations_per_worker': self.operations_per_worker,
            'database_path': self.database_path,
            'max_pool_size': self.max_pool_size,
            'connection_timeout_ms': self.connection_timeout_ms,
            'read_write_ratio': self.read_write_ratio,
            'think_time_ms': self.think_time_ms,
            'ramp_up_seconds': self.ramp_up_seconds,
            'enable_monitoring': self.enable_monitoring,
            'monitoring_interval_seconds': self.monitoring_interval_seconds,
            'detailed_logging': self.detailed_logging,
            'max_memory_mb': self.max_memory_mb,
            'max_cpu_percent': self.max_cpu_percent,
            'results_directory': self.results_directory,
            'generate_reports': self.generate_reports
        }


@dataclass
class TestEnvironment:
    """Test environment setup and configuration"""
    config: ConcurrencyTestConfig
    base_directory: Path
    database_path: Path
    monitoring_db_path: Path
    temp_directory: Path
    results_directory: Path
    
    # Infrastructure components
    connection_factory: Optional[SQLiteConnectionFactory] = None
    pool_monitor: Optional[Any] = None  # ConnectionPoolMonitor
    stats_collector: Optional[Any] = None  # RealTimeStatsCollector
    diagnostic_system: Optional[Any] = None  # ConnectionPoolDiagnosticSystem
    
    def cleanup(self):
        """Clean up test environment"""
        if self.temp_directory.exists():
            shutil.rmtree(self.temp_directory)


class ConcurrentTestInfrastructure:
    """
    Infrastructure manager for concurrent testing
    
    Provides isolated test environments with monitoring,
    resource management, and automated cleanup.
    """
    
    def __init__(self, base_config: Optional[ConcurrencyTestConfig] = None):
        """
        Initialize test infrastructure
        
        Args:
            base_config: Base configuration for testing
        """
        self.base_config = base_config or self._default_config()
        self.logger = get_logger("concurrent_test_infrastructure")
        
        # Environment management
        self._active_environments: Dict[str, TestEnvironment] = {}
        self._environment_lock = threading.RLock()
        
        # Resource monitoring
        self._resource_monitor_task: Optional[asyncio.Task] = None
        self._monitoring_active = False
        
        self.logger.info("Concurrent test infrastructure initialized")
    
    def _default_config(self) -> ConcurrencyTestConfig:
        """Create default test configuration"""
        return ConcurrencyTestConfig(
            test_name="default_concurrency_test",
            worker_count=10,
            duration_seconds=60,
            operations_per_worker=100,
            database_path="test_concurrent.db"
        )
    
    @asynccontextmanager
    async def create_test_environment(self, config: Optional[ConcurrencyTestConfig] = None):
        """
        Create isolated test environment
        
        Args:
            config: Test configuration (uses base_config if None)
        """
        if config is None:
            config = self.base_config
        
        environment_id = f"{config.test_name}_{int(time.time())}"
        
        try:
            # Create environment
            environment = await self._setup_environment(environment_id, config)
            
            with self._environment_lock:
                self._active_environments[environment_id] = environment
            
            self.logger.info(f"Created test environment: {environment_id}")
            
            yield environment
            
        finally:
            # Cleanup environment
            await self._cleanup_environment(environment_id)
    
    async def _setup_environment(self, environment_id: str, config: ConcurrencyTestConfig) -> TestEnvironment:
        """Setup test environment with all components"""
        
        # Create directories
        base_dir = Path(tempfile.mkdtemp(prefix=f"concurrent_test_{environment_id}_"))
        temp_dir = base_dir / "temp"
        results_dir = base_dir / config.results_directory
        
        temp_dir.mkdir(exist_ok=True)
        results_dir.mkdir(exist_ok=True)
        
        # Database paths
        db_path = temp_dir / config.database_path
        monitoring_db_path = temp_dir / f"monitoring_{config.database_path}"
        
        # Create environment object
        environment = TestEnvironment(
            config=config,
            base_directory=base_dir,
            database_path=db_path,
            monitoring_db_path=monitoring_db_path,
            temp_directory=temp_dir,
            results_directory=results_dir
        )
        
        # Initialize database
        await self._initialize_test_database(environment)
        
        # Setup monitoring infrastructure if enabled
        if config.enable_monitoring:
            await self._setup_monitoring_infrastructure(environment)
        
        # Save configuration
        config_path = results_dir / "test_config.json"
        with open(config_path, 'w') as f:
            json.dump(config.to_dict(), f, indent=2)
        
        self.logger.info(f"Test environment setup complete: {environment_id}")
        return environment
    
    async def _initialize_test_database(self, environment: TestEnvironment):
        """Initialize test database with schema and data"""
        config = environment.config
        
        # Create connection factory
        environment.connection_factory = SQLiteConnectionFactory(
            str(environment.database_path),
            timeout=config.connection_timeout_ms / 1000.0
        )
        
        # Create test schema
        conn = environment.connection_factory.get_connection()
        
        # Create test tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data TEXT,
                processing_time_ms REAL
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_counters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                counter_name TEXT UNIQUE NOT NULL,
                counter_value INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indices for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_test_data_worker ON test_data(worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_test_data_timestamp ON test_data(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_test_data_type ON test_data(operation_type)")
        
        # Initialize counters
        conn.execute("INSERT OR IGNORE INTO test_counters (counter_name, counter_value) VALUES ('total_operations', 0)")
        conn.execute("INSERT OR IGNORE INTO test_counters (counter_name, counter_value) VALUES ('read_operations', 0)")
        conn.execute("INSERT OR IGNORE INTO test_counters (counter_name, counter_value) VALUES ('write_operations', 0)")
        
        # Seed some initial data
        for i in range(100):
            conn.execute("""
                INSERT INTO test_data (worker_id, operation_type, data) 
                VALUES (?, 'seed', ?)
            """, (f"seed_worker", f"Initial test data record {i}"))
        
        conn.commit()
        
        self.logger.info(f"Test database initialized: {environment.database_path}")
    
    async def _setup_monitoring_infrastructure(self, environment: TestEnvironment):
        """Setup monitoring infrastructure for the environment"""
        config = environment.config
        
        try:
            # Create monitoring components
            environment.pool_monitor = create_pool_monitor(
                str(environment.monitoring_db_path),
                "test_pool",
                config.monitoring_interval_seconds,
                config.detailed_logging
            )
            
            environment.stats_collector = create_stats_collector(
                "test_pool",
                config.monitoring_interval_seconds,
                True  # Enable auto-collection
            )
            
            environment.diagnostic_system = create_diagnostic_system(
                environment.pool_monitor,
                environment.stats_collector,
                "test_pool"
            )
            
            # Initialize monitoring
            await environment.pool_monitor.start_monitoring()
            await environment.stats_collector.start_collection()
            await environment.diagnostic_system.start_diagnostics()
            
            self.logger.info("Monitoring infrastructure setup complete")
            
        except Exception as e:
            self.logger.error(f"Failed to setup monitoring infrastructure: {e}")
            # Continue without monitoring rather than failing completely
            environment.pool_monitor = None
            environment.stats_collector = None
            environment.diagnostic_system = None
    
    async def _cleanup_environment(self, environment_id: str):
        """Cleanup test environment"""
        with self._environment_lock:
            if environment_id not in self._active_environments:
                return
            
            environment = self._active_environments[environment_id]
            
            try:
                # Stop monitoring components
                if environment.pool_monitor:
                    await environment.pool_monitor.stop_monitoring()
                
                if environment.stats_collector:
                    await environment.stats_collector.stop_collection()
                
                if environment.diagnostic_system:
                    await environment.diagnostic_system.stop_diagnostics()
                
                # Close connection factory
                if environment.connection_factory:
                    environment.connection_factory.close_all_connections()
                
                # Cleanup filesystem
                environment.cleanup()
                
                self.logger.info(f"Cleaned up test environment: {environment_id}")
                
            except Exception as e:
                self.logger.error(f"Error during environment cleanup: {e}")
            
            finally:
                del self._active_environments[environment_id]
    
    def create_concurrency_test_scenarios(self) -> List[ConcurrencyTestConfig]:
        """Create predefined concurrency test scenarios"""
        base_db_path = "test_concurrent.db"
        
        scenarios = [
            # Light load
            ConcurrencyTestConfig(
                test_name="light_load",
                worker_count=5,
                duration_seconds=30,
                operations_per_worker=50,
                database_path=base_db_path,
                max_pool_size=10,
                read_write_ratio=0.8
            ),
            
            # Medium load
            ConcurrencyTestConfig(
                test_name="medium_load",
                worker_count=10,
                duration_seconds=60,
                operations_per_worker=100,
                database_path=base_db_path,
                max_pool_size=15,
                read_write_ratio=0.7
            ),
            
            # High load
            ConcurrencyTestConfig(
                test_name="high_load",
                worker_count=15,
                duration_seconds=120,
                operations_per_worker=200,
                database_path=base_db_path,
                max_pool_size=20,
                read_write_ratio=0.6
            ),
            
            # Extreme load
            ConcurrencyTestConfig(
                test_name="extreme_load",
                worker_count=25,
                duration_seconds=180,
                operations_per_worker=300,
                database_path=base_db_path,
                max_pool_size=20,
                read_write_ratio=0.5,
                think_time_ms=5  # Faster operations
            ),
            
            # Write-heavy scenario
            ConcurrencyTestConfig(
                test_name="write_heavy",
                worker_count=10,
                duration_seconds=60,
                operations_per_worker=100,
                database_path=base_db_path,
                max_pool_size=15,
                read_write_ratio=0.3  # 30% reads, 70% writes
            ),
            
            # Burst scenario
            ConcurrencyTestConfig(
                test_name="burst_scenario",
                worker_count=20,
                duration_seconds=30,
                operations_per_worker=50,
                database_path=base_db_path,
                max_pool_size=20,
                ramp_up_seconds=1,  # Fast ramp up
                think_time_ms=1     # Minimal think time
            )
        ]
        
        return scenarios
    
    async def start_resource_monitoring(self):
        """Start system resource monitoring"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._resource_monitor_task = asyncio.create_task(self._resource_monitor_loop())
        
        self.logger.info("Started system resource monitoring")
    
    async def stop_resource_monitoring(self):
        """Stop system resource monitoring"""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        
        if self._resource_monitor_task:
            self._resource_monitor_task.cancel()
            try:
                await self._resource_monitor_task
            except asyncio.CancelledError:
                pass
            self._resource_monitor_task = None
        
        self.logger.info("Stopped system resource monitoring")
    
    async def _resource_monitor_loop(self):
        """Monitor system resources during testing"""
        while self._monitoring_active:
            try:
                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                
                # Log resource usage
                self.logger.debug(f"System resources - CPU: {cpu_percent:.1f}%, "
                                f"Memory: {memory.percent:.1f}%, "
                                f"Available Memory: {memory.available / 1024**2:.1f} MB")
                
                # Check resource limits
                with self._environment_lock:
                    for env_id, environment in self._active_environments.items():
                        config = environment.config
                        
                        if cpu_percent > config.max_cpu_percent:
                            self.logger.warning(f"High CPU usage in environment {env_id}: {cpu_percent:.1f}%")
                        
                        if memory.percent > 90:  # System-wide memory warning
                            self.logger.warning(f"High system memory usage: {memory.percent:.1f}%")
                
                await asyncio.sleep(5)  # Monitor every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(5)
    
    def get_active_environments(self) -> Dict[str, TestEnvironment]:
        """Get currently active test environments"""
        with self._environment_lock:
            return dict(self._active_environments)
    
    def get_infrastructure_status(self) -> Dict[str, Any]:
        """Get infrastructure status"""
        with self._environment_lock:
            return {
                'active_environments': len(self._active_environments),
                'environment_ids': list(self._active_environments.keys()),
                'resource_monitoring_active': self._monitoring_active,
                'system_resources': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'available_memory_mb': psutil.virtual_memory().available / 1024**2,
                    'disk_usage_percent': psutil.disk_usage('/').percent
                }
            }


class TestInfrastructureManager:
    """
    High-level manager for test infrastructure lifecycle
    
    Provides simplified interface for managing multiple test environments
    with automated setup, execution, and cleanup.
    """
    
    def __init__(self):
        """Initialize test infrastructure manager"""
        self.logger = get_logger("test_infrastructure_manager")
        self.infrastructure = ConcurrentTestInfrastructure()
        
        # Test execution state
        self._running_tests: Dict[str, asyncio.Task] = {}
        self._test_results: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("Test infrastructure manager initialized")
    
    async def setup_standard_test_environments(self) -> Dict[str, TestEnvironment]:
        """Setup standard test environments for common scenarios"""
        scenarios = self.infrastructure.create_concurrency_test_scenarios()
        environments = {}
        
        for scenario in scenarios:
            env_context = self.infrastructure.create_test_environment(scenario)
            environment = await env_context.__aenter__()
            environments[scenario.test_name] = environment
        
        self.logger.info(f"Setup {len(environments)} standard test environments")
        return environments
    
    async def run_infrastructure_validation(self) -> Dict[str, Any]:
        """Run infrastructure validation tests"""
        validation_results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'overall_status': 'unknown',
            'issues': []
        }
        
        try:
            # Test 1: Basic environment creation
            basic_config = ConcurrencyTestConfig(
                test_name="validation_basic",
                worker_count=2,
                duration_seconds=10,
                operations_per_worker=10,
                database_path="validation_test.db"
            )
            
            async with self.infrastructure.create_test_environment(basic_config) as env:
                validation_results['tests']['environment_creation'] = {
                    'status': 'pass',
                    'message': 'Environment created successfully'
                }
                
                # Test 2: Database connectivity
                try:
                    conn = env.connection_factory.get_connection()
                    cursor = conn.execute("SELECT 1")
                    result = cursor.fetchone()
                    
                    validation_results['tests']['database_connectivity'] = {
                        'status': 'pass',
                        'message': 'Database connection successful'
                    }
                except Exception as e:
                    validation_results['tests']['database_connectivity'] = {
                        'status': 'fail',
                        'message': f'Database connection failed: {e}'
                    }
                    validation_results['issues'].append('Database connectivity issue')
                
                # Test 3: Monitoring infrastructure
                if env.pool_monitor and env.stats_collector:
                    validation_results['tests']['monitoring_infrastructure'] = {
                        'status': 'pass',
                        'message': 'Monitoring infrastructure operational'
                    }
                else:
                    validation_results['tests']['monitoring_infrastructure'] = {
                        'status': 'fail',
                        'message': 'Monitoring infrastructure not available'
                    }
                    validation_results['issues'].append('Monitoring infrastructure issue')
            
            # Determine overall status
            test_statuses = [test['status'] for test in validation_results['tests'].values()]
            if all(status == 'pass' for status in test_statuses):
                validation_results['overall_status'] = 'pass'
            elif any(status == 'fail' for status in test_statuses):
                validation_results['overall_status'] = 'fail'
            else:
                validation_results['overall_status'] = 'partial'
            
        except Exception as e:
            validation_results['overall_status'] = 'error'
            validation_results['issues'].append(f'Validation error: {e}')
            self.logger.error(f"Infrastructure validation failed: {e}")
        
        self.logger.info(f"Infrastructure validation completed: {validation_results['overall_status']}")
        return validation_results
    
    async def cleanup_all_environments(self):
        """Cleanup all active environments"""
        active_envs = self.infrastructure.get_active_environments()
        
        for env_id in list(active_envs.keys()):
            await self.infrastructure._cleanup_environment(env_id)
        
        self.logger.info("All test environments cleaned up")
    
    def get_manager_status(self) -> Dict[str, Any]:
        """Get manager status"""
        infrastructure_status = self.infrastructure.get_infrastructure_status()
        
        return {
            'infrastructure': infrastructure_status,
            'running_tests': len(self._running_tests),
            'completed_tests': len(self._test_results),
            'test_results_available': list(self._test_results.keys())
        }


# Factory functions
def create_test_infrastructure(base_config: Optional[ConcurrencyTestConfig] = None) -> ConcurrentTestInfrastructure:
    """Create test infrastructure instance"""
    return ConcurrentTestInfrastructure(base_config)


def create_infrastructure_manager() -> TestInfrastructureManager:
    """Create test infrastructure manager"""
    return TestInfrastructureManager()


# Configuration templates
def get_default_test_configs() -> Dict[str, ConcurrencyTestConfig]:
    """Get default test configuration templates"""
    infrastructure = ConcurrentTestInfrastructure()
    scenarios = infrastructure.create_concurrency_test_scenarios()
    
    return {scenario.test_name: scenario for scenario in scenarios}


async def validate_test_infrastructure() -> Dict[str, Any]:
    """Validate test infrastructure setup"""
    manager = create_infrastructure_manager()
    return await manager.run_infrastructure_validation()