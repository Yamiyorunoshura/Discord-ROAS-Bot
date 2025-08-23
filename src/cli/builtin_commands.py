"""
Built-in Terminal Commands
Task ID: T11 - Terminal interactive management mode

This module provides the built-in commands for the interactive terminal shell.
These are core commands that are always available in the terminal interface.
"""

import os
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

from .commands import BaseCommand, CommandResult
from src.core.logging import get_logger

if TYPE_CHECKING:
    from .interactive import InteractiveShell


class HelpCommand(BaseCommand):
    """
    Display help information about available commands
    """
    
    def __init__(self, command_registry):
        super().__init__(
            name="help",
            description="Display help information about available commands"
        )
        self.command_registry = command_registry
        
    async def execute(self, args: List[str]) -> CommandResult:
        """Execute the help command"""
        try:
            if args:
                # Show help for specific command
                command_name = args[0].lower()
                command = self.command_registry.find_command(command_name)
                
                if command:
                    help_text = f"📖 Help for '{command_name}':\\n"
                    help_text += f"Description: {command.description}\\n"
                    help_text += f"Syntax: {command.get_syntax()}\\n\\n"
                    help_text += command.get_help()
                    return CommandResult(True, help_text)
                else:
                    # Try to find similar commands
                    suggestions = self.command_registry.find_similar_commands(command_name)
                    if suggestions:
                        suggestion_text = ", ".join(suggestions)
                        message = f"Command '{command_name}' not found. Did you mean: {suggestion_text}?"
                    else:
                        message = f"Command '{command_name}' not found."
                    return CommandResult(False, message)
            else:
                # Show general help
                help_text = "📖 Available Commands:\\n\\n"
                
                # Get all commands and sort them
                commands = sorted(self.command_registry.get_all_commands(), key=lambda c: c.name)
                
                # Built-in commands first
                builtin_commands = [cmd for cmd in commands if cmd.name in ['help', 'exit', 'quit', 'history', 'clear']]
                other_commands = [cmd for cmd in commands if cmd.name not in ['help', 'exit', 'quit', 'history', 'clear']]
                
                if builtin_commands:
                    help_text += "Built-in Commands:\\n"
                    for cmd in builtin_commands:
                        help_text += f"  {cmd.name:<12} - {cmd.description}\\n"
                    help_text += "\\n"
                    
                if other_commands:
                    help_text += "System Commands:\\n"
                    for cmd in other_commands:
                        help_text += f"  {cmd.name:<12} - {cmd.description}\\n"
                    help_text += "\\n"
                        
                help_text += "Type 'help <command>' for detailed information about a specific command.\\n"
                help_text += "Type 'exit' or 'quit' to leave the terminal.\\n"
                
                return CommandResult(True, help_text.strip())
                
        except Exception as e:
            self.logger.error(f"Error in help command: {e}", exc_info=True)
            return CommandResult(False, f"Error displaying help: {str(e)}", error=e)
            
    def get_help(self) -> str:
        """Get detailed help for the help command"""
        return """Display help information about available commands.

Usage:
  help              - Show all available commands
  help <command>    - Show detailed help for a specific command

Examples:
  help              - List all commands
  help status       - Show help for the status command
  help exit         - Show help for the exit command
  
This command provides information about all available terminal commands,
including their syntax, description, and usage examples."""
        
    def get_syntax(self) -> str:
        """Get command syntax"""
        return "help [command_name]"


