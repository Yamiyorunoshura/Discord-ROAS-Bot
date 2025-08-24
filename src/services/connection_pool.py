"""
高併發連線池管理系統
T2 - 高併發連線競爭修復實施

提供企業級資料庫連線池管理，支援動態調整、效能監控和併發優化
專為ROAS Bot v2.4.2的20+工作者併發場景設計
"""

import asyncio
import logging
import threading
import time
import weakref
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
import sqlite3

from ..db.sqlite import OptimizedConnection, SQLiteConnectionFactory
from ..db.retry import retry_on_database_locked, CommonRetryStrategies

logger = logging.getLogger('src.services.connection_pool')


class ConnectionState(Enum):
    """連線狀態枚舉"""
    IDLE = "idle"           # 空閒可用
    ACTIVE = "active"       # 正在使用
    STALE = "stale"         # 過期待回收
    ERROR = "error"         # 錯誤狀態


@dataclass
class ConnectionMetrics:
    """連線指標數據結構"""
    connection_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)
    usage_count: int = 0
    error_count: int = 0
    state: ConnectionState = ConnectionState.IDLE
    thread_id: Optional[int] = None
    
    def update_usage(self):
        """更新使用統計"""
        self.last_used = datetime.utcnow()
        self.usage_count += 1
    
    def increment_error(self):
        """增加錯誤計數"""
        self.error_count += 1
        self.state = ConnectionState.ERROR
    
    def reset_error(self):
        """重置錯誤狀態"""
        self.error_count = 0
        self.state = ConnectionState.IDLE
    
    @property
    def age_seconds(self) -> float:
        """連線存活時間(秒)"""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    @property
    def idle_seconds(self) -> float:
        """空閒時間(秒)"""
        return (datetime.utcnow() - self.last_used).total_seconds()


