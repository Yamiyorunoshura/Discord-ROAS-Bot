"""
Connection Pool Infrastructure Integration
Task ID: T2 - High Concurrency Connection Competition Fix

This module provides a comprehensive integration layer that orchestrates
all connection pool infrastructure components, offering a unified interface
for complete monitoring, diagnostics, and recovery capabilities.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from ..core.logging import get_logger
from ..db.sqlite import SQLiteConnectionFactory, get_connection_factory
from .connection_pool_monitor import create_pool_monitor, ConnectionPoolMonitor
from .realtime_stats_collector import create_stats_collector, RealTimeStatsCollector
from .diagnostic_alerting_system import create_diagnostic_system, ConnectionPoolDiagnosticSystem
from .auto_recovery_system import create_auto_recovery_system, AutoRecoverySystem
from .concurrent_test_infrastructure import create_infrastructure_manager, TestInfrastructureManager
from .monitoring_integration import create_monitoring_integrator, MonitoringSystemIntegrator, MonitoringIntegrationConfig
from .monitoring_dashboard import create_monitoring_dashboard, DashboardServer, DashboardConfig


@dataclass
class InfrastructureConfig:
    """Complete infrastructure configuration"""
    
    # Database configuration
    database_path: str = "roas_bot.db"
    monitoring_db_path: Optional[str] = None  # Auto-generated if None
    
    # Pool monitoring configuration
    pool_name: str = "default"
    monitoring_interval: float = 60.0
    detailed_logging: bool = False
    
    # Stats collection configuration
    stats_collection_interval: float = 1.0
    enable_auto_collection: bool = True
    
    # Auto recovery configuration
    enable_auto_recovery: bool = True
    health_check_interval: float = 30.0
    
    # Integration configuration
    enable_monitoring_integration: bool = True
    integration_config: Optional[MonitoringIntegrationConfig] = None
    
    # Dashboard configuration
    enable_dashboard: bool = True
    dashboard_config: Optional[DashboardConfig] = None
    
    # Testing infrastructure
    enable_test_infrastructure: bool = True
    
    def __post_init__(self):
        """Post-initialization setup"""
        if self.monitoring_db_path is None:
            base_path = Path(self.database_path)
            self.monitoring_db_path = str(base_path.with_name(f"{base_path.stem}_monitoring.db"))
        
        if self.integration_config is None:
            self.integration_config = MonitoringIntegrationConfig()
        
        if self.dashboard_config is None:
            self.dashboard_config = DashboardConfig()


class ConnectionPoolInfrastructure:
    """
    Complete connection pool infrastructure orchestrator
    
    Provides unified management of all monitoring, diagnostics, recovery,
    and testing infrastructure components with simplified configuration
    and lifecycle management.
    """
    
    def __init__(self, config: Optional[InfrastructureConfig] = None):
        """
        Initialize connection pool infrastructure
        
        Args:
            config: Infrastructure configuration
        """
        self.config = config or InfrastructureConfig()
        self.logger = get_logger("pool_infrastructure")
        
        # Core components
        self.connection_factory: Optional[SQLiteConnectionFactory] = None
        self.pool_monitor: Optional[ConnectionPoolMonitor] = None
        self.stats_collector: Optional[RealTimeStatsCollector] = None
        self.diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None
        self.recovery_system: Optional[AutoRecoverySystem] = None
        
        # Integration components
        self.monitoring_integrator: Optional[MonitoringSystemIntegrator] = None
        self.dashboard_server: Optional[DashboardServer] = None
        self.test_infrastructure: Optional[TestInfrastructureManager] = None
        
        # Lifecycle state
        self._initialized = False
        self._started = False
        
        self.logger.info("Connection pool infrastructure initialized")
    
    async def initialize(self) -> None:
        """Initialize all infrastructure components"""
        if self._initialized:
            self.logger.warning("Infrastructure already initialized")
            return
        
        try:
            self.logger.info("Initializing connection pool infrastructure...")
            
            # 1. Initialize database connection factory
            self.connection_factory = get_connection_factory(self.config.database_path)
            self.logger.info(f"Database connection factory initialized: {self.config.database_path}")
            
            # 2. Initialize pool monitor
            self.pool_monitor = create_pool_monitor(
                self.config.monitoring_db_path,
                self.config.pool_name,
                self.config.monitoring_interval,
                self.config.detailed_logging
            )
            self.logger.info("Pool monitor initialized")
            
            # 3. Initialize stats collector
            self.stats_collector = create_stats_collector(
                self.config.pool_name,
                self.config.stats_collection_interval,
                self.config.enable_auto_collection
            )
            self.logger.info("Stats collector initialized")
            
            # 4. Initialize diagnostic system
            self.diagnostic_system = create_diagnostic_system(
                self.pool_monitor,
                self.stats_collector,
                self.config.pool_name
            )
            self.logger.info("Diagnostic system initialized")
            
            # 5. Initialize auto recovery system
            if self.config.enable_auto_recovery:
                self.recovery_system = create_auto_recovery_system(
                    self.connection_factory,
                    self.pool_monitor,
                    self.stats_collector,
                    self.diagnostic_system
                )
                self.logger.info("Auto recovery system initialized")
            
            # 6. Initialize monitoring integration
            if self.config.enable_monitoring_integration:
                self.monitoring_integrator = create_monitoring_integrator(
                    self.config.integration_config
                )
                self.logger.info("Monitoring integrator initialized")
            
            # 7. Initialize dashboard
            if self.config.enable_dashboard:
                self.dashboard_server, _ = create_monitoring_dashboard(
                    self.pool_monitor,
                    self.stats_collector,
                    self.diagnostic_system,
                    self.recovery_system,
                    self.config.dashboard_config
                )
                self.logger.info("Dashboard server initialized")
            
            # 8. Initialize test infrastructure
            if self.config.enable_test_infrastructure:
                self.test_infrastructure = TestInfrastructureManager()
                self.logger.info("Test infrastructure manager initialized")
            
            self._initialized = True
            self.logger.info("✅ Connection pool infrastructure initialization completed")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize infrastructure: {e}")
            raise
    
    async def start(self) -> None:
        """Start all infrastructure services"""
        if not self._initialized:
            await self.initialize()
        
        if self._started:
            self.logger.warning("Infrastructure already started")
            return
        
        try:
            self.logger.info("Starting connection pool infrastructure services...")
            
            # 1. Start pool monitor
            if self.pool_monitor:
                await self.pool_monitor.start_monitoring()
                self.logger.info("✅ Pool monitor started")
            
            # 2. Start stats collector
            if self.stats_collector:
                await self.stats_collector.start_collection()
                self.logger.info("✅ Stats collector started")
            
            # 3. Start diagnostic system
            if self.diagnostic_system:
                await self.diagnostic_system.start_diagnostics()
                self.logger.info("✅ Diagnostic system started")
            
            # 4. Start auto recovery
            if self.recovery_system:
                await self.recovery_system.start_auto_recovery()
                self.logger.info("✅ Auto recovery system started")
            
            # 5. Start monitoring integration
            if self.monitoring_integrator:
                await self.monitoring_integrator.integrate_monitoring_stack(
                    self.pool_monitor,
                    self.stats_collector,
                    self.diagnostic_system,
                    self.recovery_system
                )
                self.logger.info("✅ Monitoring integration started")
            
            # 6. Start dashboard server
            if self.dashboard_server:
                self.dashboard_server.start_server()
                dashboard_url = self.dashboard_server.get_dashboard_url()
                self.logger.info(f"✅ Dashboard server started: {dashboard_url}")
            
            self._started = True
            self.logger.info("🚀 All infrastructure services started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start infrastructure services: {e}")
            # Attempt cleanup on failure
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop all infrastructure services"""
        if not self._started:
            return
        
        try:
            self.logger.info("Stopping connection pool infrastructure services...")
            
            # Stop in reverse order
            
            # 1. Stop dashboard server
            if self.dashboard_server:
                self.dashboard_server.stop_server()
                self.logger.info("Dashboard server stopped")
            
            # 2. Stop monitoring integration
            if self.monitoring_integrator:
                await self.monitoring_integrator.stop_integration()
                self.logger.info("Monitoring integration stopped")
            
            # 3. Stop auto recovery
            if self.recovery_system:
                await self.recovery_system.stop_auto_recovery()
                self.logger.info("Auto recovery system stopped")
            
            # 4. Stop diagnostic system
            if self.diagnostic_system:
                await self.diagnostic_system.stop_diagnostics()
                self.logger.info("Diagnostic system stopped")
            
            # 5. Stop stats collector
            if self.stats_collector:
                await self.stats_collector.stop_collection()
                self.logger.info("Stats collector stopped")
            
            # 6. Stop pool monitor
            if self.pool_monitor:
                await self.pool_monitor.stop_monitoring()
                self.logger.info("Pool monitor stopped")
            
            # 7. Cleanup test infrastructure
            if self.test_infrastructure:
                await self.test_infrastructure.cleanup_all_environments()
                self.logger.info("Test infrastructure cleaned up")
            
            # 8. Close connection factory
            if self.connection_factory:
                self.connection_factory.close_all_connections()
                self.logger.info("Connection factory closed")
            
            self._started = False
            self.logger.info("🛑 All infrastructure services stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping infrastructure services: {e}")
    
    async def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all infrastructure components"""
        
        status = {
            'infrastructure': {
                'initialized': self._initialized,
                'started': self._started,
                'timestamp': datetime.now().isoformat()
            },
            'config': {
                'pool_name': self.config.pool_name,
                'database_path': self.config.database_path,
                'monitoring_db_path': self.config.monitoring_db_path,
                'auto_recovery_enabled': self.config.enable_auto_recovery,
                'dashboard_enabled': self.config.enable_dashboard
            },
            'components': {}
        }
        
        # Pool monitor status
        if self.pool_monitor:
            current_stats = await self.pool_monitor.get_current_stats()
            status['components']['pool_monitor'] = {
                'active': True,
                'current_stats': current_stats.to_dict() if current_stats else None,
                'monitoring_interval': self.config.monitoring_interval
            }
        
        # Stats collector status
        if self.stats_collector:
            status['components']['stats_collector'] = self.stats_collector.get_metrics_summary()
        
        # Diagnostic system status
        if self.diagnostic_system:
            status['components']['diagnostic_system'] = self.diagnostic_system.get_system_health()
        
        # Recovery system status
        if self.recovery_system:
            status['components']['recovery_system'] = self.recovery_system.get_system_health_overview()
        
        # Dashboard status
        if self.dashboard_server:
            status['components']['dashboard'] = {
                'active': True,
                'url': self.dashboard_server.get_dashboard_url(),
                'config': self.config.dashboard_config.__dict__
            }
        
        # Integration status
        if self.monitoring_integrator:
            status['components']['monitoring_integration'] = self.monitoring_integrator.get_integration_status()
        
        # Test infrastructure status
        if self.test_infrastructure:
            status['components']['test_infrastructure'] = self.test_infrastructure.get_manager_status()
        
        return status
    
    async def run_infrastructure_health_check(self) -> Dict[str, Any]:
        """Run comprehensive infrastructure health check"""
        
        health_check = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'unknown',
            'component_health': {},
            'issues': [],
            'recommendations': []
        }
        
        issues = []
        
        try:
            # Check database connectivity
            if self.connection_factory:
                try:
                    conn = self.connection_factory.get_connection()
                    cursor = conn.execute("SELECT 1")
                    result = cursor.fetchone()
                    
                    if result and result[0] == 1:
                        health_check['component_health']['database'] = 'healthy'
                    else:
                        health_check['component_health']['database'] = 'unhealthy'
                        issues.append('Database connectivity test failed')
                        
                except Exception as e:
                    health_check['component_health']['database'] = 'unhealthy'
                    issues.append(f'Database error: {e}')
            
            # Check monitoring components
            if self.recovery_system:
                try:
                    health_results = await self.recovery_system.run_health_checks()
                    
                    for result in health_results:
                        health_check['component_health'][result.component] = result.status.value
                        
                        if result.status.value in ['critical', 'degraded']:
                            issues.append(f'{result.component}: {result.message}')
                            
                except Exception as e:
                    health_check['component_health']['recovery_system'] = 'error'
                    issues.append(f'Recovery system health check failed: {e}')
            
            # Check dashboard accessibility
            if self.dashboard_server and self._started:
                health_check['component_health']['dashboard'] = 'healthy'
            
            # Determine overall status
            component_statuses = list(health_check['component_health'].values())
            
            if not component_statuses:
                health_check['overall_status'] = 'unknown'
            elif 'unhealthy' in component_statuses or 'critical' in component_statuses:
                health_check['overall_status'] = 'critical'
            elif 'degraded' in component_statuses:
                health_check['overall_status'] = 'degraded'
            elif 'warning' in component_statuses:
                health_check['overall_status'] = 'warning'
            else:
                health_check['overall_status'] = 'healthy'
            
            # Add issues and recommendations
            health_check['issues'] = issues
            
            if issues:
                health_check['recommendations'] = [
                    'Review component logs for detailed error information',
                    'Check database connectivity and permissions',
                    'Verify monitoring configuration settings',
                    'Consider restarting infrastructure services if issues persist'
                ]
            
        except Exception as e:
            health_check['overall_status'] = 'error'
            health_check['issues'] = [f'Health check failed: {e}']
        
        return health_check
    
    def get_dashboard_url(self) -> Optional[str]:
        """Get dashboard URL if available"""
        if self.dashboard_server and self._started:
            return self.dashboard_server.get_dashboard_url()
        return None
    
    async def trigger_manual_recovery(self, reason: str = "Manual trigger") -> Dict[str, Any]:
        """Manually trigger recovery actions"""
        if not self.recovery_system:
            return {'error': 'Recovery system not available'}
        
        recovery_results = []
        
        # Get current health status
        health_results = await self.recovery_system.run_health_checks()
        
        for result in health_results:
            if result.status.value in ['critical', 'degraded']:
                # Determine appropriate recovery action
                from .auto_recovery_system import RecoveryAction
                
                if result.component == 'connection_pool':
                    if result.score < 0.3:
                        action = RecoveryAction.RESTART_CONNECTIONS
                    else:
                        action = RecoveryAction.CLEAR_POOL
                elif result.component == 'database':
                    if result.score < 0.4:
                        action = RecoveryAction.OPTIMIZE_DATABASE
                    else:
                        action = RecoveryAction.FORCE_CHECKPOINT
                else:
                    continue  # Skip unknown components
                
                # Execute recovery
                attempt = await self.recovery_system.recovery_executor.execute_recovery(
                    action, f"{reason} - {result.component} health issue"
                )
                
                recovery_results.append(attempt.to_dict())
        
        return {
            'recovery_attempts': recovery_results,
            'total_attempts': len(recovery_results),
            'successful_attempts': len([r for r in recovery_results if r.get('success', False)]),
            'timestamp': datetime.now().isoformat()
        }


# Factory functions and utilities

def create_infrastructure(config: Optional[InfrastructureConfig] = None) -> ConnectionPoolInfrastructure:
    """Create connection pool infrastructure"""
    return ConnectionPoolInfrastructure(config)


async def quick_start_infrastructure(database_path: str = "roas_bot.db",
                                   pool_name: str = "default",
                                   enable_dashboard: bool = True,
                                   dashboard_port: int = 8080) -> ConnectionPoolInfrastructure:
    """
    Quick start infrastructure with sensible defaults
    
    Args:
        database_path: Database file path
        pool_name: Connection pool name
        enable_dashboard: Whether to enable web dashboard
        dashboard_port: Dashboard HTTP port
        
    Returns:
        Started infrastructure instance
    """
    
    # Create configuration
    config = InfrastructureConfig(
        database_path=database_path,
        pool_name=pool_name,
        enable_dashboard=enable_dashboard,
        monitoring_interval=30.0,  # More frequent for demo
        stats_collection_interval=5.0,  # More frequent for demo
        health_check_interval=15.0  # More frequent for demo
    )
    
    if enable_dashboard:
        config.dashboard_config = DashboardConfig(port=dashboard_port)
    
    # Create and start infrastructure
    infrastructure = create_infrastructure(config)
    await infrastructure.start()
    
    return infrastructure


async def validate_complete_infrastructure() -> Dict[str, Any]:
    """
    Validate complete infrastructure setup
    
    Creates a temporary infrastructure instance and validates
    all components work correctly together.
    """
    
    validation_results = {
        'timestamp': datetime.now().isoformat(),
        'overall_status': 'unknown',
        'component_tests': {},
        'integration_tests': {},
        'recommendations': []
    }
    
    infrastructure = None
    
    try:
        # Create test infrastructure
        config = InfrastructureConfig(
            database_path=":memory:",  # Use in-memory database for testing
            pool_name="validation_test",
            enable_dashboard=False,  # Skip dashboard for validation
            enable_test_infrastructure=False  # Skip test infrastructure
        )
        
        infrastructure = create_infrastructure(config)
        await infrastructure.initialize()
        await infrastructure.start()
        
        # Test individual components
        validation_results['component_tests']['initialization'] = {
            'status': 'pass',
            'message': 'Infrastructure initialized successfully'
        }
        
        # Test database connectivity
        if infrastructure.connection_factory:
            try:
                conn = infrastructure.connection_factory.get_connection()
                cursor = conn.execute("SELECT 1")
                result = cursor.fetchone()
                
                validation_results['component_tests']['database_connectivity'] = {
                    'status': 'pass' if result and result[0] == 1 else 'fail',
                    'message': 'Database connectivity test completed'
                }
            except Exception as e:
                validation_results['component_tests']['database_connectivity'] = {
                    'status': 'fail',
                    'message': f'Database connectivity failed: {e}'
                }
        
        # Test monitoring components
        if infrastructure.pool_monitor:
            try:
                stats = await infrastructure.pool_monitor.get_current_stats()
                validation_results['component_tests']['pool_monitor'] = {
                    'status': 'pass',
                    'message': 'Pool monitor operational',
                    'current_stats': stats.to_dict() if stats else None
                }
            except Exception as e:
                validation_results['component_tests']['pool_monitor'] = {
                    'status': 'fail',
                    'message': f'Pool monitor test failed: {e}'
                }
        
        # Test stats collector
        if infrastructure.stats_collector:
            try:
                metrics = infrastructure.stats_collector.get_current_snapshot()
                validation_results['component_tests']['stats_collector'] = {
                    'status': 'pass',
                    'message': 'Stats collector operational',
                    'metrics_count': len(metrics)
                }
            except Exception as e:
                validation_results['component_tests']['stats_collector'] = {
                    'status': 'fail',
                    'message': f'Stats collector test failed: {e}'
                }
        
        # Test health checks
        if infrastructure.recovery_system:
            try:
                health_results = await infrastructure.recovery_system.run_health_checks()
                validation_results['component_tests']['health_checks'] = {
                    'status': 'pass',
                    'message': f'Health checks completed, {len(health_results)} components checked'
                }
            except Exception as e:
                validation_results['component_tests']['health_checks'] = {
                    'status': 'fail',
                    'message': f'Health checks failed: {e}'
                }
        
        # Test integration
        try:
            comprehensive_status = await infrastructure.get_comprehensive_status()
            validation_results['integration_tests']['status_reporting'] = {
                'status': 'pass',
                'message': 'Comprehensive status reporting works',
                'components_count': len(comprehensive_status.get('components', {}))
            }
        except Exception as e:
            validation_results['integration_tests']['status_reporting'] = {
                'status': 'fail',
                'message': f'Status reporting failed: {e}'
            }
        
        # Determine overall status
        all_tests = {**validation_results['component_tests'], **validation_results['integration_tests']}
        test_statuses = [test.get('status', 'unknown') for test in all_tests.values()]
        
        if all(status == 'pass' for status in test_statuses):
            validation_results['overall_status'] = 'pass'
        elif any(status == 'fail' for status in test_statuses):
            validation_results['overall_status'] = 'fail'
        else:
            validation_results['overall_status'] = 'partial'
        
        # Add recommendations based on results
        if validation_results['overall_status'] == 'pass':
            validation_results['recommendations'] = [
                'Infrastructure validation successful - ready for production use',
                'Consider enabling dashboard for monitoring visualization',
                'Monitor logs for any runtime issues'
            ]
        else:
            validation_results['recommendations'] = [
                'Review failed component tests for specific issues',
                'Check database connectivity and permissions',
                'Verify all required dependencies are installed',
                'Consider running validation again after fixing issues'
            ]
        
    except Exception as e:
        validation_results['overall_status'] = 'error'
        validation_results['error'] = str(e)
        validation_results['recommendations'] = [
            'Infrastructure validation failed with error',
            'Check system logs for detailed error information',
            'Verify database and system prerequisites'
        ]
    
    finally:
        # Cleanup
        if infrastructure:
            await infrastructure.stop()
    
    return validation_results


# Usage examples and convenience functions

class InfrastructureUsageExamples:
    """
    Usage examples and patterns for infrastructure components
    
    Demonstrates common use cases and integration patterns.
    """
    
    @staticmethod
    async def basic_monitoring_setup() -> ConnectionPoolInfrastructure:
        """Basic monitoring setup example"""
        
        config = InfrastructureConfig(
            database_path="example.db",
            pool_name="example_pool",
            enable_dashboard=True,
            enable_auto_recovery=True
        )
        
        infrastructure = create_infrastructure(config)
        await infrastructure.start()
        
        print(f"✅ Monitoring started - Dashboard: {infrastructure.get_dashboard_url()}")
        
        return infrastructure
    
    @staticmethod
    async def development_setup() -> ConnectionPoolInfrastructure:
        """Development environment setup with verbose logging"""
        
        config = InfrastructureConfig(
            database_path="dev.db",
            pool_name="dev_pool",
            detailed_logging=True,
            monitoring_interval=15.0,  # More frequent monitoring
            stats_collection_interval=1.0,  # Real-time stats
            health_check_interval=10.0,  # Frequent health checks
            enable_dashboard=True
        )
        
        # Configure dashboard for development
        config.dashboard_config = DashboardConfig(
            port=8080,
            auto_refresh_interval=10,  # Fast refresh
            color_scheme="dark"  # Development theme
        )
        
        infrastructure = create_infrastructure(config)
        await infrastructure.start()
        
        # Enable detailed monitoring integration
        config.integration_config.detailed_logging = True
        config.integration_config.log_level = "DEBUG"
        
        print("🔧 Development monitoring setup complete")
        print(f"📊 Dashboard: {infrastructure.get_dashboard_url()}")
        
        return infrastructure
    
    @staticmethod
    async def production_setup() -> ConnectionPoolInfrastructure:
        """Production environment setup with optimized settings"""
        
        config = InfrastructureConfig(
            database_path="/app/data/production.db",
            pool_name="production_pool",
            detailed_logging=False,  # Reduce log volume
            monitoring_interval=60.0,  # Standard monitoring
            stats_collection_interval=5.0,  # Balanced stats collection
            health_check_interval=30.0,  # Regular health checks
            enable_dashboard=True,
            enable_auto_recovery=True
        )
        
        # Configure for production
        config.dashboard_config = DashboardConfig(
            host="0.0.0.0",  # Listen on all interfaces
            port=8080,
            auto_refresh_interval=30,
            enable_data_export=True
        )
        
        # Production integration settings
        config.integration_config = MonitoringIntegrationConfig(
            enable_structured_logging=True,
            log_to_dedicated_files=True,
            export_metrics_interval=300.0,  # Export every 5 minutes
            forward_alerts_to_logging=True
        )
        
        infrastructure = create_infrastructure(config)
        await infrastructure.start()
        
        print("🚀 Production monitoring infrastructure started")
        print(f"📊 Dashboard: {infrastructure.get_dashboard_url()}")
        
        # Run initial health check
        health_status = await infrastructure.run_infrastructure_health_check()
        print(f"🏥 Initial health status: {health_status['overall_status']}")
        
        return infrastructure


# Export main classes and functions
__all__ = [
    'InfrastructureConfig',
    'ConnectionPoolInfrastructure', 
    'create_infrastructure',
    'quick_start_infrastructure',
    'validate_complete_infrastructure',
    'InfrastructureUsageExamples'
]