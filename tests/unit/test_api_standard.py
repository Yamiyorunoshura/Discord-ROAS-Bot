"""
API標準化系統測試
Discord ADR Bot v1.6 - API標準化架構測試

測試覆蓋:
- API響應格式
- 錯誤處理
- 參數驗證
- 速率限制
- API裝飾器

作者:Discord ADR Bot 測試工程師
版本:v1.6
"""

import time

import pytest

from cogs.core.api_standard import (
    APIResponse,
    APIValidator,
    APIVersion,
    ErrorCode,
    RateLimiter,
    ResponseStatus,
    api_endpoint,
    error_response,
    partial_response,
    success_response,
    validate_parameters,
    warning_response,
)


class TestAPIResponse:
    """API響應測試"""

    def test_success_response_creation(self):
        """測試成功響應創建"""
        response = APIResponse.success({"key": "value"}, "操作成功")

        assert response.status == ResponseStatus.SUCCESS
        assert response.data == {"key": "value"}
        assert response.message == "操作成功"
        assert response.version == APIVersion.LATEST
        assert "request_id" in response.metadata

    def test_error_response_creation(self):
        """測試錯誤響應創建"""
        response = APIResponse.create_error(
            ErrorCode.INVALID_PARAMETERS, "參數錯誤", {"field": "invalid"}
        )

        assert response.status == ResponseStatus.ERROR
        assert response.error["code"] == ErrorCode.INVALID_PARAMETERS.value
        assert response.error["name"] == ErrorCode.INVALID_PARAMETERS.name
        assert response.error["details"]["field"] == "invalid"
        assert response.message == "參數錯誤"

    def test_warning_response_creation(self):
        """測試警告響應創建"""
        response = APIResponse.warning({"warnings": ["警告1"]}, "操作完成但有警告")

        assert response.status == ResponseStatus.WARNING
        assert response.data["warnings"] == ["警告1"]
        assert response.message == "操作完成但有警告"

    def test_partial_response_creation(self):
        """測試部分成功響應創建"""
        response = APIResponse.partial({"completed": 5, "failed": 2}, "部分成功")

        assert response.status == ResponseStatus.PARTIAL
        assert response.data["completed"] == 5
        assert response.data["failed"] == 2
        assert response.message == "部分成功"

    def test_response_to_dict(self):
        """測試響應轉換為字典"""
        response = APIResponse.success({"test": "data"}, "測試")
        result = response.to_dict()

        assert result["status"] == "success"
        assert result["data"]["test"] == "data"
        assert result["message"] == "測試"
        assert result["version"] == APIVersion.LATEST.value
        assert "timestamp" in result
        assert "metadata" in result

    def test_response_to_json(self):
        """測試響應轉換為JSON"""
        response = APIResponse.success({"test": "data"})
        json_str = response.to_json()

        assert isinstance(json_str, str)
        assert "success" in json_str
        assert "test" in json_str


class TestAPIValidator:
    """API驗證器測試"""

    def test_validate_string_success(self):
        """測試字符串驗證成功"""
        valid, error = APIValidator.validate_string("test", min_length=2, max_length=10)

        assert valid is True
        assert error is None

    def test_validate_string_too_short(self):
        """測試字符串太短"""
        valid, error = APIValidator.validate_string("a", min_length=2)

        assert valid is False
        assert "不能少於 2" in error

    def test_validate_string_too_long(self):
        """測試字符串太長"""
        valid, error = APIValidator.validate_string("very long string", max_length=5)

        assert valid is False
        assert "不能超過 5" in error

    def test_validate_string_allowed_values(self):
        """測試字符串允許值"""
        valid, error = APIValidator.validate_string(
            "test", allowed_values=["test", "demo"]
        )

        assert valid is True
        assert error is None

        valid, error = APIValidator.validate_string(
            "invalid", allowed_values=["test", "demo"]
        )

        assert valid is False
        assert "必須是以下之一" in error

    def test_validate_integer_success(self):
        """測試整數驗證成功"""
        valid, error = APIValidator.validate_integer(5, min_value=1, max_value=10)

        assert valid is True
        assert error is None

    def test_validate_integer_too_small(self):
        """測試整數太小"""
        valid, error = APIValidator.validate_integer(0, min_value=1)

        assert valid is False
        assert "不能小於 1" in error

    def test_validate_integer_too_large(self):
        """測試整數太大"""
        valid, error = APIValidator.validate_integer(15, max_value=10)

        assert valid is False
        assert "不能大於 10" in error

    def test_validate_boolean_success(self):
        """測試布爾值驗證成功"""
        valid, error = APIValidator.validate_boolean(True)

        assert valid is True
        assert error is None

        valid, error = APIValidator.validate_boolean(False)

        assert valid is True
        assert error is None

    def test_validate_boolean_failure(self):
        """測試布爾值驗證失敗"""
        valid, error = APIValidator.validate_boolean("true")

        assert valid is False
        assert "必須是布爾類型" in error

    def test_validate_list_success(self):
        """測試列表驗證成功"""
        valid, error = APIValidator.validate_list([1, 2, 3], min_items=1, max_items=5)

        assert valid is True
        assert error is None

    def test_validate_list_too_few_items(self):
        """測試列表項目太少"""
        valid, error = APIValidator.validate_list([], min_items=1)

        assert valid is False
        assert "不能少於 1" in error

    def test_validate_list_too_many_items(self):
        """測試列表項目太多"""
        valid, error = APIValidator.validate_list([1, 2, 3, 4, 5, 6], max_items=5)

        assert valid is False
        assert "不能超過 5" in error


