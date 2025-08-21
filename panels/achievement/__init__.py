"""
成就面板模組
Task ID: 7 - 實作成就系統使用者介面

這個模組提供成就系統的完整使用者介面，包括：
- 使用者成就查看和進度追蹤
- 管理員成就管理和統計分析
- Discord斜線指令整合
- 完整的錯誤處理和權限控制

符合要求：
- F1: 成就面板基礎結構
- F2: 使用者成就面板功能
- F3: 管理員成就面板功能
- N1-N3: 效能、可用性和穩定性要求
"""

from .achievement_panel import AchievementPanel

__all__ = ["AchievementPanel"]