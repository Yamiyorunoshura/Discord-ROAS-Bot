"""
專業級資料庫連接池系統

此模組提供了一個完整的資料庫連接池管理系統,包括:
- 連接池管理
- 連接生命週期管理
- 健康監控
- 指標收集
- 自動清理機制
- 智能負載均衡
- 連接預熱機制
- 自動故障恢復

作者: Discord ADR Bot Team
創建時間: 2025-01-24
版本: 1.6.0
"""

import asyncio
import hashlib
import logging
import os
import statistics
import time
import weakref
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import aiosqlite

# 配置日誌
logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """連接狀態枚舉"""

    IDLE = "idle"  # 空閒
    ACTIVE = "active"  # 活躍
    EXPIRED = "expired"  # 已過期
    FAILED = "failed"  # 失敗
    WARMING = "warming"  # 預熱中


class PoolStrategy(Enum):
    """連接池策略枚舉"""

    ROUND_ROBIN = "round_robin"  # 輪詢
    LEAST_USED = "least_used"  # 最少使用
    RANDOM = "random"  # 隨機
    ADAPTIVE = "adaptive"  # 自適應


@dataclass
class PoolConfiguration:
    """連接池配置類別"""

    max_connections: int = 20  # 最大連接數
    min_connections: int = 5  # 最小連接數
    max_idle_time: int = 300  # 最大空閒時間(秒)
    max_lifetime: int = 3600  # 最大生命週期(秒)
    health_check_interval: int = 30  # 健康檢查間隔(秒)
    connection_timeout: int = 30  # 連接超時(秒)
    retry_attempts: int = 3  # 重試次數
    retry_delay: float = 1.0  # 重試延遲(秒)
    enable_wal: bool = True  # 啟用WAL模式
    enable_metrics: bool = True  # 啟用指標收集
    enable_prewarming: bool = True  # 啟用連接預熱
    warmup_connections: int = 3  # 預熱連接數量
    strategy: PoolStrategy = PoolStrategy.ADAPTIVE  # 連接池策略
    enable_load_balancing: bool = True  # 啟用負載均衡
    enable_auto_recovery: bool = True  # 啟用自動恢復
    performance_monitoring: bool = True  # 啟用性能監控


@dataclass
class ConnectionMetrics:
    """單個連接的指標"""

    connection_id: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    total_queries: int = 0
    total_query_time: float = 0.0
    failed_queries: int = 0
    status: ConnectionStatus = ConnectionStatus.IDLE
    error_count: int = 0
    last_error: str | None = None

    @property
    def avg_query_time(self) -> float:
        """平均查詢時間"""
        return (
            self.total_query_time / self.total_queries
            if self.total_queries > 0
            else 0.0
        )

    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.total_queries + self.failed_queries
        return self.total_queries / total if total > 0 else 1.0

    @property
    def age(self) -> float:
        """連接年齡(秒)"""
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        """空閒時間(秒)"""
        return time.time() - self.last_used


