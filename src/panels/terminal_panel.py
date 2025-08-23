"""
Terminal Panel for the new architecture
Task ID: T2 - App architecture baseline and scaffolding

This module provides terminal-based interaction capabilities.
It will support the interactive terminal mode for administration and debugging.
"""

from typing import Optional, Dict, Any, List, Callable
import asyncio
import sys
import shlex
from io import StringIO

from src.services.achievement_service import AchievementService
from src.services.economy_service import EconomyService
from src.services.government_service import GovernmentService
from src.services.test_orchestrator_service import TestOrchestratorService


class TerminalPanel:
    """
    Terminal panel for interactive command-line operations
    
    Provides functionality for:
    - Interactive terminal sessions
    - Administrative commands
    - System debugging and inspection
    - Service coordination
    """
    
    def __init__(self, 
                 achievement_service: AchievementService,
                 economy_service: EconomyService,
                 government_service: GovernmentService,
                 test_orchestrator_service: TestOrchestratorService):
        """
        Initialize the terminal panel
        
        Args:
            achievement_service: Achievement service instance
            economy_service: Economy service instance
            government_service: Government service instance
            test_orchestrator_service: Test orchestrator service instance
        """
        self.panel_name = "TerminalPanel"
        self.achievement_service = achievement_service
        self.economy_service = economy_service
        self.government_service = government_service
        self.test_orchestrator_service = test_orchestrator_service
        
        self._initialized = False
        self._running = False
        self._commands: Dict[str, Callable] = {}
        self._setup_commands()
        
    def _setup_commands(self) -> None:
        """Setup available terminal commands"""
        self._commands = {
            'help': self._cmd_help,
            'status': self._cmd_status,
            'services': self._cmd_services,
            'achievement': self._cmd_achievement,
            'economy': self._cmd_economy,
            'government': self._cmd_government,
            'test': self._cmd_test,
            'exit': self._cmd_exit,
            'quit': self._cmd_exit,
        }
        
    async def initialize(self) -> None:
        """Initialize the panel and its dependencies"""
        if self._initialized:
            return
            
        # Ensure all services are initialized
        services = [
            self.achievement_service,
            self.economy_service, 
            self.government_service,
            self.test_orchestrator_service
        ]
        
        for service in services:
            if not service.is_initialized():
                await service.initialize()
                
        self._initialized = True
        
    async def shutdown(self) -> None:
        """Cleanup panel resources"""
        self._running = False
        self._initialized = False
        
    async def run(self) -> None:
        """
        Run the interactive terminal session
        """
        if not self._initialized:
            raise RuntimeError("Panel not initialized")
            
        self._running = True
        print("🔧 ROAS Bot Terminal Interface")
        print("Type 'help' for available commands, 'exit' to quit")
        print("-" * 50)
        
        try:
            while self._running:
                try:
                    # Get user input
                    prompt = "roas-bot> "
                    user_input = input(prompt).strip()
                    
                    if not user_input:
                        continue
                        
                    # Execute command
                    result = await self.execute_command(user_input)
                    if result:
                        print(result)
                        
                except KeyboardInterrupt:
                    print("\\n⚠️ Interrupted by user")
                    break
                except EOFError:
                    print("\\n👋 Terminal session ended")
                    break
                except Exception as e:
                    print(f"❌ Error: {str(e)}")
                    
        finally:
            self._running = False
            
    async def execute_command(self, command_line: str) -> Optional[str]:
        """
        Execute a terminal command
        
        Args:
            command_line: Command line to execute
            
        Returns:
            Command output or None
        """
        if not self._initialized:
            raise RuntimeError("Panel not initialized")
            
        try:
            # Parse command line
            parts = shlex.split(command_line)
            if not parts:
                return None
                
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # Execute command
            if command in self._commands:
                return await self._commands[command](args)
            else:
                return f"❌ Unknown command: {command}. Type 'help' for available commands."
                
        except Exception as e:
            return f"❌ Command error: {str(e)}"
            
    async def _cmd_help(self, args: List[str]) -> str:
        """Display help information"""
        help_text = StringIO()
        help_text.write("📖 Available Commands:\\n")
        help_text.write("  help              - Show this help message\\n")
        help_text.write("  status            - Show system status\\n")
        help_text.write("  services          - Show service status\\n")
        help_text.write("  achievement       - Achievement system commands\\n")
        help_text.write("  economy          - Economy system commands\\n")
        help_text.write("  government       - Government system commands\\n")
        help_text.write("  test             - Test orchestration commands\\n")
        help_text.write("  exit/quit        - Exit terminal\\n")
        return help_text.getvalue()
        
    async def _cmd_status(self, args: List[str]) -> str:
        """Show system status"""
        status = StringIO()
        status.write("🔍 System Status:\\n")
        status.write(f"  Panel initialized: {self._initialized}\\n")
        status.write(f"  Panel running: {self._running}\\n")
        status.write(f"  Achievement service: {'✅' if self.achievement_service.is_initialized() else '❌'}\\n")
        status.write(f"  Economy service: {'✅' if self.economy_service.is_initialized() else '❌'}\\n")
        status.write(f"  Government service: {'✅' if self.government_service.is_initialized() else '❌'}\\n")
        status.write(f"  Test orchestrator: {'✅' if self.test_orchestrator_service.is_initialized() else '❌'}\\n")
        return status.getvalue()
        
    async def _cmd_services(self, args: List[str]) -> str:
        """Show detailed service information"""
        return await self._cmd_status(args)  # For now, same as status
        
    async def _cmd_achievement(self, args: List[str]) -> str:
        """Handle achievement system commands"""
        if not args:
            return "📖 Achievement commands: list, grant, progress"
        return "🏆 Achievement command executed (placeholder)"
        
    async def _cmd_economy(self, args: List[str]) -> str:
        """Handle economy system commands"""
        if not args:
            return "📖 Economy commands: balance, adjust, transfer"
        return "💰 Economy command executed (placeholder)"
        
    async def _cmd_government(self, args: List[str]) -> str:
        """Handle government system commands"""
        if not args:
            return "📖 Government commands: roles, assign, remove"
        return "🏛️ Government command executed (placeholder)"
        
    async def _cmd_test(self, args: List[str]) -> str:
        """Handle test orchestration commands"""
        if not args:
            return "📖 Test commands: dpytest, random, setup, cleanup"
        return "🧪 Test command executed (placeholder)"
        
    async def _cmd_exit(self, args: List[str]) -> str:
        """Exit the terminal session"""
        self._running = False
        return "👋 Exiting terminal session..."
        
    def is_initialized(self) -> bool:
        """Check if panel is initialized"""
        return self._initialized