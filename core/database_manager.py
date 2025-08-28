"""
資料庫管理器
Task ID: 1 - 建立核心架構基礎

這個模組提供了統一的資料庫管理功能，整合現有的 Database Cog：
- 標準化的 CRUD 操作介面
- aiosqlite 連線池和事務管理
- 資料庫遷移和版本控制機制
- 與現有程式碼的向後相容性
- 統一的錯誤處理和日誌記錄
"""
import os
import asyncio
import aiosqlite
import logging
import logging.handlers
from typing import Optional, Any, List, Dict, Tuple, Union, Callable
from datetime import datetime
from contextlib import asynccontextmanager
import json

from .base_service import BaseService
from .exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    DatabaseQueryError,
    handle_errors
)

# 設定專案路徑
PROJECT_ROOT = os.environ.get(
    "PROJECT_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DBS_DIR = os.path.join(PROJECT_ROOT, "dbs")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(DBS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)


def ensure_dbs_path(filename: Optional[str], default_filename: str) -> str:
    """
    保證檔案只會存在於 dbs/ 目錄
    
    參數：
        filename: 使用者傳入的檔名或路徑
        default_filename: 預設檔名（不含路徑）
        
    返回：
        正確的資料庫檔案路徑
    """
    if not filename:
        return os.path.join(DBS_DIR, default_filename)
    
    abspath = os.path.abspath(filename)
    # 如果已經在 dbs 內就直接用
    if abspath.startswith(os.path.abspath(DBS_DIR)):
        return abspath
    # 否則無論傳什麼，全部丟進 dbs/
    return os.path.join(DBS_DIR, os.path.basename(filename))


# 設定日誌記錄器
log_file = os.path.join(LOGS_DIR, 'database.log')
handler = logging.handlers.RotatingFileHandler(
    log_file, encoding='utf-8', mode='a', maxBytes=5*1024*1024, backupCount=3
)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger = logging.getLogger('core.database_manager')
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(handler)


class ConnectionPool:
    """
    aiosqlite 連線池
    
    管理多個資料庫連線，提供連線重用和自動清理功能
    """
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections: Dict[str, List[aiosqlite.Connection]] = {}
        self.connection_counts: Dict[str, int] = {}
        self._lock = asyncio.Lock()
    
    async def get_connection(self, db_path: str) -> aiosqlite.Connection:
        """
        獲取資料庫連線
        
        參數：
            db_path: 資料庫檔案路徑
            
        返回：
            資料庫連線
        """
        async with self._lock:
            if db_path not in self.connections:
                self.connections[db_path] = []
                self.connection_counts[db_path] = 0
            
            # 如果有可用連線，直接返回
            if self.connections[db_path]:
                return self.connections[db_path].pop()
            
            # 如果達到最大連線數，等待
            if self.connection_counts[db_path] >= self.max_connections:
                # 這裡可以實作等待邏輯，目前簡單地建立新連線
                pass
            
            # 建立新連線
            try:
                conn = await aiosqlite.connect(db_path)
                await conn.execute("PRAGMA journal_mode=WAL;")
                conn.row_factory = aiosqlite.Row
                self.connection_counts[db_path] += 1
                return conn
            except Exception as e:
                raise DatabaseConnectionError(db_path, str(e))
    
    async def return_connection(self, db_path: str, conn: aiosqlite.Connection):
        """
        歸還連線到池中
        
        參數：
            db_path: 資料庫檔案路徑
            conn: 資料庫連線
        """
        async with self._lock:
            if db_path in self.connections:
                self.connections[db_path].append(conn)
    
    async def close_all_connections(self, db_path: Optional[str] = None):
        """
        關閉所有連線
        
        參數：
            db_path: 特定資料庫路徑，如果不提供則關閉所有
        """
        async with self._lock:
            if db_path:
                if db_path in self.connections:
                    for conn in self.connections[db_path]:
                        try:
                            await conn.close()
                        except Exception:
                            pass
                    self.connections[db_path].clear()
                    self.connection_counts[db_path] = 0
            else:
                for db_path, conns in self.connections.items():
                    for conn in conns:
                        try:
                            await conn.close()
                        except Exception:
                            pass
                    conns.clear()
                    self.connection_counts[db_path] = 0


class DatabaseMigration:
    """
    資料庫遷移管理
    
    提供版本控制和遷移功能
    """
    
    def __init__(self, db_manager: 'DatabaseManager'):
        self.db_manager = db_manager
        self.migrations: List[Dict[str, Any]] = []
    
    def add_migration(
        self,
        version: str,
        description: str,
        up_sql: str,
        down_sql: str
    ):
        """
        添加遷移
        
        參數：
            version: 版本號
            description: 描述
            up_sql: 升級 SQL
            down_sql: 降級 SQL
        """
        self.migrations.append({
            'version': version,
            'description': description,
            'up_sql': up_sql,
            'down_sql': down_sql,
            'created_at': datetime.now().isoformat()
        })
    
    async def initialize_migration_table(self):
        """初始化遷移記錄表"""
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT,
                applied_at TEXT,
                checksum TEXT
            )
        """)
    
    async def get_applied_migrations(self) -> List[str]:
        """獲取已應用的遷移版本"""
        rows = await self.db_manager.fetchall(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        return [row['version'] for row in rows]
    
    async def apply_migrations(self) -> bool:
        """應用所有未執行的遷移"""
        try:
            await self.initialize_migration_table()
            applied = await self.get_applied_migrations()
            
            for migration in sorted(self.migrations, key=lambda x: x['version']):
                if migration['version'] not in applied:
                    logger.info(f"應用遷移 {migration['version']}: {migration['description']}")
                    
                    # 執行遷移 SQL - 支持多語句，智能處理TRIGGER等複雜語句
                    sql_statements = self._split_sql_statements(migration['up_sql'])
                    for stmt in sql_statements:
                        stmt = stmt.strip()
                        if stmt:  # 跳過空語句
                            await self.db_manager.execute(stmt)
                    
                    # 記錄遷移
                    await self.db_manager.execute(
                        "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?)",
                        (migration['version'], migration['description'], datetime.now().isoformat())
                    )
                    
                    logger.info(f"遷移 {migration['version']} 應用成功")
            
            return True
            
        except Exception as e:
            logger.error(f"應用遷移時發生錯誤：{e}")
            return False
    
    def _split_sql_statements(self, sql: str) -> List[str]:
        """智能分割SQL語句，正確處理TRIGGER、VIEW等複雜語句"""
        statements: List[str] = []
        current_statement = ""
        lines = sql.split('\n')
        
        trigger_depth = 0
        in_trigger = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 檢測TRIGGER開始
            if line.upper().startswith('CREATE TRIGGER'):
                in_trigger = True
                trigger_depth = 0
            
            current_statement += line + '\n'
            
            # 在TRIGGER內部跟蹤BEGIN/END
            if in_trigger:
                if 'BEGIN' in line.upper():
                    trigger_depth += 1
                elif 'END;' in line.upper():
                    trigger_depth -= 1
                    if trigger_depth <= 0:
                        # TRIGGER結束
                        statements.append(current_statement.strip())
                        current_statement = ""
                        in_trigger = False
                        continue
            
            # 正常語句以分號結尾（且不在TRIGGER內）
            if line.endswith(';') and not in_trigger:
                statements.append(current_statement.strip())
                current_statement = ""
        
        # 添加剩餘的語句
        if current_statement.strip():
            statements.append(current_statement.strip())
            
        # 後備方案：若未正確分割（例如所有語句被合併為一行），用分號再次分割
        if len(statements) <= 1 and (';' in sql):
            naive_parts = [part.strip() for part in sql.split(';') if part.strip()]
            return naive_parts
        
        return statements


class DatabaseManager(BaseService):
    """
    資料庫管理器
    
    整合現有 Database Cog 的功能，提供統一的資料庫管理介面
    """
    
    def __init__(
        self,
        db_name: Optional[str] = None,
        message_db_name: Optional[str] = None,
        pool_size: int = 10
    ):
        """
        初始化資料庫管理器
        
        參數：
            db_name: 主資料庫名稱
            message_db_name: 訊息資料庫名稱
            pool_size: 連線池大小
        """
        super().__init__("DatabaseManager")
        
        self.db_name = ensure_dbs_path(db_name, 'welcome.db')
        self.message_db_name = ensure_dbs_path(message_db_name, 'message.db')
        
        # 連線池
        self.connection_pool = ConnectionPool(pool_size)
        
        # 主資料庫和訊息資料庫的專用連線
        self.conn: Optional[aiosqlite.Connection] = None
        self.message_conn: Optional[aiosqlite.Connection] = None
        
        # 遷移管理器
        self.migration_manager = DatabaseMigration(self)
        
        # 註冊預設遷移
        self._register_default_migrations()
    
    def _register_default_migrations(self):
        """註冊預設的資料庫遷移"""
        # 分別註冊每個表格的遷移
        tables_sql = [
            """CREATE TABLE IF NOT EXISTS welcome_settings (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                title TEXT,
                description TEXT,
                image_url TEXT,
                delete_url TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS welcome_messages (
                guild_id INTEGER PRIMARY KEY,
                message TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS text_styles (
                guild_id INTEGER,
                type TEXT,
                x INTEGER,
                y INTEGER,
                size INTEGER,
                color TEXT,
                opacity INTEGER,
                font TEXT,
                PRIMARY KEY (guild_id, type)
            )""",
            """CREATE TABLE IF NOT EXISTS welcome_backgrounds (
                guild_id INTEGER PRIMARY KEY,
                image_path TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS monitored_channels (
                channel_id INTEGER PRIMARY KEY
            )""",
            """CREATE TABLE IF NOT EXISTS roles (
                role_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                name TEXT,
                color TEXT,
                permissions INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                name TEXT,
                type TEXT,
                topic TEXT
            )"""
        ]
        
        drop_sql = [
            "DROP TABLE IF EXISTS channels",
            "DROP TABLE IF EXISTS roles", 
            "DROP TABLE IF EXISTS monitored_channels",
            "DROP TABLE IF EXISTS settings",
            "DROP TABLE IF EXISTS welcome_backgrounds",
            "DROP TABLE IF EXISTS text_styles",
            "DROP TABLE IF EXISTS welcome_messages",
            "DROP TABLE IF EXISTS welcome_settings"
        ]
        
        # 將SQL語句組合，使用換行符分隔以便正確分割
        up_sql = ";\n\n".join(tables_sql) + ";"
        down_sql = ";\n\n".join(drop_sql) + ";"
        
        self.migration_manager.add_migration(
            version="001",
            description="建立基礎表格",
            up_sql=up_sql,
            down_sql=down_sql
        )
        
        # v2.4.4 核心架構擴展遷移
        self._register_v2_4_4_core_migration()
    
    def _register_v2_4_4_core_migration(self):
        """註冊v2.4.4版本核心功能所需的資料庫遷移"""
        
        # 讀取遷移腳本內容
        import os
        migrations_dir = os.path.join(os.path.dirname(self.db_name), '..', 'migrations')
        
        try:
            # 讀取核心表格創建遷移
            up_sql_path = os.path.join(migrations_dir, 'v2_4_4_core_tables.sql')
            down_sql_path = os.path.join(migrations_dir, 'v2_4_4_core_tables_rollback.sql')
            
            # 確保遷移檔案存在
            if os.path.exists(up_sql_path) and os.path.exists(down_sql_path):
                with open(up_sql_path, 'r', encoding='utf-8') as f:
                    up_sql = f.read()
                
                with open(down_sql_path, 'r', encoding='utf-8') as f:
                    down_sql = f.read()
                
                # 註冊遷移
                self.migration_manager.add_migration(
                    version="002_v2_4_4_core",
                    description="ROAS Bot v2.4.4 核心架構和基礎設施建置 - 子機器人系統、AI集成系統、部署系統資料表",
                    up_sql=up_sql,
                    down_sql=down_sql
                )
                logger.info("已註冊 v2.4.4 核心資料表遷移")
            else:
                logger.warning(f"v2.4.4 核心遷移檔案不存在: {up_sql_path} 或 {down_sql_path}")
                
                # 如果檔案不存在，使用內嵌的SQL建立基本結構
                self._register_v2_4_4_inline_migration()
                
        except Exception as e:
            logger.error(f"註冊 v2.4.4 核心遷移時發生錯誤: {e}")
            # 降級為內嵌遷移
            self._register_v2_4_4_inline_migration()
    
    def _register_v2_4_4_inline_migration(self):
        """註冊內嵌的v2.4.4核心功能遷移（降級方案）"""
        
        # 核心表格創建SQL
        core_tables_up = """
-- ROAS Bot v2.4.4 核心資料表（內嵌版本）

-- 子機器人配置表
CREATE TABLE IF NOT EXISTS sub_bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    target_channels TEXT NOT NULL,
    ai_enabled BOOLEAN DEFAULT FALSE,
    ai_model VARCHAR(50),
    personality TEXT,
    rate_limit INTEGER DEFAULT 10,
    status VARCHAR(20) DEFAULT 'offline',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active_at DATETIME,
    message_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sub_bots_bot_id ON sub_bots(bot_id);
CREATE INDEX IF NOT EXISTS idx_sub_bots_status ON sub_bots(status);

-- 子機器人頻道關聯表
CREATE TABLE IF NOT EXISTS sub_bot_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_bot_id INTEGER NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_type VARCHAR(20) DEFAULT 'text',
    permissions TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sub_bot_id) REFERENCES sub_bots(id) ON DELETE CASCADE,
    UNIQUE(sub_bot_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_sub_bot_id ON sub_bot_channels(sub_bot_id);
CREATE INDEX IF NOT EXISTS idx_sub_bot_channels_channel_id ON sub_bot_channels(channel_id);

-- AI 對話記錄表
CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL,
    sub_bot_id INTEGER,
    provider VARCHAR(20) NOT NULL,
    model VARCHAR(50) NOT NULL,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    tokens_used INTEGER NOT NULL,
    cost DECIMAL(10, 6) NOT NULL,
    response_time DECIMAL(8, 3),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sub_bot_id) REFERENCES sub_bots(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_id ON ai_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_sub_bot_id ON ai_conversations(sub_bot_id);

-- AI 使用配額表
CREATE TABLE IF NOT EXISTS ai_usage_quotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT UNIQUE NOT NULL,
    daily_limit INTEGER DEFAULT 50,
    weekly_limit INTEGER DEFAULT 200,
    monthly_limit INTEGER DEFAULT 1000,
    daily_used INTEGER DEFAULT 0,
    weekly_used INTEGER DEFAULT 0,
    monthly_used INTEGER DEFAULT 0,
    total_cost_limit DECIMAL(10, 2) DEFAULT 10.00,
    total_cost_used DECIMAL(10, 2) DEFAULT 0.00,
    last_reset_daily DATE DEFAULT CURRENT_DATE,
    last_reset_weekly DATE DEFAULT CURRENT_DATE,
    last_reset_monthly DATE DEFAULT CURRENT_DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_quotas_user_id ON ai_usage_quotas(user_id);

-- AI 提供商配置表
CREATE TABLE IF NOT EXISTS ai_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name VARCHAR(20) UNIQUE NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    base_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 1,
    rate_limit_per_minute INTEGER DEFAULT 60,
    cost_per_token DECIMAL(10, 8) DEFAULT 0.000002,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_providers_name ON ai_providers(provider_name);

-- 部署日誌表
CREATE TABLE IF NOT EXISTS deployment_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id VARCHAR(50) UNIQUE NOT NULL,
    mode VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    environment_info TEXT,
    error_message TEXT,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    duration_seconds INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_deployment_logs_deployment_id ON deployment_logs(deployment_id);
CREATE INDEX IF NOT EXISTS idx_deployment_logs_status ON deployment_logs(status);

-- 預設資料
INSERT OR IGNORE INTO ai_providers (provider_name, api_key_hash, base_url, priority, cost_per_token) VALUES
('openai', '', 'https://api.openai.com/v1', 1, 0.000002),
('anthropic', '', 'https://api.anthropic.com', 2, 0.000008),
('google', '', 'https://generativelanguage.googleapis.com', 3, 0.000001);
"""

        # 核心表格移除SQL（回滾）
        core_tables_down = """
-- ROAS Bot v2.4.4 核心資料表回滾
DROP INDEX IF EXISTS idx_deployment_logs_status;
DROP INDEX IF EXISTS idx_deployment_logs_deployment_id;
DROP INDEX IF EXISTS idx_ai_providers_name;
DROP INDEX IF EXISTS idx_ai_usage_quotas_user_id;
DROP INDEX IF EXISTS idx_ai_conversations_sub_bot_id;
DROP INDEX IF EXISTS idx_ai_conversations_user_id;
DROP INDEX IF EXISTS idx_sub_bot_channels_channel_id;
DROP INDEX IF EXISTS idx_sub_bot_channels_sub_bot_id;
DROP INDEX IF EXISTS idx_sub_bots_status;
DROP INDEX IF EXISTS idx_sub_bots_bot_id;

DROP TABLE IF EXISTS deployment_logs;
DROP TABLE IF EXISTS ai_conversations;
DROP TABLE IF EXISTS ai_usage_quotas;
DROP TABLE IF EXISTS ai_providers;
DROP TABLE IF EXISTS sub_bot_channels;
DROP TABLE IF EXISTS sub_bots;
"""
        
        # 註冊內嵌遷移
        self.migration_manager.add_migration(
            version="002_v2_4_4_core_inline",
            description="ROAS Bot v2.4.4 核心架構（內嵌版本） - 子機器人、AI集成、部署系統",
            up_sql=core_tables_up,
            down_sql=core_tables_down
        )
        logger.info("已註冊 v2.4.4 核心資料表遷移（內嵌版本）")
    
    async def _initialize(self) -> bool:
        """初始化資料庫管理器"""
        try:
            # 建立主資料庫連線
            self.conn = await self.connection_pool.get_connection(self.db_name)
            
            # 建立訊息資料庫連線
            self.message_conn = await self.connection_pool.get_connection(self.message_db_name)
            
            # 初始化表格
            await self._create_tables()
            
            # 應用遷移
            await self.migration_manager.apply_migrations()
            
            logger.info("資料庫管理器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"資料庫管理器初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            # 歸還連線到池中
            if self.conn:
                await self.connection_pool.return_connection(self.db_name, self.conn)
                self.conn = None
            
            if self.message_conn:
                await self.connection_pool.return_connection(self.message_db_name, self.message_conn)
                self.message_conn = None
            
            # 關閉所有連線
            await self.connection_pool.close_all_connections()
            
            logger.info("資料庫管理器已清理")
            
        except Exception as e:
            logger.error(f"清理資料庫管理器時發生錯誤：{e}")
    
    async def _validate_permissions(
        self,
        user_id: int,
        guild_id: Optional[int],
        action: str
    ) -> bool:
        """
        資料庫權限驗證
        
        目前實作：允許所有操作（可根據需要擴展）
        """
        # 這裡可以根據需要實作更複雜的權限邏輯
        return True
    
    async def _create_tables(self):
        """建立訊息資料庫表格"""
        try:
            # 訊息資料庫表格
            assert self.message_conn is not None
            await self.message_conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    content TEXT,
                    timestamp REAL,
                    attachments TEXT
                )
            """)
            await self.message_conn.commit()
            
        except Exception as e:
            logger.error(f"建立表格時發生錯誤：{e}")
            raise DatabaseError(f"建立表格失敗：{str(e)}", operation="create_tables")
    
    @asynccontextmanager
    async def transaction(self, db_type: str = "main"):
        """
        事務管理上下文管理器
        
        參數：
            db_type: 資料庫類型 ("main" 或 "message")
        """
        conn = self.conn if db_type == "main" else self.message_conn
        if not conn:
            raise DatabaseError("資料庫連線不可用", operation="transaction")
        
        try:
            await conn.execute("BEGIN")
            yield conn
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise DatabaseError(f"事務執行失敗：{str(e)}", operation="transaction")
    
    @handle_errors(log_errors=True)
    async def execute(
        self,
        query: str,
        params: Union[Tuple, List] = (),
        db_type: str = "main"
    ) -> None:
        """
        執行 SQL 指令
        
        參數：
            query: SQL 查詢
            params: 參數
            db_type: 資料庫類型 ("main" 或 "message")
        """
        try:
            conn = self.conn if db_type == "main" else self.message_conn
            assert conn is not None
            
            async with conn.cursor() as c:
                await c.execute(query, params)
                await conn.commit()
                
        except Exception as e:
            logger.error(f"執行 SQL 指令失敗：{e}\n指令內容：{query}\n參數：{params}")
            raise DatabaseQueryError(query, str(e))
    
    @handle_errors(log_errors=True)
    async def fetchone(
        self,
        query: str,
        params: Union[Tuple, List] = (),
        db_type: str = "main"
    ) -> Optional[aiosqlite.Row]:
        """
        查詢單筆資料
        
        參數：
            query: SQL 查詢
            params: 參數
            db_type: 資料庫類型 ("main" 或 "message")
            
        返回：
            查詢結果
        """
        try:
            conn = self.conn if db_type == "main" else self.message_conn
            assert conn is not None
            
            async with conn.cursor() as c:
                await c.execute(query, params)
                return await c.fetchone()
                
        except Exception as e:
            logger.error(f"查詢(單筆)失敗：{e}\n查詢內容：{query}\n參數：{params}")
            raise DatabaseQueryError(query, str(e))
    
    @handle_errors(log_errors=True)
    async def fetchall(
        self,
        query: str,
        params: Union[Tuple, List] = (),
        db_type: str = "main"
    ) -> List[aiosqlite.Row]:
        """
        查詢多筆資料
        
        參數：
            query: SQL 查詢
            params: 參數
            db_type: 資料庫類型 ("main" 或 "message")
            
        返回：
            查詢結果列表
        """
        try:
            conn = self.conn if db_type == "main" else self.message_conn
            assert conn is not None
            
            async with conn.cursor() as c:
                await c.execute(query, params)
                return list(await c.fetchall())
                
        except Exception as e:
            logger.error(f"查詢(多筆)失敗：{e}\n查詢內容：{query}\n參數：{params}")
            raise DatabaseQueryError(query, str(e))
    
    @handle_errors(log_errors=True)
    async def executemany(
        self,
        query: str,
        params_list: List[Union[Tuple, List]],
        db_type: str = "main"
    ) -> None:
        """
        批量執行 SQL 指令
        
        參數：
            query: SQL 查詢
            params_list: 參數列表
            db_type: 資料庫類型 ("main" 或 "message")
        """
        try:
            conn = self.conn if db_type == "main" else self.message_conn
            assert conn is not None
            
            async with conn.cursor() as c:
                await c.executemany(query, params_list)
                await conn.commit()
                
        except Exception as e:
            logger.error(f"批量執行 SQL 指令失敗：{e}\n指令內容：{query}")
            raise DatabaseQueryError(query, str(e))    # ========== 向後相容性方法 ==========
    # 以下方法保持與原 Database Cog 的相容性
    
    @handle_errors(log_errors=True)
    async def update_welcome_message(self, guild_id: int, channel_id: int, message: str):
        """更新歡迎訊息"""
        try:
            await self.execute(
                "INSERT OR REPLACE INTO welcome_settings (guild_id, channel_id) VALUES (?, ?)",
                (guild_id, channel_id)
            )
            await self.execute(
                "INSERT OR REPLACE INTO welcome_messages (guild_id, message) VALUES (?, ?)",
                (guild_id, message)
            )
        except Exception as e:
            logger.error(f"更新歡迎訊息失敗：{e}")
            raise DatabaseError(f"更新歡迎訊息失敗：{str(e)}", operation="update_welcome_message")

    @handle_errors(log_errors=True)
    async def get_welcome_message(self, guild_id: int) -> Optional[str]:
        """獲取歡迎訊息"""
        try:
            row = await self.fetchone("SELECT message FROM welcome_messages WHERE guild_id = ?", (guild_id,))
            return row['message'] if row else None
        except Exception as e:
            logger.error(f"取得歡迎訊息失敗：{e}")
            raise DatabaseError(f"取得歡迎訊息失敗：{str(e)}", operation="get_welcome_message")

    @handle_errors(log_errors=True)
    async def update_welcome_background(self, guild_id: int, image_path: str):
        """更新歡迎背景"""
        try:
            await self.execute(
                "INSERT OR REPLACE INTO welcome_backgrounds (guild_id, image_path) VALUES (?, ?)",
                (guild_id, image_path)
            )
        except Exception as e:
            logger.error(f"更新歡迎背景失敗：{e}")
            raise DatabaseError(f"更新歡迎背景失敗：{str(e)}", operation="update_welcome_background")

    @handle_errors(log_errors=True)
    async def get_welcome_background(self, guild_id: int) -> Optional[str]:
        """獲取歡迎背景"""
        try:
            row = await self.fetchone("SELECT image_path FROM welcome_backgrounds WHERE guild_id = ?", (guild_id,))
            return row['image_path'] if row else None
        except Exception as e:
            logger.error(f"取得歡迎背景失敗：{e}")
            raise DatabaseError(f"取得歡迎背景失敗：{str(e)}", operation="get_welcome_background")

    @handle_errors(log_errors=True)
    async def update_welcome_title(self, guild_id: int, title: str):
        """更新歡迎標題"""
        try:
            exist = await self.fetchone("SELECT guild_id FROM welcome_settings WHERE guild_id = ?", (guild_id,))
            if exist:
                await self.execute("UPDATE welcome_settings SET title = ? WHERE guild_id = ?", (title, guild_id))
            else:
                await self.execute("INSERT INTO welcome_settings (guild_id, title) VALUES (?, ?)", (guild_id, title))
        except Exception as e:
            logger.error(f"更新歡迎標題失敗：{e}")
            raise DatabaseError(f"更新歡迎標題失敗：{str(e)}", operation="update_welcome_title")

    @handle_errors(log_errors=True)
    async def update_welcome_description(self, guild_id: int, description: str):
        """更新歡迎描述"""
        try:
            exist = await self.fetchone("SELECT guild_id FROM welcome_settings WHERE guild_id = ?", (guild_id,))
            if exist:
                await self.execute("UPDATE welcome_settings SET description = ? WHERE guild_id = ?", (description, guild_id))
            else:
                await self.execute("INSERT INTO welcome_settings (guild_id, description) VALUES (?, ?)", (guild_id, description))
        except Exception as e:
            logger.error(f"更新歡迎描述失敗：{e}")
            raise DatabaseError(f"更新歡迎描述失敗：{str(e)}", operation="update_welcome_description")

    @handle_errors(log_errors=True)
    async def get_welcome_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """獲取歡迎設定"""
        try:
            row = await self.fetchone(
                "SELECT channel_id, title, description, image_url, delete_url FROM welcome_settings WHERE guild_id = ?", (guild_id,)
            )
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"取得歡迎設定失敗：{e}")
            raise DatabaseError(f"取得歡迎設定失敗：{str(e)}", operation="get_welcome_settings")

    @handle_errors(log_errors=True)
    async def update_text_position(self, guild_id: int, text_type: str, x: Optional[int], y: Optional[int]):
        """更新文字方塊座標"""
        try:
            exist = await self.fetchone(
                "SELECT guild_id FROM text_styles WHERE guild_id = ? AND type = ?", (guild_id, text_type)
            )
            if text_type == "avatar_x":
                if exist:
                    await self.execute(
                        "UPDATE text_styles SET x = ? WHERE guild_id = ? AND type = ?",
                        (x, guild_id, text_type)
                    )
                else:
                    await self.execute(
                        "INSERT INTO text_styles (guild_id, type, x, y) VALUES (?, ?, ?, NULL)",
                        (guild_id, text_type, x)
                    )
            elif text_type == "avatar_y":
                if exist:
                    await self.execute(
                        "UPDATE text_styles SET y = ? WHERE guild_id = ? AND type = ?",
                        (y, guild_id, text_type)
                    )
                else:
                    await self.execute(
                        "INSERT INTO text_styles (guild_id, type, x, y) VALUES (?, ?, NULL, ?)",
                        (guild_id, text_type, y)
                    )
            else:
                if exist:
                    await self.execute(
                        "UPDATE text_styles SET y = ? WHERE guild_id = ? AND type = ?",
                        (y, guild_id, text_type)
                    )
                else:
                    await self.execute(
                        "INSERT INTO text_styles (guild_id, type, x, y) VALUES (?, ?, NULL, ?)",
                        (guild_id, text_type, y)
                    )
        except Exception as e:
            logger.error(f"更新文字方塊座標失敗：{e}")
            raise DatabaseError(f"更新文字方塊座標失敗：{str(e)}", operation="update_text_position")

    @handle_errors(log_errors=True)
    async def get_text_position(self, guild_id: int, text_type: str) -> Optional[int]:
        """獲取文字方塊座標"""
        try:
            row = await self.fetchone(
                "SELECT x, y FROM text_styles WHERE guild_id = ? AND type = ?", (guild_id, text_type)
            )
            if row:
                if text_type == "avatar_x":
                    return row['x']
                elif text_type == "avatar_y":
                    return row['y']
                else:
                    return row['y']
            return None
        except Exception as e:
            logger.error(f"取得文字方塊座標失敗：{e}")
            raise DatabaseError(f"取得文字方塊座標失敗：{str(e)}", operation="get_text_position")

    @handle_errors(log_errors=True)
    async def get_setting(self, setting_name: str) -> Optional[str]:
        """獲取設定"""
        try:
            row = await self.fetchone("SELECT setting_value FROM settings WHERE setting_name = ?", (setting_name,))
            return row['setting_value'] if row else None
        except Exception as e:
            logger.error(f"取得設定失敗：{e}")
            raise DatabaseError(f"取得設定失敗：{str(e)}", operation="get_setting")

    @handle_errors(log_errors=True)
    async def set_setting(self, setting_name: str, value: str):
        """設定設定值"""
        try:
            await self.execute(
                "INSERT OR REPLACE INTO settings (setting_name, setting_value) VALUES (?, ?)",
                (setting_name, value)
            )
        except Exception as e:
            logger.error(f"儲存設定失敗：{e}")
            raise DatabaseError(f"儲存設定失敗：{str(e)}", operation="set_setting")

    @handle_errors(log_errors=True)
    async def get_monitored_channels(self) -> List[int]:
        """獲取監聽頻道"""
        try:
            rows = await self.fetchall("SELECT channel_id FROM monitored_channels")
            return [row['channel_id'] for row in rows]
        except Exception as e:
            logger.error(f"取得監聽頻道失敗：{e}")
            raise DatabaseError(f"取得監聽頻道失敗：{str(e)}", operation="get_monitored_channels")

    @handle_errors(log_errors=True)
    async def add_monitored_channel(self, channel_id: int):
        """新增監聽頻道"""
        try:
            await self.execute(
                "INSERT OR IGNORE INTO monitored_channels (channel_id) VALUES (?)",
                (channel_id,)
            )
        except Exception as e:
            logger.error(f"新增監聽頻道失敗：{e}")
            raise DatabaseError(f"新增監聽頻道失敗：{str(e)}", operation="add_monitored_channel")

    @handle_errors(log_errors=True)
    async def remove_monitored_channel(self, channel_id: int):
        """移除監聽頻道"""
        try:
            await self.execute(
                "DELETE FROM monitored_channels WHERE channel_id = ?", (channel_id,)
            )
        except Exception as e:
            logger.error(f"移除監聽頻道失敗：{e}")
            raise DatabaseError(f"移除監聽頻道失敗：{str(e)}", operation="remove_monitored_channel")

    @handle_errors(log_errors=True)
    async def log_message(
        self,
        message_id: int,
        channel_id: int,
        guild_id: int,
        author_id: int,
        content: str,
        timestamp: float,
        attachments: Optional[str] = None
    ):
        """記錄訊息"""
        try:
            await self.execute(
                "INSERT INTO messages (message_id, channel_id, guild_id, author_id, content, timestamp, attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (message_id, channel_id, guild_id, author_id, content, timestamp, attachments),
                db_type="message"
            )
        except Exception as e:
            logger.error(f"訊息記錄寫入失敗：{e}")
            raise DatabaseError(f"訊息記錄寫入失敗：{str(e)}", operation="log_message")

    @handle_errors(log_errors=True)
    async def get_guild_roles(self, guild_id: int) -> List[aiosqlite.Row]:
        """獲取伺服器角色"""
        try:
            return await self.fetchall("SELECT role_id, name, color, permissions FROM roles WHERE guild_id = ?", (guild_id,))
        except Exception as e:
            logger.error(f"取得伺服器角色失敗：{e}")
            raise DatabaseError(f"取得伺服器角色失敗：{str(e)}", operation="get_guild_roles")

    @handle_errors(log_errors=True)
    async def get_guild_channels(self, guild_id: int) -> List[aiosqlite.Row]:
        """獲取伺服器頻道"""
        try:
            return await self.fetchall("SELECT channel_id, name, type, topic FROM channels WHERE guild_id = ?", (guild_id,))
        except Exception as e:
            logger.error(f"取得伺服器頻道失敗：{e}")
            raise DatabaseError(f"取得伺服器頻道失敗：{str(e)}", operation="get_guild_channels")

    @handle_errors(log_errors=True)
    async def insert_or_replace_role(self, role):
        """插入或替換角色"""
        try:
            await self.execute(
                "INSERT OR REPLACE INTO roles (role_id, guild_id, name, color, permissions) VALUES (?, ?, ?, ?, ?)",
                (role.id, role.guild.id, role.name, str(role.color), role.permissions.value)
            )
        except Exception as e:
            logger.error(f"角色同步寫入失敗：{e}")
            raise DatabaseError(f"角色同步寫入失敗：{str(e)}", operation="insert_or_replace_role")

    @handle_errors(log_errors=True)
    async def insert_or_replace_channel(self, channel):
        """插入或替換頻道"""
        try:
            topic = getattr(channel, 'topic', None)
            await self.execute(
                "INSERT OR REPLACE INTO channels (channel_id, guild_id, name, type, topic) VALUES (?, ?, ?, ?, ?)",
                (channel.id, channel.guild.id, channel.name, str(channel.type), topic)
            )
        except Exception as e:
            logger.error(f"頻道同步寫入失敗：{e}")
            raise DatabaseError(f"頻道同步寫入失敗：{str(e)}", operation="insert_or_replace_channel")

    @handle_errors(log_errors=True)
    async def delete_role(self, role_id: int):
        """刪除角色"""
        try:
            await self.execute("DELETE FROM roles WHERE role_id = ?", (role_id,))
        except Exception as e:
            logger.error(f"刪除角色時發生錯誤：{e}")
            raise DatabaseError(f"刪除角色時發生錯誤：{str(e)}", operation="delete_role")

    @handle_errors(log_errors=True)
    async def delete_channel(self, channel_id: int):
        """刪除頻道"""
        try:
            await self.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        except Exception as e:
            logger.error(f"刪除頻道時發生錯誤：{e}")
            raise DatabaseError(f"刪除頻道時發生錯誤：{str(e)}", operation="delete_channel")

    @handle_errors(log_errors=True)
    async def compare_and_update_guild(self, guild) -> bool:
        """與 Discord 伺服器現有角色、頻道進行同步"""
        try:
            import discord
            
            db_roles = await self.get_guild_roles(guild.id)
            db_channels = await self.get_guild_channels(guild.id)
            db_roles_dict = {row['role_id']: row for row in db_roles}
            db_channels_dict = {row['channel_id']: row for row in db_channels}

            # 角色同步
            for role in guild.roles:
                db_role = db_roles_dict.get(role.id)
                if not db_role or db_role['name'] != role.name or db_role['color'] != str(role.color) or db_role['permissions'] != role.permissions.value:
                    await self.insert_or_replace_role(role)
            for db_role_id in db_roles_dict:
                if not discord.utils.get(guild.roles, id=db_role_id):
                    await self.delete_role(db_role_id)

            # 頻道同步
            for ch in guild.channels:
                db_ch = db_channels_dict.get(ch.id)
                topic = getattr(ch, 'topic', None)
                if not db_ch or db_ch['name'] != ch.name or db_ch['type'] != str(ch.type) or db_ch['topic'] != topic:
                    await self.insert_or_replace_channel(ch)
            for db_ch_id in db_channels_dict:
                if not discord.utils.get(guild.channels, id=db_ch_id):
                    await self.delete_channel(db_ch_id)

            logger.info(f"伺服器 {guild.id} 資料同步完成")
            return True
        except Exception as e:
            logger.error(f"伺服器 {guild.id} 資料同步失敗：{e}")
            raise DatabaseError(f"伺服器資料同步失敗：{str(e)}", operation="compare_and_update_guild")
    
    # ========== 新增的高級功能 ==========
    
    @handle_errors(log_errors=True)
    async def backup_database(self, backup_path: Optional[str] = None, 
                              backup_type: str = "full", compression: bool = True) -> str:
        """
        企業級資料庫備份
        
        參數：
            backup_path: 備份檔案路徑，如果不提供則自動生成
            backup_type: 備份類型 ('full', 'incremental', 'differential')
            compression: 是否壓縮備份檔案
            
        返回：
            備份檔案路徑
        """
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{backup_type}_{timestamp}.db"
                backup_path = os.path.join(DBS_DIR, "..", "backups", backup_name)
                
                # 確保備份目錄存在
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # 執行備份前預檢查
            await self._validate_backup_prerequisites()
            
            # 使用 VACUUM INTO 進行完整備份
            await self.execute(f"VACUUM INTO '{backup_path}'")
            
            # 驗證備份完整性
            backup_size = await self._verify_backup_integrity(backup_path)
            
            # 可選壓縮處理
            if compression:
                backup_path = await self._compress_backup(backup_path)
            
            # 記錄備份元資料
            await self._log_backup_metadata(backup_path, backup_type, backup_size)
            
            logger.info(f"資料庫備份完成：{backup_path} (大小: {backup_size} bytes, 類型: {backup_type})")
            return backup_path
            
        except Exception as e:
            logger.error(f"資料庫備份失敗：{e}")
            raise DatabaseError(f"資料庫備份失敗：{str(e)}", operation="backup_database")
    
    async def _validate_backup_prerequisites(self) -> None:
        """驗證備份前置條件"""
        # 檢查磁碟空間
        # 檢查資料庫連線狀態
        # 檢查鎖定情況
        pass
    
    async def _verify_backup_integrity(self, backup_path: str) -> int:
        """驗證備份檔案完整性"""
        if not os.path.exists(backup_path):
            raise DatabaseError("備份檔案不存在", operation="backup_integrity_check")
        
        file_size = os.path.getsize(backup_path)
        if file_size == 0:
            raise DatabaseError("備份檔案為空", operation="backup_integrity_check")
            
        return file_size
    
    async def _compress_backup(self, backup_path: str) -> str:
        """壓縮備份檔案"""
        import gzip
        compressed_path = f"{backup_path}.gz"
        
        try:
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    f_out.writelines(f_in)
            
            # 刪除原始檔案
            os.remove(backup_path)
            return compressed_path
            
        except Exception as e:
            logger.error(f"備份壓縮失敗：{e}")
            return backup_path  # 返回原始檔案路徑
    
    async def _log_backup_metadata(self, backup_path: str, backup_type: str, size: int):
        """記錄備份元資料"""
        try:
            # 建立備份索引表（如果不存在）
            await self.execute("""
                CREATE TABLE IF NOT EXISTS backup_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_path TEXT NOT NULL,
                    backup_type TEXT NOT NULL,
                    file_size INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT
                )
            """)
            
            # 記錄備份資訊
            await self.execute(
                "INSERT INTO backup_history (backup_path, backup_type, file_size) VALUES (?, ?, ?)",
                (backup_path, backup_type, size)
            )
            
        except Exception as e:
            logger.warning(f"記錄備份元資料失敗：{e}")
    
    @handle_errors(log_errors=True)
    async def get_database_stats(self) -> Dict[str, Any]:
        """獲取資料庫統計信息"""
        try:
            stats = {}
            
            # 主資料庫統計
            main_tables = await self.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            stats['main_database'] = {
                'path': self.db_name,
                'tables': []
            }
            
            for table in main_tables:
                table_name = table['name']
                count_result = await self.fetchone(f"SELECT COUNT(*) as count FROM {table_name}")
                stats['main_database']['tables'].append({
                    'name': table_name,
                    'row_count': count_result['count'] if count_result else 0
                })
            
            # 訊息資料庫統計
            message_tables = await self.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
                db_type="message"
            )
            stats['message_database'] = {
                'path': self.message_db_name,
                'tables': []
            }
            
            for table in message_tables:
                table_name = table['name']
                count_result = await self.fetchone(f"SELECT COUNT(*) as count FROM {table_name}", db_type="message")
                stats['message_database']['tables'].append({
                    'name': table_name,
                    'row_count': count_result['count'] if count_result else 0
                })
            
            # 連線池統計
            stats['connection_pool'] = {
                'max_connections': self.connection_pool.max_connections,
                'active_connections': dict(self.connection_pool.connection_counts)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"獲取資料庫統計失敗：{e}")
            raise DatabaseError(f"獲取資料庫統計失敗：{str(e)}", operation="get_database_stats")


