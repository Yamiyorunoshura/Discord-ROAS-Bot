#!/usr/bin/env python3
"""
Discord ROAS Bot - Prometheus 品質指標導出器
整合品質指標到 Prometheus 監控系統
"""

import time
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timedelta

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QualityMetricsExporter:
    """品質指標 Prometheus 導出器"""
    
    def __init__(self, project_root: Path, registry=None):
        self.project_root = project_root
        self.registry = registry
        self.metrics = self._initialize_metrics()
        self.last_update = datetime.now()
        
    def _initialize_metrics(self) -> Dict[str, Any]:
        """初始化 Prometheus 指標"""
        try:
            from prometheus_client import (
                Gauge, Counter, Histogram, Info, 
                CollectorRegistry
            )
            
            if not self.registry:
                self.registry = CollectorRegistry()
            
            metrics = {}
            
            # 品質分數指標
            metrics['quality_score'] = Gauge(
                'discord_bot_quality_score',
                'Overall code quality score',
                ['environment', 'component'],
                registry=self.registry
            )
            
            # 測試覆蓋率指標
            metrics['test_coverage'] = Gauge(
                'discord_bot_test_coverage_percent',
                'Test coverage percentage',
                ['environment', 'component'],
                registry=self.registry
            )
            
            # 代碼品質違規計數
            metrics['ruff_violations'] = Gauge(
                'discord_bot_ruff_violations_total',
                'Total number of ruff violations',
                ['environment', 'severity'],
                registry=self.registry
            )
            
            # MyPy 錯誤計數
            metrics['mypy_errors'] = Gauge(
                'discord_bot_mypy_errors_total',
                'Total number of mypy errors',
                ['environment', 'error_type'],
                registry=self.registry
            )
            
            # 安全問題計數
            metrics['security_issues'] = Gauge(
                'discord_bot_security_issues_total',
                'Total number of security issues',
                ['environment', 'severity', 'tool'],
                registry=self.registry
            )
            
            # 部署頻率
            metrics['deployment_frequency'] = Counter(
                'discord_bot_deployments_total',
                'Total number of deployments',
                ['environment', 'status'],
                registry=self.registry
            )
            
            # 品質檢查持續時間
            metrics['quality_check_duration'] = Histogram(
                'discord_bot_quality_check_duration_seconds',
                'Duration of quality checks in seconds',
                ['environment', 'check_type'],
                registry=self.registry
            )
            
            # 最後更新時間
            metrics['last_update'] = Gauge(
                'discord_bot_metrics_last_update_timestamp',
                'Timestamp of last metrics update',
                registry=self.registry
            )
            
            return metrics
            
        except ImportError:
            logger.warning("prometheus_client 未安裝，使用模擬指標")
            return self._create_mock_metrics()
    
    def _create_mock_metrics(self) -> Dict[str, Any]:
        """創建模擬指標（用於開發環境）"""
        class MockMetric:
            def __init__(self, name):
                self.name = name
                self.values = {}
            
            def labels(self, **kwargs):
                return MockMetricInstance(self.name, kwargs)
            
            def set(self, value):
                self.values['default'] = value
            
            def inc(self, amount=1):
                self.values['default'] = self.values.get('default', 0) + amount
            
            def observe(self, value):
                self.values['default'] = value
        
        class MockMetricInstance:
            def __init__(self, name, labels):
                self.name = name
                self.labels_dict = labels
            
            def set(self, value):
                logger.debug(f"Mock metric {self.name}{self.labels_dict} = {value}")
            
            def inc(self, amount=1):
                logger.debug(f"Mock metric {self.name}{self.labels_dict} += {amount}")
            
            def observe(self, value):
                logger.debug(f"Mock metric {self.name}{self.labels_dict} observed {value}")
        
        return {
            'quality_score': MockMetric('quality_score'),
            'test_coverage': MockMetric('test_coverage'),
            'ruff_violations': MockMetric('ruff_violations'),
            'mypy_errors': MockMetric('mypy_errors'),
            'security_issues': MockMetric('security_issues'),
            'deployment_frequency': MockMetric('deployment_frequency'),
            'quality_check_duration': MockMetric('quality_check_duration'),
            'last_update': MockMetric('last_update')
        }
    
    def update_quality_score(self, environment: str, component: str, score: float):
        """更新品質分數"""
        self.metrics['quality_score'].labels(
            environment=environment, 
            component=component
        ).set(score)
    
    def update_test_coverage(self, environment: str, component: str, coverage: float):
        """更新測試覆蓋率"""
        self.metrics['test_coverage'].labels(
            environment=environment,
            component=component
        ).set(coverage)
    
    async def load_quality_data(self) -> Dict[str, Any]:
        """從品質報告文件載入資料"""
        quality_reports_dir = self.project_root / "quality-reports"
        data = {}
        
        # 載入最新的品質報告
        if quality_reports_dir.exists():
            report_files = list(quality_reports_dir.glob("quality-report-*.json"))
            if report_files:
                latest_report = max(report_files, key=lambda x: x.stat().st_mtime)
                try:
                    with open(latest_report, 'r', encoding='utf-8') as f:
                        data['quality_report'] = json.load(f)
                        logger.info(f"載入品質報告: {latest_report.name}")
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    logger.warning(f"無法讀取品質報告: {e}")
        
        # 載入覆蓋率報告
        coverage_file = self.project_root / "coverage.json"
        if coverage_file.exists():
            try:
                with open(coverage_file, 'r', encoding='utf-8') as f:
                    data['coverage'] = json.load(f)
                    logger.info("載入覆蓋率報告")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"無法讀取覆蓋率報告: {e}")
        
        return data
    
    async def update_metrics_from_data(self, data: Dict[str, Any]):
        """從載入的資料更新指標"""
        
        # 更新品質報告指標
        if 'quality_report' in data:
            report = data['quality_report']
            environment = report.get('environment', 'unknown')
            
            # 品質分數
            if 'overall_quality_score' in report:
                self.update_quality_score(environment, 'overall', report['overall_quality_score'])
                logger.debug(f"更新品質分數: {report['overall_quality_score']}")
        
        # 更新覆蓋率指標
        if 'coverage' in data:
            coverage_data = data['coverage']
            coverage_percent = coverage_data.get('totals', {}).get('percent_covered', 0)
            self.update_test_coverage('ci', 'overall', coverage_percent)
            logger.debug(f"更新覆蓋率: {coverage_percent}%")
        
        # 更新最後更新時間
        self.metrics['last_update'].set(time.time())
        self.last_update = datetime.now()
    
    async def start_metrics_collection(self, update_interval: int = 60):
        """開始定期收集指標"""
        logger.info(f"開始品質指標收集，更新間隔: {update_interval}秒")
        
        while True:
            try:
                logger.debug("更新品質指標...")
                data = await self.load_quality_data()
                await self.update_metrics_from_data(data)
                logger.debug("品質指標更新完成")
            except Exception as e:
                logger.error(f"更新指標時出錯: {str(e)}")
            
            await asyncio.sleep(update_interval)

