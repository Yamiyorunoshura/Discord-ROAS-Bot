"""
反可執行檔案保護模組 - 對話框元件
"""

import discord
from discord import ui

from ..main_view import AntiExecutableMainView


# 基礎對話框類
class BaseModal(ui.Modal):
    """基礎對話框類"""

    def __init__(self, view: AntiExecutableMainView, **kwargs):
        super().__init__(**kwargs)
        self.main_view = view


# 設定對話框
class SettingsModal(BaseModal):
    """設定對話框"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(view=view, title="⚙️ 進階設定")

        # 添加設定項目
        self.add_item(
            ui.TextInput(
                label="刪除訊息",
                placeholder="是否自動刪除違規訊息 (true/false)",
                default="true",
                max_length=5,
            )
        )

        self.add_item(
            ui.TextInput(
                label="管理員通知",
                placeholder="是否通知管理員 (true/false)",
                default="true",
                max_length=5,
            )
        )

        self.add_item(
            ui.TextInput(
                label="用戶警告",
                placeholder="是否向用戶發送警告 (true/false)",
                default="true",
                max_length=5,
            )
        )

        self.add_item(
            ui.TextInput(
                label="通知頻道ID",
                placeholder="管理員通知頻道ID (可選)",
                required=False,
                max_length=20,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        """提交設定"""
        try:
            # 解析設定值
            delete_message = self.children[0].value.lower() == "true"
            notify_admin = self.children[1].value.lower() == "true"
            warn_user = self.children[2].value.lower() == "true"
            notify_channel = (
                self.children[3].value.strip() if self.children[3].value else None
            )

            # 驗證頻道ID
            if notify_channel and not notify_channel.isdigit():
                await interaction.response.send_message(
                    "❌ 通知頻道ID必須是數字", ephemeral=True
                )
                return

            # 更新設定
            await self.main_view.cog.update_settings(
                self.main_view.guild_id,
                delete_message=delete_message,
                notify_admin=notify_admin,
                warn_user=warn_user,
                notify_channel=int(notify_channel) if notify_channel else None,
            )

            await interaction.response.send_message("✅ 設定已更新", ephemeral=True)

            # 更新面板
            await self.main_view.update_panel(interaction)

        except Exception as exc:
            await self.main_view._handle_error(interaction, f"更新設定失敗:{exc}")


# 白名單對話框
class AddWhitelistModal(BaseModal):
    """新增白名單對話框"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(view=view, title="➕ 新增白名單項目")

        self.add_item(
            ui.TextInput(
                label="白名單項目",
                placeholder="輸入檔案格式或網域 (例: jpg, example.com)",
                max_length=100,
            )
        )

        self.add_item(
            ui.TextInput(
                label="備註",
                placeholder="可選:添加備註說明",
                required=False,
                max_length=200,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        """提交新增白名單"""
        try:
            item = self.children[0].value.strip()
            note = self.children[1].value.strip() if self.children[1].value else None

            if not item:
                await interaction.response.send_message(
                    "❌ 請輸入有效的白名單項目", ephemeral=True
                )
                return

            # 新增到白名單
            await self.main_view.cog.add_whitelist(self.main_view.guild_id, item, note)

            await interaction.response.send_message(
                f"✅ 已新增白名單項目:{item}", ephemeral=True
            )

            # 更新面板
            await self.main_view.update_panel(interaction)

        except Exception as exc:
            await self.main_view._handle_error(interaction, f"新增白名單失敗:{exc}")


class RemoveWhitelistModal(BaseModal):
    """移除白名單對話框"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(view=view, title="➖ 移除白名單項目")

        self.add_item(
            ui.TextInput(
                label="白名單項目",
                placeholder="輸入要移除的檔案格式或網域",
                max_length=100,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        """提交移除白名單"""
        try:
            item = self.children[0].value.strip()

            if not item:
                await interaction.response.send_message(
                    "❌ 請輸入有效的白名單項目", ephemeral=True
                )
                return

            # 從白名單移除
            success = await self.main_view.cog.remove_whitelist(
                self.main_view.guild_id, item
            )

            if success:
                await interaction.response.send_message(
                    f"✅ 已移除白名單項目:{item}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ 找不到白名單項目:{item}", ephemeral=True
                )

            # 更新面板
            await self.main_view.update_panel(interaction)

        except Exception as exc:
            await self.main_view._handle_error(interaction, f"移除白名單失敗:{exc}")


# 黑名單對話框
class AddBlacklistModal(BaseModal):
    """新增黑名單對話框"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(view=view, title="➕ 新增黑名單項目")

        self.add_item(
            ui.TextInput(
                label="黑名單項目",
                placeholder="輸入檔案格式或網域 (例: exe, malware.com)",
                max_length=100,
            )
        )

        self.add_item(
            ui.TextInput(
                label="備註",
                placeholder="可選:添加備註說明",
                required=False,
                max_length=200,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        """提交新增黑名單"""
        try:
            item = self.children[0].value.strip()
            note = self.children[1].value.strip() if self.children[1].value else None

            if not item:
                await interaction.response.send_message(
                    "❌ 請輸入有效的黑名單項目", ephemeral=True
                )
                return

            # 新增到黑名單
            await self.main_view.cog.add_blacklist(self.main_view.guild_id, item, note)

            await interaction.response.send_message(
                f"✅ 已新增黑名單項目:{item}", ephemeral=True
            )

            # 更新面板
            await self.main_view.update_panel(interaction)

        except Exception as exc:
            await self.main_view._handle_error(interaction, f"新增黑名單失敗:{exc}")


class RemoveBlacklistModal(BaseModal):
    """移除黑名單對話框"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(view=view, title="➖ 移除黑名單項目")

        self.add_item(
            ui.TextInput(
                label="黑名單項目",
                placeholder="輸入要移除的檔案格式或網域",
                max_length=100,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        """提交移除黑名單"""
        try:
            item = self.children[0].value.strip()

            if not item:
                await interaction.response.send_message(
                    "❌ 請輸入有效的黑名單項目", ephemeral=True
                )
                return

            # 從黑名單移除
            success = await self.main_view.cog.remove_blacklist(
                self.main_view.guild_id, item
            )

            if success:
                await interaction.response.send_message(
                    f"✅ 已移除黑名單項目:{item}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ 找不到黑名單項目:{item}", ephemeral=True
                )

            # 更新面板
            await self.main_view.update_panel(interaction)

        except Exception as exc:
            await self.main_view._handle_error(interaction, f"移除黑名單失敗:{exc}")


# 格式管理對話框
class AddFormatModal(BaseModal):
    """新增格式對話框"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(view=view, title="➕ 新增檔案格式")

        self.add_item(
            ui.TextInput(
                label="檔案格式",
                placeholder="輸入檔案格式 (例: exe, bat, zip)",
                max_length=50,
            )
        )

        self.add_item(
            ui.TextInput(
                label="格式說明",
                placeholder="可選:格式說明",
                required=False,
                max_length=100,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        """提交新增格式"""
        try:
            format_name = self.children[0].value.strip().lower()
            description = (
                self.children[1].value.strip() if self.children[1].value else None
            )

            if not format_name:
                await interaction.response.send_message(
                    "❌ 請輸入有效的檔案格式", ephemeral=True
                )
                return

            # 移除點號
            format_name = format_name.lstrip(".")

            # 新增格式
            await self.main_view.cog.add_format(
                self.main_view.guild_id, format_name, description
            )

            await interaction.response.send_message(
                f"✅ 已新增檔案格式:{format_name}", ephemeral=True
            )

            # 更新面板
            await self.main_view.update_panel(interaction)

        except Exception as exc:
            await self.main_view._handle_error(interaction, f"新增格式失敗:{exc}")


class RemoveFormatModal(BaseModal):
    """移除格式對話框"""

    def __init__(self, view: AntiExecutableMainView):
        super().__init__(view=view, title="➖ 移除檔案格式")

        self.add_item(
            ui.TextInput(
                label="檔案格式", placeholder="輸入要移除的檔案格式", max_length=50
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        """提交移除格式"""
        try:
            format_name = self.children[0].value.strip().lower()

            if not format_name:
                await interaction.response.send_message(
                    "❌ 請輸入有效的檔案格式", ephemeral=True
                )
                return

            # 移除點號
            format_name = format_name.lstrip(".")

            # 移除格式
            success = await self.main_view.cog.remove_format(
                self.main_view.guild_id, format_name
            )

            if success:
                await interaction.response.send_message(
                    f"✅ 已移除檔案格式:{format_name}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ 找不到檔案格式:{format_name}", ephemeral=True
                )

            # 更新面板
            await self.main_view.update_panel(interaction)

        except Exception as exc:
            await self.main_view._handle_error(interaction, f"移除格式失敗:{exc}")