class PoolMetrics:
    """連接池指標收集器"""

    def __init__(self):
        self.total_connections_created = 0
        self.total_connections_closed = 0
        self.active_connections = 0
        self.failed_connections = 0
        self.total_queries = 0
        self.total_query_time = 0.0
        self.connection_errors = 0
        self.health_check_failures = 0
        self.created_at = time.time()
        self.peak_active_connections = 0
        self.query_history: deque = deque(maxlen=1000)  # 最近1000次查詢記錄
        self.error_history: deque = deque(maxlen=100)  # 最近100次錯誤記錄
        self._lock = asyncio.Lock()

    async def record_connection_created(self):
        """記錄連接創建"""
        async with self._lock:
            self.total_connections_created += 1
            self.active_connections += 1
            self.peak_active_connections = max(
                self.peak_active_connections, self.active_connections
            )

    async def record_connection_closed(self):
        """記錄連接關閉"""
        async with self._lock:
            self.total_connections_closed += 1
            self.active_connections = max(0, self.active_connections - 1)

    async def record_connection_error(self, error: str):
        """記錄連接錯誤"""
        async with self._lock:
            self.connection_errors += 1
            self.error_history.append(
                {"timestamp": time.time(), "error": error, "type": "connection"}
            )

    async def record_query_executed(self, duration: float, success: bool = True):
        """記錄查詢執行"""
        async with self._lock:
            self.total_queries += 1
            self.total_query_time += duration

            self.query_history.append(
                {"timestamp": time.time(), "duration": duration, "success": success}
            )

            if not success:
                self.failed_connections += 1

    async def record_health_check_failure(self):
        """記錄健康檢查失敗"""
        async with self._lock:
            self.health_check_failures += 1

    async def get_metrics_summary(self) -> dict[str, Any]:
        """獲取指標摘要"""
        async with self._lock:
            uptime = time.time() - self.created_at
            avg_query_time = (
                (self.total_query_time / self.total_queries)
                if self.total_queries > 0
                else 0.0
            )

            # 計算最近查詢性能
            recent_queries = [
                q for q in self.query_history if time.time() - q["timestamp"] < 300
            ]  # 最近5分鐘
            recent_avg_time = (
                statistics.mean([q["duration"] for q in recent_queries])
                if recent_queries
                else 0.0
            )
            recent_success_rate = (
                sum(1 for q in recent_queries if q["success"]) / len(recent_queries)
                if recent_queries
                else 1.0
            )

            return {
                "uptime_seconds": uptime,
                "total_connections_created": self.total_connections_created,
                "total_connections_closed": self.total_connections_closed,
                "active_connections": self.active_connections,
                "peak_active_connections": self.peak_active_connections,
                "failed_connections": self.failed_connections,
                "total_queries": self.total_queries,
                "avg_query_time_ms": avg_query_time * 1000,
                "recent_avg_query_time_ms": recent_avg_time * 1000,
                "recent_success_rate": recent_success_rate,
                "connection_errors": self.connection_errors,
                "health_check_failures": self.health_check_failures,
                "queries_per_second": self.total_queries / uptime
                if uptime > 0
                else 0.0,
                "error_rate": self.connection_errors / self.total_connections_created
                if self.total_connections_created > 0
                else 0.0,
            }


class LoadBalancer:
    """連接負載均衡器"""

    def __init__(self, strategy: PoolStrategy = PoolStrategy.ADAPTIVE):
        self.strategy = strategy
        self.connection_weights: dict[str, float] = {}
        self.last_used_index = 0
        self._lock = asyncio.Lock()

    async def select_connection(
        self, connections: list["PooledConnection"]
    ) -> "PooledConnection | None":
        """選擇最佳連接"""
        if not connections:
            return None

        available_connections = [
            conn for conn in connections if conn.is_healthy and not conn.in_use
        ]
        if not available_connections:
            return None

        async with self._lock:
            if self.strategy == PoolStrategy.ROUND_ROBIN:
                return self._round_robin_select(available_connections)
            elif self.strategy == PoolStrategy.LEAST_USED:
                return self._least_used_select(available_connections)
            elif self.strategy == PoolStrategy.RANDOM:
                return self._random_select(available_connections)
            elif self.strategy == PoolStrategy.ADAPTIVE:
                return await self._adaptive_select(available_connections)
            else:
                return available_connections[0]

    def _round_robin_select(
        self, connections: list["PooledConnection"]
    ) -> "PooledConnection":
        """輪詢選擇"""
        self.last_used_index = (self.last_used_index + 1) % len(connections)
        return connections[self.last_used_index]

    def _least_used_select(
        self, connections: list["PooledConnection"]
    ) -> "PooledConnection":
        """選擇使用次數最少的連接"""
        return min(connections, key=lambda conn: conn.metrics.total_queries)

    def _random_select(
        self, connections: list["PooledConnection"]
    ) -> "PooledConnection":
        """隨機選擇"""
        import random

        return random.choice(connections)

    async def _adaptive_select(
        self, connections: list["PooledConnection"]
    ) -> "PooledConnection":
        """自適應選擇 - 基於性能指標"""
        # 計算每個連接的綜合分數
        best_connection = None
        best_score = float("inf")

        for conn in connections:
            # 綜合考慮:查詢時間、成功率、負載
            time_score = conn.metrics.avg_query_time
            load_score = conn.metrics.total_queries / (conn.metrics.age + 1)
            error_score = 1.0 - conn.metrics.success_rate

            # 加權計算總分(越低越好)
            total_score = time_score * 0.4 + load_score * 0.3 + error_score * 0.3

            if total_score < best_score:
                best_score = total_score
                best_connection = conn

        return best_connection or connections[0]


