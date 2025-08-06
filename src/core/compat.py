"""Python 3.12 compatibility helpers and fixes."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Coroutine


class AsyncIteratorWrapper[T]:
    """Wrapper to fix 'coroutine' object is not an async iterator errors."""

    def __init__(self, async_iterable: AsyncIterable[T]):
        """Initialize wrapper with async iterable."""
        self._async_iterable = async_iterable
        self._iterator: AsyncIterator[T] | None = None

    def __aiter__(self) -> AsyncIterator[T]:
        """Return async iterator."""
        if self._iterator is None:
            self._iterator = self._async_iterable.__aiter__()
        return self._iterator

    async def __anext__(self) -> T:
        """Get next item from async iterator."""
        if self._iterator is None:
            self._iterator = self._async_iterable.__aiter__()
        return await self._iterator.__anext__()


def ensure_async_iterator(obj: Any) -> AsyncIterator[Any]:
    """Ensure object is an async iterator, fixing Python 3.12 compatibility issues.

    Args:
        obj: Object that should be an async iterator

    Returns:
        Properly wrapped async iterator
    """
    # Check if it's already an async iterator
    if hasattr(obj, "__aiter__") and hasattr(obj, "__anext__"):
        return obj  # type: ignore[no-any-return]

    # Check if it's an async iterable
    if hasattr(obj, "__aiter__"):
        return obj.__aiter__()  # type: ignore[no-any-return]

    # Check if it's a coroutine that should return an async iterator
    if asyncio.iscoroutine(obj):

        async def _wrapper() -> AsyncIterator[Any]:
            result = await obj
            if hasattr(result, "__aiter__"):
                async for item in result:
                    yield item
            else:
                yield result

        return _wrapper()

    # If it's a regular iterable, convert to async iterator
    if hasattr(obj, "__iter__"):

        async def _async_iter() -> AsyncIterator[Any]:
            for item in obj:
                yield item

        return _async_iter()

    # Fallback: wrap in async iterator that yields the object
    async def _single_item() -> AsyncIterator[Any]:
        yield obj

    return _single_item()


async def safe_async_iterator[T](
    coro_or_iter: Awaitable[AsyncIterable[T]] | AsyncIterable[T],
) -> AsyncIterator[T]:
    """Safely handle coroutines that return async iterators.

    This fixes the common Python 3.12 error:
    'coroutine' object is not an async iterator

    Args:
        coro_or_iter: Either a coroutine that returns an async iterable,
                     or an async iterable directly

    Yields:
        Items from the async iterator
    """
    # If it's a coroutine, await it first
    if asyncio.iscoroutine(coro_or_iter):
        async_iterable = await coro_or_iter
    else:
        async_iterable = coro_or_iter

    # Now iterate over the async iterable
    if hasattr(async_iterable, "__aiter__"):
        async for item in async_iterable:
            yield item
    # If it's not async iterable, try to make it one
    elif hasattr(async_iterable, "__iter__"):
        for item in async_iterable:
            yield item
    else:
        yield async_iterable


class AsyncContextManagerWrapper:
    """Wrapper for async context managers to fix Python 3.12 issues."""

    def __init__(self, context_manager: Any):
        """Initialize wrapper."""
        self._context_manager = context_manager

    async def __aenter__(self) -> Any:
        """Enter async context."""
        if hasattr(self._context_manager, "__aenter__"):
            return await self._context_manager.__aenter__()
        else:
            # Fallback for objects that aren't proper async context managers
            return self._context_manager

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        if hasattr(self._context_manager, "__aexit__"):
            await self._context_manager.__aexit__(exc_type, exc_val, exc_tb)


def fix_async_context_manager(obj: Any) -> AsyncContextManagerWrapper:
    """Fix async context manager compatibility issues.

    Args:
        obj: Object that should be an async context manager

    Returns:
        Wrapped async context manager
    """
    return AsyncContextManagerWrapper(obj)


# Database cursor compatibility fixes
class AsyncCursorWrapper:
    """Wrapper for database cursors to fix async iteration issues."""

    def __init__(self, cursor: Any):
        """Initialize cursor wrapper."""
        self._cursor = cursor

    def __aiter__(self) -> AsyncIterator[Any]:
        """Return async iterator for cursor."""
        return self

    async def __anext__(self) -> Any:
        """Get next row from cursor."""
        if hasattr(self._cursor, "fetchone"):
            row = await self._cursor.fetchone()
            if row is None:
                raise StopAsyncIteration
            return row
        else:
            raise StopAsyncIteration

    async def fetchall(self) -> list[Any]:
        """Fetch all rows."""
        if hasattr(self._cursor, "fetchall"):
            result: list[Any] = await self._cursor.fetchall()
            return result
        else:
            rows = []
            try:
                async for row in self:
                    rows.append(row)
            except StopAsyncIteration:
                pass
            return rows

    async def fetchone(self) -> Any:
        """Fetch one row."""
        if hasattr(self._cursor, "fetchone"):
            return await self._cursor.fetchone()
        else:
            try:
                return await self.__anext__()
            except StopAsyncIteration:
                return None

    @property
    def lastrowid(self) -> int | None:
        """Get last inserted row ID."""
        if hasattr(self._cursor, "lastrowid"):
            return self._cursor.lastrowid  # type: ignore[no-any-return]
        return None

    @property
    def rowcount(self) -> int:
        """Get affected row count."""
        if hasattr(self._cursor, "rowcount"):
            return self._cursor.rowcount  # type: ignore[no-any-return]
        return -1


def fix_database_cursor(cursor: Any) -> AsyncCursorWrapper:
    """Fix database cursor for Python 3.12 compatibility.

    Args:
        cursor: Database cursor object

    Returns:
        Wrapped cursor with proper async iteration
    """
    return AsyncCursorWrapper(cursor)


# HTTP session compatibility fixes
class AsyncHTTPSessionWrapper:
    """Wrapper for HTTP sessions to fix async context manager issues."""

    def __init__(self, session_factory: Any):
        """Initialize session wrapper."""
        self._session_factory = session_factory
        self._session: Any = None

    async def __aenter__(self) -> Any:
        """Enter async context and create session."""
        if asyncio.iscoroutinefunction(self._session_factory):
            self._session = await self._session_factory()
        else:
            self._session = self._session_factory()

        # If session has __aenter__, use it
        if hasattr(self._session, "__aenter__"):
            return await self._session.__aenter__()
        else:
            return self._session

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context and close session."""
        if self._session:
            if hasattr(self._session, "__aexit__"):
                await self._session.__aexit__(exc_type, exc_val, exc_tb)
            elif hasattr(self._session, "close"):
                if asyncio.iscoroutinefunction(self._session.close):
                    await self._session.close()
                else:
                    self._session.close()


