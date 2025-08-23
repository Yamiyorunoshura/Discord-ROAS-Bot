#!/usr/bin/env python3
"""
Activity Meter 併發壓測腳本
T3 - 併發與資料庫鎖定穩定性實施

模擬高併發活躍度更新場景，測試系統在壓力下的表現
生成詳細的性能指標報告，用於持續監控和基準比較
"""

import os
import sys
import time
import json
import argparse
import logging
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import multiprocessing as mp

# 確保能導入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.activity.concurrent_activity_meter import ConcurrentActivityMeterService


@dataclass
class LoadTestConfig:
    """壓測配置"""
    db_path: str
    total_operations: int = 10000
    concurrent_workers: int = 10
    guilds_count: int = 5
    users_per_guild: int = 1000
    duration_seconds: Optional[int] = None
    worker_type: str = "thread"  # "thread" or "process"
    report_interval: int = 1000
    enable_batch_operations: bool = False
    batch_size: int = 50


@dataclass
class OperationResult:
    """單次操作結果"""
    success: bool
    duration: float
    operation_type: str
    worker_id: int
    timestamp: float
    error_message: Optional[str] = None


@dataclass
class LoadTestReport:
    """壓測報告"""
    config: LoadTestConfig
    start_time: str
    end_time: str
    duration_seconds: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    success_rate: float
    operations_per_second: float
    
    # 延遲統計 (毫秒)
    latency_p50: float
    latency_p95: float
    latency_p99: float
    latency_min: float
    latency_max: float
    latency_mean: float
    
    # 錯誤統計
    error_distribution: Dict[str, int]
    
    # 工作者統計
    worker_performance: Dict[int, Dict[str, Any]]
    
    # 資料庫統計
    final_record_count: int
    database_file_size: int


