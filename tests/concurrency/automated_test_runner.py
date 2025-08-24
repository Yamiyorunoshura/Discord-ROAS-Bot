#!/usr/bin/env python3
"""
T2 - 併發測試自動化和持續集成系統
提供自動化的測試執行、結果分析和CI/CD集成功能
"""

import asyncio
import json
import logging
import os
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import subprocess

# 添加專案路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.connection_pool.connection_pool_manager import ConnectionPoolManager
from services.connection_pool.models import PoolConfiguration
from error_rate_monitor import ErrorRateMonitor, ConcurrencyTestReporter, PerformanceThresholds

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ConcurrencyTestSuite:
    """自動化併發測試套件"""
    
    def __init__(self, config_file: Optional[str] = None):
        """初始化測試套件"""
        self.config = self._load_config(config_file)
        self.results_dir = Path(self.config.get('results_dir', 'test_reports/concurrency'))
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.monitor = ErrorRateMonitor(
            thresholds=PerformanceThresholds(**self.config.get('thresholds', {}))
        )
        self.reporter = ConcurrencyTestReporter(str(self.results_dir))
        
        self.test_results = []
        self.overall_success = True
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """加載測試配置"""
        default_config = {
            "tests": [
                {
                    "name": "basic_concurrency",
                    "workers": 10,
                    "operations_per_worker": 20,
                    "timeout_seconds": 60
                },
                {
                    "name": "stress_test", 
                    "workers": 20,
                    "operations_per_worker": 15,
                    "timeout_seconds": 120
                },
                {
                    "name": "burst_load",
                    "workers": 25,
                    "operations_per_worker": 10,
                    "timeout_seconds": 90
                }
            ],
            "connection_pool": {
                "min_connections": 3,
                "max_connections": 30,
                "connection_timeout": 15.0,
                "acquire_timeout": 10.0
            },
            "thresholds": {
                "max_error_rate": 1.0,
                "max_p95_response_time_ms": 50.0,
                "min_success_rate": 99.0,
                "max_concurrent_failures": 3
            },
            "results_dir": "test_reports/concurrency",
            "database_path": None  # 使用臨時資料庫
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
                    logger.info(f"已載入配置文件：{config_file}")
            except Exception as e:
                logger.warning(f"無法載入配置文件 {config_file}：{e}，使用默認配置")
        
        return default_config
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """執行所有配置的測試"""
        logger.info("🚀 開始執行自動化併發測試套件")
        logger.info(f"測試數量：{len(self.config['tests'])}")
        logger.info(f"結果目錄：{self.results_dir}")
        
        start_time = time.time()
        
        for i, test_config in enumerate(self.config['tests'], 1):
            logger.info(f"[{i}/{len(self.config['tests'])}] 執行測試：{test_config['name']}")
            
            try:
                test_result = await self._run_single_test(test_config)
                self.test_results.append(test_result)
                
                # 記錄到監控系統
                self.monitor.record_operation_batch(
                    successful_ops=test_result['successful_operations'],
                    failed_ops=test_result['failed_operations'],
                    response_times=test_result['response_times'],
                    concurrent_workers=test_config['workers'],
                    error_details=test_result['error_details'],
                    phase=test_config['name']
                )
                
                # 檢查測試是否通過
                if not self._is_test_passing(test_result):
                    self.overall_success = False
                    logger.warning(f"❌ 測試 {test_config['name']} 未通過標準")
                else:
                    logger.info(f"✅ 測試 {test_config['name']} 通過標準")
                    
            except Exception as e:
                logger.error(f"❌ 測試 {test_config['name']} 執行失敗：{e}")
                self.overall_success = False
                
                # 記錄失敗的測試
                failed_result = {
                    'test_name': test_config['name'],
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                self.test_results.append(failed_result)
        
        total_duration = time.time() - start_time
        
        # 生成綜合報告
        final_report = self._generate_final_report(total_duration)
        
        logger.info("📋 測試套件執行完成")
        logger.info(f"總耗時：{total_duration:.2f} 秒")
        logger.info(f"整體結果：{'通過' if self.overall_success else '失敗'}")
        
        return final_report
    
    async def _run_single_test(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """執行單個併發測試"""
        import tempfile
        
        # 創建臨時資料庫
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_path = temp_db.name
        temp_db.close()
        
        # 配置連線池
        pool_config = PoolConfiguration(**self.config['connection_pool'])
        pool_manager = ConnectionPoolManager(db_path=db_path, config=pool_config)
        
        try:
            await pool_manager.start()
            
            # 建立測試表
            async with pool_manager.connection() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS auto_test_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        worker_id INTEGER NOT NULL,
                        data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await conn.commit()
            
            # 執行測試
            start_time = time.time()
            successful_operations = 0
            failed_operations = 0
            response_times = []
            error_details = {}
            
            async def test_worker(worker_id: int):
                """測試工作者"""
                nonlocal successful_operations, failed_operations, response_times, error_details
                
                for op_id in range(test_config['operations_per_worker']):
                    op_start = time.time()
                    
                    try:
                        async with pool_manager.connection() as conn:
                            # 插入操作
                            await conn.execute(
                                "INSERT INTO auto_test_data (worker_id, data) VALUES (?, ?)",
                                (worker_id, f"data_{worker_id}_{op_id}")
                            )
                            
                            # 查詢操作
                            async with conn.execute(
                                "SELECT COUNT(*) as count FROM auto_test_data WHERE worker_id = ?",
                                (worker_id,)
                            ) as cursor:
                                result = await cursor.fetchone()
                            
                            await conn.commit()
                            
                            successful_operations += 1
                            op_time = (time.time() - op_start) * 1000
                            response_times.append(op_time)
                    
                    except Exception as e:
                        failed_operations += 1
                        error_type = type(e).__name__
                        if error_type not in error_details:
                            error_details[error_type] = 0
                        error_details[error_type] += 1
                        
                        logger.debug(f"Worker {worker_id} 操作 {op_id} 失敗：{e}")
                    
                    # 短暫延遲
                    await asyncio.sleep(0.01)
            
            # 啟動所有工作者
            timeout = test_config.get('timeout_seconds', 60)
            tasks = [test_worker(i) for i in range(test_config['workers'])]
            
            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"測試 {test_config['name']} 超時 ({timeout}s)")
                failed_operations += 1
                error_details['timeout'] = 1
            
            duration = time.time() - start_time
            total_operations = successful_operations + failed_operations
            
            # 計算統計
            success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
            error_rate = (failed_operations / total_operations * 100) if total_operations > 0 else 0
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # 計算P95響應時間
            sorted_times = sorted(response_times)
            p95_index = int(0.95 * len(sorted_times)) if sorted_times else 0
            p95_response_time = sorted_times[p95_index] if sorted_times else 0
            
            return {
                'test_name': test_config['name'],
                'status': 'completed',
                'timestamp': datetime.now().isoformat(),
                'duration_seconds': duration,
                'concurrent_workers': test_config['workers'],
                'operations_per_worker': test_config['operations_per_worker'],
                'total_operations': total_operations,
                'successful_operations': successful_operations,
                'failed_operations': failed_operations,
                'success_rate_percent': success_rate,
                'error_rate_percent': error_rate,
                'average_response_time_ms': avg_response_time,
                'p95_response_time_ms': p95_response_time,
                'throughput_ops_per_sec': total_operations / duration if duration > 0 else 0,
                'response_times': response_times,
                'error_details': error_details
            }
            
        finally:
            await pool_manager.stop()
            
            # 清理臨時檔案
            try:
                os.unlink(db_path)
            except OSError:
                pass
    
    def _is_test_passing(self, test_result: Dict[str, Any]) -> bool:
        """檢查測試是否通過標準"""
        if test_result.get('status') != 'completed':
            return False
        
        thresholds = self.config['thresholds']
        
        return (
            test_result['error_rate_percent'] <= thresholds['max_error_rate'] and
            test_result['p95_response_time_ms'] <= thresholds['max_p95_response_time_ms'] and
            test_result['success_rate_percent'] >= thresholds['min_success_rate']
        )
    
    def _generate_final_report(self, total_duration: float) -> Dict[str, Any]:
        """生成最終測試報告"""
        # 計算綜合統計
        completed_tests = [r for r in self.test_results if r.get('status') == 'completed']
        
        if completed_tests:
            total_ops = sum(r['total_operations'] for r in completed_tests)
            total_successful = sum(r['successful_operations'] for r in completed_tests)
            total_failed = sum(r['failed_operations'] for r in completed_tests)
            
            avg_success_rate = sum(r['success_rate_percent'] for r in completed_tests) / len(completed_tests)
            avg_error_rate = sum(r['error_rate_percent'] for r in completed_tests) / len(completed_tests)
            avg_response_time = sum(r['average_response_time_ms'] for r in completed_tests) / len(completed_tests)
            max_p95_response_time = max(r['p95_response_time_ms'] for r in completed_tests)
        else:
            total_ops = total_successful = total_failed = 0
            avg_success_rate = avg_error_rate = avg_response_time = max_p95_response_time = 0
        
        passing_tests = sum(1 for r in self.test_results if self._is_test_passing(r))
        
        # 生成監控報告
        test_config = {
            'test_type': 'automated_concurrency_suite',
            'total_tests': len(self.test_results),
            'configuration': self.config
        }
        
        monitor_report = self.reporter.generate_comprehensive_report(
            self.monitor, test_config, total_duration
        )
        
        final_report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'test_suite_version': '2.4.2',
                'total_duration_seconds': total_duration,
                'overall_success': self.overall_success
            },
            'test_summary': {
                'total_tests': len(self.test_results),
                'passing_tests': passing_tests,
                'failing_tests': len(self.test_results) - passing_tests,
                'success_rate_percent': (passing_tests / len(self.test_results) * 100) if self.test_results else 0
            },
            'performance_summary': {
                'total_operations': total_ops,
                'successful_operations': total_successful,
                'failed_operations': total_failed,
                'average_success_rate_percent': avg_success_rate,
                'average_error_rate_percent': avg_error_rate,
                'average_response_time_ms': avg_response_time,
                'max_p95_response_time_ms': max_p95_response_time
            },
            'individual_test_results': self.test_results,
            'monitoring_report': monitor_report,
            'ci_cd_integration': self._generate_ci_results()
        }
        
        # 保存報告
        self._save_final_report(final_report)
        
        return final_report
    
    def _generate_ci_results(self) -> Dict[str, Any]:
        """生成CI/CD集成結果"""
        return {
            'exit_code': 0 if self.overall_success else 1,
            'junit_xml_available': False,  # 可以擴展支持JUnit XML格式
            'coverage_report': False,      # 可以擴展支持覆蓋率報告
            'artifacts': [
                str(self.results_dir / f"concurrency_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            ],
            'badges': {
                'tests_passing': f"{sum(1 for r in self.test_results if self._is_test_passing(r))}/{len(self.test_results)}",
                'overall_status': 'passing' if self.overall_success else 'failing'
            }
        }
    
    def _save_final_report(self, report: Dict[str, Any]) -> str:
        """保存最終報告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"automated_concurrency_suite_{timestamp}.json"
        filepath = self.results_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"最終報告已保存：{filepath}")
        return str(filepath)


class CIIntegration:
    """持續集成系統整合"""
    
    @staticmethod
    def create_github_workflow() -> str:
        """創建GitHub Actions工作流程"""
        workflow_content = """name: T2 Concurrency Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2點執行

jobs:
  concurrency-tests:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run concurrency tests
      run: |
        python tests/concurrency/automated_test_runner.py --mode=ci --timeout=1800
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: concurrency-test-results
        path: test_reports/concurrency/
    
    - name: Comment PR with results
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          const reportPath = 'test_reports/concurrency/ci_summary.json';
          if (fs.existsSync(reportPath)) {
            const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
            const comment = `## 🧪 T2 併發測試結果
            
            - **總測試數**: ${report.total_tests}
            - **通過測試**: ${report.passing_tests}
            - **失敗測試**: ${report.failing_tests}
            - **整體狀態**: ${report.overall_success ? '✅ 通過' : '❌ 失敗'}
            - **錯誤率**: ${report.average_error_rate_percent.toFixed(2)}%
            - **平均響應時間**: ${report.average_response_time_ms.toFixed(2)}ms
            
            詳細報告請查看 Actions artifacts。
            `;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
          }
"""
        
        workflow_file = Path(".github/workflows/concurrency-tests.yml")
        workflow_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(workflow_file, 'w', encoding='utf-8') as f:
            f.write(workflow_content)
        
        return str(workflow_file)
    
    @staticmethod
    def create_docker_compose() -> str:
        """創建Docker Compose配置用於測試環境"""
        compose_content = """version: '3.8'

services:
  concurrency-test:
    build: .
    environment:
      - TEST_MODE=concurrency
      - RESULTS_DIR=/app/test_reports
    volumes:
      - ./test_reports:/app/test_reports
      - ./tests:/app/tests
    command: python tests/concurrency/automated_test_runner.py --mode=docker
    
  test-db:
    image: sqlite:latest
    volumes:
      - test_data:/var/lib/sqlite
    
volumes:
  test_data:
"""
        
        compose_file = Path("docker-compose.test.yml")
        with open(compose_file, 'w', encoding='utf-8') as f:
            f.write(compose_content)
        
        return str(compose_file)


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='T2 併發測試自動化執行器')
    parser.add_argument('--mode', choices=['dev', 'ci', 'docker'], default='dev',
                       help='執行模式')
    parser.add_argument('--config', type=str, 
                       help='配置文件路徑')
    parser.add_argument('--timeout', type=int, default=1800,
                       help='總超時時間（秒）')
    parser.add_argument('--create-ci-files', action='store_true',
                       help='創建CI/CD配置文件')
    
    args = parser.parse_args()
    
    if args.create_ci_files:
        logger.info("創建CI/CD配置文件...")
        workflow_file = CIIntegration.create_github_workflow()
        compose_file = CIIntegration.create_docker_compose()
        logger.info(f"✅ GitHub Actions工作流程已創建：{workflow_file}")
        logger.info(f"✅ Docker Compose配置已創建：{compose_file}")
        return
    
    logger.info(f"以 {args.mode} 模式執行併發測試")
    
    try:
        test_suite = ConcurrencyTestSuite(args.config)
        
        # 設定超時
        report = await asyncio.wait_for(
            test_suite.run_all_tests(), 
            timeout=args.timeout
        )
        
        # 根據模式輸出不同格式的結果
        if args.mode == 'ci':
            # CI模式：輸出簡潔結果並設定退出碼
            ci_results = report['ci_cd_integration']
            summary = {
                'total_tests': report['test_summary']['total_tests'],
                'passing_tests': report['test_summary']['passing_tests'], 
                'failing_tests': report['test_summary']['failing_tests'],
                'overall_success': report['report_metadata']['overall_success'],
                'average_error_rate_percent': report['performance_summary']['average_error_rate_percent'],
                'average_response_time_ms': report['performance_summary']['average_response_time_ms']
            }
            
            # 為CI系統保存簡化摘要
            summary_file = Path('test_reports/concurrency/ci_summary.json')
            summary_file.parent.mkdir(parents=True, exist_ok=True)
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)
            
            if report['report_metadata']['overall_success']:
                logger.info("🎉 所有併發測試通過！")
                sys.exit(0)
            else:
                logger.error("❌ 部分併發測試失敗")
                sys.exit(1)
        
        else:
            # 開發模式：顯示詳細結果
            logger.info("=" * 80)
            logger.info("📊 測試套件執行摘要")
            logger.info("=" * 80)
            
            test_summary = report['test_summary']
            perf_summary = report['performance_summary']
            
            logger.info(f"測試總數：{test_summary['total_tests']}")
            logger.info(f"通過測試：{test_summary['passing_tests']}")
            logger.info(f"失敗測試：{test_summary['failing_tests']}")
            logger.info(f"成功率：{test_summary['success_rate_percent']:.1f}%")
            
            logger.info(f"\n📈 效能摘要：")
            logger.info(f"總操作數：{perf_summary['total_operations']}")
            logger.info(f"平均錯誤率：{perf_summary['average_error_rate_percent']:.2f}%")
            logger.info(f"平均響應時間：{perf_summary['average_response_time_ms']:.2f}ms")
            logger.info(f"最大P95響應時間：{perf_summary['max_p95_response_time_ms']:.2f}ms")
            
            if report['report_metadata']['overall_success']:
                logger.info("\n🎉 所有測試都通過了T2標準！")
            else:
                logger.warning("\n⚠️ 部分測試需要優化")
        
    except asyncio.TimeoutError:
        logger.error(f"❌ 測試套件執行超時 ({args.timeout}秒)")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 測試套件執行失敗：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())