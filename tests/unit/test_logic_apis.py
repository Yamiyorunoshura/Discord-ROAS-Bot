"""
🧪 LogicAPIs 測試
- 測試程式邏輯個別API功能
- 驗證數據驗證和錯誤處理
- 測試API響應格式標準化
- 驗證性能監控和指標收集
"""

from unittest.mock import Mock, patch

import pytest

from cogs.activity_meter.main.logic_apis import APIResponse, LogicAPIs


class TestLogicAPIs:
    """LogicAPIs 測試類"""

    @pytest.fixture
    def logic_apis(self):
        """建立測試用 LogicAPIs"""
        with (
            patch(
                "cogs.activity_meter.main.logic_apis.ActivityDatabase"
            ) as mock_database,
            patch(
                "cogs.activity_meter.main.logic_apis.ActivityRenderer"
            ) as mock_renderer,
            patch(
                "cogs.activity_meter.main.logic_apis.ActivityCalculator"
            ) as mock_calculator,
        ):
            mock_database.return_value = Mock()
            mock_renderer.return_value = Mock()
            mock_calculator.return_value = Mock()

            return LogicAPIs()

    def test_initialization(self, logic_apis):
        """測試初始化"""
        assert logic_apis.database is not None
        assert logic_apis.renderer is not None
        assert logic_apis.calculator is not None
        assert logic_apis.api_calls == {}
        assert logic_apis.error_counts == {}

    def test_renderer_logic_api_success(self, logic_apis):
        """測試渲染邏輯API成功"""
        # 模擬渲染器返回結果
        mock_file = Mock()
        logic_apis.renderer.render_progress_bar.return_value = mock_file

        data = {"username": "測試用戶", "score": 75.5}

        result = logic_apis.renderer_logic_api(data)

        assert isinstance(result, APIResponse)
        assert result.status == "success"
        assert result.data is not None
        assert "rendered_file" in result.data
        assert result.message == "渲染成功"
        assert result.execution_time >= 0
        assert "renderer_logic" in logic_apis.api_calls

    def test_renderer_logic_api_invalid_data(self, logic_apis):
        """測試渲染邏輯API無效數據"""
        data = {
            "username": "測試用戶"
            # 缺少 score 字段
        }

        result = logic_apis.renderer_logic_api(data)

        assert isinstance(result, APIResponse)
        assert result.status == "error"
        assert "渲染數據格式錯誤" in result.message

    def test_renderer_logic_api_exception(self, logic_apis):
        """測試渲染邏輯API異常"""
        # 模擬渲染器拋出異常
        logic_apis.renderer.render_progress_bar.side_effect = Exception("渲染失敗")

        data = {"username": "測試用戶", "score": 75.5}

        result = logic_apis.renderer_logic_api(data)

        assert isinstance(result, APIResponse)
        assert result.status == "error"
        assert "渲染失敗" in result.message
        assert "renderer_logic" in logic_apis.error_counts

    def test_settings_logic_api_success(self, logic_apis):
        """測試設定邏輯API成功"""
        # 模擬數據庫保存成功
        logic_apis.database.save_settings.return_value = True

        settings = {"guild_id": "123456789", "key": "auto_report", "value": "true"}

        result = logic_apis.settings_logic_api(settings)

        assert isinstance(result, APIResponse)
        assert result.status == "success"
        assert result.message == "設定保存成功"
        assert result.execution_time >= 0
        assert "settings_logic" in logic_apis.api_calls

    def test_settings_logic_api_invalid_data(self, logic_apis):
        """測試設定邏輯API無效數據"""
        settings = {
            "guild_id": "123456789"
            # 缺少 key 和 value 字段
        }

        result = logic_apis.settings_logic_api(settings)

        assert isinstance(result, APIResponse)
        assert result.status == "error"
        assert "設定數據格式錯誤" in result.message

    def test_settings_logic_api_save_failure(self, logic_apis):
        """測試設定邏輯API保存失敗"""
        # 模擬數據庫保存失敗
        logic_apis.database.save_settings.return_value = False

        settings = {"guild_id": "123456789", "key": "auto_report", "value": "true"}

        result = logic_apis.settings_logic_api(settings)

        assert isinstance(result, APIResponse)
        assert result.status == "error"
        assert result.message == "設定保存失敗"

    def test_get_user_data_success(self, logic_apis):
        """測試獲取用戶數據成功"""
        # 模擬數據庫返回用戶數據
        mock_user_data = {
            "user_id": "123456789",
            "score": 75.5,
            "last_activity": "2024-01-01T12:00:00",
        }
        logic_apis.database.get_user_activity.return_value = mock_user_data

        # 模擬計算器
        logic_apis.calculator.calculate_level.return_value = 3
        logic_apis.calculator.get_next_level_score.return_value = 80.0

        result = logic_apis.get_user_data("123456789")

        assert result is not None
        assert result["user_id"] == "123456789"
        assert result["score"] == 75.5
        assert result["level"] == 3
        assert result["next_level_score"] == 80.0
        assert "get_user_data" in logic_apis.api_calls

    def test_get_user_data_not_found(self, logic_apis):
        """測試獲取用戶數據不存在"""
        # 模擬數據庫返回None
        logic_apis.database.get_user_activity.return_value = None

        result = logic_apis.get_user_data("invalid_user")

        assert result is None
        assert "get_user_data" in logic_apis.api_calls

    def test_get_user_data_exception(self, logic_apis):
        """測試獲取用戶數據異常"""
        # 模擬數據庫拋出異常
        logic_apis.database.get_user_activity.side_effect = Exception("Database error")

        result = logic_apis.get_user_data("123456789")

        assert result is None
        assert "get_user_data" in logic_apis.error_counts

    def test_get_user_rank_success(self, logic_apis):
        """測試獲取用戶排名成功"""
        # 模擬數據庫返回排名
        logic_apis.database.get_user_rank.return_value = 5

        result = logic_apis.get_user_rank("123456789")

        assert result == 5
        assert "get_user_rank" in logic_apis.api_calls

    def test_get_user_rank_not_found(self, logic_apis):
        """測試獲取用戶排名不存在"""
        # 模擬數據庫返回None
        logic_apis.database.get_user_rank.return_value = None

        result = logic_apis.get_user_rank("invalid_user")

        assert result is None

    def test_get_user_activity_history(self, logic_apis):
        """測試獲取用戶活躍度歷史"""
        # 模擬數據庫返回歷史數據
        mock_history_data = [
            {"score": 75.5, "timestamp": "2024-01-01"},
            {"score": 80.0, "timestamp": "2024-01-02"},
        ]
        logic_apis.database.get_user_activity_history.return_value = mock_history_data

        result = logic_apis.get_user_activity_history("123456789", 30)

        assert result == mock_history_data
        assert "get_user_activity_history" in logic_apis.api_calls

    def test_get_leaderboard(self, logic_apis):
        """測試獲取排行榜"""
        # 模擬數據庫返回排行榜數據
        mock_leaderboard_data = [
            {"user_id": "123", "score": 95.0, "messages": 500},
            {"user_id": "456", "score": 85.0, "messages": 400},
        ]
        logic_apis.database.get_leaderboard.return_value = mock_leaderboard_data

        result = logic_apis.get_leaderboard("guild_123", 10)

        assert result == mock_leaderboard_data
        assert "get_leaderboard" in logic_apis.api_calls

    def test_update_user_activity_success(self, logic_apis):
        """測試更新用戶活躍度成功"""
        # 模擬數據庫操作
        logic_apis.database.get_user_score.return_value = 50.0
        logic_apis.database.update_user_activity.return_value = True

        # 模擬計算器
        logic_apis.calculator.calculate_new_score.return_value = 55.0

        result = logic_apis.update_user_activity("123456789", "guild_123", "message")

        assert result is True
        assert "update_user_activity" in logic_apis.api_calls

    def test_update_user_activity_failure(self, logic_apis):
        """測試更新用戶活躍度失敗"""
        # 模擬數據庫操作失敗
        logic_apis.database.update_user_activity.return_value = False

        result = logic_apis.update_user_activity("123456789", "guild_123", "message")

        assert result is False

    def test_calculate_activity_score_api_success(self, logic_apis):
        """測試計算活躍度分數API成功"""
        # 模擬計算器
        logic_apis.calculator.calculate_score.return_value = 75.5
        logic_apis.calculator.calculate_level.return_value = 3
        logic_apis.calculator.get_next_level_score.return_value = 80.0

        user_data = {"user_id": "123456789", "messages": 100, "total_messages": 500}

        result = logic_apis.calculate_activity_score_api(user_data)

        assert isinstance(result, APIResponse)
        assert result.status == "success"
        assert result.data["score"] == 75.5
        assert result.data["level"] == 3
        assert result.data["next_level_score"] == 80.0
        assert "calculate_activity_score" in logic_apis.api_calls

    def test_calculate_activity_score_api_invalid_data(self, logic_apis):
        """測試計算活躍度分數API無效數據"""
        user_data = {
            "messages": 100
            # 缺少 user_id 字段
        }

        result = logic_apis.calculate_activity_score_api(user_data)

        assert isinstance(result, APIResponse)
        assert result.status == "error"
        assert "用戶數據格式錯誤" in result.message

    def test_get_api_metrics(self, logic_apis):
        """測試獲取API指標"""
        # 設置一些測試數據
        logic_apis.api_calls = {
            "renderer_logic": 10,
            "settings_logic": 5,
            "get_user_data": 20,
        }
        logic_apis.error_counts = {"renderer_logic": 1, "get_user_data": 2}

        metrics = logic_apis.get_api_metrics()

        assert "api_calls" in metrics
        assert "error_counts" in metrics
        assert "success_rates" in metrics
        assert metrics["api_calls"]["renderer_logic"] == 10
        assert metrics["error_counts"]["renderer_logic"] == 1
        assert "renderer_logic" in metrics["success_rates"]

    def test_validate_render_data(self, logic_apis):
        """測試渲染數據驗證"""
        # 有效數據
        valid_data = {"username": "測試用戶", "score": 75.5}
        assert logic_apis._validate_render_data(valid_data) is True

        # 無效數據
        invalid_data = {
            "username": "測試用戶"
            # 缺少 score
        }
        assert logic_apis._validate_render_data(invalid_data) is False

    def test_validate_settings(self, logic_apis):
        """測試設定數據驗證"""
        # 有效設定
        valid_settings = {
            "guild_id": "123456789",
            "key": "auto_report",
            "value": "true",
        }
        assert logic_apis._validate_settings(valid_settings) is True

        # 無效設定
        invalid_settings = {
            "guild_id": "123456789"
            # 缺少 key 和 value
        }
        assert logic_apis._validate_settings(invalid_settings) is False

    def test_validate_user_data(self, logic_apis):
        """測試用戶數據驗證"""
        # 有效用戶數據
        valid_user_data = {"user_id": "123456789", "messages": 100}
        assert logic_apis._validate_user_data(valid_user_data) is True

        # 無效用戶數據
        invalid_user_data = {
            "messages": 100
            # 缺少 user_id
        }
        assert logic_apis._validate_user_data(invalid_user_data) is False


class TestAPIResponse:
    """APIResponse 測試類"""

    def test_api_response_creation(self):
        """測試 APIResponse 創建"""
        response = APIResponse(
            status="success",
            data={"key": "value"},
            message="操作成功",
            execution_time=1.5,
        )

        assert response.status == "success"
        assert response.data == {"key": "value"}
        assert response.message == "操作成功"
        assert response.execution_time == 1.5
        assert response.timestamp is not None

    def test_api_response_with_defaults(self):
        """測試 APIResponse 默認值"""
        response = APIResponse(status="error")

        assert response.status == "error"
        assert response.data is None
        assert response.message == ""
        assert response.execution_time == 0.0
        assert response.timestamp is not None
