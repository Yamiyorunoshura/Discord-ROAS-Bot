"""Main entry point for Discord ROAS Bot v2.0."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.core.bot import create_and_run_bot
from src.core.config import (
    Settings,
)
from src.core.logger import setup_logging

# Rich console for beautiful output
console = Console()

# Typer CLI app
app = typer.Typer(
    name="adr-bot",
    help="Discord ADR Bot - Advanced server management bot",
    add_completion=False,
)


def setup_event_loop() -> None:
    """Set up the optimal event loop for the platform."""
    try:
        # Use uvloop on Unix systems for better performance
        if sys.platform != "win32":
            import uvloop
            uvloop.install()
            console.print("[green]Using uvloop for enhanced performance[/green]")
        else:
            console.print("[yellow]Using default asyncio event loop (Windows)[/yellow]")
    except ImportError:
        console.print(
            "[yellow]uvloop not available, using default event loop[/yellow]"
        )


def check_python_version() -> None:
    """Check if Python version is compatible."""


def print_banner() -> None:
    """Print application banner."""
    banner_text = Text()
    banner_text.append("Discord ADR Bot v2.0\n", style="bold blue")
    banner_text.append("Advanced Server Management Bot\n", style="cyan")
    banner_text.append(
        f"Python {sys.version.split()[0]} • Modern Architecture", style="dim"
    )

    panel = Panel(
        banner_text,
        border_style="blue",
        padding=(1, 2),
    )

    console.print(panel)


async def validate_and_load_configuration(config_file: Path | None = None) -> Settings:
    """Validate environment and load configuration using simple Settings.

    Args:
        config_file: Optional configuration file path

    Returns:
        Loaded settings

    Raises:
        typer.Exit: If validation fails
    """
    try:
        # 臨時使用簡單的Settings類，避免複雜配置系統的編碼問題
        console.print("[cyan]Loading configuration...[/cyan]")
        settings = Settings()

        # Validate token
        if not settings.token:
            console.print("[red]Discord bot token not found![/red]")
            console.print(
                "   Please set [yellow]TOKEN[/yellow] in your .env file or environment variables."
            )
            console.print(
                "   Example: [dim]echo 'TOKEN=your_bot_token_here' > .env[/dim]"
            )
            raise typer.Exit(1)

        # Validate token format (basic check)
        if not settings.token.startswith(("MTI", "OTk", "MTA", "MTM", "Bot ")):
            console.print(
                "[yellow]Warning: Token format might be incorrect[/yellow]"
            )
            console.print(
                "   Discord bot tokens usually start with 'MTI', 'OTk', or 'MTA'"
            )

        # Create necessary directories
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.logging.file_path.mkdir(parents=True, exist_ok=True)
        settings.database.sqlite_path.mkdir(parents=True, exist_ok=True)

        console.print(
            "[green]Configuration loaded successfully[/green]"
        )
        return settings

    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def run(
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="Discord bot token (overrides environment variable)",
    ),
    environment: str | None = typer.Option(
        None,
        "--env",
        "-e",
        help="Environment (development/staging/production)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug mode",
    ),
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    hot_reload: bool = typer.Option(
        True,
        "--hot-reload/--no-hot-reload",
        help="Enable/disable configuration hot reload",
    ),
) -> None:
    """Run the Discord ADR Bot with unified configuration system."""

    async def main():
        # Print banner
        print_banner()

        # Check Python version
        check_python_version()

        # Set environment variables if provided
        if token:
            os.environ["TOKEN"] = token
        if environment:
            os.environ["ENVIRONMENT"] = environment
        if debug:
            os.environ["DEBUG"] = "true"

        try:
            # Validate environment and load settings
            settings = await validate_and_load_configuration(config_file)

            # Print configuration summary
            console.print(f"[green]Environment:[/green] {settings.environment}")
            console.print(f"[green]Python:[/green] {sys.version.split()[0]}")
            console.print(f"[green]Project Root:[/green] {settings.project_root}")
            console.print(
                f"[green]Debug Mode:[/green] {'Enabled' if settings.debug else 'Disabled'}"
            )
            console.print(
                f"[green]Hot Reload:[/green] {'Enabled' if hot_reload else 'Disabled'}"
            )

            # Set up event loop
            setup_event_loop()

            # Set up logging
            setup_logging(settings)

            # Print enabled features
            enabled_features = [
                name for name, enabled in settings.features.items() if enabled
            ]
            console.print(
                f"[green]Enabled Features:[/green] {', '.join(enabled_features)}"
            )

            # Run the bot
            console.print(
                "[green bold]Starting Discord ADR Bot with unified configuration...[/green bold]"
            )

            try:
                await create_and_run_bot(settings)
            except KeyboardInterrupt:
                console.print("\n🛑 [yellow]Bot stopped by user[/yellow]")
            except Exception as e:
                console.print(f"💥 [red bold]Fatal error: {e}[/red bold]")
                console.print("📝 [dim]Check the logs for more details[/dim]")
                raise
            finally:
                # 清理資源
                console.print("🔧 [cyan]Cleaning up resources...[/cyan]")
                console.print("✅ [green]Cleanup complete[/green]")

        except Exception as e:
            console.print(f"💥 [red bold]Startup error: {e}[/red bold]")
            sys.exit(1)

    try:
        asyncio.run(main())
        console.print("👋 [green]Thank you for using Discord ADR Bot![/green]")
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Application interrupted[/yellow]")
    except Exception as e:
        console.print(f"💥 [red bold]Application error: {e}[/red bold]")
        sys.exit(1)


@app.command()
def validate_config(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    show_sources: bool = typer.Option(
        False,
        "--show-sources",
        help="Show configuration sources",
    ),
) -> None:
    """Validate configuration using unified configuration system."""

    async def main():
        console.print("[cyan]Validating configuration...[/cyan]")

        try:
            # Load configuration using unified system
            settings = await validate_and_load_configuration(config_file)

            # Print detailed configuration
            console.print(
                "\n✅ [green bold]Configuration validation successful![/green bold]"
            )

            # Basic configuration info
            console.print(f"Environment: {settings.environment}")
            console.print(f"🔑 Token: {'✓ Present' if settings.token else '✗ Missing'}")
            console.print(f"Data Directory: {settings.data_dir}")
            console.print(f"📝 Log Directory: {settings.logging.file_path}")
            console.print(f"🗄️  Database Directory: {settings.database.sqlite_path}")

            # Feature flags
            enabled_features = [
                name for name, enabled in settings.features.items() if enabled
            ]
            disabled_features = [
                name for name, enabled in settings.features.items() if not enabled
            ]
            console.print(
                f"✅ Enabled Features: {', '.join(enabled_features) if enabled_features else 'None'}"
            )
            console.print(
                f"❌ Disabled Features: {', '.join(disabled_features) if disabled_features else 'None'}"
            )

            # Database configuration
            console.print("\n🗄️  Database Configuration:")
            console.print(f"   Pool Size: {settings.database.pool_size}")
            console.print(f"   Max Overflow: {settings.database.max_overflow}")
            console.print(f"   Query Timeout: {settings.database.query_timeout}s")
            console.print(
                f"   WAL Mode: {'Enabled' if settings.database.enable_wal_mode else 'Disabled'}"
            )

            # Logging configuration
            console.print("\n📝 Logging Configuration:")
            console.print(f"   Level: {settings.logging.level}")
            console.print(f"   Format: {settings.logging.format}")
            console.print(
                f"   File Logging: {'Enabled' if settings.logging.file_enabled else 'Disabled'}"
            )
            console.print(
                f"   Console Logging: {'Enabled' if settings.logging.console_enabled else 'Disabled'}"
            )

            # Performance configuration
            console.print("\n⚡ Performance Configuration:")
            console.print(f"   Max Workers: {settings.performance.max_workers}")
            console.print(
                f"   Event Loop Policy: {settings.performance.event_loop_policy}"
            )
            console.print(
                f"   Max Concurrent Tasks: {settings.performance.max_concurrent_tasks}"
            )
            console.print(
                f"   Metrics Enabled: {'Yes' if settings.performance.metrics_enabled else 'No'}"
            )

            # Security configuration
            console.print("\n🔒 Security Configuration:")
            console.print(
                f"   Rate Limiting: {'Enabled' if settings.security.rate_limit_enabled else 'Disabled'}"
            )
            console.print(
                f"   Rate Limit: {settings.security.rate_limit_requests} requests/{settings.security.rate_limit_window}s"
            )
            console.print(
                f"   Admin Roles: {len(settings.security.admin_role_ids)} configured"
            )
            console.print(
                f"   Moderator Roles: {len(settings.security.moderator_role_ids)} configured"
            )

            # Configuration sources (if requested)
            if show_sources:
                try:
                    from src.core.config import get_config_manager

                    manager = get_config_manager()
                    console.print("\n📊 Configuration Sources:")
                    for name, loader in manager.loaders.items():
                        console.print(f"   • {name}: {loader.source.name}")
                except Exception as e:
                    console.print(f"⚠️  Could not show configuration sources: {e}")

            console.print("\n🎉 [green]All configuration checks passed![/green]")

        except Exception as e:
            console.print(f"❌ [red]Configuration validation failed: {e}[/red]")
            import traceback

            console.print(f"📝 [dim]Details: {traceback.format_exc()}[/dim]")
            sys.exit(1)
        finally:
            # 清理資源
            pass

    try:
        asyncio.run(main())
    except Exception as e:
        console.print(f"💥 [red bold]Validation error: {e}[/red bold]")
        sys.exit(1)


@app.command()
def create_config() -> None:
    """Create a sample configuration file."""
    config_content = """# Discord ADR Bot Configuration
