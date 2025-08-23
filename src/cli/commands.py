"""
Base Command Classes and Command Registry
Task ID: T11 - Terminal interactive management mode

This module provides the base command architecture and command registry system
for the interactive terminal management interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import re
from datetime import datetime

from src.core.logging import get_logger
from src.core.errors import ValidationError


class CommandResult:
    """
    Represents the result of a command execution
    """
    
    def __init__(self, 
                 success: bool = True,
                 message: str = "",
                 data: Optional[Dict[str, Any]] = None,
                 error: Optional[Exception] = None):
        """
        Initialize command result
        
        Args:
            success: Whether command executed successfully
            message: Human-readable result message
            data: Additional result data
            error: Exception if command failed
        """
        self.success = success
        self.message = message
        self.data = data or {}
        self.error = error
        self.timestamp = datetime.utcnow()
        
    def __str__(self) -> str:
        """String representation of the result"""
        if self.success:
            return f"✅ {self.message}" if self.message else "✅ Command executed successfully"
        else:
            error_info = f" - {str(self.error)}" if self.error else ""
            return f"❌ {self.message}{error_info}" if self.message else f"❌ Command failed{error_info}"


class BaseCommand(ABC):
    """
    Abstract base class for all terminal commands
    
    All commands must inherit from this class and implement the required methods.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize the command
        
        Args:
            name: Command name (used for invocation)
            description: Short description of what the command does
        """
        self.name = name.lower()
        self.description = description
        self.logger = get_logger(f"command.{self.name}")
        
    @abstractmethod
    async def execute(self, args: List[str]) -> CommandResult:
        """
        Execute the command with given arguments
        
        Args:
            args: List of command arguments
            
        Returns:
            CommandResult with execution status and output
        """
        pass
        
    @abstractmethod
    def get_help(self) -> str:
        """
        Get detailed help text for the command
        
        Returns:
            Multi-line help text including syntax and examples
        """
        pass
        
    def get_syntax(self) -> str:
        """
        Get the command syntax
        
        Returns:
            Command syntax string (default implementation)
        """
        return f"{self.name} [options]"
        
    def validate_args(self, args: List[str], min_args: int = 0, max_args: Optional[int] = None) -> None:
        """
        Validate command arguments
        
        Args:
            args: Arguments to validate
            min_args: Minimum required arguments
            max_args: Maximum allowed arguments (None = unlimited)
            
        Raises:
            ValidationError: If arguments are invalid
        """
        arg_count = len(args)
        
        if arg_count < min_args:
            raise ValidationError(
                field="args",
                value=args,
                validation_rule=f"minimum {min_args} arguments required",
                message=f"Command '{self.name}' requires at least {min_args} arguments, got {arg_count}"
            )
            
        if max_args is not None and arg_count > max_args:
            raise ValidationError(
                field="args", 
                value=args,
                validation_rule=f"maximum {max_args} arguments allowed",
                message=f"Command '{self.name}' accepts at most {max_args} arguments, got {arg_count}"
            )
            
    def sanitize_input(self, input_str: str) -> str:
        """
        Sanitize user input to prevent injection attacks
        
        Args:
            input_str: Input string to sanitize
            
        Returns:
            Sanitized input string
        """
        # Remove control characters and limit length
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', input_str)
        return sanitized[:1000]  # Limit to 1000 characters
        
    def log_command_execution(self, args: List[str], result: CommandResult) -> None:
        """
        Log command execution for audit purposes
        
        Args:
            args: Command arguments (sanitized)
            result: Command execution result
        """
        # Sanitize arguments for logging
        sanitized_args = [self.sanitize_input(str(arg)) for arg in args]
        
        log_data = {
            "command": self.name,
            "args": sanitized_args,
            "success": result.success,
            "message": result.message,
            "timestamp": result.timestamp.isoformat()
        }
        
        if result.success:
            self.logger.info("Command executed successfully", extra=log_data)
        else:
            self.logger.error("Command execution failed", extra={
                **log_data,
                "error": str(result.error) if result.error else "Unknown error"
            })


class CommandRegistry:
    """
    Central registry for managing all available terminal commands
    
    Provides command registration, discovery, and execution management.
    """
    
    def __init__(self):
        """Initialize the command registry"""
        self.commands: Dict[str, BaseCommand] = {}
        self.logger = get_logger("command_registry")
        
    def register_command(self, command: BaseCommand) -> None:
        """
        Register a command in the registry
        
        Args:
            command: Command instance to register
            
        Raises:
            ValidationError: If command name is invalid or already exists
        """
        # Validate command name
        if not command.name:
            raise ValidationError(
                field="command_name",
                value=command.name,
                validation_rule="non-empty string",
                message="Command name cannot be empty"
            )
            
        if not re.match(r'^[a-z][a-z0-9_-]*$', command.name):
            raise ValidationError(
                field="command_name",
                value=command.name,
                validation_rule="alphanumeric with dashes and underscores",
                message=f"Invalid command name '{command.name}': must start with letter and contain only lowercase letters, numbers, dashes and underscores"
            )
            
        # Check for conflicts
        if command.name in self.commands:
            self.logger.warning(f"Overriding existing command: {command.name}")
            
        self.commands[command.name] = command
        self.logger.debug(f"Registered command: {command.name}")
        
    def unregister_command(self, command_name: str) -> bool:
        """
        Unregister a command from the registry
        
        Args:
            command_name: Name of command to unregister
            
        Returns:
            True if command was found and removed, False otherwise
        """
        command_name = command_name.lower()
        if command_name in self.commands:
            del self.commands[command_name]
            self.logger.debug(f"Unregistered command: {command_name}")
            return True
        return False
        
    def find_command(self, command_name: str) -> Optional[BaseCommand]:
        """
        Find a command by name
        
        Args:
            command_name: Name of command to find
            
        Returns:
            Command instance if found, None otherwise
        """
        return self.commands.get(command_name.lower())
        
    def get_all_commands(self) -> List[BaseCommand]:
        """
        Get all registered commands
        
        Returns:
            List of all registered command instances
        """
        return list(self.commands.values())
        
    def get_command_names(self) -> List[str]:
        """
        Get names of all registered commands
        
        Returns:
            Sorted list of command names
        """
        return sorted(self.commands.keys())
        
    def find_similar_commands(self, command_name: str, max_suggestions: int = 3) -> List[str]:
        """
        Find commands with similar names (for typo suggestions)
        
        Args:
            command_name: The incorrectly typed command name
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of similar command names
        """
        command_name = command_name.lower()
        suggestions = []
        
        for cmd_name in self.commands.keys():
            # Simple similarity based on common prefixes and character overlap
            if (cmd_name.startswith(command_name[:2]) or 
                command_name.startswith(cmd_name[:2]) or
                command_name in cmd_name or
                cmd_name in command_name):
                suggestions.append(cmd_name)
                
        return suggestions[:max_suggestions]
        
    async def execute_command(self, command_name: str, args: List[str]) -> CommandResult:
        """
        Execute a command by name
        
        Args:
            command_name: Name of command to execute
            args: Command arguments
            
        Returns:
            CommandResult with execution status and output
        """
        command = self.find_command(command_name)
        
        if not command:
            # Try to find similar commands for suggestions
            suggestions = self.find_similar_commands(command_name)
            if suggestions:
                suggestion_text = ", ".join(suggestions)
                message = f"Unknown command: {command_name}. Did you mean: {suggestion_text}?"
            else:
                message = f"Unknown command: {command_name}. Type 'help' for available commands."
                
            return CommandResult(
                success=False,
                message=message
            )
            
        try:
            # Execute the command
            result = await command.execute(args)
            
            # Log the command execution for audit
            command.log_command_execution(args, result)
            
            return result
            
        except ValidationError as e:
            self.logger.warning(f"Command validation error for '{command_name}': {e}")
            return CommandResult(
                success=False,
                message=str(e),
                error=e
            )
        except Exception as e:
            self.logger.error(f"Command execution error for '{command_name}': {e}", exc_info=True)
            return CommandResult(
                success=False,
                message=f"Internal error executing command '{command_name}'",
                error=e
            )
            
    def clear_registry(self) -> None:
        """Clear all registered commands"""
        command_count = len(self.commands)
        self.commands.clear()
        self.logger.debug(f"Cleared {command_count} commands from registry")