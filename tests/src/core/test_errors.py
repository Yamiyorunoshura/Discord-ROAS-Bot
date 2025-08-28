"""
Unit tests for src.core.errors module
Task ID: 1 - 核心架構和基礎設施建置
Updated for v2.4.4 - 測試完整錯誤類別層次結構
"""

import pytest
from datetime import datetime
from unittest.mock import patch
import json

from src.core.errors import (
    # 原始錯誤類別
    AppError, ServiceError, DatabaseError, PermissionError,
    ValidationError, NotFoundError, ConfigurationError, 
    ExternalServiceError,
    
    # ROAS Bot v2.4.4 新增錯誤類別
    ROASBotError,
    
    # 部署系統錯誤
    DeploymentError, EnvironmentError, DependencyInstallError, ServiceStartupError,
    
    # 子機器人系統錯誤
    SubBotError, SubBotCreationError, SubBotTokenError, SubBotChannelError,
    
    # AI服務錯誤
    AIServiceError, AIProviderError, AIQuotaExceededError, AIResponseError,
    
    # 安全錯誤
    SecurityError, ContentFilterError, AuthenticationError,
    
    # 工具函數
    create_error
)


class TestAppError:
    """Test the base AppError class"""
    
    def test_basic_initialization(self):
        """Test basic error initialization"""
        error = AppError("Test message")
        
        assert error.message == "Test message"
        assert error.error_code == "APPERROR"
        assert error.details == {}
        assert error.cause is None
        assert isinstance(error.timestamp, datetime)
        
    def test_full_initialization(self):
        """Test error initialization with all parameters"""
        cause = ValueError("Original error")
        details = {"key": "value"}
        
        error = AppError(
            message="Test message",
            error_code="TEST_001",
            details=details,
            cause=cause
        )
        
        assert error.message == "Test message"
        assert error.error_code == "TEST_001"
        assert error.details == details
        assert error.cause == cause
        
    def test_to_dict(self):
        """Test error conversion to dictionary"""
        error = AppError(
            message="Test message",
            error_code="TEST_001",
            details={"key": "value"}
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["error_type"] == "AppError"
        assert error_dict["error_code"] == "TEST_001"
        assert error_dict["message"] == "Test message"
        assert error_dict["details"] == {"key": "value"}
        assert "timestamp" in error_dict
        
    def test_str_representation(self):
        """Test string representation of error"""
        error = AppError("Test message", "TEST_001", {"key": "value"})
        
        str_repr = str(error)
        
        assert "Test message" in str_repr
        assert "TEST_001" in str_repr
        assert "key" in str_repr
        
    def test_str_representation_without_details(self):
        """Test string representation of error without details"""
        error = AppError("Test message", "TEST_001")
        
        str_repr = str(error)
        
        assert "Test message" in str_repr
        assert "TEST_001" in str_repr
        # Should use the simpler format without Details part


class TestServiceError:
    """Test the ServiceError class"""
    
    def test_service_error_initialization(self):
        """Test ServiceError initialization"""
        error = ServiceError(
            service_name="TestService",
            operation="test_operation",
            message="Operation failed"
        )
        
        assert error.service_name == "TestService"
        assert error.operation == "test_operation"
        assert "TestService" in error.message
        assert "test_operation" in error.message
        assert error.details["service_name"] == "TestService"
        assert error.details["operation"] == "test_operation"
        
    def test_service_error_with_cause(self):
        """Test ServiceError with underlying cause"""
        cause = ValueError("Database connection failed")
        
        error = ServiceError(
            service_name="DatabaseService",
            operation="connect",
            message="Failed to connect",
            cause=cause
        )
        
        assert error.cause == cause
        assert "DatabaseService" in error.message


class TestDatabaseError:
    """Test the DatabaseError class"""
    
    def test_database_error_initialization(self):
        """Test DatabaseError initialization"""
        error = DatabaseError(
            operation="SELECT",
            message="Query failed",
            query="SELECT * FROM users"
        )
        
        assert error.operation == "SELECT"
        assert error.query == "SELECT * FROM users"
        assert "Database SELECT" in error.message
        assert error.details["operation"] == "SELECT"
        assert error.details["query"] == "SELECT * FROM users"


class TestPermissionError:
    """Test the PermissionError class"""
    
    def test_permission_error_initialization(self):
        """Test PermissionError initialization"""
        error = PermissionError(
            user_id=12345,
            guild_id=67890,
            required_permission="manage_server",
            message="Access denied"
        )
        
        assert error.user_id == 12345
        assert error.guild_id == 67890
        assert error.required_permission == "manage_server"
        assert error.message == "Access denied"
        assert error.details["user_id"] == 12345
        assert error.details["guild_id"] == 67890


class TestValidationError:
    """Test the ValidationError class"""
    
    def test_validation_error_initialization(self):
        """Test ValidationError initialization"""
        error = ValidationError(
            field="email",
            value="invalid-email",
            validation_rule="must be valid email format"
        )
        
        assert error.field == "email"
        assert error.value == "invalid-email"
        assert error.validation_rule == "must be valid email format"
        assert "email" in error.message
        
    def test_validation_error_with_long_value(self):
        """Test ValidationError with value that needs sanitization"""
        long_value = "x" * 200
        
        error = ValidationError(
            field="data",
            value=long_value,
            validation_rule="too long"
        )
        
        # Value should be truncated to 100 characters
        assert len(error.value) == 100


class TestNotFoundError:
    """Test the NotFoundError class"""
    
    def test_not_found_error_initialization(self):
        """Test NotFoundError initialization"""
        error = NotFoundError(
            resource_type="User",
            resource_id=12345
        )
        
        assert error.resource_type == "User"
        assert error.resource_id == "12345"  # Should be converted to string
        assert "User not found: 12345" in error.message


class TestConfigurationError:
    """Test the ConfigurationError class"""
    
    def test_configuration_error_initialization(self):
        """Test ConfigurationError initialization"""
        error = ConfigurationError(
            config_key="database.url",
            message="Invalid database URL"
        )
        
        assert error.config_key == "database.url"
        assert "database.url" in error.message
        assert "Invalid database URL" in error.message


class TestExternalServiceError:
    """Test the ExternalServiceError class"""
    
    def test_external_service_error_initialization(self):
        """Test ExternalServiceError initialization"""
        error = ExternalServiceError(
            service_name="Discord API",
            operation="send_message",
            status_code=429,
            message="Rate limited"
        )
        
        assert error.service_name == "Discord API"
        assert error.operation == "send_message"
        assert error.status_code == 429
        assert "Discord API" in error.message
        assert "send_message" in error.message


class TestCreateError:
    """Test the create_error factory function"""
    
    def test_create_app_error(self):
        """Test creating AppError via factory"""
        error = create_error("AppError", message="Test message")
        
        assert isinstance(error, AppError)
        assert error.message == "Test message"
        
    def test_create_service_error(self):
        """Test creating ServiceError via factory"""
        error = create_error(
            "ServiceError",
            service_name="TestService",
            operation="test",
            message="Failed"
        )
        
        assert isinstance(error, ServiceError)
        assert error.service_name == "TestService"
    
    # 新增：測試ROAS Bot錯誤類別
    def test_create_roas_bot_error(self):
        """Test creating ROASBotError via factory"""
        error = create_error("ROASBotError", message="ROAS Bot 測試錯誤")
        
        assert isinstance(error, ROASBotError)
        assert error.message == "ROAS Bot 測試錯誤"
        assert hasattr(error, 'error_code')
        assert hasattr(error, 'timestamp')
    
    def test_create_deployment_errors(self):
        """Test creating deployment error types"""
        # 測試EnvironmentError
        env_error = create_error(
            "EnvironmentError",
            environment_type="docker",
            check_failed="Docker 未安裝"
        )
        assert isinstance(env_error, EnvironmentError)
        assert env_error.environment_type == "docker"
        
        # 測試DependencyInstallError
        dep_error = create_error(
            "DependencyInstallError",
            dependency_name="python",
            install_method="uv",
            reason="版本衝突"
        )
        assert isinstance(dep_error, DependencyInstallError)
        assert dep_error.dependency_name == "python"
    
    def test_create_sub_bot_errors(self):
        """Test creating sub-bot error types"""
        # 測試SubBotCreationError
        creation_error = create_error(
            "SubBotCreationError",
            bot_id="bot_001",
            reason="Token 無效"
        )
        assert isinstance(creation_error, SubBotCreationError)
        assert creation_error.bot_id == "bot_001"
        
        # 測試SubBotTokenError
        token_error = create_error(
            "SubBotTokenError",
            bot_id="bot_002",
            token_issue="權限不足"
        )
        assert isinstance(token_error, SubBotTokenError)
        assert token_error.token_issue == "權限不足"
    
    def test_create_ai_service_errors(self):
        """Test creating AI service error types"""
        # 測試AIProviderError
        provider_error = create_error(
            "AIProviderError",
            provider="openai",
            operation="chat_completion",
            api_error="API金鑰無效"
        )
        assert isinstance(provider_error, AIProviderError)
        assert provider_error.provider == "openai"
        
        # 測試AIQuotaExceededError
        quota_error = create_error(
            "AIQuotaExceededError",
            user_id="user_123",
            quota_type="daily",
            limit=100,
            current_usage=105
        )
        assert isinstance(quota_error, AIQuotaExceededError)
        assert quota_error.current_usage == 105
    
    def test_create_security_errors(self):
        """Test creating security error types"""
        # 測試ContentFilterError
        filter_error = create_error(
            "ContentFilterError",
            content_type="user_input",
            filter_rule="profanity_filter",
            violation="包含不當言語"
        )
        assert isinstance(filter_error, ContentFilterError)
        assert filter_error.content_type == "user_input"
        
        # 測試AuthenticationError
        auth_error = create_error(
            "AuthenticationError",
            auth_type="discord",
            user_info="user_456",
            reason="Token已過期"
        )
        assert isinstance(auth_error, AuthenticationError)
        assert auth_error.auth_type == "discord"
        
    def test_create_unknown_error_type(self):
        """Test creating unknown error type defaults to AppError"""
        error = create_error("UnknownError", message="Test")
        
        assert isinstance(error, AppError)
        assert error.message == "Test"
        
    def test_create_error_with_invalid_args(self):
        """Test creating error with invalid arguments"""
        # This should fall back to AppError when ServiceError can't be created
        error = create_error("ServiceError", message="Test")
        
        assert isinstance(error, AppError)
        assert error.message == "Test"


# ========== 新增：ROAS Bot v2.4.4 錯誤類別測試 ==========

class TestROASBotError:
    """Test ROASBotError base class"""
    
    def test_basic_initialization(self):
        """Test basic ROASBotError initialization"""
        error = ROASBotError("測試錯誤訊息")
        
        assert error.message == "測試錯誤訊息"
        assert error.error_code == "ROASBOTERROR"
        assert isinstance(error.timestamp, datetime)
        assert error.details == {}
        assert error.cause is None
        
    def test_inheritance_from_app_error(self):
        """Test ROASBotError inherits from AppError"""
        error = ROASBotError("測試")
        assert isinstance(error, AppError)
        assert isinstance(error, Exception)
        
    def test_error_code_fallback(self):
        """Test ROASBotError error_code fallback mechanism"""
        # Test with empty error_code
        error = ROASBotError("測試", error_code="")
        assert error.error_code == "ROASBOTERROR"
        
        # Test with None error_code
        error2 = ROASBotError("測試", error_code=None)
        assert error2.error_code == "ROASBOTERROR"
        
    def test_to_dict_method(self):
        """Test to_dict method includes all required fields"""
        error = ROASBotError("測試", error_code="TEST_001", details={"key": "value"})
        result = error.to_dict()
        
        required_fields = ["error_type", "error_code", "message", "details", "timestamp"]
        for field in required_fields:
            assert field in result
        
        assert result["error_type"] == "ROASBotError"
        assert result["error_code"] == "TEST_001"
        assert result["message"] == "測試"


class TestDeploymentErrors:
    """Test deployment system errors"""
    
    def test_environment_error(self):
        """Test EnvironmentError functionality"""
        error = EnvironmentError("docker", "Docker 未安裝")
        
        assert isinstance(error, DeploymentError)
        assert isinstance(error, ROASBotError)
        assert error.environment_type == "docker"
        assert error.check_failed == "Docker 未安裝"
        assert "環境檢測失敗" in error.message
        assert error.details["environment_type"] == "docker"
        
    def test_dependency_install_error(self):
        """Test DependencyInstallError functionality"""
        error = DependencyInstallError("python", "uv", "版本不相容")
        
        assert isinstance(error, DeploymentError)
        assert error.dependency_name == "python"
        assert error.install_method == "uv"
        assert error.reason == "版本不相容"
        assert "依賴安裝失敗" in error.message
        
    def test_service_startup_error(self):
        """Test ServiceStartupError functionality"""
        error = ServiceStartupError("discord_bot", "docker", "端口被佔用")
        
        assert isinstance(error, DeploymentError)
        assert error.service_name == "discord_bot"
        assert error.startup_mode == "docker"
        assert error.reason == "端口被佔用"
        assert "服務啟動失敗" in error.message


class TestSubBotErrors:
    """Test sub-bot system errors"""
    
    def test_sub_bot_creation_error(self):
        """Test SubBotCreationError functionality"""
        error = SubBotCreationError("bot_001", "Token 無效")
        
        assert isinstance(error, SubBotError)
        assert isinstance(error, ROASBotError)
        assert error.bot_id == "bot_001"
        assert error.reason == "Token 無效"
        assert "子機器人創建失敗" in error.message
        assert error.details["reason"] == "Token 無效"
        
    def test_sub_bot_token_error(self):
        """Test SubBotTokenError functionality"""
        error = SubBotTokenError("bot_002", "權限不足")
        
        assert isinstance(error, SubBotError)
        assert error.bot_id == "bot_002"
        assert error.token_issue == "權限不足"
        assert "Token 錯誤" in error.message
        
    def test_sub_bot_channel_error(self):
        """Test SubBotChannelError functionality"""
        error = SubBotChannelError("bot_003", "123456789", "join", "頻道不存在")
        
        assert isinstance(error, SubBotError)
        assert error.bot_id == "bot_003"
        assert error.channel_id == "123456789"
        assert error.operation == "join"
        assert error.reason == "頻道不存在"
        assert "頻道操作失敗" in error.message


class TestAIServiceErrors:
    """Test AI service errors"""
    
    def test_ai_provider_error(self):
        """Test AIProviderError functionality"""
        error = AIProviderError("openai", "chat_completion", "API金鑰無效")
        
        assert isinstance(error, AIServiceError)
        assert isinstance(error, ROASBotError)
        assert error.provider == "openai"
        assert error.operation == "chat_completion"
        assert error.api_error == "API金鑰無效"
        assert "AI提供商錯誤" in error.message
        
    def test_ai_quota_exceeded_error(self):
        """Test AIQuotaExceededError functionality"""
        error = AIQuotaExceededError("user_123", "daily", 100, 105)
        
        assert isinstance(error, AIServiceError)
        assert error.user_id == "user_123"
        assert error.quota_type == "daily"
        assert error.limit == 100
        assert error.current_usage == 105
        assert "配額超限" in error.message
        
    def test_ai_response_error(self):
        """Test AIResponseError functionality"""
        error = AIResponseError("anthropic", "claude-3-sonnet", "回應格式錯誤")
        
        assert isinstance(error, AIServiceError)
        assert error.provider == "anthropic"
        assert error.model == "claude-3-sonnet"
        assert error.issue == "回應格式錯誤"
        assert "AI回應錯誤" in error.message


class TestSecurityErrors:
    """Test security errors"""
    
    def test_content_filter_error(self):
        """Test ContentFilterError functionality"""
        error = ContentFilterError("user_input", "profanity_filter", "包含不當言語")
        
        assert isinstance(error, SecurityError)
        assert isinstance(error, ROASBotError)
        assert error.content_type == "user_input"
        assert error.filter_rule == "profanity_filter"
        assert error.violation == "包含不當言語"
        assert error.security_context == "content_filter"
        assert "內容過濾失敗" in error.message
        
    def test_authentication_error(self):
        """Test AuthenticationError functionality"""
        error = AuthenticationError("discord", "user_456", "Token已過期")
        
        assert isinstance(error, SecurityError)
        assert error.auth_type == "discord"
        assert error.user_info == "user_456"
        assert error.reason == "Token已過期"
        assert error.security_context == "authentication"
        assert "身份驗證失敗" in error.message


class TestErrorInheritanceHierarchy:
    """Test error class inheritance hierarchy"""
    
    def test_deployment_error_hierarchy(self):
        """Test deployment error inheritance chain"""
        error = EnvironmentError("docker", "test")
        
        assert isinstance(error, EnvironmentError)
        assert isinstance(error, DeploymentError)
        assert isinstance(error, ROASBotError)
        assert isinstance(error, AppError)
        assert isinstance(error, Exception)
        
    def test_sub_bot_error_hierarchy(self):
        """Test sub-bot error inheritance chain"""
        error = SubBotCreationError("bot_1", "test")
        
        assert isinstance(error, SubBotCreationError)
        assert isinstance(error, SubBotError)
        assert isinstance(error, ROASBotError)
        assert isinstance(error, AppError)
        assert isinstance(error, Exception)
        
    def test_ai_service_error_hierarchy(self):
        """Test AI service error inheritance chain"""
        error = AIProviderError("openai", "test", "test")
        
        assert isinstance(error, AIProviderError)
        assert isinstance(error, AIServiceError)
        assert isinstance(error, ROASBotError)
        assert isinstance(error, AppError)
        assert isinstance(error, Exception)
        
    def test_security_error_hierarchy(self):
        """Test security error inheritance chain"""
        error = ContentFilterError("input", "rule", "test")
        
        assert isinstance(error, ContentFilterError)
        assert isinstance(error, SecurityError)
        assert isinstance(error, ROASBotError)
        assert isinstance(error, AppError)
        assert isinstance(error, Exception)


class TestErrorSerialization:
    """Test error serialization capabilities"""
    
    def test_error_json_serialization(self):
        """Test that errors can be JSON serialized"""
        error = AIQuotaExceededError("user_123", "daily", 100, 105)
        error_dict = error.to_dict()
        
        # 測試可以JSON序列化
        json_str = json.dumps(error_dict, default=str)
        restored = json.loads(json_str)
        
        assert restored["error_type"] == "AIQuotaExceededError"
        assert restored["details"]["user_id"] == "user_123"
        assert restored["details"]["current_usage"] == 105
        
    def test_all_new_errors_have_required_attributes(self):
        """Test that all new error types have required attributes"""
        error_instances = [
            EnvironmentError("docker", "test"),
            DependencyInstallError("dep", "method", "reason"),
            ServiceStartupError("service", "mode", "reason"),
            SubBotCreationError("bot_id", "reason"),
            SubBotTokenError("bot_id", "issue"),
            SubBotChannelError("bot_id", "channel", "op", "reason"),
            AIProviderError("provider", "op", "error"),
            AIQuotaExceededError("user", "type", 100, 101),
            AIResponseError("provider", "model", "issue"),
            ContentFilterError("type", "rule", "violation"),
            AuthenticationError("type", "user", "reason")
        ]
        
        for error in error_instances:
            # 檢查必要屬性
            assert hasattr(error, 'error_code')
            assert hasattr(error, 'timestamp')
            assert hasattr(error, 'message')
            assert hasattr(error, 'details')
            
            # 檢查屬性類型
            assert isinstance(error.error_code, str)
            assert isinstance(error.timestamp, datetime)
            assert isinstance(error.message, str)
            assert isinstance(error.details, dict)
            
            # 檢查to_dict方法
            error_dict = error.to_dict()
            assert "error_type" in error_dict
            assert "error_code" in error_dict
            assert "timestamp" in error_dict