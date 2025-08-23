"""
Unit tests for src.services.achievement_service module
Task ID: T2 - App architecture baseline and scaffolding

CORRECTED TESTS: These tests have been fixed to reflect the actual
architecture and proper method calls after the adapter fix.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.services.achievement_service import AchievementService


class TestAchievementService:
    """Test the AchievementService class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.service = AchievementService()
        
    def test_initialization(self):
        """Test service initialization"""
        assert self.service.service_name == "AchievementService"
        assert self.service._initialized is False
        assert self.service._legacy_service is None
        
    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test service initialization with corrected method calls"""
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            # CORRECTED: Mock the actual method _initialize() not initialize()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            
            assert self.service._initialized is True
            assert self.service._legacy_service is not None
            # CORRECTED: Check for _initialize() call instead of initialize()
            mock_legacy_instance._initialize.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test that initialize is idempotent"""
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            # CORRECTED: Mock the actual method _initialize() not initialize()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            await self.service.initialize()  # Second call
            
            # Should only initialize once
            assert mock_legacy_instance._initialize.call_count == 1
            
    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test initialization failure handling"""
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            # CORRECTED: Mock _initialize() returning False (failure)
            mock_legacy_instance._initialize.return_value = False
            mock_legacy.return_value = mock_legacy_instance
            
            with pytest.raises(RuntimeError) as exc_info:
                await self.service.initialize()
                
            assert "Failed to initialize legacy achievement service" in str(exc_info.value)
            assert self.service._initialized is False
            
    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test service shutdown with corrected method calls"""
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            # CORRECTED: Mock the actual methods _initialize() and _cleanup()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            await self.service.shutdown()
            
            assert self.service._initialized is False
            # CORRECTED: Check for _cleanup() call instead of shutdown()
            mock_legacy_instance._cleanup.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_grant_achievement_not_initialized(self):
        """Test grant_achievement when service not initialized"""
        with pytest.raises(RuntimeError) as exc_info:
            await self.service.grant_achievement(12345, 67890, "test_achievement")
            
        assert "Service not initialized" in str(exc_info.value)
        
    @pytest.mark.asyncio
    async def test_grant_achievement_success(self):
        """Test successful achievement granting with corrected implementation"""
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            
            # CORRECTED: Mock the actual methods used by the adapter
            mock_achievement = MagicMock()
            mock_achievement.rewards = [MagicMock()]
            mock_legacy_instance.get_achievement.return_value = mock_achievement
            mock_legacy_instance.award_reward.return_value = {"success": True}
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            result = await self.service.grant_achievement(12345, 67890, "test_achievement")
            
            assert result is True
            # CORRECTED: Verify the actual methods called by the adapter
            mock_legacy_instance.get_achievement.assert_called_once_with("test_achievement")
            mock_legacy_instance.award_reward.assert_called()
            
    @pytest.mark.asyncio
    async def test_grant_achievement_no_achievement(self):
        """Test achievement granting when achievement doesn't exist"""
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            
            # CORRECTED: Mock get_achievement returning None (not found)
            mock_legacy_instance.get_achievement.return_value = None
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            result = await self.service.grant_achievement(12345, 67890, "nonexistent")
            
            assert result is False
            mock_legacy_instance.get_achievement.assert_called_once_with("nonexistent")
            
    @pytest.mark.asyncio
    async def test_list_user_achievements_not_initialized(self):
        """Test list_user_achievements when service not initialized"""
        with pytest.raises(RuntimeError) as exc_info:
            await self.service.list_user_achievements(12345, 67890)
            
        assert "Service not initialized" in str(exc_info.value)
        
    @pytest.mark.asyncio
    async def test_list_user_achievements_success(self):
        """Test successful user achievement listing"""
        expected_achievements = [
            {"id": "ach1", "name": "First Achievement"},
            {"id": "ach2", "name": "Second Achievement"}
        ]
        
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            # CORRECTED: This method exists in legacy service
            mock_legacy_instance.list_user_achievements.return_value = expected_achievements
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            result = await self.service.list_user_achievements(12345, 67890)
            
            assert result == expected_achievements
            mock_legacy_instance.list_user_achievements.assert_called_once_with(12345, 67890)
            
    @pytest.mark.asyncio
    async def test_get_achievement_progress_not_initialized(self):
        """Test get_achievement_progress when service not initialized"""
        with pytest.raises(RuntimeError) as exc_info:
            await self.service.get_achievement_progress(12345, 67890, "test_achievement")
            
        assert "Service not initialized" in str(exc_info.value)
        
    @pytest.mark.asyncio
    async def test_get_achievement_progress_success(self):
        """Test successful achievement progress retrieval with corrected implementation"""
        # Create a mock progress object that matches the legacy system
        mock_progress = MagicMock()
        mock_progress.achievement_id = "test_achievement"
        mock_progress.user_id = 12345
        mock_progress.guild_id = 67890
        mock_progress.current_progress = 50
        mock_progress.completed = False
        mock_progress.completed_at = None
        mock_progress.last_updated = "2023-01-01"
        
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            # CORRECTED: Mock the actual method get_user_progress() not get_achievement_progress()
            mock_legacy_instance.get_user_progress.return_value = mock_progress
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            result = await self.service.get_achievement_progress(12345, 67890, "test_achievement")
            
            assert result is not None
            assert result["achievement_id"] == "test_achievement"
            assert result["current_progress"] == 50
            assert result["completed"] is False
            # CORRECTED: Verify the actual method called
            mock_legacy_instance.get_user_progress.assert_called_once_with(12345, "test_achievement")
            
    @pytest.mark.asyncio
    async def test_get_achievement_progress_not_found(self):
        """Test achievement progress retrieval when not found"""
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            # CORRECTED: Mock get_user_progress() returning None
            mock_legacy_instance.get_user_progress.return_value = None
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            result = await self.service.get_achievement_progress(12345, 67890, "nonexistent")
            
            assert result is None
            
    def test_is_initialized_false(self):
        """Test is_initialized when service not initialized"""
        assert self.service.is_initialized() is False
        
    @pytest.mark.asyncio
    async def test_is_initialized_true(self):
        """Test is_initialized when service is initialized"""
        with patch('services.achievement.achievement_service.AchievementService') as mock_legacy:
            mock_legacy_instance = AsyncMock()
            mock_legacy_instance._initialize.return_value = True
            mock_legacy_instance.get_dependency.return_value = MagicMock()
            mock_legacy.return_value = mock_legacy_instance
            
            await self.service.initialize()
            
            assert self.service.is_initialized() is True