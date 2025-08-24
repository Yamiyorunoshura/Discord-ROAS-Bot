"""
T2 - 高併發連線競爭修復 - ConnectionPoolManager實作
Task ID: T2

企業級連線池管理系統，提供：
- 動態連線池大小調整機制
- 智慧負載平衡和連線調度
- 實時效能監控和統計
- 併發錯誤率控制和診斷
- 自適應容量規劃
"""

import asyncio
import aiosqlite
import logging
import time
import statistics
import threading
from typing import Optional, Dict, List, Any, Set
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from dataclasses import dataclass
from collections import deque, defaultdict

from .models import (
    ConnectionPoolStats, 
    ConnectionStatus, 
    ConnectionInfo,
    PoolConfiguration, 
    LoadMetrics, 
    PerformanceMetrics
)

logger = logging.getLogger('connection_pool_manager')


class ConnectionWrapper:
    """連線包裝器，提供監控和生命週期管理"""
    
    def __init__(self, connection: aiosqlite.Connection, connection_id: str):
        self.connection = connection
        self.connection_id = connection_id
        self.created_at = datetime.now()
        self.last_used_at = None
        self.usage_count = 0
        self.error_count = 0
        self.status = ConnectionStatus.IDLE
        self._lock = asyncio.Lock()
    
    async def execute(self, query: str, params: tuple = ()):
        """執行SQL查詢並記錄統計"""
        async with self._lock:
            try:
                self.status = ConnectionStatus.ACTIVE
                self.last_used_at = datetime.now()
                
                result = await self.connection.execute(query, params)
                
                self.usage_count += 1
                self.status = ConnectionStatus.IDLE
                return result
                
            except Exception as e:
                self.error_count += 1
                self.status = ConnectionStatus.ERROR
                raise e
    
    async def is_healthy(self) -> bool:
        """檢查連線健康狀態"""
        try:
            async with self.connection.execute("SELECT 1"):
                pass
            return True
        except:
            return False
    
    async def close(self):
        """關閉連線"""
        try:
            self.status = ConnectionStatus.CLOSED
            await self.connection.close()
        except:
            pass


