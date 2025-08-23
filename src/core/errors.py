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
        'AppError': AppError,
        'ServiceError': ServiceError,
        'DatabaseError': DatabaseError,
        'PermissionError': PermissionError,
        'ValidationError': ValidationError,
        'NotFoundError': NotFoundError,
        'ConfigurationError': ConfigurationError,
        'ExternalServiceError': ExternalServiceError,
    }
    
    error_class = error_classes.get(error_type, AppError)
    
    try:
        return error_class(**kwargs)
    except TypeError:
        # If the constructor fails due to missing arguments, 
        # fall back to AppError with a message
        message = kwargs.get('message', f'Error of type {error_type}')
        return AppError(message, error_code=error_type.upper())