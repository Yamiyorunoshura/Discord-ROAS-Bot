#!/usr/bin/env python3
"""
效能基準測試工具
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

用於測試和驗證Docker啟動效能優化的效果。
"""

import asyncio
import json
import logging
import time
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 導入效能優化器
from core.performance_optimizer import PerformanceOptimizer, PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基準測試結果"""
    test_name: str
    environment: str
    timestamp: datetime
    duration_seconds: float
    success: bool
    error_message: Optional[str] = None
    metrics: Optional[PerformanceMetrics] = None


@dataclass 
class ComparisonReport:
    """對比報告"""
    baseline_result: BenchmarkResult
    optimized_result: BenchmarkResult
    improvements: Dict[str, str]
    summary: Dict[str, str]


class PerformanceBenchmark:
    """
    效能基準測試工具
    
    負責測試和對比不同配置的啟動效能，驗證優化效果。
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.optimizer = PerformanceOptimizer(project_root)
        
    async def run_startup_benchmark(self, compose_file: str, test_name: str) -> BenchmarkResult:
        """
        運行啟動基準測試
        
        Args:
            compose_file: Docker Compose文件路徑
            test_name: 測試名稱
            
        Returns:
            BenchmarkResult: 測試結果
        """
        self.logger.info(f"開始效能基準測試: {test_name}")
        start_time = time.time()
        
        try:
            # 確保清理現有容器
            await self._cleanup_containers(compose_file)
            
            # 測量完整的啟動流程
            startup_start = time.time()
            
            # 建置和啟動
            build_success = await self._build_services(compose_file)
            if not build_success:
                return BenchmarkResult(
                    test_name=test_name,
                    environment=compose_file,
                    timestamp=datetime.now(),
                    duration_seconds=time.time() - start_time,
                    success=False,
                    error_message="服務建置失敗"
                )
            
            # 啟動服務
            startup_success = await self._start_services(compose_file)
            if not startup_success:
                return BenchmarkResult(
                    test_name=test_name,
                    environment=compose_file,
                    timestamp=datetime.now(),
                    duration_seconds=time.time() - start_time,
                    success=False,
                    error_message="服務啟動失敗"
                )
            
            # 等待服務準備就緒
            ready_success = await self._wait_for_ready(compose_file)
            startup_duration = time.time() - startup_start
            
            # 收集效能指標
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                startup_time_seconds=startup_duration,
                build_time_seconds=None,  # 已包含在startup_time中
                memory_usage_mb=None,     # 稍後收集
                cpu_usage_percent=None,   # 稍後收集
            )
            
            # 如果服務準備就緒，收集資源使用情況
            if ready_success:
                memory_usage, cpu_usage = await self._collect_resource_metrics(compose_file)
                metrics.memory_usage_mb = memory_usage
                metrics.cpu_usage_percent = cpu_usage
                
                # 收集服務狀態
                healthy_count, total_count = await self._get_service_health(compose_file)
                metrics.healthy_services = healthy_count
                metrics.total_services = total_count
            
            return BenchmarkResult(
                test_name=test_name,
                environment=compose_file,
                timestamp=datetime.now(),
                duration_seconds=time.time() - start_time,
                success=ready_success,
                error_message=None if ready_success else "服務未能在預期時間內就緒",
                metrics=metrics
            )
            
        except Exception as e:
            self.logger.error(f"基準測試失敗: {str(e)}", exc_info=True)
            return BenchmarkResult(
                test_name=test_name,
                environment=compose_file,
                timestamp=datetime.now(),
                duration_seconds=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
        finally:
            # 清理測試環境
            await self._cleanup_containers(compose_file)
    
    async def _cleanup_containers(self, compose_file: str) -> None:
        """清理現有容器"""
        try:
            self.logger.debug(f"清理容器: {compose_file}")
            cmd = ['docker', 'compose', '-f', compose_file, 'down', '-v', '--remove-orphans']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            await asyncio.wait_for(process.communicate(), timeout=60)
            
            # 等待清理完成
            await asyncio.sleep(2)
            
        except Exception as e:
            self.logger.warning(f"清理容器失敗: {str(e)}")
    
    async def _build_services(self, compose_file: str) -> bool:
        """建置服務"""
        try:
            self.logger.debug(f"建置服務: {compose_file}")
            cmd = ['docker', 'compose', '-f', compose_file, 'build', '--no-cache']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=600  # 10分鐘建置超時
            )
            
            return process.returncode == 0
            
        except asyncio.TimeoutError:
            self.logger.error("服務建置超時")
            return False
        except Exception as e:
            self.logger.error(f"服務建置失敗: {str(e)}")
            return False
    
    async def _start_services(self, compose_file: str) -> bool:
        """啟動服務"""
        try:
            self.logger.debug(f"啟動服務: {compose_file}")
            cmd = ['docker', 'compose', '-f', compose_file, 'up', '-d']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300  # 5分鐘啟動超時
            )
            
            return process.returncode == 0
            
        except asyncio.TimeoutError:
            self.logger.error("服務啟動超時")
            return False
        except Exception as e:
            self.logger.error(f"服務啟動失敗: {str(e)}")
            return False
    
    async def _wait_for_ready(self, compose_file: str, max_wait_time: int = 300) -> bool:
        """等待服務準備就緒"""
        self.logger.debug(f"等待服務準備就緒: {compose_file}")
        
        start_time = time.time()
        check_interval = 10  # 10秒檢查間隔
        
        while time.time() - start_time < max_wait_time:
            try:
                healthy_count, total_count = await self._get_service_health(compose_file)
                
                if total_count > 0 and healthy_count == total_count:
                    self.logger.info(f"所有服務準備就緒 ({healthy_count}/{total_count})")
                    return True
                
                self.logger.debug(f"等待中... {healthy_count}/{total_count} 服務準備就緒")
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                self.logger.warning(f"服務狀態檢查失敗: {str(e)}")
                await asyncio.sleep(check_interval)
        
        self.logger.warning(f"服務未在 {max_wait_time} 秒內準備就緒")
        return False
    
    async def _get_service_health(self, compose_file: str) -> Tuple[int, int]:
        """獲取服務健康狀態"""
        try:
            cmd = ['docker', 'compose', '-f', compose_file, 'ps', '--format', 'json']
            
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=30, cwd=self.project_root
            )
            
            if result.returncode != 0:
                return 0, 0
            
            healthy_count = 0
            total_count = 0
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        service_data = json.loads(line)
                        total_count += 1
                        
                        state = service_data.get('State', '').lower()
                        health = service_data.get('Health', '').lower()
                        
                        # 檢查服務是否健康
                        if state == 'running':
                            if health == 'healthy' or not health:  # 無健康檢查也算健康
                                healthy_count += 1
                    except json.JSONDecodeError:
                        continue
            
            return healthy_count, total_count
            
        except Exception as e:
            self.logger.error(f"獲取服務健康狀態失敗: {str(e)}")
            return 0, 0
    
    async def _collect_resource_metrics(self, compose_file: str) -> Tuple[Optional[float], Optional[float]]:
        """收集資源使用指標"""
        try:
            # 獲取容器統計
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', 'json'],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                return None, None
            
            total_memory_mb = 0.0
            max_cpu_percent = 0.0
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        stats = json.loads(line)
                        
                        # 解析記憶體使用量
                        mem_usage_str = stats.get('MemUsage', '0B / 0B')
                        used_memory = mem_usage_str.split(' / ')[0]
                        
                        if 'MiB' in used_memory:
                            total_memory_mb += float(used_memory.replace('MiB', ''))
                        elif 'GiB' in used_memory:
                            total_memory_mb += float(used_memory.replace('GiB', '')) * 1024
                        
                        # 解析CPU使用率
                        cpu_percent_str = stats.get('CPUPerc', '0.00%').rstrip('%')
                        cpu_percent = float(cpu_percent_str)
                        max_cpu_percent = max(max_cpu_percent, cpu_percent)
                        
                    except (json.JSONDecodeError, ValueError, IndexError):
                        continue
            
            return total_memory_mb, max_cpu_percent
            
        except Exception as e:
            self.logger.error(f"收集資源指標失敗: {str(e)}")
            return None, None
    
    async def compare_configurations(self, baseline_compose: str, optimized_compose: str) -> ComparisonReport:
        """
        對比兩種配置的效能
        
        Args:
            baseline_compose: 基線配置文件
            optimized_compose: 優化配置文件
            
        Returns:
            ComparisonReport: 對比報告
        """
        self.logger.info("開始配置效能對比測試")
        
        # 測試基線配置
        self.logger.info("測試基線配置...")
        baseline_result = await self.run_startup_benchmark(baseline_compose, "基線配置")
        
        # 等待一段時間確保系統穩定
        await asyncio.sleep(30)
        
        # 測試優化配置
        self.logger.info("測試優化配置...")
        optimized_result = await self.run_startup_benchmark(optimized_compose, "優化配置")
        
        # 計算改進
        improvements = self._calculate_improvements(baseline_result, optimized_result)
        
        # 生成總結
        summary = self._generate_comparison_summary(baseline_result, optimized_result, improvements)
        
        return ComparisonReport(
            baseline_result=baseline_result,
            optimized_result=optimized_result,
            improvements=improvements,
            summary=summary
        )
    
    def _calculate_improvements(self, baseline: BenchmarkResult, optimized: BenchmarkResult) -> Dict[str, str]:
        """計算改進指標"""
        improvements = {}
        
        # 啟動時間改進
        if (baseline.metrics and baseline.metrics.startup_time_seconds and
            optimized.metrics and optimized.metrics.startup_time_seconds):
            
            baseline_time = baseline.metrics.startup_time_seconds
            optimized_time = optimized.metrics.startup_time_seconds
            
            if baseline_time > 0:
                time_improvement = ((baseline_time - optimized_time) / baseline_time) * 100
                improvements['startup_time'] = f"{time_improvement:.1f}% ({baseline_time:.1f}s → {optimized_time:.1f}s)"
        
        # 記憶體使用改進
        if (baseline.metrics and baseline.metrics.memory_usage_mb and
            optimized.metrics and optimized.metrics.memory_usage_mb):
            
            baseline_mem = baseline.metrics.memory_usage_mb
            optimized_mem = optimized.metrics.memory_usage_mb
            
            if baseline_mem > 0:
                mem_improvement = ((baseline_mem - optimized_mem) / baseline_mem) * 100
                improvements['memory_usage'] = f"{mem_improvement:.1f}% ({baseline_mem:.1f}MB → {optimized_mem:.1f}MB)"
        
        # 成功率改進
        baseline_success = 1 if baseline.success else 0
        optimized_success = 1 if optimized.success else 0
        improvements['success_rate'] = f"基線: {'成功' if baseline_success else '失敗'}, 優化: {'成功' if optimized_success else '失敗'}"
        
        return improvements
    
    def _generate_comparison_summary(self, baseline: BenchmarkResult, optimized: BenchmarkResult, 
                                   improvements: Dict[str, str]) -> Dict[str, str]:
        """生成對比總結"""
        summary = {
            'test_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'baseline_config': baseline.environment,
            'optimized_config': optimized.environment,
            'baseline_success': '成功' if baseline.success else '失敗',
            'optimized_success': '成功' if optimized.success else '失敗',
        }
        
        # 評估整體改進
        if baseline.success and optimized.success:
            if baseline.metrics and optimized.metrics:
                if (baseline.metrics.startup_time_seconds and optimized.metrics.startup_time_seconds and
                    optimized.metrics.startup_time_seconds < baseline.metrics.startup_time_seconds):
                    summary['overall_result'] = '優化有效：啟動時間顯著改善'
                elif (baseline.metrics.startup_time_seconds and optimized.metrics.startup_time_seconds and
                      optimized.metrics.startup_time_seconds <= baseline.metrics.startup_time_seconds * 1.1):
                    summary['overall_result'] = '優化中等：啟動時間略有改善或持平'
                else:
                    summary['overall_result'] = '優化無效：啟動時間未改善'
            else:
                summary['overall_result'] = '數據不足：無法確定優化效果'
        elif not baseline.success and optimized.success:
            summary['overall_result'] = '優化顯著：修復了啟動問題'
        elif baseline.success and not optimized.success:
            summary['overall_result'] = '優化失敗：引入了新問題'
        else:
            summary['overall_result'] = '雙方失敗：需要檢查配置問題'
        
        return summary
    
    def save_comparison_report(self, report: ComparisonReport, output_path: Optional[Path] = None) -> Path:
        """保存對比報告"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.project_root / f"performance-comparison-{timestamp}.json"
        
        # 轉換數據
        report_data = asdict(report)
        
        # 處理datetime序列化
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=convert_datetime)
        
        self.logger.info(f"對比報告已保存: {output_path}")
        return output_path


async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 效能基準測試工具')
    parser.add_argument('command', choices=['benchmark', 'compare'],
                       help='執行的命令')
    parser.add_argument('--compose-file', required=True, 
                       help='Docker Compose文件路徑')
    parser.add_argument('--baseline-compose', 
                       help='基線配置文件（僅用於compare命令）')
    parser.add_argument('--test-name', default='效能測試',
                       help='測試名稱')
    parser.add_argument('--output', type=Path, help='輸出檔案路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    benchmark = PerformanceBenchmark()
    
    try:
        if args.command == 'benchmark':
            # 單一配置基準測試
            result = await benchmark.run_startup_benchmark(args.compose_file, args.test_name)
            
            print(f"\n{'='*60}")
            print("🚀 ROAS Bot 效能基準測試報告")
            print(f"{'='*60}")
            print(f"測試名稱: {result.test_name}")
            print(f"配置文件: {result.environment}")
            print(f"測試時間: {result.timestamp}")
            print(f"測試結果: {'✅ 成功' if result.success else '❌ 失敗'}")
            print(f"總耗時: {result.duration_seconds:.1f}秒")
            
            if result.error_message:
                print(f"錯誤訊息: {result.error_message}")
            
            if result.metrics:
                print(f"\n效能指標:")
                if result.metrics.startup_time_seconds:
                    print(f"  啟動時間: {result.metrics.startup_time_seconds:.1f}秒")
                if result.metrics.memory_usage_mb:
                    print(f"  記憶體使用: {result.metrics.memory_usage_mb:.1f}MB")
                if result.metrics.cpu_usage_percent:
                    print(f"  CPU使用率: {result.metrics.cpu_usage_percent:.1f}%")
                print(f"  服務狀態: {result.metrics.healthy_services}/{result.metrics.total_services} 健康")
            
            # 評估是否達到目標
            target_time = 300  # 5分鐘
            if result.metrics and result.metrics.startup_time_seconds:
                meets_target = result.metrics.startup_time_seconds <= target_time
                print(f"\n目標達成: {'✅ 是' if meets_target else '❌ 否'} (目標: ≤{target_time}秒)")
            
        elif args.command == 'compare':
            # 配置對比測試
            if not args.baseline_compose:
                print("❌ 對比測試需要提供 --baseline-compose 參數")
                return 1
            
            report = await benchmark.compare_configurations(args.baseline_compose, args.compose_file)
            output_path = benchmark.save_comparison_report(report, args.output)
            
            print(f"\n{'='*60}")
            print("📊 ROAS Bot 效能對比報告") 
            print(f"{'='*60}")
            print(f"測試日期: {report.summary['test_date']}")
            print(f"基線配置: {report.summary['baseline_config']}")
            print(f"優化配置: {report.summary['optimized_config']}")
            print(f"基線結果: {report.summary['baseline_success']}")
            print(f"優化結果: {report.summary['optimized_success']}")
            print(f"\n總體評估: {report.summary['overall_result']}")
            
            if report.improvements:
                print(f"\n🔧 改進指標:")
                for metric, improvement in report.improvements.items():
                    print(f"  {metric}: {improvement}")
            
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