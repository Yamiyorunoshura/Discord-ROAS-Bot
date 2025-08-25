#!/usr/bin/env python3
"""
效能優化器 - 專注於Docker啟動和系統效能優化
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

負責分析和優化系統啟動效能，實現啟動時間 < 5分鐘的目標。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import subprocess
import yaml
import psutil

logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """優化類型枚舉"""
    DOCKER_BUILD = "docker_build"
    DOCKER_STARTUP = "docker_startup"
    RESOURCE_ALLOCATION = "resource_allocation"
    HEALTH_CHECK = "health_check"
    SERVICE_DEPENDENCIES = "service_dependencies"
    CACHING = "caching"


@dataclass
class PerformanceMetrics:
    """效能指標"""
    timestamp: datetime
    startup_time_seconds: Optional[float] = None
    build_time_seconds: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    container_pull_time_seconds: Optional[float] = None
    health_check_time_seconds: Optional[float] = None
    total_services: int = 0
    healthy_services: int = 0
    failed_services: int = 0


@dataclass
class OptimizationRecommendation:
    """優化建議"""
    type: OptimizationType
    priority: str  # high, medium, low
    description: str
    implementation: str
    expected_improvement: str
    estimated_effort: str
    risk_level: str  # low, medium, high


@dataclass
class PerformanceReport:
    """效能報告"""
    timestamp: datetime
    baseline_metrics: PerformanceMetrics
    current_metrics: Optional[PerformanceMetrics]
    optimization_recommendations: List[OptimizationRecommendation]
    performance_trend: Dict[str, List[float]]
    summary: Dict[str, Any]


class PerformanceOptimizer:
    """
    效能優化器 - 專注於Docker啟動和系統效能優化
    
    核心職責:
    - 啟動效能測量和分析
    - Docker配置優化建議
    - 資源使用優化
    - 監控和告警整合
    - 效能趨勢分析
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.target_startup_time = 300  # 5分鐘目標
        self.performance_history = []
        
        # 效能目標定義
        self.performance_targets = {
            'startup_time_seconds': 300,    # 5分鐘
            'memory_usage_mb': 512,         # 512MB總計
            'cpu_usage_percent': 50,        # 啟動過程中<50%
            'health_check_time_seconds': 60 # 1分鐘內完成健康檢查
        }
    
    async def analyze_startup_performance(self, environment: str = 'dev') -> PerformanceMetrics:
        """
        分析啟動效能
        
        Args:
            environment: 環境類型 (dev/prod)
            
        Returns:
            PerformanceMetrics: 效能指標
        """
        self.logger.info(f"開始分析 {environment} 環境啟動效能")
        
        start_time = time.time()
        
        try:
            # 準備Docker Compose命令
            compose_file = f'docker-compose.{environment}.yml'
            
            # 測量建置時間
            build_start = time.time()
            build_success = await self._measure_build_time(compose_file)
            build_time = time.time() - build_start if build_success else None
            
            # 測量啟動時間
            startup_start = time.time()
            startup_success = await self._measure_startup_time(compose_file)
            startup_time = time.time() - startup_start if startup_success else None
            
            # 測量健康檢查時間
            health_start = time.time()
            healthy_services, total_services, failed_services = await self._measure_health_check_time(compose_file)
            health_check_time = time.time() - health_start
            
            # 獲取資源使用情況
            memory_usage, cpu_usage = await self._get_resource_usage()
            
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                startup_time_seconds=startup_time,
                build_time_seconds=build_time,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage,
                health_check_time_seconds=health_check_time,
                total_services=total_services,
                healthy_services=healthy_services,
                failed_services=failed_services
            )
            
            self.logger.info(f"效能分析完成，總耗時: {time.time() - start_time:.1f}秒")
            return metrics
            
        except Exception as e:
            self.logger.error(f"效能分析失敗: {str(e)}", exc_info=True)
            return PerformanceMetrics(
                timestamp=datetime.now(),
                total_services=0,
                healthy_services=0,
                failed_services=0
            )
    
    async def _measure_build_time(self, compose_file: str) -> bool:
        """測量映像建置時間"""
        try:
            self.logger.debug(f"測量建置時間: {compose_file}")
            
            cmd = ['docker', 'compose', '-f', compose_file, 'build']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=600  # 10分鐘超時
            )
            
            return process.returncode == 0
            
        except asyncio.TimeoutError:
            self.logger.warning("建置時間測量超時")
            return False
        except Exception as e:
            self.logger.error(f"建置時間測量失敗: {str(e)}")
            return False
    
    async def _measure_startup_time(self, compose_file: str) -> bool:
        """測量啟動時間"""
        try:
            self.logger.debug(f"測量啟動時間: {compose_file}")
            
            # 確保先停止所有服務
            stop_cmd = ['docker', 'compose', '-f', compose_file, 'down']
            await asyncio.create_subprocess_exec(*stop_cmd, cwd=self.project_root)
            await asyncio.sleep(2)
            
            # 啟動服務
            start_cmd = ['docker', 'compose', '-f', compose_file, 'up', '-d']
            
            process = await asyncio.create_subprocess_exec(
                *start_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.target_startup_time
            )
            
            return process.returncode == 0
            
        except asyncio.TimeoutError:
            self.logger.warning(f"啟動時間測量超時 (>{self.target_startup_time}秒)")
            return False
        except Exception as e:
            self.logger.error(f"啟動時間測量失敗: {str(e)}")
            return False
    
    async def _measure_health_check_time(self, compose_file: str) -> Tuple[int, int, int]:
        """測量健康檢查時間並返回服務狀態"""
        try:
            self.logger.debug("測量健康檢查時間")
            
            # 等待服務啟動穩定
            await asyncio.sleep(5)
            
            max_wait_time = 120  # 2分鐘最大等待時間
            check_interval = 10   # 10秒檢查間隔
            
            for attempt in range(max_wait_time // check_interval):
                cmd = ['docker', 'compose', '-f', compose_file, 'ps', '--format', 'json']
                
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=30, cwd=self.project_root
                )
                
                if result.returncode == 0:
                    healthy_services = 0
                    total_services = 0
                    failed_services = 0
                    
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            try:
                                service_data = json.loads(line)
                                total_services += 1
                                
                                state = service_data.get('State', '').lower()
                                health = service_data.get('Health', '').lower()
                                
                                if state == 'running':
                                    if health == 'healthy' or not health:
                                        healthy_services += 1
                                elif state in ['exited', 'dead']:
                                    failed_services += 1
                                        
                            except json.JSONDecodeError:
                                continue
                    
                    if total_services > 0 and healthy_services == total_services:
                        self.logger.info(f"所有服務健康，檢查完成 (第{attempt+1}次嘗試)")
                        return healthy_services, total_services, failed_services
                
                await asyncio.sleep(check_interval)
            
            # 如果超時，返回最後的狀態
            cmd = ['docker', 'compose', '-f', compose_file, 'ps', '--format', 'json']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=self.project_root)
            
            if result.returncode == 0:
                healthy_services = 0
                total_services = 0
                failed_services = 0
                
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            service_data = json.loads(line)
                            total_services += 1
                            
                            state = service_data.get('State', '').lower()
                            health = service_data.get('Health', '').lower()
                            
                            if state == 'running':
                                if health == 'healthy' or not health:
                                    healthy_services += 1
                            elif state in ['exited', 'dead']:
                                failed_services += 1
                                
                        except json.JSONDecodeError:
                            continue
                
                return healthy_services, total_services, failed_services
            
            return 0, 0, 0
            
        except Exception as e:
            self.logger.error(f"健康檢查時間測量失敗: {str(e)}")
            return 0, 0, 0
    
    async def _get_resource_usage(self) -> Tuple[Optional[float], Optional[float]]:
        """獲取當前資源使用情況"""
        try:
            # 獲取Docker容器的記憶體使用情況
            memory_usage = 0.0
            cpu_usage = 0.0
            
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', 'json'],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            stats = json.loads(line)
                            
                            # 解析記憶體使用量
                            mem_usage_str = stats.get('MemUsage', '0B / 0B')
                            used_memory = mem_usage_str.split(' / ')[0]
                            
                            if 'MiB' in used_memory:
                                memory_usage += float(used_memory.replace('MiB', ''))
                            elif 'GiB' in used_memory:
                                memory_usage += float(used_memory.replace('GiB', '')) * 1024
                                
                            # 解析CPU使用率
                            cpu_percent_str = stats.get('CPUPerc', '0.00%').rstrip('%')
                            cpu_usage = max(cpu_usage, float(cpu_percent_str))
                            
                        except (json.JSONDecodeError, ValueError, IndexError):
                            continue
            
            return memory_usage, cpu_usage
            
        except Exception as e:
            self.logger.error(f"資源使用情況獲取失敗: {str(e)}")
            return None, None
    
    def generate_optimization_recommendations(self, metrics: PerformanceMetrics) -> List[OptimizationRecommendation]:
        """
        基於效能指標生成優化建議
        
        Args:
            metrics: 效能指標
            
        Returns:
            List[OptimizationRecommendation]: 優化建議清單
        """
        recommendations = []
        
        # 啟動時間優化
        if metrics.startup_time_seconds and metrics.startup_time_seconds > self.performance_targets['startup_time_seconds']:
            recommendations.append(OptimizationRecommendation(
                type=OptimizationType.DOCKER_STARTUP,
                priority="high",
                description=f"啟動時間過長 ({metrics.startup_time_seconds:.1f}s > {self.performance_targets['startup_time_seconds']}s)",
                implementation="優化健康檢查配置、減少啟動依賴、使用並行啟動",
                expected_improvement="減少啟動時間30-50%",
                estimated_effort="中等",
                risk_level="low"
            ))
        
        # 記憶體使用優化
        if metrics.memory_usage_mb and metrics.memory_usage_mb > self.performance_targets['memory_usage_mb']:
            recommendations.append(OptimizationRecommendation(
                type=OptimizationType.RESOURCE_ALLOCATION,
                priority="medium",
                description=f"記憶體使用過高 ({metrics.memory_usage_mb:.1f}MB > {self.performance_targets['memory_usage_mb']}MB)",
                implementation="調整容器記憶體限制、優化應用配置",
                expected_improvement="減少記憶體使用20-30%",
                estimated_effort="低",
                risk_level="low"
            ))
        
        # 健康檢查優化
        if metrics.health_check_time_seconds and metrics.health_check_time_seconds > self.performance_targets['health_check_time_seconds']:
            recommendations.append(OptimizationRecommendation(
                type=OptimizationType.HEALTH_CHECK,
                priority="high",
                description=f"健康檢查時間過長 ({metrics.health_check_time_seconds:.1f}s > {self.performance_targets['health_check_time_seconds']}s)",
                implementation="簡化健康檢查邏輯、調整檢查間隔和超時時間",
                expected_improvement="減少健康檢查時間40-60%",
                estimated_effort="低",
                risk_level="low"
            ))
        
        # 服務失敗處理
        if metrics.failed_services > 0:
            recommendations.append(OptimizationRecommendation(
                type=OptimizationType.SERVICE_DEPENDENCIES,
                priority="high",
                description=f"有 {metrics.failed_services} 個服務啟動失敗",
                implementation="檢查服務依賴關係、修復啟動腳本、改善錯誤處理",
                expected_improvement="提高服務啟動成功率至100%",
                estimated_effort="高",
                risk_level="medium"
            ))
        
        # 建置時間優化
        if metrics.build_time_seconds and metrics.build_time_seconds > 300:  # 5分鐘
            recommendations.append(OptimizationRecommendation(
                type=OptimizationType.DOCKER_BUILD,
                priority="medium",
                description=f"映像建置時間過長 ({metrics.build_time_seconds:.1f}s)",
                implementation="優化Dockerfile、使用多階段建置、改善層次快取",
                expected_improvement="減少建置時間30-50%",
                estimated_effort="中等",
                risk_level="low"
            ))
        
        # 按優先級排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 3))
        
        return recommendations
    
    def create_optimized_compose_config(self, original_compose_path: Path, 
                                      optimization_type: str = 'performance') -> Dict[str, Any]:
        """
        創建優化的Docker Compose配置
        
        Args:
            original_compose_path: 原始配置檔案路徑
            optimization_type: 優化類型 (performance/development)
            
        Returns:
            Dict[str, Any]: 優化後的配置
        """
        try:
            with open(original_compose_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if optimization_type == 'performance':
                config = self._apply_performance_optimizations(config)
            elif optimization_type == 'development':
                config = self._apply_development_optimizations(config)
            
            return config
            
        except Exception as e:
            self.logger.error(f"配置優化失敗: {str(e)}")
            return {}
    
    def _apply_performance_optimizations(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """應用效能優化配置"""
        services = config.get('services', {})
        
        for service_name, service_config in services.items():
            # 優化健康檢查配置
            if 'healthcheck' in service_config:
                healthcheck = service_config['healthcheck']
                # 更頻繁但更輕量的健康檢查
                healthcheck['interval'] = '15s'
                healthcheck['timeout'] = '5s'
                healthcheck['retries'] = 3
                healthcheck['start_period'] = '10s'
            
            # 優化資源限制
            if 'deploy' not in service_config:
                service_config['deploy'] = {}
            if 'resources' not in service_config['deploy']:
                service_config['deploy']['resources'] = {}
            
            # 根據服務類型設置合理的資源限制
            if service_name == 'discord-bot':
                service_config['deploy']['resources'] = {
                    'limits': {'memory': '512M', 'cpus': '0.5'},
                    'reservations': {'memory': '256M', 'cpus': '0.25'}
                }
            elif service_name == 'redis':
                service_config['deploy']['resources'] = {
                    'limits': {'memory': '256M', 'cpus': '0.25'},
                    'reservations': {'memory': '128M', 'cpus': '0.1'}
                }
            elif service_name in ['prometheus', 'grafana']:
                service_config['deploy']['resources'] = {
                    'limits': {'memory': '512M', 'cpus': '0.3'},
                    'reservations': {'memory': '256M', 'cpus': '0.1'}
                }
            
            # 優化重啟策略
            if service_config.get('restart') == 'always':
                service_config['restart'] = 'unless-stopped'
        
        return config
    
    def _apply_development_optimizations(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """應用開發環境優化配置"""
        services = config.get('services', {})
        
        for service_name, service_config in services.items():
            # 開發環境使用更寬鬆的健康檢查
            if 'healthcheck' in service_config:
                healthcheck = service_config['healthcheck']
                healthcheck['interval'] = '30s'
                healthcheck['timeout'] = '10s'
                healthcheck['retries'] = 2
                healthcheck['start_period'] = '30s'
            
            # 開發環境允許更多資源使用
            if service_name == 'discord-bot':
                if 'deploy' not in service_config:
                    service_config['deploy'] = {}
                service_config['deploy']['resources'] = {
                    'limits': {'memory': '1G', 'cpus': '1.0'}
                }
        
        return config
    
    async def generate_performance_report(self, environment: str = 'dev') -> PerformanceReport:
        """
        生成完整的效能報告
        
        Args:
            environment: 環境類型
            
        Returns:
            PerformanceReport: 完整效能報告
        """
        self.logger.info("生成效能報告")
        
        # 收集當前指標
        current_metrics = await self.analyze_startup_performance(environment)
        
        # 生成優化建議
        recommendations = self.generate_optimization_recommendations(current_metrics)
        
        # 簡單的效能趨勢（實際應該從歷史數據計算）
        performance_trend = {
            'startup_time': [current_metrics.startup_time_seconds] if current_metrics.startup_time_seconds else [],
            'memory_usage': [current_metrics.memory_usage_mb] if current_metrics.memory_usage_mb else [],
            'cpu_usage': [current_metrics.cpu_usage_percent] if current_metrics.cpu_usage_percent else []
        }
        
        # 生成摘要
        summary = {
            'overall_performance': 'good' if (
                current_metrics.startup_time_seconds and 
                current_metrics.startup_time_seconds <= self.performance_targets['startup_time_seconds']
            ) else 'needs_improvement',
            'critical_issues': len([r for r in recommendations if r.priority == 'high']),
            'total_recommendations': len(recommendations),
            'target_startup_time': self.performance_targets['startup_time_seconds'],
            'current_startup_time': current_metrics.startup_time_seconds,
            'improvement_potential': self._calculate_improvement_potential(recommendations)
        }
        
        return PerformanceReport(
            timestamp=datetime.now(),
            baseline_metrics=current_metrics,  # 這裡應該使用歷史基線
            current_metrics=current_metrics,
            optimization_recommendations=recommendations,
            performance_trend=performance_trend,
            summary=summary
        )
    
    def _calculate_improvement_potential(self, recommendations: List[OptimizationRecommendation]) -> str:
        """計算改進潛力"""
        high_impact = len([r for r in recommendations if r.priority == 'high'])
        medium_impact = len([r for r in recommendations if r.priority == 'medium'])
        
        if high_impact >= 3:
            return "high"
        elif high_impact >= 1 or medium_impact >= 3:
            return "medium"
        else:
            return "low"
    
    def save_performance_report(self, report: PerformanceReport, output_path: Optional[Path] = None) -> Path:
        """保存效能報告"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.project_root / f"performance-report-{timestamp}.json"
        
        report_data = asdict(report)
        
        # 轉換datetime為字串
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=convert_datetime)
        
        self.logger.info(f"效能報告已保存: {output_path}")
        return output_path


# 工具函數
async def quick_performance_check(environment: str = 'dev') -> Dict[str, Any]:
    """快速效能檢查"""
    optimizer = PerformanceOptimizer()
    metrics = await optimizer.analyze_startup_performance(environment)
    
    return {
        'startup_time_seconds': metrics.startup_time_seconds,
        'memory_usage_mb': metrics.memory_usage_mb,
        'healthy_services': metrics.healthy_services,
        'total_services': metrics.total_services,
        'meets_target': (
            metrics.startup_time_seconds and 
            metrics.startup_time_seconds <= 300
        ) if metrics.startup_time_seconds else False
    }


# 命令行介面
async def main():
    """主函數 - 用於獨立執行效能優化工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 效能優化工具')
    parser.add_argument('command', choices=['analyze', 'optimize', 'report'],
                       help='執行的命令')
    parser.add_argument('--environment', '-e', default='dev', choices=['dev', 'prod'],
                       help='環境類型')
    parser.add_argument('--output', '-o', type=Path, help='輸出檔案路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    optimizer = PerformanceOptimizer()
    
    try:
        if args.command == 'analyze':
            metrics = await optimizer.analyze_startup_performance(args.environment)
            print(f"\n{'='*60}")
            print("🚀 ROAS Bot v2.4.3 效能分析報告")
            print(f"{'='*60}")
            print(f"分析時間: {metrics.timestamp}")
            print(f"啟動時間: {metrics.startup_time_seconds:.1f}秒" if metrics.startup_time_seconds else "啟動時間: 無法測量")
            print(f"建置時間: {metrics.build_time_seconds:.1f}秒" if metrics.build_time_seconds else "建置時間: 無法測量")
            print(f"記憶體使用: {metrics.memory_usage_mb:.1f}MB" if metrics.memory_usage_mb else "記憶體使用: 無法測量")
            print(f"健康服務: {metrics.healthy_services}/{metrics.total_services}")
            
            target_met = (
                metrics.startup_time_seconds and 
                metrics.startup_time_seconds <= optimizer.performance_targets['startup_time_seconds']
            )
            print(f"目標達成: {'✅ 是' if target_met else '❌ 否'}")
            
        elif args.command == 'optimize':
            # 生成優化配置
            compose_file = Path(f'docker-compose.{args.environment}.yml')
            optimized_config = optimizer.create_optimized_compose_config(compose_file, 'performance')
            
            output_file = args.output or Path(f'docker-compose.{args.environment}.optimized.yml')
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(optimized_config, f, default_flow_style=False, allow_unicode=True)
            
            print(f"✅ 優化配置已生成: {output_file}")
            
        elif args.command == 'report':
            report = await optimizer.generate_performance_report(args.environment)
            output_path = optimizer.save_performance_report(report, args.output)
            
            print(f"\n{'='*60}")
            print("📊 ROAS Bot v2.4.3 完整效能報告")
            print(f"{'='*60}")
            print(f"報告時間: {report.timestamp}")
            print(f"整體效能: {report.summary['overall_performance'].upper()}")
            print(f"關鍵問題: {report.summary['critical_issues']}")
            print(f"優化建議: {report.summary['total_recommendations']}")
            print(f"改進潛力: {report.summary['improvement_potential'].upper()}")
            
            if report.optimization_recommendations:
                print(f"\n🔧 優化建議:")
                for i, rec in enumerate(report.optimization_recommendations[:5], 1):
                    print(f"  {i}. [{rec.priority.upper()}] {rec.description}")
                    print(f"     實施方案: {rec.implementation}")
                    print(f"     預期改善: {rec.expected_improvement}")
            
            print(f"\n📄 完整報告: {output_path}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))