class TestRateLimiter:
    """速率限制器測試"""

    def test_rate_limiter_allows_requests(self):
        """測試速率限制器允許請求"""
        limiter = RateLimiter(max_requests=3, time_window=60)

        # 前3個請求應該被允許
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True

        # 第4個請求應該被拒絕
        assert limiter.is_allowed("user1") is False

    def test_rate_limiter_different_users(self):
        """測試速率限制器對不同用戶"""
        limiter = RateLimiter(max_requests=2, time_window=60)

        # 不同用戶應該有獨立的限制
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user2") is True
        assert limiter.is_allowed("user2") is True

        # 但各自的第3個請求應該被拒絕
        assert limiter.is_allowed("user1") is False
        assert limiter.is_allowed("user2") is False

    def test_rate_limiter_time_window_reset(self):
        """測試速率限制器時間窗口重置"""
        limiter = RateLimiter(max_requests=1, time_window=1)

        # 第一個請求被允許
        assert limiter.is_allowed("user1") is True

        # 第二個請求被拒絕
        assert limiter.is_allowed("user1") is False

        # 等待時間窗口過期
        time.sleep(1.1)

        # 現在應該可以再次請求
        assert limiter.is_allowed("user1") is True


class TestAPIEndpointDecorator:
    """API端點裝飾器測試"""

    @pytest.mark.asyncio
    async def test_api_endpoint_basic(self):
        """測試基本API端點裝飾器"""

        @api_endpoint("test_api", "測試API")
        async def test_function():
            return {"result": "success"}

        result = await test_function()

        assert isinstance(result, APIResponse)
        assert result.status == ResponseStatus.SUCCESS
        assert result.data["result"] == "success"

    @pytest.mark.asyncio
    async def test_api_endpoint_with_api_response(self):
        """測試返回APIResponse的API端點"""

        @api_endpoint("test_api", "測試API")
        async def test_function():
            return APIResponse.success({"custom": "response"})

        result = await test_function()

        assert isinstance(result, APIResponse)
        assert result.status == ResponseStatus.SUCCESS
        assert result.data["custom"] == "response"

    @pytest.mark.asyncio
    async def test_api_endpoint_with_exception(self):
        """測試拋出異常的API端點"""

        @api_endpoint("test_api", "測試API")
        async def test_function():
            raise ValueError("測試錯誤")

        result = await test_function()

        assert isinstance(result, APIResponse)
        assert result.status == ResponseStatus.ERROR
        assert result.error["code"] == ErrorCode.UNKNOWN_ERROR.value
        assert "測試錯誤" in result.error["message"]

    @pytest.mark.asyncio
    async def test_api_endpoint_with_rate_limit(self):
        """測試帶速率限制的API端點"""
        from unittest.mock import Mock

        import discord

        # 創建mock interaction,確保它被識別為discord.Interaction
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.user.id = 12345

        @api_endpoint("test_api", "測試API", rate_limit=(2, 60))
        async def test_function(interaction):
            return {"result": "success"}

        # 前兩次調用應該成功
        result1 = await test_function(mock_interaction)
        assert result1.status == ResponseStatus.SUCCESS

        result2 = await test_function(mock_interaction)
        assert result2.status == ResponseStatus.SUCCESS

        # 第三次調用應該被限制
        result3 = await test_function(mock_interaction)
        assert result3.status == ResponseStatus.ERROR
        assert result3.error["code"] == ErrorCode.RATE_LIMITED.value

    def test_api_endpoint_metadata(self):
        """測試API端點元數據"""

        @api_endpoint(
            "test_api", "測試API", version=APIVersion.V1_1, rate_limit=(5, 60)
        )
        async def test_function():
            return {"result": "success"}

        metadata = getattr(test_function, "_api_metadata", None)

        assert metadata is not None
        assert metadata["name"] == "test_api"
        assert metadata["description"] == "測試API"
        assert metadata["version"] == APIVersion.V1_1
        assert metadata["rate_limit"] == (5, 60)