class PrometheusServer:
    """Prometheus 指標伺服器"""
    
    def __init__(self, exporter: QualityMetricsExporter, host: str = '0.0.0.0', port: int = 8090):
        self.exporter = exporter
        self.host = host
        self.port = port
        self.has_prometheus = self._check_prometheus_client()
        self.has_aiohttp = self._check_aiohttp()
        
    def _check_prometheus_client(self) -> bool:
        """檢查是否安裝 prometheus_client"""
        try:
            import prometheus_client
            return True
        except ImportError:
            return False
    
    def _check_aiohttp(self) -> bool:
        """檢查是否安裝 aiohttp"""
        try:
            import aiohttp
            return True
        except ImportError:
            return False
    
    async def start(self):
        """啟動伺服器"""
        if not self.has_prometheus or not self.has_aiohttp:
            logger.warning("缺少必要套件，以模擬模式運行")
            logger.info("執行: uv add prometheus-client aiohttp 來安裝完整功能")
            
            # 模擬模式：只運行指標收集
            await self.exporter.start_metrics_collection()
            return
        
        # 完整模式：啟動 HTTP 伺服器
        from aiohttp import web
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        
        app = web.Application()
        
        # 設定路由
        async def metrics_handler(request):
            try:
                metrics_data = generate_latest(self.exporter.registry)
                return web.Response(
                    body=metrics_data,
                    content_type=CONTENT_TYPE_LATEST
                )
            except Exception as e:
                logger.error(f"生成指標時出錯: {str(e)}")
                return web.Response(text=f"Error: {str(e)}", status=500)
        
        async def health_handler(request):
            health_data = {
                'status': 'healthy',
                'last_update': self.exporter.last_update.isoformat(),
                'metrics_count': len(self.exporter.metrics)
            }
            return web.json_response(health_data)
        
        app.router.add_get('/metrics', metrics_handler)
        app.router.add_get('/health', health_handler)
        
        logger.info(f"啟動 Prometheus 指標伺服器於 {self.host}:{self.port}")
        
        # 啟動指標收集
        collection_task = asyncio.create_task(
            self.exporter.start_metrics_collection()
        )
        
        # 啟動 web 伺服器
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"指標端點: http://{self.host}:{self.port}/metrics")
        
        try:
            await collection_task
        except asyncio.CancelledError:
            logger.info("指標收集任務已取消")
        finally:
            await runner.cleanup()

# CLI 介面和主程式
async def main():
    """主程式入口"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Discord ROAS Bot Prometheus 品質指標導出器')
    parser.add_argument('--host', default='0.0.0.0', help='伺服器主機 (預設: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8090, help='伺服器埠口 (預設: 8090)')
    parser.add_argument('--interval', type=int, default=60, help='指標更新間隔秒數 (預設: 60)')
    parser.add_argument('--project-root', help='專案根目錄路徑')
    
    args = parser.parse_args()
    
    project_root = Path(args.project_root) if args.project_root else Path(__file__).parent.parent.parent
    
    if not project_root.exists():
        logger.error(f"專案根目錄不存在: {project_root}")
        sys.exit(1)
    
    logger.info(f"使用專案根目錄: {project_root}")
    
    # 建立指標導出器
    exporter = QualityMetricsExporter(project_root)
    
    # 建立伺服器
    server = PrometheusServer(exporter, args.host, args.port)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("收到中斷信號，正在關閉...")
    except Exception as e:
        logger.error(f"伺服器運行錯誤: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())