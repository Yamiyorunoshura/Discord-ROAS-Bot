"""
資料庫架構擴展驗證測試
Task ID: 1 - 核心架構和基礎設施建置

測試v2.4.4的資料庫遷移和表結構：
- 子機器人系統資料模型
- AI系統資料模型  
- 部署系統資料模型
- 索引創建和約束驗證
"""

import pytest
import asyncio
import sqlite3
import os
import tempfile
import json
from datetime import datetime, date
from typing import Dict, Any, List, Optional


class TestDatabaseMigration:
    """測試資料庫遷移和表結構"""
    
    @pytest.fixture
    def temp_database(self):
        """創建臨時資料庫用於測試"""
        # 創建臨時檔案
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        
        yield db_path
        
        # 清理
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def migration_script_path(self):
        """獲取遷移腳本路徑"""
        return "/Users/tszkinlai/Coding/roas-bot/migrations/0009_roas_bot_v2_4_4_core_tables.sql"
    
    def execute_migration(self, db_path: str, script_path: str):
        """執行遷移腳本"""
        if not os.path.exists(script_path):
            pytest.skip(f"Migration script not found: {script_path}")
        
        with open(script_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # 分割SQL語句並執行
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 執行遷移腳本
            cursor.executescript(migration_sql)
            conn.commit()
            return conn
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e
    
    def test_migration_script_exists(self, migration_script_path):
        """測試遷移腳本是否存在"""
        assert os.path.exists(migration_script_path), f"Migration script not found: {migration_script_path}"
    
    def test_execute_migration_script(self, temp_database, migration_script_path):
        """測試執行遷移腳本"""
        conn = self.execute_migration(temp_database, migration_script_path)
        
        # 驗證資料庫連接成功
        assert conn is not None
        
        # 檢查是否有表被創建
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # 驗證核心表存在
        expected_tables = ['sub_bots', 'sub_bot_channels', 'ai_conversations', 
                          'ai_usage_quotas', 'ai_providers', 'deployment_logs']
        
        for table in expected_tables:
            assert table in tables, f"Table {table} not found in database"
        
        conn.close()


class TestSubBotTables:
    """測試子機器人相關資料表"""
    
    @pytest.fixture
    def database_conn(self, temp_database, migration_script_path):
        """創建有遷移資料的資料庫連接"""
        test_instance = TestDatabaseMigration()
        conn = test_instance.execute_migration(temp_database, migration_script_path)
        yield conn
        conn.close()
    
    @pytest.fixture
    def temp_database(self):
        """創建臨時資料庫"""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        yield db_path
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def migration_script_path(self):
        """獲取遷移腳本路徑"""
        return "/Users/tszkinlai/Coding/roas-bot/migrations/0009_roas_bot_v2_4_4_core_tables.sql"
    
    def test_sub_bots_table_structure(self, database_conn):
        """測試sub_bots表結構"""
        cursor = database_conn.cursor()
        cursor.execute("PRAGMA table_info(sub_bots)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            'id': 'INTEGER',
            'bot_id': 'VARCHAR(50)',
            'name': 'VARCHAR(100)', 
            'token_hash': 'VARCHAR(255)',
            'target_channels': 'TEXT',
            'ai_enabled': 'BOOLEAN',
            'ai_model': 'VARCHAR(50)',
            'personality': 'TEXT',
            'rate_limit': 'INTEGER',
            'status': 'VARCHAR(20)',
            'created_at': 'DATETIME',
            'updated_at': 'DATETIME',
            'last_active_at': 'DATETIME',
            'message_count': 'INTEGER'
        }
        
        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Column {col_name} not found in sub_bots table"
            assert columns[col_name] == col_type, f"Column {col_name} has wrong type: {columns[col_name]} != {col_type}"
    
    def test_sub_bots_constraints(self, database_conn):
        """測試sub_bots表約束"""
        cursor = database_conn.cursor()
        
        # 測試正常插入
        cursor.execute("""
            INSERT INTO sub_bots (bot_id, name, token_hash, target_channels)
            VALUES (?, ?, ?, ?)
        """, ('test_bot_001', 'Test Bot', 'encrypted_token', '["123456789"]'))
        
        # 測試唯一約束
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO sub_bots (bot_id, name, token_hash, target_channels)
                VALUES (?, ?, ?, ?)
            """, ('test_bot_001', 'Another Bot', 'another_token', '["987654321"]'))
        
        # 測試CHECK約束 - 無效狀態
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO sub_bots (bot_id, name, token_hash, target_channels, status)
                VALUES (?, ?, ?, ?, ?)
            """, ('test_bot_002', 'Test Bot 2', 'encrypted_token2', '["123456789"]', 'invalid_status'))
        
        # 測試CHECK約束 - 無效rate_limit
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO sub_bots (bot_id, name, token_hash, target_channels, rate_limit)
                VALUES (?, ?, ?, ?, ?)
            """, ('test_bot_003', 'Test Bot 3', 'encrypted_token3', '["123456789"]', 0))
    
    def test_sub_bot_channels_table_structure(self, database_conn):
        """測試sub_bot_channels表結構"""
        cursor = database_conn.cursor()
        cursor.execute("PRAGMA table_info(sub_bot_channels)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            'id': 'INTEGER',
            'sub_bot_id': 'INTEGER',
            'channel_id': 'BIGINT',
            'channel_type': 'VARCHAR(20)',
            'permissions': 'TEXT',
            'created_at': 'DATETIME'
        }
        
        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Column {col_name} not found in sub_bot_channels table"
    
    def test_sub_bot_channels_foreign_key(self, database_conn):
        """測試sub_bot_channels外鍵約束"""
        cursor = database_conn.cursor()
        
        # 先插入parent記錄
        cursor.execute("""
            INSERT INTO sub_bots (bot_id, name, token_hash, target_channels)
            VALUES (?, ?, ?, ?)
        """, ('test_bot_001', 'Test Bot', 'encrypted_token', '["123456789"]'))
        
        sub_bot_id = cursor.lastrowid
        
        # 測試正常插入
        cursor.execute("""
            INSERT INTO sub_bot_channels (sub_bot_id, channel_id, channel_type)
            VALUES (?, ?, ?)
        """, (sub_bot_id, 123456789, 'text'))
        
        # 測試唯一約束
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO sub_bot_channels (sub_bot_id, channel_id, channel_type)
                VALUES (?, ?, ?)
            """, (sub_bot_id, 123456789, 'voice'))  # 同樣的sub_bot_id和channel_id