class TestConvenienceFunctions:
    """便利函數測試"""

    def test_success_response_function(self):
        """測試成功響應便利函數"""
        response = success_response({"data": "test"}, "成功")

        assert isinstance(response, APIResponse)
        assert response.status == ResponseStatus.SUCCESS
        assert response.data["data"] == "test"
        assert response.message == "成功"

    def test_error_response_function(self):
        """測試錯誤響應便利函數"""
        response = error_response(ErrorCode.INVALID_PARAMETERS, "參數錯誤")

        assert isinstance(response, APIResponse)
        assert response.status == ResponseStatus.ERROR
        assert response.error["code"] == ErrorCode.INVALID_PARAMETERS.value
        assert response.message == "參數錯誤"

    def test_warning_response_function(self):
        """測試警告響應便利函數"""
        response = warning_response({"warnings": ["警告"]}, "有警告")

        assert isinstance(response, APIResponse)
        assert response.status == ResponseStatus.WARNING
        assert response.data["warnings"] == ["警告"]
        assert response.message == "有警告"

    def test_partial_response_function(self):
        """測試部分成功響應便利函數"""
        response = partial_response({"partial": "data"}, "部分成功")

        assert isinstance(response, APIResponse)
        assert response.status == ResponseStatus.PARTIAL
        assert response.data["partial"] == "data"
        assert response.message == "部分成功"


class TestParameterValidation:
    """參數驗證測試"""

    def test_validate_parameters_success(self):
        """測試參數驗證成功"""
        data = {"name": "test", "age": 25, "active": True, "tags": ["tag1", "tag2"]}

        rules = {
            "name": {"type": "string", "min_length": 2, "max_length": 50},
            "age": {"type": "integer", "min_value": 0, "max_value": 150},
            "active": {"type": "boolean"},
            "tags": {"type": "list", "min_items": 1, "max_items": 10},
        }

        result = validate_parameters(data, rules)

        assert result.status == ResponseStatus.SUCCESS
        assert result.data["name"] == "test"
        assert result.data["age"] == 25
        assert result.data["active"] is True
        assert result.data["tags"] == ["tag1", "tag2"]

    def test_validate_parameters_missing_required(self):
        """測試缺少必需參數"""
        data = {"name": "test"}

        rules = {
            "name": {"type": "string"},
            "age": {"type": "integer", "required": True},
        }

        result = validate_parameters(data, rules)

        assert result.status == ResponseStatus.ERROR
        assert result.error["code"] == ErrorCode.VALIDATION_FAILED.value
        assert "age" in result.error["details"]["validation_errors"]
        assert "必需項" in result.error["details"]["validation_errors"]["age"]

    def test_validate_parameters_with_defaults(self):
        """測試使用默認值的參數驗證"""
        data = {"name": "test"}

        rules = {
            "name": {"type": "string"},
            "age": {"type": "integer", "required": False, "default": 18},
        }

        result = validate_parameters(data, rules)

        assert result.status == ResponseStatus.SUCCESS
        assert result.data["name"] == "test"
        assert result.data["age"] == 18

    def test_validate_parameters_validation_errors(self):
        """測試參數驗證錯誤"""
        data = {
            "name": "a",  # 太短
            "age": -5,  # 太小
            "active": "yes",  # 不是布爾值
            "tags": [],  # 太少項目
        }

        rules = {
            "name": {"type": "string", "min_length": 2},
            "age": {"type": "integer", "min_value": 0},
            "active": {"type": "boolean"},
            "tags": {"type": "list", "min_items": 1},
        }

        result = validate_parameters(data, rules)

        assert result.status == ResponseStatus.ERROR
        assert result.error["code"] == ErrorCode.VALIDATION_FAILED.value

        errors = result.error["details"]["validation_errors"]
        assert "name" in errors
        assert "age" in errors
        assert "active" in errors
        assert "tags" in errors

    def test_validate_parameters_unknown_params(self):
        """測試未知參數"""
        data = {"name": "test", "unknown_param": "value"}

        rules = {"name": {"type": "string"}}

        result = validate_parameters(data, rules)

        assert result.status == ResponseStatus.ERROR
        assert result.error["code"] == ErrorCode.VALIDATION_FAILED.value
        assert "unknown_param" in result.error["details"]["validation_errors"]
        assert (
            "未知參數" in result.error["details"]["validation_errors"]["unknown_param"]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
