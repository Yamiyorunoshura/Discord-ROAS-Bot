"""成就系統主 Cog 單元測試.

測試 AchievementCog 的核心功能：
- Cog 初始化和清理
- Slash Command 註冊和處理
- 依賴注入整合
- 錯誤處理
"""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
import pytest_asyncio
from discord.ext import commands

from src.cogs.achievement.main.main import AchievementCog


class TestAchievementCog:
    """成就系統主 Cog 測試類別."""

    @pytest.fixture
    def mock_bot(self):
        """模擬 Discord Bot."""
        bot = MagicMock(spec=commands.Bot)
        bot.loop = AsyncMock()
        bot.loop.create_task = MagicMock()
        return bot

    @pytest.fixture
    def mock_database_pool(self):
        """模擬資料庫連線池."""
        return MagicMock()

    @pytest.fixture
    def mock_service_container(self):
        """模擬服務容器."""
        container = MagicMock()
        container._initialize_services = AsyncMock()
        container._cleanup_services = AsyncMock()
        container.achievement_service = MagicMock()
        container.repository = MagicMock()
        container.progress_tracker = MagicMock()
        container.trigger_engine = MagicMock()
        return container

    @pytest_asyncio.fixture
    async def achievement_cog(self, mock_bot):
        """建立成就系統 Cog 實例."""
        with patch('src.cogs.achievement.main.main.get_database_pool') as mock_get_db:
            mock_get_db.return_value = MagicMock()

            with patch('src.cogs.achievement.main.main.AchievementServiceContainer') as mock_container_class:
                mock_container_class.return_value._initialize_services = AsyncMock()
                mock_container_class.return_value.achievement_service = MagicMock()
                mock_container_class.return_value.repository = MagicMock()
                mock_container_class.return_value.progress_tracker = MagicMock()
                mock_container_class.return_value.trigger_engine = MagicMock()

                cog = AchievementCog(mock_bot)
                # 模擬初始化完成
                cog._initialized = True
                cog.achievement_service = MagicMock()
                cog._service_container = mock_container_class.return_value

                return cog

    @pytest.mark.asyncio
    async def test_initialization(self, mock_bot, mock_database_pool):
        """測試 Cog 初始化."""
        with patch('src.cogs.achievement.main.main.get_database_pool') as mock_get_db:
            mock_get_db.return_value = mock_database_pool

            with patch('src.cogs.achievement.main.main.AchievementServiceContainer') as mock_container_class:
                mock_container = mock_container_class.return_value
                mock_container._initialize_services = AsyncMock()
                mock_container.achievement_service = MagicMock()
                mock_container.repository = MagicMock()
                mock_container.progress_tracker = MagicMock()
                mock_container.trigger_engine = MagicMock()

                cog = AchievementCog(mock_bot)
                await cog.initialize()

                # 驗證初始化流程
                mock_get_db.assert_called_once()
                mock_container_class.assert_called_once_with(mock_database_pool)
                mock_container._initialize_services.assert_called_once()
                assert cog.achievement_service is not None

    @pytest.mark.asyncio
    async def test_initialization_failure(self, mock_bot):
        """測試初始化失敗處理."""
        with patch('src.cogs.achievement.main.main.get_database_pool') as mock_get_db:
            mock_get_db.side_effect = Exception("Database connection failed")

            cog = AchievementCog(mock_bot)

            with pytest.raises(Exception, match="Database connection failed"):
                await cog.initialize()

    @pytest.mark.asyncio
    async def test_achievement_command_success(self, achievement_cog):
        """測試成就指令成功執行."""
        # 建立模擬 interaction
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 12345

        mock_user = MagicMock(spec=discord.Member)
        mock_user.id = 67890

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.guild = mock_guild
        mock_interaction.user = mock_user
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.original_response = AsyncMock()

        # 模擬面板
        with patch('src.cogs.achievement.main.main.AchievementPanel') as mock_panel_class:
            mock_panel = mock_panel_class.return_value
            mock_panel.start = AsyncMock()

            await achievement_cog.achievement_command(mock_interaction)

            # 驗證執行流程
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_panel_class.assert_called_once_with(
                bot=achievement_cog.bot,
                achievement_service=achievement_cog.achievement_service,
                guild_id=12345,
                user_id=67890
            )
            mock_panel.start.assert_called_once_with(mock_interaction)

    @pytest.mark.asyncio
    async def test_achievement_command_no_guild(self, achievement_cog):
        """測試成就指令在私訊中使用。"""
        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.guild = None
        mock_interaction.response.send_message = AsyncMock()

        await achievement_cog.achievement_command(mock_interaction)

        mock_interaction.response.send_message.assert_called_once_with(
            "❌ 此指令只能在伺服器中使用",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_achievement_command_invalid_user(self, achievement_cog):
        """測試成就指令用戶類型無效。"""
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 12345

        mock_user = MagicMock(spec=discord.User)  # 不是 Member
        mock_user.id = 67890

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.guild = mock_guild
        mock_interaction.user = mock_user
        mock_interaction.response.send_message = AsyncMock()

        await achievement_cog.achievement_command(mock_interaction)

        mock_interaction.response.send_message.assert_called_once_with(
            "❌ 無法獲取用戶資訊",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_achievement_command_panel_error(self, achievement_cog):
        """測試成就指令面板載入失敗。"""
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 12345

        mock_user = MagicMock(spec=discord.Member)
        mock_user.id = 67890

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.guild = mock_guild
        mock_interaction.user = mock_user
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.response.is_done.return_value = True
        mock_interaction.followup.send = AsyncMock()

        # 模擬面板載入失敗
        with patch('src.cogs.achievement.main.main.AchievementPanel') as mock_panel_class:
            mock_panel_class.side_effect = Exception("Panel initialization failed")

            await achievement_cog.achievement_command(mock_interaction)

            # 驗證錯誤處理
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            assert call_args[1]['ephemeral'] is True

            # 檢查是否發送了錯誤 embed
            embed = call_args[1]['embed']
            assert "載入失敗" in embed.title

    @pytest.mark.asyncio
    async def test_cleanup(self, achievement_cog, mock_service_container):
        """測試 Cog 清理。"""
        achievement_cog._service_container = mock_service_container

        await achievement_cog.cleanup()

        mock_service_container._cleanup_services.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_no_container(self, achievement_cog):
        """測試沒有服務容器時的清理。"""
        achievement_cog._service_container = None

        # 應該不會拋出異常
        await achievement_cog.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_error(self, achievement_cog, mock_service_container):
        """測試清理時發生錯誤。"""
        mock_service_container._cleanup_services.side_effect = Exception("Cleanup failed")
        achievement_cog._service_container = mock_service_container

        # 應該不會拋出異常，但會記錄錯誤
        await achievement_cog.cleanup()

    def test_service_registration(self, achievement_cog, mock_service_container):
        """測試服務註冊。"""
        achievement_cog._service_container = mock_service_container
        achievement_cog.register_instance = MagicMock()

        # 手動呼叫服務註冊方法（通常在初始化時呼叫）
        import asyncio
        asyncio.run(achievement_cog._register_services())

        # 驗證所有服務都被註冊
        assert achievement_cog.register_instance.call_count == 4  # 4 個服務

    @pytest.mark.asyncio
    async def test_setup_function(self, mock_bot):
        """測試 setup 函數。"""
        with patch('src.cogs.achievement.main.main.AchievementCog') as mock_cog_class:
            mock_cog = mock_cog_class.return_value
            mock_bot.add_cog = AsyncMock()

            from src.cogs.achievement.main.main import setup
            await setup(mock_bot)

            mock_cog_class.assert_called_once_with(mock_bot)
            mock_bot.add_cog.assert_called_once_with(mock_cog)

    @pytest.mark.asyncio
    async def test_setup_function_error(self, mock_bot):
        """測試 setup 函數錯誤處理。"""
        mock_bot.add_cog = AsyncMock(side_effect=Exception("Add cog failed"))

        from src.cogs.achievement.main.main import setup

        with pytest.raises(Exception, match="Add cog failed"):
            await setup(mock_bot)


class TestAchievementCogIntegration:
    """成就系統 Cog 整合測試."""

    @pytest.mark.asyncio
    async def test_full_initialization_flow(self):
        """測試完整初始化流程。"""
        mock_bot = MagicMock(spec=commands.Bot)
        mock_bot.loop = AsyncMock()
        mock_bot.loop.create_task = MagicMock()

        with patch('src.cogs.achievement.main.main.get_database_pool') as mock_get_db:
            mock_get_db.return_value = MagicMock()

            with patch('src.cogs.achievement.main.main.AchievementServiceContainer') as mock_container_class:
                mock_container = mock_container_class.return_value
                mock_container._initialize_services = AsyncMock()
                mock_container.achievement_service = MagicMock()
                mock_container.repository = MagicMock()
                mock_container.progress_tracker = MagicMock()
                mock_container.trigger_engine = MagicMock()

                # 建立 Cog
                cog = AchievementCog(mock_bot)

                # 驗證建構函數設置
                assert cog.bot is mock_bot
                assert cog.achievement_service is None
                assert cog._service_container is None

                # 執行初始化
                await cog.initialize()

                # 驗證初始化結果
                assert cog.achievement_service is not None
                assert cog._service_container is not None

                # 測試清理
                await cog.cleanup()
                mock_container._cleanup_services.assert_called_once()