class ConnectionPrewarmer:
    """連接預熱器"""

    def __init__(self, pool_ref: weakref.ref, config: PoolConfiguration):
        self.pool_ref = pool_ref
        self.config = config
        self.prewarming_tasks: set[asyncio.Task] = set()
        self._lock = asyncio.Lock()

    async def start_prewarming(self, db_path: str):
        """開始預熱連接"""
        if not self.config.enable_prewarming:
            return

        async with self._lock:
            # 創建預熱任務
            task = asyncio.create_task(self._prewarm_connections(db_path))
            self.prewarming_tasks.add(task)
            task.add_done_callback(self.prewarming_tasks.discard)

    async def _prewarm_connections(self, db_path: str):
        """預熱連接"""
        pool = self.pool_ref()
        if pool is None:
            return

        try:
            for _i in range(self.config.warmup_connections):
                conn = await pool._create_connection(db_path)
                if conn:
                    conn.metrics.status = ConnectionStatus.WARMING
                    # 執行一個簡單的查詢來預熱連接
                    await conn.execute("SELECT 1")
                    conn.metrics.status = ConnectionStatus.IDLE

                    # 將連接返回到池中
                    await pool.return_connection(conn)

                    logger.debug(f"預熱連接完成: {conn.connection_id}")

                # 避免一次性創建過多連接
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"連接預熱失敗: {e}")


class AutoRecovery:
    """自動恢復機制"""

    def __init__(self, pool_ref: weakref.ref, config: PoolConfiguration):
        self.pool_ref = pool_ref
        self.config = config
        self.recovery_attempts: dict[str, int] = defaultdict(int)
        self.last_recovery: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    async def attempt_recovery(self, db_path: str, error: Exception) -> bool:
        """嘗試自動恢復"""
        if not self.config.enable_auto_recovery:
            return False

        async with self._lock:
            current_time = time.time()

            # 檢查恢復頻率限制
            if current_time - self.last_recovery[db_path] < 60:  # 1分鐘內最多恢復一次
                return False

            # 檢查恢復次數限制
            if self.recovery_attempts[db_path] >= 3:  # 最多嘗試3次
                return False

            self.recovery_attempts[db_path] += 1
            self.last_recovery[db_path] = current_time

            return await self._perform_recovery(db_path, error)

    async def _perform_recovery(self, db_path: str, error: Exception) -> bool:
        """執行恢復操作"""
        pool = self.pool_ref()
        if pool is None:
            return False

        try:
            logger.info(f"開始自動恢復資料庫連接: {db_path}")

            # 移除所有失效連接
            if db_path in pool._connections:
                failed_connections = [
                    conn
                    for conn in pool._connections[db_path]
                    if not conn.is_healthy
                    or conn.metrics.status == ConnectionStatus.FAILED
                ]

                for conn in failed_connections:
                    await pool._remove_connection(db_path, conn)

            # 重新創建最小數量的連接
            for _ in range(pool.config.min_connections):
                conn = await pool._create_connection(db_path)
                if conn:
                    logger.debug(f"恢復連接成功: {conn.connection_id}")
                else:
                    return False

            logger.info(f"自動恢復完成: {db_path}")
            return True

        except Exception as e:
            logger.error(f"自動恢復失敗: {e}")
            return False


