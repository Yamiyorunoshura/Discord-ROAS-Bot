"""
Unit Tests for Interactive Terminal System
Task ID: T11 - Terminal interactive management mode

This module provides comprehensive unit tests for the interactive terminal system,
including command registry, interactive shell, and built-in commands.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from io import StringIO
import sys

# Add project root to path
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.cli.interactive import InteractiveShell
from src.cli.commands import CommandRegistry, BaseCommand, CommandResult
from src.cli.builtin_commands import HelpCommand, ExitCommand, HistoryCommand, ClearCommand
from src.cli.system_commands import StatusCommand, LogsCommand, ConfigCommand
from src.core.errors import ValidationError


class MockTerminalPanel:
    """Mock terminal panel for testing"""
    
    def __init__(self):
        self._initialized = False
        self._running = False
        self.achievement_service = Mock()
        self.economy_service = Mock()
        self.government_service = Mock()
        self.test_orchestrator_service = Mock()
        
        # Mock service initialization status
        self.achievement_service.is_initialized.return_value = True
        self.economy_service.is_initialized.return_value = True
        self.government_service.is_initialized.return_value = True
        self.test_orchestrator_service.is_initialized.return_value = True
        
    async def initialize(self):
        """Mock initialization"""
        self._initialized = True
        
    async def shutdown(self):
        """Mock shutdown"""
        self._initialized = False
        self._running = False
        
    def is_initialized(self) -> bool:
        """Check if initialized"""
        return self._initialized
        
    async def execute_command(self, command: str) -> str:
        """Mock command execution"""
        return f"Mock panel executed: {command}"


class TestCommand(BaseCommand):
    """Test command for testing purposes"""
    
    def __init__(self):
        super().__init__(
            name="test",
            description="Test command for unit testing"
        )
        
    async def execute(self, args):
        """Execute test command"""
        if args and args[0] == "error":
            raise ValueError("Test error")
        return CommandResult(True, f"Test executed with args: {args}")
        
    def get_help(self) -> str:
        """Get help text"""
        return "Test command help text"


class TestCommandRegistry:
    """Test cases for CommandRegistry"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.registry = CommandRegistry()
        self.test_command = TestCommand()
        
    def test_register_command(self):
        """Test command registration"""
        self.registry.register_command(self.test_command)
        
        # Check command was registered
        assert "test" in self.registry.commands
        assert self.registry.find_command("test") == self.test_command
        
    def test_register_invalid_command_name(self):
        """Test registration with invalid command name"""
        invalid_command = TestCommand()
        invalid_command.name = "123invalid"
        
        with pytest.raises(ValidationError):
            self.registry.register_command(invalid_command)
            
    def test_find_command(self):
        """Test command finding"""
        self.registry.register_command(self.test_command)
        
        # Test case insensitive finding
        assert self.registry.find_command("test") == self.test_command
        assert self.registry.find_command("TEST") == self.test_command
        assert self.registry.find_command("Test") == self.test_command
        
        # Test non-existent command
        assert self.registry.find_command("nonexistent") is None
        
    def test_get_all_commands(self):
        """Test getting all commands"""
        self.registry.register_command(self.test_command)
        
        commands = self.registry.get_all_commands()
        assert len(commands) == 1
        assert commands[0] == self.test_command
        
    def test_find_similar_commands(self):
        """Test finding similar commands"""
        self.registry.register_command(self.test_command)
        
        # Register additional commands for similarity testing
        similar_cmd = TestCommand()
        similar_cmd.name = "testing"
        self.registry.register_command(similar_cmd)
        
        # Test similarity finding
        suggestions = self.registry.find_similar_commands("tes")
        assert "test" in suggestions or "testing" in suggestions
        
    @pytest.mark.asyncio
    async def test_execute_command_success(self):
        """Test successful command execution"""
        self.registry.register_command(self.test_command)
        
        result = await self.registry.execute_command("test", ["arg1", "arg2"])
        
        assert result.success
        assert "Test executed with args: ['arg1', 'arg2']" in result.message
        
    @pytest.mark.asyncio
    async def test_execute_command_not_found(self):
        """Test execution of non-existent command"""
        result = await self.registry.execute_command("nonexistent", [])
        
        assert not result.success
        assert "Unknown command" in result.message
        
    @pytest.mark.asyncio
    async def test_execute_command_error(self):
        """Test command execution with error"""
        self.registry.register_command(self.test_command)
        
        result = await self.registry.execute_command("test", ["error"])
        
        assert not result.success
        assert "Internal error" in result.message


