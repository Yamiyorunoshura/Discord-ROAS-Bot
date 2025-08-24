"""
連線池監控資料表管理
T2 - 高併發連線競爭修復實施

提供connection_pool_stats監控表的創建、維護和查詢功能
支援連線池效能指標的持久化存儲和歷史分析
"""

import sqlite3
import logging
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from contextlib import contextmanager
from dataclasses import asdict

from ..db.sqlite import OptimizedConnection, SQLiteConnectionFactory
from ..db.retry import retry_on_database_locked, CommonRetryStrategies

logger = logging.getLogger('src.services.connection_pool_monitor')


class ConnectionPoolMonitor:
    """
    連線池監控資料表管理器
    
    負責創建、維護connection_pool_stats表，並提供效能數據的持久化功能
    支援歷史數據查詢、統計分析和自動清理過期數據
    """
    
    # 監控表SQL結構
    CREATE_MONITOR_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS connection_pool_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        db_path TEXT NOT NULL,
        active_connections INTEGER DEFAULT 0,
        idle_connections INTEGER DEFAULT 0,
        total_connections INTEGER DEFAULT 0,
        max_connections INTEGER DEFAULT 0,
        total_requests INTEGER DEFAULT 0,
        successful_requests INTEGER DEFAULT 0,
        failed_requests INTEGER DEFAULT 0,
        average_wait_time_ms REAL DEFAULT 0.0,
        peak_wait_time_ms REAL DEFAULT 0.0,
        success_rate REAL DEFAULT 100.0,
        error_rate REAL DEFAULT 0.0,
        pool_efficiency REAL DEFAULT 100.0,
        config_data TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    # 創建索引以優化查詢效能
    CREATE_INDEXES_SQL = [
        "CREATE INDEX IF NOT EXISTS idx_pool_stats_timestamp ON connection_pool_stats(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_pool_stats_db_path ON connection_pool_stats(db_path);",
        "CREATE INDEX IF NOT EXISTS idx_pool_stats_created_at ON connection_pool_stats(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_pool_stats_success_rate ON connection_pool_stats(success_rate);",
        "CREATE INDEX IF NOT EXISTS idx_pool_stats_composite ON connection_pool_stats(db_path, timestamp);"
    ]
    
    def __init__(self, monitor_db_path: str = None):
        """
        初始化連線池監控器
        
        參數:
            monitor_db_path: 監控資料庫路徑，None則使用預設路徑
        """
        if monitor_db_path is None:
            # 使用專門的監控資料庫，避免與業務資料庫混合
            monitor_db_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                '..', '..', 'data', 'connection_pool_monitor.db'
            )
        
        self.monitor_db_path = os.path.abspath(monitor_db_path)
        
        # 確保監控資料庫目錄存在
        os.makedirs(os.path.dirname(self.monitor_db_path), exist_ok=True)
        
        # 連線工廠
        self._factory = SQLiteConnectionFactory(self.monitor_db_path)
        
        # 初始化標誌
        self._initialized = False
        
        logger.info(f"連線池監控器已建立 - 監控資料庫: {self.monitor_db_path}")
    
    @retry_on_database_locked(strategy=CommonRetryStrategies.BALANCED)
    def initialize_monitor_tables(self):
        """初始化監控資料表結構"""
        if self._initialized:
            return
        
        try:
            conn = self._factory.get_connection()
            
            with conn.transaction():
                # 創建監控表
                conn.execute(self.CREATE_MONITOR_TABLE_SQL)
                
                # 創建索引
                for index_sql in self.CREATE_INDEXES_SQL:
                    conn.execute(index_sql)
            
            self._initialized = True
            logger.info("監控資料表結構已初始化")
            
        except Exception as e:
            logger.error(f"初始化監控資料表失敗: {e}")
            raise
    
    @retry_on_database_locked(strategy=CommonRetryStrategies.BALANCED)
    def record_pool_statistics(self, pool_stats: Dict[str, Any]) -> int:
        """
        記錄連線池統計數據
        
        參數:
            pool_stats: 連線池統計數據字典
            
        返回:
            插入記錄的ID
        """
        if not self._initialized:
            self.initialize_monitor_tables()
        
        try:
            conn = self._factory.get_connection()
            
            # 準備插入數據
            insert_sql = """
            INSERT INTO connection_pool_stats (
                timestamp,
                db_path,
                active_connections,
                idle_connections,
                total_connections,
                max_connections,
                total_requests,
                successful_requests,
                failed_requests,
                average_wait_time_ms,
                peak_wait_time_ms,
                success_rate,
                error_rate,
                pool_efficiency,
                config_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # 處理配置數據
            import json
            config_json = json.dumps(pool_stats.get('config', {}))
            
            params = (
                pool_stats.get('timestamp', datetime.utcnow()),
                pool_stats.get('db_path', ''),
                pool_stats.get('active_connections', 0),
                pool_stats.get('idle_connections', 0),
                pool_stats.get('total_connections', 0),
                pool_stats.get('max_connections_used', 0),
                pool_stats.get('total_requests', 0),
                pool_stats.get('successful_requests', 0),
                pool_stats.get('failed_requests', 0),
                pool_stats.get('average_wait_time_ms', 0.0),
                pool_stats.get('peak_wait_time_ms', 0.0),
                pool_stats.get('success_rate', 100.0),
                pool_stats.get('error_rate', 0.0),
                pool_stats.get('pool_efficiency', 100.0),
                config_json
            )
            
            cursor = conn.execute(insert_sql, params)
            conn.commit()
            
            record_id = cursor.lastrowid
            logger.debug(f"已記錄連線池統計 - ID: {record_id}, DB: {pool_stats.get('db_path', 'unknown')}")
            return record_id
            
        except Exception as e:
            logger.error(f"記錄連線池統計失敗: {e}")
            raise
    
    @retry_on_database_locked(strategy=CommonRetryStrategies.BALANCED)
    def get_recent_statistics(self, db_path: str = None, hours: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        獲取最近的連線池統計數據
        
        參數:
            db_path: 資料庫路徑篩選，None表示所有資料庫
            hours: 查詢最近多少小時的數據
            limit: 最大記錄數
            
        返回:
            統計數據列表
        """
        if not self._initialized:
            self.initialize_monitor_tables()
        
        try:
            conn = self._factory.get_connection()
            
            # 構建查詢SQL
            base_sql = """
            SELECT * FROM connection_pool_stats
            WHERE timestamp >= ?
            """
            params = [datetime.utcnow() - timedelta(hours=hours)]
            
            if db_path:
                base_sql += " AND db_path = ?"
                params.append(db_path)
            
            base_sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(base_sql, params)
            rows = cursor.fetchall()
            
            # 轉換為字典列表
            columns = [description[0] for description in cursor.description]
            results = []
            
            for row in rows:
                result = dict(zip(columns, row))
                # 解析配置JSON
                if result.get('config_data'):
                    try:
                        import json
                        result['config'] = json.loads(result['config_data'])
                    except:
                        result['config'] = {}
                del result['config_data']
                results.append(result)
            
            logger.debug(f"查詢到 {len(results)} 條統計記錄")
            return results
            
        except Exception as e:
            logger.error(f"查詢統計數據失敗: {e}")
            raise
    
    @retry_on_database_locked(strategy=CommonRetryStrategies.BALANCED)
    def get_performance_summary(self, db_path: str = None, hours: int = 24) -> Dict[str, Any]:
        """
        獲取效能摘要報告
        
        參數:
            db_path: 資料庫路徑篩選
            hours: 統計時間範圍(小時)
            
        返回:
            效能摘要字典
        """
        if not self._initialized:
            self.initialize_monitor_tables()
        
        try:
            conn = self._factory.get_connection()
            
            # 構建摘要查詢SQL
            base_sql = """
            SELECT 
                COUNT(*) as record_count,
                AVG(active_connections) as avg_active_connections,
                MAX(active_connections) as peak_active_connections,
                AVG(total_connections) as avg_total_connections,
                MAX(total_connections) as peak_total_connections,
                AVG(success_rate) as avg_success_rate,
                MIN(success_rate) as min_success_rate,
                AVG(error_rate) as avg_error_rate,
                MAX(error_rate) as max_error_rate,
                AVG(average_wait_time_ms) as avg_wait_time_ms,
                MAX(peak_wait_time_ms) as max_wait_time_ms,
                AVG(pool_efficiency) as avg_pool_efficiency,
                MIN(pool_efficiency) as min_pool_efficiency,
                SUM(total_requests) as total_requests_sum,
                SUM(successful_requests) as successful_requests_sum,
                SUM(failed_requests) as failed_requests_sum
            FROM connection_pool_stats
            WHERE timestamp >= ?
            """
            params = [datetime.utcnow() - timedelta(hours=hours)]
            
            if db_path:
                base_sql += " AND db_path = ?"
                params.append(db_path)
            
            cursor = conn.execute(base_sql, params)
            row = cursor.fetchone()
            
            if not row or row[0] == 0:
                return {
                    'period_hours': hours,
                    'db_path': db_path,
                    'no_data': True,
                    'message': f'最近 {hours} 小時內無統計數據'
                }
            
            # 構建摘要結果
            columns = [description[0] for description in cursor.description]
            summary = dict(zip(columns, row))
            
            # 計算衍生指標
            if summary['total_requests_sum'] > 0:
                summary['overall_success_rate'] = (
                    summary['successful_requests_sum'] / summary['total_requests_sum']
                ) * 100.0
                summary['overall_error_rate'] = 100.0 - summary['overall_success_rate']
            else:
                summary['overall_success_rate'] = 100.0
                summary['overall_error_rate'] = 0.0
            
            # 添加元數據
            summary['period_hours'] = hours
            summary['db_path'] = db_path
            summary['generated_at'] = datetime.utcnow()
            
            logger.debug(f"生成效能摘要 - 記錄數: {summary['record_count']}")
            return summary
            
        except Exception as e:
            logger.error(f"生成效能摘要失敗: {e}")
            raise
    
    @retry_on_database_locked(strategy=CommonRetryStrategies.BALANCED)
    def cleanup_old_records(self, retention_days: int = 7) -> int:
        """
        清理過期的監控記錄
        
        參數:
            retention_days: 保留天數，超過此天數的記錄將被刪除
            
        返回:
            清理的記錄數
        """
        if not self._initialized:
            self.initialize_monitor_tables()
        
        try:
            conn = self._factory.get_connection()
            
            cutoff_time = datetime.utcnow() - timedelta(days=retention_days)
            
            # 先查詢要刪除的記錄數
            count_sql = "SELECT COUNT(*) FROM connection_pool_stats WHERE timestamp < ?"
            count_cursor = conn.execute(count_sql, (cutoff_time,))
            delete_count = count_cursor.fetchone()[0]
            
            if delete_count > 0:
                # 執行刪除
                delete_sql = "DELETE FROM connection_pool_stats WHERE timestamp < ?"
                conn.execute(delete_sql, (cutoff_time,))
                conn.commit()
                
                # 整理資料庫
                conn.execute("VACUUM")
                
                logger.info(f"已清理 {delete_count} 條過期監控記錄 (超過 {retention_days} 天)")
            else:
                logger.debug(f"無需清理監控記錄 (保留期限: {retention_days} 天)")
            
            return delete_count
            
        except Exception as e:
            logger.error(f"清理過期記錄失敗: {e}")
            raise
    
    @retry_on_database_locked(strategy=CommonRetryStrategies.BALANCED)
    def get_connection_health_trends(self, db_path: str, hours: int = 24) -> Dict[str, List]:
        """
        獲取連線健康趨勢數據
        
        參數:
            db_path: 資料庫路徑
            hours: 分析時間範圍
            
        返回:
            趨勢數據字典，包含時間序列和各項指標
        """
        if not self._initialized:
            self.initialize_monitor_tables()
        
        try:
            conn = self._factory.get_connection()
            
            sql = """
            SELECT 
                timestamp,
                active_connections,
                total_connections,
                success_rate,
                error_rate,
                average_wait_time_ms,
                pool_efficiency
            FROM connection_pool_stats
            WHERE db_path = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            """
            
            params = (db_path, datetime.utcnow() - timedelta(hours=hours))
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            
            # 構建趨勢數據
            trends = {
                'timestamps': [],
                'active_connections': [],
                'total_connections': [],
                'success_rates': [],
                'error_rates': [],
                'wait_times': [],
                'efficiencies': []
            }
            
            for row in rows:
                trends['timestamps'].append(row[0])
                trends['active_connections'].append(row[1])
                trends['total_connections'].append(row[2])
                trends['success_rates'].append(row[3])
                trends['error_rates'].append(row[4])
                trends['wait_times'].append(row[5])
                trends['efficiencies'].append(row[6])
            
            trends['data_points'] = len(rows)
            trends['db_path'] = db_path
            trends['period_hours'] = hours
            
            logger.debug(f"獲取健康趨勢數據 - {len(rows)} 個數據點")
            return trends
            
        except Exception as e:
            logger.error(f"獲取健康趨勢失敗: {e}")
            raise
    
    def get_monitor_database_stats(self) -> Dict[str, Any]:
        """獲取監控資料庫本身的統計資訊"""
        try:
            conn = self._factory.get_connection()
            
            # 獲取表信息
            table_info = conn.execute("PRAGMA table_info(connection_pool_stats)").fetchall()
            
            # 獲取記錄數
            total_records = conn.execute("SELECT COUNT(*) FROM connection_pool_stats").fetchone()[0]
            
            # 獲取資料庫大小
            db_size = os.path.getsize(self.monitor_db_path) if os.path.exists(self.monitor_db_path) else 0
            
            # 獲取最早和最新記錄時間
            time_range = conn.execute("""
                SELECT MIN(timestamp) as earliest, MAX(timestamp) as latest 
                FROM connection_pool_stats
            """).fetchone()
            
            stats = {
                'monitor_db_path': self.monitor_db_path,
                'total_records': total_records,
                'db_size_bytes': db_size,
                'db_size_mb': round(db_size / (1024 * 1024), 2),
                'table_columns': len(table_info),
                'earliest_record': time_range[0] if time_range[0] else None,
                'latest_record': time_range[1] if time_range[1] else None,
                'initialized': self._initialized
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"獲取監控資料庫統計失敗: {e}")
            return {'error': str(e)}
    
    def close(self):
        """關閉監控器"""
        try:
            if hasattr(self, '_factory'):
                self._factory.close_all_connections()
            logger.info("連線池監控器已關閉")
        except Exception as e:
            logger.error(f"關閉監控器失敗: {e}")


