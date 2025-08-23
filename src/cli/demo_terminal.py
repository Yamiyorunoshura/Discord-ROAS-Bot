"""
Simple Terminal Demo
Task ID: T11 - Terminal interactive management mode

A simplified demonstration of the terminal interactive mode without full system dependencies.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Create a simple mock logging system to avoid configuration dependencies
class SimpleLogger:
    """Simple logger for demo purposes"""
    
    def __init__(self, name):
        self.name = name
        
    def info(self, msg, **kwargs):
        print(f"[INFO] {self.name}: {msg}")
        
    def debug(self, msg, **kwargs):
        print(f"[DEBUG] {self.name}: {msg}")
        
    def warning(self, msg, **kwargs):
        print(f"[WARN] {self.name}: {msg}")
        
    def error(self, msg, **kwargs):
        print(f"[ERROR] {self.name}: {msg}")


# Mock the logging module
sys.modules['src.core.logging'] = type('MockModule', (), {
    'get_logger': lambda name: SimpleLogger(name),
    'log_context': lambda **kwargs: type('MockContext', (), {'__enter__': lambda x: x, '__exit__': lambda x,a,b,c: None})()
})()

# Now import our CLI modules
from src.cli.commands import BaseCommand, CommandResult, CommandRegistry


class DemoHelpCommand(BaseCommand):
    """Demo help command"""
    
    def __init__(self, registry):
        super().__init__("help", "Show available commands")
        self.registry = registry
        
    async def execute(self, args):
        """Execute help command"""
        help_text = "📖 Available Commands:\\n\\n"
        
        commands = sorted(self.registry.get_all_commands(), key=lambda c: c.name)
        for cmd in commands:
            help_text += f"  {cmd.name:<12} - {cmd.description}\\n"
            
        help_text += "\\nType a command name to execute it, or 'exit' to quit."
        return CommandResult(True, help_text)
        
    def get_help(self):
        return "Display available commands and their descriptions."


class DemoExitCommand(BaseCommand):
    """Demo exit command"""
    
    def __init__(self):
        super().__init__("exit", "Exit the terminal")
        self.should_exit = False
        
    async def execute(self, args):
        """Execute exit command"""
        self.should_exit = True
        return CommandResult(True, "👋 Goodbye!")
        
    def get_help(self):
        return "Exit the terminal session gracefully."


class DemoStatusCommand(BaseCommand):
    """Demo status command"""
    
    def __init__(self):
        super().__init__("status", "Show system status")
        
    async def execute(self, args):
        """Execute status command"""
        status = "🔍 System Status:\\n"
        status += f"  Python Version: {sys.version.split()[0]}\\n"
        status += f"  Platform: {sys.platform}\\n"
        status += f"  Working Directory: {os.getcwd()}\\n"
        status += f"  Terminal Session: Active ✅\\n"
        return CommandResult(True, status)
        
    def get_help(self):
        return "Display current system status information."


class DemoEchoCommand(BaseCommand):
    """Demo echo command"""
    
    def __init__(self):
        super().__init__("echo", "Echo back the arguments")
        
    async def execute(self, args):
        """Execute echo command"""
        if not args:
            return CommandResult(True, "🔊 Echo: (no arguments)")
        return CommandResult(True, f"🔊 Echo: {' '.join(args)}")
        
    def get_help(self):
        return "Echo back the provided arguments.\\n\\nUsage: echo <message>"


async def run_demo_terminal():
    """Run the demo terminal session"""
    print("🔧 ROAS Bot Terminal Demo")
    print("Task ID: T11 - Terminal Interactive Management Mode")
    print("=" * 60)
    print("This is a simplified demonstration of the terminal system.")
    print("Type 'help' for available commands, 'exit' to quit.\\n")
    
    # Create command registry and register demo commands
    registry = CommandRegistry()
    
    help_cmd = DemoHelpCommand(registry)
    exit_cmd = DemoExitCommand()
    status_cmd = DemoStatusCommand()
    echo_cmd = DemoEchoCommand()
    
    registry.register_command(help_cmd)
    registry.register_command(exit_cmd)
    registry.register_command(status_cmd)
    registry.register_command(echo_cmd)
    
    # Main interaction loop
    while True:
        try:
            # Get user input
            prompt = "roas-demo> "
            user_input = input(prompt).strip()
            
            if not user_input:
                continue
                
            # Parse command
            parts = user_input.split()
            command_name = parts[0].lower()
            args = parts[1:]
            
            # Execute command
            result = await registry.execute_command(command_name, args)
            
            # Display result
            if result.message:
                print(result.message)
                
            # Check for exit
            if hasattr(exit_cmd, 'should_exit') and exit_cmd.should_exit:
                break
                
        except KeyboardInterrupt:
            print("\\n⚠️  Interrupted by user. Type 'exit' to quit properly.")
        except EOFError:
            print("\\n👋 Session ended")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            
    print("\\n🎉 Demo completed!")


async def test_command_registry():
    """Test the command registry functionality"""
    print("🧪 Testing Command Registry...")
    
    registry = CommandRegistry()
    echo_cmd = DemoEchoCommand()
    registry.register_command(echo_cmd)
    
    # Test command registration
    found_cmd = registry.find_command("echo")
    assert found_cmd == echo_cmd
    print("✅ Command registration test passed")
    
    # Test command execution
    result = await registry.execute_command("echo", ["Hello", "World"])
    assert result.success
    assert "Hello World" in result.message
    print("✅ Command execution test passed")
    
    # Test unknown command
    result = await registry.execute_command("unknown", [])
    assert not result.success
    assert "Unknown command" in result.message
    print("✅ Unknown command handling test passed")
    
    print("🎉 All registry tests passed!")


async def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        await test_command_registry()
    else:
        await run_demo_terminal()


if __name__ == "__main__":
    asyncio.run(main())