"""
反垃圾訊息保護模組資料庫操作
- 封裝所有資料庫相關操作
- 提供統一的資料存取介面
- 支援異步操作和錯誤處理
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from ...base import ProtectionCog

logger = logging.getLogger("anti_spam")

class AntiSpamDatabase:
    """
    反垃圾訊息保護模組資料庫操作類
    
    功能：
    - 配置管理
    - 統計資料記錄
    - 操作日誌記錄
    - 資料查詢和更新
    """
    
    def __init__(self, protection_cog: ProtectionCog):
        """
        初始化資料庫操作類
        
        Args:
            protection_cog: 保護模組基礎類實例
        """
        self.cog = protection_cog
        self.module_name = "anti_spam"
    
    async def init_db(self):
        """初始化資料庫表格"""
        try:
            # 確保保護配置表存在
            await self.cog._ensure_table()
            
            # 創建統計資料表
            await self._create_stats_table()
            
            # 創建操作日誌表
            await self._create_action_log_table()
            
            logger.info("【反垃圾訊息】資料庫初始化完成")
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】資料庫初始化失敗: {exc}")
            raise
    
    async def _create_stats_table(self):
        """創建統計資料表"""
        sql = """
        CREATE TABLE IF NOT EXISTS anti_spam_stats(
            guild_id INTEGER,
            stat_type TEXT,
            count INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, stat_type)
        );"""
        database = getattr(self.cog.bot, 'database', None)
        if database:
            await database.execute(sql)
    
    async def _create_action_log_table(self):
        """創建操作日誌表"""
        sql = """
        CREATE TABLE IF NOT EXISTS anti_spam_action_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
        database = getattr(self.cog.bot, 'database', None)
        if database:
            await database.execute(sql)
    
    # ───────── 配置管理 ─────────
    async def get_config(self, guild_id: int, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        取得配置值
        
        Args:
            guild_id: 伺服器ID
            key: 配置鍵名
            default: 預設值
            
        Returns:
            Optional[str]: 配置值
        """
        return await self.cog.get_cfg(guild_id, key, default)
    
    async def set_config(self, guild_id: int, key: str, value: str):
        """
        設定配置值
        
        Args:
            guild_id: 伺服器ID
            key: 配置鍵名
            value: 配置值
        """
        await self.cog.set_cfg(guild_id, key, value)
    
    async def get_all_configs(self, guild_id: int) -> Dict[str, str]:
        """
        取得所有配置
        
        Args:
            guild_id: 伺服器ID
            
        Returns:
            Dict[str, str]: 所有配置
        """
        try:
            database = getattr(self.cog.bot, 'database', None)
            if not database:
                return {}
            
            rows = await database.fetchall(
                "SELECT key, value FROM protection_config WHERE guild_id=? AND module=?",
                (guild_id, self.module_name)
            )
            
            return {row["key"]: row["value"] for row in rows}
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】取得配置失敗: {exc}")
            return {}
    
    async def reset_all_configs(self, guild_id: int):
        """
        重置所有配置為預設值
        
        Args:
            guild_id: 伺服器ID
        """
        try:
            database = getattr(self.cog.bot, 'database', None)
            if not database:
                return
            
            await database.execute(
                "DELETE FROM protection_config WHERE guild_id=? AND module=?",
                (guild_id, self.module_name)
            )
            
            # 清除快取
            if guild_id in self.cog._cache:
                del self.cog._cache[guild_id]
            
            logger.info(f"【反垃圾訊息】已重置伺服器 {guild_id} 的所有配置")
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】重置配置失敗: {exc}")
            raise
    
    # ───────── 統計資料 ─────────
    async def add_stat(self, guild_id: int, stat_type: str):
        """
        增加統計計數
        
        Args:
            guild_id: 伺服器ID
            stat_type: 統計類型
        """
        try:
            database = getattr(self.cog.bot, 'database', None)
            if not database:
                return
            
            await database.execute(
                """
                INSERT OR REPLACE INTO anti_spam_stats (guild_id, stat_type, count, last_updated)
                VALUES (?, ?, COALESCE((SELECT count FROM anti_spam_stats WHERE guild_id=? AND stat_type=?), 0) + 1, CURRENT_TIMESTAMP)
                """,
                (guild_id, stat_type, guild_id, stat_type)
            )
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】增加統計失敗: {exc}")
    
    async def get_stats(self, guild_id: int) -> Dict[str, int]:
        """
        取得統計資料
        
        Args:
            guild_id: 伺服器ID
            
        Returns:
            Dict[str, int]: 統計資料
        """
        try:
            database = getattr(self.cog.bot, 'database', None)
            if not database:
                return {}
            
            rows = await database.fetchall(
                "SELECT stat_type, count FROM anti_spam_stats WHERE guild_id=?",
                (guild_id,)
            )
            
            return {row["stat_type"]: row["count"] for row in rows}
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】取得統計失敗: {exc}")
            return {}
    
    async def reset_stats(self, guild_id: int):
        """
        重置統計資料
        
        Args:
            guild_id: 伺服器ID
        """
        try:
            database = getattr(self.cog.bot, 'database', None)
            if not database:
                return
            
            await database.execute(
                "DELETE FROM anti_spam_stats WHERE guild_id=?",
                (guild_id,)
            )
            
            logger.info(f"【反垃圾訊息】已重置伺服器 {guild_id} 的統計資料")
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】重置統計失敗: {exc}")
            raise
    
    # ───────── 操作日誌 ─────────
    async def add_action_log(self, guild_id: int, user_id: int, action: str, details: str):
        """
        添加操作日誌
        
        Args:
            guild_id: 伺服器ID
            user_id: 用戶ID
            action: 操作類型
            details: 詳細資訊
        """
        try:
            database = getattr(self.cog.bot, 'database', None)
            if not database:
                return
            
            await database.execute(
                "INSERT INTO anti_spam_action_log (guild_id, user_id, action, details) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, action, details)
            )
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】添加操作日誌失敗: {exc}")
    
    async def get_action_logs(self, guild_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        取得操作日誌
        
        Args:
            guild_id: 伺服器ID
            limit: 限制數量
            
        Returns:
            List[Dict[str, Any]]: 操作日誌列表
        """
        try:
            database = getattr(self.cog.bot, 'database', None)
            if not database:
                return []
            
            rows = await database.fetchall(
                "SELECT * FROM anti_spam_action_log WHERE guild_id=? ORDER BY timestamp DESC LIMIT ?",
                (guild_id, limit)
            )
            
            return [dict(row) for row in rows]
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】取得操作日誌失敗: {exc}")
            return []
    
    async def cleanup_old_logs(self, guild_id: int, days: int = 30):
        """
        清理舊日誌
        
        Args:
            guild_id: 伺服器ID
            days: 保留天數
        """
        try:
            database = getattr(self.cog.bot, 'database', None)
            if not database:
                return
            
            await database.execute(
                "DELETE FROM anti_spam_action_log WHERE guild_id=? AND timestamp < datetime('now', '-{} days')".format(days),
                (guild_id,)
            )
            
        except Exception as exc:
            logger.error(f"【反垃圾訊息】清理舊日誌失敗: {exc}")
    
    # ───────── 配置變更日誌 ─────────
    async def log_config_change(self, guild_id: int, user_id: int, key: str, old_value: str, new_value: str):
        """
        記錄配置變更
        
        Args:
            guild_id: 伺服器ID
            user_id: 用戶ID
            key: 配置鍵名
            old_value: 舊值
            new_value: 新值
        """
        details = f"配置項 '{key}' 從 '{old_value}' 變更為 '{new_value}'"
        await self.add_action_log(guild_id, user_id, "配置變更", details) 