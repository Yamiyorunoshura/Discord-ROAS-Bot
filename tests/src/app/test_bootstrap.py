"""
Unit tests for src.app.bootstrap module
Task ID: T2 - App architecture baseline and scaffolding
"""

import pytest
import logging
from unittest.mock import Mock, AsyncMock, patch

from src.app.bootstrap import ApplicationBootstrap


class TestApplicationBootstrap:
    """Test the ApplicationBootstrap class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.bootstrap = ApplicationBootstrap()
        
    def test_initialization(self):
        """Test bootstrap initialization"""
        assert self.bootstrap.config == {}
        assert self.bootstrap._initialized is False
        assert self.bootstrap._services_initialized is False
        assert self.bootstrap._panels_initialized is False
        
    def test_initialization_with_config(self):
        """Test bootstrap initialization with config"""
        config = {"debug": True}
        bootstrap = ApplicationBootstrap(config)
        
        assert bootstrap.config == config
        
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful application initialization"""
        with patch.multiple(
            'src.services.achievement_service',
            AchievementService=AsyncMock
        ), patch.multiple(
            'src.services.activity_meter_service',
            ActivityMeterService=AsyncMock
        ), patch.multiple(
            'src.services.economy_service',
            EconomyService=AsyncMock
        ), patch.multiple(
            'src.services.government_service',
            GovernmentService=AsyncMock
        ), patch.multiple(
            'src.services.test_orchestrator_service',
            TestOrchestratorService=AsyncMock
        ), patch.multiple(
            'src.panels.achievement_panel',
            AchievementPanel=AsyncMock
        ), patch.multiple(
            'src.panels.terminal_panel',
            TerminalPanel=AsyncMock
        ):
            await self.bootstrap.initialize()
            
            assert self.bootstrap._initialized is True
            assert self.bootstrap._services_initialized is True
            assert self.bootstrap._panels_initialized is True
            
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test that initialize is idempotent"""
        with patch.multiple(
            'src.services.achievement_service',
            AchievementService=AsyncMock
        ), patch.multiple(
            'src.services.activity_meter_service',
            ActivityMeterService=AsyncMock
        ), patch.multiple(
            'src.services.economy_service',
            EconomyService=AsyncMock
        ), patch.multiple(
            'src.services.government_service',
            GovernmentService=AsyncMock
        ), patch.multiple(
            'src.services.test_orchestrator_service',
            TestOrchestratorService=AsyncMock
        ), patch.multiple(
            'src.panels.achievement_panel',
            AchievementPanel=AsyncMock
        ), patch.multiple(
            'src.panels.terminal_panel',
            TerminalPanel=AsyncMock
        ):
            await self.bootstrap.initialize()
            await self.bootstrap.initialize()  # Second call
            
            assert self.bootstrap._initialized is True
            
    @pytest.mark.asyncio
    async def test_initialize_service_failure(self):
        """Test initialization with service failure"""
        with patch('src.services.achievement_service.AchievementService') as mock_service:
            mock_instance = AsyncMock()
            mock_instance.initialize.side_effect = Exception("Service initialization failed")
            mock_service.return_value = mock_instance
            
            with pytest.raises(Exception) as exc_info:
                await self.bootstrap.initialize()
                
            assert "Service initialization failed" in str(exc_info.value)
            assert self.bootstrap._initialized is False
            
    @pytest.mark.asyncio
    async def test_shutdown_success(self):
        """Test successful application shutdown"""
        # First initialize
        with patch.multiple(
            'src.services.achievement_service',
            AchievementService=AsyncMock
        ), patch.multiple(
            'src.services.activity_meter_service',
            ActivityMeterService=AsyncMock
        ), patch.multiple(
            'src.services.economy_service',
            EconomyService=AsyncMock
        ), patch.multiple(
            'src.services.government_service',
            GovernmentService=AsyncMock
        ), patch.multiple(
            'src.services.test_orchestrator_service',
            TestOrchestratorService=AsyncMock
        ), patch.multiple(
            'src.panels.achievement_panel',
            AchievementPanel=AsyncMock
        ), patch.multiple(
            'src.panels.terminal_panel',
            TerminalPanel=AsyncMock
        ):
            await self.bootstrap.initialize()
            await self.bootstrap.shutdown()
            
            assert self.bootstrap._initialized is False
            
    @pytest.mark.asyncio
    async def test_run_terminal_mode_not_initialized(self):
        """Test running terminal mode when not initialized"""
        with pytest.raises(RuntimeError) as exc_info:
            await self.bootstrap.run_terminal_mode()
            
        assert "Application not initialized" in str(exc_info.value)
        
    @pytest.mark.asyncio
    async def test_run_terminal_mode_no_panel(self):
        """Test running terminal mode when terminal panel not available"""
        self.bootstrap._initialized = True
        self.bootstrap.terminal_panel = None
        
        with pytest.raises(RuntimeError) as exc_info:
            await self.bootstrap.run_terminal_mode()
            
        assert "Terminal panel not available" in str(exc_info.value)
        
    @pytest.mark.asyncio
    async def test_run_terminal_mode_success(self):
        """Test successful terminal mode execution"""
        mock_terminal_panel = AsyncMock()
        self.bootstrap._initialized = True
        self.bootstrap.terminal_panel = mock_terminal_panel
        
        await self.bootstrap.run_terminal_mode()
        
        mock_terminal_panel.run.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_run_terminal_mode_keyboard_interrupt(self):
        """Test terminal mode with keyboard interrupt"""
        mock_terminal_panel = AsyncMock()
        mock_terminal_panel.run.side_effect = KeyboardInterrupt()
        
        self.bootstrap._initialized = True
        self.bootstrap.terminal_panel = mock_terminal_panel
        
        # Should not raise exception
        await self.bootstrap.run_terminal_mode()
        
    def test_get_service_by_name(self):
        """Test getting service by name"""
        mock_achievement_service = Mock()
        self.bootstrap.achievement_service = mock_achievement_service
        
        result = self.bootstrap.get_service('achievement')
        
        assert result == mock_achievement_service
        
    def test_get_service_unknown_name(self):
        """Test getting unknown service"""
        result = self.bootstrap.get_service('unknown')
        
        assert result is None
        
    def test_get_panel_by_name(self):
        """Test getting panel by name"""
        mock_terminal_panel = Mock()
        self.bootstrap.terminal_panel = mock_terminal_panel
        
        result = self.bootstrap.get_panel('terminal')
        
        assert result == mock_terminal_panel
        
    def test_get_panel_unknown_name(self):
        """Test getting unknown panel"""
        result = self.bootstrap.get_panel('unknown')
        
        assert result is None
        
    def test_is_initialized_false(self):
        """Test is_initialized when not initialized"""
        assert self.bootstrap.is_initialized() is False
        
    def test_is_initialized_true(self):
        """Test is_initialized when initialized"""
        self.bootstrap._initialized = True
        
        assert self.bootstrap.is_initialized() is True
        
    def test_get_status(self):
        """Test getting application status"""
        # Set up mock services
        mock_achievement_service = Mock()
        mock_achievement_service.is_initialized.return_value = True
        self.bootstrap.achievement_service = mock_achievement_service
        
        mock_terminal_panel = Mock()
        mock_terminal_panel.is_initialized.return_value = True
        self.bootstrap.terminal_panel = mock_terminal_panel
        
        self.bootstrap._initialized = True
        self.bootstrap._services_initialized = True
        self.bootstrap._panels_initialized = True
        
        status = self.bootstrap.get_status()
        
        assert status["initialized"] is True
        assert status["services_initialized"] is True
        assert status["panels_initialized"] is True
        assert status["services"]["achievement"] is True
        assert status["panels"]["terminal"] is True
        
    def test_get_status_with_none_services(self):
        """Test getting status when services are None"""
        status = self.bootstrap.get_status()
        
        assert status["services"]["achievement"] is False
        assert status["services"]["economy"] is False
        assert status["panels"]["achievement"] is False
        assert status["panels"]["terminal"] is False