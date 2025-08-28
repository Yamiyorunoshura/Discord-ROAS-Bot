"""
子機器人資料庫異步操作管理器
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供完整的異步操作支援：
- 非阻塞資料庫操作執行
- 並發控制和資源管理
- 任務佇列和批次處理
- 異步操作監控和統計
- 背景任務管理和調度
- 操作超時和取消機制
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, TypeVar, Generic, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import weakref
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

# 核心依賴
from core.base_service import BaseService
from .subbot_database_service import SubBotDatabaseService
from .error_handler import SubBotErrorHandler, ErrorContext, error_handler

logger = logging.getLogger('core.database.async_manager')

T = TypeVar('T')


class OperationType(Enum):
    """操作類型"""
    READ = "read"
    WRITE = "write"
    BATCH = "batch"
    TRANSACTION = "transaction"
    BACKGROUND = "background"


class OperationPriority(Enum):
    """操作優先級"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class OperationStatus(Enum):
    """操作狀態"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class AsyncOperation(Generic[T]):
    """異步操作描述"""
    id: str
    operation_type: OperationType
    priority: OperationPriority
    func: Callable[..., T]
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: OperationStatus = OperationStatus.PENDING
    result: Optional[T] = None
    error: Optional[Exception] = None
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 0
    context: Optional[ErrorContext] = None
    future: Optional[asyncio.Future] = None
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'id': self.id,
            'operation_type': self.operation_type.value,
            'priority': self.priority.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'timeout': self.timeout,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'has_error': self.error is not None,
            'error_message': str(self.error) if self.error else None,
            'dependencies': self.dependencies
        }


@dataclass
class BatchOperation:
    """批次操作"""
    id: str
    operations: List[AsyncOperation]
    strategy: str = "parallel"  # parallel, sequential, mixed
    max_concurrency: int = 5
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: OperationStatus = OperationStatus.PENDING
    results: List[Any] = field(default_factory=list)
    errors: List[Exception] = field(default_factory=list)
    
    @property
    def success_count(self) -> int:
        """成功操作數量"""
        return sum(1 for op in self.operations if op.status == OperationStatus.COMPLETED)
    
    @property
    def failure_count(self) -> int:
        """失敗操作數量"""
        return sum(1 for op in self.operations if op.status == OperationStatus.FAILED)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'id': self.id,
            'total_operations': len(self.operations),
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'strategy': self.strategy,
            'max_concurrency': self.max_concurrency,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'operations': [op.to_dict() for op in self.operations]
        }


class ResourcePool:
    """資源池管理"""
    
    def __init__(
        self,
        max_concurrent_reads: int = 50,
        max_concurrent_writes: int = 10,
        max_concurrent_transactions: int = 5,
        max_queue_size: int = 1000
    ):
        self.max_concurrent_reads = max_concurrent_reads
        self.max_concurrent_writes = max_concurrent_writes
        self.max_concurrent_transactions = max_concurrent_transactions
        self.max_queue_size = max_queue_size
        
        # 信號量控制並發數量
        self.read_semaphore = asyncio.Semaphore(max_concurrent_reads)
        self.write_semaphore = asyncio.Semaphore(max_concurrent_writes)
        self.transaction_semaphore = asyncio.Semaphore(max_concurrent_transactions)
        
        # 當前運行的操作
        self.running_operations: Dict[OperationType, int] = defaultdict(int)
        
        # 等待隊列
        self.pending_operations: Dict[OperationPriority, deque] = {
            priority: deque() for priority in OperationPriority
        }
        
        # 統計資訊
        self.stats = {
            'total_operations': 0,
            'completed_operations': 0,
            'failed_operations': 0,
            'peak_concurrent_operations': 0,
            'average_wait_time': 0.0,
            'queue_overflow_count': 0
        }
    
    @asynccontextmanager
    async def acquire_resource(self, operation_type: OperationType):
        """獲取資源"""
        # 選擇對應的信號量
        semaphore = {
            OperationType.READ: self.read_semaphore,
            OperationType.WRITE: self.write_semaphore,
            OperationType.TRANSACTION: self.transaction_semaphore,
            OperationType.BATCH: self.write_semaphore,  # 批次操作使用寫信號量
            OperationType.BACKGROUND: self.read_semaphore  # 背景任務使用讀信號量
        }.get(operation_type, self.read_semaphore)
        
        try:
            # 獲取資源
            await semaphore.acquire()
            self.running_operations[operation_type] += 1
            
            # 更新統計
            total_running = sum(self.running_operations.values())
            self.stats['peak_concurrent_operations'] = max(
                self.stats['peak_concurrent_operations'],
                total_running
            )
            
            yield
            
        finally:
            # 釋放資源
            semaphore.release()
            self.running_operations[operation_type] -= 1
    
    def can_accept_operation(self) -> bool:
        """檢查是否可以接受新操作"""
        total_pending = sum(len(queue) for queue in self.pending_operations.values())
        return total_pending < self.max_queue_size
    
    def add_to_queue(self, operation: AsyncOperation) -> bool:
        """添加操作到佇列"""
        if not self.can_accept_operation():
            self.stats['queue_overflow_count'] += 1
            return False
        
        self.pending_operations[operation.priority].appendleft(operation)
        return True
    
    def get_next_operation(self) -> Optional[AsyncOperation]:
        """獲取下一個操作（優先級順序）"""
        # 按優先級從高到低檢查
        for priority in sorted(OperationPriority, key=lambda x: x.value, reverse=True):
            if self.pending_operations[priority]:
                return self.pending_operations[priority].pop()
        
        return None
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """獲取資源使用情況"""
        return {
            'running_operations': dict(self.running_operations),
            'pending_by_priority': {
                priority.name: len(queue)
                for priority, queue in self.pending_operations.items()
            },
            'resource_limits': {
                'max_concurrent_reads': self.max_concurrent_reads,
                'max_concurrent_writes': self.max_concurrent_writes,
                'max_concurrent_transactions': self.max_concurrent_transactions,
                'max_queue_size': self.max_queue_size
            },
            'utilization': {
                'read_utilization': (self.max_concurrent_reads - self.read_semaphore._value) / self.max_concurrent_reads * 100,
                'write_utilization': (self.max_concurrent_writes - self.write_semaphore._value) / self.max_concurrent_writes * 100,
                'transaction_utilization': (self.max_concurrent_transactions - self.transaction_semaphore._value) / self.max_concurrent_transactions * 100
            }
        }


class TaskScheduler:
    """任務調度器"""
    
    def __init__(self, resource_pool: ResourcePool):
        self.resource_pool = resource_pool
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: deque = deque(maxlen=1000)
        self.scheduler_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()
        
    async def start(self):
        """啟動調度器"""
        if self.scheduler_task is None or self.scheduler_task.done():
            self.shutdown_event.clear()
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop(self):
        """停止調度器"""
        self.shutdown_event.set()
        if self.scheduler_task and not self.scheduler_task.done():
            try:
                await asyncio.wait_for(self.scheduler_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.scheduler_task.cancel()
        
        # 等待所有運行中的任務完成或取消
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
    
    async def schedule_operation(self, operation: AsyncOperation) -> bool:
        """調度操作"""
        # 檢查依賴
        if not await self._check_dependencies(operation):
            return False
        
        # 添加到資源池佇列
        return self.resource_pool.add_to_queue(operation)
    
    async def _scheduler_loop(self):
        """調度循環"""
        while not self.shutdown_event.is_set():
            try:
                # 獲取下一個操作
                operation = self.resource_pool.get_next_operation()
                
                if operation:
                    # 執行操作
                    task = asyncio.create_task(self._execute_operation(operation))
                    self.running_tasks[operation.id] = task
                    
                    # 設置任務完成回調
                    task.add_done_callback(lambda t, op_id=operation.id: self._on_task_completed(op_id))
                
                # 短暫等待避免忙等待
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"調度循環發生錯誤: {e}")
                await asyncio.sleep(1.0)  # 錯誤後稍長等待
    
    async def _execute_operation(self, operation: AsyncOperation):
        """執行操作"""
        try:
            # 更新狀態
            operation.status = OperationStatus.RUNNING
            operation.started_at = datetime.now()
            
            # 獲取資源
            async with self.resource_pool.acquire_resource(operation.operation_type):
                # 設置超時
                if operation.timeout:
                    operation.result = await asyncio.wait_for(
                        operation.func(*operation.args, **operation.kwargs),
                        timeout=operation.timeout
                    )
                else:
                    operation.result = await operation.func(*operation.args, **operation.kwargs)
            
            # 更新狀態
            operation.status = OperationStatus.COMPLETED
            operation.completed_at = datetime.now()
            
            # 更新統計
            self.resource_pool.stats['completed_operations'] += 1
            
        except asyncio.TimeoutError:
            operation.status = OperationStatus.TIMEOUT
            operation.error = asyncio.TimeoutError(f"Operation {operation.id} timed out")
            
        except asyncio.CancelledError:
            operation.status = OperationStatus.CANCELLED
            raise
            
        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error = e
            operation.completed_at = datetime.now()
            
            # 更新統計
            self.resource_pool.stats['failed_operations'] += 1
            
        finally:
            # 完成future
            if operation.future and not operation.future.done():
                if operation.status == OperationStatus.COMPLETED:
                    operation.future.set_result(operation.result)
                else:
                    operation.future.set_exception(operation.error or Exception("Operation failed"))
    
    async def _check_dependencies(self, operation: AsyncOperation) -> bool:
        """檢查操作依賴"""
        if not operation.dependencies:
            return True
        
        for dep_id in operation.dependencies:
            # 檢查依賴操作是否完成
            if dep_id in self.running_tasks:
                task = self.running_tasks[dep_id]
                if not task.done():
                    return False
                
                # 檢查依賴操作是否成功
                try:
                    task.result()
                except Exception:
                    return False  # 依賴操作失敗
        
        return True
    
    def _on_task_completed(self, operation_id: str):
        """任務完成回調"""
        if operation_id in self.running_tasks:
            task = self.running_tasks.pop(operation_id)
            self.completed_tasks.append({
                'operation_id': operation_id,
                'completed_at': datetime.now(),
                'success': not task.exception()
            })
    
    def cancel_operation(self, operation_id: str) -> bool:
        """取消操作"""
        if operation_id in self.running_tasks:
            task = self.running_tasks[operation_id]
            if not task.done():
                task.cancel()
                return True
        
        return False
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """獲取調度器狀態"""
        return {
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'scheduler_running': self.scheduler_task is not None and not self.scheduler_task.done(),
            'resource_usage': self.resource_pool.get_resource_usage(),
            'stats': self.resource_pool.stats
        }


class SubBotAsyncManager(BaseService):
    """
    子機器人異步操作管理器
    
    提供完整的異步操作管理、資源控制和任務調度功能
    """
    
    def __init__(
        self,
        max_concurrent_reads: int = 50,
        max_concurrent_writes: int = 10,
        max_concurrent_transactions: int = 5,
        default_operation_timeout: float = 30.0,
        enable_background_cleanup: bool = True
    ):
        """
        初始化異步管理器
        
        Args:
            max_concurrent_reads: 最大並發讀操作數
            max_concurrent_writes: 最大並發寫操作數
            max_concurrent_transactions: 最大並發事務數
            default_operation_timeout: 預設操作超時時間
            enable_background_cleanup: 是否啟用背景清理
        """
        super().__init__("SubBotAsyncManager")
        
        self.default_operation_timeout = default_operation_timeout
        self.enable_background_cleanup = enable_background_cleanup
        
        # 核心組件
        self.resource_pool = ResourcePool(
            max_concurrent_reads=max_concurrent_reads,
            max_concurrent_writes=max_concurrent_writes,
            max_concurrent_transactions=max_concurrent_transactions
        )
        self.scheduler = TaskScheduler(self.resource_pool)
        
        # 資料庫服務（將在初始化時注入）
        self.db_service: Optional[SubBotDatabaseService] = None
        self.error_handler: Optional[SubBotErrorHandler] = None
        
        # 操作追蹤
        self.operations: Dict[str, AsyncOperation] = {}
        self.batch_operations: Dict[str, BatchOperation] = {}
        
        # 背景任務
        self.background_tasks: List[asyncio.Task] = []
        
        # 線程池（用於CPU密集型操作）
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # 統計資訊
        self.stats = {
            'operations_created': 0,
            'operations_completed': 0,
            'operations_failed': 0,
            'batch_operations_created': 0,
            'average_operation_time': 0.0,
            'total_operation_time': 0.0
        }
    
    async def _initialize(self) -> bool:
        """初始化異步管理器"""
        try:
            self.logger.info("異步操作管理器初始化中...")
            
            # 啟動任務調度器
            await self.scheduler.start()
            
            # 啟動背景清理任務
            if self.enable_background_cleanup:
                cleanup_task = asyncio.create_task(self._cleanup_loop())
                self.background_tasks.append(cleanup_task)
            
            self.logger.info("異步操作管理器初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"異步操作管理器初始化失敗: {e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            # 停止調度器
            await self.scheduler.stop()
            
            # 取消所有背景任務
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()
            
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)
            
            # 關閉線程池
            self.thread_pool.shutdown(wait=True)
            
            self.logger.info("異步操作管理器清理完成")
            
        except Exception as e:
            self.logger.error(f"清理異步操作管理器時發生錯誤: {e}")
    
    async def _validate_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """驗證權限"""
        return True  # 異步管理器通常不需要特殊權限
    
    # ========== 核心異步操作API ==========
    
    async def execute_async(
        self,
        func: Callable[..., T],
        *args,
        operation_type: OperationType = OperationType.READ,
        priority: OperationPriority = OperationPriority.NORMAL,
        timeout: Optional[float] = None,
        max_retries: int = 0,
        context: Optional[ErrorContext] = None,
        dependencies: Optional[List[str]] = None,
        **kwargs
    ) -> T:
        """
        執行異步操作
        
        Args:
            func: 要執行的函數
            *args: 函數參數
            operation_type: 操作類型
            priority: 操作優先級
            timeout: 超時時間
            max_retries: 最大重試次數
            context: 錯誤上下文
            dependencies: 依賴操作ID列表
            **kwargs: 關鍵字參數
            
        Returns:
            操作結果
        """
        # 生成操作ID
        operation_id = f"op_{uuid.uuid4().hex[:8]}"
        
        # 創建操作
        operation = AsyncOperation(
            id=operation_id,
            operation_type=operation_type,
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            timeout=timeout or self.default_operation_timeout,
            max_retries=max_retries,
            context=context,
            dependencies=dependencies or [],
            future=asyncio.Future()
        )
        
        # 註冊操作
        self.operations[operation_id] = operation
        self.stats['operations_created'] += 1
        
        try:
            # 調度操作
            if await self.scheduler.schedule_operation(operation):
                # 等待操作完成
                result = await operation.future
                
                # 更新統計
                if operation.completed_at and operation.started_at:
                    execution_time = (operation.completed_at - operation.started_at).total_seconds()
                    self.stats['total_operation_time'] += execution_time
                    self.stats['operations_completed'] += 1
                    self.stats['average_operation_time'] = self.stats['total_operation_time'] / self.stats['operations_completed']
                
                return result
            else:
                raise Exception("無法調度操作：佇列已滿")
                
        except Exception as e:
            self.stats['operations_failed'] += 1
            
            # 如果有錯誤處理器，記錄錯誤
            if self.error_handler and context:
                await self.error_handler.handle_error(e, context)
            
            raise
        
        finally:
            # 清理操作記錄
            self._schedule_operation_cleanup(operation_id)
    
    async def execute_batch(
        self,
        operations: List[Tuple[Callable, tuple, dict]],
        strategy: str = "parallel",
        max_concurrency: int = 5,
        timeout: Optional[float] = None,
        stop_on_error: bool = False
    ) -> BatchOperation:
        """
        執行批次操作
        
        Args:
            operations: 操作列表 [(func, args, kwargs), ...]
            strategy: 執行策略（parallel, sequential, mixed）
            max_concurrency: 最大並發數
            timeout: 批次超時時間
            stop_on_error: 遇到錯誤是否停止
            
        Returns:
            批次操作結果
        """
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        
        # 創建批次中的所有操作
        async_operations = []
        for i, (func, args, kwargs) in enumerate(operations):
            op_id = f"{batch_id}_op_{i}"
            
            operation = AsyncOperation(
                id=op_id,
                operation_type=OperationType.BATCH,
                priority=OperationPriority.NORMAL,
                func=func,
                args=args,
                kwargs=kwargs,
                timeout=timeout,
                future=asyncio.Future()
            )
            
            async_operations.append(operation)
            self.operations[op_id] = operation
        
        # 創建批次操作
        batch_operation = BatchOperation(
            id=batch_id,
            operations=async_operations,
            strategy=strategy,
            max_concurrency=max_concurrency
        )
        
        self.batch_operations[batch_id] = batch_operation
        self.stats['batch_operations_created'] += 1
        
        try:
            batch_operation.status = OperationStatus.RUNNING
            batch_operation.started_at = datetime.now()
            
            if strategy == "parallel":
                # 並行執行
                tasks = [
                    asyncio.create_task(self._execute_single_operation(op))
                    for op in async_operations
                ]
                
                # 使用Semaphore控制並發數
                semaphore = asyncio.Semaphore(max_concurrency)
                
                async def limited_execution(task):
                    async with semaphore:
                        return await task
                
                results = await asyncio.gather(
                    *[limited_execution(task) for task in tasks],
                    return_exceptions=True
                )
                
            elif strategy == "sequential":
                # 順序執行
                results = []
                for operation in async_operations:
                    try:
                        result = await self._execute_single_operation(operation)
                        results.append(result)
                        
                        if stop_on_error and operation.status == OperationStatus.FAILED:
                            break
                            
                    except Exception as e:
                        results.append(e)
                        if stop_on_error:
                            break
            
            else:  # mixed strategy
                # 混合策略：讀操作並行，寫操作順序
                read_ops = [op for op in async_operations if op.operation_type == OperationType.READ]
                write_ops = [op for op in async_operations if op.operation_type != OperationType.READ]
                
                # 並行執行讀操作
                read_tasks = [asyncio.create_task(self._execute_single_operation(op)) for op in read_ops]
                read_results = await asyncio.gather(*read_tasks, return_exceptions=True)
                
                # 順序執行寫操作
                write_results = []
                for operation in write_ops:
                    try:
                        result = await self._execute_single_operation(operation)
                        write_results.append(result)
                    except Exception as e:
                        write_results.append(e)
                
                results = read_results + write_results
            
            # 整理結果
            batch_operation.results = [r for r in results if not isinstance(r, Exception)]
            batch_operation.errors = [r for r in results if isinstance(r, Exception)]
            
            batch_operation.status = OperationStatus.COMPLETED
            batch_operation.completed_at = datetime.now()
            
            return batch_operation
            
        except Exception as e:
            batch_operation.status = OperationStatus.FAILED
            batch_operation.errors.append(e)
            batch_operation.completed_at = datetime.now()
            raise
    
    async def _execute_single_operation(self, operation: AsyncOperation):
        """執行單個操作"""
        try:
            operation.status = OperationStatus.RUNNING
            operation.started_at = datetime.now()
            
            # 使用資源池
            async with self.resource_pool.acquire_resource(operation.operation_type):
                if operation.timeout:
                    result = await asyncio.wait_for(
                        operation.func(*operation.args, **operation.kwargs),
                        timeout=operation.timeout
                    )
                else:
                    result = await operation.func(*operation.args, **operation.kwargs)
            
            operation.result = result
            operation.status = OperationStatus.COMPLETED
            operation.completed_at = datetime.now()
            
            return result
            
        except Exception as e:
            operation.error = e
            operation.status = OperationStatus.FAILED
            operation.completed_at = datetime.now()
            raise
    
    # ========== 背景任務管理 ==========
    
    def create_background_task(
        self,
        func: Callable,
        *args,
        interval: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        創建背景任務
        
        Args:
            func: 要執行的函數
            *args: 函數參數
            interval: 執行間隔（秒），None表示只執行一次
            **kwargs: 關鍵字參數
            
        Returns:
            任務ID
        """
        task_id = f"bg_task_{uuid.uuid4().hex[:8]}"
        
        if interval:
            # 定期任務
            task = asyncio.create_task(self._periodic_task(func, interval, *args, **kwargs))
        else:
            # 單次任務
            task = asyncio.create_task(func(*args, **kwargs))
        
        # 設置任務名稱
        task.set_name(task_id)
        
        self.background_tasks.append(task)
        
        self.logger.info(f"創建背景任務: {task_id}")
        
        return task_id
    
    async def _periodic_task(self, func: Callable, interval: float, *args, **kwargs):
        """定期執行任務"""
        while True:
            try:
                await func(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"背景任務執行失敗: {e}")
            
            await asyncio.sleep(interval)
    
    def cancel_background_task(self, task_id: str) -> bool:
        """取消背景任務"""
        for task in self.background_tasks:
            if task.get_name() == task_id:
                if not task.done():
                    task.cancel()
                    self.logger.info(f"取消背景任務: {task_id}")
                    return True
        
        return False
    
    # ========== 監控和統計 ==========
    
    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """獲取操作狀態"""
        if operation_id in self.operations:
            return self.operations[operation_id].to_dict()
        
        return None
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """獲取批次操作狀態"""
        if batch_id in self.batch_operations:
            return self.batch_operations[batch_id].to_dict()
        
        return None
    
    def get_manager_statistics(self) -> Dict[str, Any]:
        """獲取管理器統計"""
        scheduler_status = self.scheduler.get_scheduler_status()
        
        return {
            'async_manager': self.stats,
            'scheduler': scheduler_status,
            'background_tasks': {
                'total_tasks': len(self.background_tasks),
                'running_tasks': sum(1 for task in self.background_tasks if not task.done())
            },
            'operations': {
                'active_operations': len(self.operations),
                'active_batches': len(self.batch_operations)
            }
        }
    
    async def _cleanup_loop(self):
        """清理循環"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分鐘清理一次
                await self._cleanup_completed_operations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"清理循環發生錯誤: {e}")
                await asyncio.sleep(60)  # 錯誤後等待1分鐘
    
    def _schedule_operation_cleanup(self, operation_id: str, delay: float = 300.0):
        """安排操作清理"""
        async def cleanup():
            await asyncio.sleep(delay)
            self.operations.pop(operation_id, None)
        
        asyncio.create_task(cleanup())
    
    async def _cleanup_completed_operations(self):
        """清理已完成的操作"""
        cutoff_time = datetime.now() - timedelta(hours=1)  # 清理1小時前的操作
        
        # 清理普通操作
        operations_to_remove = [
            op_id for op_id, operation in self.operations.items()
            if operation.status in [OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED]
            and operation.completed_at
            and operation.completed_at < cutoff_time
        ]
        
        for op_id in operations_to_remove:
            del self.operations[op_id]
        
        # 清理批次操作
        batches_to_remove = [
            batch_id for batch_id, batch_op in self.batch_operations.items()
            if batch_op.status in [OperationStatus.COMPLETED, OperationStatus.FAILED]
            and batch_op.completed_at
            and batch_op.completed_at < cutoff_time
        ]
        
        for batch_id in batches_to_remove:
            del self.batch_operations[batch_id]
        
        # 清理已完成的背景任務
        self.background_tasks = [task for task in self.background_tasks if not task.done()]
        
        if operations_to_remove or batches_to_remove:
            self.logger.debug(f"清理了 {len(operations_to_remove)} 個操作和 {len(batches_to_remove)} 個批次操作")


# 便利裝飾器

def async_database_operation(
    operation_type: OperationType = OperationType.READ,
    priority: OperationPriority = OperationPriority.NORMAL,
    timeout: Optional[float] = None,
    max_retries: int = 0
):
    """
    異步資料庫操作裝飾器
    
    Args:
        operation_type: 操作類型
        priority: 優先級
        timeout: 超時時間
        max_retries: 最大重試次數
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 獲取異步管理器
            manager = await get_async_manager()
            
            # 執行異步操作
            return await manager.execute_async(
                func, *args,
                operation_type=operation_type,
                priority=priority,
                timeout=timeout,
                max_retries=max_retries,
                **kwargs
            )
        
        return wrapper
    return decorator


# 全域實例
_async_manager: Optional[SubBotAsyncManager] = None


async def get_async_manager() -> SubBotAsyncManager:
    """
    獲取全域異步管理器實例
    
    Returns:
        異步管理器實例
    """
    global _async_manager
    if _async_manager is None:
        _async_manager = SubBotAsyncManager()
        await _async_manager.initialize()
    return _async_manager