class ConnectionPoolManager:
    """
    企業級連線池管理器
    
    核心功能：
    1. 動態連線池大小調整
    2. 智慧負載平衡
    3. 實時效能監控  
    4. 併發錯誤率控制
    5. 自適應容量規劃
    """
    
    def __init__(
        self, 
        db_path: str, 
        config: Optional[PoolConfiguration] = None
    ):
        self.db_path = db_path
        self.config = config or PoolConfiguration()
        
        # 驗證配置
        config_errors = self.config.validate()
        if config_errors:
            raise ValueError(f"配置錯誤: {', '.join(config_errors)}")
        
        # 連線池狀態
        self._connections: Dict[str, ConnectionWrapper] = {}
        self._idle_connections: deque = deque()
        self._waiting_queue: asyncio.Queue = asyncio.Queue()
        self._pool_lock = asyncio.Lock()
        
        # 統計和監控
        self._stats = ConnectionPoolStats(
            timestamp=datetime.now(),
            active_connections=0,
            idle_connections=0,
            waiting_requests=0,
            max_connections=self.config.max_connections,
            total_connections_created=0,
            total_requests_served=0,
            average_wait_time_ms=0.0,
            error_count=0,
            success_rate=100.0
        )
        
        # 效能指標追蹤
        self._response_times: deque = deque(maxlen=1000)
        self._error_history: deque = deque(maxlen=100)
        self._load_history: deque = deque(maxlen=60)
        
        # 動態調整參數
        self._last_adjustment = datetime.now()
        self._adjustment_cooldown = timedelta(seconds=30)
        
        # 監控和任務
        self._monitoring_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        logger.info(f"ConnectionPoolManager 初始化完成 - 資料庫: {db_path}")
    
    async def start(self):
        """啟動連線池管理器"""
        if self._is_running:
            return
            
        self._is_running = True
        
        # 初始化最小連線數
        await self._ensure_min_connections()
        
        # 啟動背景任務
        if self.config.enable_monitoring:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("ConnectionPoolManager 已啟動")
    
    async def stop(self):
        """停止連線池管理器"""
        if not self._is_running:
            return
            
        self._is_running = False
        
        # 停止背景任務
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 關閉所有連線
        await self._close_all_connections()
        
        logger.info("ConnectionPoolManager 已停止")
    
    async def get_connection(self) -> aiosqlite.Connection:
        """
        獲取資料庫連線
        
        實現智慧調度算法：
        1. 優先使用空閒連線
        2. 動態調整池大小
        3. 負載感知的等待機制
        4. 併發競爭控制
        """
        start_time = time.time()
        
        try:
            # 嘗試獲取空閒連線
            connection = await self._try_get_idle_connection()
            if connection:
                wait_time_ms = (time.time() - start_time) * 1000
                self._record_successful_request(wait_time_ms)
                return connection
            
            # 檢查是否可以創建新連線
            if len(self._connections) < self.config.max_connections:
                connection = await self._create_new_connection()
                wait_time_ms = (time.time() - start_time) * 1000
                self._record_successful_request(wait_time_ms)
                return connection
            
            # 需要等待連線可用
            return await self._wait_for_connection(start_time)
            
        except Exception as e:
            self._record_failed_request()
            logger.error(f"獲取連線失敗: {e}")
            raise
    
    async def release_connection(self, connection: aiosqlite.Connection):
        """
        釋放連線回池中
        
        實現智慧回收：
        1. 健康檢查
        2. 統計更新  
        3. 動態池調整觸發
        """
        try:
            # 查找對應的連線包裝器
            wrapper = None
            for conn_id, conn_wrapper in self._connections.items():
                if conn_wrapper.connection == connection:
                    wrapper = conn_wrapper
                    break
            
            if not wrapper:
                logger.warning("嘗試釋放未知連線")
                return
            
            # 健康檢查
            if await wrapper.is_healthy():
                wrapper.status = ConnectionStatus.IDLE
                self._idle_connections.append(wrapper)
                
                # 通知等待中的請求
                if not self._waiting_queue.empty():
                    try:
                        waiter = self._waiting_queue.get_nowait()
                        waiter.set_result(wrapper.connection)
                    except asyncio.QueueEmpty:
                        pass
            else:
                # 連線不健康，移除並可能創建新連線
                await self._remove_connection(wrapper)
            
            # 觸發動態調整檢查
            await self._maybe_adjust_pool_size()
                
        except Exception as e:
            logger.error(f"釋放連線時發生錯誤: {e}")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """獲取連線池統計資訊"""
        active_count = sum(
            1 for conn in self._connections.values() 
            if conn.status == ConnectionStatus.ACTIVE
        )
        
        idle_count = len(self._idle_connections)
        waiting_count = self._waiting_queue.qsize()
        
        # 更新統計
        self._stats.active_connections = active_count
        self._stats.idle_connections = idle_count
        self._stats.waiting_requests = waiting_count
        self._stats.timestamp = datetime.now()
        
        # 計算平均等待時間
        if self._response_times:
            self._stats.average_wait_time_ms = statistics.mean(self._response_times)
        
        # 計算成功率
        total_requests = self._stats.total_requests_served + self._stats.error_count
        if total_requests > 0:
            self._stats.success_rate = (self._stats.total_requests_served / total_requests) * 100
        
        return self._stats.to_dict()
    
    async def optimize_pool(self):
        """
        主動優化連線池
        
        實現智慧優化策略：
        1. 負載趨勢分析
        2. 預測性擴縮容
        3. 效能基準對比
        4. 異常檢測和恢復
        """
        try:
            current_load = await self._calculate_current_load()
            
            # 記錄負載歷史
            self._load_history.append(current_load)
            
            # 分析負載趨勢
            load_trend = self._analyze_load_trend()
            
            # 根據趨勢調整池大小
            if load_trend > 0.7:  # 負載上升趨勢
                await self._scale_up()
            elif load_trend < 0.3:  # 負載下降趨勢
                await self._scale_down()
            
            # 清理不健康的連線
            await self._health_check_and_cleanup()
            
            logger.debug(f"連線池優化完成 - 負載趨勢: {load_trend:.2f}")
                
        except Exception as e:
            logger.error(f"連線池優化失敗: {e}")
    
    async def get_performance_metrics(self) -> PerformanceMetrics:
        """獲取效能指標"""
        if not self._response_times:
            return PerformanceMetrics.create_empty()
        
        response_times = list(self._response_times)
        response_times.sort()
        
        total_requests = self._stats.total_requests_served + self._stats.error_count
        
        return PerformanceMetrics(
            total_requests=total_requests,
            successful_requests=self._stats.total_requests_served,
            failed_requests=self._stats.error_count,
            total_response_time_ms=sum(response_times),
            min_response_time_ms=min(response_times) if response_times else 0,
            max_response_time_ms=max(response_times) if response_times else 0,
            p50_response_time_ms=self._percentile(response_times, 0.5),
            p95_response_time_ms=self._percentile(response_times, 0.95),
            p99_response_time_ms=self._percentile(response_times, 0.99),
            throughput_rps=self._calculate_throughput(),
            error_rate=(self._stats.error_count / total_requests * 100) if total_requests > 0 else 0
        )
    
    # 私有方法實作
    
    async def _try_get_idle_connection(self) -> Optional[aiosqlite.Connection]:
        """嘗試獲取空閒連線"""
        while self._idle_connections:
            wrapper = self._idle_connections.popleft()
            if await wrapper.is_healthy():
                wrapper.status = ConnectionStatus.ACTIVE
                return wrapper.connection
            else:
                await self._remove_connection(wrapper)
        return None
    
    async def _create_new_connection(self) -> aiosqlite.Connection:
        """創建新連線"""
        try:
            # 創建SQLite連線
            connection = await aiosqlite.connect(self.db_path)
            await connection.execute("PRAGMA journal_mode=WAL;")
            await connection.execute("PRAGMA busy_timeout=30000;")
            connection.row_factory = aiosqlite.Row
            
            # 創建連線包裝器
            connection_id = f"conn_{len(self._connections)}_{int(time.time())}"
            wrapper = ConnectionWrapper(connection, connection_id)
            wrapper.status = ConnectionStatus.ACTIVE
            
            # 添加到連線池
            self._connections[connection_id] = wrapper
            self._stats.total_connections_created += 1
            
            logger.debug(f"創建新連線: {connection_id}")
            return connection
            
        except Exception as e:
            logger.error(f"創建連線失敗: {e}")
            raise
    
    async def _wait_for_connection(self, start_time: float) -> aiosqlite.Connection:
        """等待連線可用"""
        future = asyncio.Future()
        await self._waiting_queue.put(future)
        
        try:
            connection = await asyncio.wait_for(
                future, 
                timeout=self.config.acquire_timeout
            )
            wait_time_ms = (time.time() - start_time) * 1000
            self._record_successful_request(wait_time_ms)
            return connection
            
        except asyncio.TimeoutError:
            self._record_failed_request()
            raise TimeoutError("獲取連線超時")
    
    async def _ensure_min_connections(self):
        """確保最小連線數"""
        while len(self._connections) < self.config.min_connections:
            try:
                connection = await aiosqlite.connect(self.db_path)
                await connection.execute("PRAGMA journal_mode=WAL;")
                await connection.execute("PRAGMA busy_timeout=30000;")
                connection.row_factory = aiosqlite.Row
                
                connection_id = f"conn_{len(self._connections)}_{int(time.time())}"
                wrapper = ConnectionWrapper(connection, connection_id)
                
                self._connections[connection_id] = wrapper
                self._idle_connections.append(wrapper)
                self._stats.total_connections_created += 1
                
            except Exception as e:
                logger.error(f"創建最小連線失敗: {e}")
                break
    
    async def _remove_connection(self, wrapper: ConnectionWrapper):
        """移除連線"""
        try:
            await wrapper.close()
            if wrapper.connection_id in self._connections:
                del self._connections[wrapper.connection_id]
            
            # 從空閒列表中移除
            try:
                self._idle_connections.remove(wrapper)
            except ValueError:
                pass
            
            logger.debug(f"移除連線: {wrapper.connection_id}")
            
        except Exception as e:
            logger.error(f"移除連線時發生錯誤: {e}")
    
    async def _close_all_connections(self):
        """關閉所有連線"""
        for wrapper in list(self._connections.values()):
            await self._remove_connection(wrapper)
        
        self._idle_connections.clear()
        logger.info("已關閉所有連線")
    
    async def _monitoring_loop(self):
        """監控循環"""
        while self._is_running:
            try:
                await asyncio.sleep(self.config.stats_collection_interval)
                
                if not self._is_running:
                    break
                
                # 收集統計資訊
                stats = self.get_pool_stats()
                logger.debug(f"連線池統計: {stats}")
                
                # 執行優化
                await self.optimize_pool()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"監控循環錯誤: {e}")
    
    async def _cleanup_loop(self):
        """清理循環"""
        while self._is_running:
            try:
                await asyncio.sleep(60)  # 每分鐘執行一次清理
                
                if not self._is_running:
                    break
                
                await self._cleanup_idle_connections()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理循環錯誤: {e}")
    
    async def _cleanup_idle_connections(self):
        """清理超時的空閒連線"""
        current_time = datetime.now()
        timeout_threshold = current_time - timedelta(seconds=self.config.idle_timeout)
        
        connections_to_remove = []
        
        for wrapper in list(self._idle_connections):
            if (wrapper.last_used_at and 
                wrapper.last_used_at < timeout_threshold and
                len(self._connections) > self.config.min_connections):
                
                connections_to_remove.append(wrapper)
        
        for wrapper in connections_to_remove:
            await self._remove_connection(wrapper)
            logger.debug(f"清理空閒連線: {wrapper.connection_id}")
    
    async def _calculate_current_load(self) -> LoadMetrics:
        """計算當前負載"""
        active_connections = sum(
            1 for conn in self._connections.values() 
            if conn.status == ConnectionStatus.ACTIVE
        )
        
        queue_length = self._waiting_queue.qsize()
        
        # 計算平均響應時間
        avg_response_time = 0.0
        if self._response_times:
            avg_response_time = statistics.mean(list(self._response_times)[-10:])  # 最近10個請求
        
        return LoadMetrics(
            cpu_usage=0.0,  # 可以擴展為實際CPU使用率
            memory_usage_mb=len(self._connections) * 10,  # 估算記憶體使用
            active_requests=active_connections,
            queue_length=queue_length,
            average_response_time_ms=avg_response_time,
            timestamp=datetime.now()
        )
    
    def _analyze_load_trend(self) -> float:
        """分析負載趨勢 (0-1, 0.5為穩定)"""
        if len(self._load_history) < 3:
            return 0.5
        
        recent_loads = [load.calculate_load_score() for load in list(self._load_history)[-5:]]
        
        # 簡單的趨勢分析：比較最近和較早的負載
        recent_avg = statistics.mean(recent_loads[-2:])
        earlier_avg = statistics.mean(recent_loads[:-2]) if len(recent_loads) > 2 else recent_avg
        
        if earlier_avg == 0:
            return 0.5
        
        trend = recent_avg / earlier_avg
        return min(max(trend, 0), 1)  # 限制在0-1範圍
    
    async def _scale_up(self):
        """擴容連線池"""
        if (len(self._connections) < self.config.max_connections and 
            datetime.now() - self._last_adjustment > self._adjustment_cooldown):
            
            try:
                connection = await self._create_new_connection()
                wrapper = None
                
                # 查找對應的包裝器並設為空閒
                for conn_wrapper in self._connections.values():
                    if conn_wrapper.connection == connection:
                        wrapper = conn_wrapper
                        break
                
                if wrapper:
                    wrapper.status = ConnectionStatus.IDLE
                    self._idle_connections.append(wrapper)
                
                self._last_adjustment = datetime.now()
                logger.info(f"連線池擴容: {len(self._connections)}")
                
            except Exception as e:
                logger.error(f"連線池擴容失敗: {e}")
    
    async def _scale_down(self):
        """縮容連線池"""
        if (len(self._connections) > self.config.min_connections and 
            datetime.now() - self._last_adjustment > self._adjustment_cooldown):
            
            # 移除一個空閒連線
            if self._idle_connections:
                wrapper = self._idle_connections.popleft()
                await self._remove_connection(wrapper)
                
                self._last_adjustment = datetime.now()
                logger.info(f"連線池縮容: {len(self._connections)}")
    
    async def _health_check_and_cleanup(self):
        """健康檢查和清理"""
        unhealthy_connections = []
        
        for wrapper in list(self._connections.values()):
            if not await wrapper.is_healthy():
                unhealthy_connections.append(wrapper)
        
        for wrapper in unhealthy_connections:
            await self._remove_connection(wrapper)
            logger.warning(f"移除不健康連線: {wrapper.connection_id}")
        
        # 如果移除了連線，確保最小連線數
        if unhealthy_connections:
            await self._ensure_min_connections()
    
    async def _maybe_adjust_pool_size(self):
        """根據當前狀況動態調整池大小"""
        # 如果有等待的請求且未達最大連線數，考慮增加連線
        if (not self._waiting_queue.empty() and 
            len(self._connections) < self.config.max_connections):
            await self._scale_up()
    
    def _record_successful_request(self, wait_time_ms: float):
        """記錄成功請求"""
        self._stats.total_requests_served += 1
        self._response_times.append(wait_time_ms)
    
    def _record_failed_request(self):
        """記錄失敗請求"""
        self._stats.error_count += 1
        self._error_history.append(datetime.now())
    
    def _percentile(self, data: List[float], p: float) -> float:
        """計算百分位數"""
        if not data:
            return 0.0
        
        k = (len(data) - 1) * p
        f = int(k)
        c = k - f
        
        if f == len(data) - 1:
            return data[f]
        
        return data[f] * (1 - c) + data[f + 1] * c
    
    def _calculate_throughput(self) -> float:
        """計算吞吐量 (RPS)"""
        # 基於最近60秒的請求數計算
        recent_requests = sum(
            1 for error_time in self._error_history 
            if error_time > datetime.now() - timedelta(seconds=60)
        ) + min(len(self._response_times), 60)
        
        return recent_requests / 60.0
    
    @asynccontextmanager
    async def connection(self):
        """連線上下文管理器"""
        conn = await self.get_connection()
        try:
            yield conn
        finally:
            await self.release_connection(conn)