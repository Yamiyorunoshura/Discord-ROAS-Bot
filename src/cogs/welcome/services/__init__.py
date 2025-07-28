"""
歡迎系統服務模組

提供依賴注入相關的服務註冊和管理功能
"""

from .service_registrar import WelcomeServiceRegistrar, register_welcome_services

__all__ = ["WelcomeServiceRegistrar", "register_welcome_services"]
