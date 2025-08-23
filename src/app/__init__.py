"""
Application layer for roas-bot
Task ID: T2

This module provides application startup, bootstrapping, and dependency injection
for the roas-bot application architecture.
"""

from .bootstrap import ApplicationBootstrap

__all__ = [
    'ApplicationBootstrap',
]