class ExitCommand(BaseCommand):
    """
    Exit the interactive terminal session
    """
    
    def __init__(self, shell: 'InteractiveShell'):
        super().__init__(
            name="exit",
            description="Exit the interactive terminal session"
        )
        self.shell = shell
        
    async def execute(self, args: List[str]) -> CommandResult:
        """Execute the exit command"""
        try:
            self.logger.info("Exit command executed, shutting down shell")
            
            # Signal the shell to stop
            self.shell.stop()
            
            return CommandResult(True, "👋 Exiting terminal session...")
            
        except Exception as e:
            self.logger.error(f"Error in exit command: {e}", exc_info=True)
            return CommandResult(False, f"Error during exit: {str(e)}", error=e)
            
    def get_help(self) -> str:
        """Get detailed help for the exit command"""
        return """Exit the interactive terminal session safely.

Usage:
  exit              - Exit the terminal session
  quit              - Alias for exit

This command will:
1. Stop the interactive shell loop
2. Clean up resources and connections
3. Shutdown the terminal panel
4. Return to the parent process

The exit is graceful and will not affect the main Discord bot operation."""
        
    def get_syntax(self) -> str:
        """Get command syntax"""
        return "exit"


class QuitCommand(ExitCommand):
    """
    Alias for the exit command
    """
    
    def __init__(self, shell: 'InteractiveShell'):
        super().__init__(shell)
        self.name = "quit"
        self.description = "Exit the interactive terminal session (alias for exit)"


class HistoryCommand(BaseCommand):
    """
    Display command history (placeholder for future implementation)
    """
    
    def __init__(self):
        super().__init__(
            name="history",
            description="Display command history"
        )
        self._command_history: List[str] = []
        
    async def execute(self, args: List[str]) -> CommandResult:
        """Execute the history command"""
        try:
            if not self._command_history:
                return CommandResult(True, "📜 No command history available yet.")
                
            # For now, just show a placeholder
            # In future versions, this could integrate with readline history
            history_text = "📜 Command History (last 10 commands):\\n"
            
            # Show last 10 commands
            recent_commands = self._command_history[-10:]
            for i, cmd in enumerate(recent_commands, 1):
                history_text += f"  {i:2d}. {cmd}\\n"
                
            return CommandResult(True, history_text.strip())
            
        except Exception as e:
            self.logger.error(f"Error in history command: {e}", exc_info=True)
            return CommandResult(False, f"Error displaying history: {str(e)}", error=e)
            
    def add_to_history(self, command: str) -> None:
        """
        Add a command to the history
        
        Args:
            command: Command to add to history
        """
        if command.strip() and command.strip() != "history":
            self._command_history.append(command.strip())
            
            # Keep only last 100 commands
            if len(self._command_history) > 100:
                self._command_history = self._command_history[-100:]
                
    def get_help(self) -> str:
        """Get detailed help for the history command"""
        return """Display recently executed commands.

Usage:
  history           - Show recent command history

This command shows the last 10 commands that were executed in this session.
The history is not persistent across sessions.

Note: This is a basic implementation. Future versions may include:
- Persistent history across sessions
- History search functionality
- Command re-execution from history"""
        
    def get_syntax(self) -> str:
        """Get command syntax"""
        return "history"


class ClearCommand(BaseCommand):
    """
    Clear the terminal screen
    """
    
    def __init__(self):
        super().__init__(
            name="clear",
            description="Clear the terminal screen"
        )
        
    async def execute(self, args: List[str]) -> CommandResult:
        """Execute the clear command"""
        try:
            # Clear screen using ANSI escape codes
            if os.name == 'nt':  # Windows
                os.system('cls')
            else:  # Unix/Linux/macOS
                os.system('clear')
                
            return CommandResult(True, "")  # No message needed after clearing
            
        except Exception as e:
            self.logger.error(f"Error in clear command: {e}", exc_info=True)
            return CommandResult(False, f"Error clearing screen: {str(e)}", error=e)
            
    def get_help(self) -> str:
        """Get detailed help for the clear command"""
        return """Clear the terminal screen.

Usage:
  clear             - Clear the terminal screen

This command clears the terminal display, providing a clean workspace.
It uses the system's native clear functionality:
- Windows: Uses 'cls' command
- Unix/Linux/macOS: Uses 'clear' command

The command history and session state are preserved."""
        
    def get_syntax(self) -> str:
        """Get command syntax"""
        return "clear"