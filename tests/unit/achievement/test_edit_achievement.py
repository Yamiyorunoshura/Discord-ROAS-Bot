"""Tests for achievement editing functionality.

This module tests the achievement editing features including:
- Achievement selection interface
- Editing modal forms
- Data validation
- Change detection and preview
- Update confirmation flow
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest

from src.cogs.achievement.database.models import Achievement, AchievementType
from src.cogs.achievement.panel.admin_panel import (
    AchievementManagementView,
    AchievementSelectionView,
    AdminPanel,
    AdminPanelState,
    EditAchievementConfirmView,
    EditAchievementModal,
)


class TestAchievementEditFunctionality:
    """Test suite for achievement editing functionality."""

    @pytest.fixture
    def mock_admin_panel(self):
        """Create a mock admin panel."""
        panel = Mock(spec=AdminPanel)
        panel.handle_navigation = AsyncMock()
        return panel

    @pytest.fixture
    def sample_achievement(self):
        """Create a sample achievement for testing."""
        return Achievement(
            id=1,
            name="初次發言",
            description="在伺服器中發送第一條訊息",
            category_id=1,
            type=AchievementType.MILESTONE,
            criteria={"target_value": 1, "milestone_type": "first_message"},
            points=10,
            badge_url=None,
            is_active=True,
            role_reward=None,
            is_hidden=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @pytest.fixture
    def sample_achievements(self, sample_achievement):
        """Create a list of sample achievements."""
        return [
            sample_achievement,
            Achievement(
                id=2,
                name="社交高手",
                description="累計發送100條訊息",
                category_id=1,
                type=AchievementType.COUNTER,
                criteria={"target_value": 100, "counter_field": "message_count"},
                points=50,
                badge_url=None,
                is_active=True,
                role_reward="社交達人",
                is_hidden=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.response.send_modal = AsyncMock()
        interaction.followup.send = AsyncMock()
        return interaction

    def test_achievement_management_view_get_available_achievements(
        self, mock_admin_panel
    ):
        """Test getting available achievements from management view."""
        view = AchievementManagementView(mock_admin_panel)

        # Test that the method exists and can be called
        assert hasattr(view, "_get_available_achievements")
        assert callable(view._get_available_achievements)

    @pytest.mark.asyncio
    async def test_handle_edit_achievement_no_achievements(
        self, mock_admin_panel, mock_interaction
    ):
        """Test handling edit when no achievements are available."""
        view = AchievementManagementView(mock_admin_panel)

        # Mock empty achievements list
        with patch.object(view, "_get_available_achievements", return_value=[]):
            await view._handle_edit_achievement(mock_interaction)

        # Should send error message
        mock_interaction.response.send_message.assert_called_once()
        args = mock_interaction.response.send_message.call_args
        assert "❌ 沒有可編輯的成就" in str(args)

    @pytest.mark.asyncio
    async def test_handle_edit_achievement_with_achievements(
        self, mock_admin_panel, mock_interaction, sample_achievements
    ):
        """Test handling edit with available achievements."""
        view = AchievementManagementView(mock_admin_panel)

        # Mock achievements list
        with patch.object(
            view, "_get_available_achievements", return_value=sample_achievements
        ):
            await view._handle_edit_achievement(mock_interaction)

        # Should send achievement selection view
        mock_interaction.response.send_message.assert_called_once()

    def test_achievement_selection_view_initialization(
        self, mock_admin_panel, sample_achievements
    ):
        """Test AchievementSelectionView initialization."""
        view = AchievementSelectionView(mock_admin_panel, sample_achievements, "edit")

        assert view.admin_panel == mock_admin_panel
        assert view.achievements == sample_achievements
        assert view.action == "edit"

        # Check that select menu is created
        assert len(view.children) == 1
        assert isinstance(view.children[0], discord.ui.Select)

    def test_achievement_selection_view_options_creation(
        self, mock_admin_panel, sample_achievements
    ):
        """Test that achievement selection options are created correctly."""
        view = AchievementSelectionView(mock_admin_panel, sample_achievements, "edit")
        select_menu = view.children[0]

        assert len(select_menu.options) == len(sample_achievements)

        # Check first option
        first_option = select_menu.options[0]
        assert "初次發言" in first_option.label
        assert first_option.value == "1"
        assert first_option.emoji == "🏆"

    @pytest.mark.asyncio
    async def test_achievement_selection_invalid_id(
        self, mock_admin_panel, sample_achievements, mock_interaction
    ):
        """Test handling invalid achievement ID selection."""
        view = AchievementSelectionView(mock_admin_panel, sample_achievements, "edit")

        # Mock select with invalid ID
        view.achievement_select.values = ["999"]

        await view.on_achievement_select(mock_interaction)

        # Should send error message
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args
        assert "❌ 選擇的成就無效" in str(args)

    @pytest.mark.asyncio
    async def test_achievement_selection_edit_action(
        self, mock_admin_panel, sample_achievements, mock_interaction
    ):
        """Test handling edit action in achievement selection."""
        view = AchievementSelectionView(mock_admin_panel, sample_achievements, "edit")

        # Mock select with valid ID
        view.achievement_select.values = ["1"]

        with patch.object(view, "_handle_edit_selected") as mock_edit:
            await view.on_achievement_select(mock_interaction)

        # Should call edit handler with correct achievement
        mock_edit.assert_called_once()
        args = mock_edit.call_args[0]
        assert args[1].id == 1

    def test_edit_achievement_modal_initialization(
        self, mock_admin_panel, sample_achievement
    ):
        """Test EditAchievementModal initialization."""
        modal = EditAchievementModal(mock_admin_panel, sample_achievement)

        assert modal.admin_panel == mock_admin_panel
        assert modal.achievement == sample_achievement
        assert modal.title == f"編輯成就: {sample_achievement.name}"

        # Check that all input fields are created
        assert len(modal.children) == 5  # name, description, points, type, badge_url

    def test_edit_achievement_modal_default_values(
        self, mock_admin_panel, sample_achievement
    ):
        """Test that modal fields are populated with current values."""
        modal = EditAchievementModal(mock_admin_panel, sample_achievement)

        # Check default values
        name_input = modal.children[0]
        assert name_input.default == sample_achievement.name

        description_input = modal.children[1]
        assert description_input.default == sample_achievement.description

        points_input = modal.children[2]
        assert points_input.default == str(sample_achievement.points)

        type_input = modal.children[3]
        assert type_input.default == sample_achievement.type.value

    @pytest.mark.asyncio
    async def test_edit_modal_empty_name_validation(
        self, mock_admin_panel, sample_achievement, mock_interaction
    ):
        """Test validation for empty achievement name."""
        modal = EditAchievementModal(mock_admin_panel, sample_achievement)

        # Mock empty name input
        modal.name_input.value = "   "
        modal.description_input.value = "Valid description"
        modal.points_input.value = "10"
        modal.type_input.value = "milestone"
        modal.badge_url_input.value = ""

        await modal.on_submit(mock_interaction)

        # Should send validation error
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args
        assert "❌ 成就名稱不能為空" in str(args)

    @pytest.mark.asyncio
    async def test_edit_modal_invalid_points_validation(
        self, mock_admin_panel, sample_achievement, mock_interaction
    ):
        """Test validation for invalid points value."""
        modal = EditAchievementModal(mock_admin_panel, sample_achievement)

        # Mock invalid points input
        modal.name_input.value = "Valid Name"
        modal.description_input.value = "Valid description"
        modal.points_input.value = "invalid"
        modal.type_input.value = "milestone"
        modal.badge_url_input.value = ""

        await modal.on_submit(mock_interaction)

        # Should send validation error
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args
        assert "❌ 獎勵點數必須為 0-10000 的整數" in str(args)

    @pytest.mark.asyncio
    async def test_edit_modal_invalid_type_validation(
        self, mock_admin_panel, sample_achievement, mock_interaction
    ):
        """Test validation for invalid achievement type."""
        modal = EditAchievementModal(mock_admin_panel, sample_achievement)

        # Mock invalid type input
        modal.name_input.value = "Valid Name"
        modal.description_input.value = "Valid description"
        modal.points_input.value = "10"
        modal.type_input.value = "invalid_type"
        modal.badge_url_input.value = ""

        await modal.on_submit(mock_interaction)

        # Should send validation error
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args
        assert "❌ 無效的成就類型" in str(args)

    @pytest.mark.asyncio
    async def test_edit_modal_no_changes_detection(
        self, mock_admin_panel, sample_achievement, mock_interaction
    ):
        """Test detection when no changes are made."""
        modal = EditAchievementModal(mock_admin_panel, sample_achievement)

        # Mock inputs with same values as original
        modal.name_input.value = sample_achievement.name
        modal.description_input.value = sample_achievement.description
        modal.points_input.value = str(sample_achievement.points)
        modal.type_input.value = sample_achievement.type.value
        modal.badge_url_input.value = sample_achievement.badge_url or ""

        await modal.on_submit(mock_interaction)

        # Should send no changes message
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args
        assert "ℹ️ 沒有檢測到任何變更" in str(args)

    @pytest.mark.asyncio
    async def test_edit_modal_changes_detection(
        self, mock_admin_panel, sample_achievement, mock_interaction
    ):
        """Test detection and preview of changes."""
        modal = EditAchievementModal(mock_admin_panel, sample_achievement)

        # Mock inputs with changed values
        modal.name_input.value = "Updated Name"
        modal.description_input.value = "Updated description"
        modal.points_input.value = "20"
        modal.type_input.value = "counter"
        modal.badge_url_input.value = "https://example.com/badge.png"

        await modal.on_submit(mock_interaction)

        # Should send preview with changes
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args

        # Check that embed and view are provided
        assert "embed" in call_args.kwargs
        assert "view" in call_args.kwargs

    def test_edit_confirm_view_initialization(
        self, mock_admin_panel, sample_achievement
    ):
        """Test EditAchievementConfirmView initialization."""
        changes = {"name": "New Name", "points": 20}
        view = EditAchievementConfirmView(mock_admin_panel, sample_achievement, changes)

        assert view.admin_panel == mock_admin_panel
        assert view.achievement == sample_achievement
        assert view.changes == changes

        # Check that buttons are created
        assert len(view.children) == 2  # confirm and cancel buttons

    @pytest.mark.asyncio
    async def test_edit_confirm_update_success(
        self, mock_admin_panel, sample_achievement, mock_interaction
    ):
        """Test successful achievement update confirmation."""
        changes = {"name": "New Name", "points": 20}
        view = EditAchievementConfirmView(mock_admin_panel, sample_achievement, changes)

        await view.confirm_update(mock_interaction, Mock())

        # Should send success message and navigate back
        mock_interaction.followup.send.assert_called_once()
        mock_admin_panel.handle_navigation.assert_called_once_with(
            mock_interaction, AdminPanelState.ACHIEVEMENTS
        )

    @pytest.mark.asyncio
    async def test_edit_confirm_cancel(
        self, mock_admin_panel, sample_achievement, mock_interaction
    ):
        """Test cancelling achievement update."""
        changes = {"name": "New Name", "points": 20}
        view = EditAchievementConfirmView(mock_admin_panel, sample_achievement, changes)

        await view.cancel_update(mock_interaction, Mock())

        # Should send cancellation message
        mock_interaction.response.send_message.assert_called_once()
        args = mock_interaction.response.send_message.call_args
        assert "✅ 成就編輯操作已被取消" in str(args)


class TestAchievementEditIntegration:
    """Integration tests for achievement editing workflow."""

    @pytest.mark.asyncio
    async def test_complete_edit_workflow(self):
        """Test the complete achievement editing workflow."""
        # This would test the full flow from selection to confirmation
        # In a real implementation, this would involve:
        # 1. Opening edit dialog
        # 2. Selecting achievement
        # 3. Filling edit form
        # 4. Reviewing changes
        # 5. Confirming update

        # For now, we'll mark this as a placeholder for future implementation
        assert True

    @pytest.mark.asyncio
    async def test_edit_workflow_error_handling(self):
        """Test error handling throughout the edit workflow."""
        # This would test error scenarios like:
        # - Network failures
        # - Database errors
        # - Permission issues
        # - Invalid data

        # For now, we'll mark this as a placeholder for future implementation
        assert True


if __name__ == "__main__":
    pytest.main([__file__])
