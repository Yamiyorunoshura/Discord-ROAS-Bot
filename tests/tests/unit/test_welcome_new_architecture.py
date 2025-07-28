"""
新架構歡迎模組測試 - 修復測試導入和覆蓋率問題

此模組測試新架構的歡迎功能,包括:
- 配置管理測試
- 資料存取層測試
- UI組件測試
- 服務層測試
- 整合測試

符合 TASK-005: 測試環境建立與修復的要求
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# 修復導入路徑問題
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 導入測試配置

# 導入要測試的模組
from src.cogs.welcome.config.config import (
    WelcomeGuildConfig,
    WelcomeImageSettings,
    WelcomeMessageSettings,
)
from src.cogs.welcome.database.repository import WelcomeRepositoryException
from src.cogs.welcome.ui.components.buttons import WelcomeControlButtons
from src.cogs.welcome.ui.components.modals import (
    WelcomeChannelModal,
    WelcomeMessageModal,
    WelcomeTitleModal,
)
from src.cogs.welcome.ui.components.selectors import WelcomeSettingsSelector


class TestWelcomeConfig:
    """測試歡迎配置管理器"""

    @pytest.mark.unit
    def test_welcome_config_initialization(self, welcome_config):
        """測試配置管理器初始化"""
        assert welcome_config is not None
        assert hasattr(welcome_config, "_settings")
        assert hasattr(welcome_config, "_logger")

    @pytest.mark.unit
    def test_get_default_settings(self, welcome_config):
        """測試獲取預設設定"""
        default_settings = welcome_config.get_default_settings()

        assert isinstance(default_settings, dict)
        assert "enabled" in default_settings
        assert "channel_id" in default_settings
        assert "message" in default_settings
        assert "title" in default_settings
        assert "description" in default_settings
        assert not default_settings["enabled"]
        assert "歡迎" in default_settings["message"]

    @pytest.mark.unit
    def test_get_default_guild_config(self, welcome_config):
        """測試獲取預設伺服器配置"""
        guild_id = 123456789
        config = welcome_config.get_default_guild_config(guild_id)

        assert isinstance(config, WelcomeGuildConfig)
        assert config.guild_id == guild_id
        assert isinstance(config.message_settings, WelcomeMessageSettings)
        assert isinstance(config.image_settings, WelcomeImageSettings)

    @pytest.mark.unit
    def test_validate_settings_valid(self, welcome_config):
        """測試驗證有效設定"""
        valid_settings = {
            "enabled": True,
            "channel_id": 123456789,
            "message": "歡迎消息",
            "title": "標題",
            "description": "描述",
            "avatar_size": 128,
            "avatar_x": 100,
            "avatar_y": 100,
        }

        is_valid, errors = welcome_config.validate_settings(valid_settings)
        assert is_valid
        assert len(errors) == 0

    @pytest.mark.unit
    def test_validate_settings_invalid(self, welcome_config):
        """測試驗證無效設定"""
        invalid_settings = {
            "enabled": "not_boolean",  # 類型錯誤
            "avatar_size": -10,  # 範圍錯誤
            "message": "x" * 3000,  # 長度超限
            "unknown_field": "value",  # 不支援的欄位
        }

        is_valid, errors = welcome_config.validate_settings(invalid_settings)
        assert not is_valid
        assert len(errors) > 0

    @pytest.mark.unit
    def test_normalize_settings(self, welcome_config):
        """測試設定正規化"""
        input_settings = {
            "enabled": True,
            "channel_id": 123456789,
            "unknown_field": "should_be_ignored",
        }

        normalized = welcome_config.normalize_settings(input_settings)

        assert "enabled" in normalized
        assert "channel_id" in normalized
        assert "unknown_field" not in normalized
        assert normalized["enabled"]
        assert normalized["channel_id"] == 123456789

        # 應該包含所有預設欄位
        default_settings = welcome_config.get_default_settings()
        for key in default_settings:
            assert key in normalized

    @pytest.mark.unit
    def test_directory_management(self, welcome_config):
        """測試目錄管理功能"""
        # 測試獲取背景圖片目錄
        bg_dir = welcome_config.get_welcome_bg_directory()
        assert isinstance(bg_dir, Path)

        # 測試獲取字體目錄
        fonts_dir = welcome_config.get_fonts_directory()
        assert isinstance(fonts_dir, Path)

        # 測試獲取可用字體
        fonts = welcome_config.get_available_fonts()
        assert isinstance(fonts, list)

    @pytest.mark.unit
    async def test_health_check(self, welcome_config):
        """測試健康檢查"""
        health_data = await welcome_config.health_check()

        assert isinstance(health_data, dict)
        assert "service_name" in health_data
        assert "status" in health_data
        assert "directories" in health_data
        assert "fonts" in health_data
        assert health_data["service_name"] == "WelcomeConfig"


class TestWelcomeGuildConfig:
    """測試伺服器配置數據模型"""

    @pytest.mark.unit
    def test_guild_config_creation(self):
        """測試伺服器配置創建"""
        guild_id = 123456789
        config = WelcomeGuildConfig(guild_id=guild_id)

        assert config.guild_id == guild_id
        assert isinstance(config.message_settings, WelcomeMessageSettings)
        assert isinstance(config.image_settings, WelcomeImageSettings)

    @pytest.mark.unit
    def test_to_dict_conversion(self):
        """測試轉為字典格式"""
        guild_id = 123456789
        config = WelcomeGuildConfig(guild_id=guild_id)

        data = config.to_dict()

        assert isinstance(data, dict)
        assert data["guild_id"] == guild_id
        assert "enabled" in data
        assert "channel_id" in data
        assert "message" in data
        assert "title" in data
        assert "description" in data

    @pytest.mark.unit
    def test_from_dict_creation(self):
        """測試從字典創建配置"""
        data = {
            "guild_id": 123456789,
            "enabled": True,
            "channel_id": 555666777,
            "message": "自訂歡迎消息",
            "title": "自訂標題",
            "description": "自訂描述",
            "avatar_size": 150,
            "avatar_x": 200,
            "avatar_y": 200,
        }

        config = WelcomeGuildConfig.from_dict(data)

        assert config.guild_id == data["guild_id"]
        assert config.message_settings.enabled == data["enabled"]
        assert config.message_settings.channel_id == data["channel_id"]
        assert config.message_settings.message == data["message"]
        assert config.image_settings.avatar_size == data["avatar_size"]


class TestWelcomeRepository:
    """測試歡迎資料存取層"""

    @pytest.mark.unit
    @pytest.mark.database
    async def test_repository_initialization(self, welcome_repository):
        """測試資料存取層初始化"""
        assert welcome_repository is not None
        assert hasattr(welcome_repository, "_db")
        assert hasattr(welcome_repository, "_logger")
        assert hasattr(welcome_repository, "_monitor")
        assert hasattr(welcome_repository, "_config")

    @pytest.mark.unit
    @pytest.mark.database
    async def test_get_settings_default(self, welcome_repository, test_data_factory):
        """測試獲取預設設定"""
        guild_id = 123456789

        # 模擬數據庫返回空結果(無現有設定)
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None

        connection_mock = AsyncMock()
        connection_mock.execute.return_value = mock_cursor

        welcome_repository._db.get_connection.return_value.__aenter__.return_value = (
            connection_mock
        )

        settings = await welcome_repository.get_settings(guild_id)

        assert isinstance(settings, dict)
        assert "guild_id" in settings
        assert settings["guild_id"] == guild_id

    @pytest.mark.unit
    @pytest.mark.database
    async def test_update_settings_success(self, welcome_repository, test_data_factory):
        """測試更新設定成功"""
        guild_id = 123456789
        test_settings = test_data_factory.create_welcome_settings(guild_id)

        # 模擬數據庫操作
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None  # 記錄不存在,需要插入

        connection_mock = AsyncMock()
        connection_mock.execute.return_value = mock_cursor
        connection_mock.commit = AsyncMock()

        welcome_repository._db.get_connection.return_value.__aenter__.return_value = (
            connection_mock
        )

        # 模擬配置驗證通過
        welcome_repository._config.validate_settings.return_value = (True, [])
        welcome_repository._config.normalize_settings.return_value = test_settings

        result = await welcome_repository.update_settings(guild_id, test_settings)

        assert result
        connection_mock.commit.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.database
    async def test_update_settings_validation_failure(
        self, welcome_repository, test_data_factory
    ):
        """測試更新設定驗證失敗"""
        guild_id = 123456789
        invalid_settings = {"enabled": "not_boolean"}

        # 模擬配置驗證失敗
        welcome_repository._config.validate_settings.return_value = (
            False,
            ["類型錯誤"],
        )

        with pytest.raises(WelcomeRepositoryException):
            await welcome_repository.update_settings(guild_id, invalid_settings)

    @pytest.mark.unit
    @pytest.mark.database
    async def test_background_operations(self, welcome_repository):
        """測試背景圖片操作"""
        guild_id = 123456789
        bg_path = "/test/path/bg.png"
        filename = "test_bg.png"
        file_size = 1024

        # 模擬數據庫操作
        connection_mock = AsyncMock()
        connection_mock.execute = AsyncMock()
        connection_mock.commit = AsyncMock()

        welcome_repository._db.get_connection.return_value.__aenter__.return_value = (
            connection_mock
        )

        # 測試更新背景
        result = await welcome_repository.update_background(
            guild_id, bg_path, filename, file_size
        )
        assert result

        # 測試獲取背景路徑
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (bg_path,)
        connection_mock.execute.return_value = mock_cursor

        retrieved_path = await welcome_repository.get_background_path(guild_id)
        assert retrieved_path == bg_path

        # 測試移除背景
        result = await welcome_repository.remove_background(guild_id)
        assert result

    @pytest.mark.unit
    @pytest.mark.database
    async def test_statistics_operations(self, welcome_repository):
        """測試統計數據操作"""
        guild_id = 123456789

        # 模擬數據庫操作
        connection_mock = AsyncMock()
        connection_mock.execute = AsyncMock()
        connection_mock.commit = AsyncMock()

        welcome_repository._db.get_connection.return_value.__aenter__.return_value = (
            connection_mock
        )

        # 測試記錄統計
        await welcome_repository.record_welcome_stat(
            guild_id, welcomes_sent=1, images_generated=1
        )

        # 驗證數據庫調用
        assert connection_mock.execute.call_count >= 2  # INSERT和UPDATE
        connection_mock.commit.assert_called()

    @pytest.mark.unit
    @pytest.mark.database
    async def test_data_integrity_validation(self, welcome_repository):
        """測試資料完整性驗證"""
        # 模擬數據庫查詢結果
        connection_mock = AsyncMock()

        # 模擬檢查孤立記錄的查詢
        mock_cursor1 = AsyncMock()
        mock_cursor1.fetchone.return_value = (0,)  # 無孤立背景記錄

        mock_cursor2 = AsyncMock()
        mock_cursor2.fetchone.return_value = (0,)  # 無孤立統計記錄

        mock_cursor3 = AsyncMock()
        mock_cursor3.fetchone.return_value = (5,)  # 總伺服器數

        mock_cursor4 = AsyncMock()
        mock_cursor4.fetchone.return_value = (3,)  # 啟用的伺服器數

        mock_cursor5 = AsyncMock()
        mock_cursor5.fetchone.return_value = (2,)  # 背景圖片數

        mock_cursor6 = AsyncMock()
        mock_cursor6.fetchone.return_value = (4,)  # 有統計的伺服器數

        connection_mock.execute.side_effect = [
            mock_cursor1,
            mock_cursor2,
            mock_cursor3,
            mock_cursor4,
            mock_cursor5,
            mock_cursor6,
        ]

        welcome_repository._db.get_connection.return_value.__aenter__.return_value = (
            connection_mock
        )

        integrity_report = await welcome_repository.validate_data_integrity()

        assert isinstance(integrity_report, dict)
        assert "status" in integrity_report
        assert "issues" in integrity_report
        assert "statistics" in integrity_report
        assert integrity_report["status"] == "healthy"

    @pytest.mark.unit
    @pytest.mark.database
    async def test_health_check(self, welcome_repository):
        """測試健康檢查"""
        # 模擬成功的健康檢查
        welcome_repository._initialized = True

        # 模擬表計數查詢
        connection_mock = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = (10,)  # 表中有10條記錄
        connection_mock.execute.return_value = mock_cursor

        welcome_repository._db.get_connection.return_value.__aenter__.return_value = (
            connection_mock
        )

        # 模擬完整性檢查
        welcome_repository.validate_data_integrity = AsyncMock(
            return_value={"status": "healthy", "issues": []}
        )

        health_data = await welcome_repository.health_check()

        assert isinstance(health_data, dict)
        assert health_data["service_name"] == "WelcomeRepository"
        assert health_data["status"] == "healthy"
        assert "database" in health_data
        assert "tables" in health_data
        assert "data_integrity" in health_data


class TestWelcomeUIComponents:
    """測試歡迎UI組件"""

    @pytest.mark.unit
    def test_welcome_channel_modal_creation(self):
        """測試歡迎頻道模態框創建"""
        mock_service = MagicMock()
        mock_logger = MagicMock()

        modal = WelcomeChannelModal(mock_service, mock_logger)

        assert modal is not None
        assert modal.title == "設定歡迎頻道"
        assert hasattr(modal, "channel_input")
        assert modal._welcome_service == mock_service
        assert modal._logger == mock_logger

    @pytest.mark.unit
    def test_welcome_message_modal_creation(self):
        """測試歡迎訊息模態框創建"""
        mock_service = MagicMock()
        mock_logger = MagicMock()

        modal = WelcomeMessageModal(mock_service, mock_logger)

        assert modal is not None
        assert modal.title == "設定歡迎訊息"
        assert hasattr(modal, "message_input")
        assert modal._welcome_service == mock_service
        assert modal._logger == mock_logger

    @pytest.mark.unit
    def test_welcome_title_modal_creation(self):
        """測試歡迎標題模態框創建"""
        mock_service = MagicMock()
        mock_logger = MagicMock()

        modal = WelcomeTitleModal(mock_service, mock_logger)

        assert modal is not None
        assert modal.title == "設定圖片標題"
        assert hasattr(modal, "title_input")
        assert modal._welcome_service == mock_service
        assert modal._logger == mock_logger

    @pytest.mark.unit
    def test_welcome_control_buttons_creation(self):
        """測試歡迎控制按鈕創建"""
        mock_service = MagicMock()
        mock_renderer = MagicMock()
        mock_logger = MagicMock()
        mock_monitor = MagicMock()

        buttons = WelcomeControlButtons(
            mock_service, mock_renderer, mock_logger, mock_monitor
        )

        assert buttons is not None
        assert hasattr(buttons, "_welcome_service")
        assert hasattr(buttons, "_renderer")
        assert hasattr(buttons, "_logger")
        assert hasattr(buttons, "_monitor")

        # 測試獲取按鈕列表
        button_list = buttons.get_buttons()
        assert isinstance(button_list, list)
        assert len(button_list) > 0

    @pytest.mark.unit
    def test_welcome_settings_selector_creation(self):
        """測試歡迎設定選擇器創建"""
        mock_service = MagicMock()
        mock_logger = MagicMock()

        selector = WelcomeSettingsSelector(mock_service, mock_logger)

        assert selector is not None
        assert hasattr(selector, "_welcome_service")
        assert hasattr(selector, "_logger")
        assert selector.placeholder == "選擇要調整的設定項目"
        assert len(selector.options) > 0


class TestWelcomeIntegration:
    """測試歡迎模組整合功能"""

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_full_welcome_configuration_flow(
        self, welcome_config, welcome_repository, test_data_factory, mock_discord_guild
    ):
        """測試完整的歡迎配置流程"""
        guild_id = mock_discord_guild.id

        # 1. 創建測試設定
        test_settings = test_data_factory.create_welcome_settings(guild_id)

        # 2. 驗證設定
        is_valid, errors = welcome_config.validate_settings(test_settings)
        assert is_valid, f"設定驗證失敗: {errors}"

        # 3. 正規化設定
        normalized_settings = welcome_config.normalize_settings(test_settings)
        assert (
            "guild_id" not in normalized_settings
        )  # normalize_settings不應該包含guild_id

        # 4. 模擬資料庫操作成功
        welcome_repository._config.validate_settings.return_value = (True, [])
        welcome_repository._config.normalize_settings.return_value = test_settings

        connection_mock = AsyncMock()
        connection_mock.execute = AsyncMock()
        connection_mock.commit = AsyncMock()
        welcome_repository._db.get_connection.return_value.__aenter__.return_value = (
            connection_mock
        )

        # 5. 更新設定
        result = await welcome_repository.update_settings(guild_id, test_settings)
        assert result

    @pytest.mark.integration
    @pytest.mark.performance
    async def test_repository_performance(
        self, welcome_repository, test_data_factory, performance_monitor
    ):
        """測試資料存取層性能"""
        guild_id = 123456789
        test_settings = test_data_factory.create_welcome_settings(guild_id)

        # 模擬數據庫操作
        welcome_repository._config.validate_settings.return_value = (True, [])
        welcome_repository._config.normalize_settings.return_value = test_settings

        connection_mock = AsyncMock()
        connection_mock.execute = AsyncMock()
        connection_mock.commit = AsyncMock()
        welcome_repository._db.get_connection.return_value.__aenter__.return_value = (
            connection_mock
        )

        # 性能測試
        performance_monitor.start()

        # 執行多次操作
        for _ in range(10):
            await welcome_repository.update_settings(guild_id, test_settings)

        performance_monitor.stop()

        # 驗證性能在可接受範圍內 (10次操作應該在1秒內完成)
        performance_monitor.assert_performance(1.0)

    @pytest.mark.integration
    @pytest.mark.database
    async def test_error_handling_and_recovery(
        self, welcome_repository, test_data_factory
    ):
        """測試錯誤處理和恢復"""
        guild_id = 123456789
        test_settings = test_data_factory.create_welcome_settings(guild_id)

        # 模擬數據庫連接錯誤
        welcome_repository._db.get_connection.side_effect = Exception("數據庫連接失敗")

        # 驗證異常被正確拋出
        with pytest.raises(WelcomeRepositoryException):
            await welcome_repository.update_settings(guild_id, test_settings)

        # 模擬配置驗證錯誤
        welcome_repository._db.get_connection.side_effect = None  # 重置
        welcome_repository._config.validate_settings.return_value = (
            False,
            ["驗證錯誤"],
        )

        with pytest.raises(WelcomeRepositoryException):
            await welcome_repository.update_settings(guild_id, test_settings)


class TestWelcomeCoverage:
    """測試覆蓋率相關測試"""

    @pytest.mark.unit
    def test_welcome_config_edge_cases(self, welcome_config):
        """測試配置管理器邊界情況"""
        # 測試空設定
        empty_settings = {}
        normalized = welcome_config.normalize_settings(empty_settings)
        assert isinstance(normalized, dict)

        # 測試None值處理
        none_settings = {"enabled": None, "channel_id": None}
        is_valid, errors = welcome_config.validate_settings(none_settings)
        # None值應該被接受(會被預設值替換)

        # 測試極大數值
        large_settings = {
            "avatar_size": 999999,
            "avatar_x": 999999,
            "title_font_size": 999999,
        }
        is_valid, errors = welcome_config.validate_settings(large_settings)
        assert not is_valid  # 應該超出範圍限制
        assert len(errors) > 0

    @pytest.mark.unit
    def test_guild_config_edge_cases(self):
        """測試伺服器配置邊界情況"""
        # 測試空字典創建
        empty_data = {"guild_id": 123456789}
        config = WelcomeGuildConfig.from_dict(empty_data)
        assert config.guild_id == 123456789

        # 測試包含額外欄位的字典
        extra_data = {
            "guild_id": 123456789,
            "unknown_field": "should_be_ignored",
            "enabled": True,
        }
        config = WelcomeGuildConfig.from_dict(extra_data)
        assert config.guild_id == 123456789
        assert config.message_settings.enabled

    @pytest.mark.unit
    @pytest.mark.database
    async def test_repository_error_scenarios(self, welcome_repository):
        """測試資料存取層錯誤場景"""
        guild_id = 123456789

        # 測試數據庫查詢異常
        welcome_repository._db.get_connection.side_effect = Exception("查詢失敗")

        # 獲取設定應該拋出異常
        with pytest.raises(WelcomeRepositoryException):
            await welcome_repository.get_settings(guild_id)

        # 統計操作應該靜默失敗(記錄警告但不拋出異常)
        await welcome_repository.record_welcome_stat(guild_id, welcomes_sent=1)
        # 這應該不會拋出異常,而是記錄警告

    @pytest.mark.unit
    async def test_async_context_managers(self, welcome_repository):
        """測試異步上下文管理器"""
        # 測試正常的異步上下文使用
        mock_connection = AsyncMock()
        welcome_repository._db.get_connection.return_value = mock_connection

        # 確保異步上下文管理器被正確使用
        async with welcome_repository._db.get_connection() as conn:
            assert conn == mock_connection.__aenter__.return_value


if __name__ == "__main__":
    # 運行測試
    pytest.main([__file__, "-v", "--tb=short"])
