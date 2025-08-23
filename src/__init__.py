"""
New Architecture for roas-bot
Task ID: T2

This package provides the new layered architecture for the roas-bot application:

- app/: Application layer with bootstrapping and dependency injection
- core/: Core infrastructure (errors, config, logging)
- services/: Business logic services layer
- panels/: Presentation layer for user interactions

The architecture follows clean architecture principles with clear separation of concerns.
"""

# 延遲導入避免循環依賴
# 這些模組只在實際需要時才導入，不在包初始化時導入
def get_application_bootstrap():
    """延遲導入ApplicationBootstrap以避免循環依賴"""
    from .app import ApplicationBootstrap
    return ApplicationBootstrap

def get_core_utilities():
    """延遲導入核心工具"""
    from .core import get_logger, get_config, AppError
    return get_logger, get_config, AppError

def get_services():
    """延遲導入服務層"""
    from .services import (
        AchievementService,
        ActivityMeterService, 
        EconomyService,
        GovernmentService,
        TestOrchestratorService
    )
    return AchievementService, ActivityMeterService, EconomyService, GovernmentService, TestOrchestratorService

def get_panels():
    """延遲導入面板"""
    from .panels import AchievementPanel, TerminalPanel
    return AchievementPanel, TerminalPanel

# 為了向後兼容性，提供核心錯誤類型
from .core.errors import AppError

__version__ = "2.4.1"

__all__ = [
    # 延遲導入函數
    'get_application_bootstrap',
    'get_core_utilities',
    'get_services',
    'get_panels',
    
    # 核心錯誤類型（直接可用）
    'AppError',
]