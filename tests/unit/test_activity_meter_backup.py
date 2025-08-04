"""
活躍度系統測試模塊
測試活躍度計算器、資料庫操作、渲染器和整合功能
"""

import logging
import time
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest
import pytest_asyncio

# 測試配置
logging.basicConfig(level=logging.DEBUG)


class TestActivityCalculator:
    """🧮 活躍度計算器測試類"""

    @pytest.fixture
    def calculator(self):
        """建立測試用計算器"""
        from cogs.activity_meter.main.calculator import ActivityCalculator

        return ActivityCalculator()

    @pytest.fixture
    def mock_config(self):
        """模擬配置"""
        return {
            "ACTIVITY_MAX_SCORE": 100.0,
            "ACTIVITY_DECAY_RATE": 0.1,
            "ACTIVITY_GRACE_PERIOD": 300,
            "ACTIVITY_COOLDOWN": 30,
            "ACTIVITY_SCORE_INCREMENT": 2.0,
        }

    def test_decay_calculation_no_time(self, calculator):
        """測試無時間差的衰減計算"""
        current_score = 50.0
        time_diff = 0

        result = calculator.decay(current_score, time_diff)

        assert result == current_score, f"無時間差應無衰減: {result} != {current_score}"

    def test_decay_calculation_within_grace_period(self, calculator):
        """測試寬限期內的衰減計算"""
        current_score = 50.0
        time_diff = 200  # 小於寬限期

        result = calculator.decay(current_score, time_diff)

        assert result == current_score, f"寬限期內應無衰減: {result} != {current_score}"

    def test_decay_calculation_after_grace_period(self, calculator):
        """測試寬限期後的衰減計算"""
        current_score = 50.0
        time_diff = 7200  # 2小時,大於寬限期(1小時)

        result = calculator.decay(current_score, time_diff)

        assert result < current_score, f"寬限期後應有衰減: {result} >= {current_score}"
        assert result >= 0, f"衰減後分數不應為負: {result}"

    def test_decay_minimum_boundary(self, calculator):
        """測試衰減最小邊界"""
        current_score = 1.0
        time_diff = 10000  # 很長時間

        result = calculator.decay(current_score, time_diff)

        assert result >= 0, f"衰減不應產生負分數: {result}"

    def test_calculate_new_score_normal_case(self, calculator):
        """測試正常情況下的新分數計算"""
        current_score = 50.0
        last_message_time = int(time.time()) - 100
        now = int(time.time())

        result = calculator.calculate_new_score(current_score, last_message_time, now)

        assert isinstance(result, float), f"結果應為浮點數: {type(result)}"
        assert result >= 0, f"新分數不應為負: {result}"
        assert result <= 100, f"新分數不應超過上限: {result}"

    def test_calculate_new_score_maximum_cap(self, calculator):
        """測試新分數的最大值限制"""
        current_score = 99.0
        last_message_time = int(time.time()) - 100
        now = int(time.time())

        result = calculator.calculate_new_score(current_score, last_message_time, now)

        assert result <= 100, f"新分數不應超過100: {result}"

    def test_should_update_cooldown_logic(self, calculator):
        """測試更新冷卻邏輯"""
        recent_time = int(time.time()) - 10  # 10秒前
        old_time = int(time.time()) - 100  # 100秒前
        now = int(time.time())

        should_update_recent = calculator.should_update(recent_time, now)
        should_update_old = calculator.should_update(old_time, now)

        assert not should_update_recent, "最近更新應在冷卻期內"
        assert should_update_old, "較舊更新應允許更新"

    def test_edge_case_zero_score(self, calculator):
        """測試零分數邊界情況"""
        current_score = 0.0
        last_message_time = int(time.time()) - 100
        now = int(time.time())

        result = calculator.calculate_new_score(current_score, last_message_time, now)

        assert result > 0, f"零分數應能增加: {result}"

    def test_edge_case_negative_delta(self, calculator):
        """測試負時間差邊界情況"""
        current_score = 50.0
        future_time = int(time.time()) + 100  # 未來時間
        now = int(time.time())

        result = calculator.calculate_new_score(current_score, future_time, now)

        assert result >= 0, f"負時間差不應產生負分數: {result}"

    def test_edge_case_maximum_score(self, calculator):
        """測試最大分數邊界情況"""
        current_score = 100.0
        last_message_time = int(time.time()) - 100
        now = int(time.time())

        result = calculator.calculate_new_score(current_score, last_message_time, now)

        assert result <= 100, f"最大分數不應超過上限: {result}"


