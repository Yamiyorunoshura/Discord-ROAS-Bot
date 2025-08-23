"""
Economy Service Adapter for T2 Architecture Integration
Task ID: T2 - App architecture baseline and scaffolding

This module provides a corrected adapter for the existing economy service,
fixing the architectural mismatch identified in Dr. Thompson's review.

ARCHITECTURE FIX: This adapter properly handles account ID generation 
and maps new architecture methods to existing system capabilities.
"""

from typing import Optional
from decimal import Decimal
import asyncio

# Import from existing services with correct understanding
from services.economy.economy_service import EconomyService as LegacyEconomyService
from services.economy.models import AccountType


class EconomyService:
    """
    Economy service adapter for the new architecture
    
    CORRECTED DESIGN: This adapter properly handles account management
    and maps new architecture methods to existing account-based operations.
    
    Provides economic system functionality including:
    - User balance management (with proper account mapping)
    - Transaction processing  
    - Economic rewards integration
    """
    
    def __init__(self):
        """Initialize the economy service adapter"""
        self.service_name = "EconomyService"
        self._legacy_service: Optional[LegacyEconomyService] = None
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the service and its dependencies"""
        if self._initialized:
            return
            
        # CORRECTED: Use the actual initialization method from legacy service
        self._legacy_service = LegacyEconomyService()
        # Call the real method: _initialize() not initialize()
        initialization_result = await self._legacy_service._initialize()
        
        if not initialization_result:
            raise RuntimeError("Failed to initialize legacy economy service")
        
        self._initialized = True
        
    async def shutdown(self) -> None:
        """Cleanup service resources"""
        if self._legacy_service:
            # CORRECTED: Use the actual cleanup method from legacy service
            await self._legacy_service._cleanup()
        self._initialized = False
        
    def _get_user_account_id(self, user_id: int, guild_id: int) -> str:
        """
        Generate account ID for user
        
        ARCHITECTURE FIX: The existing system requires account IDs,
        not user_id/guild_id pairs directly.
        """
        return f"user_{user_id}_{guild_id}"
        
    async def _ensure_user_account(self, user_id: int, guild_id: int) -> str:
        """
        Ensure user account exists and return account ID
        
        ARCHITECTURE FIX: The existing system requires accounts to be created
        before they can be used for balance operations.
        """
        account_id = self._get_user_account_id(user_id, guild_id)
        
        try:
            # Check if account exists
            account = await self._legacy_service.get_account(account_id)
            if account:
                return account_id
                
        except Exception:
            # Account doesn't exist, create it
            pass
        
        # Create new account
        try:
            await self._legacy_service.create_account(
                guild_id=guild_id,
                account_type=AccountType.USER,
                user_id=user_id,
                initial_balance=0.0
            )
            return account_id
        except Exception as e:
            # Account might already exist (race condition)
            if "已存在" in str(e) or "already exists" in str(e):
                return account_id
            raise
        
    async def get_balance(self, user_id: int, guild_id: int) -> Decimal:
        """
        Get user's current balance
        
        ARCHITECTURE FIX: This method now properly converts user_id/guild_id
        to account_id and uses the existing get_balance(account_id) method.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            User's current balance
        """
        if not self._initialized or not self._legacy_service:
            raise RuntimeError("Service not initialized")
        
        try:
            account_id = await self._ensure_user_account(user_id, guild_id)
            balance = await self._legacy_service.get_balance(account_id)
            return Decimal(str(balance))
        except Exception as e:
            print(f"Error getting balance: {e}")
            return Decimal('0')
        
    async def adjust_balance(self, user_id: int, guild_id: int, amount: Decimal, reason: str = "") -> Decimal:
        """
        Adjust user's balance by the specified amount
        
        ARCHITECTURE FIX: This method now properly uses the existing system's
        deposit() and withdraw() methods instead of the non-existent adjust_balance().
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            amount: Amount to adjust (positive for credit, negative for debit)
            reason: Reason for the adjustment
            
        Returns:
            New balance after adjustment
        """
        if not self._initialized or not self._legacy_service:
            raise RuntimeError("Service not initialized")
        
        try:
            account_id = await self._ensure_user_account(user_id, guild_id)
            amount_float = float(amount)
            
            if amount_float > 0:
                # CORRECTED: Use deposit() for positive amounts
                await self._legacy_service.deposit(
                    account_id=account_id,
                    amount=amount_float,
                    reason=reason or "Balance adjustment",
                    created_by=user_id
                )
            elif amount_float < 0:
                # CORRECTED: Use withdraw() for negative amounts
                await self._legacy_service.withdraw(
                    account_id=account_id,
                    amount=abs(amount_float),
                    reason=reason or "Balance adjustment",
                    created_by=user_id
                )
            
            # Get the new balance
            new_balance = await self._legacy_service.get_balance(account_id)
            return Decimal(str(new_balance))
            
        except Exception as e:
            print(f"Error adjusting balance: {e}")
            # Return current balance if adjustment failed
            try:
                account_id = self._get_user_account_id(user_id, guild_id)
                current_balance = await self._legacy_service.get_balance(account_id)
                return Decimal(str(current_balance))
            except:
                return Decimal('0')
        
    async def transfer_balance(self, from_user_id: int, to_user_id: int, guild_id: int, amount: Decimal) -> bool:
        """
        Transfer balance between users
        
        ARCHITECTURE FIX: This method now properly uses the existing system's
        transfer() method with correct account ID mapping.
        
        Args:
            from_user_id: Source user ID
            to_user_id: Destination user ID  
            guild_id: Discord guild ID
            amount: Amount to transfer
            
        Returns:
            True if transfer was successful
        """
        if not self._initialized or not self._legacy_service:
            raise RuntimeError("Service not initialized")
        
        try:
            # Ensure both accounts exist
            from_account_id = await self._ensure_user_account(from_user_id, guild_id)
            to_account_id = await self._ensure_user_account(to_user_id, guild_id)
            
            # CORRECTED: Use the existing transfer() method with account IDs
            await self._legacy_service.transfer(
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount=float(amount),
                reason="User transfer",
                created_by=from_user_id
            )
            
            return True
            
        except Exception as e:
            print(f"Error transferring balance: {e}")
            return False
        
    def is_initialized(self) -> bool:
        """Check if service is initialized"""
        return self._initialized