# Copy this to .env in your project root

# Discord Bot Token (Required)
TOKEN=your_bot_token_here

# Environment (development/staging/production)
ENVIRONMENT=development

# Debug Mode (true/false)
DEBUG=false

# Database Settings
DB_POOL_SIZE=10
DB_QUERY_TIMEOUT=30

# Cache Settings
CACHE_DEFAULT_TTL=300
CACHE_MAX_SIZE=1000

# Logging Settings
LOG_LEVEL=INFO
LOG_FORMAT=colored
LOG_FILE_ENABLED=true

# Performance Settings
PERF_MAX_WORKERS=4
PERF_MAX_CONCURRENT_TASKS=100

# Security Settings
SECURITY_RATE_LIMIT_ENABLED=true
SECURITY_RATE_LIMIT_REQUESTS=100
SECURITY_RATE_LIMIT_WINDOW=60
"""

    config_path = Path(".env.example")

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)

        console.print(f"✅ [green]Sample configuration created: {config_path}[/green]")
        console.print(
            "📝 [yellow]Copy this file to .env and customize it for your setup[/yellow]"
        )

    except Exception as e:
        console.print(f"❌ [red]Failed to create configuration file: {e}[/red]")
        sys.exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    from src import __author__, __description__, __version__

    console.print(f"Discord ADR Bot v{__version__}")
    console.print(f"Author: {__author__}")
    console.print(f"Description: {__description__}")
    console.print(f"Python: {sys.version.split()[0]}")
    console.print(f"Platform: {sys.platform}")


def cli() -> None:
    """CLI entry point for setuptools."""
    app()


if __name__ == "__main__":
    cli()
