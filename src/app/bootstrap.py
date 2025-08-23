"""
Application Bootstrap for the new architecture
Task ID: T2 - App architecture baseline and scaffolding

This module provides the application startup and dependency injection functionality.
It coordinates the initialization of all services and panels in the correct order.
"""

from typing import Optional, Dict, Any
import asyncio
import logging

from src.services.achievement_service import AchievementService
from src.services.activity_meter_service import ActivityMeterService
from src.services.economy_service import EconomyService
from src.services.government_service import GovernmentService
from src.services.test_orchestrator_service import TestOrchestratorService

from src.panels.achievement_panel import AchievementPanel
from src.panels.terminal_panel import TerminalPanel


class ApplicationBootstrap:
    """
    Application bootstrap for coordinating startup and dependency injection
    
    Provides functionality for:
    - Service initialization in correct dependency order
    - Panel initialization with service dependencies
    - Graceful shutdown and cleanup
    - Configuration management
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the application bootstrap
        
        Args:
            config: Optional application configuration
        """
        self.config = config or {}
        self._logger = logging.getLogger(__name__)
        
        # Service instances
        self.achievement_service: Optional[AchievementService] = None
        self.activity_meter_service: Optional[ActivityMeterService] = None
        self.economy_service: Optional[EconomyService] = None
        self.government_service: Optional[GovernmentService] = None
        self.test_orchestrator_service: Optional[TestOrchestratorService] = None
        
        # Panel instances
        self.achievement_panel: Optional[AchievementPanel] = None
        self.terminal_panel: Optional[TerminalPanel] = None
        
        self._initialized = False
        self._services_initialized = False
        self._panels_initialized = False
        
    async def initialize(self) -> None:
        """
        Initialize the entire application stack
        """
        if self._initialized:
            return
            
        self._logger.info("🚀 Starting application initialization...")
        
        try:
            # Initialize services first (they have no dependencies on panels)
            await self._initialize_services()
            
            # Initialize panels (they depend on services)
            await self._initialize_panels()
            
            self._initialized = True
            self._logger.info("✅ Application initialization completed successfully")
            
        except Exception as e:
            self._logger.error(f"❌ Application initialization failed: {str(e)}")
            await self.shutdown()
            raise
            
    async def _initialize_services(self) -> None:
        """Initialize all services in dependency order"""
        self._logger.info("🔧 Initializing services...")
        
        # Initialize services (order matters for dependencies)
        services = [
            ("Achievement Service", lambda: AchievementService()),
            ("Activity Meter Service", lambda: ActivityMeterService()),
            ("Economy Service", lambda: EconomyService()),
            ("Government Service", lambda: GovernmentService()),
            ("Test Orchestrator Service", lambda: TestOrchestratorService()),
        ]
        
        for service_name, service_factory in services:
            try:
                self._logger.info(f"  Initializing {service_name}...")
                service = service_factory()
                await service.initialize()
                
                # Store service reference
                if service_name == "Achievement Service":
                    self.achievement_service = service
                elif service_name == "Activity Meter Service":
                    self.activity_meter_service = service
                elif service_name == "Economy Service":
                    self.economy_service = service
                elif service_name == "Government Service":
                    self.government_service = service
                elif service_name == "Test Orchestrator Service":
                    self.test_orchestrator_service = service
                    
                self._logger.info(f"  ✅ {service_name} initialized successfully")
                
            except Exception as e:
                self._logger.error(f"  ❌ Failed to initialize {service_name}: {str(e)}")
                raise
                
        self._services_initialized = True
        self._logger.info("✅ All services initialized successfully")
        
    async def _initialize_panels(self) -> None:
        """Initialize all panels with service dependencies"""
        self._logger.info("🎨 Initializing panels...")
        
        try:
            # Achievement Panel
            self._logger.info("  Initializing Achievement Panel...")
            self.achievement_panel = AchievementPanel(self.achievement_service)
            await self.achievement_panel.initialize()
            self._logger.info("  ✅ Achievement Panel initialized successfully")
            
            # Terminal Panel
            self._logger.info("  Initializing Terminal Panel...")
            self.terminal_panel = TerminalPanel(
                self.achievement_service,
                self.economy_service,
                self.government_service,
                self.test_orchestrator_service
            )
            await self.terminal_panel.initialize()
            self._logger.info("  ✅ Terminal Panel initialized successfully")
            
            self._panels_initialized = True
            self._logger.info("✅ All panels initialized successfully")
            
        except Exception as e:
            self._logger.error(f"❌ Failed to initialize panels: {str(e)}")
            raise
            
    async def shutdown(self) -> None:
        """
        Gracefully shutdown the entire application stack
        """
        self._logger.info("🔄 Starting application shutdown...")
        
        try:
            # Shutdown panels first
            if self._panels_initialized:
                await self._shutdown_panels()
                
            # Shutdown services last
            if self._services_initialized:
                await self._shutdown_services()
                
            self._initialized = False
            self._logger.info("✅ Application shutdown completed successfully")
            
        except Exception as e:
            self._logger.error(f"❌ Error during application shutdown: {str(e)}")
            raise
            
    async def _shutdown_panels(self) -> None:
        """Shutdown all panels"""
        self._logger.info("🎨 Shutting down panels...")
        
        panels = [
            ("Terminal Panel", self.terminal_panel),
            ("Achievement Panel", self.achievement_panel),
        ]
        
        for panel_name, panel in panels:
            if panel:
                try:
                    self._logger.info(f"  Shutting down {panel_name}...")
                    await panel.shutdown()
                    self._logger.info(f"  ✅ {panel_name} shutdown successfully")
                except Exception as e:
                    self._logger.error(f"  ❌ Error shutting down {panel_name}: {str(e)}")
                    
        self._panels_initialized = False
        
    async def _shutdown_services(self) -> None:
        """Shutdown all services"""
        self._logger.info("🔧 Shutting down services...")
        
        services = [
            ("Test Orchestrator Service", self.test_orchestrator_service),
            ("Government Service", self.government_service),
            ("Economy Service", self.economy_service),
            ("Activity Meter Service", self.activity_meter_service),
            ("Achievement Service", self.achievement_service),
        ]
        
        for service_name, service in services:
            if service:
                try:
                    self._logger.info(f"  Shutting down {service_name}...")
                    await service.shutdown()
                    self._logger.info(f"  ✅ {service_name} shutdown successfully")
                except Exception as e:
                    self._logger.error(f"  ❌ Error shutting down {service_name}: {str(e)}")
                    
        self._services_initialized = False
        
    async def run_terminal_mode(self) -> None:
        """
        Run the application in terminal interactive mode
        """
        if not self._initialized:
            raise RuntimeError("Application not initialized")
            
        if not self.terminal_panel:
            raise RuntimeError("Terminal panel not available")
            
        self._logger.info("🔧 Starting terminal interactive mode...")
        
        try:
            await self.terminal_panel.run()
        except KeyboardInterrupt:
            self._logger.info("⚠️ Terminal mode interrupted by user")
        finally:
            self._logger.info("🔄 Terminal mode ended")
            
    def get_service(self, service_name: str) -> Optional[Any]:
        """
        Get a service instance by name
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service instance or None
        """
        service_map = {
            'achievement': self.achievement_service,
            'activity_meter': self.activity_meter_service,
            'economy': self.economy_service,
            'government': self.government_service,
            'test_orchestrator': self.test_orchestrator_service,
        }
        
        return service_map.get(service_name.lower())
        
    def get_panel(self, panel_name: str) -> Optional[Any]:
        """
        Get a panel instance by name
        
        Args:
            panel_name: Name of the panel
            
        Returns:
            Panel instance or None
        """
        panel_map = {
            'achievement': self.achievement_panel,
            'terminal': self.terminal_panel,
        }
        
        return panel_map.get(panel_name.lower())
        
    def is_initialized(self) -> bool:
        """Check if application is fully initialized"""
        return self._initialized
        
    def get_status(self) -> Dict[str, Any]:
        """
        Get application status information
        
        Returns:
            Status information dictionary
        """
        return {
            "initialized": self._initialized,
            "services_initialized": self._services_initialized,
            "panels_initialized": self._panels_initialized,
            "services": {
                "achievement": self.achievement_service.is_initialized() if self.achievement_service else False,
                "activity_meter": self.activity_meter_service.is_initialized() if self.activity_meter_service else False,
                "economy": self.economy_service.is_initialized() if self.economy_service else False,
                "government": self.government_service.is_initialized() if self.government_service else False,
                "test_orchestrator": self.test_orchestrator_service.is_initialized() if self.test_orchestrator_service else False,
            },
            "panels": {
                "achievement": self.achievement_panel.is_initialized() if self.achievement_panel else False,
                "terminal": self.terminal_panel.is_initialized() if self.terminal_panel else False,
            }
        }