def fix_http_session(session_factory: Any) -> AsyncHTTPSessionWrapper:
    """Fix HTTP session for Python 3.12 compatibility.

    Args:
        session_factory: Function or class that creates HTTP session

    Returns:
        Wrapped session with proper async context management
    """
    return AsyncHTTPSessionWrapper(session_factory)


# General purpose async wrapper
async def ensure_awaitable(obj: Any) -> Any:
    """Ensure object is awaitable, handling various Python 3.12 edge cases.

    Args:
        obj: Object that might need to be awaited

    Returns:
        Result of awaiting the object, or the object itself if not awaitable
    """
    if asyncio.iscoroutine(obj) or hasattr(obj, "__await__"):
        return await obj
    else:
        return obj


# Task creation helpers for Python 3.12
def create_task_safe[T](
    coro: Coroutine[Any, Any, T], *, name: str | None = None
) -> asyncio.Task[T]:
    """Safely create asyncio task with Python 3.12 compatibility.

    Args:
        coro: Coroutine to run as task
        name: Optional task name

    Returns:
        Created task
    """
    try:
        # Python 3.11+ supports name parameter
        if sys.version_info >= (3, 11) and name is not None:
            return asyncio.create_task(coro, name=name)
        else:
            return asyncio.create_task(coro)
    except Exception:
        # Fallback for edge cases
        loop = asyncio.get_event_loop()
        return loop.create_task(coro)


# Gather with proper error handling
async def gather_safe(
    *coros: Awaitable[Any], return_exceptions: bool = False
) -> list[Any]:
    """Safely gather coroutines with Python 3.12 compatibility.

    Args:
        *coros: Coroutines to gather
        return_exceptions: Whether to return exceptions instead of raising

    Returns:
        List of results
    """
    try:
        return await asyncio.gather(*coros, return_exceptions=return_exceptions)
    except Exception as e:
        if return_exceptions:
            return [e for _ in coros]
        else:
            raise


__all__ = [
    "AsyncContextManagerWrapper",
    "AsyncCursorWrapper",
    "AsyncHTTPSessionWrapper",
    "AsyncIteratorWrapper",
    "create_task_safe",
    "ensure_async_iterator",
    "ensure_awaitable",
    "fix_async_context_manager",
    "fix_database_cursor",
    "fix_http_session",
    "gather_safe",
    "safe_async_iterator",
]
