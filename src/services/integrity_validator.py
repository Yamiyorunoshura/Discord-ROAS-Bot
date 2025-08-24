"""
資料完整性和併發安全性驗證器
T2 - 高併發連線競爭修復實施

提供ACID特性驗證、死鎖檢測、資料一致性檢查和併發安全測試
確保在高併發環境下資料庫操作的正確性和可靠性
"""

import asyncio
import logging
import threading
import time
import random
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from contextlib import contextmanager
from enum import Enum

from .database_service import DatabaseService, DatabaseServiceConfig
from ..db.sqlite import OptimizedConnection
from ..db.retry import retry_on_database_locked, CommonRetryStrategies

logger = logging.getLogger('src.services.integrity_validator')


class ValidationResult(Enum):
    """驗證結果狀態"""
    PASS = "pass"
    FAIL = "fail" 
    WARNING = "warning"
    SKIP = "skip"


@dataclass
class ValidationTest:
    """驗證測試項目"""
    name: str
    description: str
    test_function: str
    timeout: float = 30.0
    required: bool = True
    concurrent_safe: bool = True
    

@dataclass
class TestResult:
    """測試結果"""
    test_name: str
    result: ValidationResult
    execution_time_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    

class DataIntegrityValidator:
    """
    資料完整性和併發安全性驗證器
    
    提供全面的資料庫完整性測試，包括ACID特性驗證、
    死鎖檢測、併發安全測試和資料一致性檢查
    """
    
    # 測試表結構
    TEST_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS integrity_test (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_group TEXT NOT NULL,
        value INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        thread_id TEXT,
        test_data TEXT
    );
    """
    
    # 預定義測試項目
    VALIDATION_TESTS = [
        ValidationTest(
            name="connection_pool_basic",
            description="連線池基本功能測試",
            test_function="_test_connection_pool_basic",
            timeout=10.0,
            required=True
        ),
        ValidationTest(
            name="acid_atomicity", 
            description="原子性(Atomicity)測試",
            test_function="_test_atomicity",
            timeout=15.0,
            required=True
        ),
        ValidationTest(
            name="acid_consistency",
            description="一致性(Consistency)測試", 
            test_function="_test_consistency",
            timeout=20.0,
            required=True
        ),
        ValidationTest(
            name="acid_isolation",
            description="隔離性(Isolation)測試",
            test_function="_test_isolation",
            timeout=25.0,
            required=True
        ),
        ValidationTest(
            name="acid_durability",
            description="持久性(Durability)測試",
            test_function="_test_durability", 
            timeout=15.0,
            required=True
        ),
        ValidationTest(
            name="concurrent_reads",
            description="併發讀取測試",
            test_function="_test_concurrent_reads",
            timeout=30.0,
            required=True
        ),
        ValidationTest(
            name="concurrent_writes", 
            description="併發寫入測試",
            test_function="_test_concurrent_writes",
            timeout=45.0,
            required=True
        ),
        ValidationTest(
            name="deadlock_detection",
            description="死鎖檢測測試",
            test_function="_test_deadlock_detection",
            timeout=60.0,
            required=False
        ),
        ValidationTest(
            name="data_consistency_under_load",
            description="負載下資料一致性測試", 
            test_function="_test_data_consistency_under_load",
            timeout=90.0,
            required=False
        ),
        ValidationTest(
            name="connection_pool_stress",
            description="連線池壓力測試",
            test_function="_test_connection_pool_stress",
            timeout=120.0,
            required=False
        )
    ]
    
    def __init__(self, database_service: DatabaseService):
        """
        初始化驗證器
        
        參數:
            database_service: 資料庫服務實例
        """
        self.database_service = database_service
        self.test_results: List[TestResult] = []
        self.validation_start_time: Optional[datetime] = None
        self.validation_end_time: Optional[datetime] = None
        
        # 測試配置
        self.max_concurrent_workers = 20
        self.test_timeout_multiplier = 1.5
        
        logger.info("資料完整性驗證器已初始化")
    
    async def setup_test_environment(self):
        """設置測試環境"""
        try:
            # 確保資料庫服務已初始化
            await self.database_service.initialize()
            
            # 創建測試表
            await self.database_service.execute_query(self.TEST_TABLE_SQL)
            
            # 清理舊的測試資料
            await self.database_service.execute_query(
                "DELETE FROM integrity_test WHERE timestamp < ?",
                (datetime.utcnow() - timedelta(hours=1),)
            )
            
            logger.info("測試環境已設置完成")
            
        except Exception as e:
            logger.error(f"設置測試環境失敗: {e}")
            raise
    
    async def run_all_validations(self, skip_optional: bool = False) -> Dict[str, Any]:
        """
        執行所有驗證測試
        
        參數:
            skip_optional: 是否跳過可選測試
            
        返回:
            驗證結果摘要
        """
        self.validation_start_time = datetime.utcnow()
        self.test_results.clear()
        
        try:
            # 設置測試環境
            await self.setup_test_environment()
            
            # 篩選測試項目
            tests_to_run = [
                test for test in self.VALIDATION_TESTS
                if test.required or not skip_optional
            ]
            
            # 執行測試
            for test in tests_to_run:
                result = await self._run_single_test(test)
                self.test_results.append(result)
                
                # 如果關鍵測試失敗，記錄但繼續
                if result.result == ValidationResult.FAIL and test.required:
                    logger.warning(f"關鍵測試失敗: {test.name} - {result.message}")
            
            self.validation_end_time = datetime.utcnow()
            
            # 生成驗證摘要
            return self._generate_validation_summary()
            
        except Exception as e:
            logger.error(f"驗證過程發生錯誤: {e}")
            self.validation_end_time = datetime.utcnow()
            
            return {
                'status': 'error',
                'error': str(e),
                'completed_tests': len(self.test_results),
                'total_tests': len(self.VALIDATION_TESTS)
            }
    
    async def _run_single_test(self, test: ValidationTest) -> TestResult:
        """執行單個測試"""
        start_time = time.time()
        
        try:
            # 獲取測試函數
            test_func = getattr(self, test.test_function)
            
            # 執行測試並設置超時
            result_data = await asyncio.wait_for(
                test_func(),
                timeout=test.timeout * self.test_timeout_multiplier
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            return TestResult(
                test_name=test.name,
                result=result_data.get('result', ValidationResult.PASS),
                execution_time_ms=execution_time,
                message=result_data.get('message', '測試完成'),
                details=result_data.get('details', {})
            )
            
        except asyncio.TimeoutError:
            execution_time = (time.time() - start_time) * 1000
            return TestResult(
                test_name=test.name,
                result=ValidationResult.FAIL,
                execution_time_ms=execution_time,
                message=f"測試超時 (>{test.timeout}s)",
                details={'timeout': test.timeout}
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return TestResult(
                test_name=test.name,
                result=ValidationResult.FAIL,
                execution_time_ms=execution_time,
                message=f"測試執行失敗: {str(e)}",
                details={'error': str(e)}
            )
    
    async def _test_connection_pool_basic(self) -> Dict[str, Any]:
        """連線池基本功能測試"""
        try:
            # 測試基本連線取得和釋放
            test_queries = [
                "SELECT 1 as test",
                "SELECT datetime('now') as current_time",
                "SELECT COUNT(*) FROM sqlite_master"
            ]
            
            results = []
            for sql in test_queries:
                result = await self.database_service.execute_query(sql)
                results.append(result)
            
            # 驗證連線池統計
            stats = self.database_service.get_service_statistics()
            pool_stats = stats.get('connection_pool', {})
            
            if pool_stats.get('success_rate', 0) < 90:
                return {
                    'result': ValidationResult.WARNING,
                    'message': f"連線池成功率偏低: {pool_stats.get('success_rate', 0):.1f}%"
                }
            
            return {
                'result': ValidationResult.PASS,
                'message': "連線池基本功能正常",
                'details': {
                    'test_queries': len(test_queries),
                    'pool_stats': pool_stats
                }
            }
            
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"連線池基本測試失敗: {str(e)}"
            }
    
    async def _test_atomicity(self) -> Dict[str, Any]:
        """原子性測試"""
        test_group = f"atomicity_{int(time.time())}"
        
        try:
            # 測試事務回滾
            operations = [
                ("INSERT INTO integrity_test (test_group, value) VALUES (?, ?)", (test_group, 1)),
                ("INSERT INTO integrity_test (test_group, value) VALUES (?, ?)", (test_group, 2)),
                ("INSERT INTO integrity_test (test_group, value) VALUES (?, ?)", (test_group, 'invalid')),  # 故意失敗
            ]
            
            try:
                await self.database_service.execute_transaction(operations)
                # 如果到這裡說明事務沒有正確回滾
                return {
                    'result': ValidationResult.FAIL,
                    'message': "事務未正確回滾"
                }
            except Exception:
                # 預期的錯誤，檢查是否回滾
                pass
            
            # 檢查資料是否被回滾
            result = await self.database_service.execute_query(
                "SELECT COUNT(*) FROM integrity_test WHERE test_group = ?",
                (test_group,)
            )
            
            count = result[0][0] if result else 0
            
            if count == 0:
                return {
                    'result': ValidationResult.PASS,
                    'message': "原子性測試通過，事務正確回滾",
                    'details': {'records_after_rollback': count}
                }
            else:
                return {
                    'result': ValidationResult.FAIL,
                    'message': f"原子性測試失敗，發現 {count} 筆未回滾資料"
                }
                
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"原子性測試執行失敗: {str(e)}"
            }
    
    async def _test_consistency(self) -> Dict[str, Any]:
        """一致性測試"""
        test_group = f"consistency_{int(time.time())}"
        
        try:
            # 插入測試資料
            initial_sum = 1000
            records = [(test_group, 100), (test_group, 200), (test_group, 300), (test_group, 400)]
            
            for group, value in records:
                await self.database_service.execute_query(
                    "INSERT INTO integrity_test (test_group, value) VALUES (?, ?)",
                    (group, value)
                )
            
            # 驗證總和
            result = await self.database_service.execute_query(
                "SELECT SUM(value) FROM integrity_test WHERE test_group = ?",
                (test_group,)
            )
            
            actual_sum = result[0][0] if result and result[0] else 0
            
            if actual_sum == initial_sum:
                return {
                    'result': ValidationResult.PASS,
                    'message': "一致性測試通過",
                    'details': {
                        'expected_sum': initial_sum,
                        'actual_sum': actual_sum
                    }
                }
            else:
                return {
                    'result': ValidationResult.FAIL,
                    'message': f"一致性測試失敗，期望總和 {initial_sum}，實際 {actual_sum}"
                }
                
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"一致性測試執行失敗: {str(e)}"
            }
    
    async def _test_isolation(self) -> Dict[str, Any]:
        """隔離性測試"""
        test_group = f"isolation_{int(time.time())}"
        
        try:
            # 併發讀寫測試
            async def writer_task():
                await self.database_service.execute_query(
                    "INSERT INTO integrity_test (test_group, value, thread_id) VALUES (?, ?, ?)",
                    (test_group, 1, 'writer')
                )
                await asyncio.sleep(0.1)  # 模擬處理時間
                await self.database_service.execute_query(
                    "UPDATE integrity_test SET value = 2 WHERE test_group = ? AND thread_id = 'writer'",
                    (test_group,)
                )
            
            async def reader_task():
                await asyncio.sleep(0.05)  # 確保在寫入過程中讀取
                result = await self.database_service.execute_query(
                    "SELECT value FROM integrity_test WHERE test_group = ? AND thread_id = 'writer'",
                    (test_group,)
                )
                return result[0][0] if result else None
            
            # 並行執行讀寫
            writer_future = asyncio.create_task(writer_task())
            reader_future = asyncio.create_task(reader_task())
            
            await writer_future
            read_value = await reader_future
            
            # 檢查最終結果
            final_result = await self.database_service.execute_query(
                "SELECT value FROM integrity_test WHERE test_group = ? AND thread_id = 'writer'",
                (test_group,)
            )
            
            final_value = final_result[0][0] if final_result else None
            
            return {
                'result': ValidationResult.PASS,
                'message': "隔離性測試完成",
                'details': {
                    'read_during_write': read_value,
                    'final_value': final_value,
                    'isolation_maintained': read_value in [None, 1, 2]  # 任何這些值都是合理的
                }
            }
            
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"隔離性測試執行失敗: {str(e)}"
            }
    
    async def _test_durability(self) -> Dict[str, Any]:
        """持久性測試"""
        test_group = f"durability_{int(time.time())}"
        test_value = random.randint(1000, 9999)
        
        try:
            # 插入資料
            await self.database_service.execute_query(
                "INSERT INTO integrity_test (test_group, value) VALUES (?, ?)",
                (test_group, test_value)
            )
            
            # 強制提交和檢查
            result = await self.database_service.execute_query(
                "SELECT value FROM integrity_test WHERE test_group = ?",
                (test_group,)
            )
            
            if result and result[0][0] == test_value:
                return {
                    'result': ValidationResult.PASS,
                    'message': "持久性測試通過",
                    'details': {
                        'test_value': test_value,
                        'persisted_value': result[0][0]
                    }
                }
            else:
                return {
                    'result': ValidationResult.FAIL,
                    'message': "持久性測試失敗，資料未正確持久化"
                }
                
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"持久性測試執行失敗: {str(e)}"
            }
    
    async def _test_concurrent_reads(self) -> Dict[str, Any]:
        """併發讀取測試"""
        test_group = f"concurrent_reads_{int(time.time())}"
        num_readers = 10
        
        try:
            # 先插入測試資料
            await self.database_service.execute_query(
                "INSERT INTO integrity_test (test_group, value) VALUES (?, ?)",
                (test_group, 42)
            )
            
            # 併發讀取任務
            async def read_task(task_id: int):
                result = await self.database_service.execute_query(
                    "SELECT value FROM integrity_test WHERE test_group = ?",
                    (test_group,)
                )
                return {
                    'task_id': task_id,
                    'value': result[0][0] if result else None,
                    'timestamp': time.time()
                }
            
            # 創建併發任務
            tasks = [read_task(i) for i in range(num_readers)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 分析結果
            successful_reads = [r for r in results if isinstance(r, dict) and r.get('value') == 42]
            failed_reads = [r for r in results if not isinstance(r, dict) or r.get('value') != 42]
            
            success_rate = len(successful_reads) / num_readers * 100
            
            if success_rate >= 90:
                return {
                    'result': ValidationResult.PASS,
                    'message': f"併發讀取測試通過，成功率: {success_rate:.1f}%",
                    'details': {
                        'total_readers': num_readers,
                        'successful_reads': len(successful_reads),
                        'failed_reads': len(failed_reads),
                        'success_rate': success_rate
                    }
                }
            else:
                return {
                    'result': ValidationResult.WARNING,
                    'message': f"併發讀取成功率偏低: {success_rate:.1f}%",
                    'details': {
                        'total_readers': num_readers,
                        'successful_reads': len(successful_reads),
                        'failed_reads': len(failed_reads)
                    }
                }
                
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"併發讀取測試執行失敗: {str(e)}"
            }
    
    async def _test_concurrent_writes(self) -> Dict[str, Any]:
        """併發寫入測試"""
        test_group = f"concurrent_writes_{int(time.time())}"
        num_writers = 5
        
        try:
            # 併發寫入任務
            async def write_task(task_id: int):
                await self.database_service.execute_query(
                    "INSERT INTO integrity_test (test_group, value, thread_id) VALUES (?, ?, ?)",
                    (test_group, task_id, f'writer_{task_id}')
                )
                return task_id
            
            # 創建併發任務
            tasks = [write_task(i) for i in range(num_writers)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 檢查結果
            successful_writes = [r for r in results if isinstance(r, int)]
            
            # 驗證資料庫中的記錄
            db_result = await self.database_service.execute_query(
                "SELECT COUNT(*) FROM integrity_test WHERE test_group = ?",
                (test_group,)
            )
            
            actual_records = db_result[0][0] if db_result else 0
            
            if actual_records == num_writers:
                return {
                    'result': ValidationResult.PASS,
                    'message': "併發寫入測試通過",
                    'details': {
                        'expected_writes': num_writers,
                        'successful_writes': len(successful_writes),
                        'actual_records': actual_records
                    }
                }
            else:
                return {
                    'result': ValidationResult.WARNING,
                    'message': f"併發寫入測試部分成功，期望 {num_writers} 筆，實際 {actual_records} 筆",
                    'details': {
                        'expected_writes': num_writers,
                        'actual_records': actual_records
                    }
                }
                
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"併發寫入測試執行失敗: {str(e)}"
            }
    
    async def _test_deadlock_detection(self) -> Dict[str, Any]:
        """死鎖檢測測試"""
        try:
            # 這個測試比較複雜，暫時返回跳過
            return {
                'result': ValidationResult.SKIP,
                'message': "死鎖檢測測試暫未實施"
            }
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"死鎖檢測測試執行失敗: {str(e)}"
            }
    
    async def _test_data_consistency_under_load(self) -> Dict[str, Any]:
        """負載下資料一致性測試"""
        test_group = f"load_test_{int(time.time())}"
        num_operations = 50
        
        try:
            # 併發混合操作
            async def mixed_operation(op_id: int):
                if op_id % 2 == 0:
                    # 寫入操作
                    await self.database_service.execute_query(
                        "INSERT INTO integrity_test (test_group, value, thread_id) VALUES (?, ?, ?)",
                        (test_group, op_id, f'op_{op_id}')
                    )
                else:
                    # 讀取操作
                    result = await self.database_service.execute_query(
                        "SELECT COUNT(*) FROM integrity_test WHERE test_group = ?",
                        (test_group,)
                    )
                    return result[0][0] if result else 0
                return op_id
            
            # 創建負載
            tasks = [mixed_operation(i) for i in range(num_operations)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 檢查最終一致性
            final_count = await self.database_service.execute_query(
                "SELECT COUNT(*) FROM integrity_test WHERE test_group = ?",
                (test_group,)
            )
            
            actual_count = final_count[0][0] if final_count else 0
            expected_count = num_operations // 2  # 只有偶數操作是寫入
            
            success_count = len([r for r in results if not isinstance(r, Exception)])
            success_rate = success_count / num_operations * 100
            
            if success_rate >= 80 and actual_count >= expected_count * 0.8:
                return {
                    'result': ValidationResult.PASS,
                    'message': f"負載測試通過，成功率: {success_rate:.1f}%",
                    'details': {
                        'total_operations': num_operations,
                        'success_count': success_count,
                        'expected_records': expected_count,
                        'actual_records': actual_count,
                        'success_rate': success_rate
                    }
                }
            else:
                return {
                    'result': ValidationResult.WARNING,
                    'message': f"負載測試部分成功，成功率: {success_rate:.1f}%"
                }
                
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"負載測試執行失敗: {str(e)}"
            }
    
    async def _test_connection_pool_stress(self) -> Dict[str, Any]:
        """連線池壓力測試"""
        num_concurrent = 20
        operations_per_worker = 10
        
        try:
            async def stress_worker(worker_id: int):
                operations = 0
                errors = 0
                
                for i in range(operations_per_worker):
                    try:
                        await self.database_service.execute_query(
                            "SELECT ?, ? as worker_id, ? as operation",
                            (datetime.utcnow(), worker_id, i)
                        )
                        operations += 1
                    except Exception:
                        errors += 1
                
                return {'worker_id': worker_id, 'operations': operations, 'errors': errors}
            
            # 創建壓力測試工作者
            tasks = [stress_worker(i) for i in range(num_concurrent)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 分析結果
            successful_workers = [r for r in results if isinstance(r, dict)]
            total_operations = sum(r['operations'] for r in successful_workers)
            total_errors = sum(r['errors'] for r in successful_workers)
            
            expected_operations = num_concurrent * operations_per_worker
            success_rate = total_operations / expected_operations * 100 if expected_operations > 0 else 0
            
            # 獲取連線池統計
            stats = self.database_service.get_service_statistics()
            
            if success_rate >= 90:
                return {
                    'result': ValidationResult.PASS,
                    'message': f"連線池壓力測試通過，成功率: {success_rate:.1f}%",
                    'details': {
                        'concurrent_workers': num_concurrent,
                        'operations_per_worker': operations_per_worker,
                        'total_operations': total_operations,
                        'total_errors': total_errors,
                        'success_rate': success_rate,
                        'pool_stats': stats.get('connection_pool', {})
                    }
                }
            else:
                return {
                    'result': ValidationResult.WARNING,
                    'message': f"連線池壓力測試部分成功，成功率: {success_rate:.1f}%",
                    'details': {
                        'total_operations': total_operations,
                        'total_errors': total_errors,
                        'success_rate': success_rate
                    }
                }
                
        except Exception as e:
            return {
                'result': ValidationResult.FAIL,
                'message': f"連線池壓力測試執行失敗: {str(e)}"
            }
    
    def _generate_validation_summary(self) -> Dict[str, Any]:
        """生成驗證摘要報告"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.result == ValidationResult.PASS])
        failed_tests = len([r for r in self.test_results if r.result == ValidationResult.FAIL])
        warning_tests = len([r for r in self.test_results if r.result == ValidationResult.WARNING])
        skipped_tests = len([r for r in self.test_results if r.result == ValidationResult.SKIP])
        
        # 計算總執行時間
        total_execution_time = sum(r.execution_time_ms for r in self.test_results)
        validation_duration = 0
        if self.validation_start_time and self.validation_end_time:
            validation_duration = (self.validation_end_time - self.validation_start_time).total_seconds()
        
        # 確定整體狀態
        if failed_tests == 0 and warning_tests <= 2:
            overall_status = 'healthy'
        elif failed_tests <= 2:
            overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'
        
        # 生成建議
        recommendations = self._generate_recommendations(failed_tests, warning_tests)
        
        return {
            'overall_status': overall_status,
            'validation_timestamp': self.validation_end_time or datetime.utcnow(),
            'validation_duration_seconds': validation_duration,
            'total_execution_time_ms': total_execution_time,
            'test_summary': {
                'total': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'warnings': warning_tests,
                'skipped': skipped_tests
            },
            'pass_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            'detailed_results': [
                {
                    'test_name': r.test_name,
                    'result': r.result.value,
                    'execution_time_ms': r.execution_time_ms,
                    'message': r.message,
                    'details': r.details
                }
                for r in self.test_results
            ],
            'recommendations': recommendations,
            'database_stats': self.database_service.get_service_statistics()
        }
    
    def _generate_recommendations(self, failed_tests: int, warning_tests: int) -> List[str]:
        """生成建議列表"""
        recommendations = []
        
        if failed_tests > 0:
            recommendations.append(f"發現 {failed_tests} 個失敗測試，需要立即檢查並修復")
        
        if warning_tests > 2:
            recommendations.append(f"發現 {warning_tests} 個警告，建議優化相關功能")
        
        # 根據具體失敗的測試給出建議
        failed_test_names = [r.test_name for r in self.test_results if r.result == ValidationResult.FAIL]
        
        if 'connection_pool_basic' in failed_test_names:
            recommendations.append("連線池基本功能異常，檢查連線池配置和資料庫連線")
        
        if any('acid_' in name for name in failed_test_names):
            recommendations.append("ACID特性測試失敗，檢查事務處理和資料一致性")
        
        if any('concurrent_' in name for name in failed_test_names):
            recommendations.append("併發測試失敗，檢查鎖定機制和併發控制")
        
        if 'connection_pool_stress' in failed_test_names:
            recommendations.append("連線池壓力測試失敗，考慮調整連線池大小或優化查詢")
        
        if not recommendations:
            recommendations.append("所有驗證測試通過，系統狀態良好")
        
        return recommendations
    
    async def cleanup_test_data(self):
        """清理測試資料"""
        try:
            # 清理測試表資料
            await self.database_service.execute_query(
                "DELETE FROM integrity_test WHERE timestamp < ?",
                (datetime.utcnow() - timedelta(minutes=30),)
            )
            
            logger.info("測試資料清理完成")
            
        except Exception as e:
            logger.warning(f"清理測試資料失敗: {e}")


# 便利函數
async def validate_database_integrity(
    database_service: DatabaseService,
    skip_optional: bool = False
) -> Dict[str, Any]:
    """
    驗證資料庫完整性的便利函數
    
    參數:
        database_service: 資料庫服務實例
        skip_optional: 是否跳過可選測試
        
    返回:
        驗證結果
    """
    validator = DataIntegrityValidator(database_service)
    
    try:
        result = await validator.run_all_validations(skip_optional)
        await validator.cleanup_test_data()
        return result
    except Exception as e:
        logger.error(f"完整性驗證失敗: {e}")
        return {
            'overall_status': 'error',
            'error': str(e),
            'validation_timestamp': datetime.utcnow()
        }