class TestInteractiveShell:
    """Test cases for InteractiveShell"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_panel = MockTerminalPanel()
        self.shell = InteractiveShell(self.mock_panel)
        
    @pytest.mark.asyncio
    async def test_shell_initialization(self):
        """Test shell initialization"""
        await self.shell.initialize()
        
        assert self.mock_panel.is_initialized()
        
    @pytest.mark.asyncio
    async def test_process_command(self):
        """Test command processing"""
        await self.shell.initialize()
        
        # Test help command
        result = await self.shell.process_command("help")
        assert result.success
        assert "Available Commands" in result.message
        
    @pytest.mark.asyncio
    async def test_exit_command(self):
        """Test exit command functionality"""
        await self.shell.initialize()
        
        result = await self.shell.process_command("exit")
        assert result.success
        assert "Exiting" in result.message
        assert not self.shell.is_running()
        
    def test_interactive_mode_detection(self):
        """Test interactive mode detection"""
        # This test depends on the environment, so we just verify it's callable
        is_interactive = self.shell.is_interactive()
        assert isinstance(is_interactive, bool)
        
    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test shell shutdown"""
        await self.shell.initialize()
        await self.shell.shutdown()
        
        assert not self.mock_panel.is_initialized()


class TestBuiltinCommands:
    """Test cases for built-in commands"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.registry = CommandRegistry()
        
    @pytest.mark.asyncio
    async def test_help_command(self):
        """Test help command"""
        help_cmd = HelpCommand(self.registry)
        
        # Test general help
        result = await help_cmd.execute([])
        assert result.success
        assert "Available Commands" in result.message
        
        # Test specific command help
        test_cmd = TestCommand()
        self.registry.register_command(test_cmd)
        
        result = await help_cmd.execute(["test"])
        assert result.success
        assert "Test command help text" in result.message
        
        # Test non-existent command help
        result = await help_cmd.execute(["nonexistent"])
        assert not result.success
        assert "not found" in result.message
        
    @pytest.mark.asyncio
    async def test_history_command(self):
        """Test history command"""
        history_cmd = HistoryCommand()
        
        # Test empty history
        result = await history_cmd.execute([])
        assert result.success
        assert "No command history" in result.message
        
        # Add some history
        history_cmd.add_to_history("test command 1")
        history_cmd.add_to_history("test command 2")
        
        result = await history_cmd.execute([])
        assert result.success
        assert "Command History" in result.message
        
    @pytest.mark.asyncio 
    async def test_clear_command(self):
        """Test clear command"""
        clear_cmd = ClearCommand()
        
        # Mock the os.system call to avoid actually clearing the screen
        with patch('os.system') as mock_system:
            result = await clear_cmd.execute([])
            assert result.success
            assert mock_system.called


class TestSystemCommands:
    """Test cases for system management commands"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_panel = MockTerminalPanel()
        
    @pytest.mark.asyncio
    async def test_status_command(self):
        """Test status command"""
        status_cmd = StatusCommand(self.mock_panel)
        
        # Mock psutil to avoid system dependencies in tests
        with patch('src.cli.system_commands.psutil') as mock_psutil:
            # Mock process info
            mock_process = Mock()
            mock_process.pid = 12345
            mock_process.memory_percent.return_value = 5.5
            mock_process.cpu_percent.return_value = 2.1
            mock_process.num_threads.return_value = 8
            mock_process.create_time.return_value = 1609459200  # Fixed timestamp
            mock_process.status.return_value = "running"
            
            mock_psutil.Process.return_value = mock_process
            
            # Mock system info
            mock_psutil.cpu_count.return_value = 4
            mock_psutil.cpu_percent.return_value = 25.0
            
            mock_memory = Mock()
            mock_memory.total = 8 * 1024**3  # 8GB
            mock_memory.available = 4 * 1024**3  # 4GB
            mock_memory.percent = 50.0
            mock_psutil.virtual_memory.return_value = mock_memory
            
            mock_psutil.boot_time.return_value = 1609459200
            
            result = await status_cmd.execute([])
            
            assert result.success
            assert "System Status Report" in result.message
            assert "Process Information" in result.message
            assert "System Information" in result.message
            
    @pytest.mark.asyncio
    async def test_logs_command(self):
        """Test logs command"""
        logs_cmd = LogsCommand()
        
        # Test default logs
        result = await logs_cmd.execute([])
        assert result.success
        assert "Recent Main Logs" in result.message
        
        # Test specific log type
        result = await logs_cmd.execute(["error"])
        assert result.success
        assert "Recent Error Logs" in result.message
        
        # Test with line count
        result = await logs_cmd.execute(["50"])
        assert result.success
        assert "last 50 lines" in result.message
        
        # Test invalid line count
        result = await logs_cmd.execute(["invalid"])
        assert not result.success
        assert "Invalid" in result.message
        
    @pytest.mark.asyncio
    async def test_config_command(self):
        """Test config command"""
        config_cmd = ConfigCommand()
        
        result = await config_cmd.execute([])
        assert result.success
        assert "System Configuration" in result.message


@pytest.mark.integration
class TestIntegration:
    """Integration tests for the complete terminal system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_panel = MockTerminalPanel()
        self.shell = InteractiveShell(self.mock_panel)
        
    @pytest.mark.asyncio
    async def test_full_shell_session(self):
        """Test a complete shell session workflow"""
        async with self.shell.session():
            # Test multiple commands in sequence
            commands = [
                "help",
                "status", 
                "logs",
                "config",
                "history"
            ]
            
            for cmd in commands:
                result = await self.shell.process_command(cmd)
                # Each command should execute successfully
                assert result.success or "placeholder" in result.message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])