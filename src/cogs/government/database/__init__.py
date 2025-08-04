"""Government database package."""

from .government_repository import (
    CircularReferenceError,
    DepartmentNotFoundError,
    DuplicateDepartmentError,
    GovernmentRepository,
    GovernmentRepositoryError,
)

__all__ = [
    "CircularReferenceError",
    "DepartmentNotFoundError",
    "DuplicateDepartmentError",
    "GovernmentRepository",
    "GovernmentRepositoryError",
]
