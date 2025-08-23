"""
Unit tests for src.core.errors module
Task ID: T2 - App architecture baseline and scaffolding
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from src.core.errors import (
    AppError, ServiceError, DatabaseError, PermissionError,
    ValidationError, NotFoundError, ConfigurationError, 
    ExternalServiceError, create_error
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