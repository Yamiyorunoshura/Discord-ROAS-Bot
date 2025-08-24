"""
Monitoring Dashboard and Visualization System
Task ID: T2 - High Concurrency Connection Competition Fix

This module provides a comprehensive dashboard and visualization system
for connection pool monitoring data, offering real-time insights and
historical analysis through web-based interfaces and reports.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import socketserver

from ..core.logging import get_logger
from .connection_pool_monitor import ConnectionPoolMonitor, PoolStats
from .realtime_stats_collector import RealTimeStatsCollector, AggregatedMetric
from .diagnostic_alerting_system import ConnectionPoolDiagnosticSystem, Alert
from .auto_recovery_system import AutoRecoverySystem, HealthCheckResult


@dataclass
class DashboardConfig:
    """Configuration for monitoring dashboard"""
    
    # Server configuration
    host: str = "127.0.0.1"
    port: int = 8080
    serve_static: bool = True
    dashboard_directory: str = "dashboard"
    
    # Data refresh settings
    auto_refresh_interval: int = 30  # seconds
    historical_data_hours: int = 24
    max_data_points: int = 1000
    
    # Visualization settings
    enable_real_time_charts: bool = True
    chart_animation: bool = True
    color_scheme: str = "default"  # default, dark, light
    
    # Export settings
    enable_data_export: bool = True
    export_formats: List[str] = None
    
    def __post_init__(self):
        if self.export_formats is None:
            self.export_formats = ["json", "csv"]


class DashboardDataProvider:
    """
    Data provider for dashboard visualization
    
    Aggregates and formats data from monitoring components
    for consumption by the dashboard frontend.
    """
    
    def __init__(self, config: DashboardConfig):
        """Initialize dashboard data provider"""
        self.config = config
        self.logger = get_logger("dashboard_data_provider")
        
        # Monitoring components (set via registration)
        self.pool_monitor: Optional[ConnectionPoolMonitor] = None
        self.stats_collector: Optional[RealTimeStatsCollector] = None
        self.diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None
        self.recovery_system: Optional[AutoRecoverySystem] = None
        
        # Data cache
        self._data_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(seconds=5)  # 5-second cache TTL
        
        self.logger.info("Dashboard data provider initialized")
    
    def register_components(self,
                          pool_monitor: Optional[ConnectionPoolMonitor] = None,
                          stats_collector: Optional[RealTimeStatsCollector] = None,
                          diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None,
                          recovery_system: Optional[AutoRecoverySystem] = None):
        """Register monitoring components"""
        
        if pool_monitor:
            self.pool_monitor = pool_monitor
            self.logger.info("Registered pool monitor")
        
        if stats_collector:
            self.stats_collector = stats_collector
            self.logger.info("Registered stats collector")
        
        if diagnostic_system:
            self.diagnostic_system = diagnostic_system
            self.logger.info("Registered diagnostic system")
        
        if recovery_system:
            self.recovery_system = recovery_system
            self.logger.info("Registered recovery system")
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        
        # Check cache first
        cache_key = "dashboard_data"
        if self._is_cache_valid(cache_key):
            return self._data_cache[cache_key]
        
        try:
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'system_overview': await self._get_system_overview(),
                'current_metrics': await self._get_current_metrics(),
                'historical_data': await self._get_historical_data(),
                'alerts': await self._get_alerts_data(),
                'health_status': await self._get_health_status(),
                'performance_summary': await self._get_performance_summary()
            }
            
            # Cache the data
            self._data_cache[cache_key] = dashboard_data
            self._cache_timestamps[cache_key] = datetime.now()
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Error getting dashboard data: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    async def _get_system_overview(self) -> Dict[str, Any]:
        """Get system overview data"""
        overview = {
            'components': {
                'pool_monitor': self.pool_monitor is not None,
                'stats_collector': self.stats_collector is not None,
                'diagnostic_system': self.diagnostic_system is not None,
                'recovery_system': self.recovery_system is not None
            },
            'uptime': 'N/A'  # Would need to track start time
        }
        
        # Get current pool statistics
        if self.pool_monitor:
            current_stats = await self.pool_monitor.get_current_stats()
            if current_stats:
                overview['current_pool_stats'] = {
                    'active_connections': current_stats.active_connections,
                    'idle_connections': current_stats.idle_connections,
                    'utilization_ratio': current_stats.utilization_ratio,
                    'pool_health_score': current_stats.pool_health_score
                }
        
        return overview
    
    async def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics data"""
        if not self.stats_collector:
            return {}
        
        current_snapshot = self.stats_collector.get_current_snapshot()
        metrics_summary = self.stats_collector.get_metrics_summary()
        
        return {
            'current_values': current_snapshot,
            'collection_status': {
                'collecting': metrics_summary.get('collecting', False),
                'collection_interval': metrics_summary.get('collection_interval', 0)
            },
            'metrics_info': metrics_summary.get('metrics', {})
        }
    
    async def _get_historical_data(self) -> Dict[str, Any]:
        """Get historical data for charts"""
        historical_data = {}
        
        if self.pool_monitor:
            # Get historical statistics
            historical_stats = await self.pool_monitor.get_historical_stats(self.config.historical_data_hours)
            
            if historical_stats:
                # Limit data points for performance
                if len(historical_stats) > self.config.max_data_points:
                    step = len(historical_stats) // self.config.max_data_points
                    historical_stats = historical_stats[::step]
                
                # Format for charts
                timestamps = [stats.timestamp.isoformat() for stats in historical_stats]
                
                historical_data['timeline'] = timestamps
                historical_data['metrics'] = {
                    'active_connections': [stats.active_connections for stats in historical_stats],
                    'utilization_ratio': [stats.utilization_ratio for stats in historical_stats],
                    'average_wait_time': [stats.average_wait_time_ms for stats in historical_stats],
                    'pool_health_score': [stats.pool_health_score for stats in historical_stats],
                    'success_rate': [stats.success_rate for stats in historical_stats],
                    'error_rate': [stats.error_rate for stats in historical_stats]
                }
        
        return historical_data
    
    async def _get_alerts_data(self) -> Dict[str, Any]:
        """Get alerts and diagnostics data"""
        if not self.diagnostic_system:
            return {}
        
        try:
            # Get active alerts
            active_alerts = self.diagnostic_system.alert_manager.get_active_alerts()
            alert_history = self.diagnostic_system.alert_manager.get_alert_history(24)
            
            # Get recent diagnoses
            recent_diagnoses = self.diagnostic_system.diagnostic_engine.get_diagnosis_history(1)
            
            return {
                'active_alerts': [alert.to_dict() for alert in active_alerts],
                'alert_history_24h': [alert.to_dict() for alert in alert_history[-50:]],  # Last 50
                'recent_diagnoses': [diagnosis.to_dict() for diagnosis in recent_diagnoses],
                'alert_summary': self.diagnostic_system.alert_manager.get_alert_summary()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting alerts data: {e}")
            return {}
    
    async def _get_health_status(self) -> Dict[str, Any]:
        """Get health status data"""
        if not self.recovery_system:
            return {}
        
        try:
            # Get system health overview
            health_overview = self.recovery_system.get_system_health_overview()
            
            # Get recent health results
            recent_health = self.recovery_system.get_recent_health_results(1)
            
            # Get recovery history
            recovery_history = self.recovery_system.recovery_executor.get_recovery_history(24)
            
            return {
                'overview': health_overview,
                'recent_checks': [result.to_dict() for result in recent_health],
                'recovery_history': [attempt.to_dict() for attempt in recovery_history[-20:]]  # Last 20
            }
            
        except Exception as e:
            self.logger.error(f"Error getting health status: {e}")
            return {}
    
    async def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        summary = {}
        
        if self.pool_monitor:
            try:
                performance_summary = await self.pool_monitor.get_performance_summary()
                summary.update(performance_summary)
            except Exception as e:
                self.logger.error(f"Error getting performance summary: {e}")
        
        return summary
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self._cache_timestamps:
            return False
        
        cache_age = datetime.now() - self._cache_timestamps[cache_key]
        return cache_age < self._cache_ttl
    
    async def export_data(self, format_type: str, hours: int = 24) -> str:
        """Export dashboard data to specified format"""
        
        if format_type not in self.config.export_formats:
            raise ValueError(f"Unsupported export format: {format_type}")
        
        # Get comprehensive data
        dashboard_data = await self.get_dashboard_data()
        
        # Create export filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"monitoring_export_{timestamp}.{format_type}"
        filepath = Path(self.config.dashboard_directory) / "exports" / filename
        
        # Ensure export directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if format_type == "json":
            with open(filepath, 'w') as f:
                json.dump(dashboard_data, f, indent=2, default=str)
        
        elif format_type == "csv":
            # Export historical data as CSV
            import csv
            
            with open(filepath, 'w', newline='') as f:
                if 'historical_data' in dashboard_data and dashboard_data['historical_data']:
                    hist_data = dashboard_data['historical_data']
                    
                    if 'timeline' in hist_data and 'metrics' in hist_data:
                        writer = csv.writer(f)
                        
                        # Header
                        headers = ['timestamp'] + list(hist_data['metrics'].keys())
                        writer.writerow(headers)
                        
                        # Data rows
                        for i, timestamp in enumerate(hist_data['timeline']):
                            row = [timestamp]
                            for metric_name in hist_data['metrics']:
                                values = hist_data['metrics'][metric_name]
                                row.append(values[i] if i < len(values) else None)
                            writer.writerow(row)
        
        self.logger.info(f"Exported data to: {filepath}")
        return str(filepath)


class DashboardHTMLGenerator:
    """
    Generates HTML dashboard pages
    
    Creates responsive HTML dashboard with embedded charts
    and real-time data updates.
    """
    
    def __init__(self, config: DashboardConfig):
        """Initialize HTML generator"""
        self.config = config
        self.logger = get_logger("dashboard_html_generator")
    
    def generate_dashboard_html(self, data_provider: DashboardDataProvider) -> str:
        """Generate main dashboard HTML"""
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connection Pool Monitoring Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        {self._get_css_styles()}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <header class="dashboard-header">
            <h1>🔗 Connection Pool Monitoring Dashboard</h1>
            <div class="header-controls">
                <button onclick="refreshData()" class="btn btn-primary">Refresh</button>
                <button onclick="exportData('json')" class="btn btn-secondary">Export JSON</button>
                <select id="timeRange" onchange="updateTimeRange()">
                    <option value="1">Last 1 Hour</option>
                    <option value="6">Last 6 Hours</option>
                    <option value="24" selected>Last 24 Hours</option>
                    <option value="168">Last 7 Days</option>
                </select>
            </div>
        </header>
        
        <div class="dashboard-grid">
            <!-- System Overview -->
            <div class="card overview-card">
                <h2>📊 System Overview</h2>
                <div id="systemOverview" class="overview-content">
                    Loading...
                </div>
            </div>
            
            <!-- Current Metrics -->
            <div class="card metrics-card">
                <h2>📈 Current Metrics</h2>
                <div id="currentMetrics" class="metrics-grid">
                    Loading...
                </div>
            </div>
            
            <!-- Health Status -->
            <div class="card health-card">
                <h2>❤️ Health Status</h2>
                <div id="healthStatus" class="health-content">
                    Loading...
                </div>
            </div>
            
            <!-- Performance Chart -->
            <div class="card chart-card">
                <h2>📈 Performance Trends</h2>
                <canvas id="performanceChart"></canvas>
            </div>
            
            <!-- Utilization Chart -->
            <div class="card chart-card">
                <h2>🔄 Pool Utilization</h2>
                <canvas id="utilizationChart"></canvas>
            </div>
            
            <!-- Alerts -->
            <div class="card alerts-card">
                <h2>🚨 Active Alerts</h2>
                <div id="activeAlerts" class="alerts-content">
                    Loading...
                </div>
            </div>
        </div>
        
        <footer class="dashboard-footer">
            <p>Last updated: <span id="lastUpdated">-</span> | Auto-refresh: {self.config.auto_refresh_interval}s</p>
        </footer>
    </div>
    
    <script>
        {self._get_javascript_code()}
    </script>
</body>
</html>
"""
        return html_template
    
    def _get_css_styles(self) -> str:
        """Get CSS styles for dashboard"""
        
        color_schemes = {
            "default": {
                "bg": "#f5f5f5",
                "card_bg": "#ffffff",
                "text": "#333333",
                "primary": "#007bff",
                "success": "#28a745",
                "warning": "#ffc107",
                "danger": "#dc3545"
            },
            "dark": {
                "bg": "#1a1a1a",
                "card_bg": "#2d2d2d",
                "text": "#ffffff",
                "primary": "#0d6efd",
                "success": "#198754",
                "warning": "#fd7e14",
                "danger": "#dc3545"
            }
        }
        
        colors = color_schemes.get(self.config.color_scheme, color_schemes["default"])
        
        return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: {colors["bg"]};
            color: {colors["text"]};
            line-height: 1.6;
        }}
        
        .dashboard-container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .dashboard-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: {colors["card_bg"]};
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .header-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        
        .btn {{
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.3s;
        }}
        
        .btn-primary {{
            background-color: {colors["primary"]};
            color: white;
        }}
        
        .btn-secondary {{
            background-color: #6c757d;
            color: white;
        }}
        
        .btn:hover {{
            opacity: 0.8;
        }}
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: {colors["card_bg"]};
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .card h2 {{
            margin-bottom: 15px;
            color: {colors["primary"]};
        }}
        
        .chart-card {{
            grid-column: span 1;
        }}
        
        .overview-card, .alerts-card {{
            grid-column: span 1;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
        }}
        
        .metric-item {{
            text-align: center;
            padding: 10px;
            background: rgba(0,123,255,0.1);
            border-radius: 4px;
        }}
        
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: {colors["primary"]};
        }}
        
        .metric-label {{
            font-size: 12px;
            color: {colors["text"]};
            opacity: 0.8;
        }}
        
        .status-indicator {{
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }}
        
        .status-healthy {{ background-color: {colors["success"]}; }}
        .status-warning {{ background-color: {colors["warning"]}; }}
        .status-critical {{ background-color: {colors["danger"]}; }}
        
        .alert-item {{
            padding: 10px;
            margin-bottom: 10px;
            border-left: 4px solid {colors["danger"]};
            background: rgba(220,53,69,0.1);
            border-radius: 4px;
        }}
        
        .dashboard-footer {{
            text-align: center;
            padding: 20px;
            background: {colors["card_bg"]};
            border-radius: 8px;
            color: {colors["text"]};
            opacity: 0.8;
        }}
        
        @media (max-width: 768px) {{
            .dashboard-grid {{
                grid-template-columns: 1fr;
            }}
            
            .dashboard-header {{
                flex-direction: column;
                gap: 15px;
            }}
        }}
        """
    
    def _get_javascript_code(self) -> str:
        """Get JavaScript code for dashboard interactivity"""
        
        return f"""
        let performanceChart, utilizationChart;
        let dashboardData = {{}};
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {{
            initializeCharts();
            refreshData();
            
            // Auto-refresh
            setInterval(refreshData, {self.config.auto_refresh_interval * 1000});
        }});
        
        function initializeCharts() {{
            // Performance Chart
            const perfCtx = document.getElementById('performanceChart').getContext('2d');
            performanceChart = new Chart(perfCtx, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [
                        {{
                            label: 'Response Time (ms)',
                            data: [],
                            borderColor: 'rgb(255, 99, 132)',
                            tension: 0.1
                        }},
                        {{
                            label: 'Health Score',
                            data: [],
                            borderColor: 'rgb(54, 162, 235)',
                            tension: 0.1
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    animation: {str(self.config.chart_animation).lower()},
                    scales: {{
                        y: {{
                            beginAtZero: true
                        }}
                    }}
                }}
            }});
            
            // Utilization Chart
            const utilCtx = document.getElementById('utilizationChart').getContext('2d');
            utilizationChart = new Chart(utilCtx, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [
                        {{
                            label: 'Pool Utilization',
                            data: [],
                            borderColor: 'rgb(75, 192, 192)',
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            fill: true,
                            tension: 0.1
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    animation: {str(self.config.chart_animation).lower()},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: 1
                        }}
                    }}
                }}
            }});
        }}
        
        async function refreshData() {{
            try {{
                const response = await fetch('/api/dashboard-data');
                dashboardData = await response.json();
                
                updateSystemOverview();
                updateCurrentMetrics();
                updateHealthStatus();
                updateCharts();
                updateAlerts();
                
                document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();
                
            }} catch (error) {{
                console.error('Error refreshing data:', error);
                showError('Failed to refresh data: ' + error.message);
            }}
        }}
        
        function updateSystemOverview() {{
            const overview = dashboardData.system_overview || {{}};
            const components = overview.components || {{}};
            
            let html = '<div class="overview-items">';
            
            // Component status
            Object.keys(components).forEach(component => {{
                const status = components[component] ? 'healthy' : 'critical';
                const icon = components[component] ? '✅' : '❌';
                html += `<div class="overview-item">
                    <span class="status-indicator status-${{status}}"></span>
                    ${{component.replace('_', ' ').toUpperCase()}}: ${{icon}}
                </div>`;
            }});
            
            // Pool stats
            if (overview.current_pool_stats) {{
                const stats = overview.current_pool_stats;
                html += `<div class="pool-stats">
                    <h4>Current Pool State:</h4>
                    <p>Active: ${{stats.active_connections}} | Idle: ${{stats.idle_connections}}</p>
                    <p>Utilization: ${{(stats.utilization_ratio * 100).toFixed(1)}}%</p>
                    <p>Health Score: ${{stats.pool_health_score.toFixed(2)}}</p>
                </div>`;
            }}
            
            html += '</div>';
            document.getElementById('systemOverview').innerHTML = html;
        }}
        
        function updateCurrentMetrics() {{
            const metrics = dashboardData.current_metrics || {{}};
            const currentValues = metrics.current_values || {{}};
            
            let html = '';
            
            // Key metrics
            const keyMetrics = [
                {{ key: 'connections.active', label: 'Active Connections', format: 'int' }},
                {{ key: 'pool.utilization', label: 'Pool Utilization', format: 'percent' }},
                {{ key: 'pool.health_score', label: 'Health Score', format: 'float' }},
                {{ key: 'requests.total', label: 'Total Requests', format: 'int' }}
            ];
            
            keyMetrics.forEach(metric => {{
                const value = currentValues[metric.key] || 0;
                let formattedValue = value;
                
                if (metric.format === 'percent') {{
                    formattedValue = (value * 100).toFixed(1) + '%';
                }} else if (metric.format === 'float') {{
                    formattedValue = value.toFixed(2);
                }} else if (metric.format === 'int') {{
                    formattedValue = Math.floor(value);
                }}
                
                html += `<div class="metric-item">
                    <div class="metric-value">${{formattedValue}}</div>
                    <div class="metric-label">${{metric.label}}</div>
                </div>`;
            }});
            
            document.getElementById('currentMetrics').innerHTML = html;
        }}
        
        function updateHealthStatus() {{
            const health = dashboardData.health_status || {{}};
            const overview = health.overview || {{}};
            
            let html = `<div class="health-overview">
                <h4>System Health: <span class="status-indicator status-${{overview.status || 'unknown'}}"></span>${{(overview.status || 'unknown').toUpperCase()}}</h4>
                <p>Health Score: ${{(overview.health_score || 0).toFixed(2)}}</p>
                <p>Active Alerts: ${{overview.active_alerts || 0}}</p>
                <p>Auto Recovery: ${{overview.auto_recovery_active ? 'ON' : 'OFF'}}</p>
            </div>`;
            
            // Recent health checks
            if (health.recent_checks && health.recent_checks.length > 0) {{
                html += '<h4>Recent Health Checks:</h4>';
                health.recent_checks.slice(0, 3).forEach(check => {{
                    html += `<div class="health-check-item">
                        <span class="status-indicator status-${{check.status}}"></span>
                        ${{check.component}}: ${{check.message}}
                    </div>`;
                }});
            }}
            
            document.getElementById('healthStatus').innerHTML = html;
        }}
        
        function updateCharts() {{
            const historicalData = dashboardData.historical_data || {{}};
            
            if (historicalData.timeline && historicalData.metrics) {{
                const timeline = historicalData.timeline;
                const metrics = historicalData.metrics;
                
                // Update performance chart
                performanceChart.data.labels = timeline.map(t => new Date(t).toLocaleTimeString());
                performanceChart.data.datasets[0].data = metrics.average_wait_time || [];
                performanceChart.data.datasets[1].data = (metrics.pool_health_score || []).map(v => v * 100);
                performanceChart.update('none');
                
                // Update utilization chart
                utilizationChart.data.labels = timeline.map(t => new Date(t).toLocaleTimeString());
                utilizationChart.data.datasets[0].data = metrics.utilization_ratio || [];
                utilizationChart.update('none');
            }}
        }}
        
        function updateAlerts() {{
            const alerts = dashboardData.alerts || {{}};
            const activeAlerts = alerts.active_alerts || [];
            
            let html = '';
            
            if (activeAlerts.length === 0) {{
                html = '<p>🟢 No active alerts</p>';
            }} else {{
                activeAlerts.forEach(alert => {{
                    html += `<div class="alert-item">
                        <strong>${{alert.severity.toUpperCase()}}: ${{alert.title}}</strong>
                        <p>${{alert.message}}</p>
                        <small>${{new Date(alert.timestamp).toLocaleString()}}</small>
                    </div>`;
                }});
            }}
            
            document.getElementById('activeAlerts').innerHTML = html;
        }}
        
        function updateTimeRange() {{
            // Implement time range update logic
            console.log('Time range updated');
            refreshData();
        }}
        
        async function exportData(format) {{
            try {{
                const response = await fetch(`/api/export/${{format}}`);
                const blob = await response.blob();
                
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `monitoring_export_${{new Date().toISOString().slice(0,19).replace(/:/g, '-')}}.${{format}}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
            }} catch (error) {{
                console.error('Export failed:', error);
                alert('Export failed: ' + error.message);
            }}
        }}
        
        function showError(message) {{
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = message;
            errorDiv.style.cssText = `
                position: fixed; 
                top: 20px; 
                right: 20px; 
                background: #dc3545; 
                color: white; 
                padding: 10px; 
                border-radius: 4px; 
                z-index: 1000;
            `;
            
            document.body.appendChild(errorDiv);
            
            setTimeout(() => {{
                document.body.removeChild(errorDiv);
            }}, 5000);
        }}
        """


class DashboardServer:
    """
    HTTP server for monitoring dashboard
    
    Serves the dashboard interface and provides API endpoints
    for data access and export functionality.
    """
    
    def __init__(self, config: DashboardConfig, data_provider: DashboardDataProvider):
        """Initialize dashboard server"""
        self.config = config
        self.data_provider = data_provider
        self.logger = get_logger("dashboard_server")
        
        # Server components
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.html_generator = DashboardHTMLGenerator(config)
        
        # Setup dashboard directory
        self._setup_dashboard_directory()
        
        self.logger.info(f"Dashboard server initialized on {config.host}:{config.port}")
    
    def _setup_dashboard_directory(self):
        """Setup dashboard directory structure"""
        dashboard_path = Path(self.config.dashboard_directory)
        dashboard_path.mkdir(exist_ok=True)
        
        # Create subdirectories
        (dashboard_path / "exports").mkdir(exist_ok=True)
        (dashboard_path / "static").mkdir(exist_ok=True)
        
        # Generate dashboard HTML
        html_content = self.html_generator.generate_dashboard_html(self.data_provider)
        with open(dashboard_path / "index.html", 'w') as f:
            f.write(html_content)
        
        self.logger.info(f"Dashboard directory setup: {dashboard_path}")
    
    def start_server(self):
        """Start the dashboard HTTP server"""
        if self.server_thread and self.server_thread.is_alive():
            self.logger.warning("Server already running")
            return
        
        try:
            # Create custom handler
            handler_class = self._create_request_handler()
            
            # Start server
            self.server = HTTPServer((self.config.host, self.config.port), handler_class)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            
            self.logger.info(f"Dashboard server started at http://{self.config.host}:{self.config.port}")
            
        except Exception as e:
            self.logger.error(f"Failed to start dashboard server: {e}")
            raise
    
    def stop_server(self):
        """Stop the dashboard server"""
        if self.server:
            self.server.shutdown()
            self.server = None
        
        if self.server_thread:
            self.server_thread.join(timeout=5)
            self.server_thread = None
        
        self.logger.info("Dashboard server stopped")
    
    def _create_request_handler(self):
        """Create custom HTTP request handler"""
        
        config = self.config
        data_provider = self.data_provider
        logger = self.logger
        
        class DashboardRequestHandler(SimpleHTTPRequestHandler):
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=config.dashboard_directory, **kwargs)
            
            def do_GET(self):
                """Handle GET requests"""
                try:
                    if self.path == '/api/dashboard-data':
                        self._handle_api_dashboard_data()
                    elif self.path.startswith('/api/export/'):
                        format_type = self.path.split('/')[-1]
                        self._handle_api_export(format_type)
                    elif self.path == '/':
                        # Serve main dashboard
                        self.path = '/index.html'
                        super().do_GET()
                    else:
                        # Serve static files
                        super().do_GET()
                        
                except Exception as e:
                    logger.error(f"Error handling request {self.path}: {e}")
                    self._send_error_response(500, str(e))
            
            def _handle_api_dashboard_data(self):
                """Handle dashboard data API request"""
                try:
                    # Get dashboard data asynchronously
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    dashboard_data = loop.run_until_complete(data_provider.get_dashboard_data())
                    loop.close()
                    
                    # Send JSON response
                    self._send_json_response(dashboard_data)
                    
                except Exception as e:
                    logger.error(f"Error getting dashboard data: {e}")
                    self._send_error_response(500, str(e))
            
            def _handle_api_export(self, format_type: str):
                """Handle data export API request"""
                try:
                    # Export data
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    filepath = loop.run_until_complete(data_provider.export_data(format_type))
                    loop.close()
                    
                    # Send file
                    with open(filepath, 'rb') as f:
                        content = f.read()
                    
                    self.send_response(200)
                    self.send_header('Content-Type', f'application/{format_type}')
                    self.send_header('Content-Disposition', f'attachment; filename="{Path(filepath).name}"')
                    self.end_headers()
                    self.wfile.write(content)
                    
                except Exception as e:
                    logger.error(f"Error exporting data: {e}")
                    self._send_error_response(500, str(e))
            
            def _send_json_response(self, data: dict):
                """Send JSON response"""
                json_data = json.dumps(data, default=str).encode('utf-8')
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(json_data)))
                self.end_headers()
                self.wfile.write(json_data)
            
            def _send_error_response(self, code: int, message: str):
                """Send error response"""
                error_data = {'error': message, 'code': code}
                self._send_json_response(error_data)
            
            def log_message(self, format, *args):
                """Override to use our logger"""
                logger.debug(f"HTTP: {format % args}")
        
        return DashboardRequestHandler
    
    def get_dashboard_url(self) -> str:
        """Get dashboard URL"""
        return f"http://{self.config.host}:{self.config.port}"