# 全局監控器實例
_global_monitor: Optional[ConnectionPoolMonitor] = None
_monitor_lock = asyncio.Lock()


async def get_global_monitor(monitor_db_path: str = None) -> ConnectionPoolMonitor:
    """
    獲取全局監控器實例
    
    參數:
        monitor_db_path: 監控資料庫路徑
        
    返回:
        監控器實例
    """
    global _global_monitor
    
    async with _monitor_lock:
        if _global_monitor is None:
            _global_monitor = ConnectionPoolMonitor(monitor_db_path)
            _global_monitor.initialize_monitor_tables()
            logger.info("全局連線池監控器已初始化")
        
        return _global_monitor


def get_sync_global_monitor(monitor_db_path: str = None) -> ConnectionPoolMonitor:
    """
    同步獲取全局監控器實例
    
    參數:
        monitor_db_path: 監控資料庫路徑
        
    返回:
        監控器實例
    """
    global _global_monitor
    
    if _global_monitor is None:
        _global_monitor = ConnectionPoolMonitor(monitor_db_path)
        _global_monitor.initialize_monitor_tables()
        logger.info("全局連線池監控器已初始化 (同步)")
    
    return _global_monitor


async def cleanup_global_monitor():
    """清理全局監控器"""
    global _global_monitor
    
    async with _monitor_lock:
        if _global_monitor:
            _global_monitor.close()
            _global_monitor = None
            logger.info("全局連線池監控器已清理")