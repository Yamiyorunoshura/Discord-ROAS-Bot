"""Modern Discord ADR Bot implementation with Python 3.12 features."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands

from src.core.compat import create_task_safe, gather_safe
from src.core.config import Settings, get_settings
from src.core.container import get_container
from src.core.logger import get_logger, setup_discord_logging, setup_logging

# 導入整合的事件匯流排和錯誤處理模組
try:
    import os
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.cogs.core.error_handler import (
        ErrorHandler,
        ErrorSeverity,
        create_error_handler,
    )
    from src.cogs.core.event_bus import (
        Event,
        EventBus,
        EventPriority,
        get_global_event_bus,
    )
except ImportError:
    # 如果無法導入舊模組,使用佔位符
    EventBus = None
    Event = None
    EventPriority = None
    get_global_event_bus = None
    ErrorHandler = None
    ErrorSeverity = None
    create_error_handler = None


class ModuleLoadResult:
    """Result of module loading operation."""

    def __init__(
        self, name: str, success: bool, load_time: float, error: Exception | None = None
    ):
        """Initialize load result.

        Args:
            name: Module name
            success: Whether loading succeeded
            load_time: Time taken to load
            error: Exception if loading failed
        """
        self.name = name
        self.success = success
        self.load_time = load_time
        self.error = error


class StartupManager:
    """Modern startup manager for bot modules."""

    def __init__(self, bot: ADRBot, settings: Settings):
        """Initialize startup manager.

        Args:
            bot: Bot instance
            settings: Settings instance
        """
        self.bot = bot
        self.settings = settings
        self.logger = get_logger("startup", settings)

        # Module configuration
        self.module_config = {
            "core": {
                "priority": 0,
                "critical": True,
                "description": "Core functionality",
            },
            "activity_meter": {
                "priority": 1,
                "critical": False,
                "description": "Activity tracking",
            },
            "message_listener": {
                "priority": 1,
                "critical": False,
                "description": "Message monitoring",
            },
            "protection": {
                "priority": 2,
                "critical": False,
                "description": "Server protection",
            },
            "welcome": {
                "priority": 1,
                "critical": False,
                "description": "Welcome system",
            },
            "sync_data": {
                "priority": 3,
                "critical": False,
                "description": "Data synchronization",
            },
        }

    async def discover_and_load_modules(self) -> dict[str, Any]:
        """Discover and load all bot modules.

        Returns:
            Dictionary with loading statistics
        """
        start_time = time.perf_counter()
        self.logger.info("Starting module discovery and loading")

        # Discover modules
        modules = self._discover_modules()

        if not modules:
            self.logger.warning("No modules discovered")
            return {
                "total_modules": 0,
                "loaded_modules": 0,
                "failed_modules": 0,
                "total_time": 0.0,
                "results": [],
            }

        # Load modules by priority
        results = await self._load_modules_by_priority(modules)

        # Calculate statistics
        total_time = time.perf_counter() - start_time
        loaded_count = sum(1 for r in results if r.success)
        failed_count = len(results) - loaded_count

        stats = {
            "total_modules": len(results),
            "loaded_modules": loaded_count,
            "failed_modules": failed_count,
            "total_time": total_time,
            "results": results,
        }

        # Log summary
        self.logger.info(
            "Module loading completed",
            total_modules=len(results),
            loaded=loaded_count,
            failed=failed_count,
            total_time=total_time,
        )

        return stats

    def _discover_modules(self) -> list[str]:
        """Discover available modules.

        Returns:
            List of module names
        """
        modules = []
        cogs_path = Path("src/cogs")

        if not cogs_path.exists():
            self.logger.warning("Cogs directory not found", path=str(cogs_path))
            return modules

        for module_dir in cogs_path.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue

            init_file = module_dir / "__init__.py"
            if init_file.exists():
                modules.append(module_dir.name)
                self.logger.debug("Discovered module", module=module_dir.name)

        # Sort by priority
        modules.sort(key=lambda m: self.module_config.get(m, {}).get("priority", 999))

        self.logger.info(
            "Module discovery completed", count=len(modules), modules=modules
        )
        return modules

    async def _load_modules_by_priority(
        self, modules: list[str]
    ) -> list[ModuleLoadResult]:
        """Load modules grouped by priority.

        Args:
            modules: List of module names

        Returns:
            List of load results
        """
        # Group by priority
        priority_groups: dict[int, list[str]] = {}
        for module in modules:
            config = self.module_config.get(module, {})
            priority = config.get("priority", 999)

            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(module)

        # Load by priority order
        all_results = []
        for priority in sorted(priority_groups.keys()):
            group_modules = priority_groups[priority]

            self.logger.info(
                "Loading module priority group",
                priority=priority,
                modules=group_modules,
            )

            # Load critical modules sequentially, others in parallel
            critical_modules = [
                m
                for m in group_modules
                if self.module_config.get(m, {}).get("critical", False)
            ]
            normal_modules = [
                m
                for m in group_modules
                if not self.module_config.get(m, {}).get("critical", False)
            ]

            # Load critical modules first (sequential)
            for module in critical_modules:
                result = await self._load_single_module(module)
                all_results.append(result)

                if not result.success:
                    self.logger.critical(
                        "Critical module failed to load",
                        module=module,
                        error=str(result.error),
                    )
                    # For critical modules, we might want to stop loading
                    # For now, we'll continue but log it as critical

            # Load normal modules in parallel
            if normal_modules:
                tasks = [
                    create_task_safe(
                        self._load_single_module(module), name=f"load_{module}"
                    )
                    for module in normal_modules
                ]

                results = await gather_safe(*tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        # Task failed
                        module_name = normal_modules[i]
                        self.logger.error(
                            f"Module {module_name} failed to load with exception: {type(result).__name__}: {result}",
                            exc_info=result
                        )
                        all_results.append(
                            ModuleLoadResult(
                                name=module_name,
                                success=False,
                                load_time=0.0,
                                error=result,
                            )
                        )
                    else:
                        all_results.append(result)

        return all_results

    async def _load_single_module(self, module_name: str) -> ModuleLoadResult:
        """Load a single module.

        Args:
            module_name: Name of module to load

        Returns:
            Load result
        """
        start_time = time.perf_counter()

        try:
            # Check if feature is enabled
            if not self.settings.is_feature_enabled(module_name):
                self.logger.info("Module disabled by feature flag", module=module_name)
                return ModuleLoadResult(
                    name=module_name,
                    success=False,
                    load_time=0.0,
                    error=ValueError(f"Module {module_name} disabled by feature flag"),
                )

            # Load the extension
            extension_path = f"src.cogs.{module_name}"
            await self.bot.load_extension(extension_path)

            load_time = time.perf_counter() - start_time

            self.logger.info(
                "Module loaded successfully",
                module=module_name,
                load_time=load_time,
            )

            return ModuleLoadResult(
                name=module_name,
                success=True,
                load_time=load_time,
            )

        except Exception as e:
            load_time = time.perf_counter() - start_time

            self.logger.error(
                "Module failed to load",
                module=module_name,
                load_time=load_time,
                error=str(e),
                exc_info=True,
            )

            return ModuleLoadResult(
                name=module_name,
                success=False,
                load_time=load_time,
                error=e,
            )


class ADRBot(commands.Bot):
    """Modern Discord ADR Bot with Python 3.12 features."""

    def __init__(self, settings: Settings | None = None):
        """Initialize the bot.

        Args:
            settings: Optional settings instance
        """
        # Get settings
        self.settings = settings or get_settings()

        # Set up logging first
        setup_logging(self.settings)
        setup_discord_logging()

        # Get logger
        self.logger = get_logger("bot", self.settings)

        # Set up dependency injection
        self.container = get_container()

        # 初始化事件匯流排(如果可用) - 必須在 _register_services 之前
        self.event_bus = None
        if EventBus and get_global_event_bus:
            try:
                # 非阻塞方式獲取事件匯流排
                import asyncio

                if asyncio.get_event_loop().is_running():
                    # 如果事件循環已經在運行,創建任務
                    asyncio.create_task(self._init_event_bus())
                else:
                    # 否則同步獲取
                    self.event_bus = EventBus()
            except Exception as e:
                self.logger.warning(f"無法初始化事件匯流排: {e}")

        # 初始化錯誤處理器(如果可用)
        self.error_handler = None
        if ErrorHandler and create_error_handler:
            try:
                self.error_handler = create_error_handler("bot", self.logger)
            except Exception as e:
                self.logger.warning(f"無法初始化錯誤處理器: {e}")

        # 現在註冊服務（在所有屬性初始化之後）
        self._register_services()

        # Set up Discord intents
        intents = self._setup_intents()

        # Initialize bot
        super().__init__(
            command_prefix=self.settings.command_prefix,
            intents=intents,
            help_command=None,  # We'll implement our own
        )

        # Initialize startup manager
        self.startup_manager = StartupManager(self, self.settings)

        # Bot state
        self.startup_time: float | None = None
        self.startup_stats: dict[str, Any] | None = None
        self.is_ready_event_fired = False

        self.logger.info("Bot initialized", version=self.settings.app_version)

    async def _init_event_bus(self) -> None:
        """異步初始化事件匯流排"""
        try:
            if get_global_event_bus:
                self.event_bus = await get_global_event_bus()
                self.logger.debug("事件匯流排已初始化")
        except Exception as e:
            self.logger.error(f"異步初始化事件匯流排失敗: {e}")

    def _register_services(self) -> None:
        """Register services in the DI container."""
        # Register bot instance
        self.container.register_singleton(ADRBot, self)

        # Register settings (already registered in container)
        # Register logger factory (already registered in container)

        # 註冊事件匯流排(如果可用)
        if self.event_bus and EventBus:
            self.container.register_singleton(EventBus, self.event_bus)

        # 註冊錯誤處理器(如果可用)
        if self.error_handler and ErrorHandler:
            self.container.register_singleton(ErrorHandler, self.error_handler)

        self.logger.debug("Services registered in DI container")

    def _setup_intents(self) -> discord.Intents:
        """Set up Discord intents.

        Returns:
            Configured intents
        """
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True

        self.logger.debug("Discord intents configured")
        return intents

    async def setup_hook(self) -> None:
        """Set up hook called when bot is starting."""
        self.logger.info("Running setup hook")

        # Record startup time
        self.startup_time = time.perf_counter()

        # Load extensions
        self.startup_stats = await self.startup_manager.discover_and_load_modules()

        # Register admin commands
        await self._register_admin_commands()

        # Sync commands in development
        if self.settings.is_development:
            try:
                synced = await self.tree.sync()
                self.logger.info("Commands synced", count=len(synced))
            except Exception as e:
                self.logger.error("Failed to sync commands", error=str(e))

        self.logger.info("Setup hook completed")

    async def _register_admin_commands(self) -> None:
        """Register admin-only commands."""

        @self.tree.command(name="sync", description="Sync slash commands (Admin only)")
        async def sync_command(interaction: discord.Interaction) -> None:
            """Sync slash commands."""
            # Check permissions
            if not await self._check_admin_permissions(interaction):
                return

            await interaction.response.defer(ephemeral=True)

            try:
                synced = await self.tree.sync()
                await interaction.followup.send(
                    f"✅ Successfully synced {len(synced)} commands!",
                    ephemeral=True,
                )
                self.logger.info(
                    "Commands manually synced",
                    user=str(interaction.user),
                    count=len(synced),
                )
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Failed to sync commands: {e}",
                    ephemeral=True,
                )
                self.logger.error(
                    "Manual command sync failed",
                    user=str(interaction.user),
                    error=str(e),
                )

        @self.tree.command(name="reload", description="Reload a module (Admin only)")
        async def reload_command(interaction: discord.Interaction, module: str) -> None:
            """Reload a module."""
            # Check permissions
            if not await self._check_admin_permissions(interaction):
                return

            await interaction.response.defer(ephemeral=True)

            try:
                extension_path = f"src.cogs.{module}"
                await self.reload_extension(extension_path)
                await interaction.followup.send(
                    f"✅ Successfully reloaded module: {module}",
                    ephemeral=True,
                )
                self.logger.info(
                    "Module manually reloaded",
                    user=str(interaction.user),
                    module=module,
                )
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Failed to reload module {module}: {e}",
                    ephemeral=True,
                )
                self.logger.error(
                    "Manual module reload failed",
                    user=str(interaction.user),
                    module=module,
                    error=str(e),
                )

        self.logger.debug("Admin commands registered")

    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions.

        Args:
            interaction: Discord interaction

        Returns:
            True if user has admin permissions
        """
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )
            return False

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need 'Manage Server' permission to use this command.",
                ephemeral=True,
            )
            return False

        return True

    async def on_ready(self) -> None:
        """Called when bot is ready."""
        try:
            if self.is_ready_event_fired:
                self.logger.debug("on_ready called again (reconnection)")
                return

            self.is_ready_event_fired = True

            if self.user is None:
                self.logger.error("Bot user is None in on_ready")
                return

            # Calculate startup time
            startup_duration = time.perf_counter() - (self.startup_time or 0)

            # Log bot ready
            self.logger.info(
                "Bot is ready!",
                bot_name=self.user.name,
                bot_id=self.user.id,
                guild_count=len(self.guilds),
                startup_time=startup_duration,
            )

            # Log startup stats
            if self.startup_stats:
                stats = self.startup_stats
                self.logger.info(
                    "Startup statistics",
                    total_modules=stats["total_modules"],
                    loaded_modules=stats["loaded_modules"],
                    failed_modules=stats["failed_modules"],
                    module_load_time=stats["total_time"],
                )

            # Log guild information
            if self.guilds:
                for guild in self.guilds:
                    self.logger.info(
                        "Connected to guild",
                        guild_name=guild.name,
                        guild_id=guild.id,
                        member_count=guild.member_count,
                    )
            else:
                self.logger.warning("Bot is not connected to any guilds")
        
        except Exception as e:
            self.logger.error(f"Error in on_ready: {type(e).__name__}: {e}", exc_info=True)

    async def on_message(self, message: discord.Message) -> None:
        """Handle message events.

        Args:
            message: Discord message
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Process commands
        await self.process_commands(message)

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Handle command errors.

        Args:
            ctx: Command context
            error: Command error
        """
        # 嘗試使用整合的錯誤處理器
        if self.error_handler:
            try:
                with self.error_handler.handle_error(
                    ctx, "命令執行發生錯誤", error_code=500, auto_classify=True
                ):
                    # 如果到達這裡,表示沒有拋出異常,正常處理
                    pass
                return
            except Exception:
                # 錯誤處理器處理了異常,直接返回
                return

        # 備用錯誤處理邏輯
        self.logger.error(
            "Command error occurred",
            command=ctx.command.name if ctx.command else "unknown",
            user=str(ctx.author),
            guild=str(ctx.guild) if ctx.guild else "DM",
            error=str(error),
            exc_info=True,
        )

        # Send user-friendly error message
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands

        error_message = "An error occurred while processing your command."

        if isinstance(error, commands.MissingPermissions):
            error_message = "You don't have permission to use this command."
        elif isinstance(error, commands.MissingRequiredArgument):
            error_message = f"Missing required argument: {error.param.name}"
        elif isinstance(error, commands.BadArgument):
            error_message = "Invalid argument provided."

        try:
            await ctx.send(f"❌ {error_message}")
        except discord.HTTPException:
            pass  # Ignore if we can't send the message

    async def close(self) -> None:
        """Close the bot and clean up resources."""
        self.logger.info("Bot is shutting down")

        # 關閉事件匯流排(如果存在)
        if self.event_bus and hasattr(self.event_bus, "shutdown"):
            try:
                await self.event_bus.shutdown()
                self.logger.debug("事件匯流排已關閉")
            except Exception as e:
                self.logger.error(f"關閉事件匯流排時發生錯誤: {e}")

        # Clear scoped services
        self.container.clear_scoped()

        # Close bot connection
        await super().close()

        self.logger.info("Bot shutdown completed")


async def create_and_run_bot(settings: Settings | None = None) -> None:
    """Create and run the bot.

    Args:
        settings: Optional settings instance
    """
    # Get settings
    if settings is None:
        settings = get_settings()

    # Validate token
    if not settings.token:
        print("❌ Discord bot token not found!")
        print("Please set TOKEN in your .env file or environment variables.")
        sys.exit(1)

    # Create bot
    bot = ADRBot(settings)

    try:
        # Run bot
        await bot.start(settings.token)
    except discord.LoginFailure:
        print("❌ Invalid Discord bot token!")
        print("Please check your token and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        sys.exit(1)
    finally:
        await bot.close()


__all__ = ["ADRBot", "ModuleLoadResult", "StartupManager", "create_and_run_bot"]