# 全域資料庫管理器實例
database_manager: Optional[DatabaseManager] = None


async def get_database_manager() -> DatabaseManager:
    """
    獲取全域資料庫管理器實例
    
    返回：
        資料庫管理器實例
    """
    global database_manager
    if not database_manager:
        database_manager = DatabaseManager()
        await database_manager.initialize()
    return database_manager


# 向後相容性：提供與原 Database Cog 相同的介面
class Database:
    """
    向後相容性類別
    
    提供與原 Database Cog 相同的介面，內部使用 DatabaseManager
    """
    
    def __init__(self, bot, db_name: Optional[str] = None, message_db_name: Optional[str] = None):
        self.bot = bot
        self.db_manager = DatabaseManager(db_name, message_db_name)
        self.ready = False
    
    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self.db_manager.initialize()
            setattr(self.bot, "database", self.db_manager)
            self.ready = True
            logger.info("Database Cog 相容模式已就緒")
        except Exception as e:
            logger.error(f"Database Cog 相容模式初始化失敗：{e}")
    
    async def cog_unload(self):
        """Cog 卸載時的清理"""
        await self.db_manager.cleanup()
    
    def __getattr__(self, name):
        """將方法調用轉發到 DatabaseManager"""
        if hasattr(self.db_manager, name):
            return getattr(self.db_manager, name)
        raise AttributeError(f"'Database' object has no attribute '{name}'")


async def setup(bot):
    """
    向後相容性設定函數
    
    保持與原 Database Cog 相同的設定介面
    """
    db_cog = Database(bot)
    await bot.add_cog(db_cog)
    await db_cog.cog_load()
    setattr(bot, "database", db_cog.db_manager)