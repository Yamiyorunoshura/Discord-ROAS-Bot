"""
Core module for roas-bot application
Task ID: T2

This module provides the core infrastructure for the new architecture including:
- Error handling system
- Configuration management  
- Logging system
- Common utilities
"""

from .errors import *
from .error_codes import ErrorCode, map_exception_to_error_code, format_error_response
from .config import AppConfig, get_config, load_config
from .logging import get_logger, log_context, initialize_logging

__all__ = [
    # Error handling
    'AppError',
    'ServiceError', 
    'DatabaseError',
    'PermissionError',
    'ValidationError',
    'NotFoundError',
    'ConfigurationError',
    'ExternalServiceError',
    
    # Error codes
    'ErrorCode',
    'map_exception_to_error_code',
    'format_error_response',
    
    # Configuration
    'AppConfig',
    'get_config', 
    'load_config',
    
    # Logging
    'get_logger',
    'log_context',
    'initialize_logging',
]