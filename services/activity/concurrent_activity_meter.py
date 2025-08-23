"""
增強版 ActivityMeterService - T3 併發優化整合
整合 SQLite 連線工廠與重試機制，實施 UPSERT 策略

這個模組是對現有 ActivityService 的增強，專門針對 activity_meter 表的併發操作優化
"""

import os
import logging
import sqlite3
from typing import Optional, Dict, Any
from datetime import datetime

# 導入我們新建立的併發優化組件
from src.db.sqlite import SQLiteConnectionFactory
from src.db.retry import retry_on_database_locked, CommonRetryStrategies

logger = logging.getLogger('services.activity.activity_meter_service')


class ConcurrentActivityMeterService:
    """
    併發安全的 ActivityMeter 服務
    
    專門處理 activity_meter 表的高併發操作，使用 UPSERT 策略避免鎖定衝突
    """
    
    def __init__(self, db_path: str):
        """
        初始化服務
        
        參數：
            db_path: 資料庫檔案路徑
        """
        self.db_path = db_path
        self.factory = SQLiteConnectionFactory(db_path)
        
        # 確保資料庫表存在並已遷移
        self._ensure_table_ready()
        
        logger.info(f"ConcurrentActivityMeterService 已初始化：{db_path}")
    
    def _ensure_table_ready(self):
        """確保 activity_meter 表存在且具有正確的結構"""
        conn = self.factory.get_connection()
        
        try:
            # 檢查表是否存在
            result = conn.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_meter'"
            )
            
            if not result:
                # 表不存在，創建新表
                self._create_activity_meter_table(conn)
            else:
                # 檢查是否有唯一約束
                table_info = conn.fetchall("PRAGMA table_info(activity_meter)")
                
                # 檢查主鍵設置
                has_compound_pk = False
                for col in table_info:
                    if col[5] > 0:  # pk column
                        has_compound_pk = True
                        break
                
                if not has_compound_pk:
                    logger.info("偵測到舊版 activity_meter 表，開始遷移...")
                    self._migrate_activity_meter_table(conn)
        
        except Exception as e:
            logger.error(f"確保表結構時發生錯誤：{e}")
            raise
    
    def _create_activity_meter_table(self, conn):
        """創建具有唯一約束的 activity_meter 表"""
        conn.execute("""
            CREATE TABLE activity_meter (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                score REAL DEFAULT 0,
                last_msg INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # 創建索引
        conn.execute("""
            CREATE INDEX idx_activity_meter_last_msg 
            ON activity_meter(last_msg)
        """)
        
        conn.commit()
        logger.info("已創建具有唯一約束的 activity_meter 表")
    
    def _migrate_activity_meter_table(self, conn):
        """遷移現有的 activity_meter 表"""
        try:
            # 執行遷移 SQL
            with open('/Users/tszkinlai/Coding/roas-bot/migrations/0002_activity_meter_unique_constraint.sql', 'r') as f:
                migration_sql = f.read()
            
            # 分割並執行 SQL 語句
            for statement in migration_sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    conn.execute(statement)
            
            conn.commit()
            logger.info("activity_meter 表遷移完成")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"遷移 activity_meter 表失敗：{e}")
            raise
    
    @retry_on_database_locked(
        strategy=CommonRetryStrategies.AGGRESSIVE,
        log_attempts=True
    )
    def upsert_activity_score(
        self, 
        guild_id: int, 
        user_id: int, 
        score_delta: float, 
        last_msg_time: int,
        max_score: float = 100.0
    ) -> Dict[str, Any]:
        """
        使用 UPSERT 策略更新活躍度分數
        
        這個方法是併發安全的，使用 INSERT ... ON CONFLICT DO UPDATE 避免鎖定衝突
        
        參數：
            guild_id: 伺服器 ID
            user_id: 用戶 ID
            score_delta: 分數變化量
            last_msg_time: 最後訊息時間
            max_score: 最大分數限制
            
        返回：
            包含更新後分數和狀態的字典
        """
        conn = self.factory.get_connection()
        
        try:
            with conn.transaction():
                # 使用 UPSERT 策略更新分數
                # INSERT ... ON CONFLICT DO UPDATE 是 SQLite 3.24+ 的語法
                result = conn.execute("""
                    INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (guild_id, user_id) DO UPDATE SET
                        score = MIN(?, score + ?),
                        last_msg = ?
                    RETURNING score, last_msg
                """, (
                    guild_id, user_id, min(max_score, score_delta), last_msg_time,  # INSERT 值
                    max_score, score_delta, last_msg_time  # UPDATE 值
                ))
                
                row = result.fetchone()
                if row:
                    new_score = row[0]
                    updated_time = row[1]
                    
                    logger.debug(
                        f"UPSERT 活躍度：用戶 {user_id} 在 {guild_id}，"
                        f"新分數 {new_score}，時間 {updated_time}"
                    )
                    
                    return {
                        'success': True,
                        'score': new_score,
                        'last_msg': updated_time,
                        'operation': 'upsert'
                    }
                else:
                    # 兜底：如果 RETURNING 不支持，使用傳統查詢
                    return self._fallback_upsert(conn, guild_id, user_id, score_delta, last_msg_time, max_score)
        
        except sqlite3.OperationalError as e:
            if "ON CONFLICT" in str(e) or "RETURNING" in str(e):
                # SQLite 版本不支持新語法，使用兜底方案
                logger.warning(f"SQLite 版本不支援 UPSERT 語法，使用兜底方案：{e}")
                return self._fallback_upsert(conn, guild_id, user_id, score_delta, last_msg_time, max_score)
            else:
                raise
    
    def _fallback_upsert(self, conn, guild_id: int, user_id: int, score_delta: float, last_msg_time: int, max_score: float) -> Dict[str, Any]:
        """兜底 UPSERT 實現，適用於舊版 SQLite"""
        try:
            with conn.transaction():
                # 嘗試更新
                conn.execute("""
                    UPDATE activity_meter 
                    SET score = MIN(?, score + ?), last_msg = ?
                    WHERE guild_id = ? AND user_id = ?
                """, (max_score, score_delta, last_msg_time, guild_id, user_id))
                
                if conn.execute("SELECT changes()").fetchone()[0] == 0:
                    # 沒有更新任何行，執行插入
                    conn.execute("""
                        INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                        VALUES (?, ?, ?, ?)
                    """, (guild_id, user_id, min(max_score, score_delta), last_msg_time))
                    operation = 'insert'
                else:
                    operation = 'update'
                
                # 查詢最終結果
                result = conn.fetchone("""
                    SELECT score, last_msg FROM activity_meter 
                    WHERE guild_id = ? AND user_id = ?
                """, (guild_id, user_id))
                
                return {
                    'success': True,
                    'score': result[0],
                    'last_msg': result[1],
                    'operation': operation
                }
        
        except Exception as e:
            logger.error(f"兜底 UPSERT 執行失敗：{e}")
            raise
    
    @retry_on_database_locked(
        strategy=CommonRetryStrategies.BALANCED,
        log_attempts=False
    )
    def get_activity_score(self, guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        獲取用戶活躍度分數
        
        參數：
            guild_id: 伺服器 ID
            user_id: 用戶 ID
            
        返回：
            包含分數和時間的字典，如果不存在則返回 None
        """
        conn = self.factory.get_connection()
        
        result = conn.fetchone(
            "SELECT score, last_msg FROM activity_meter WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        
        if result:
            return {
                'score': result[0],
                'last_msg': result[1]
            }
        
        return None
    
    @retry_on_database_locked(
        strategy=CommonRetryStrategies.BALANCED,
        log_attempts=False
    )
    def batch_upsert_activities(self, activities: list) -> Dict[str, Any]:
        """
        批次更新多個活躍度記錄
        
        參數：
            activities: 活躍度記錄列表，每個元素包含 (guild_id, user_id, score_delta, last_msg_time)
            
        返回：
            批次操作結果統計
        """
        if not activities:
            return {'success': True, 'processed': 0, 'errors': 0}
        
        conn = self.factory.get_connection()
        processed = 0
        errors = 0
        
        try:
            with conn.transaction():
                for guild_id, user_id, score_delta, last_msg_time in activities:
                    try:
                        # 對於批次操作，使用更簡單的 UPSERT
                        conn.execute("""
                            INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                                score = MIN(100.0, score + ?),
                                last_msg = ?
                        """, (guild_id, user_id, score_delta, last_msg_time, score_delta, last_msg_time))
                        processed += 1
                        
                    except Exception as e:
                        logger.warning(f"批次處理單項失敗：{e}")
                        errors += 1
                
                logger.info(f"批次 UPSERT 完成：處理 {processed} 筆，錯誤 {errors} 筆")
                
                return {
                    'success': True,
                    'processed': processed,
                    'errors': errors
                }
        
        except sqlite3.OperationalError as e:
            if "ON CONFLICT" in str(e):
                # 兜底到逐個處理
                logger.warning("批次 UPSERT 失敗，改用逐個處理")
                return self._fallback_batch_upsert(conn, activities)
            else:
                raise
    
    def _fallback_batch_upsert(self, conn, activities: list) -> Dict[str, Any]:
        """兜底批次 UPSERT 實現"""
        processed = 0
        errors = 0
        
        for guild_id, user_id, score_delta, last_msg_time in activities:
            try:
                result = self._fallback_upsert(conn, guild_id, user_id, score_delta, last_msg_time, 100.0)
                if result['success']:
                    processed += 1
                else:
                    errors += 1
            except Exception as e:
                logger.warning(f"兜底批次處理項目失敗：{e}")
                errors += 1
        
        return {
            'success': True,
            'processed': processed,
            'errors': errors
        }
    
    @retry_on_database_locked(
        strategy=CommonRetryStrategies.CONSERVATIVE,
        log_attempts=False
    )
    def get_top_users_by_score(self, guild_id: int, limit: int = 10) -> list:
        """
        獲取活躍度排行榜
        
        參數：
            guild_id: 伺服器 ID
            limit: 限制數量
            
        返回：
            排序後的用戶列表
        """
        conn = self.factory.get_connection()
        
        results = conn.fetchall("""
            SELECT user_id, score, last_msg 
            FROM activity_meter 
            WHERE guild_id = ? 
            ORDER BY score DESC, last_msg DESC 
            LIMIT ?
        """, (guild_id, limit))
        
        return [
            {
                'user_id': row[0],
                'score': row[1],
                'last_msg': row[2]
            }
            for row in results
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """獲取服務統計資訊"""
        conn = self.factory.get_connection()
        
        # 獲取總記錄數
        total_records = conn.fetchone("SELECT COUNT(*) FROM activity_meter")[0]
        
        # 獲取連線統計
        connection_stats = self.factory.get_connection_stats()
        
        return {
            'total_activity_records': total_records,
            'connection_stats': connection_stats,
            'database_path': self.db_path
        }
    
    def close(self):
        """關閉服務並清理資源"""
        try:
            self.factory.close_all_connections()
            logger.info("ConcurrentActivityMeterService 已關閉")
        except Exception as e:
            logger.warning(f"關閉服務時發生錯誤：{e}")


# 使用範例與整合輔助函數
def integrate_with_existing_service(existing_db_path: str) -> ConcurrentActivityMeterService:
    """
    與現有 ActivityService 整合的輔助函數
    
    參數：
        existing_db_path: 現有資料庫路徑
        
    返回：
        配置好的併發安全服務實例
    """
    service = ConcurrentActivityMeterService(existing_db_path)
    
    logger.info("併發安全的 ActivityMeter 服務已整合到現有系統")
    return service


def test_upsert_performance(db_path: str, num_operations: int = 1000) -> Dict[str, Any]:
    """
    測試 UPSERT 性能的工具函數
    
    參數：
        db_path: 資料庫路徑
        num_operations: 操作數量
        
    返回：
        性能統計結果
    """
    import time
    import random
    
    service = ConcurrentActivityMeterService(db_path)
    
    start_time = time.time()
    success_count = 0
    error_count = 0
    
    for i in range(num_operations):
        try:
            result = service.upsert_activity_score(
                guild_id=random.randint(1, 10),
                user_id=random.randint(1, 1000),
                score_delta=random.uniform(0.1, 2.0),
                last_msg_time=int(time.time())
            )
            
            if result['success']:
                success_count += 1
            else:
                error_count += 1
        
        except Exception as e:
            error_count += 1
            if i < 10:  # 只記錄前10個錯誤
                logger.warning(f"性能測試操作失敗：{e}")
    
    end_time = time.time()
    duration = end_time - start_time
    
    service.close()
    
    return {
        'total_operations': num_operations,
        'success_count': success_count,
        'error_count': error_count,
        'duration_seconds': duration,
        'operations_per_second': num_operations / duration if duration > 0 else 0,
        'success_rate': success_count / num_operations if num_operations > 0 else 0
    }