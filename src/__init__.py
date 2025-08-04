"""Discord ROAS Bot - Modern Python 3.12 Implementation."""

from src.core.bot import ADRBot
from src.core.config import Settings

__version__ = "2.2.0"
__author__ = "ROAS MOTS"
__email__ = "admin@adrbot.dev"
__description__ = (
    "Advanced Discord server management bot with modern Python architecture"
)

# Version info tuple for programmatic access - handle non-standard versions
def _parse_version(version_str: str) -> tuple:
    """Parse version string into tuple of integers and strings."""
    parts = version_str.split(".")
    result = []
    for part in parts:
        try:
            result.append(int(part))
        except ValueError:
            result.append(part)
    return tuple(result)

VERSION_INFO = _parse_version(__version__)

__all__ = ["VERSION_INFO", "ADRBot", "Settings", "__version__"]
