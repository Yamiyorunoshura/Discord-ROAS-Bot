"""
Standalone Terminal Interactive Demo
Task ID: T11 - Terminal interactive management mode

A completely standalone demonstration of the terminal interactive mode
without any external dependencies from the project.
"""

import asyncio
import sys
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class CommandResult:
    """Result of a command execution"""
    
    def __init__(self, success: bool = True, message: str = "", data: Optional[Dict[str, Any]] = None, error: Optional[Exception] = None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.error = error
        self.timestamp = datetime.utcnow()
        
    def __str__(self) -> str:
        if self.success:
            return f"✅ {self.message}" if self.message else "✅ Command executed successfully"
        else:
            return f"❌ {self.message}" if self.message else "❌ Command failed"


class BaseCommand(ABC):
    """Base class for all commands"""
    
    def __init__(self, name: str, description: str):
        self.name = name.lower()
        self.description = description
        
    @abstractmethod
    async def execute(self, args: List[str]) -> CommandResult:
        """Execute the command"""
        pass
        
    @abstractmethod
    def get_help(self) -> str:
        """Get help text for the command"""
        pass
        
    def get_syntax(self) -> str:
        """Get command syntax"""
        return f"{self.name} [options]"


class CommandRegistry:
    """Registry for managing commands"""
    
    def __init__(self):
        self.commands: Dict[str, BaseCommand] = {}
        
    def register_command(self, command: BaseCommand) -> None:
        """Register a command"""
        if not re.match(r'^[a-z][a-z0-9_-]*$', command.name):
            raise ValueError(f"Invalid command name: {command.name}")
        self.commands[command.name] = command
        
    def find_command(self, command_name: str) -> Optional[BaseCommand]:
        """Find a command by name"""
        return self.commands.get(command_name.lower())
        
    def get_all_commands(self) -> List[BaseCommand]:
        """Get all registered commands"""
        return list(self.commands.values())
        
    def find_similar_commands(self, command_name: str, max_suggestions: int = 3) -> List[str]:
        """Find similar command names"""
        command_name = command_name.lower()
        suggestions = []
        
        for cmd_name in self.commands.keys():
            if (cmd_name.startswith(command_name[:2]) or 
                command_name.startswith(cmd_name[:2]) or
                command_name in cmd_name or
                cmd_name in command_name):
                suggestions.append(cmd_name)
                
        return suggestions[:max_suggestions]
        
    async def execute_command(self, command_name: str, args: List[str]) -> CommandResult:
        """Execute a command"""
        command = self.find_command(command_name)
        
        if not command:
            suggestions = self.find_similar_commands(command_name)
            if suggestions:
                suggestion_text = ", ".join(suggestions)
                message = f"Unknown command: {command_name}. Did you mean: {suggestion_text}?"
            else:
                message = f"Unknown command: {command_name}. Type 'help' for available commands."
            return CommandResult(False, message)
            
        try:
            return await command.execute(args)
        except Exception as e:
            return CommandResult(False, f"Error executing '{command_name}': {str(e)}", error=e)


# Built-in Commands
class HelpCommand(BaseCommand):
    """Help command"""
    
    def __init__(self, registry: CommandRegistry):
        super().__init__("help", "Show help information")
        self.registry = registry
        
    async def execute(self, args: List[str]) -> CommandResult:
        if args:
            command_name = args[0].lower()
            command = self.registry.find_command(command_name)
            
            if command:
                help_text = f"📖 Help for '{command_name}':\\n"
                help_text += f"Description: {command.description}\\n"
                help_text += f"Syntax: {command.get_syntax()}\\n\\n"
                help_text += command.get_help()
                return CommandResult(True, help_text)
            else:
                suggestions = self.registry.find_similar_commands(command_name)
                if suggestions:
                    suggestion_text = ", ".join(suggestions)
                    message = f"Command '{command_name}' not found. Did you mean: {suggestion_text}?"
                else:
                    message = f"Command '{command_name}' not found."
                return CommandResult(False, message)
        else:
            help_text = "📖 Available Commands:\\n\\n"
            commands = sorted(self.registry.get_all_commands(), key=lambda c: c.name)
            
            for cmd in commands:
                help_text += f"  {cmd.name:<12} - {cmd.description}\\n"
                
            help_text += "\\nType 'help <command>' for detailed help on a specific command."
            return CommandResult(True, help_text)
            
    def get_help(self) -> str:
        return """Display help information about commands.

Usage:
  help              - Show all available commands
  help <command>    - Show detailed help for a specific command

Examples:
  help              - List all commands
  help status       - Show help for the status command"""


class ExitCommand(BaseCommand):
    """Exit command"""
    
    def __init__(self):
        super().__init__("exit", "Exit the terminal session")
        self.should_exit = False
        
    async def execute(self, args: List[str]) -> CommandResult:
        self.should_exit = True
        return CommandResult(True, "👋 Exiting terminal session...")
        
    def get_help(self) -> str:
        return """Exit the terminal session safely.

Usage:
  exit              - Exit the terminal session

This command will gracefully exit the terminal interface."""


class StatusCommand(BaseCommand):
    """Status command"""
    
    def __init__(self):
        super().__init__("status", "Show system status")
        
    async def execute(self, args: List[str]) -> CommandResult:
        status_text = "🔍 System Status Report\\n"
        status_text += "=" * 40 + "\\n\\n"
        
        status_text += "💻 System Information:\\n"
        status_text += f"  Python Version: {sys.version.split()[0]}\\n"
        status_text += f"  Platform: {sys.platform}\\n"
        status_text += f"  Working Directory: {os.getcwd()}\\n"
        status_text += f"  Process ID: {os.getpid()}\\n\\n"
        
        status_text += "⌨️  Terminal Status:\\n"
        status_text += "  Interactive Mode: ✅ Active\\n"
        status_text += "  Command Registry: ✅ Initialized\\n"
        
        return CommandResult(True, status_text)
        
    def get_help(self) -> str:
        return """Display comprehensive system status information.

Usage:
  status            - Show complete system status

This command provides information about:
- System environment details
- Terminal session status
- Python runtime information"""


class EchoCommand(BaseCommand):
    """Echo command"""
    
    def __init__(self):
        super().__init__("echo", "Echo back the provided arguments")
        
    async def execute(self, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(True, "🔊 Echo: (no arguments provided)")
        
        echo_text = " ".join(args)
        return CommandResult(True, f"🔊 Echo: {echo_text}")
        
    def get_help(self) -> str:
        return """Echo back the provided arguments.

Usage:
  echo <message>    - Echo back the message

Examples:
  echo Hello World  - Echoes "Hello World"
  echo "Test 123"   - Echoes "Test 123"

This command is useful for testing command parsing and execution."""


class ClearCommand(BaseCommand):
    """Clear screen command"""
    
    def __init__(self):
        super().__init__("clear", "Clear the terminal screen")
        
    async def execute(self, args: List[str]) -> CommandResult:
        try:
            if os.name == 'nt':  # Windows
                os.system('cls')
            else:  # Unix/Linux/macOS
                os.system('clear')
            return CommandResult(True, "")
        except Exception as e:
            return CommandResult(False, f"Failed to clear screen: {str(e)}")
            
    def get_help(self) -> str:
        return """Clear the terminal screen.

Usage:
  clear             - Clear the terminal screen

This command clears the terminal display for a clean workspace."""


class InteractiveShell:
    """Interactive terminal shell"""
    
    def __init__(self):
        self.command_registry = CommandRegistry()
        self.running = False
        self.command_history = []
        self._setup_commands()
        
    def _setup_commands(self):
        """Setup built-in commands"""
        help_cmd = HelpCommand(self.command_registry)
        exit_cmd = ExitCommand()
        status_cmd = StatusCommand()
        echo_cmd = EchoCommand()
        clear_cmd = ClearCommand()
        
        self.command_registry.register_command(help_cmd)
        self.command_registry.register_command(exit_cmd)
        self.command_registry.register_command(status_cmd)
        self.command_registry.register_command(echo_cmd)
        self.command_registry.register_command(clear_cmd)
        
        self.exit_cmd = exit_cmd  # Keep reference for exit checking
        
    def _display_welcome(self):
        """Display welcome message"""
        print("🔧 ROAS Bot Interactive Terminal Demo")
        print("Task ID: T11 - Terminal Interactive Management Mode")
        print("-" * 60)
        print("This demonstrates the core interactive terminal functionality.")
        print("Type 'help' for available commands, 'exit' to quit.\\n")
        
    async def start(self):
        """Start the interactive shell"""
        self._display_welcome()
        self.running = True
        
        while self.running and not self.exit_cmd.should_exit:
            try:
                # Get user input
                prompt = "roas-bot> "
                user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                    
                # Add to history
                self.command_history.append(user_input)
                
                # Parse and execute command
                parts = user_input.split()
                command_name = parts[0].lower()
                args = parts[1:]
                
                result = await self.command_registry.execute_command(command_name, args)
                
                # Display result
                if result.message:
                    print(result.message)
                    
            except KeyboardInterrupt:
                print("\\n⚠️  Interrupted. Type 'exit' to quit properly.")
            except EOFError:
                print("\\n👋 Session ended")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                
        print("\\n🎉 Terminal session completed!")


async def run_tests():
    """Run basic functionality tests"""
    print("🧪 Running Terminal System Tests\\n")
    
    # Test 1: Command Registry
    print("Test 1: Command Registry")
    registry = CommandRegistry()
    echo_cmd = EchoCommand()
    registry.register_command(echo_cmd)
    
    found = registry.find_command("echo")
    assert found == echo_cmd
    print("✅ Command registration and lookup")
    
    # Test 2: Command execution
    result = await registry.execute_command("echo", ["Hello", "Test"])
    assert result.success
    assert "Hello Test" in result.message
    print("✅ Command execution")
    
    # Test 3: Unknown command handling
    result = await registry.execute_command("unknown", [])
    assert not result.success
    assert "Unknown command" in result.message
    print("✅ Unknown command handling")
    
    # Test 4: Help system
    help_cmd = HelpCommand(registry)
    registry.register_command(help_cmd)
    
    result = await help_cmd.execute([])
    assert result.success
    assert "Available Commands" in result.message
    print("✅ Help system")
    
    # Test 5: Status command
    status_cmd = StatusCommand()
    result = await status_cmd.execute([])
    assert result.success
    assert "System Status" in result.message
    print("✅ Status command")
    
    print("\\n🎉 All tests passed!")


async def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        await run_tests()
    else:
        shell = InteractiveShell()
        await shell.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)