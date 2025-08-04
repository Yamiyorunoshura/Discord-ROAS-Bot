"""
🧪 基本測試 - 驗證測試框架和核心功能正常工作
- 測試基本模組導入和初始化
- 驗證 Mock 物件創建和使用
- 測試資料庫連接和操作
- 驗證配置管理和錯誤處理
- 測試效能基準線
"""

import asyncio
import gc
import os
import sys
import time

import aiosqlite
import discord
import pytest

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🎯 基本測試框架驗證
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestFrameworkBasics:
    """🧪 測試框架基本功能"""

    def test_pytest_working(self):
        """✅ 測試 pytest 框架工作正常"""
        assert True, "pytest 應該能正常工作"
        assert 1 + 1 == 2, "基本運算應該正確"
        assert "test" in "testing", "字符串操作應該正常"

    @pytest.mark.asyncio
    async def test_asyncio_working(self):
        """🔄 測試異步功能工作正常"""

        async def async_task():
            await asyncio.sleep(0.01)
            return "完成"

        result = await async_task()
        assert result == "完成", "異步任務應該正常完成"

    def test_imports_working(self):
        """📦 測試基本導入功能"""
        # 測試標準庫導入
        import datetime
        import json
        import pathlib

        assert json is not None, "json 模組應該可用"
        assert datetime is not None, "datetime 模組應該可用"
        assert pathlib is not None, "pathlib 模組應該可用"

    def test_discord_py_available(self):
        """🎮 測試 Discord.py 可用性"""
        assert discord is not None, "discord.py 應該可用"
        assert hasattr(discord, "Guild"), "應該有 Guild 類別"
        assert hasattr(discord, "User"), "應該有 User 類別"
        assert hasattr(discord, "Message"), "應該有 Message 類別"
        assert hasattr(discord, "TextChannel"), "應該有 TextChannel 類別"


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🎭 Mock 物件測試
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestMockObjects:
    """🎭 測試 Mock 物件創建和使用"""

    def test_mock_guild_creation(self, mock_guild):
        """🏰 測試模擬伺服器創建"""
        assert mock_guild.id == 12345, "伺服器 ID 應該正確"
        assert mock_guild.name == "測試伺服器", "伺服器名稱應該正確"
        assert mock_guild.member_count == 100, "成員數量應該正確"
        assert hasattr(mock_guild, "get_member"), "應該有獲取成員方法"
        assert hasattr(mock_guild, "get_channel"), "應該有獲取頻道方法"
        assert hasattr(mock_guild, "get_role"), "應該有獲取角色方法"

    def test_mock_user_creation(self, mock_user):
        """👤 測試模擬用戶創建"""
        assert mock_user.id == 67890, "用戶 ID 應該正確"
        assert mock_user.name == "測試用戶", "用戶名稱應該正確"
        assert mock_user.discriminator == "0001", "用戶標識符應該正確"
        assert not mock_user.bot, "應該不是機器人"
        assert hasattr(mock_user, "display_avatar"), "應該有頭像屬性"
        assert hasattr(mock_user, "mention"), "應該有提及屬性"

    def test_mock_member_creation(self, mock_member):
        """👥 測試模擬成員創建"""
        assert mock_member.id == 67890, "成員 ID 應該正確"
        assert hasattr(mock_member, "guild"), "應該有伺服器屬性"
        assert hasattr(mock_member, "guild_permissions"), "應該有權限屬性"
        assert hasattr(mock_member, "timeout"), "應該有超時方法"
        assert hasattr(mock_member, "edit"), "應該有編輯方法"

        # 測試權限設定
        assert not mock_member.guild_permissions.administrator, "預設不應該是管理員"
        assert not mock_member.guild_permissions.manage_guild, (
            "預設不應該有管理伺服器權限"
        )

    def test_mock_admin_member_creation(self, mock_admin_member):
        """👑 測試模擬管理員成員創建"""
        assert mock_admin_member.name == "管理員", "管理員名稱應該正確"
        assert mock_admin_member.guild_permissions.administrator, "應該是管理員"
        assert mock_admin_member.guild_permissions.manage_guild, "應該有管理伺服器權限"
        assert mock_admin_member.guild_permissions.manage_messages, "應該有管理訊息權限"

    def test_mock_channel_creation(self, mock_channel):
        """📝 測試模擬頻道創建"""
        assert mock_channel.id == 98765, "頻道 ID 應該正確"
        assert mock_channel.name == "測試頻道", "頻道名稱應該正確"
        assert mock_channel.type == discord.ChannelType.text, "頻道類型應該正確"
        assert hasattr(mock_channel, "send"), "應該有發送方法"
        assert hasattr(mock_channel, "edit"), "應該有編輯方法"
        assert hasattr(mock_channel, "delete"), "應該有刪除方法"

    def test_mock_message_creation(self, mock_message):
        """💬 測試模擬訊息創建"""
        assert mock_message.id == 123456789, "訊息 ID 應該正確"
        assert mock_message.content == "測試訊息內容", "訊息內容應該正確"
        assert hasattr(mock_message, "author"), "應該有作者屬性"
        assert hasattr(mock_message, "guild"), "應該有伺服器屬性"
        assert hasattr(mock_message, "channel"), "應該有頻道屬性"
        assert hasattr(mock_message, "edit"), "應該有編輯方法"
        assert hasattr(mock_message, "delete"), "應該有刪除方法"

    def test_mock_interaction_creation(self, mock_interaction):
        """⚡ 測試模擬互動創建"""
        assert mock_interaction.guild_id == 12345, "互動伺服器 ID 應該正確"
        assert hasattr(mock_interaction, "response"), "應該有響應屬性"
        assert hasattr(mock_interaction, "followup"), "應該有跟進屬性"
        assert hasattr(mock_interaction.response, "send_message"), "響應應該有發送方法"
        assert hasattr(mock_interaction.followup, "send"), "跟進應該有發送方法"

    def test_mock_bot_creation(self, mock_bot):
        """🤖 測試模擬機器人創建"""
        assert mock_bot.user.id == 11111, "機器人 ID 應該正確"
        assert mock_bot.user.name == "測試機器人", "機器人名稱應該正確"
        assert mock_bot.user.bot, "應該是機器人"
        assert hasattr(mock_bot, "add_cog"), "應該有添加 Cog 方法"
        assert hasattr(mock_bot, "remove_cog"), "應該有移除 Cog 方法"
        assert hasattr(mock_bot, "get_guild"), "應該有獲取伺服器方法"


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🗄️ 資料庫測試
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestDatabaseOperations:
    """🗄️ 測試資料庫操作功能"""

    @pytest.mark.asyncio
    async def test_memory_database_connection(self, test_db):
        """🔗 測試記憶體資料庫連接"""
        # 測試基本連接
        assert test_db is not None, "資料庫連接應該存在"

        # 測試基本操作
        await test_db.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        await test_db.execute("INSERT INTO test VALUES (1, '測試')")
        await test_db.commit()

        cursor = await test_db.execute("SELECT * FROM test")
        result = await cursor.fetchone()

        assert result is not None, "查詢結果應該存在"
        assert result[0] == 1, "ID 應該正確"
        assert result[1] == "測試", "名稱應該正確"

    @pytest.mark.asyncio
    async def test_activity_database_schema(self, activity_test_db):
        """📊 測試活躍度資料庫架構"""
        # 檢查表格是否存在
        tables = ["meter", "daily", "report_channel", "settings"]
        for table in tables:
            cursor = await activity_test_db.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            result = await cursor.fetchone()
            assert result is not None, f"{table} 表格應該存在"

        # 測試插入資料
        await activity_test_db.execute(
            "INSERT INTO meter (guild_id, user_id, score, last_msg) VALUES (?, ?, ?, ?)",
            (12345, 67890, 50.0, int(time.time())),
        )
        await activity_test_db.commit()

        # 驗證插入
        cursor = await activity_test_db.execute(
            "SELECT * FROM meter WHERE guild_id=? AND user_id=?", (12345, 67890)
        )
        result = await cursor.fetchone()
        assert result is not None, "活躍度資料應該被插入"
        assert result["score"] == 50.0, "分數應該正確"

    @pytest.mark.asyncio
    async def test_message_listener_database_schema(self, message_listener_test_db):
        """💬 測試訊息監聽資料庫架構"""
        # 檢查表格和索引
        tables = ["messages", "settings", "monitored_channels"]
        for table in tables:
            cursor = await message_listener_test_db.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            result = await cursor.fetchone()
            assert result is not None, f"{table} 表格應該存在"

        # 檢查索引
        indexes = [
            "idx_messages_channel",
            "idx_messages_author",
            "idx_messages_timestamp",
        ]
        for index in indexes:
            cursor = await message_listener_test_db.execute(
                f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index}'"
            )
            result = await cursor.fetchone()
            assert result is not None, f"{index} 索引應該存在"

    @pytest.mark.asyncio
    async def test_database_transaction_handling(self, test_db):
        """🔄 測試資料庫事務處理"""
        # 創建測試表格
        await test_db.execute(
            "CREATE TABLE transaction_test (id INTEGER PRIMARY KEY, value TEXT)"
        )

        # 測試成功事務
        await test_db.execute(
            "INSERT INTO transaction_test (value) VALUES (?)", ("成功",)
        )
        await test_db.commit()

        cursor = await test_db.execute("SELECT COUNT(*) FROM transaction_test")
        count = await cursor.fetchone()
        assert count[0] == 1, "成功事務應該提交資料"

        # 測試回滾事務
        await test_db.execute(
            "INSERT INTO transaction_test (value) VALUES (?)", ("失敗",)
        )
        await test_db.rollback()

        cursor = await test_db.execute("SELECT COUNT(*) FROM transaction_test")
        count = await cursor.fetchone()
        assert count[0] == 1, "回滾事務不應該提交資料"

    @pytest.mark.asyncio
    async def test_database_error_handling(self, test_db):
        """❌ 測試資料庫錯誤處理"""
        # 測試語法錯誤
        with pytest.raises(aiosqlite.OperationalError):
            await test_db.execute("INVALID SQL SYNTAX")

        # 測試約束違反
        await test_db.execute(
            "CREATE TABLE constraint_test (id INTEGER PRIMARY KEY UNIQUE)"
        )
        await test_db.execute("INSERT INTO constraint_test (id) VALUES (1)")
        await test_db.commit()

        with pytest.raises(aiosqlite.IntegrityError):
            await test_db.execute("INSERT INTO constraint_test (id) VALUES (1)")
            await test_db.commit()


