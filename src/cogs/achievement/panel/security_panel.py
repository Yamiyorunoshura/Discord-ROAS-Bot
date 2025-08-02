"""成就系統安全管理面板擴展.

此模組提供成就系統的安全管理功能，包含：
- 審計日誌查詢和分析
- 安全權限管理
- 操作歷史追蹤
- 安全事件監控

整合到主管理面板中，提供完整的安全管理能力。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

from ..services.audit_logger import (
    AuditContext,
    AuditEventType,
    AuditLogger,
    AuditQuery,
    AuditSeverity,
)
from ..services.history_manager import (
    HistoryManager,
    HistoryQuery,
)
from ..services.security_validator import (
    PermissionLevel,
    SecurityChallenge,
    SecurityValidator,
)
from .admin_panel import AdminPanel, AdminPanelState

logger = logging.getLogger(__name__)


class SecurityPanelState(Enum):
    """安全管理面板狀態."""
    # 繼承基本狀態
    INITIALIZING = "initializing"
    OVERVIEW = "overview"
    ACHIEVEMENTS = "achievements"
    USERS = "users"
    SETTINGS = "settings"
    ERROR = "error"
    CLOSED = "closed"

    # 擴展安全相關狀態
    SECURITY_OVERVIEW = "security_overview"
    AUDIT_LOGS = "audit_logs"
    OPERATION_HISTORY = "operation_history"
    SECURITY_SETTINGS = "security_settings"
    PERMISSION_MANAGEMENT = "permission_management"


class SecurityPanelMixin:
    """安全管理面板混入類.

    為 AdminPanel 添加安全管理功能。
    """

    def __init__(self, *args, **kwargs):
        """初始化安全管理功能."""
        super().__init__(*args, **kwargs)

        # 安全服務初始化
        self.audit_logger: AuditLogger | None = None
        self.security_validator: SecurityValidator | None = None
        self.history_manager: HistoryManager | None = None

        # 安全狀態追蹤
        self._pending_approvals: dict[str, Any] = {}
        self._active_challenges: dict[str, SecurityChallenge] = {}

    async def initialize_security_services(self):
        """初始化安全服務."""
        try:
            # 初始化審計日誌記錄器
            self.audit_logger = AuditLogger(
                database_service=getattr(self, 'database_service', None),
                cache_service=getattr(self, 'cache_service', None)
            )

            # 初始化安全驗證器
            self.security_validator = SecurityValidator(
                audit_logger=self.audit_logger
            )

            # 初始化歷史管理器
            self.history_manager = HistoryManager(
                database_service=getattr(self, 'database_service', None),
                cache_service=getattr(self, 'cache_service', None)
            )

            # 為管理員授予基本權限
            await self.security_validator.grant_permission(
                user_id=self.admin_user_id,
                permission_level=PermissionLevel.ADMIN,
                granted_by=self.admin_user_id,  # 自我授權
                expires_in_hours=24
            )

            logger.info(f"【安全管理】為用戶 {self.admin_user_id} 初始化安全服務")

        except Exception as e:
            logger.error(f"【安全管理】初始化安全服務失敗: {e}")


class SecureAdminPanel(SecurityPanelMixin, AdminPanel):
    """整合安全功能的管理面板."""

    async def start(self, interaction: discord.Interaction) -> None:
        """啟動安全管理面板."""
        # 初始化安全服務
        await self.initialize_security_services()

        # 記錄管理員登錄
        if self.audit_logger:
            await self.audit_logger.log_event(
                event_type=AuditEventType.ADMIN_LOGIN,
                context=AuditContext(
                    user_id=self.admin_user_id,
                    guild_id=self.guild_id,
                    interaction_id=str(interaction.id)
                ),
                operation_name="admin_panel_login",
                severity=AuditSeverity.INFO,
                metadata={
                    "session_start": datetime.utcnow().isoformat(),
                    "user_agent": getattr(interaction, 'user_agent', 'Unknown'),
                    "panel_version": "2.0"
                }
            )

        # 調用父類的啟動方法
        await super().start(interaction)

    async def _create_state_content(self, target_state: AdminPanelState):
        """創建狀態相關的內容，包含安全功能."""
        if target_state == SecurityPanelState.SECURITY_OVERVIEW:
            return await self._create_security_overview()
        elif target_state == SecurityPanelState.AUDIT_LOGS:
            return await self._create_audit_logs_view()
        elif target_state == SecurityPanelState.OPERATION_HISTORY:
            return await self._create_operation_history_view()
        elif target_state == SecurityPanelState.SECURITY_SETTINGS:
            return await self._create_security_settings_view()
        elif target_state == SecurityPanelState.PERMISSION_MANAGEMENT:
            return await self._create_permission_management_view()
        else:
            # 調用父類方法處理其他狀態
            return await super()._create_state_content(target_state)

    async def _create_security_overview(self):
        """創建安全概覽視圖."""
        try:
            # 獲取安全統計
            security_stats = {}
            if self.audit_logger:
                security_stats.update(await self.audit_logger.get_audit_statistics())
            if self.security_validator:
                security_stats.update(await self.security_validator.get_security_statistics())
            if self.history_manager:
                security_stats.update(await self.history_manager.get_history_statistics())

            # 創建概覽 embed
            embed = StandardEmbedBuilder.create_info_embed(
                "🔒 安全管理概覽",
                "系統安全狀態和統計資訊"
            )

            # 審計日誌統計
            embed.add_field(
                name="📋 審計日誌",
                value=(
                    f"• 已記錄事件: {security_stats.get('events_logged', 0)}\n"
                    f"• 查詢次數: {security_stats.get('events_queried', 0)}\n"
                    f"• 安全違規: {security_stats.get('security_violations', 0)}\n"
                    f"• 生成報告: {security_stats.get('reports_generated', 0)}"
                ),
                inline=True
            )

            # 權限管理統計
            embed.add_field(
                name="🛡️ 權限管理",
                value=(
                    f"• 權限檢查: {security_stats.get('permission_checks', 0)}\n"
                    f"• 活動令牌: {security_stats.get('active_tokens', 0)}\n"
                    f"• 待審批操作: {security_stats.get('pending_approvals', 0)}\n"
                    f"• 安全挑戰: {security_stats.get('active_challenges', 0)}"
                ),
                inline=True
            )

            # 操作歷史統計
            embed.add_field(
                name="📊 操作歷史",
                value=(
                    f"• 已記錄操作: {security_stats.get('records_created', 0)}\n"
                    f"• 歷史查詢: {security_stats.get('queries_executed', 0)}\n"
                    f"• 分析報告: {security_stats.get('analyses_generated', 0)}\n"
                    f"• 資料導出: {security_stats.get('export_operations', 0)}"
                ),
                inline=True
            )

            # 添加最近的安全事件
            if self.audit_logger:
                recent_events = await self.audit_logger.query_events(
                    AuditQuery(
                        risk_levels=["high", "critical"],
                        limit=3,
                        sort_order="desc"
                    )
                )

                if recent_events:
                    event_text = ""
                    for event in recent_events:
                        event_text += f"• {event.event_type.value} - {event.timestamp.strftime('%H:%M')}\n"

                    embed.add_field(
                        name="⚠️ 最近高風險事件",
                        value=event_text or "無",
                        inline=False
                    )

            embed.set_footer(text=f"會話開始時間: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

            # 創建安全管理視圖
            view = SecurityOverviewView(self)

            return embed, view

        except Exception as e:
            logger.error(f"【安全管理】創建安全概覽失敗: {e}")
            return await self._create_error_embed("創建安全概覽失敗", str(e))

    async def _create_audit_logs_view(self):
        """創建審計日誌視圖."""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "📋 審計日誌管理",
                "查詢和分析系統審計日誌"
            )

            embed.add_field(
                name="可用功能",
                value=(
                    "• 🔍 查詢審計事件\n"
                    "• 📊 生成審計報告\n"
                    "• ⚠️ 安全事件分析\n"
                    "• 📤 導出日誌資料"
                ),
                inline=True
            )

            embed.add_field(
                name="查詢選項",
                value=(
                    "• 按時間範圍篩選\n"
                    "• 按事件類型篩選\n"
                    "• 按風險等級篩選\n"
                    "• 按用戶ID篩選"
                ),
                inline=True
            )

            view = AuditLogsView(self)
            return embed, view

        except Exception as e:
            logger.error(f"【安全管理】創建審計日誌視圖失敗: {e}")
            return await self._create_error_embed("創建審計日誌視圖失敗", str(e))

    async def _create_operation_history_view(self):
        """創建操作歷史視圖."""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "📊 操作歷史管理",
                "查詢和分析系統操作歷史"
            )

            embed.add_field(
                name="歷史追蹤",
                value=(
                    "• 📝 所有管理操作記錄\n"
                    "• 🎯 詳細的操作資料變更\n"
                    "• 👤 執行者資訊追蹤\n"
                    "• ⏰ 完整的時間軸記錄"
                ),
                inline=True
            )

            embed.add_field(
                name="分析功能",
                value=(
                    "• 📈 操作趨勢分析\n"
                    "• 🔍 異常模式檢測\n"
                    "• 📊 用戶活動統計\n"
                    "• 🚨 風險操作監控"
                ),
                inline=True
            )

            view = OperationHistoryView(self)
            return embed, view

        except Exception as e:
            logger.error(f"【安全管理】創建操作歷史視圖失敗: {e}")
            return await self._create_error_embed("創建操作歷史視圖失敗", str(e))


class SecurityOverviewView(ui.View):
    """安全概覽視圖."""

    def __init__(self, admin_panel: SecureAdminPanel):
        super().__init__(timeout=900)  # 15分鐘超時
        self.admin_panel = admin_panel

    @ui.button(label="審計日誌", emoji="📋", style=discord.ButtonStyle.primary)
    async def audit_logs_button(self, interaction: discord.Interaction, button: ui.Button):
        """審計日誌按鈕."""
        await self.admin_panel.handle_navigation(
            interaction, SecurityPanelState.AUDIT_LOGS
        )

    @ui.button(label="操作歷史", emoji="📊", style=discord.ButtonStyle.primary)
    async def operation_history_button(self, interaction: discord.Interaction, button: ui.Button):
        """操作歷史按鈕."""
        await self.admin_panel.handle_navigation(
            interaction, SecurityPanelState.OPERATION_HISTORY
        )

    @ui.button(label="權限管理", emoji="🛡️", style=discord.ButtonStyle.secondary)
    async def permission_management_button(self, interaction: discord.Interaction, button: ui.Button):
        """權限管理按鈕."""
        await self.admin_panel.handle_navigation(
            interaction, SecurityPanelState.PERMISSION_MANAGEMENT
        )

    @ui.button(label="安全設定", emoji="⚙️", style=discord.ButtonStyle.secondary)
    async def security_settings_button(self, interaction: discord.Interaction, button: ui.Button):
        """安全設定按鈕."""
        await self.admin_panel.handle_navigation(
            interaction, SecurityPanelState.SECURITY_SETTINGS
        )

    @ui.button(label="返回主面板", emoji="🏠", style=discord.ButtonStyle.success, row=1)
    async def back_to_main_button(self, interaction: discord.Interaction, button: ui.Button):
        """返回主面板按鈕."""
        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.OVERVIEW
        )


class AuditLogsView(ui.View):
    """審計日誌視圖."""

    def __init__(self, admin_panel: SecureAdminPanel):
        super().__init__(timeout=900)
        self.admin_panel = admin_panel

    @ui.button(label="查詢最近事件", emoji="🔍", style=discord.ButtonStyle.primary)
    async def query_recent_events(self, interaction: discord.Interaction, button: ui.Button):
        """查詢最近事件."""
        try:
            await interaction.response.defer(ephemeral=True)

            if not self.admin_panel.audit_logger:
                await interaction.followup.send("❌ 審計日誌服務未初始化", ephemeral=True)
                return

            # 查詢最近24小時的事件
            query = AuditQuery(
                start_time=datetime.utcnow() - timedelta(hours=24),
                limit=20,
                sort_order="desc"
            )

            events = await self.admin_panel.audit_logger.query_events(query)

            if not events:
                await interaction.followup.send("📭 最近24小時內沒有審計事件", ephemeral=True)
                return

            # 創建事件列表 embed
            embed = StandardEmbedBuilder.create_info_embed(
                "🔍 最近審計事件",
                f"顯示最近24小時內的 {len(events)} 個事件"
            )

            event_text = ""
            for event in events[:10]:  # 只顯示前10個
                time_str = event.timestamp.strftime("%H:%M")
                event_text += (
                    f"**{time_str}** `{event.event_type.value}`\n"
                    f"執行者: <@{event.context.user_id if event.context else 'Unknown'}>\n"
                    f"風險: {event.risk_level} | 成功: {'✅' if event.success else '❌'}\n\n"
                )

            embed.description = event_text

            if len(events) > 10:
                embed.set_footer(text=f"還有 {len(events) - 10} 個事件未顯示")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【審計日誌】查詢最近事件失敗: {e}")
            await interaction.followup.send("❌ 查詢審計事件時發生錯誤", ephemeral=True)

    @ui.button(label="高風險事件", emoji="⚠️", style=discord.ButtonStyle.danger)
    async def query_high_risk_events(self, interaction: discord.Interaction, button: ui.Button):
        """查詢高風險事件."""
        try:
            await interaction.response.defer(ephemeral=True)

            if not self.admin_panel.audit_logger:
                await interaction.followup.send("❌ 審計日誌服務未初始化", ephemeral=True)
                return

            # 查詢高風險事件
            query = AuditQuery(
                risk_levels=["high", "critical"],
                start_time=datetime.utcnow() - timedelta(days=7),
                limit=15,
                sort_order="desc"
            )

            events = await self.admin_panel.audit_logger.query_events(query)

            if not events:
                await interaction.followup.send("✅ 最近7天內無高風險事件", ephemeral=True)
                return

            # 創建高風險事件 embed
            embed = StandardEmbedBuilder.create_warning_embed(
                "⚠️ 高風險審計事件",
                f"最近7天內發現 {len(events)} 個高風險事件"
            )

            event_text = ""
            for event in events[:8]:  # 只顯示前8個
                date_str = event.timestamp.strftime("%m-%d %H:%M")
                risk_emoji = "🔴" if event.risk_level == "critical" else "🟠"
                event_text += (
                    f"{risk_emoji} **{date_str}** `{event.event_type.value}`\n"
                    f"執行者: <@{event.context.user_id if event.context else 'Unknown'}>\n"
                    f"操作: {event.operation_name}\n\n"
                )

            embed.description = event_text

            if len(events) > 8:
                embed.set_footer(text=f"還有 {len(events) - 8} 個高風險事件")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【審計日誌】查詢高風險事件失敗: {e}")
            await interaction.followup.send("❌ 查詢高風險事件時發生錯誤", ephemeral=True)

    @ui.button(label="生成報告", emoji="📊", style=discord.ButtonStyle.secondary)
    async def generate_audit_report(self, interaction: discord.Interaction, button: ui.Button):
        """生成審計報告."""
        try:
            await interaction.response.defer(ephemeral=True)

            if not self.admin_panel.audit_logger:
                await interaction.followup.send("❌ 審計日誌服務未初始化", ephemeral=True)
                return

            # 生成最近7天的審計報告
            query = AuditQuery(
                start_time=datetime.utcnow() - timedelta(days=7),
                include_statistics=True
            )

            report = await self.admin_panel.audit_logger.generate_report(
                report_type="weekly_security_report",
                query=query,
                generated_by=self.admin_panel.admin_user_id
            )

            # 創建報告 embed
            embed = StandardEmbedBuilder.create_info_embed(
                "📊 審計報告",
                "最近7天的系統審計報告"
            )

            embed.add_field(
                name="📈 基本統計",
                value=(
                    f"• 總事件數: {report.total_events}\n"
                    f"• 成功率: {(report.total_events - len([e for e in report.events if not e.success]) / report.total_events * 100):.1f}%\n"
                    f"• 安全問題: {len(report.security_issues)}\n"
                    f"• 生成時間: {report.duration_ms:.0f}ms"
                ),
                inline=True
            )

            if report.events_by_type:
                type_stats = "\n".join([
                    f"• {type_name}: {count}"
                    for type_name, count in sorted(report.events_by_type.items(),
                                                 key=lambda x: x[1], reverse=True)[:5]
                ])
                embed.add_field(
                    name="🔍 主要事件類型",
                    value=type_stats,
                    inline=True
                )

            if report.security_issues:
                issues_text = ""
                for issue in report.security_issues[:3]:
                    issues_text += f"• {issue.get('description', 'Unknown issue')}\n"

                embed.add_field(
                    name="⚠️ 安全問題",
                    value=issues_text,
                    inline=False
                )

            embed.set_footer(text=f"報告ID: {report.report_id}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【審計日誌】生成報告失敗: {e}")
            await interaction.followup.send("❌ 生成審計報告時發生錯誤", ephemeral=True)

    @ui.button(label="返回安全面板", emoji="🔒", style=discord.ButtonStyle.success, row=1)
    async def back_to_security_button(self, interaction: discord.Interaction, button: ui.Button):
        """返回安全面板按鈕."""
        await self.admin_panel.handle_navigation(
            interaction, SecurityPanelState.SECURITY_OVERVIEW
        )


class OperationHistoryView(ui.View):
    """操作歷史視圖."""

    def __init__(self, admin_panel: SecureAdminPanel):
        super().__init__(timeout=900)
        self.admin_panel = admin_panel

    @ui.button(label="最近操作", emoji="📝", style=discord.ButtonStyle.primary)
    async def recent_operations(self, interaction: discord.Interaction, button: ui.Button):
        """查詢最近操作."""
        try:
            await interaction.response.defer(ephemeral=True)

            if not self.admin_panel.history_manager:
                await interaction.followup.send("❌ 歷史管理服務未初始化", ephemeral=True)
                return

            # 查詢最近的操作
            query = HistoryQuery(
                start_time=datetime.utcnow() - timedelta(hours=24),
                limit=15,
                sort_order="desc"
            )

            records = await self.admin_panel.history_manager.query_history(query)

            if not records:
                await interaction.followup.send("📭 最近24小時內沒有操作記錄", ephemeral=True)
                return

            # 創建操作歷史 embed
            embed = StandardEmbedBuilder.create_info_embed(
                "📝 最近操作記錄",
                f"最近24小時內的 {len(records)} 個操作"
            )

            record_text = ""
            for record in records[:10]:
                time_str = record.timestamp.strftime("%H:%M")
                success_emoji = "✅" if record.success else "❌"
                record_text += (
                    f"**{time_str}** {success_emoji} `{record.action.value}`\n"
                    f"操作: {record.operation_name}\n"
                    f"執行者: <@{record.executor_id}>\n"
                    f"目標: {record.target_name or record.target_id}\n\n"
                )

            embed.description = record_text

            if len(records) > 10:
                embed.set_footer(text=f"還有 {len(records) - 10} 個操作記錄")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【操作歷史】查詢最近操作失敗: {e}")
            await interaction.followup.send("❌ 查詢操作歷史時發生錯誤", ephemeral=True)

    @ui.button(label="操作分析", emoji="📊", style=discord.ButtonStyle.secondary)
    async def operation_analysis(self, interaction: discord.Interaction, button: ui.Button):
        """進行操作分析."""
        try:
            await interaction.response.defer(ephemeral=True)

            if not self.admin_panel.history_manager:
                await interaction.followup.send("❌ 歷史管理服務未初始化", ephemeral=True)
                return

            # 分析最近7天的操作
            query = HistoryQuery(
                start_time=datetime.utcnow() - timedelta(days=7),
                include_statistics=True
            )

            analysis = await self.admin_panel.history_manager.analyze_history(query)

            # 創建分析結果 embed
            embed = StandardEmbedBuilder.create_info_embed(
                "📊 操作分析報告",
                "最近7天的操作分析結果"
            )

            embed.add_field(
                name="📈 基本統計",
                value=(
                    f"• 總操作數: {analysis.total_records}\n"
                    f"• 成功率: {analysis.success_rate:.1f}%\n"
                    f"• 失敗操作: {analysis.failed_operations}\n"
                    f"• 分析耗時: {getattr(analysis, 'duration_ms', 0):.0f}ms"
                ),
                inline=True
            )

            if analysis.operations_by_action:
                action_stats = "\n".join([
                    f"• {action}: {count}"
                    for action, count in sorted(analysis.operations_by_action.items(),
                                              key=lambda x: x[1], reverse=True)[:5]
                ])
                embed.add_field(
                    name="🎯 主要操作類型",
                    value=action_stats,
                    inline=True
                )

            if analysis.most_active_executors:
                executor_stats = ""
                for executor in analysis.most_active_executors[:3]:
                    executor_stats += f"• <@{executor['executor_id']}>: {executor['operations_count']}\n"

                embed.add_field(
                    name="👥 最活躍執行者",
                    value=executor_stats,
                    inline=True
                )

            if analysis.security_incidents:
                incidents_text = ""
                for incident in analysis.security_incidents[:3]:
                    incidents_text += f"• {incident.get('description', incident.get('type', 'Unknown'))}\n"

                embed.add_field(
                    name="🚨 安全事件",
                    value=incidents_text,
                    inline=False
                )

            embed.set_footer(text=f"分析ID: {analysis.analysis_id}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【操作歷史】操作分析失敗: {e}")
            await interaction.followup.send("❌ 進行操作分析時發生錯誤", ephemeral=True)

    @ui.button(label="返回安全面板", emoji="🔒", style=discord.ButtonStyle.success, row=1)
    async def back_to_security_button(self, interaction: discord.Interaction, button: ui.Button):
        """返回安全面板按鈕."""
        await self.admin_panel.handle_navigation(
            interaction, SecurityPanelState.SECURITY_OVERVIEW
        )