class TestAITables:
    """測試AI相關資料表"""
    
    @pytest.fixture
    def database_conn(self, temp_database, migration_script_path):
        """創建有遷移資料的資料庫連接"""
        test_instance = TestDatabaseMigration()
        conn = test_instance.execute_migration(temp_database, migration_script_path)
        yield conn
        conn.close()
    
    @pytest.fixture
    def temp_database(self):
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        yield db_path
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def migration_script_path(self):
        return "/Users/tszkinlai/Coding/roas-bot/migrations/0009_roas_bot_v2_4_4_core_tables.sql"
    
    def test_ai_conversations_table_structure(self, database_conn):
        """測試ai_conversations表結構"""
        cursor = database_conn.cursor()
        cursor.execute("PRAGMA table_info(ai_conversations)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            'id': 'INTEGER',
            'user_id': 'BIGINT',
            'sub_bot_id': 'INTEGER',
            'provider': 'VARCHAR(20)',
            'model': 'VARCHAR(50)',
            'user_message': 'TEXT',
            'ai_response': 'TEXT',
            'tokens_used': 'INTEGER',
            'cost': 'DECIMAL(10, 6)',
            'response_time': 'DECIMAL(8, 3)',
            'created_at': 'DATETIME'
        }
        
        for col_name in expected_columns.keys():
            assert col_name in columns, f"Column {col_name} not found in ai_conversations table"
    
    def test_ai_conversations_constraints(self, database_conn):
        """測試ai_conversations表約束"""
        cursor = database_conn.cursor()
        
        # 測試正常插入
        cursor.execute("""
            INSERT INTO ai_conversations (user_id, provider, model, user_message, ai_response, tokens_used, cost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (12345, 'openai', 'gpt-3.5-turbo', 'Hello', 'Hi there!', 10, 0.0001))
        
        # 測試CHECK約束 - 無效provider
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO ai_conversations (user_id, provider, model, user_message, ai_response)
                VALUES (?, ?, ?, ?, ?)
            """, (12345, 'invalid_provider', 'model', 'message', 'response'))
        
        # 測試CHECK約束 - 負tokens_used
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO ai_conversations (user_id, provider, model, user_message, ai_response, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (12345, 'openai', 'model', 'message', 'response', -1))
    
    def test_ai_usage_quotas_table_structure(self, database_conn):
        """測試ai_usage_quotas表結構"""
        cursor = database_conn.cursor()
        cursor.execute("PRAGMA table_info(ai_usage_quotas)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            'id': 'INTEGER',
            'user_id': 'BIGINT',
            'daily_limit': 'INTEGER',
            'weekly_limit': 'INTEGER', 
            'monthly_limit': 'INTEGER',
            'daily_used': 'INTEGER',
            'weekly_used': 'INTEGER',
            'monthly_used': 'INTEGER',
            'total_cost_limit': 'DECIMAL(10, 2)',
            'total_cost_used': 'DECIMAL(10, 2)',
            'last_reset_daily': 'DATE',
            'last_reset_weekly': 'DATE',
            'last_reset_monthly': 'DATE',
            'created_at': 'DATETIME',
            'updated_at': 'DATETIME'
        }
        
        for col_name in expected_columns.keys():
            assert col_name in columns, f"Column {col_name} not found in ai_usage_quotas table"
    
    def test_ai_providers_default_data(self, database_conn):
        """測試ai_providers預設資料"""
        cursor = database_conn.cursor()
        cursor.execute("SELECT provider_name, is_active, priority FROM ai_providers ORDER BY priority")
        providers = cursor.fetchall()
        
        # 驗證預設提供商
        expected_providers = ['openai', 'anthropic', 'google']
        actual_providers = [row[0] for row in providers]
        
        for provider in expected_providers:
            assert provider in actual_providers, f"Default provider {provider} not found"
    
    def test_ai_providers_constraints(self, database_conn):
        """測試ai_providers表約束"""
        cursor = database_conn.cursor()
        
        # 測試CHECK約束 - 無效priority
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO ai_providers (provider_name, api_key_hash, priority)
                VALUES (?, ?, ?)
            """, ('test_provider', 'hash', 0))  # priority必須>0


class TestDeploymentTables:
    """測試部署相關資料表"""
    
    @pytest.fixture
    def database_conn(self, temp_database, migration_script_path):
        test_instance = TestDatabaseMigration()
        conn = test_instance.execute_migration(temp_database, migration_script_path)
        yield conn
        conn.close()
    
    @pytest.fixture
    def temp_database(self):
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        yield db_path
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def migration_script_path(self):
        return "/Users/tszkinlai/Coding/roas-bot/migrations/0009_roas_bot_v2_4_4_core_tables.sql"
    
    def test_deployment_logs_table_structure(self, database_conn):
        """測試deployment_logs表結構"""
        cursor = database_conn.cursor()
        cursor.execute("PRAGMA table_info(deployment_logs)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            'id': 'INTEGER',
            'deployment_id': 'VARCHAR(50)',
            'mode': 'VARCHAR(20)',
            'status': 'VARCHAR(20)', 
            'environment_info': 'TEXT',
            'error_message': 'TEXT',
            'start_time': 'DATETIME',
            'end_time': 'DATETIME',
            'duration_seconds': 'INTEGER',
            'created_at': 'DATETIME'
        }
        
        for col_name in expected_columns.keys():
            assert col_name in columns, f"Column {col_name} not found in deployment_logs table"
    
    def test_deployment_logs_constraints(self, database_conn):
        """測試deployment_logs表約束"""
        cursor = database_conn.cursor()
        
        # 測試正常插入
        cursor.execute("""
            INSERT INTO deployment_logs (deployment_id, mode, status, duration_seconds)
            VALUES (?, ?, ?, ?)
        """, ('deploy_001', 'docker', 'running', 120))
        
        # 測試唯一約束
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO deployment_logs (deployment_id, mode, status)
                VALUES (?, ?, ?)
            """, ('deploy_001', 'uv_python', 'pending'))
        
        # 測試CHECK約束 - 無效mode
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO deployment_logs (deployment_id, mode, status)
                VALUES (?, ?, ?)
            """, ('deploy_002', 'invalid_mode', 'pending'))
        
        # 測試CHECK約束 - 無效status
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO deployment_logs (deployment_id, mode, status)
                VALUES (?, ?, ?)
            """, ('deploy_003', 'docker', 'invalid_status'))
        
        # 測試CHECK約束 - 負duration_seconds
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO deployment_logs (deployment_id, mode, status, duration_seconds)
                VALUES (?, ?, ?, ?)
            """, ('deploy_004', 'docker', 'failed', -1))


class TestDatabaseIndexes:
    """測試資料庫索引"""
    
    @pytest.fixture
    def database_conn(self, temp_database, migration_script_path):
        test_instance = TestDatabaseMigration()
        conn = test_instance.execute_migration(temp_database, migration_script_path)
        yield conn
        conn.close()
    
    @pytest.fixture
    def temp_database(self):
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        yield db_path
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def migration_script_path(self):
        return "/Users/tszkinlai/Coding/roas-bot/migrations/0009_roas_bot_v2_4_4_core_tables.sql"
    
    def test_indexes_created(self, database_conn):
        """測試索引是否正確創建"""
        cursor = database_conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_%'
            ORDER BY name
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        
        expected_indexes = [
            'idx_ai_conversations_created_at',
            'idx_ai_conversations_provider',
            'idx_ai_conversations_sub_bot_id',
            'idx_ai_conversations_user_date',
            'idx_ai_conversations_user_id',
            'idx_ai_providers_active',
            'idx_ai_providers_name',
            'idx_ai_providers_priority',
            'idx_ai_usage_quotas_daily_reset',
            'idx_ai_usage_quotas_monthly_reset',
            'idx_ai_usage_quotas_user_id',
            'idx_ai_usage_quotas_weekly_reset',
            'idx_deployment_logs_deployment_id',
            'idx_deployment_logs_mode',
            'idx_deployment_logs_start_time',
            'idx_deployment_logs_status',
            'idx_sub_bot_channels_channel_id',
            'idx_sub_bot_channels_sub_bot_id',
            'idx_sub_bot_channels_type',
            'idx_sub_bots_ai_enabled',
            'idx_sub_bots_bot_id',
            'idx_sub_bots_created_at',
            'idx_sub_bots_status'
        ]
        
        for expected_index in expected_indexes:
            assert expected_index in indexes, f"Index {expected_index} not found"
    
    def test_index_functionality(self, database_conn):
        """測試索引功能性"""
        cursor = database_conn.cursor()
        
        # 插入測試資料
        cursor.execute("""
            INSERT INTO sub_bots (bot_id, name, token_hash, target_channels, status)
            VALUES (?, ?, ?, ?, ?)
        """, ('test_bot_001', 'Test Bot', 'hash', '["123"]', 'online'))
        
        # 測試索引是否被使用
        cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM sub_bots WHERE bot_id = ?", ('test_bot_001',))
        plan = cursor.fetchall()
        
        # 檢查是否使用索引（查詢計劃中應包含USING INDEX）
        plan_text = ' '.join([str(row[3]) for row in plan])  # 獲取查詢計劃詳細信息
        assert 'USING INDEX' in plan_text or 'SEARCH' in plan_text or 'INDEX' in plan_text, f"Index not used in query plan: {plan_text}"


class TestDatabaseIntegration:
    """測試資料庫整合功能"""
    
    @pytest.fixture
    def database_conn(self, temp_database, migration_script_path):
        test_instance = TestDatabaseMigration()
        conn = test_instance.execute_migration(temp_database, migration_script_path)
        yield conn
        conn.close()
    
    @pytest.fixture
    def temp_database(self):
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        yield db_path
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def migration_script_path(self):
        return "/Users/tszkinlai/Coding/roas-bot/migrations/0009_roas_bot_v2_4_4_core_tables.sql"
    
    def test_complete_workflow_integration(self, database_conn):
        """測試完整的工作流程整合"""
        cursor = database_conn.cursor()
        
        # 1. 創建子機器人
        cursor.execute("""
            INSERT INTO sub_bots (bot_id, name, token_hash, target_channels, ai_enabled, ai_model)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('bot_001', 'AI Bot', 'encrypted_token', '["123456789"]', True, 'gpt-3.5-turbo'))
        
        sub_bot_id = cursor.lastrowid
        
        # 2. 配置頻道
        cursor.execute("""
            INSERT INTO sub_bot_channels (sub_bot_id, channel_id, channel_type, permissions)
            VALUES (?, ?, ?, ?)
        """, (sub_bot_id, 123456789, 'text', '{"read": true, "write": true}'))
        
        # 3. 創建AI對話記錄
        cursor.execute("""
            INSERT INTO ai_conversations (user_id, sub_bot_id, provider, model, user_message, ai_response, tokens_used, cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (98765, sub_bot_id, 'openai', 'gpt-3.5-turbo', 'Hello', 'Hi! How can I help?', 15, 0.0002))
        
        # 4. 更新用戶配額
        cursor.execute("""
            INSERT INTO ai_usage_quotas (user_id, daily_used, total_cost_used)
            VALUES (?, ?, ?)
        """, (98765, 1, 0.0002))
        
        # 5. 記錄部署日誌
        cursor.execute("""
            INSERT INTO deployment_logs (deployment_id, mode, status, duration_seconds)
            VALUES (?, ?, ?, ?)
        """, ('deploy_bot_001', 'docker', 'running', 45))
        
        # 驗證資料一致性
        cursor.execute("""
            SELECT sb.name, sbc.channel_id, ai.tokens_used, aiq.daily_used, dl.status
            FROM sub_bots sb
            LEFT JOIN sub_bot_channels sbc ON sb.id = sbc.sub_bot_id
            LEFT JOIN ai_conversations ai ON sb.id = ai.sub_bot_id
            LEFT JOIN ai_usage_quotas aiq ON ai.user_id = aiq.user_id
            LEFT JOIN deployment_logs dl ON dl.deployment_id = 'deploy_bot_001'
            WHERE sb.bot_id = 'bot_001'
        """)
        
        result = cursor.fetchone()
        assert result is not None, "Integration query returned no results"
        assert result[0] == 'AI Bot', "Sub bot name mismatch"
        assert result[1] == 123456789, "Channel ID mismatch" 
        assert result[2] == 15, "Tokens used mismatch"
        assert result[3] == 1, "Daily used mismatch"
        assert result[4] == 'running', "Deployment status mismatch"


if __name__ == "__main__":
    # 運行測試
    pytest.main([__file__, "-v"])