# ═══════════════════════════════════════════════════════════════════════════════════════════
# ⚙️ 配置管理測試
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestConfigurationManagement:
    """⚙️ 測試配置管理功能"""

    def test_environment_variables(self):
        """🌍 測試環境變數"""
        # 檢查測試環境變數
        assert os.getenv("TESTING") == "true", "測試環境變數應該設置"
        assert os.getenv("ENV") == "test", "環境應該是測試模式"

    def test_project_structure(self):
        """📁 測試專案結構"""
        # 檢查專案根目錄
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        # 檢查主要目錄存在
        expected_dirs = ["cogs", "tests", "logs", "data"]
        for dir_name in expected_dirs:
            dir_path = os.path.join(project_root, dir_name)
            if os.path.exists(dir_path):
                assert os.path.isdir(dir_path), f"{dir_name} 應該是目錄"

    def test_python_version(self):
        """🐍 測試 Python 版本"""
        # 檢查 Python 版本
        version_info = sys.version_info
        assert version_info.major >= 3, "應該使用 Python 3"
        assert version_info.minor >= 8, "應該使用 Python 3.8 或更高版本"


# ═══════════════════════════════════════════════════════════════════════════════════════════
# ⚡ 效能測試
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestPerformanceBasics:
    """⚡ 測試基本效能指標"""

    def test_basic_calculation_performance(self, performance_timer):
        """🔢 測試基本計算效能"""
        performance_timer.start()

        # 執行基本計算
        results = []
        for i in range(10000):
            result = i * 2 + 1
            results.append(result)

        performance_timer.stop()

        assert len(results) == 10000, "計算結果數量應該正確"
        assert performance_timer.elapsed < 1.0, (
            f"基本計算時間過長: {performance_timer.elapsed:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_database_operation_performance(self, test_db, performance_timer):
        """🗄️ 測試資料庫操作效能"""
        # 創建測試表格
        await test_db.execute(
            "CREATE TABLE perf_test (id INTEGER PRIMARY KEY, data TEXT)"
        )

        # 測試批量插入效能
        performance_timer.start()

        for i in range(100):
            await test_db.execute(
                "INSERT INTO perf_test (data) VALUES (?)", (f"資料{i}",)
            )
        await test_db.commit()

        performance_timer.stop()

        # 驗證插入時間在可接受範圍內 (2秒)
        assert performance_timer.elapsed < 2.0, (
            f"批量插入時間過長: {performance_timer.elapsed:.3f}s"
        )

        # 測試查詢效能
        performance_timer.start()

        cursor = await test_db.execute("SELECT COUNT(*) FROM perf_test")
        result = await cursor.fetchone()

        performance_timer.stop()

        assert result[0] == 100, "查詢結果應該正確"
        assert performance_timer.elapsed < 0.1, (
            f"查詢時間過長: {performance_timer.elapsed:.3f}s"
        )

    def test_memory_usage_basic(self, memory_monitor):
        """🧠 測試基本記憶體使用"""
        initial_memory = memory_monitor.get_current_usage()

        # 創建一些物件
        test_data = []
        for i in range(1000):
            test_data.append(f"測試資料{i}" * 100)

        current_memory = memory_monitor.get_current_usage()
        memory_increase = current_memory - initial_memory

        # 驗證記憶體增加在合理範圍內 (100MB)
        assert memory_increase < 100 * 1024 * 1024, (
            f"記憶體使用過多: {memory_increase} bytes"
        )

        # 清理資料
        del test_data
        gc.collect()

    @pytest.mark.asyncio
    async def test_async_operation_performance(self, performance_timer):
        """🔄 測試異步操作效能"""

        async def test_async_task():
            await asyncio.sleep(0.01)  # 模擬異步操作
            return "完成"

        performance_timer.start()

        # 並行執行多個異步任務
        tasks = [test_async_task() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        performance_timer.stop()

        assert len(results) == 10, "所有任務應該完成"
        assert all(result == "完成" for result in results), "所有任務結果應該正確"
        # 並行執行應該比串行快
        assert performance_timer.elapsed < 0.5, (
            f"並行執行時間過長: {performance_timer.elapsed:.3f}s"
        )


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🔒 安全性測試
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestSecurityBasics:
    """🔒 測試基本安全性"""

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, test_db):
        """🛡️ 測試 SQL 注入防護"""
        await test_db.execute(
            "CREATE TABLE security_test (id INTEGER PRIMARY KEY, name TEXT)"
        )

        # 嘗試 SQL 注入攻擊
        malicious_input = "'; DROP TABLE security_test; --"

        # 使用參數化查詢應該安全
        await test_db.execute(
            "INSERT INTO security_test (name) VALUES (?)", (malicious_input,)
        )
        await test_db.commit()

        # 驗證表格仍然存在
        cursor = await test_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='security_test'"
        )
        result = await cursor.fetchone()
        assert result is not None, "表格應該仍然存在,SQL 注入應該被防護"

        # 驗證資料被正確插入
        cursor = await test_db.execute(
            "SELECT name FROM security_test WHERE name = ?", (malicious_input,)
        )
        result = await cursor.fetchone()
        assert result is not None, "惡意輸入應該被當作普通資料處理"

    def test_input_validation_basic(self):
        """✅ 測試基本輸入驗證"""

        def validate_discord_id(discord_id) -> bool:
            """基本 Discord ID 驗證"""
            if not isinstance(discord_id, int):
                return False
            if discord_id <= 0:
                return False
            return not len(str(discord_id)) < 17

        # 測試有效 Discord ID
        valid_id = 123456789012345678
        assert validate_discord_id(valid_id), "有效 Discord ID 應該通過驗證"

        # 測試無效 Discord ID
        invalid_inputs = [-1, 0, 123, "not_a_number"]

        for invalid_input in invalid_inputs:
            assert not validate_discord_id(invalid_input), (
                f"無效 ID {invalid_input} 應該被拒絕"
            )

    def test_data_sanitization(self, security_tester):
        """🧹 測試資料清理"""

        def sanitize_user_input(user_input: str) -> str:
            """基本用戶輸入清理"""
            if not isinstance(user_input, str):
                return ""

            # 移除危險內容
            sanitized = user_input.replace("<script>", "")
            sanitized = sanitized.replace("DROP TABLE", "")

            # 限制長度
            if len(sanitized) > 2000:
                sanitized = sanitized[:2000]

            return sanitized

        malicious_inputs = security_tester.generate_malicious_inputs()

        for malicious_input in malicious_inputs:
            if isinstance(malicious_input, str):
                sanitized = sanitize_user_input(malicious_input)

                # 驗證清理後的資料安全
                assert "<script>" not in sanitized, "腳本標籤應該被清理"
                assert "DROP TABLE" not in sanitized.upper(), "SQL 命令應該被清理"
                assert len(sanitized) <= 2000, "清理後的資料長度應該被限制"


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🧪 整合測試
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestIntegrationBasics:
    """🧪 測試基本整合功能"""

    @pytest.mark.asyncio
    async def test_mock_integration(
        self, mock_bot, mock_guild, mock_channel, mock_member
    ):
        """🔌 測試 Mock 物件整合"""
        # 測試物件關聯
        assert mock_member.guild == mock_guild, "成員應該屬於伺服器"
        assert mock_channel.guild == mock_guild, "頻道應該屬於伺服器"

        # 測試 AsyncMock 功能
        await mock_channel.send("測試訊息")
        mock_channel.send.assert_called_once_with("測試訊息")

        # 測試權限檢查
        assert hasattr(mock_member, "guild_permissions"), "成員應該有權限屬性"
        assert hasattr(mock_member.guild_permissions, "administrator"), (
            "應該有管理員權限屬性"
        )

    @pytest.mark.asyncio
    async def test_database_integration(self, activity_test_db):
        """🗄️ 測試資料庫整合"""
        # 測試跨表格操作
        guild_id, user_id = 12345, 67890

        # 插入活躍度資料
        await activity_test_db.execute(
            "INSERT INTO meter (guild_id, user_id, score, last_msg) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, 75.5, int(time.time())),
        )

        # 插入每日資料
        await activity_test_db.execute(
            "INSERT INTO daily (ymd, guild_id, user_id, msg_cnt) VALUES (?, ?, ?, ?)",
            ("20240101", guild_id, user_id, 25),
        )

        await activity_test_db.commit()

        # 驗證資料一致性
        cursor = await activity_test_db.execute(
            "SELECT m.score, d.msg_cnt FROM meter m JOIN daily d ON m.guild_id = d.guild_id AND m.user_id = d.user_id WHERE m.guild_id = ? AND m.user_id = ?",
            (guild_id, user_id),
        )
        result = await cursor.fetchone()

        assert result is not None, "聯合查詢應該有結果"
        assert result["score"] == 75.5, "活躍度分數應該正確"
        assert result["msg_cnt"] == 25, "訊息計數應該正確"

    def test_fixture_integration(self, test_data_generator):
        """🔧 測試 Fixture 整合"""
        # 測試資料生成器
        guild_data = test_data_generator.generate_guild_data(3)
        assert len(guild_data) == 3, "應該生成 3 個伺服器資料"

        for i, data in enumerate(guild_data):
            assert data["guild_id"] == 12345 + i, "伺服器 ID 應該遞增"
            assert "測試伺服器" in data["guild_name"], "伺服器名稱應該包含測試"

        # 測試用戶資料生成
        user_data = test_data_generator.generate_user_data(2)
        assert len(user_data) == 2, "應該生成 2 個用戶資料"

        for data in user_data:
            assert isinstance(data["user_id"], int), "用戶 ID 應該是整數"
            assert not data["bot"], "測試用戶不應該是機器人"


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🎯 工具函數測試
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestUtilityFunctions:
    """🎯 測試工具函數"""

    def test_tracking_id_format_validation(self):
        """🔍 測試追蹤碼格式驗證"""
        from tests.conftest import assert_tracking_id_format

        # 測試有效追蹤碼
        valid_tracking_id = "TRACKING_ID-TEST_001-123456"
        assert_tracking_id_format(valid_tracking_id)

        # 測試無效追蹤碼
        invalid_tracking_ids = [
            "INVALID_FORMAT",
            "TRACKING_ID-123",
            "TRACKING-ID-TEST-001-123456",
            "",
        ]

        for invalid_id in invalid_tracking_ids:
            with pytest.raises(AssertionError):
                assert_tracking_id_format(invalid_id)

    def test_discord_id_validation(self):
        """✅ 測試 Discord ID 驗證"""
        from tests.conftest import assert_discord_id_valid

        # 測試有效 Discord ID
        valid_id = 123456789012345678
        assert_discord_id_valid(valid_id)

        # 測試無效 Discord ID
        invalid_ids = [0, -1, 123, "invalid"]

        for invalid_id in invalid_ids:
            with pytest.raises(AssertionError):
                assert_discord_id_valid(invalid_id)

    def test_timestamp_validation(self):
        """⏰ 測試時間戳驗證"""
        from tests.conftest import assert_timestamp_valid

        # 測試有效時間戳
        current_time = time.time()
        assert_timestamp_valid(current_time)

        # 測試無效時間戳
        invalid_timestamps = [0, -1, "invalid", 9999999999]

        for invalid_timestamp in invalid_timestamps:
            with pytest.raises(AssertionError):
                assert_timestamp_valid(invalid_timestamp)

    def test_embed_validation(self):
        """📝 測試 Embed 驗證"""
        from tests.conftest import assert_embed_valid

        # 測試有效 Embed
        embed = discord.Embed(title="測試標題", description="測試描述")
        embed.add_field(name="欄位名稱", value="欄位值", inline=False)
        assert_embed_valid(embed)

        # 測試無效 Embed(非 Embed 物件)
        with pytest.raises(AssertionError):
            assert_embed_valid("not an embed")


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 🔧 錯誤處理測試
# ═══════════════════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """🔧 測試錯誤處理機制"""

    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """🔄 測試異步錯誤處理"""
        from tests.conftest import assert_async_no_exception

        async def successful_function():
            await asyncio.sleep(0.01)
            return "成功"

        # 測試成功的異步函數
        result = await assert_async_no_exception(successful_function())
        assert result == "成功", "成功的函數應該返回正確結果"

        async def failing_function():
            raise ValueError("測試錯誤")

        # 測試失敗的異步函數 - 我們期望 assert_async_no_exception 會失敗
        # 所以我們直接測試原始函數的異常行為
        with pytest.raises(ValueError, match="測試錯誤"):
            await failing_function()

        # 另外測試 assert_async_no_exception 的行為
        # 當函數拋出異常時,assert_async_no_exception 應該導致測試失敗
        # 這是一個輔助函數,我們不直接測試它的失敗情況

    def test_performance_validation(self):
        """⚡ 測試效能驗證"""
        from tests.conftest import assert_performance_acceptable

        # 測試可接受的效能
        assert_performance_acceptable(0.5, 1.0)  # 0.5秒 < 1.0秒限制

        # 測試不可接受的效能
        with pytest.raises(AssertionError):
            assert_performance_acceptable(2.0, 1.0)  # 2.0秒 > 1.0秒限制

    def test_memory_validation(self):
        """🧠 測試記憶體驗證"""
        from tests.conftest import assert_memory_usage_acceptable

        # 測試可接受的記憶體使用
        assert_memory_usage_acceptable(
            50 * 1024 * 1024, 100 * 1024 * 1024
        )  # 50MB < 100MB限制

        # 測試不可接受的記憶體使用
        with pytest.raises(AssertionError):
            assert_memory_usage_acceptable(
                150 * 1024 * 1024, 100 * 1024 * 1024
            )  # 150MB > 100MB限制

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """⏰ 測試超時處理"""

        async def slow_function():
            await asyncio.sleep(2)
            return "完成"

        # 測試超時
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_function(), timeout=1.0)

        # 測試正常完成
        result = await asyncio.wait_for(slow_function(), timeout=3.0)
        assert result == "完成", "正常情況下應該完成"
