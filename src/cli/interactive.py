"""
Interactive Terminal Shell
Task ID: T11 - Terminal interactive management mode

This module provides the main interactive shell for terminal management operations.
Integrates with the existing TerminalPanel and provides the core interactive loop.
"""

import asyncio
import os
import signal
import sys
from typing import Optional, List
import shlex
from contextlib import asynccontextmanager

from src.core.logging import get_logger, log_context
from src.core.errors import AppError, ConfigurationError
from src.panels.terminal_panel import TerminalPanel
from .commands import CommandRegistry, CommandResult


class InteractiveShell:
    """
    Main interactive shell for terminal management
    
    Provides a command-line interface for system administration and debugging.
    Integrates with the existing TerminalPanel for command execution.
    """
    
    def __init__(self, terminal_panel: TerminalPanel):
        """
        Initialize the interactive shell
        
        Args:
            terminal_panel: TerminalPanel instance for command execution
        """
        self.terminal_panel = terminal_panel
        self.command_registry = CommandRegistry()
        self.logger = get_logger("interactive_shell")
        self.running = False
        self.should_shutdown = False
        
        # Interactive mode detection
        self._is_interactive = self._detect_interactive_mode()
        
        # Signal handling for graceful shutdown
        self._setup_signal_handlers()
        
        # Built-in commands
        self._register_builtin_commands()
        
    def _detect_interactive_mode(self) -> bool:
        """
        Detect if we're running in an interactive environment
        
        Returns:
            True if interactive, False otherwise
        """
        # Check if stdin/stdout are connected to a terminal
        return (sys.stdin.isatty() and sys.stdout.isatty() and 
                not os.environ.get('NON_INTERACTIVE', False))
                
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        try:
            # Handle Ctrl+C (SIGINT)
            signal.signal(signal.SIGINT, self._handle_interrupt)
            
            # Handle termination signal (SIGTERM) 
            signal.signal(signal.SIGTERM, self._handle_termination)
            
        except ValueError:
            # Signal handling may not be available in all environments
            self.logger.warning("Signal handling not available in this environment")
            
    def _handle_interrupt(self, signum, frame):
        """Handle interrupt signal (Ctrl+C)"""
        self.logger.info("Received interrupt signal, initiating graceful shutdown")
        self.should_shutdown = True
        
    def _handle_termination(self, signum, frame):
        """Handle termination signal"""
        self.logger.info("Received termination signal, shutting down immediately")
        self.should_shutdown = True
        
    def _register_builtin_commands(self) -> None:
        """Register built-in shell commands"""
        from .builtin_commands import (
            HelpCommand, ExitCommand, QuitCommand, HistoryCommand, ClearCommand
        )
        from .system_commands import (
            StatusCommand, LogsCommand, ConfigCommand
        )
        
        # Register core commands
        self.command_registry.register_command(HelpCommand(self.command_registry))
        self.command_registry.register_command(ExitCommand(self))
        self.command_registry.register_command(QuitCommand(self))
        self.command_registry.register_command(HistoryCommand())
        self.command_registry.register_command(ClearCommand())
        
        # Register system management commands
        self.command_registry.register_command(StatusCommand(self.terminal_panel))
        self.command_registry.register_command(LogsCommand())
        self.command_registry.register_command(ConfigCommand())
        
    async def initialize(self) -> None:
        """
        Initialize the shell and its dependencies
        
        Raises:
            ConfigurationError: If initialization fails
        """
        try:
            self.logger.info("Initializing interactive shell")
            
            # Initialize terminal panel
            if not self.terminal_panel.is_initialized():
                await self.terminal_panel.initialize()
                
            # Verify interactive mode
            if not self._is_interactive:
                self.logger.warning(
                    "Non-interactive environment detected. "
                    "Shell will auto-exit unless overridden."
                )
                
            self.logger.info("Interactive shell initialized successfully")
            
        except Exception as e:
            raise ConfigurationError(
                "interactive_shell",
                f"Failed to initialize interactive shell: {str(e)}",
                cause=e
            )
            
    async def start(self) -> None:
        """
        Start the interactive shell session
        
        This is the main entry point for running the interactive terminal.
        """
        if not self.terminal_panel.is_initialized():
            raise RuntimeError("Shell not initialized. Call initialize() first.")
            
        self.running = True
        
        try:
            with log_context(component="interactive_shell", session="terminal"):
                await self._run_shell_loop()
        finally:
            await self.shutdown()
            
    async def _run_shell_loop(self) -> None:
        """Run the main interactive shell loop"""
        # Display welcome message
        self._display_welcome()
        
        # Auto-exit for non-interactive environments
        if not self._is_interactive:
            self.logger.info("Auto-exiting in non-interactive environment")
            return
            
        # Main interaction loop
        command_history = []
        
        while self.running and not self.should_shutdown:
            try:
                # Get user input
                prompt = self._get_prompt()
                user_input = await self._get_user_input(prompt)
                
                if user_input is None:  # EOF
                    break
                    
                if not user_input.strip():
                    continue
                    
                # Add to history
                command_history.append(user_input.strip())
                
                # Process command
                await self._process_command_input(user_input.strip())
                
            except KeyboardInterrupt:
                print("\\n⚠️  Interrupted by user. Type 'exit' to quit.")
                continue
            except EOFError:
                print("\\n👋 Terminal session ended")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in shell loop: {e}", exc_info=True)
                print(f"❌ Unexpected error: {str(e)}")
                
    def _display_welcome(self) -> None:
        """Display welcome message"""
        print("🔧 ROAS Bot Interactive Terminal")
        print("Task ID: T11 - Terminal Interactive Management Mode")
        print("-" * 60)
        print("Type 'help' for available commands, 'exit' to quit")
        print("")
        
    def _get_prompt(self) -> str:
        """Get the shell prompt string"""
        return "roas-bot> "
        
    async def _get_user_input(self, prompt: str) -> Optional[str]:
        """
        Get user input asynchronously
        
        Args:
            prompt: Prompt string to display
            
        Returns:
            User input string or None if EOF
        """
        try:
            # For now, use synchronous input
            # In future, could be enhanced with async readline
            return input(prompt)
        except EOFError:
            return None
            
    async def _process_command_input(self, input_line: str) -> None:
        """
        Process a command input line
        
        Args:
            input_line: Raw command input from user
        """
        try:
            # Parse command line using shell-like parsing
            parts = shlex.split(input_line)
            if not parts:
                return
                
            command_name = parts[0].lower()
            args = parts[1:]
            
            # Log command attempt for audit
            self.logger.info("Processing command", extra={
                "command": command_name,
                "args_count": len(args)
            })
            
            # Try built-in commands first
            result = await self.command_registry.execute_command(command_name, args)
            
            if result.success:
                if result.message:
                    print(result.message)
            else:
                # Try terminal panel commands as fallback
                panel_result = await self.terminal_panel.execute_command(input_line)
                if panel_result:
                    print(panel_result)
                else:
                    print(result.message)
                    
        except Exception as e:
            self.logger.error(f"Error processing command: {e}", exc_info=True)
            print(f"❌ Error processing command: {str(e)}")
            
    async def process_command(self, input_line: str) -> CommandResult:
        """
        Process a command programmatically (for testing/automation)
        
        Args:
            input_line: Command line to process
            
        Returns:
            CommandResult with execution status and output
        """
        try:
            parts = shlex.split(input_line)
            if not parts:
                return CommandResult(False, "Empty command")
                
            command_name = parts[0].lower()
            args = parts[1:]
            
            # Try built-in commands first
            result = await self.command_registry.execute_command(command_name, args)
            
            if not result.success and command_name not in ['help', 'exit', 'quit']:
                # Try terminal panel as fallback for unknown commands
                panel_output = await self.terminal_panel.execute_command(input_line)
                if panel_output:
                    return CommandResult(True, panel_output)
                    
            return result
            
        except Exception as e:
            self.logger.error(f"Error in process_command: {e}", exc_info=True)
            return CommandResult(False, f"Command processing error: {str(e)}", error=e)
            
    def stop(self) -> None:
        """Stop the shell gracefully"""
        self.logger.info("Stopping interactive shell")
        self.running = False
        
    async def shutdown(self) -> None:
        """
        Shutdown the shell and cleanup resources
        """
        self.logger.info("Shutting down interactive shell")
        
        try:
            self.running = False
            
            # Clear command registry
            self.command_registry.clear_registry()
            
            # Shutdown terminal panel
            if self.terminal_panel.is_initialized():
                await self.terminal_panel.shutdown()
                
            self.logger.info("Interactive shell shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shell shutdown: {e}", exc_info=True)
            
    @asynccontextmanager
    async def session(self):
        """
        Context manager for shell sessions
        
        Usage:
            async with shell.session():
                await shell.start()
        """
        try:
            await self.initialize()
            yield self
        finally:
            await self.shutdown()
            
    def is_running(self) -> bool:
        """Check if shell is currently running"""
        return self.running
        
    def is_interactive(self) -> bool:
        """Check if shell is in interactive mode"""
        return self._is_interactive
        
    def get_command_registry(self) -> CommandRegistry:
        """Get the command registry for external command registration"""
        return self.command_registry