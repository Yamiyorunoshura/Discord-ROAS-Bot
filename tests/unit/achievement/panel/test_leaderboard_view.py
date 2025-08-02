"""測試排行榜視圖模組.

測試 LeaderboardView 類別的功能和邏輯。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.cogs.achievement.panel.views import LeaderboardView
from src.cogs.achievement.services.achievement_service import AchievementService


class TestLeaderboardView:
    """LeaderboardView 測試類別."""

    @pytest.fixture
    def mock_achievement_service(self) -> AsyncMock:
        """創建模擬的成就服務."""
        service = AsyncMock(spec=AchievementService)
        return service

    @pytest.fixture
    def leaderboard_view(self, mock_achievement_service) -> LeaderboardView:
        """創建排行榜視圖實例."""
        return LeaderboardView(
            achievement_service=mock_achievement_service,
            guild_id=123456789,
            user_id=987654321
        )

    @pytest.fixture
    def mock_bot(self) -> MagicMock:
        """創建模擬的 Discord 機器人."""
        bot = MagicMock(spec=discord.Client)
        guild = MagicMock()
        guild.id = 123456789
        bot.get_guild.return_value = guild

        # 模擬成員
        member = MagicMock()
        member.display_name = "測試用戶"
        guild.get_member.return_value = member

        return bot

    def test_initialization(self, leaderboard_view):
        """測試排行榜視圖初始化."""
        assert leaderboard_view._current_page == 0
        assert leaderboard_view._page_size == 10
        assert leaderboard_view._selected_type == "count"
        assert leaderboard_view._total_pages == 0
        assert leaderboard_view._selected_category_id is None

    def test_set_page(self, leaderboard_view):
        """測試設置頁面功能."""
        leaderboard_view._total_pages = 5

        # 正常設置頁面
        leaderboard_view.set_page(2)
        assert leaderboard_view.get_current_page() == 2
        assert not leaderboard_view._cache_valid

        # 超出範圍的頁面
        leaderboard_view.set_page(10)
        assert leaderboard_view.get_current_page() == 4  # 最大頁面

        # 負數頁面
        leaderboard_view.set_page(-1)
        assert leaderboard_view.get_current_page() == 0  # 最小頁面

    def test_set_leaderboard_type(self, leaderboard_view):
        """測試設置排行榜類型功能."""
        # 設置為點數排行榜
        leaderboard_view.set_leaderboard_type("points")
        assert leaderboard_view.get_selected_type() == "points"
        assert leaderboard_view.get_current_page() == 0
        assert not leaderboard_view._cache_valid

        # 設置為分類排行榜
        leaderboard_view.set_leaderboard_type("category", 42)
        assert leaderboard_view.get_selected_type() == "category"
        assert leaderboard_view.get_selected_category_id() == 42
        assert leaderboard_view.get_current_page() == 0

    def test_has_next_previous_page(self, leaderboard_view):
        """測試分頁檢查功能."""
        leaderboard_view._total_pages = 5

        # 第一頁
        leaderboard_view._current_page = 0
        assert not leaderboard_view.has_previous_page()
        assert leaderboard_view.has_next_page()

        # 中間頁面
        leaderboard_view._current_page = 2
        assert leaderboard_view.has_previous_page()
        assert leaderboard_view.has_next_page()

        # 最後一頁
        leaderboard_view._current_page = 4
        assert leaderboard_view.has_previous_page()
        assert not leaderboard_view.has_next_page()

    def test_get_type_display_name(self, leaderboard_view):
        """測試獲取排行榜類型顯示名稱."""
        assert leaderboard_view._get_type_display_name("count") == "成就總數"
        assert leaderboard_view._get_type_display_name("points") == "成就點數"
        assert leaderboard_view._get_type_display_name("category_1", 1) == "分類成就 (1)"
        assert leaderboard_view._get_type_display_name("unknown") == "成就總數"

    def test_get_value_display_name(self, leaderboard_view):
        """測試獲取數值顯示名稱."""
        assert leaderboard_view._get_value_display_name("count") == "個成就"
        assert leaderboard_view._get_value_display_name("points") == "點"
        assert leaderboard_view._get_value_display_name("category_1") == "個成就"

    def test_get_rank_emoji(self, leaderboard_view):
        """測試獲取排名表情符號."""
        assert leaderboard_view._get_rank_emoji(1) == "🥇"
        assert leaderboard_view._get_rank_emoji(2) == "🥈"
        assert leaderboard_view._get_rank_emoji(3) == "🥉"
        assert leaderboard_view._get_rank_emoji(5) == "🏅"
        assert leaderboard_view._get_rank_emoji(15) == "🔸"

    @pytest.mark.asyncio
    async def test_get_user_display_name(self, leaderboard_view, mock_bot):
        """測試獲取用戶顯示名稱."""
        # 成功獲取成員名稱
        display_name = await leaderboard_view._get_user_display_name(mock_bot, 987654321)
        assert display_name == "測試用戶"

        # 無法獲取成員時返回用戶ID
        mock_bot.get_guild.return_value.get_member.return_value = None
        display_name = await leaderboard_view._get_user_display_name(mock_bot, 999)
        assert display_name == "用戶999"

    @pytest.mark.asyncio
    async def test_load_data_count_leaderboard(self, leaderboard_view, mock_achievement_service):
        """測試載入成就總數排行榜資料."""
        # 設置模擬資料
        mock_leaderboard_data = [
            {"user_id": 111, "value": 15},
            {"user_id": 222, "value": 12},
            {"user_id": 333, "value": 10},
        ]
        mock_user_rank = {"rank": 5, "value": 8}

        mock_achievement_service.get_leaderboard_by_count.return_value = mock_leaderboard_data
        mock_achievement_service.get_user_rank.return_value = mock_user_rank

        # 測試載入資料
        data = await leaderboard_view.load_data(page=0, type="count")

        # 驗證結果
        assert data["leaderboard_data"] == mock_leaderboard_data[:10]
        assert data["current_page"] == 0
        assert data["leaderboard_type"] == "count"
        assert data["user_rank"] == mock_user_rank
        assert data["stats"]["total_users"] == 3

        # 驗證服務調用
        mock_achievement_service.get_leaderboard_by_count.assert_called_once_with(
            limit=10
        )
        mock_achievement_service.get_user_rank.assert_called_once_with(987654321, "count")

    @pytest.mark.asyncio
    async def test_load_data_points_leaderboard(self, leaderboard_view, mock_achievement_service):
        """測試載入成就點數排行榜資料."""
        # 設置模擬資料
        mock_leaderboard_data = [
            {"user_id": 111, "value": 150},
            {"user_id": 222, "value": 120},
        ]
        mock_user_rank = {"rank": 3, "value": 90}

        mock_achievement_service.get_leaderboard_by_points.return_value = mock_leaderboard_data
        mock_achievement_service.get_user_rank.return_value = mock_user_rank

        # 測試載入資料
        data = await leaderboard_view.load_data(page=0, type="points")

        # 驗證結果
        assert data["leaderboard_type"] == "points"
        assert data["user_rank"] == mock_user_rank

        # 驗證服務調用
        mock_achievement_service.get_leaderboard_by_points.assert_called_once_with(
            limit=10
        )
        mock_achievement_service.get_user_rank.assert_called_once_with(987654321, "points")

    @pytest.mark.asyncio
    async def test_load_data_category_leaderboard(self, leaderboard_view, mock_achievement_service):
        """測試載入分類排行榜資料."""
        # 設置模擬資料
        mock_leaderboard_data = [{"user_id": 111, "value": 5}]
        mock_user_rank = {"rank": 2, "value": 3}
        mock_category = MagicMock()
        mock_category.name = "社交成就"

        mock_achievement_service.get_leaderboard_by_category.return_value = mock_leaderboard_data
        mock_achievement_service.get_user_rank.return_value = mock_user_rank
        mock_achievement_service.get_category_by_id.return_value = mock_category

        # 測試載入資料
        data = await leaderboard_view.load_data(
            page=0, type="category_42", category_id=42
        )

        # 驗證結果
        assert data["category_id"] == 42
        assert data["category_name"] == "社交成就"

        # 驗證服務調用
        mock_achievement_service.get_leaderboard_by_category.assert_called_once_with(
            category_id=42, limit=10
        )
        mock_achievement_service.get_user_rank.assert_called_once_with(
            987654321, "category_42"
        )
        mock_achievement_service.get_category_by_id.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_build_embed_success(self, leaderboard_view, mock_achievement_service, mock_bot):
        """測試成功建立排行榜 Embed."""
        # 設置模擬資料
        mock_data = {
            "leaderboard_data": [
                {"user_id": 111, "value": 15},
                {"user_id": 987654321, "value": 10},  # 當前用戶
            ],
            "current_page": 0,
            "total_pages": 1,
            "leaderboard_type": "count",
            "user_rank": {"rank": 2, "value": 10},
            "stats": {"total_users": 2, "page_size": 10}
        }

        with patch.object(leaderboard_view, 'get_cached_data', return_value=mock_data):
            embed = await leaderboard_view.build_embed(bot=mock_bot)

            # 驗證 Embed 基本屬性
            assert "🏆 成就排行榜 - 成就總數" in embed.title
            assert "查看伺服器成就排行榜" in embed.description

            # 驗證欄位存在
            field_names = [field.name for field in embed.fields]
            assert "📊 排行榜統計" in field_names
            assert "📄 頁面資訊" in field_names
            assert "📍 您的排名" in field_names
            assert "🏅 排行榜 (第 1-2 名)" in field_names

    @pytest.mark.asyncio
    async def test_build_embed_error_handling(self, leaderboard_view, mock_bot):
        """測試 Embed 建立錯誤處理."""
        # 模擬載入資料時發生錯誤
        with patch.object(leaderboard_view, 'get_cached_data', side_effect=Exception("測試錯誤")):
            embed = await leaderboard_view.build_embed(bot=mock_bot)

            # 驗證錯誤 Embed
            assert "載入失敗" in embed.title
            assert "無法載入排行榜資料" in embed.description

    @pytest.mark.asyncio
    async def test_build_embed_current_user_highlight(self, leaderboard_view, mock_achievement_service, mock_bot):
        """測試當前用戶在排行榜中的突出顯示."""
        # 設置包含當前用戶的排行榜資料
        mock_data = {
            "leaderboard_data": [
                {"user_id": 111, "value": 15},
                {"user_id": 987654321, "value": 10},  # 當前用戶
                {"user_id": 333, "value": 8},
            ],
            "current_page": 0,
            "total_pages": 1,
            "leaderboard_type": "count",
            "user_rank": {"rank": 2, "value": 10},
            "stats": {"total_users": 3, "page_size": 10}
        }

        with patch.object(leaderboard_view, 'get_cached_data', return_value=mock_data):
            embed = await leaderboard_view.build_embed(bot=mock_bot)

            # 檢查排行榜欄位內容
            leaderboard_field = next(
                field for field in embed.fields
                if field.name.startswith("🏅 排行榜")
            )

            # 驗證當前用戶有特殊標記（**粗體**和⭐）
            assert "**🥈 測試用戶 - 10 個成就** ⭐" in leaderboard_field.value

    @pytest.mark.asyncio
    async def test_load_data_pagination(self, leaderboard_view, mock_achievement_service):
        """測試分頁資料載入."""
        # 設置大量資料以測試分頁
        mock_leaderboard_data = [
            {"user_id": i, "value": 100 - i} for i in range(25)
        ]
        mock_achievement_service.get_leaderboard_by_count.return_value = mock_leaderboard_data
        mock_achievement_service.get_user_rank.return_value = {"rank": 10, "value": 85}

        # 測試第二頁資料
        data = await leaderboard_view.load_data(page=1, type="count")

        # 驗證分頁計算
        assert data["current_page"] == 1
        assert data["total_pages"] == 3  # 25項目，每頁10項 = 3頁
        assert len(data["leaderboard_data"]) == 10  # 第二頁有10項目

        # 驗證服務調用包含正確的限制和偏移
        mock_achievement_service.get_leaderboard_by_count.assert_called_once_with(
            limit=20  # limit包含偏移量以計算總頁數
        )
