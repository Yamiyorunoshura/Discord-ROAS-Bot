# 高併發測試基礎設施配置
# Task ID: T2 - 高併發連線競爭修復 - 測試基礎設施配置
"""
高併發測試基礎設施配置模組

為T2任務提供專業的高併發測試環境支援：
- 支援20+工作者併發測試環境
- 動態資源調整和負載均衡
- 測試隔離和清理機制
- 效能監控和結果收集
"""

import asyncio
import json
import logging
import os
import psutil
import time
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, AsyncIterator
import multiprocessing
import threading

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError


class TestEnvironmentStatus(Enum):
    """測試環境狀態"""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    CLEANING = "cleaning"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class ResourceType(Enum):
    """資源類型"""
    CPU = "cpu"
    MEMORY = "memory"
    CONNECTIONS = "connections"
    DISK_IO = "disk_io"
    NETWORK = "network"


@dataclass
class TestResource:
    """測試資源配置"""
    resource_type: ResourceType
    allocated: float  # 已分配量
    limit: float      # 限制量
    unit: str         # 單位
    
    @property
    def utilization(self) -> float:
        """資源使用率"""
        return (self.allocated / self.limit) * 100 if self.limit > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'resource_type': self.resource_type.value,
            'allocated': self.allocated,
            'limit': self.limit,
            'unit': self.unit,
            'utilization': self.utilization
        }


@dataclass
class WorkerConfig:
    """工作者配置"""
    worker_id: str
    concurrent_connections: int
    test_duration_seconds: int
    request_rate_per_second: int
    database_operations: List[str]  # 要執行的資料庫操作類型
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'worker_id': self.worker_id,
            'concurrent_connections': self.concurrent_connections,
            'test_duration_seconds': self.test_duration_seconds,
            'request_rate_per_second': self.request_rate_per_second,
            'database_operations': self.database_operations,
            'metadata': self.metadata or {}
        }


@dataclass
class TestEnvironmentConfig:
    """測試環境配置"""
    environment_id: str
    total_workers: int
    max_concurrent_connections: int
    test_duration_minutes: int
    database_pool_size: int
    monitoring_interval_seconds: int
    cleanup_after_test: bool
    resource_limits: Dict[ResourceType, float]
    isolation_mode: str  # 'process', 'thread', 'async'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'environment_id': self.environment_id,
            'total_workers': self.total_workers,
            'max_concurrent_connections': self.max_concurrent_connections,
            'test_duration_minutes': self.test_duration_minutes,
            'database_pool_size': self.database_pool_size,
            'monitoring_interval_seconds': self.monitoring_interval_seconds,
            'cleanup_after_test': self.cleanup_after_test,
            'resource_limits': {k.value: v for k, v in self.resource_limits.items()},
            'isolation_mode': self.isolation_mode
        }


@dataclass
class TestSession:
    """測試會話"""
    session_id: str
    environment_config: TestEnvironmentConfig
    worker_configs: List[WorkerConfig]
    status: TestEnvironmentStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    results_summary: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'environment_config': self.environment_config.to_dict(),
            'worker_configs': [w.to_dict() for w in self.worker_configs],
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'results_summary': self.results_summary or {}
        }