class ActivityLoadTester:
    """活躍度系統壓測器"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[OperationResult] = []
        self.logger = self._setup_logger()
        
        # 確保資料庫目錄存在
        os.makedirs(os.path.dirname(config.db_path), exist_ok=True)
        
        self.logger.info(f"初始化壓測器，目標：{config.total_operations} 次操作，{config.concurrent_workers} 個工作者")
    
    def _setup_logger(self) -> logging.Logger:
        """設置日誌記錄"""
        logger = logging.getLogger('activity_load_test')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def run_load_test(self) -> LoadTestReport:
        """執行壓測"""
        self.logger.info("開始壓測...")
        start_time = time.time()
        start_time_str = datetime.now().isoformat()
        
        if self.config.worker_type == "process":
            results = self._run_process_based_test()
        else:
            results = self._run_thread_based_test()
        
        end_time = time.time()
        end_time_str = datetime.now().isoformat()
        duration = end_time - start_time
        
        self.logger.info(f"壓測完成，耗時 {duration:.2f} 秒")
        
        # 生成報告
        report = self._generate_report(results, start_time_str, end_time_str, duration)
        return report
    
    def _run_thread_based_test(self) -> List[OperationResult]:
        """執行基於執行緒的壓測"""
        operations_per_worker = self.config.total_operations // self.config.concurrent_workers
        remaining_operations = self.config.total_operations % self.config.concurrent_workers
        
        with ThreadPoolExecutor(max_workers=self.config.concurrent_workers) as executor:
            futures = []
            
            for worker_id in range(self.config.concurrent_workers):
                operations_count = operations_per_worker
                if worker_id < remaining_operations:
                    operations_count += 1
                
                future = executor.submit(
                    self._worker_function, 
                    worker_id, 
                    operations_count,
                    self.config
                )
                futures.append(future)
            
            # 收集結果
            all_results = []
            completed_count = 0
            
            for future in as_completed(futures):
                try:
                    worker_results = future.result()
                    all_results.extend(worker_results)
                    completed_count += 1
                    
                    if completed_count % max(1, self.config.concurrent_workers // 4) == 0:
                        self.logger.info(f"已完成 {completed_count}/{self.config.concurrent_workers} 個工作者")
                
                except Exception as e:
                    self.logger.error(f"工作者執行失敗：{e}")
        
        return all_results
    
    def _run_process_based_test(self) -> List[OperationResult]:
        """執行基於多進程的壓測"""
        operations_per_worker = self.config.total_operations // self.config.concurrent_workers
        remaining_operations = self.config.total_operations % self.config.concurrent_workers
        
        with ProcessPoolExecutor(max_workers=self.config.concurrent_workers) as executor:
            futures = []
            
            for worker_id in range(self.config.concurrent_workers):
                operations_count = operations_per_worker
                if worker_id < remaining_operations:
                    operations_count += 1
                
                future = executor.submit(
                    worker_process_function,
                    worker_id,
                    operations_count,
                    self.config
                )
                futures.append(future)
            
            # 收集結果
            all_results = []
            for future in as_completed(futures):
                try:
                    worker_results = future.result()
                    all_results.extend(worker_results)
                except Exception as e:
                    self.logger.error(f"進程工作者執行失敗：{e}")
        
        return all_results
    
    @staticmethod
    def _worker_function(worker_id: int, operations_count: int, config: LoadTestConfig) -> List[OperationResult]:
        """工作者函數 - 執行指定數量的操作"""
        service = ConcurrentActivityMeterService(config.db_path)
        results = []
        
        try:
            for i in range(operations_count):
                result = ActivityLoadTester._perform_operation(service, worker_id, config)
                results.append(result)
                
                # 定期報告進度
                if (i + 1) % config.report_interval == 0:
                    success_count = sum(1 for r in results if r.success)
                    success_rate = success_count / len(results)
                    print(f"工作者 {worker_id}: {i + 1}/{operations_count} 操作完成，成功率 {success_rate:.2%}")
        
        finally:
            service.close()
        
        return results
    
    @staticmethod
    def _perform_operation(service: ConcurrentActivityMeterService, worker_id: int, config: LoadTestConfig) -> OperationResult:
        """執行單次操作"""
        import random
        
        start_time = time.time()
        timestamp = start_time
        
        try:
            # 隨機選擇 guild 和 user
            guild_id = random.randint(1, config.guilds_count)
            user_id = random.randint(1, config.users_per_guild)
            score_delta = random.uniform(0.5, 3.0)
            last_msg_time = int(time.time() * 1000)
            
            if config.enable_batch_operations and random.random() < 0.3:
                # 30% 概率執行批次操作
                activities = [
                    (guild_id, user_id + j, score_delta, last_msg_time + j)
                    for j in range(min(config.batch_size, 10))
                ]
                result = service.batch_upsert_activities(activities)
                operation_type = "batch_upsert"
                success = result['success'] and result['processed'] > 0
            else:
                # 執行單次 UPSERT
                result = service.upsert_activity_score(guild_id, user_id, score_delta, last_msg_time)
                operation_type = "upsert"
                success = result['success']
            
            duration = (time.time() - start_time) * 1000  # 轉換為毫秒
            
            return OperationResult(
                success=success,
                duration=duration,
                operation_type=operation_type,
                worker_id=worker_id,
                timestamp=timestamp
            )
        
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return OperationResult(
                success=False,
                duration=duration,
                operation_type="upsert",
                worker_id=worker_id,
                timestamp=timestamp,
                error_message=str(e)
            )
    
    def _generate_report(self, results: List[OperationResult], start_time: str, end_time: str, duration: float) -> LoadTestReport:
        """生成詳細的測試報告"""
        if not results:
            raise ValueError("沒有測試結果可以生成報告")
        
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        # 延遲統計
        latencies = [r.duration for r in results]
        latencies.sort()
        
        # 錯誤統計
        error_distribution = {}
        for result in failed_results:
            error_key = result.error_message or "Unknown Error"
            error_distribution[error_key] = error_distribution.get(error_key, 0) + 1
        
        # 工作者性能統計
        worker_performance = {}
        for worker_id in range(self.config.concurrent_workers):
            worker_results = [r for r in results if r.worker_id == worker_id]
            if worker_results:
                worker_latencies = [r.duration for r in worker_results]
                worker_performance[worker_id] = {
                    'total_operations': len(worker_results),
                    'successful_operations': len([r for r in worker_results if r.success]),
                    'success_rate': len([r for r in worker_results if r.success]) / len(worker_results),
                    'average_latency': statistics.mean(worker_latencies),
                    'p95_latency': statistics.quantiles(worker_latencies, n=20)[18] if len(worker_latencies) >= 20 else max(worker_latencies)
                }
        
        # 資料庫統計
        try:
            service = ConcurrentActivityMeterService(self.config.db_path)
            stats = service.get_statistics()
            final_record_count = stats['total_activity_records']
            service.close()
        except:
            final_record_count = -1
        
        try:
            database_file_size = os.path.getsize(self.config.db_path)
        except:
            database_file_size = -1
        
        return LoadTestReport(
            config=self.config,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            total_operations=len(results),
            successful_operations=len(successful_results),
            failed_operations=len(failed_results),
            success_rate=len(successful_results) / len(results),
            operations_per_second=len(results) / duration if duration > 0 else 0,
            
            latency_p50=statistics.quantiles(latencies, n=2)[0] if len(latencies) >= 2 else latencies[0],
            latency_p95=statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
            latency_p99=statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies),
            latency_min=min(latencies),
            latency_max=max(latencies),
            latency_mean=statistics.mean(latencies),
            
            error_distribution=error_distribution,
            worker_performance=worker_performance,
            final_record_count=final_record_count,
            database_file_size=database_file_size
        )
    
    def save_report(self, report: LoadTestReport, output_path: str):
        """保存報告到文件"""
        # 保存為 JSON
        json_path = output_path.replace('.txt', '.json').replace('.md', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False, default=str)
        
        # 保存為 Markdown 報告
        md_path = output_path.replace('.json', '.md').replace('.txt', '.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(self._generate_markdown_report(report))
        
        self.logger.info(f"報告已保存到 {json_path} 和 {md_path}")
    
    def _generate_markdown_report(self, report: LoadTestReport) -> str:
        """生成 Markdown 格式的報告"""
        md_content = f"""# Activity Meter 併發壓測報告

