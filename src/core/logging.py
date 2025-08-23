"""
Unified Logging System
Task ID: T2 - App architecture baseline and scaffolding

This module provides a centralized logging system for the roas-bot application.
It supports structured logging, sensitive data filtering, and multi-destination output.
"""

import logging
import logging.handlers
import sys
import os
import re
import json
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

from .config import AppConfig, get_config
from .errors import ConfigurationError


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter to remove sensitive information from log messages
    
    Filters out patterns that might contain sensitive data like tokens, passwords, etc.
    """
    
    def __init__(self, sensitive_patterns: List[str]):
        """
        Initialize the sensitive data filter
        
        Args:
            sensitive_patterns: List of regex patterns to filter out
        """
        super().__init__()
        self.sensitive_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in sensitive_patterns]
        
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records to remove sensitive data
        
        Args:
            record: Log record to filter
            
        Returns:
            True if record should be logged (after filtering)
        """
        # Filter the main message
        record.msg = self._sanitize_message(record.msg)
        
        # Filter arguments if present
        if record.args:
            sanitized_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    sanitized_args.append(self._sanitize_message(arg))
                elif isinstance(arg, dict):
                    sanitized_args.append(self._sanitize_dict(arg))
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)
            
        return True
        
    def _sanitize_message(self, message: str) -> str:
        """Sanitize a string message"""
        if not isinstance(message, str):
            return message
            
        sanitized = message
        for pattern in self.sensitive_patterns:
            sanitized = pattern.sub('***FILTERED***', sanitized)
            
        return sanitized
        
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize dictionary data"""
        sanitized = {}
        for key, value in data.items():
            # Check if key indicates sensitive data
            key_lower = key.lower()
            is_sensitive_key = any(
                pattern.search(key_lower) for pattern in self.sensitive_patterns
            )
            
            if is_sensitive_key:
                sanitized[key] = "***FILTERED***"
            elif isinstance(value, str):
                sanitized[key] = self._sanitize_message(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            else:
                sanitized[key] = value
                
        return sanitized


class ContextFilter(logging.Filter):
    """
    Logging filter to add contextual information to log records
    """
    
    def __init__(self):
        super().__init__()
        self.context_data = {}
        
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add context data to log record
        
        Args:
            record: Log record to enhance
            
        Returns:
            True (always log the record)
        """
        # Add context data to the record
        for key, value in self.context_data.items():
            setattr(record, key, value)
            
        # Add timestamp if not present
        if not hasattr(record, 'timestamp'):
            record.timestamp = datetime.utcnow().isoformat()
            
        return True
        
    def set_context(self, **kwargs):
        """Set context data"""
        self.context_data.update(kwargs)
        
    def clear_context(self):
        """Clear all context data"""
        self.context_data.clear()


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    """
    
    def __init__(self, include_extra: bool = True):
        """
        Initialize JSON formatter
        
        Args:
            include_extra: Whether to include extra fields in JSON output
        """
        super().__init__()
        self.include_extra = include_extra
        
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted log string
        """
        # Base log data
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields if requested
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                              'pathname', 'filename', 'module', 'lineno', 
                              'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process',
                              'exc_info', 'exc_text', 'stack_info']:
                    log_data[key] = value
                    
        try:
            return json.dumps(log_data, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            # Fallback to string representation if JSON serialization fails
            return str(log_data)


class LogManager:
    """
    Centralized logging manager for the application
    
    Provides unified logging configuration and management across all components.
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        Initialize the logging manager
        
        Args:
            config: Application configuration (loads from global config if not provided)
        """
        self.config = config or get_config()
        self.loggers: Dict[str, logging.Logger] = {}
        self.context_filter: Optional[ContextFilter] = None
        self.sensitive_filter: Optional[SensitiveDataFilter] = None
        self._initialized = False
        
    def initialize(self) -> None:
        """Initialize the logging system"""
        if self._initialized:
            return
            
        try:
            # Create log directory if it doesn't exist
            log_dir = Path(self.config.logging.log_directory)
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filters
            self.context_filter = ContextFilter()
            self.sensitive_filter = SensitiveDataFilter(
                self.config.security.sensitive_data_patterns
            )
            
            # Configure root logger
            self._configure_root_logger()
            
            # Create default loggers
            self._create_default_loggers()
            
            self._initialized = True
            
        except Exception as e:
            raise ConfigurationError(
                "logging_initialization",
                f"Failed to initialize logging system: {str(e)}",
                cause=e
            )
            
    def _configure_root_logger(self) -> None:
        """Configure the root logger"""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.logging.level.upper()))
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Add console handler if enabled
        if self.config.logging.console_handler_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(self.config.logging.format))
            console_handler.addFilter(self.sensitive_filter)
            root_logger.addHandler(console_handler)
            
    def _create_default_loggers(self) -> None:
        """Create default application loggers"""
        logger_configs = [
            ("main", self.config.logging.main_log_file),
            ("error", self.config.logging.error_log_file),
            ("database", self.config.logging.database_log_file),
            ("achievement", self.config.logging.achievement_log_file),
            ("economy", self.config.logging.economy_log_file),
            ("government", self.config.logging.government_log_file),
        ]
        
        for logger_name, log_file in logger_configs:
            self.create_logger(logger_name, log_file)
            
    def create_logger(self, 
                     name: str, 
                     log_file: Optional[str] = None,
                     level: Optional[str] = None,
                     format_type: str = "standard") -> logging.Logger:
        """
        Create a new logger with the specified configuration
        
        Args:
            name: Logger name
            log_file: Optional log file name
            level: Optional log level (defaults to config level)
            format_type: Formatter type ("standard" or "json")
            
        Returns:
            Configured logger instance
        """
        if name in self.loggers:
            return self.loggers[name]
            
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, (level or self.config.logging.level).upper()))
        
        # Clear any existing handlers
        logger.handlers.clear()
        logger.propagate = False
        
        # Add file handler if log file is specified
        if log_file and self.config.logging.file_handler_enabled:
            log_path = Path(self.config.logging.log_directory) / log_file
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=self.config.logging.max_file_size,
                backupCount=self.config.logging.backup_count,
                encoding='utf-8'
            )
            
            # Choose formatter based on format type
            if format_type == "json":
                formatter = JSONFormatter()
            else:
                formatter = logging.Formatter(self.config.logging.format)
                
            file_handler.setFormatter(formatter)
            file_handler.addFilter(self.sensitive_filter)
            file_handler.addFilter(self.context_filter)
            
            logger.addHandler(file_handler)
            
        # Add console handler for error level and above
        if logger.name == "error" or level == "ERROR":
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(logging.Formatter(self.config.logging.format))
            console_handler.addFilter(self.sensitive_filter)
            console_handler.setLevel(logging.ERROR)
            logger.addHandler(console_handler)
            
        self.loggers[name] = logger
        return logger
        
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get an existing logger or create a new one
        
        Args:
            name: Logger name
            
        Returns:
            Logger instance
        """
        if not self._initialized:
            self.initialize()
            
        if name not in self.loggers:
            return self.create_logger(name)
            
        return self.loggers[name]
        
    @contextmanager
    def log_context(self, **kwargs):
        """
        Context manager for adding contextual information to logs
        
        Args:
            **kwargs: Context data to add to log records
        """
        if self.context_filter:
            # Store existing context
            old_context = self.context_filter.context_data.copy()
            
            # Add new context
            self.context_filter.set_context(**kwargs)
            
            try:
                yield
            finally:
                # Restore old context
                self.context_filter.context_data = old_context
        else:
            yield
            
    def shutdown(self) -> None:
        """Shutdown the logging system"""
        for logger in self.loggers.values():
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()
            
        self.loggers.clear()
        self._initialized = False


# Global logging manager instance
_log_manager: Optional[LogManager] = None


def get_log_manager() -> LogManager:
    """Get the global logging manager instance"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
        _log_manager.initialize()
    return _log_manager


def get_logger(name: str) -> logging.Logger:
    """Get a logger by name"""
    return get_log_manager().get_logger(name)


def log_context(**kwargs):
    """Context manager for adding contextual information to logs"""
    return get_log_manager().log_context(**kwargs)


def initialize_logging(config: Optional[AppConfig] = None) -> None:
    """Initialize the logging system"""
    global _log_manager
    _log_manager = LogManager(config)
    _log_manager.initialize()


def shutdown_logging() -> None:
    """Shutdown the logging system"""
    global _log_manager
    if _log_manager:
        _log_manager.shutdown()
        _log_manager = None