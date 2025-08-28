"""
Core Error Handling System
Task ID: T2 - App architecture baseline and scaffolding

This module provides a comprehensive error handling hierarchy for the roas-bot application.
It defines custom exception classes that align with different error scenarios and business logic.
"""

from typing import Optional, Any, Dict
import traceback
from datetime import datetime


class AppError(Exception):
    """
    Base application error class
    
    All custom exceptions in the application should inherit from this class.
    Provides common error handling functionality and consistent error formatting.
    """
    
    def __init__(self, 
                 message: str, 
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        """
        Initialize the application error
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code for API/logging
            details: Additional error context and metadata
            cause: The underlying exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.utcnow()
        
        # Capture stack trace if available
        self.stack_trace = traceback.format_exc() if cause else None
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary representation
        
        Returns:
            Dictionary containing error information
        """
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None,
            "stack_trace": self.stack_trace
        }
        
    def __str__(self) -> str:
        """String representation of the error"""
        if self.details:
            return f"{self.message} (Code: {self.error_code}, Details: {self.details})"
        return f"{self.message} (Code: {self.error_code})"


class ServiceError(AppError):
    """
    Service layer error
    
    Raised when errors occur in service layer business logic.
    """
    
    def __init__(self, 
                 service_name: str,
                 operation: str,
                 message: str,
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        """
        Initialize the service error
        
        Args:
            service_name: Name of the service where error occurred
            operation: Operation that was being performed
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
            cause: The underlying exception
        """
        enhanced_details = {
            "service_name": service_name,
            "operation": operation,
            **(details or {})
        }
        
        super().__init__(
            message=f"[{service_name}] {operation}: {message}",
            error_code=error_code or "SERVICE_ERROR",
            details=enhanced_details,
            cause=cause
        )
        
        self.service_name = service_name
        self.operation = operation


class DatabaseError(AppError):
    """
    Database operation error
    
    Raised when database operations fail or encounter issues.
    """
    
    def __init__(self,
                 operation: str,
                 message: str, 
                 query: Optional[str] = None,
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        """
        Initialize the database error
        
        Args:
            operation: Database operation that failed
            message: Human-readable error message
            query: SQL query or operation details (sanitized)
            error_code: Machine-readable error code
            details: Additional error context
            cause: The underlying database exception
        """
        enhanced_details = {
            "operation": operation,
            "query": query,
            **(details or {})
        }
        
        super().__init__(
            message=f"Database {operation}: {message}",
            error_code=error_code or "DATABASE_ERROR",
            details=enhanced_details,
            cause=cause
        )
        
        self.operation = operation
        self.query = query


class PermissionError(AppError):
    """
    Permission and authorization error
    
    Raised when users don't have sufficient permissions for an operation.
    """
    
    def __init__(self,
                 user_id: Optional[int] = None,
                 guild_id: Optional[int] = None,
                 required_permission: Optional[str] = None,
                 message: str = "Permission denied",
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize the permission error
        
        Args:
            user_id: Discord user ID attempting the operation
            guild_id: Discord guild ID where operation was attempted
            required_permission: Permission that was required
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
        """
        enhanced_details = {
            "user_id": user_id,
            "guild_id": guild_id, 
            "required_permission": required_permission,
            **(details or {})
        }
        
        super().__init__(
            message=message,
            error_code=error_code or "PERMISSION_DENIED",
            details=enhanced_details
        )
        
        self.user_id = user_id
        self.guild_id = guild_id
        self.required_permission = required_permission


class ValidationError(AppError):
    """
    Input validation error
    
    Raised when user input or data fails validation checks.
    """
    
    def __init__(self,
                 field: str,
                 value: Any,
                 validation_rule: str,
                 message: Optional[str] = None,
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize the validation error
        
        Args:
            field: Field name that failed validation
            value: Value that failed validation (will be sanitized)
            validation_rule: Description of the validation rule that failed
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
        """
        # Sanitize sensitive values
        sanitized_value = str(value)[:100] if value is not None else None
        
        default_message = f"Validation failed for field '{field}': {validation_rule}"
        
        enhanced_details = {
            "field": field,
            "value": sanitized_value,
            "validation_rule": validation_rule,
            **(details or {})
        }
        
        super().__init__(
            message=message or default_message,
            error_code=error_code or "VALIDATION_ERROR",
            details=enhanced_details
        )
        
        self.field = field
        self.value = sanitized_value
        self.validation_rule = validation_rule


class NotFoundError(AppError):
    """
    Resource not found error
    
    Raised when a requested resource cannot be found.
    """
    
    def __init__(self,
                 resource_type: str,
                 resource_id: Any,
                 message: Optional[str] = None,
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize the not found error
        
        Args:
            resource_type: Type of resource that was not found
            resource_id: Identifier of the resource that was not found
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
        """
        default_message = f"{resource_type} not found: {resource_id}"
        
        enhanced_details = {
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            **(details or {})
        }
        
        super().__init__(
            message=message or default_message,
            error_code=error_code or "NOT_FOUND",
            details=enhanced_details
        )
        
        self.resource_type = resource_type
        self.resource_id = str(resource_id)


class ConfigurationError(AppError):
    """
    Configuration error
    
    Raised when there are issues with application configuration.
    """
    
    def __init__(self,
                 config_key: str,
                 message: str,
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        """
        Initialize the configuration error
        
        Args:
            config_key: Configuration key that has an issue
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
            cause: The underlying exception that caused this error
        """
        enhanced_details = {
            "config_key": config_key,
            **(details or {})
        }
        
        super().__init__(
            message=f"Configuration error for '{config_key}': {message}",
            error_code=error_code or "CONFIG_ERROR",
            details=enhanced_details,
            cause=cause
        )
        
        self.config_key = config_key


class ExternalServiceError(AppError):
    """
    External service integration error
    
    Raised when external API calls or service integrations fail.
    """
    
    def __init__(self,
                 service_name: str,
                 operation: str,
                 status_code: Optional[int] = None,
                 message: str = "External service error",
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        """
        Initialize the external service error
        
        Args:
            service_name: Name of the external service
            operation: Operation that was being performed
            status_code: HTTP status code if applicable
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
            cause: The underlying exception
        """
        enhanced_details = {
            "service_name": service_name,
            "operation": operation,
            "status_code": status_code,
            **(details or {})
        }
        
        super().__init__(
            message=f"External service '{service_name}' {operation}: {message}",
            error_code=error_code or "EXTERNAL_SERVICE_ERROR",
            details=enhanced_details,
            cause=cause
        )
        
        self.service_name = service_name
        self.operation = operation
        self.status_code = status_code


# ========== ROAS Bot v2.4.4 Specific Error Classes ==========

class ROASBotError(AppError):
    """
    ROAS Bot 基礎錯誤類別
    
    v2.4.4版本的基礎錯誤類別，所有ROAS Bot特定錯誤都繼承自此類別
    包含error_code和timestamp屬性，與現有錯誤處理中間件完全整合
    """
    
    def __init__(self, 
                 message: str, 
                 error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        """
        Initialize the ROAS Bot error
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code for API/logging
            details: Additional error context and metadata
            cause: The underlying exception that caused this error
        """
        super().__init__(message, error_code, details, cause)
        # Ensure error_code and timestamp are always present
        if not hasattr(self, 'error_code') or not self.error_code:
            self.error_code = self.__class__.__name__.upper()
        if not hasattr(self, 'timestamp'):
            self.timestamp = datetime.utcnow()


# ========== Deployment System Error Classes ==========

class DeploymentError(ROASBotError):
    """部署相關錯誤基礎類別"""
    
    def __init__(self, message: str, deployment_mode: Optional[str] = None, **kwargs):
        super().__init__(message=message, **kwargs)
        self.deployment_mode = deployment_mode
        if deployment_mode:
            self.details["deployment_mode"] = deployment_mode

class EnvironmentError(DeploymentError):
    """環境檢測錯誤"""
    
    def __init__(self, environment_type: str, check_failed: str, **kwargs):
        message = f"環境檢測失敗 ({environment_type}): {check_failed}"
        super().__init__(message=message, deployment_mode=environment_type, **kwargs)
        self.environment_type = environment_type
        self.check_failed = check_failed
        self.details.update({
            "environment_type": environment_type,
            "check_failed": check_failed
        })

class DependencyInstallError(DeploymentError):
    """依賴安裝錯誤"""
    
    def __init__(self, dependency_name: str, install_method: str, reason: str, **kwargs):
        message = f"依賴安裝失敗 ({dependency_name} via {install_method}): {reason}"
        super().__init__(message=message, deployment_mode=install_method, **kwargs)
        self.dependency_name = dependency_name
        self.install_method = install_method
        self.reason = reason
        self.details.update({
            "dependency_name": dependency_name,
            "install_method": install_method,
            "reason": reason
        })

class ServiceStartupError(DeploymentError):
    """服務啟動錯誤"""
    
    def __init__(self, service_name: str, startup_mode: str, reason: str, **kwargs):
        message = f"服務啟動失敗 ({service_name} in {startup_mode} mode): {reason}"
        super().__init__(message=message, deployment_mode=startup_mode, **kwargs)
        self.service_name = service_name
        self.startup_mode = startup_mode
        self.reason = reason
        self.details.update({
            "service_name": service_name,
            "startup_mode": startup_mode,
            "reason": reason
        })


# ========== Sub-Bot System Error Classes ==========

class SubBotError(ROASBotError):
    """子機器人相關錯誤基礎類別"""
    
    def __init__(self, message: str, bot_id: Optional[str] = None, **kwargs):
        super().__init__(message=message, **kwargs)
        self.bot_id = bot_id
        if bot_id:
            self.details["bot_id"] = bot_id

class SubBotCreationError(SubBotError):
    """子機器人創建錯誤"""
    
    def __init__(self, bot_id: str, reason: str, **kwargs):
        message = f"子機器人創建失敗 (ID: {bot_id}): {reason}"
        super().__init__(message=message, bot_id=bot_id, **kwargs)
        self.reason = reason
        self.details["reason"] = reason

class SubBotTokenError(SubBotError):
    """子機器人 Token 錯誤"""
    
    def __init__(self, bot_id: str, token_issue: str, **kwargs):
        message = f"子機器人 Token 錯誤 (ID: {bot_id}): {token_issue}"
        super().__init__(message=message, bot_id=bot_id, **kwargs)
        self.token_issue = token_issue
        self.details["token_issue"] = token_issue

class SubBotChannelError(SubBotError):
    """子機器人頻道配置錯誤"""
    
    def __init__(self, bot_id: str, channel_id: Optional[str], operation: str, reason: str, **kwargs):
        channel_info = f"Channel: {channel_id}" if channel_id else "No channel specified"
        message = f"子機器人頻道操作失敗 (Bot: {bot_id}, {channel_info}, Op: {operation}): {reason}"
        super().__init__(message=message, bot_id=bot_id, **kwargs)
        self.channel_id = channel_id
        self.operation = operation
        self.reason = reason
        self.details.update({
            "channel_id": channel_id,
            "operation": operation,
            "reason": reason
        })


# ========== AI Service Error Classes ==========

class AIServiceError(ROASBotError):
    """AI 服務相關錯誤基礎類別"""
    
    def __init__(self, message: str, provider: Optional[str] = None, model: Optional[str] = None, **kwargs):
        super().__init__(message=message, **kwargs)
        self.provider = provider
        self.model = model
        if provider:
            self.details["provider"] = provider
        if model:
            self.details["model"] = model

class AIProviderError(AIServiceError):
    """AI 提供商錯誤"""
    
    def __init__(self, provider: str, operation: str, api_error: str, **kwargs):
        message = f"AI提供商錯誤 ({provider} - {operation}): {api_error}"
        super().__init__(message=message, provider=provider, **kwargs)
        self.operation = operation
        self.api_error = api_error
        self.details.update({
            "operation": operation,
            "api_error": api_error
        })

class AIQuotaExceededError(AIServiceError):
    """AI 配額超限錯誤"""
    
    def __init__(self, user_id: str, quota_type: str, limit: int, current_usage: int, **kwargs):
        message = f"AI配額超限 (User: {user_id}, Type: {quota_type}): {current_usage}/{limit}"
        super().__init__(message=message, **kwargs)
        self.user_id = user_id
        self.quota_type = quota_type
        self.limit = limit
        self.current_usage = current_usage
        self.details.update({
            "user_id": user_id,
            "quota_type": quota_type,
            "limit": limit,
            "current_usage": current_usage
        })

class AIResponseError(AIServiceError):
    """AI 回應錯誤"""
    
    def __init__(self, provider: str, model: str, issue: str, **kwargs):
        message = f"AI回應錯誤 ({provider}/{model}): {issue}"
        super().__init__(message=message, provider=provider, model=model, **kwargs)
        self.issue = issue
        self.details["issue"] = issue


# ========== Security Error Classes ==========

class SecurityError(ROASBotError):
    """安全相關錯誤基礎類別"""
    
    def __init__(self, message: str, security_context: Optional[str] = None, **kwargs):
        super().__init__(message=message, **kwargs)
        self.security_context = security_context
        if security_context:
            self.details["security_context"] = security_context

class ContentFilterError(SecurityError):
    """內容過濾錯誤"""
    
    def __init__(self, content_type: str, filter_rule: str, violation: str, **kwargs):
        message = f"內容過濾失敗 ({content_type} - {filter_rule}): {violation}"
        super().__init__(message=message, security_context="content_filter", **kwargs)
        self.content_type = content_type
        self.filter_rule = filter_rule
        self.violation = violation
        self.details.update({
            "content_type": content_type,
            "filter_rule": filter_rule,
            "violation": violation
        })

class AuthenticationError(SecurityError):
    """身份驗證錯誤"""
    
    def __init__(self, auth_type: str, user_info: str, reason: str, **kwargs):
        message = f"身份驗證失敗 ({auth_type} - {user_info}): {reason}"
        super().__init__(message=message, security_context="authentication", **kwargs)
        self.auth_type = auth_type
        self.user_info = user_info  # Should be sanitized before passing
        self.reason = reason
        self.details.update({
            "auth_type": auth_type,
            "user_info": user_info,
            "reason": reason
        })


# Convenience function for error handling
def create_error(error_type: str, **kwargs) -> AppError:
    """
    Factory function for creating errors by type name
    
    Args:
        error_type: Name of the error class
        **kwargs: Arguments to pass to the error constructor
        
    Returns:
        Instance of the specified error type
    """
    error_classes = {
        # Original error classes
        'AppError': AppError,
        'ServiceError': ServiceError,
        'DatabaseError': DatabaseError,
        'PermissionError': PermissionError,
        'ValidationError': ValidationError,
        'NotFoundError': NotFoundError,
        'ConfigurationError': ConfigurationError,
        'ExternalServiceError': ExternalServiceError,
        
        # ROAS Bot v2.4.4 specific error classes
        'ROASBotError': ROASBotError,
        
        # Deployment error classes
        'DeploymentError': DeploymentError,
        'EnvironmentError': EnvironmentError,
        'DependencyInstallError': DependencyInstallError,
        'ServiceStartupError': ServiceStartupError,
        
        # Sub-Bot error classes
        'SubBotError': SubBotError,
        'SubBotCreationError': SubBotCreationError,
        'SubBotTokenError': SubBotTokenError,
        'SubBotChannelError': SubBotChannelError,
        
        # AI Service error classes
        'AIServiceError': AIServiceError,
        'AIProviderError': AIProviderError,
        'AIQuotaExceededError': AIQuotaExceededError,
        'AIResponseError': AIResponseError,
        
        # Security error classes
        'SecurityError': SecurityError,
        'ContentFilterError': ContentFilterError,
        'AuthenticationError': AuthenticationError,
    }
    
    error_class = error_classes.get(error_type, AppError)
    
    try:
        return error_class(**kwargs)
    except TypeError:
        # If the constructor fails due to missing arguments, 
        # fall back to AppError with a message
        message = kwargs.get('message', f'Error of type {error_type}')
        return AppError(message, error_code=error_type.upper())