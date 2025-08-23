"""
Achievement Panel for the new architecture
Task ID: T2 - App architecture baseline and scaffolding

This module provides the user interface layer for achievement interactions.
It handles Discord commands, interactions, and displays for the achievement system.
"""

from typing import Optional, Dict, Any, List
import discord
from discord.ext import commands
import asyncio

from src.services.achievement_service import AchievementService


class AchievementPanel:
    """
    Achievement panel for handling user interactions
    
    Provides user interface functionality for:
    - Displaying user achievements
    - Handling achievement-related commands
    - Managing achievement interactions and feedback
    """
    
    def __init__(self, achievement_service: AchievementService):
        """
        Initialize the achievement panel
        
        Args:
            achievement_service: Achievement service instance
        """
        self.panel_name = "AchievementPanel"
        self.achievement_service = achievement_service
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the panel and its dependencies"""
        if self._initialized:
            return
            
        # Ensure the achievement service is initialized
        if not self.achievement_service.is_initialized():
            await self.achievement_service.initialize()
            
        self._initialized = True
        
    async def shutdown(self) -> None:
        """Cleanup panel resources"""
        self._initialized = False
        
    async def show_user_achievements(self, user_id: int, guild_id: int, ctx: Optional[commands.Context] = None) -> Dict[str, Any]:
        """
        Display user achievements
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            ctx: Optional command context for Discord integration
            
        Returns:
            Achievement display data
        """
        if not self._initialized:
            raise RuntimeError("Panel not initialized")
            
        try:
            achievements = await self.achievement_service.list_user_achievements(user_id, guild_id)
            
            display_data = {
                "user_id": user_id,
                "guild_id": guild_id,
                "achievement_count": len(achievements),
                "achievements": achievements,
                "display_format": "embed" if ctx else "json"
            }
            
            # If we have a Discord context, format as an embed
            if ctx:
                embed = discord.Embed(
                    title=f"🏆 Achievements for {ctx.author.display_name}",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                
                if achievements:
                    for achievement in achievements[:10]:  # Limit to first 10
                        embed.add_field(
                            name=achievement.get('name', 'Unknown Achievement'),
                            value=achievement.get('description', 'No description available'),
                            inline=False
                        )
                    
                    if len(achievements) > 10:
                        embed.add_field(
                            name="...",
                            value=f"And {len(achievements) - 10} more achievements",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="No Achievements Yet",
                        value="Keep participating to earn your first achievement!",
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                
            return display_data
            
        except Exception as e:
            error_data = {
                "error": str(e),
                "user_id": user_id,
                "guild_id": guild_id
            }
            
            if ctx:
                await ctx.send("❌ Error retrieving achievements. Please try again later.")
                
            return error_data
            
    async def handle_interaction(self, interaction: discord.Interaction) -> bool:
        """
        Handle Discord interactions for achievements
        
        Args:
            interaction: Discord interaction object
            
        Returns:
            True if interaction was handled successfully
        """
        if not self._initialized:
            raise RuntimeError("Panel not initialized")
            
        try:
            # Handle different interaction types
            if interaction.type == discord.InteractionType.application_command:
                if interaction.data.get('name') == 'achievements':
                    await self.show_user_achievements(
                        interaction.user.id, 
                        interaction.guild_id,
                        None  # No context for interactions
                    )
                    await interaction.response.send_message("✅ Achievement list displayed!", ephemeral=True)
                    return True
                    
            elif interaction.type == discord.InteractionType.component:
                # Handle button/select menu interactions
                custom_id = interaction.data.get('custom_id', '')
                if custom_id.startswith('achievement_'):
                    await interaction.response.send_message("🏆 Achievement interaction handled!", ephemeral=True)
                    return True
                    
            return False
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error handling interaction: {str(e)}", ephemeral=True)
            return False
            
    def is_initialized(self) -> bool:
        """Check if panel is initialized"""
        return self._initialized