## 測試配置

- **資料庫路徑**: `{report.config.db_path}`
- **總操作數**: {report.total_operations:,}
- **併發工作者**: {report.config.concurrent_workers}
- **目標伺服器數**: {report.config.guilds_count}
- **每伺服器用戶數**: {report.config.users_per_guild:,}
- **工作者類型**: {report.config.worker_type}
- **批次操作**: {'啟用' if report.config.enable_batch_operations else '停用'}

## 執行結果

- **開始時間**: {report.start_time}
- **結束時間**: {report.end_time}
- **執行時長**: {report.duration_seconds:.2f} 秒
- **成功操作**: {report.successful_operations:,} ({report.success_rate:.2%})
- **失敗操作**: {report.failed_operations:,}
- **平均 TPS**: {report.operations_per_second:.2f} ops/sec

## 延遲統計

| 指標 | 值 (毫秒) |
|------|----------|
| P50 | {report.latency_p50:.2f} |
| P95 | {report.latency_p95:.2f} |
| P99 | {report.latency_p99:.2f} |
| 最小值 | {report.latency_min:.2f} |
| 最大值 | {report.latency_max:.2f} |
| 平均值 | {report.latency_mean:.2f} |

## 錯誤分佈

"""
        
        if report.error_distribution:
            for error, count in report.error_distribution.items():
                md_content += f"- **{error}**: {count} 次\n"
        else:
            md_content += "無錯誤發生 ✅\n"
        
        md_content += f"""
## 工作者性能

