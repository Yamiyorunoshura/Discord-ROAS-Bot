"""
Government Service Adapter for T2 Architecture Integration
Task ID: T2 - App architecture baseline and scaffolding

This module provides a corrected adapter for the existing government service,
fixing the architectural mismatch identified in Dr. Thompson's review.

ARCHITECTURE FIX: This adapter properly handles role management integration
and maps new architecture methods to existing role service capabilities.
"""

from typing import Optional, List
import asyncio

# Import from existing services with correct understanding  
from services.government.government_service import GovernmentService as LegacyGovernmentService
from services.government.role_service import RoleService as LegacyRoleService


class GovernmentService:
    """
    Government service adapter for the new architecture
    
    CORRECTED DESIGN: This adapter properly handles Discord integration
    and maps new architecture methods to existing government/role services.
    
    Provides government and role management functionality including:
    - Role assignment and removal (with proper Discord integration)
    - Permission management
    - Government structure management
    """
    
    def __init__(self):
        """Initialize the government service adapter"""
        self.service_name = "GovernmentService"
        self._legacy_government_service: Optional[LegacyGovernmentService] = None
        self._legacy_role_service: Optional[LegacyRoleService] = None
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the service and its dependencies"""
        if self._initialized:
            return
            
        # CORRECTED: Use the actual initialization method from legacy services
        self._legacy_government_service = LegacyGovernmentService()
        self._legacy_role_service = LegacyRoleService()
        
        # Call the real methods: _initialize() not initialize()
        gov_result = await self._legacy_government_service._initialize()
        role_result = await self._legacy_role_service._initialize()
        
        if not gov_result or not role_result:
            raise RuntimeError("Failed to initialize legacy government/role services")
        
        self._initialized = True
        
    async def shutdown(self) -> None:
        """Cleanup service resources"""
        if self._legacy_government_service:
            # CORRECTED: Use the actual cleanup method from legacy service
            await self._legacy_government_service._cleanup()
        if self._legacy_role_service:
            # CORRECTED: Use the actual cleanup method from legacy service
            await self._legacy_role_service._cleanup()
        self._initialized = False
        
    async def assign_role(self, user_id: int, guild_id: int, role_name: str) -> bool:
        """
        Assign a role to a user
        
        ARCHITECTURE FIX: This method now properly integrates with Discord
        to get guild and member objects required by the existing role service.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            role_name: Name of the role to assign
            
        Returns:
            True if role was assigned successfully
        """
        if not self._initialized or not self._legacy_role_service:
            raise RuntimeError("Service not initialized")
        
        try:
            # CORRECTED: Get Discord client to access guild and member objects
            discord_client = self._legacy_role_service.get_dependency("discord_client")
            if not discord_client:
                print("Discord client not available")
                return False
            
            guild = discord_client.get_guild(guild_id)
            if not guild:
                print(f"Guild {guild_id} not found")
                return False
            
            member = guild.get_member(user_id)
            if not member:
                print(f"Member {user_id} not found in guild {guild_id}")
                return False
            
            # Get or create the role
            role = await self._legacy_role_service.get_role_by_name(guild, role_name)
            if not role:
                # Try to create the role if it doesn't exist
                role_data = {"name": role_name}
                role = await self._legacy_role_service.create_role_if_not_exists(guild, role_data)
            
            if not role:
                print(f"Could not find or create role {role_name}")
                return False
            
            # CORRECTED: Use the existing method with proper parameters
            await self._legacy_role_service.assign_role_to_user(
                guild=guild,
                member=member, 
                role=role,
                reason=f"Role assignment via new architecture"
            )
            
            return True
            
        except Exception as e:
            print(f"Error assigning role: {e}")
            return False
        
    async def remove_role(self, user_id: int, guild_id: int, role_name: str) -> bool:
        """
        Remove a role from a user
        
        ARCHITECTURE FIX: This method now properly integrates with Discord
        to get guild and member objects required by the existing role service.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            role_name: Name of the role to remove
            
        Returns:
            True if role was removed successfully
        """
        if not self._initialized or not self._legacy_role_service:
            raise RuntimeError("Service not initialized")
        
        try:
            # CORRECTED: Get Discord client to access guild and member objects
            discord_client = self._legacy_role_service.get_dependency("discord_client")
            if not discord_client:
                print("Discord client not available")
                return False
            
            guild = discord_client.get_guild(guild_id)
            if not guild:
                print(f"Guild {guild_id} not found")
                return False
            
            member = guild.get_member(user_id)
            if not member:
                print(f"Member {user_id} not found in guild {guild_id}")
                return False
            
            role = await self._legacy_role_service.get_role_by_name(guild, role_name)
            if not role:
                print(f"Role {role_name} not found")
                return False
            
            # CORRECTED: Use the existing method with proper parameters
            await self._legacy_role_service.remove_role_from_user(
                guild=guild,
                member=member,
                role=role,
                reason=f"Role removal via new architecture"
            )
            
            return True
            
        except Exception as e:
            print(f"Error removing role: {e}")
            return False
        
    async def get_user_roles(self, user_id: int, guild_id: int) -> List[str]:
        """
        Get all roles for a user
        
        ARCHITECTURE FIX: This method now properly integrates with Discord
        to get user roles directly from the member object.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            List of role names
        """
        if not self._initialized or not self._legacy_role_service:
            raise RuntimeError("Service not initialized")
        
        try:
            # CORRECTED: Get Discord client to access guild and member objects
            discord_client = self._legacy_role_service.get_dependency("discord_client")
            if not discord_client:
                print("Discord client not available")
                return []
            
            guild = discord_client.get_guild(guild_id)
            if not guild:
                print(f"Guild {guild_id} not found")
                return []
            
            member = guild.get_member(user_id)
            if not member:
                print(f"Member {user_id} not found in guild {guild_id}")
                return []
            
            # Return role names (excluding @everyone)
            role_names = [role.name for role in member.roles if role.name != "@everyone"]
            return role_names
            
        except Exception as e:
            print(f"Error getting user roles: {e}")
            return []
        
    def is_initialized(self) -> bool:
        """Check if service is initialized"""
        return self._initialized