@dataclass
class PoolStatistics:
    """連線池統計數據結構"""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    active_connections: int = 0
    idle_connections: int = 0
    total_connections: int = 0
    max_connections_used: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_wait_time_ms: float = 0.0
    peak_wait_time_ms: float = 0.0
    pool_efficiency: float = 0.0  # 成功率
    
    @property
    def success_rate(self) -> float:
        """請求成功率"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0
    
    @property
    def error_rate(self) -> float:
        """錯誤率"""
        return 100.0 - self.success_rate


class ConnectionPoolConfig:
    """連線池配置類"""
    
    def __init__(
        self,
        min_connections: int = 2,
        max_connections: int = 20,
        max_idle_time: timedelta = timedelta(minutes=30),
        max_lifetime: timedelta = timedelta(hours=4),
        connection_timeout: float = 5.0,
        validation_interval: timedelta = timedelta(minutes=5),
        dynamic_scaling: bool = True,
        scale_up_threshold: float = 0.8,  # 使用率超過80%時擴容
        scale_down_threshold: float = 0.3,  # 使用率低於30%時縮容
        max_error_count: int = 5
    ):
        """
        初始化連線池配置
        
        參數:
            min_connections: 最小連線數
            max_connections: 最大連線數 
            max_idle_time: 最大空閒時間
            max_lifetime: 連線最大生命週期
            connection_timeout: 連線取得逾時(秒)
            validation_interval: 驗證間隔
            dynamic_scaling: 是否啟用動態調整
            scale_up_threshold: 擴容閾值(使用率)
            scale_down_threshold: 縮容閾值(使用率)
            max_error_count: 最大錯誤數
        """
        self.min_connections = max(1, min_connections)
        self.max_connections = max(self.min_connections, max_connections)
        self.max_idle_time = max_idle_time
        self.max_lifetime = max_lifetime
        self.connection_timeout = max(1.0, connection_timeout)
        self.validation_interval = validation_interval
        self.dynamic_scaling = dynamic_scaling
        self.scale_up_threshold = max(0.1, min(0.99, scale_up_threshold))
        self.scale_down_threshold = max(0.1, min(self.scale_up_threshold - 0.1, scale_down_threshold))
        self.max_error_count = max(1, max_error_count)


class ConnectionWrapper:
    """連線包裝器類"""
    
    def __init__(self, connection: OptimizedConnection, metrics: ConnectionMetrics, pool_ref: weakref.ref):
        self.connection = connection
        self.metrics = metrics
        self._pool_ref = pool_ref
        self._released = False
    
    def __getattr__(self, name):
        """代理連線方法調用"""
        return getattr(self.connection, name)
    
    def __enter__(self):
        return self.connection
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
    
    async def __aenter__(self):
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release_async()
    
    def release(self):
        """同步釋放連線"""
        if not self._released:
            pool = self._pool_ref()
            if pool:
                pool._release_connection(self)
            self._released = True
    
    async def release_async(self):
        """非同步釋放連線"""
        if not self._released:
            pool = self._pool_ref()
            if pool:
                await pool._release_connection_async(self)
            self._released = True
    
    def __del__(self):
        """析構時自動釋放"""
        if not self._released:
            try:
                self.release()
            except:
                pass


class ConnectionPoolManager:
    """
    企業級連線池管理器
    
    提供動態調整、效能監控、併發安全的資料庫連線管理
    專為高併發環境下的SQLite連線競爭問題設計
    """
    
    def __init__(self, db_path: str, config: Optional[ConnectionPoolConfig] = None):
        """
        初始化連線池管理器
        
        參數:
            db_path: 資料庫檔案路徑
            config: 連線池配置
        """
        self.db_path = db_path
        self.config = config or ConnectionPoolConfig()
        
        # 連線池狀態
        self._connections: Dict[str, ConnectionWrapper] = {}
        self._idle_connections: deque = deque()
        self._active_connections: Dict[str, ConnectionWrapper] = {}
        
        # 同步控制
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        self._thread_lock = threading.RLock()
        
        # 統計數據
        self._stats = PoolStatistics()
        self._connection_counter = 0
        self._request_times: deque = deque(maxlen=1000)  # 保留最近1000次請求時間
        
        # 連線工廠
        self._factory = SQLiteConnectionFactory(db_path)
        
        # 管理執行緒控制
        self._shutdown = False
        self._maintenance_task: Optional[asyncio.Task] = None
        
        logger.info(f"連線池管理器已初始化 - 資料庫: {db_path}, 配置: {self.config.min_connections}-{self.config.max_connections} 連線")
    
    async def initialize(self):
        """初始化連線池"""
        async with self._lock:
            # 創建最小連線數
            for _ in range(self.config.min_connections):
                await self._create_connection()
            
            # 啟動維護任務
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
            
            logger.info(f"連線池已初始化 - {len(self._connections)} 個連線")
    
    async def _create_connection(self) -> ConnectionWrapper:
        """創建新連線"""
        self._connection_counter += 1
        connection_id = f"conn_{self._connection_counter}_{int(time.time())}"
        
        try:
            # 使用現有工廠創建連線
            optimized_conn = self._factory.get_connection()
            
            # 創建連線指標
            metrics = ConnectionMetrics(
                connection_id=connection_id,
                thread_id=threading.get_ident()
            )
            
            # 包裝連線
            wrapper = ConnectionWrapper(
                optimized_conn, 
                metrics, 
                weakref.ref(self)
            )
            
            # 加入連線池
            self._connections[connection_id] = wrapper
            self._idle_connections.append(wrapper)
            
            logger.debug(f"已創建新連線: {connection_id}")
            return wrapper
            
        except Exception as e:
            logger.error(f"創建連線失敗: {e}")
            raise
    
    @retry_on_database_locked(strategy=CommonRetryStrategies.BALANCED)
    async def get_connection(self, timeout: Optional[float] = None) -> ConnectionWrapper:
        """
        取得資料庫連線
        
        參數:
            timeout: 逾時時間(秒)，None表示使用配置預設值
            
        返回:
            連線包裝器
        """
        start_time = time.time()
        timeout = timeout or self.config.connection_timeout
        
        try:
            async with asyncio.wait_for(self._condition, timeout=timeout):
                # 統計請求
                self._stats.total_requests += 1
                
                # 嘗試從空閒連線取得
                if self._idle_connections:
                    wrapper = self._idle_connections.popleft()
                    
                    # 驗證連線有效性
                    if await self._validate_connection(wrapper):
                        await self._activate_connection(wrapper)
                        self._record_request_time(start_time)
                        self._stats.successful_requests += 1
                        return wrapper
                    else:
                        # 移除無效連線
                        await self._remove_connection(wrapper)
                
                # 嘗試創建新連線
                if len(self._connections) < self.config.max_connections:
                    wrapper = await self._create_connection()
                    await self._activate_connection(wrapper)
                    self._record_request_time(start_time)
                    self._stats.successful_requests += 1
                    return wrapper
                
                # 等待連線可用
                await self._condition.wait()
                return await self.get_connection(timeout)
                
        except asyncio.TimeoutError:
            self._stats.failed_requests += 1
            wait_time = (time.time() - start_time) * 1000
            logger.warning(f"取得連線逾時 - 等待時間: {wait_time:.2f}ms")
            raise ConnectionPoolTimeoutError(f"取得連線逾時 ({wait_time:.2f}ms)")
        except Exception as e:
            self._stats.failed_requests += 1
            logger.error(f"取得連線失敗: {e}")
            raise
    
    async def _validate_connection(self, wrapper: ConnectionWrapper) -> bool:
        """驗證連線有效性"""
        try:
            metrics = wrapper.metrics
            
            # 檢查連線狀態
            if metrics.state == ConnectionState.ERROR:
                if metrics.error_count >= self.config.max_error_count:
                    return False
            
            # 檢查生命週期
            if metrics.age_seconds > self.config.max_lifetime.total_seconds():
                return False
            
            # 檢查空閒時間
            if metrics.idle_seconds > self.config.max_idle_time.total_seconds():
                return False
            
            # 測試連線
            wrapper.connection.execute("SELECT 1").fetchone()
            metrics.reset_error()
            return True
            
        except Exception as e:
            wrapper.metrics.increment_error()
            logger.debug(f"連線驗證失敗: {wrapper.metrics.connection_id}, 錯誤: {e}")
            return False
    
    async def _activate_connection(self, wrapper: ConnectionWrapper):
        """啟用連線"""
        wrapper.metrics.state = ConnectionState.ACTIVE
        wrapper.metrics.update_usage()
        self._active_connections[wrapper.metrics.connection_id] = wrapper
        
        # 更新統計
        current_active = len(self._active_connections)
        self._stats.active_connections = current_active
        self._stats.idle_connections = len(self._idle_connections)
        self._stats.max_connections_used = max(self._stats.max_connections_used, current_active)
    
    def _release_connection(self, wrapper: ConnectionWrapper):
        """同步釋放連線"""
        asyncio.create_task(self._release_connection_async(wrapper))
    
    async def _release_connection_async(self, wrapper: ConnectionWrapper):
        """非同步釋放連線"""
        async with self._lock:
            connection_id = wrapper.metrics.connection_id
            
            if connection_id in self._active_connections:
                del self._active_connections[connection_id]
                
                # 檢查連線是否仍然有效
                if connection_id in self._connections:
                    if await self._validate_connection(wrapper):
                        wrapper.metrics.state = ConnectionState.IDLE
                        self._idle_connections.append(wrapper)
                    else:
                        await self._remove_connection(wrapper)
                
                # 更新統計
                self._stats.active_connections = len(self._active_connections)
                self._stats.idle_connections = len(self._idle_connections)
                
                # 通知等待中的請求
                self._condition.notify()
    
    async def _remove_connection(self, wrapper: ConnectionWrapper):
        """移除連線"""
        connection_id = wrapper.metrics.connection_id
        
        try:
            # 從各個集合中移除
            self._connections.pop(connection_id, None)
            self._active_connections.pop(connection_id, None)
            
            # 從空閒佇列移除
            try:
                self._idle_connections.remove(wrapper)
            except ValueError:
                pass
            
            # 關閉連線
            wrapper.connection.close()
            
            logger.debug(f"已移除連線: {connection_id}")
            
        except Exception as e:
            logger.error(f"移除連線失敗 {connection_id}: {e}")
    
    def _record_request_time(self, start_time: float):
        """記錄請求時間"""
        request_time = (time.time() - start_time) * 1000  # 轉換為毫秒
        self._request_times.append(request_time)
        
        # 更新統計
        if self._request_times:
            self._stats.average_wait_time_ms = sum(self._request_times) / len(self._request_times)
            self._stats.peak_wait_time_ms = max(self._request_times)
    
    async def _maintenance_loop(self):
        """連線池維護循環"""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.validation_interval.total_seconds())
                await self._perform_maintenance()
            except Exception as e:
                logger.error(f"維護任務錯誤: {e}")
    
    async def _perform_maintenance(self):
        """執行維護任務"""
        async with self._lock:
            await self._cleanup_stale_connections()
            await self._adjust_pool_size()
            await self._update_statistics()
    
    async def _cleanup_stale_connections(self):
        """清理過期連線"""
        stale_connections = []
        
        # 檢查空閒連線
        for wrapper in list(self._idle_connections):
            if not await self._validate_connection(wrapper):
                stale_connections.append(wrapper)
        
        # 移除過期連線
        for wrapper in stale_connections:
            await self._remove_connection(wrapper)
            logger.debug(f"清理過期連線: {wrapper.metrics.connection_id}")
    
    async def _adjust_pool_size(self):
        """動態調整連線池大小"""
        if not self.config.dynamic_scaling:
            return
        
        current_total = len(self._connections)
        current_active = len(self._active_connections)
        
        if current_total == 0:
            utilization = 0.0
        else:
            utilization = current_active / current_total
        
        # 擴容判斷
        if (utilization > self.config.scale_up_threshold and 
            current_total < self.config.max_connections):
            
            await self._create_connection()
            logger.info(f"動態擴容 - 目前使用率: {utilization:.1%}, 總連線數: {len(self._connections)}")
        
        # 縮容判斷
        elif (utilization < self.config.scale_down_threshold and 
              current_total > self.config.min_connections and
              len(self._idle_connections) > 1):
            
            wrapper = self._idle_connections.pop()
            await self._remove_connection(wrapper)
            logger.info(f"動態縮容 - 目前使用率: {utilization:.1%}, 總連線數: {len(self._connections)}")
    
    async def _update_statistics(self):
        """更新統計資訊"""
        self._stats.timestamp = datetime.utcnow()
        self._stats.total_connections = len(self._connections)
        self._stats.active_connections = len(self._active_connections)
        self._stats.idle_connections = len(self._idle_connections)
        
        # 計算效率
        if self._stats.total_requests > 0:
            self._stats.pool_efficiency = (self._stats.successful_requests / self._stats.total_requests) * 100.0
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """取得連線池統計資訊"""
        return {
            'timestamp': self._stats.timestamp,
            'total_connections': self._stats.total_connections,
            'active_connections': self._stats.active_connections, 
            'idle_connections': self._stats.idle_connections,
            'max_connections_used': self._stats.max_connections_used,
            'total_requests': self._stats.total_requests,
            'successful_requests': self._stats.successful_requests,
            'failed_requests': self._stats.failed_requests,
            'success_rate': self._stats.success_rate,
            'error_rate': self._stats.error_rate,
            'average_wait_time_ms': self._stats.average_wait_time_ms,
            'peak_wait_time_ms': self._stats.peak_wait_time_ms,
            'pool_efficiency': self._stats.pool_efficiency,
            'db_path': self.db_path,
            'config': {
                'min_connections': self.config.min_connections,
                'max_connections': self.config.max_connections,
                'connection_timeout': self.config.connection_timeout,
                'dynamic_scaling': self.config.dynamic_scaling
            }
        }
    
    async def optimize_pool(self):
        """手動優化連線池"""
        async with self._lock:
            logger.info("開始手動優化連線池")
            await self._cleanup_stale_connections()
            await self._adjust_pool_size()
            await self._update_statistics()
            logger.info("連線池優化完成")
    
    @contextmanager
    def get_sync_connection(self, timeout: Optional[float] = None):
        """同步連線上下文管理器"""
        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        wrapper = loop.run_until_complete(self.get_connection(timeout))
        try:
            yield wrapper.connection
        finally:
            wrapper.release()
    
    @asynccontextmanager
    async def get_async_connection(self, timeout: Optional[float] = None):
        """非同步連線上下文管理器"""
        wrapper = await self.get_connection(timeout)
        try:
            yield wrapper.connection
        finally:
            await wrapper.release_async()
    
    async def close(self):
        """關閉連線池"""
        logger.info("正在關閉連線池...")
        self._shutdown = True
        
        # 停止維護任務
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        
        # 關閉所有連線
        async with self._lock:
            for wrapper in list(self._connections.values()):
                await self._remove_connection(wrapper)
        
        # 清理工廠
        self._factory.close_all_connections()
        
        logger.info("連線池已關閉")
    
    def __del__(self):
        """析構函數"""
        if not self._shutdown:
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.create_task(self.close())
            except:
                pass


class ConnectionPoolTimeoutError(Exception):
    """連線池逾時錯誤"""
    pass


class ConnectionPoolExhaustedError(Exception):
    """連線池耗盡錯誤"""
    pass


# 全局連線池管理器實例
_pool_instances: Dict[str, ConnectionPoolManager] = {}
_pool_lock = threading.RLock()


def get_connection_pool(db_path: str, config: Optional[ConnectionPoolConfig] = None) -> ConnectionPoolManager:
    """
    獲取指定資料庫的連線池管理器實例
    
    參數:
        db_path: 資料庫檔案路徑
        config: 連線池配置
        
    返回:
        連線池管理器實例
    """
    abs_path = os.path.abspath(db_path)
    
    with _pool_lock:
        if abs_path not in _pool_instances:
            pool_manager = ConnectionPoolManager(abs_path, config)
            _pool_instances[abs_path] = pool_manager
            logger.info(f"已創建連線池實例: {abs_path}")
        
        return _pool_instances[abs_path]


async def cleanup_all_pools():
    """清理所有連線池"""
    with _pool_lock:
        for pool in list(_pool_instances.values()):
            await pool.close()
        _pool_instances.clear()
        logger.info("已清理所有連線池")