class TestActivityDatabase:
    """🗄️ 活躍度資料庫測試類"""

    @pytest_asyncio.fixture
    async def activity_db(self, test_db):
        """建立測試用活躍度資料庫"""
        from cogs.activity_meter.database.database import ActivityDatabase

        db = ActivityDatabase()

        # 覆蓋 _get_connection 方法使用測試資料庫
        async def mock_get_connection():
            return test_db

        db._get_connection = mock_get_connection
        await db.init_db()
        return db

    @pytest_asyncio.fixture
    async def sample_activity_data(self, activity_db):
        """插入測試活躍度資料"""
        await activity_db.update_user_activity(
            guild_id=12345, user_id=67890, score=75.5, timestamp=int(time.time()) - 1800
        )

        await activity_db.increment_daily_message_count(
            ymd="20240101", guild_id=12345, user_id=67890
        )

        return activity_db

    @pytest.mark.asyncio
    async def test_database_initialization(self, test_db):
        """測試資料庫初始化"""
        from cogs.activity_meter.database.database import ActivityDatabase

        db = ActivityDatabase()

        # 覆蓋 _get_connection 方法使用測試資料庫
        async def mock_get_connection():
            return test_db

        db._get_connection = mock_get_connection

        await db.init_db()

        # 驗證表格創建
        conn = await db._get_connection()
        tables = ["meter", "daily"]
        for table in tables:
            cursor = await conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            result = await cursor.fetchone()
            assert result is not None, f"表格 {table} 應該被創建"

    @pytest.mark.asyncio
    async def test_get_user_activity_existing(self, sample_activity_data):
        """測試獲取存在用戶的活躍度"""
        db = sample_activity_data
        score, last_msg = await db.get_user_activity(12345, 67890)

        assert score == 75.5, f"分數應該正確: {score}"
        assert isinstance(last_msg, int), f"時間戳應為整數: {type(last_msg)}"
        assert last_msg > 0, f"時間戳應大於0: {last_msg}"

    @pytest.mark.asyncio
    async def test_get_user_activity_nonexistent(self, activity_db):
        """測試獲取不存在用戶的活躍度"""
        score, last_msg = await activity_db.get_user_activity(99999, 88888)

        assert score == 0.0, f"不存在用戶的分數應為0: {score}"
        assert last_msg == 0, f"不存在用戶的時間戳應為0: {last_msg}"

    @pytest.mark.asyncio
    async def test_update_user_activity(self, activity_db):
        """測試更新用戶活躍度"""
        guild_id, user_id = 12345, 67890
        new_score = 85.0
        timestamp = int(time.time())

        await activity_db.update_user_activity(guild_id, user_id, new_score, timestamp)

        # 驗證更新
        score, last_msg = await activity_db.get_user_activity(guild_id, user_id)
        assert score == new_score, f"分數應已更新: {score} != {new_score}"
        assert last_msg == timestamp, f"時間戳應已更新: {last_msg} != {timestamp}"


