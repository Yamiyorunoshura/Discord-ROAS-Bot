import os
import sqlite3
import logging
from dotenv import load_dotenv
from discord.ext import commands

# 設定專案根目錄
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 設定日誌
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_dir = os.path.join(PROJECT_ROOT, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
handler = logging.FileHandler(os.path.join(log_dir, 'database.log'), encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(handler)

class Database(commands.Cog):
    def __init__(self, bot, db_name=None):
        load_dotenv()
        if db_name is None:
            db_name = os.getenv("DATABASE_NAME")
        if db_name is None:
            db_name = "welcome.db"

        # 確保資料庫檔案位於 dbs/ 目錄下
        db_dir = os.path.join(PROJECT_ROOT, 'dbs')
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self.db_name = os.path.join(db_dir, db_name)

        logger.info(f"Database class initialized with db_name: {self.db_name}")
        self.conn = None
        self.cursor = None
        self.bot = bot
        self.initialized = False
        self.connect()
        self.create_tables()
        self._initialize_settings()

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            logger.debug(f"Successfully connected to database {self.db_name}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database {self.db_name}: {e}")
            raise

    def close(self):
        if self.conn:
            self.conn.close()
            logger.debug("資料庫連接已關閉")
            self.conn = None
            self.cursor = None

    def _get_connection(self):
        if self.conn is None:
            self.connect()
        return self.conn

    def _execute_query(self, query, params=None):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            logger.debug(f"Executed query: {query} with params: {params}")
        except sqlite3.Error as e:
            logger.error(f"Failed to execute query: {query} with params: {params}: {e}")
            if self.conn:
                self.conn.rollback()
            raise

    def _execute_select_query(self, query, params=None):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchall()
            logger.debug(f"Executed SELECT query: {query} with params: {params}, result: {result}")
            return result
        except sqlite3.Error as e:
            logger.error(f"Failed to execute SELECT query: {query} with params: {params}: {e}")
            raise

    def create_tables(self):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS welcome_settings (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    title TEXT,
                    description TEXT,
                    image_url TEXT,
                    delete_url TEXT
                );
                CREATE TABLE IF NOT EXISTS welcome_messages (
                    guild_id INTEGER PRIMARY KEY,
                    message TEXT
                );
                CREATE TABLE IF NOT EXISTS text_styles (
                    guild_id INTEGER,
                    type TEXT,
                    x INTEGER,
                    y INTEGER,
                    size INTEGER,
                    color TEXT,
                    opacity INTEGER,
                    font TEXT,
                    PRIMARY KEY (guild_id, type)
                );
                CREATE TABLE IF NOT EXISTS welcome_backgrounds (
                    guild_id INTEGER PRIMARY KEY,
                    image_path TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    setting_name TEXT PRIMARY KEY,
                    log_channel_id INTEGER,
                    log_edits INTEGER DEFAULT 1,
                    log_deletes INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    content TEXT,
                    timestamp REAL
                );
                CREATE TABLE IF NOT EXISTS monitored_channels (
                    channel_id INTEGER PRIMARY KEY
                );
            """)
            conn.commit()
            logger.info("資料表建立成功")
        except sqlite3.Error as e:
            logger.error(f"資料表建立失敗: {e}")
            raise

    def _add_column_if_not_exists(self, table_name, column_name, column_type):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    conn.commit()
                    logger.info(f"成功新增 '{column_name}' 欄位到 {table_name} 資料表")
                except sqlite3.Error as e:
                    logger.error(f"新增 '{column_name}' 欄位到 {table_name} 資料表失敗: {e}")
                    raise
            finally:
                if self.conn:
                    pass
        except sqlite3.Error as e:
            logger.error(f"資料表 {table_name} 操作失敗: {e}")
            raise

    def update_welcome_message(self, guild_id, channel_id, message):
        try:
            query_check = "SELECT guild_id FROM welcome_settings WHERE guild_id = ?"
            result = self._execute_select_query(query_check, (guild_id,))

            if result:
                query_update_settings = """
                    UPDATE welcome_settings SET channel_id = ? WHERE guild_id = ?
                """
                self._execute_query(query_update_settings, (channel_id, guild_id))
            else:
                query_insert_settings = """
                    INSERT INTO welcome_settings (guild_id, channel_id) VALUES (?, ?)
                """
                self._execute_query(query_insert_settings, (guild_id, channel_id))

            query_message = """
                INSERT OR REPLACE INTO welcome_messages (guild_id, message) VALUES (?, ?)
            """
            self._execute_query(query_message, (guild_id, message))

            logger.debug(f"成功更新歡迎訊息，伺服器 ID: {guild_id}, 頻道 ID: {channel_id}, 訊息: {message}")
        except sqlite3.Error as e:
            logger.error(f"更新歡迎訊息失敗，伺服器 ID: {guild_id}, 頻道 ID: {channel_id}, 訊息: {message}, 錯誤: {e}")
            raise

    def get_welcome_message(self, guild_id):
        try:
            query = "SELECT message FROM welcome_messages WHERE guild_id = ?"
            result = self._execute_select_query(query, (guild_id,))
            if result:
                logger.debug(f"成功取得歡迎訊息，伺服器 ID: {guild_id}, 訊息: {result[0][0]}")
                return result[0][0]
            logger.debug(f"找不到歡迎訊息，伺服器 ID: {guild_id}")
            return None
        except sqlite3.Error as e:
            logger.error(f"取得歡迎訊息失敗，伺服器 ID: {guild_id}, 錯誤: {e}")
            raise

    def update_welcome_background(self, guild_id, image_path):
        try:
            query = """
                INSERT OR REPLACE INTO welcome_backgrounds (guild_id, image_path) VALUES (?, ?)
            """
            self._execute_query(query, (guild_id, image_path))
            logger.debug(f"成功更新歡迎背景圖片，伺服器 ID: {guild_id}, 圖片路徑: {image_path}")
        except sqlite3.Error as e:
            logger.error(f"更新歡迎背景圖片失敗，伺服器 ID: {guild_id}, 圖片路徑: {image_path}, 錯誤: {e}")
            raise

    def get_welcome_background(self, guild_id):
        try:
            query = "SELECT image_path FROM welcome_backgrounds WHERE guild_id = ?"
            result = self._execute_select_query(query, (guild_id,))
            if result:
                logger.debug(f"成功取得歡迎背景圖片，伺服器 ID: {guild_id}, 圖片路徑: {result[0][0]}")
                return result[0][0]
            logger.debug(f"找不到歡迎背景圖片，伺服器 ID: {guild_id}")
            return None
        except sqlite3.Error as e:
            logger.error(f"取得歡迎背景圖片失敗，伺服器 ID: {guild_id}, 錯誤: {e}")
            raise

    def update_text_style(self, guild_id, x, y, size, color, opacity, font, text_type):
        try:
            query = """
                INSERT OR REPLACE INTO text_styles (guild_id, type, x, y, size, color, opacity, font)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            self._execute_query(query, (guild_id, text_type, x, y, size, color, opacity, font))
            logger.debug(f"成功更新文字樣式，伺服器 ID: {guild_id}, 類型: {text_type}, x: {x}, y: {y}, 大小: {size}, 顏色: {color}, 透明度: {opacity}, 字體: {font}")
        except sqlite3.Error as e:
            logger.error(f"更新文字樣式失敗，伺服器 ID: {guild_id}, 類型: {text_type}, x: {x}, y: {y}, 大小: {size}, 顏色: {color}, 透明度: {opacity}, 字體: {font}, 錯誤: {e}")
            raise

    def get_text_style(self, guild_id, text_type):
        try:
            query = """
                SELECT x, y, size, color, opacity, font FROM text_styles
                WHERE guild_id = ? AND type = ?
            """
            result = self._execute_select_query(query, (guild_id, text_type))
            if result:
                logger.debug(f"成功取得文字樣式，伺服器 ID: {guild_id}, 類型: {text_type}, 樣式: {result}")
                x = int(result[0][0]) if result[0][0] is not None else 0
                y = int(result[0][1]) if result[0][1] is not None else 0
                size = int(result[0][2]) if result[0][2] is not None else 30
                color = str(result[0][3]) if result[0][3] is not None else "#000000"
                opacity = int(result[0][4]) if result[0][4] is not None else 255
                font = str(result[0][5]) if result[0][5] is not None else "arial.ttf"
                return {
                    "x": x,
                    "y": y,
                    "size": size,
                    "color": color,
                    "opacity": opacity,
                    "font": font
                }
            logger.debug(f"找不到文字樣式，伺服器 ID: {guild_id}, 類型: {text_type}")
            return None
        except sqlite3.Error as e:
            logger.error(f"取得文字樣式失敗，伺服器 ID: {guild_id}, 類型: {text_type}, 錯誤: {e}")
            raise

    def update_welcome_title(self, guild_id, title):
        try:
            query_check = "SELECT guild_id FROM welcome_settings WHERE guild_id = ?"
            result = self._execute_select_query(query_check, (guild_id,))

            if result:
                query = """
                    UPDATE welcome_settings SET title = ? WHERE guild_id = ?
                """
                self._execute_query(query, (title, guild_id))
            else:
                query = """
                    INSERT INTO welcome_settings (guild_id, title) VALUES (?, ?)
                """
                self._execute_query(query, (guild_id, title))

            logger.debug(f"成功更新歡迎標題，伺服器 ID: {guild_id}, 標題: {title}")
        except sqlite3.Error as e:
            logger.error(f"更新歡迎標題失敗，伺服器 ID: {guild_id}, 標題: {title}, 錯誤: {e}")
            raise

    def update_welcome_description(self, guild_id, description):
        try:
            query_check = "SELECT guild_id FROM welcome_settings WHERE guild_id = ?"
            result = self._execute_select_query(query_check, (guild_id,))

            if result:
                query = """
                    UPDATE welcome_settings SET description = ? WHERE guild_id = ?
                """
                self._execute_query(query, (description, guild_id))
            else:
                query = """
                    INSERT INTO welcome_settings (guild_id, description) VALUES (?, ?)
                """
                self._execute_query(query, (guild_id, description))

            logger.debug(f"成功更新歡迎描述，伺服器 ID: {guild_id}, 描述: {description}")
        except sqlite3.Error as e:
            logger.error(f"更新歡迎描述失敗，伺服器 ID: {guild_id}, 描述: {description}, 錯誤: {e}")
            raise

    def get_welcome_settings(self, guild_id):
        try:
            query = """
                SELECT channel_id, title, description, image_url, delete_url
                FROM welcome_settings
                WHERE guild_id = ?
            """
            result = self._execute_select_query(query, (guild_id,))
            if result:
                logger.debug(f"成功取得歡迎設定，伺服器 ID: {guild_id}, 設定: {result}")
                welcome_settings = {
                    "channel_id": result[0][0],
                    "title": result[0][1],
                    "description": result[0][2],
                    "image_url": result[0][3],
                    "delete_url": result[0][4]
                }
            else:
                logger.debug(f"找不到歡迎設定，伺服器 ID: {guild_id}")
                welcome_settings = None

            if welcome_settings is None:
                welcome_settings = {
                    "channel_id": None,
                    "title": "歡迎 {member.name}!",
                    "description": "感謝你的加入！",
                    "image_url": None,
                    "delete_url": None
                }
            return welcome_settings
        except sqlite3.Error as e:
            logger.error(f"取得歡迎設定失敗，伺服器 ID: {guild_id}, 錯誤: {e}")
            raise

    def get_monitored_channels(self):
        try:
            query = "SELECT channel_id FROM monitored_channels"
            results = self._execute_select_query(query)
            if results:
                return [result[0] for result in results]
            else:
                return []
        except Exception as e:
            logger.error(f"獲取需要監聽的頻道列表失敗: {e}")
            return []

    def add_monitored_channel(self, channel_id):
        try:
            query = "INSERT INTO monitored_channels (channel_id) VALUES (?)"
            self._execute_query(query, (channel_id,))
        except Exception as e:
            logger.error(f"新增需要監聽的頻道失敗: {e}")

    def remove_monitored_channel(self, channel_id):
        try:
            query = "DELETE FROM monitored_channels WHERE channel_id = ?"
            self._execute_query(query, (channel_id,))
        except Exception as e:
            logger.error(f"移除需要監聽的頻道失敗: {e}")

    def _initialize_settings(self):
        if self.initialized:
            return
        default_settings = {
            "log_channel_id": None,
            "log_edits": 1,
            "log_deletes": 1
        }
        try:
            for setting_name, default_value in default_settings.items():
                query = "SELECT setting_name FROM settings WHERE setting_name = ?"
                result = self._execute_select_query(query, (setting_name,))
                if not result:
                    query = "INSERT INTO settings (setting_name, log_channel_id, log_edits, log_deletes) VALUES (?, ?, ?, ?)"
                    self._execute_query(query, (setting_name, default_settings["log_channel_id"], default_settings["log_edits"], default_settings["log_deletes"]))
                    logger.info(f"已初始化設定 '{setting_name}' 為預設值: {default_value}")
            self.initialized = True
        except Exception as e:
            logger.error(f"初始化設定失敗: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Database Cog is ready.")

async def setup(bot):
    database_cog = Database(bot)
    bot.database = database_cog
    await bot.add_cog(database_cog)