| 工作者 ID | 總操作 | 成功操作 | 成功率 | 平均延遲 (ms) | P95 延遲 (ms) |
|----------|--------|----------|--------|---------------|---------------|
"""
        
        for worker_id, perf in report.worker_performance.items():
            md_content += f"| {worker_id} | {perf['total_operations']} | {perf['successful_operations']} | {perf['success_rate']:.2%} | {perf['average_latency']:.2f} | {perf['p95_latency']:.2f} |\n"
        
        md_content += f"""
## 資料庫狀態

- **最終記錄數**: {report.final_record_count:,}
- **資料庫文件大小**: {report.database_file_size / 1024 / 1024:.2f} MB

## 效能評估

"""
        
        # 效能評估邏輯
        if report.success_rate >= 0.99:
            md_content += "✅ **優秀**: 成功率 ≥ 99%\n"
        elif report.success_rate >= 0.95:
            md_content += "🟡 **良好**: 成功率 ≥ 95%\n"
        else:
            md_content += "🔴 **需要改進**: 成功率 < 95%\n"
        
        if report.latency_p99 <= 100:
            md_content += "✅ **優秀**: P99 延遲 ≤ 100ms\n"
        elif report.latency_p99 <= 500:
            md_content += "🟡 **可接受**: P99 延遲 ≤ 500ms\n"
        else:
            md_content += "🔴 **需要優化**: P99 延遲 > 500ms\n"
        
        if report.operations_per_second >= 1000:
            md_content += "✅ **高性能**: TPS ≥ 1000\n"
        elif report.operations_per_second >= 500:
            md_content += "🟡 **中等性能**: TPS ≥ 500\n"
        else:
            md_content += "🔴 **低性能**: TPS < 500\n"
        
        md_content += f"""
---
報告生成時間: {datetime.now().isoformat()}
"""
        
        return md_content


def worker_process_function(worker_id: int, operations_count: int, config: LoadTestConfig) -> List[OperationResult]:
    """多進程工作者函數"""
    return ActivityLoadTester._worker_function(worker_id, operations_count, config)


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='Activity Meter 併發壓測工具')
    
    parser.add_argument('--db-path', default='dbs/load_test.db', help='資料庫文件路徑')
    parser.add_argument('--operations', type=int, default=10000, help='總操作數')
    parser.add_argument('--workers', type=int, default=10, help='併發工作者數量')
    parser.add_argument('--guilds', type=int, default=5, help='測試伺服器數量')
    parser.add_argument('--users-per-guild', type=int, default=1000, help='每伺服器用戶數')
    parser.add_argument('--worker-type', choices=['thread', 'process'], default='thread', help='工作者類型')
    parser.add_argument('--enable-batch', action='store_true', help='啟用批次操作')
    parser.add_argument('--batch-size', type=int, default=50, help='批次大小')
    parser.add_argument('--output', default='load_test_report', help='輸出報告路徑前綴')
    parser.add_argument('--verbose', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # 確保資料庫路徑是絕對路徑
    if not os.path.isabs(args.db_path):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        args.db_path = os.path.join(project_root, args.db_path)
    
    config = LoadTestConfig(
        db_path=args.db_path,
        total_operations=args.operations,
        concurrent_workers=args.workers,
        guilds_count=args.guilds,
        users_per_guild=args.users_per_guild,
        worker_type=args.worker_type,
        enable_batch_operations=args.enable_batch,
        batch_size=args.batch_size
    )
    
    tester = ActivityLoadTester(config)
    report = tester.run_load_test()
    
    # 生成輸出文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"{args.output}_{timestamp}.md"
    
    tester.save_report(report, output_path)
    
    # 控制台摘要
    print("\n" + "="*60)
    print("壓測摘要")
    print("="*60)
    print(f"總操作數: {report.total_operations:,}")
    print(f"成功率: {report.success_rate:.2%}")
    print(f"平均 TPS: {report.operations_per_second:.2f}")
    print(f"P99 延遲: {report.latency_p99:.2f} ms")
    print(f"資料庫記錄數: {report.final_record_count:,}")
    print("="*60)


if __name__ == '__main__':
    main()