class ConcurrencyTestInfrastructure(BaseService):
    """高併發測試基礎設施
    
    提供企業級的高併發測試環境支援
    專門為T2任務的連線池競爭測試設計
    """
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__("ConcurrencyTestInfrastructure")
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 系統資源監控
        self._system_resources = {
            ResourceType.CPU: TestResource(ResourceType.CPU, 0, psutil.cpu_count() * 100, 'percent'),
            ResourceType.MEMORY: TestResource(ResourceType.MEMORY, 0, psutil.virtual_memory().total, 'bytes'),
            ResourceType.CONNECTIONS: TestResource(ResourceType.CONNECTIONS, 0, 1000, 'count'),
            ResourceType.DISK_IO: TestResource(ResourceType.DISK_IO, 0, 1000, 'mbps'),
            ResourceType.NETWORK: TestResource(ResourceType.NETWORK, 0, 1000, 'mbps')
        }
        
        # 測試會話管理
        self._active_sessions: Dict[str, TestSession] = {}
        self._test_databases: Dict[str, str] = {}  # session_id -> temp_db_path
        self._worker_executors: Dict[str, ThreadPoolExecutor] = {}
        
        # 預設配置
        self.default_config = TestEnvironmentConfig(
            environment_id="default",
            total_workers=10,
            max_concurrent_connections=20,
            test_duration_minutes=5,
            database_pool_size=25,
            monitoring_interval_seconds=5,
            cleanup_after_test=True,
            resource_limits={
                ResourceType.CPU: 80.0,      # 80% CPU使用率限制
                ResourceType.MEMORY: 0.8,    # 80% 記憶體使用率限制
                ResourceType.CONNECTIONS: 50 # 50個連線限制
            },
            isolation_mode='async'
        )
    
    async def initialize(self) -> None:
        """初始化高併發測試基礎設施"""
        try:
            await self._create_test_tables()
            await self._initialize_system_monitoring()
            self.logger.info("高併發測試基礎設施初始化完成")
        except Exception as e:
            self.logger.error(f"高併發測試基礎設施初始化失敗: {e}")
            raise ServiceError("高併發測試基礎設施初始化失敗", "initialize", str(e))
    
    async def _create_test_tables(self) -> None:
        """創建測試相關資料表"""
        # 測試會話表
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                environment_config TEXT NOT NULL,
                worker_configs TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                results_summary TEXT
            )
        """)
        
        # 測試資源使用記錄
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS test_resource_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                resource_type TEXT NOT NULL,
                allocated REAL NOT NULL,
                limit_value REAL NOT NULL,
                utilization REAL NOT NULL,
                metadata TEXT
            )
        """)
        
        # 工作者執行記錄
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS test_worker_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                avg_response_time_ms REAL DEFAULT 0,
                peak_memory_mb REAL DEFAULT 0,
                error_details TEXT
            )
        """)
        
        # 連線競爭事件記錄
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS test_connection_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                worker_id TEXT NOT NULL,
                event_type TEXT NOT NULL,  -- 'acquire', 'release', 'timeout', 'error'
                timestamp TIMESTAMP NOT NULL,
                wait_time_ms REAL,
                error_message TEXT,
                connection_pool_stats TEXT
            )
        """)
    
    async def _initialize_system_monitoring(self) -> None:
        """初始化系統資源監控"""
        # 更新系統資源限制
        memory_info = psutil.virtual_memory()
        self._system_resources[ResourceType.MEMORY] = TestResource(
            ResourceType.MEMORY, 0, memory_info.total, 'bytes'
        )
        
        cpu_count = psutil.cpu_count()
        self._system_resources[ResourceType.CPU] = TestResource(
            ResourceType.CPU, 0, cpu_count * 100, 'percent'
        )
        
        self.logger.info(f"系統資源監控初始化完成 - CPU: {cpu_count} 核心, 記憶體: {memory_info.total // (1024**3)} GB")
    
    async def create_test_environment(self, config: Optional[TestEnvironmentConfig] = None) -> str:
        """創建測試環境"""
        if config is None:
            config = self.default_config
            config.environment_id = str(uuid.uuid4())
        
        # 檢查系統資源是否足夠
        if not await self._check_resource_availability(config):
            raise ServiceError("系統資源不足，無法創建測試環境", "create_test_environment")
        
        # 創建獨立的測試資料庫
        temp_db_path = await self._create_test_database(config.environment_id)
        
        # 生成工作者配置
        worker_configs = await self._generate_worker_configs(config)
        
        # 創建測試會話
        session = TestSession(
            session_id=str(uuid.uuid4()),
            environment_config=config,
            worker_configs=worker_configs,
            status=TestEnvironmentStatus.INITIALIZING,
            created_at=datetime.now()
        )
        
        # 保存到資料庫
        await self.db.execute("""
            INSERT INTO test_sessions (
                session_id, environment_config, worker_configs, status, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            session.session_id,
            json.dumps(config.to_dict()),
            json.dumps([w.to_dict() for w in worker_configs]),
            session.status.value,
            session.created_at
        ))
        
        # 註冊會話
        self._active_sessions[session.session_id] = session
        self._test_databases[session.session_id] = temp_db_path
        
        # 設置資源分配
        await self._allocate_resources(session.session_id, config)
        
        # 標記為準備完成
        session.status = TestEnvironmentStatus.READY
        await self._update_session_status(session.session_id, TestEnvironmentStatus.READY)
        
        self.logger.info(f"測試環境創建完成 - 會話ID: {session.session_id}")
        return session.session_id
    
    async def _check_resource_availability(self, config: TestEnvironmentConfig) -> bool:
        """檢查系統資源可用性"""
        try:
            # 檢查CPU可用性
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                self.logger.warning(f"CPU使用率過高: {cpu_percent}%")
                return False
            
            # 檢查記憶體可用性
            memory = psutil.virtual_memory()
            required_memory = config.total_workers * 100 * 1024 * 1024  # 每工作者預估100MB
            if memory.available < required_memory:
                self.logger.warning(f"可用記憶體不足: 需要 {required_memory // (1024**2)} MB, 可用 {memory.available // (1024**2)} MB")
                return False
            
            # 檢查連線數限制
            if config.max_concurrent_connections > 1000:
                self.logger.warning(f"連線數超過系統建議限制: {config.max_concurrent_connections}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"資源可用性檢查失敗: {e}")
            return False
    
    async def _create_test_database(self, environment_id: str) -> str:
        """創建獨立的測試資料庫"""
        try:
            # 創建臨時資料庫文件
            temp_dir = tempfile.gettempdir()
            temp_db_path = os.path.join(temp_dir, f"test_db_{environment_id}_{int(time.time())}.db")
            
            # 從主資料庫複製結構
            main_db_path = self.db.db_name
            
            # 使用SQLite的BACKUP命令複製資料庫結構
            import sqlite3
            main_conn = sqlite3.connect(main_db_path)
            test_conn = sqlite3.connect(temp_db_path)
            
            # 複製結構（不含數據）
            main_conn.backup(test_conn)
            
            # 清空所有數據，只保留結構
            cursor = test_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                if not table_name.startswith('sqlite_'):
                    cursor.execute(f"DELETE FROM {table_name}")
            
            test_conn.commit()
            test_conn.close()
            main_conn.close()
            
            self.logger.info(f"測試資料庫創建完成: {temp_db_path}")
            return temp_db_path
            
        except Exception as e:
            self.logger.error(f"測試資料庫創建失敗: {e}")
            raise ServiceError("測試資料庫創建失敗", "_create_test_database", str(e))
    
    async def _generate_worker_configs(self, env_config: TestEnvironmentConfig) -> List[WorkerConfig]:
        """生成工作者配置"""
        worker_configs = []
        
        # 平均分配連線數給每個工作者
        connections_per_worker = env_config.max_concurrent_connections // env_config.total_workers
        remaining_connections = env_config.max_concurrent_connections % env_config.total_workers
        
        # 定義不同的測試操作模式
        operation_patterns = [
            ['read_heavy'],  # 讀取密集型
            ['write_heavy'], # 寫入密集型
            ['mixed'],       # 混合型
            ['transaction_heavy']  # 事務密集型
        ]
        
        for i in range(env_config.total_workers):
            # 為每個工作者分配連線數
            worker_connections = connections_per_worker
            if i < remaining_connections:
                worker_connections += 1
            
            # 選擇操作模式（循環分配不同模式）
            operations = operation_patterns[i % len(operation_patterns)]
            
            # 創建工作者配置
            config = WorkerConfig(
                worker_id=f"worker_{i+1:03d}",
                concurrent_connections=worker_connections,
                test_duration_seconds=env_config.test_duration_minutes * 60,
                request_rate_per_second=10,  # 每秒10個請求
                database_operations=operations,
                metadata={
                    'worker_index': i,
                    'operation_pattern': operations[0] if operations else 'mixed'
                }
            )
            
            worker_configs.append(config)
        
        return worker_configs
    
    async def _allocate_resources(self, session_id: str, config: TestEnvironmentConfig) -> None:
        """分配系統資源"""
        try:
            # 分配CPU資源
            cpu_allocation = min(config.resource_limits.get(ResourceType.CPU, 50), 
                               self._system_resources[ResourceType.CPU].limit - self._system_resources[ResourceType.CPU].allocated)
            self._system_resources[ResourceType.CPU].allocated += cpu_allocation
            
            # 分配記憶體資源
            memory_needed = config.total_workers * 100 * 1024 * 1024  # 100MB per worker
            memory_allocation = min(memory_needed,
                                  self._system_resources[ResourceType.MEMORY].limit - self._system_resources[ResourceType.MEMORY].allocated)
            self._system_resources[ResourceType.MEMORY].allocated += memory_allocation
            
            # 分配連線資源
            connection_allocation = config.max_concurrent_connections
            self._system_resources[ResourceType.CONNECTIONS].allocated += connection_allocation
            
            self.logger.info(f"資源分配完成 - 會話 {session_id}: CPU {cpu_allocation}%, 記憶體 {memory_allocation // (1024**2)}MB, 連線 {connection_allocation}")
            
        except Exception as e:
            self.logger.error(f"資源分配失敗: {e}")
            raise ServiceError("資源分配失敗", "_allocate_resources", str(e))
    
    async def start_test_session(self, session_id: str) -> bool:
        """啟動測試會話"""
        try:
            session = self._active_sessions.get(session_id)
            if not session:
                raise ServiceError("測試會話不存在", "start_test_session")
            
            if session.status != TestEnvironmentStatus.READY:
                raise ServiceError("測試會話狀態不正確", "start_test_session")
            
            # 更新狀態為運行中
            session.status = TestEnvironmentStatus.RUNNING
            session.started_at = datetime.now()
            await self._update_session_status(session_id, TestEnvironmentStatus.RUNNING)
            
            # 啟動資源監控
            asyncio.create_task(self._monitor_session_resources(session_id))
            
            # 根據隔離模式啟動工作者
            if session.environment_config.isolation_mode == 'async':
                await self._start_async_workers(session)
            elif session.environment_config.isolation_mode == 'thread':
                await self._start_threaded_workers(session)
            elif session.environment_config.isolation_mode == 'process':
                await self._start_process_workers(session)
            
            self.logger.info(f"測試會話啟動完成 - 會話ID: {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"測試會話啟動失敗: {e}")
            if session_id in self._active_sessions:
                self._active_sessions[session_id].status = TestEnvironmentStatus.ERROR
                self._active_sessions[session_id].error_message = str(e)
                await self._update_session_status(session_id, TestEnvironmentStatus.ERROR, str(e))
            return False
    
    async def _start_async_workers(self, session: TestSession) -> None:
        """啟動異步工作者"""
        tasks = []
        
        for worker_config in session.worker_configs:
            task = asyncio.create_task(
                self._run_async_worker(session.session_id, worker_config)
            )
            tasks.append(task)
        
        # 等待所有工作者完成
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            await self._process_worker_results(session.session_id, results)
        except Exception as e:
            self.logger.error(f"異步工作者執行失敗: {e}")
        finally:
            await self._complete_test_session(session.session_id)
    
    async def _run_async_worker(self, session_id: str, worker_config: WorkerConfig) -> Dict[str, Any]:
        """運行異步工作者"""
        worker_results = {
            'worker_id': worker_config.worker_id,
            'success_count': 0,
            'error_count': 0,
            'total_response_time': 0.0,
            'peak_memory': 0.0,
            'errors': []
        }
        
        # 記錄工作者開始執行
        await self.db.execute("""
            INSERT INTO test_worker_executions (
                session_id, worker_id, started_at
            ) VALUES (?, ?, ?)
        """, (session_id, worker_config.worker_id, datetime.now()))
        
        try:
            # 獲取測試資料庫連線
            test_db_path = self._test_databases.get(session_id)
            if not test_db_path:
                raise Exception("測試資料庫不存在")
            
            # 創建專用的資料庫管理器實例
            from core.database_manager import DatabaseManager
            worker_db = DatabaseManager(db_name=test_db_path)
            await worker_db.initialize()
            
            # 執行並發測試
            end_time = datetime.now() + timedelta(seconds=worker_config.test_duration_seconds)
            
            while datetime.now() < end_time:
                # 模擬並發連線請求
                concurrent_tasks = []
                for _ in range(worker_config.concurrent_connections):
                    task = asyncio.create_task(
                        self._execute_database_operation(
                            worker_db, worker_config, worker_results, session_id
                        )
                    )
                    concurrent_tasks.append(task)
                
                # 等待這一批連線完成
                await asyncio.gather(*concurrent_tasks, return_exceptions=True)
                
                # 控制請求頻率
                await asyncio.sleep(1.0 / worker_config.request_rate_per_second)
            
            # 清理資源
            await worker_db.cleanup()
            
        except Exception as e:
            self.logger.error(f"工作者 {worker_config.worker_id} 執行失敗: {e}")
            worker_results['errors'].append(str(e))
            worker_results['error_count'] += 1
        
        finally:
            # 更新工作者執行記錄
            avg_response_time = (worker_results['total_response_time'] / 
                               max(worker_results['success_count'], 1))
            
            await self.db.execute("""
                UPDATE test_worker_executions 
                SET completed_at = ?, success_count = ?, error_count = ?, 
                    avg_response_time_ms = ?, peak_memory_mb = ?, error_details = ?
                WHERE session_id = ? AND worker_id = ?
            """, (
                datetime.now(), worker_results['success_count'], worker_results['error_count'],
                avg_response_time, worker_results['peak_memory'], 
                json.dumps(worker_results['errors']),
                session_id, worker_config.worker_id
            ))
        
        return worker_results
    
    async def _execute_database_operation(self, 
                                        worker_db: DatabaseManager, 
                                        worker_config: WorkerConfig, 
                                        worker_results: Dict[str, Any],
                                        session_id: str) -> None:
        """執行資料庫操作"""
        operation_start = time.time()
        
        try:
            # 記錄連線取得事件
            await self.db.execute("""
                INSERT INTO test_connection_events (
                    session_id, worker_id, event_type, timestamp
                ) VALUES (?, ?, ?, ?)
            """, (session_id, worker_config.worker_id, 'acquire', datetime.now()))
            
            # 根據操作類型執行不同的資料庫操作
            for operation_type in worker_config.database_operations:
                if operation_type == 'read_heavy':
                    await self._execute_read_operations(worker_db)
                elif operation_type == 'write_heavy':
                    await self._execute_write_operations(worker_db)
                elif operation_type == 'mixed':
                    await self._execute_mixed_operations(worker_db)
                elif operation_type == 'transaction_heavy':
                    await self._execute_transaction_operations(worker_db)
            
            # 記錄成功
            worker_results['success_count'] += 1
            
            # 記錄連線釋放事件
            await self.db.execute("""
                INSERT INTO test_connection_events (
                    session_id, worker_id, event_type, timestamp, wait_time_ms
                ) VALUES (?, ?, ?, ?, ?)
            """, (session_id, worker_config.worker_id, 'release', datetime.now(),
                  (time.time() - operation_start) * 1000))
            
        except Exception as e:
            # 記錄錯誤
            worker_results['error_count'] += 1
            worker_results['errors'].append(str(e))
            
            # 記錄連線錯誤事件
            await self.db.execute("""
                INSERT INTO test_connection_events (
                    session_id, worker_id, event_type, timestamp, wait_time_ms, error_message
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, worker_config.worker_id, 'error', datetime.now(),
                  (time.time() - operation_start) * 1000, str(e)))
        
        # 記錄響應時間
        response_time = (time.time() - operation_start) * 1000
        worker_results['total_response_time'] += response_time
    
    async def _execute_read_operations(self, db: DatabaseManager) -> None:
        """執行讀取操作"""
        # 模擬複雜查詢
        await db.fetchall("SELECT * FROM welcome_settings LIMIT 10")
        await db.fetchall("SELECT * FROM monitored_channels")
        await db.fetchone("SELECT COUNT(*) FROM settings")
    
    async def _execute_write_operations(self, db: DatabaseManager) -> None:
        """執行寫入操作"""
        test_id = int(time.time() * 1000) % 1000000
        await db.execute(
            "INSERT OR IGNORE INTO settings (setting_name, setting_value) VALUES (?, ?)",
            (f"test_setting_{test_id}", f"test_value_{test_id}")
        )
    
    async def _execute_mixed_operations(self, db: DatabaseManager) -> None:
        """執行混合操作"""
        # 混合讀寫操作
        await self._execute_read_operations(db)
        if time.time() % 3 < 1:  # 1/3的機率寫入
            await self._execute_write_operations(db)
    
    async def _execute_transaction_operations(self, db: DatabaseManager) -> None:
        """執行事務操作"""
        async with db.transaction():
            test_id = int(time.time() * 1000) % 1000000
            await db.execute(
                "INSERT OR IGNORE INTO settings (setting_name, setting_value) VALUES (?, ?)",
                (f"trans_setting_{test_id}", "value1")
            )
            await db.execute(
                "UPDATE settings SET setting_value = ? WHERE setting_name = ?",
                ("value2", f"trans_setting_{test_id}")
            )
    
    async def _monitor_session_resources(self, session_id: str) -> None:
        """監控會話資源使用"""
        session = self._active_sessions.get(session_id)
        if not session:
            return
        
        while session.status == TestEnvironmentStatus.RUNNING:
            try:
                # 收集資源使用統計
                for resource_type, resource in self._system_resources.items():
                    await self.db.execute("""
                        INSERT INTO test_resource_usage (
                            session_id, timestamp, resource_type, allocated, limit_value, utilization
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        session_id, datetime.now(), resource_type.value,
                        resource.allocated, resource.limit, resource.utilization
                    ))
                
                await asyncio.sleep(session.environment_config.monitoring_interval_seconds)
                
            except Exception as e:
                self.logger.error(f"資源監控錯誤: {e}")
                await asyncio.sleep(30)
    
    async def _process_worker_results(self, session_id: str, results: List[Any]) -> None:
        """處理工作者結果"""
        session = self._active_sessions.get(session_id)
        if not session:
            return
        
        # 統計整體結果
        total_success = 0
        total_errors = 0
        total_response_time = 0.0
        
        for result in results:
            if isinstance(result, dict):
                total_success += result.get('success_count', 0)
                total_errors += result.get('error_count', 0)
                total_response_time += result.get('total_response_time', 0.0)
        
        # 計算統計信息
        total_requests = total_success + total_errors
        avg_response_time = total_response_time / max(total_requests, 1)
        error_rate = (total_errors / max(total_requests, 1)) * 100
        
        # 保存結果摘要
        session.results_summary = {
            'total_requests': total_requests,
            'successful_requests': total_success,
            'failed_requests': total_errors,
            'error_rate_percent': error_rate,
            'avg_response_time_ms': avg_response_time,
            'test_duration_seconds': (datetime.now() - session.started_at).total_seconds() if session.started_at else 0
        }
    
    async def _complete_test_session(self, session_id: str) -> None:
        """完成測試會話"""
        session = self._active_sessions.get(session_id)
        if not session:
            return
        
        try:
            session.status = TestEnvironmentStatus.CLEANING
            session.completed_at = datetime.now()
            
            # 更新資料庫記錄
            await self.db.execute("""
                UPDATE test_sessions 
                SET status = ?, completed_at = ?, results_summary = ?
                WHERE session_id = ?
            """, (
                session.status.value, session.completed_at,
                json.dumps(session.results_summary) if session.results_summary else None,
                session_id
            ))
            
            # 清理資源
            if session.environment_config.cleanup_after_test:
                await self._cleanup_test_environment(session_id)
            
            session.status = TestEnvironmentStatus.SHUTDOWN
            await self._update_session_status(session_id, TestEnvironmentStatus.SHUTDOWN)
            
            self.logger.info(f"測試會話完成 - 會話ID: {session_id}")
            
        except Exception as e:
            self.logger.error(f"測試會話完成處理失敗: {e}")
    
    async def _cleanup_test_environment(self, session_id: str) -> None:
        """清理測試環境"""
        try:
            # 清理測試資料庫
            if session_id in self._test_databases:
                test_db_path = self._test_databases[session_id]
                if os.path.exists(test_db_path):
                    os.remove(test_db_path)
                del self._test_databases[session_id]
            
            # 釋放系統資源
            await self._deallocate_resources(session_id)
            
            # 清理執行器
            if session_id in self._worker_executors:
                executor = self._worker_executors[session_id]
                executor.shutdown(wait=True)
                del self._worker_executors[session_id]
            
            self.logger.info(f"測試環境清理完成 - 會話ID: {session_id}")
            
        except Exception as e:
            self.logger.error(f"測試環境清理失敗: {e}")
    
    async def _deallocate_resources(self, session_id: str) -> None:
        """釋放分配的資源"""
        session = self._active_sessions.get(session_id)
        if not session:
            return
        
        config = session.environment_config
        
        # 釋放CPU資源
        cpu_allocation = min(config.resource_limits.get(ResourceType.CPU, 0), 
                           self._system_resources[ResourceType.CPU].allocated)
        self._system_resources[ResourceType.CPU].allocated = max(0, 
            self._system_resources[ResourceType.CPU].allocated - cpu_allocation)
        
        # 釋放記憶體資源
        memory_allocation = config.total_workers * 100 * 1024 * 1024
        self._system_resources[ResourceType.MEMORY].allocated = max(0,
            self._system_resources[ResourceType.MEMORY].allocated - memory_allocation)
        
        # 釋放連線資源
        self._system_resources[ResourceType.CONNECTIONS].allocated = max(0,
            self._system_resources[ResourceType.CONNECTIONS].allocated - config.max_concurrent_connections)
    
    async def _update_session_status(self, session_id: str, status: TestEnvironmentStatus, error_message: Optional[str] = None) -> None:
        """更新會話狀態"""
        await self.db.execute("""
            UPDATE test_sessions 
            SET status = ?, error_message = ?
            WHERE session_id = ?
        """, (status.value, error_message, session_id))
    
    async def get_session_status(self, session_id: str) -> Optional[TestSession]:
        """獲取會話狀態"""
        return self._active_sessions.get(session_id)
    
    async def get_active_sessions(self) -> List[TestSession]:
        """獲取所有活動會話"""
        return list(self._active_sessions.values())
    
    async def get_system_resources(self) -> Dict[str, TestResource]:
        """獲取系統資源狀態"""
        return {rt.value: resource for rt, resource in self._system_resources.items()}
    
    async def _start_threaded_workers(self, session: TestSession) -> None:
        """啟動線程工作者（預留實現）"""
        # 這裡可以實現基於線程的工作者執行
        pass
    
    async def _start_process_workers(self, session: TestSession) -> None:
        """啟動進程工作者（預留實現）"""
        # 這裡可以實現基於進程的工作者執行
        pass