class PooledConnection:
    """池化連接包裝器"""

    def __init__(
        self, connection: aiosqlite.Connection, db_path: str, pool_ref: weakref.ref
    ):
        self.connection = connection
        self.db_path = db_path
        self.pool_ref = pool_ref
        self.connection_id = hashlib.sha256(
            f"{db_path}_{time.time()}_{id(self)}".encode()
        ).hexdigest()[:8]
        self.metrics = ConnectionMetrics(self.connection_id)
        self.is_healthy = True
        self.in_use = False
        self._lock = asyncio.Lock()
        self._query_lock = asyncio.Lock()  # 防止並發查詢

    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        """執行查詢 - 自動健康檢查"""
        async with self._query_lock:
            if not self.is_healthy or not self.connection:
                raise RuntimeError(f"Connection {self.connection_id} is not healthy")

            start_time = time.time()
            try:
                self.metrics.last_used = time.time()
                self.metrics.status = ConnectionStatus.ACTIVE

                cursor = await self.connection.execute(query, params)

                # 記錄成功查詢
                duration = time.time() - start_time
                self.metrics.total_queries += 1
                self.metrics.total_query_time += duration

                # 記錄到池指標
                pool = self.pool_ref()
                if pool and pool.config.enable_metrics:
                    await pool.metrics.record_query_executed(duration, True)

                self.metrics.status = ConnectionStatus.IDLE
                return cursor

            except Exception as e:
                self.is_healthy = False
                self.metrics.status = ConnectionStatus.FAILED
                self.metrics.failed_queries += 1
                self.metrics.error_count += 1
                self.metrics.last_error = str(e)

                # 記錄到池指標
                pool = self.pool_ref()
                if pool and pool.config.enable_metrics:
                    duration = time.time() - start_time
                    await pool.metrics.record_query_executed(duration, False)
                    await pool.metrics.record_connection_error(str(e))

                logger.error(f"【連接池】連接 {self.connection_id} 查詢執行失敗: {e}")
                raise

    async def executemany(
        self, query: str, params_list: list[tuple]
    ) -> aiosqlite.Cursor:
        """執行批量查詢"""
        async with self._query_lock:
            if not self.is_healthy or not self.connection:
                raise RuntimeError(f"Connection {self.connection_id} is not healthy")

            start_time = time.time()
            try:
                self.metrics.last_used = time.time()
                self.metrics.status = ConnectionStatus.ACTIVE

                cursor = await self.connection.executemany(query, params_list)

                # 記錄成功查詢
                duration = time.time() - start_time
                self.metrics.total_queries += len(params_list)
                self.metrics.total_query_time += duration

                # 記錄到池指標
                pool = self.pool_ref()
                if pool and pool.config.enable_metrics:
                    await pool.metrics.record_query_executed(duration, True)

                self.metrics.status = ConnectionStatus.IDLE
                return cursor

            except Exception as e:
                self.is_healthy = False
                self.metrics.status = ConnectionStatus.FAILED
                self.metrics.failed_queries += 1
                self.metrics.error_count += 1
                self.metrics.last_error = str(e)

                pool = self.pool_ref()
                if pool and pool.config.enable_metrics:
                    duration = time.time() - start_time
                    await pool.metrics.record_query_executed(duration, False)
                    await pool.metrics.record_connection_error(str(e))

                logger.error(
                    f"【連接池】連接 {self.connection_id} 批量查詢執行失敗: {e}"
                )
                raise

    async def commit(self):
        """提交事務"""
        async with self._lock:
            if not self.is_healthy or not self.connection:
                raise RuntimeError(f"Connection {self.connection_id} is not healthy")

            try:
                await self.connection.commit()
            except Exception as e:
                self.is_healthy = False
                self.metrics.status = ConnectionStatus.FAILED
                self.metrics.error_count += 1
                self.metrics.last_error = str(e)
                logger.error(f"【連接池】連接 {self.connection_id} 提交事務失敗: {e}")
                raise

    async def rollback(self):
        """回滾事務"""
        async with self._lock:
            if not self.is_healthy or not self.connection:
                raise RuntimeError(f"Connection {self.connection_id} is not healthy")

            try:
                await self.connection.rollback()
            except Exception as e:
                self.is_healthy = False
                self.metrics.status = ConnectionStatus.FAILED
                self.metrics.error_count += 1
                self.metrics.last_error = str(e)
                logger.error(f"【連接池】連接 {self.connection_id} 回滾事務失敗: {e}")
                raise

    async def health_check(self) -> bool:
        """健康檢查"""
        try:
            async with self._lock:
                if not self.connection:
                    return False

                # 執行簡單查詢測試連接
                cursor = await self.connection.execute("SELECT 1")
                await cursor.fetchone()

                self.is_healthy = True
                return True

        except Exception as e:
            self.is_healthy = False
            self.metrics.status = ConnectionStatus.FAILED
            self.metrics.error_count += 1
            self.metrics.last_error = str(e)
            logger.warning(f"【連接池】連接 {self.connection_id} 健康檢查失敗: {e}")
            return False

    def is_expired(self, config: PoolConfiguration) -> bool:
        """檢查連接是否過期"""
        time.time()

        # 檢查生命週期
        if config.max_lifetime > 0 and self.metrics.age > config.max_lifetime:
            self.metrics.status = ConnectionStatus.EXPIRED
            return True

        # 檢查空閒時間
        if config.max_idle_time > 0 and self.metrics.idle_time > config.max_idle_time:
            self.metrics.status = ConnectionStatus.EXPIRED
            return True

        # 檢查錯誤率
        if self.metrics.error_count > 10:  # 錯誤次數過多
            self.metrics.status = ConnectionStatus.FAILED
            return True

        return False

    async def close(self):
        """關閉連接"""
        async with self._lock:
            try:
                if self.connection:
                    await self.connection.close()
                    self.connection = None

                self.is_healthy = False
                self.metrics.status = ConnectionStatus.EXPIRED

                # 記錄到池指標
                pool = self.pool_ref()
                if pool and pool.config.enable_metrics:
                    await pool.metrics.record_connection_closed()

                logger.debug(f"【連接池】連接 {self.connection_id} 已關閉")

            except Exception as e:
                logger.error(f"【連接池】關閉連接 {self.connection_id} 失敗: {e}")


