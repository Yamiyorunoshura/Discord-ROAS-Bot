"""Discord ROAS Bot - Modern Python 3.12 Implementation."""

from src.core.bot import ADRBot
from src.core.config import Settings

__version__ = "2.0.0"
__author__ = "ROAS MOTS"
__email__ = "admin@adrbot.dev"
__description__ = (
    "Advanced Discord server management bot with modern Python architecture"
)

# Version info tuple for programmatic access - handle non-standard versions
try:
    VERSION_INFO = tuple(map(int, __version__.split(".")))
except ValueError:
    VERSION_INFO = tuple(__version__.split("."))

__all__ = ["VERSION_INFO", "ADRBot", "Settings", "__version__"]
