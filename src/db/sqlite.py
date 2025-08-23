"""
SQLite 連線工廠與配置優化
T3 - 併發與資料庫鎖定穩定性實施

提供集中化 SQLite 連線管理，啟用 WAL 模式與適當的 busy_timeout
實現連線重用與併發安全的資料庫操作
"""

import os
import sqlite3
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, Union
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime

logger = logging.getLogger('src.db.sqlite')

class OptimizedConnection:
    """
    優化的 SQLite 連線包裝類
    
    提供連線級別的優化配置與重試機制整合
    """
    
    def __init__(self, db_path: str, **config):
        self.db_path = db_path
        self.config = config
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self.is_closed = False
    
    def connect(self) -> sqlite3.Connection:
        """建立並配置 SQLite 連線"""
        if self._conn is None or self.is_closed:
            with self._lock:
                if self._conn is None or self.is_closed:
                    self._conn = sqlite3.connect(self.db_path, **self.config)
                    self._configure_connection(self._conn)
                    self.is_closed = False
        
        return self._conn
    
    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        """配置連線參數以優化併發性能"""
        try:
            # 啟用 WAL 模式以提升併發讀寫性能
            conn.execute("PRAGMA journal_mode=WAL;")
            
            # 設定 busy_timeout 處理鎖定衝突
            conn.execute("PRAGMA busy_timeout=30000;")  # 30 秒
            
            # 優化同步模式平衡性能與安全性
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            # 啟用外鍵約束
            conn.execute("PRAGMA foreign_keys=ON;")
            
            # 設定適當的快取大小 (10MB)
            conn.execute("PRAGMA cache_size=10240;")
            
            # 設定 temp_store 使用記憶體
            conn.execute("PRAGMA temp_store=MEMORY;")
            
            # 設定 mmap_size 使用記憶體映射 (256MB)
            conn.execute("PRAGMA mmap_size=268435456;")
            
            conn.commit()
            logger.info(f"SQLite 連線配置完成：{self.db_path}")
            
        except sqlite3.Error as e:
            logger.error(f"配置 SQLite 連線失敗：{e}")
            raise
    
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """執行 SQL 語句"""
        conn = self.connect()
        return conn.execute(sql, params)
    
    def executemany(self, sql: str, params_list) -> sqlite3.Cursor:
        """批量執行 SQL 語句"""
        conn = self.connect()
        return conn.executemany(sql, params_list)
    
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """查詢單筆資料"""
        cursor = self.execute(sql, params)
        return cursor.fetchone()
    
    def fetchall(self, sql: str, params: tuple = ()) -> list:
        """查詢多筆資料"""
        cursor = self.execute(sql, params)
        return cursor.fetchall()
    
    def commit(self):
        """提交事務"""
        if self._conn:
            self._conn.commit()
    
    def rollback(self):
        """回滾事務"""
        if self._conn:
            self._conn.rollback()
    
    @contextmanager
    def transaction(self):
        """事務上下文管理器"""
        conn = self.connect()
        try:
            conn.execute("BEGIN;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def close(self):
        """關閉連線"""
        with self._lock:
            if self._conn and not self.is_closed:
                self._conn.close()
            self.is_closed = True
    
    def __del__(self):
        """析構函數確保連線關閉"""
        try:
            self.close()
        except:
            pass


class SQLiteConnectionFactory:
    """
    SQLite 連線工廠
    
    提供連線重用、配置標準化與執行緒安全的連線管理
    """
    
    _instances: Dict[str, 'SQLiteConnectionFactory'] = {}
    _lock = threading.RLock()
    
    def __new__(cls, db_path: str, **config):
        """單例模式確保同一資料庫路徑只有一個工廠實例"""
        abs_path = os.path.abspath(db_path)
        
        with cls._lock:
            if abs_path not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[abs_path] = instance
                instance._initialized = False
            return cls._instances[abs_path]
    
    def __init__(self, db_path: str, **config):
        """
        初始化連線工廠
        
        參數：
            db_path: 資料庫檔案路徑
            **config: SQLite 連線配置參數
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.db_path = os.path.abspath(db_path)
        self.default_config = {
            'check_same_thread': False,  # 允許跨執行緒使用
            'timeout': 30.0,  # 連線逾時
            'isolation_level': None,  # 自動提交模式
        }
        self.default_config.update(config)
        
        self._connections: Dict[int, OptimizedConnection] = {}
        self._connection_lock = threading.RLock()
        
        # 確保資料庫目錄存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._initialized = True
        logger.info(f"SQLite 連線工廠已建立：{self.db_path}")
    
    def get_connection(self) -> OptimizedConnection:
        """
        獲取當前執行緒的資料庫連線
        
        返回：
            優化的資料庫連線
        """
        thread_id = threading.get_ident()
        
        with self._connection_lock:
            if thread_id not in self._connections or self._connections[thread_id].is_closed:
                self._connections[thread_id] = OptimizedConnection(
                    self.db_path, **self.default_config
                )
                logger.debug(f"為執行緒 {thread_id} 建立新連線：{self.db_path}")
            
            return self._connections[thread_id]
    
    def close_all_connections(self):
        """關閉所有連線"""
        with self._connection_lock:
            for conn in list(self._connections.values()):
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"關閉連線時發生錯誤：{e}")
            
            self._connections.clear()
            logger.info(f"已關閉所有連線：{self.db_path}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """獲取連線統計資訊"""
        with self._connection_lock:
            active_connections = sum(
                1 for conn in self._connections.values() 
                if not conn.is_closed
            )
            
            return {
                'db_path': self.db_path,
                'total_connections': len(self._connections),
                'active_connections': active_connections,
                'thread_ids': list(self._connections.keys())
            }
    
    @staticmethod
    def cleanup_all_factories():
        """清理所有工廠實例"""
        with SQLiteConnectionFactory._lock:
            for factory in list(SQLiteConnectionFactory._instances.values()):
                try:
                    factory.close_all_connections()
                except Exception as e:
                    logger.warning(f"清理工廠時發生錯誤：{e}")
            
            SQLiteConnectionFactory._instances.clear()
            logger.info("已清理所有 SQLite 連線工廠")


# 便利函數
def get_connection_factory(db_path: str, **config) -> SQLiteConnectionFactory:
    """
    獲取指定資料庫的連線工廠
    
    參數：
        db_path: 資料庫檔案路徑
        **config: 連線配置參數
    
    返回：
        連線工廠實例
    """
    return SQLiteConnectionFactory(db_path, **config)


def create_optimized_connection(db_path: str, **config) -> OptimizedConnection:
    """
    創建單一優化連線（適用於簡單場景）
    
    參數：
        db_path: 資料庫檔案路徑
        **config: 連線配置參數
        
    返回：
        優化的資料庫連線
    """
    return OptimizedConnection(db_path, **config)


# 模組級清理函數
def cleanup_connections():
    """清理所有連線（模組卸載時調用）"""
    SQLiteConnectionFactory.cleanup_all_factories()