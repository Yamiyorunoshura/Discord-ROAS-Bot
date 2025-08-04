"""Government service package."""

from .government_service import (
    DepartmentChangedEvent,
    DiscordPermissionError,
    FileSyncError,
    GovernmentService,
    GovernmentServiceError,
    RoleSyncError,
)

__all__ = [
    "DepartmentChangedEvent",
    "DiscordPermissionError",
    "FileSyncError",
    "GovernmentService",
    "GovernmentServiceError",
    "RoleSyncError",
]
