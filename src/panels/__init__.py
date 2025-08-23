"""
Panels layer for roas-bot application
Task ID: T2

This module provides the presentation layer for user interactions,
handling Discord events and user feedback.
"""

from .achievement_panel import AchievementPanel
from .terminal_panel import TerminalPanel

__all__ = [
    'AchievementPanel',
    'TerminalPanel',
]