# Factory functions
def create_monitoring_dashboard(pool_monitor: Optional[ConnectionPoolMonitor] = None,
                              stats_collector: Optional[RealTimeStatsCollector] = None,
                              diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None,
                              recovery_system: Optional[AutoRecoverySystem] = None,
                              config: Optional[DashboardConfig] = None) -> Tuple[DashboardServer, DashboardDataProvider]:
    """
    Create complete monitoring dashboard setup
    
    Returns:
        Tuple of (dashboard_server, data_provider)
    """
    if config is None:
        config = DashboardConfig()
    
    # Create data provider
    data_provider = DashboardDataProvider(config)
    data_provider.register_components(pool_monitor, stats_collector, diagnostic_system, recovery_system)
    
    # Create server
    dashboard_server = DashboardServer(config, data_provider)
    
    return dashboard_server, data_provider


async def start_monitoring_dashboard(pool_monitor: Optional[ConnectionPoolMonitor] = None,
                                   stats_collector: Optional[RealTimeStatsCollector] = None,
                                   diagnostic_system: Optional[ConnectionPoolDiagnosticSystem] = None,
                                   recovery_system: Optional[AutoRecoverySystem] = None,
                                   config: Optional[DashboardConfig] = None) -> DashboardServer:
    """
    Start monitoring dashboard with all components
    
    Returns:
        Running dashboard server instance
    """
    dashboard_server, _ = create_monitoring_dashboard(
        pool_monitor, stats_collector, diagnostic_system, recovery_system, config
    )
    
    dashboard_server.start_server()
    return dashboard_server