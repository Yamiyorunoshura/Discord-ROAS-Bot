"""
Terminal Interactive Mode Entry Point
Task ID: T11 - Terminal interactive management mode

This script provides the main entry point for running the interactive terminal mode.
It sets up all necessary dependencies and starts the interactive shell.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.logging import initialize_logging
from src.cli.interactive import InteractiveShell
from src.panels.terminal_panel import TerminalPanel

# Mock service dependencies for testing
class MockService:
    """Mock service for testing purposes"""
    
    def __init__(self, name: str):
        self.name = name
        self._initialized = False
        
    async def initialize(self):
        """Mock initialization"""
        self._initialized = True
        
    def is_initialized(self) -> bool:
        """Check if initialized"""
        return self._initialized


async def main():
    """Main entry point for terminal interactive mode"""
    try:
        print("🔧 Starting ROAS Bot Terminal Interactive Mode")
        print("Task ID: T11 - Terminal Interactive Management Mode")
        print("-" * 60)
        
        # Initialize logging
        initialize_logging()
        logger = logging.getLogger("terminal_main")
        logger.info("Starting terminal interactive mode")
        
        # Create mock services for testing
        achievement_service = MockService("achievement")
        economy_service = MockService("economy")
        government_service = MockService("government")
        test_orchestrator_service = MockService("test_orchestrator")
        
        # Initialize services
        await achievement_service.initialize()
        await economy_service.initialize()
        await government_service.initialize()
        await test_orchestrator_service.initialize()
        
        # Create terminal panel
        terminal_panel = TerminalPanel(
            achievement_service=achievement_service,
            economy_service=economy_service,
            government_service=government_service,
            test_orchestrator_service=test_orchestrator_service
        )
        
        # Create and start interactive shell
        shell = InteractiveShell(terminal_panel)
        
        async with shell.session():
            await shell.start()
            
    except KeyboardInterrupt:
        print("\\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Error starting terminal: {e}")
        logging.error(f"Error in main: {e}", exc_info=True)
    finally:
        print("👋 Terminal session ended")


if __name__ == "__main__":
    asyncio.run(main())