class TestActivityRenderer:
    """📊 活躍度渲染器測試類"""

    @pytest.fixture
    def renderer(self):
        """建立測試用渲染器"""
        from cogs.activity_meter.main.renderer import ActivityRenderer

        return ActivityRenderer()

    def test_render_progress_bar_normal(self, renderer):
        """測試正常進度條渲染"""
        with (
            patch("PIL.Image.new") as mock_image,
            patch("PIL.ImageDraw.Draw") as mock_draw,
            patch("PIL.ImageFont.truetype") as mock_font,
        ):
            mock_img = Mock()
            mock_drawer = Mock()
            mock_font_obj = Mock()

            mock_image.return_value = mock_img
            mock_draw.return_value = mock_drawer
            mock_font.return_value = mock_font_obj

            # 模擬字體方法
            mock_font_obj.getlength.return_value = 100
            mock_drawer.textbbox.return_value = (0, 0, 100, 20)

            # 模擬圖片保存
            mock_img.save = Mock()

            result = renderer.render_progress_bar("測試用戶", 75.5)

            assert result is not None, "應返回渲染結果"
            assert isinstance(result, discord.File), "應返回Discord文件"


class TestActivityMeterIntegration:
    """🔗 活躍度系統整合測試類"""

    @pytest_asyncio.fixture
    async def activity_meter(self, mock_bot):
        """建立測試用活躍度計量器"""
        from cogs.activity_meter.main.main import ActivityMeter

        with patch(
            "cogs.activity_meter.database.database.ActivityDatabase"
        ) as mock_db_class:
            mock_db = AsyncMock()
            mock_db.init_db = AsyncMock()
            mock_db.get_user_activity.return_value = (75.5, int(time.time()) - 1800)
            mock_db.update_user_activity = AsyncMock()
            mock_db.increment_daily_message_count = AsyncMock()
            mock_db_class.return_value = mock_db

            cog = ActivityMeter(mock_bot)
            cog.db = mock_db
            return cog

    @pytest.mark.asyncio
    async def test_activity_command_existing_user(
        self, activity_meter, mock_interaction, mock_member
    ):
        """測試查詢現有用戶活躍度命令"""
        mock_interaction.guild.id = 12345
        mock_member.id = 67890
        mock_member.display_name = "測試用戶"

        # 模擬 defer 回應
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        with patch.object(activity_meter, "renderer") as mock_renderer:
            mock_renderer.render_progress_bar.return_value = Mock()

            # 直接調用命令方法
            await activity_meter.activity.callback(
                activity_meter, mock_interaction, mock_member
            )

            # 驗證交互回應
            mock_interaction.response.defer.assert_called_once()
            mock_interaction.followup.send.assert_called_once()

            # 驗證資料庫查詢
            activity_meter.db.get_user_activity.assert_called_with(12345, 67890)


# 測試工具函數
def test_tracking_id_generation():
    """測試追蹤ID生成"""
    from cogs.core.error_handler import ErrorHandler

    handler = ErrorHandler("test_module")
    tracking_id = handler.generate_tracking_id(500)

    assert tracking_id.startswith("TRACKING_ID-500-"), (
        f"追蹤ID格式不正確: {tracking_id}"
    )
    assert len(tracking_id) == 22, f"追蹤ID長度不正確: {len(tracking_id)}"


def test_config_validation():
    """測試配置驗證"""
    from cogs.activity_meter.config import config

    # 驗證重要配置項存在
    assert hasattr(config, "ACTIVITY_MAX_SCORE"), "應有最大分數配置"
    assert hasattr(config, "ACTIVITY_GAIN"), "應有增益配置"
    assert hasattr(config, "ACTIVITY_DECAY_PER_H"), "應有衰減率配置"
    assert hasattr(config, "ACTIVITY_COOLDOWN"), "應有冷卻時間配置"

    # 驗證配置值合理性
    assert config.ACTIVITY_MAX_SCORE > 0, "最大分數應大於0"
    assert config.ACTIVITY_GAIN > 0, "增益應大於0"
    assert config.ACTIVITY_DECAY_PER_H >= 0, "衰減率應非負"
    assert config.ACTIVITY_COOLDOWN >= 0, "冷卻時間應非負"


def test_time_utilities():
    """測試時間工具函數"""
    import time

    current_time = int(time.time())

    assert current_time > 0, "當前時間應大於0"
    assert isinstance(current_time, int), "時間戳應為整數"