class ConnectionHealthMonitor:
    """連接健康監控器"""

    def __init__(self, pool_ref: weakref.ref, config: PoolConfiguration):
        self.pool_ref = pool_ref
        self.config = config
        self._monitor_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start_monitoring(self):
        """開始監控"""
        if self._monitor_task is None or self._monitor_task.done():
            self._stop_event.clear()
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.debug("【連接池】健康監控已啟動")

    async def stop_monitoring(self):
        """停止監控"""
        if self._monitor_task and not self._monitor_task.done():
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._monitor_task, timeout=5.0)
            except TimeoutError:
                self._monitor_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._monitor_task

            logger.debug("【連接池】健康監控已停止")

    async def _monitor_loop(self):
        """監控循環"""
        while not self._stop_event.is_set():
            try:
                await self._check_all_connections()
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.config.health_check_interval
                )
            except TimeoutError:
                continue  # 正常的超時,繼續監控
            except Exception as e:
                logger.error(f"【連接池】監控循環錯誤: {e}")
                await asyncio.sleep(10)  # 錯誤後等待10秒再繼續

    async def _check_all_connections(self):
        """檢查所有連接的健康狀態"""
        pool = self.pool_ref()
        if pool is None:
            return

        for db_path, connections in pool._connections.items():
            connections_to_remove = []

            for conn in connections:
                # 檢查是否過期
                if conn.is_expired(self.config):
                    connections_to_remove.append(conn)
                    continue

                # 執行健康檢查
                if not await conn.health_check():
                    connections_to_remove.append(conn)

                    # 記錄健康檢查失敗
                    if pool.config.enable_metrics:
                        await pool.metrics.record_health_check_failure()

            # 移除不健康的連接
            for conn in connections_to_remove:
                await pool._remove_connection(db_path, conn)

            # 確保最小連接數
            current_count = len(pool._connections.get(db_path, []))
            if current_count < self.config.min_connections:
                needed = self.config.min_connections - current_count
                for _ in range(needed):
                    try:
                        new_conn = await pool._create_connection(db_path)
                        if new_conn:
                            logger.debug(
                                f"【連接池】補充連接: {new_conn.connection_id}"
                            )
                    except Exception as e:
                        logger.error(f"【連接池】補充連接失敗: {e}")
                        break


class DatabaseConnectionPool:
    """資料庫連接池"""

    def __init__(self, config: PoolConfiguration | None = None):
        self.config = config or PoolConfiguration()
        self._connections: dict[str, list[PooledConnection]] = defaultdict(list)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.metrics = PoolMetrics()

        # 初始化組件
        self.health_monitor = ConnectionHealthMonitor(weakref.ref(self), self.config)
        self.load_balancer = LoadBalancer(self.config.strategy)
        self.prewarmer = ConnectionPrewarmer(weakref.ref(self), self.config)
        self.auto_recovery = AutoRecovery(weakref.ref(self), self.config)

        self._initialized = False

    async def initialize(self):
        """初始化連接池"""
        if not self._initialized:
            await self.health_monitor.start_monitoring()
            self._initialized = True
            logger.info("【連接池】資料庫連接池已初始化")

    async def close(self):
        """關閉連接池"""
        logger.info("【連接池】正在關閉連接池...")

        # 停止健康監控
        await self.health_monitor.stop_monitoring()

        # 關閉所有連接
        for _db_path, connections in self._connections.items():
            for conn in connections:
                await conn.close()

        self._connections.clear()
        self._locks.clear()
        self._initialized = False

        logger.info("【連接池】連接池已關閉")

    async def get_connection(self, db_path: str) -> PooledConnection:
        """獲取連接"""
        if not self._initialized:
            await self.initialize()

        async with self._locks[db_path]:
            # 嘗試從現有連接中選擇
            connections = self._connections[db_path]

            # 使用負載均衡器選擇連接
            if self.config.enable_load_balancing:
                connection = await self.load_balancer.select_connection(connections)
                if connection:
                    connection.in_use = True
                    return connection
            else:
                # 簡單選擇第一個可用連接
                for conn in connections:
                    if conn.is_healthy and not conn.in_use:
                        conn.in_use = True
                        return conn

            # 如果沒有可用連接且未達到最大數量,創建新連接
            if len(connections) < self.config.max_connections:
                new_conn = await self._create_connection(db_path)
                if new_conn:
                    new_conn.in_use = True

                    # 觸發預熱(如果是第一個連接)
                    if len(connections) == 1:
                        await self.prewarmer.start_prewarming(db_path)

                    return new_conn

            # 如果仍然沒有可用連接,等待或拋出異常
            raise RuntimeError(
                f"無法獲取資料庫連接: {db_path} (活躍連接: {len(connections)}/{self.config.max_connections})"
            )

    async def return_connection(self, connection: PooledConnection):
        """歸還連接"""
        if connection:
            connection.in_use = False
            logger.debug(f"【連接池】連接 {connection.connection_id} 已歸還")

    async def _create_connection(self, db_path: str) -> PooledConnection:
        """創建新連接"""
        retry_count = 0
        last_error = None

        while retry_count < self.config.retry_attempts:
            try:
                # 確保資料庫目錄存在
                os.makedirs(
                    os.path.dirname(db_path) if os.path.dirname(db_path) else ".",
                    exist_ok=True,
                )

                # 創建連接
                connection = await asyncio.wait_for(
                    aiosqlite.connect(db_path), timeout=self.config.connection_timeout
                )

                # 配置連接
                if self.config.enable_wal:
                    await connection.execute("PRAGMA journal_mode=WAL")

                # 其他優化設置
                await connection.execute("PRAGMA synchronous=NORMAL")
                await connection.execute("PRAGMA cache_size=10000")
                await connection.execute("PRAGMA temp_store=memory")
                await connection.execute("PRAGMA mmap_size=268435456")  # 256MB

                # 創建池化連接包裝器
                pooled_conn = PooledConnection(connection, db_path, weakref.ref(self))

                # 添加到連接列表
                self._connections[db_path].append(pooled_conn)

                # 記錄指標
                if self.config.enable_metrics:
                    await self.metrics.record_connection_created()

                logger.debug(
                    f"【連接池】新連接已創建: {pooled_conn.connection_id} for {db_path}"
                )

                return pooled_conn

            except Exception as e:
                last_error = e
                retry_count += 1

                if self.config.enable_metrics:
                    await self.metrics.record_connection_error(str(e))

                logger.warning(
                    f"【連接池】創建連接失敗 (嘗試 {retry_count}/{self.config.retry_attempts}): {e}"
                )

                if retry_count < self.config.retry_attempts:
                    await asyncio.sleep(self.config.retry_delay * retry_count)
                # 嘗試自動恢復
                elif await self.auto_recovery.attempt_recovery(db_path, e):
                    logger.info("【連接池】自動恢復成功,重試創建連接")
                    retry_count = 0  # 重置重試計數
                    continue

        raise RuntimeError(f"無法創建資料庫連接 {db_path}: {last_error}")

    async def _remove_connection(self, db_path: str, connection: PooledConnection):
        """移除連接"""
        try:
            if connection in self._connections[db_path]:
                self._connections[db_path].remove(connection)

            await connection.close()

            logger.debug(f"【連接池】連接已移除: {connection.connection_id}")

        except Exception as e:
            logger.error(f"【連接池】移除連接失敗: {e}")

    @asynccontextmanager
    async def get_connection_context(self, db_path: str):
        """連接上下文管理器"""
        connection = await self.get_connection(db_path)
        try:
            yield connection
        finally:
            await self.return_connection(connection)

    async def execute(
        self, db_path: str, query: str, params: tuple = ()
    ) -> aiosqlite.Cursor:
        """執行查詢的便捷方法"""
        async with self.get_connection_context(db_path) as conn:
            return await conn.execute(query, params)

    async def get_pool_status(self) -> dict[str, Any]:
        """獲取連接池狀態"""
        status = {
            "initialized": self._initialized,
            "databases": {},
            "total_connections": 0,
            "total_active_connections": 0,
            "total_idle_connections": 0,
            "configuration": {
                "max_connections": self.config.max_connections,
                "min_connections": self.config.min_connections,
                "strategy": self.config.strategy.value,
                "enable_load_balancing": self.config.enable_load_balancing,
                "enable_prewarming": self.config.enable_prewarming,
                "enable_auto_recovery": self.config.enable_auto_recovery,
            },
        }

        # 統計每個資料庫的連接狀態
        for db_path, connections in self._connections.items():
            active_count = sum(1 for conn in connections if conn.in_use)
            idle_count = len(connections) - active_count
            healthy_count = sum(1 for conn in connections if conn.is_healthy)

            status["databases"][db_path] = {
                "total_connections": len(connections),
                "active_connections": active_count,
                "idle_connections": idle_count,
                "healthy_connections": healthy_count,
                "connections": [
                    {
                        "id": conn.connection_id,
                        "status": conn.metrics.status.value,
                        "is_healthy": conn.is_healthy,
                        "in_use": conn.in_use,
                        "total_queries": conn.metrics.total_queries,
                        "avg_query_time_ms": conn.metrics.avg_query_time * 1000,
                        "success_rate": conn.metrics.success_rate,
                        "age_seconds": conn.metrics.age,
                        "idle_time_seconds": conn.metrics.idle_time,
                    }
                    for conn in connections
                ],
            }

            status["total_connections"] += len(connections)
            status["total_active_connections"] += active_count
            status["total_idle_connections"] += idle_count

        # 添加指標摘要
        if self.config.enable_metrics:
            status["metrics"] = await self.metrics.get_metrics_summary()

        return status


# 全域連接池實例
_global_pool: DatabaseConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def get_global_pool(test_mode: bool = False) -> DatabaseConnectionPool:
    """獲取全域連接池"""
    global _global_pool

    async with _pool_lock:
        if _global_pool is None:
            config = PoolConfiguration()
            if test_mode:
                config.max_connections = 5
                config.min_connections = 1
                config.health_check_interval = 5

            _global_pool = DatabaseConnectionPool(config)
            await _global_pool.initialize()

    return _global_pool


async def close_global_pool():
    """關閉全域連接池"""
    global _global_pool

    async with _pool_lock:
        if _global_pool is not None:
            await _global_pool.close()
            _global_pool = None
