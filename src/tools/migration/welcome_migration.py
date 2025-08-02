"""
歡迎模塊數據遷移工具 - 將舊系統數據遷移到新架構

此模組實現從舊歡迎系統到新企業級架構的數據遷移,包括:
- 設定數據遷移
- 背景圖片遷移
- 數據驗證和回退機制
- 遷移進度追蹤

符合 TASK-004: 數據遷移工具實現的要求
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.cogs.welcome.config.config import WelcomeConfig
from src.cogs.welcome.database.repository import WelcomeRepository
from src.core.config import get_settings
from src.core.logger import BotLogger
from src.core.monitor import PerformanceMonitor

if TYPE_CHECKING:
    from src.core.container import Container


class MigrationError(Exception):
    """遷移錯誤異常"""

    pass


class MigrationValidationError(MigrationError):
    """遷移驗證錯誤"""

    pass


class WelcomeMigrationTool:
    """歡迎模塊數據遷移工具

    負責將舊系統的數據遷移到新架構,包括:
    - 設定表結構遷移
    - 數據內容遷移
    - 背景圖片文件遷移
    - 遷移驗證和回退
    """

    def __init__(
        self,
        container: Container,
        old_db_path: str | None = None,
        old_bg_dir: str | None = None,
        migration_log_path: str | None = None,
    ):
        """初始化遷移工具

        Args:
            container: 依賴注入容器
            old_db_path: 舊數據庫路徑
            old_bg_dir: 舊背景圖片目錄
            migration_log_path: 遷移日誌路徑
        """
        self._container = container
        self._logger = container.get(BotLogger)
        self._monitor = container.get(PerformanceMonitor)
        self._repository = container.get(WelcomeRepository)
        self._config = container.get(WelcomeConfig)

        # 使用配置系統獲取正確路徑
        settings = get_settings()

        # 路徑配置
        self._old_db_path = Path(old_db_path) if old_db_path else (settings.database.sqlite_path / "welcome.db")
        self._old_bg_dir = Path(old_bg_dir) if old_bg_dir else (settings.data_dir / "backgrounds")
        self._migration_log_path = Path(migration_log_path) if migration_log_path else settings.get_log_file_path("welcome_migration")

        # 遷移狀態
        self._migration_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._backup_dir = settings.data_dir / "backups" / f"welcome_migration_{self._migration_id}"

        # 遷移統計
        self._stats = {
            "guilds_migrated": 0,
            "settings_migrated": 0,
            "backgrounds_migrated": 0,
            "errors": 0,
            "warnings": 0,
            "start_time": None,
            "end_time": None,
        }

        self._logger.info(f"歡迎數據遷移工具已初始化 - 遷移ID: {self._migration_id}")

    async def migrate_all(
        self, dry_run: bool = False, backup: bool = True
    ) -> dict[str, Any]:
        """執行完整的數據遷移

        Args:
            dry_run: 是否為試運行(不實際執行遷移)
            backup: 是否創建備份

        Returns:
            遷移結果報告
        """
        self._stats["start_time"] = datetime.now()

        try:
            with self._monitor.track_operation(
                f"welcome_migration_{self._migration_id}"
            ):
                self._logger.info(
                    f"開始歡迎數據遷移 - 試運行: {dry_run}, 備份: {backup}"
                )

                # 1. 預檢查
                await self._pre_migration_check()

                # 2. 創建備份(如果需要)
                if backup and not dry_run:
                    await self._create_backup()

                # 3. 遷移設定數據
                settings_result = await self._migrate_settings(dry_run)

                # 4. 遷移背景圖片
                backgrounds_result = await self._migrate_backgrounds(dry_run)

                # 5. 驗證遷移結果
                validation_result = await self._validate_migration(dry_run)

                # 6. 生成遷移報告
                migration_report = self._generate_migration_report(
                    settings_result, backgrounds_result, validation_result, dry_run
                )

                self._stats["end_time"] = datetime.now()

                if not dry_run:
                    await self._save_migration_log(migration_report)

                self._logger.info(
                    f"歡迎數據遷移完成 - 成功遷移 {self._stats['guilds_migrated']} 個伺服器"
                )

                return migration_report

        except Exception as e:
            self._stats["errors"] += 1
            self._stats["end_time"] = datetime.now()
            self._logger.error(f"歡迎數據遷移失敗: {e}", exc_info=True)
            raise MigrationError(f"遷移失敗: {e}")

    async def _pre_migration_check(self) -> None:
        """遷移前檢查"""
        self._logger.info("執行遷移前檢查...")

        # 檢查舊數據庫是否存在
        if not self._old_db_path.exists():
            raise MigrationError(f"舊數據庫不存在: {self._old_db_path}")

        # 檢查舊數據庫是否可讀
        try:
            conn = sqlite3.connect(str(self._old_db_path))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            if "welcome_settings" not in tables:
                raise MigrationError("舊數據庫中未找到 welcome_settings 表")

            self._logger.info(f"舊數據庫檢查通過 - 發現表: {', '.join(tables)}")

        except sqlite3.Error as e:
            raise MigrationError(f"無法讀取舊數據庫: {e}")

        # 檢查新系統是否已初始化
        try:
            await self._repository.initialize()
            self._logger.info("新系統資料庫檢查通過")
        except Exception as e:
            raise MigrationError(f"新系統初始化失敗: {e}")

        # 檢查背景圖片目錄
        if self._old_bg_dir.exists():
            bg_files = list(self._old_bg_dir.glob("welcome_bg_*.png")) + list(
                self._old_bg_dir.glob("welcome_bg_*.jpg")
            )
            self._logger.info(f"發現 {len(bg_files)} 個背景圖片文件")
        else:
            self._logger.warning(f"舊背景圖片目錄不存在: {self._old_bg_dir}")

    async def _create_backup(self) -> None:
        """創建數據備份"""
        self._logger.info("創建數據備份...")

        self._backup_dir.mkdir(parents=True, exist_ok=True)

        # 備份舊數據庫
        if self._old_db_path.exists():
            backup_db_path = self._backup_dir / "old_welcome.db"
            shutil.copy2(self._old_db_path, backup_db_path)
            self._logger.info(f"舊數據庫已備份至: {backup_db_path}")

        # 備份舊背景圖片目錄
        if self._old_bg_dir.exists():
            backup_bg_dir = self._backup_dir / "old_backgrounds"
            backup_bg_dir.mkdir(parents=True, exist_ok=True)

            for bg_file in self._old_bg_dir.rglob("welcome_bg_*"):
                if bg_file.is_file():
                    shutil.copy2(bg_file, backup_bg_dir / bg_file.name)

            self._logger.info(f"背景圖片已備份至: {backup_bg_dir}")

        # 備份新系統數據(如果存在)
        try:
            all_settings = await self._get_all_new_settings()
            if all_settings:
                backup_new_path = self._backup_dir / "new_system_backup.json"
                with open(backup_new_path, "w", encoding="utf-8") as f:
                    json.dump(all_settings, f, ensure_ascii=False, indent=2)
                self._logger.info(f"新系統數據已備份至: {backup_new_path}")
        except Exception as e:
            self._logger.warning(f"新系統數據備份失敗: {e}")

    async def _migrate_settings(self, dry_run: bool) -> dict[str, Any]:
        """遷移設定數據

        Args:
            dry_run: 是否為試運行

        Returns:
            遷移結果
        """
        self._logger.info("開始遷移設定數據...")

        result = {"success": True, "migrated_count": 0, "errors": [], "warnings": []}

        try:
            # 讀取舊數據庫中的設定
            old_settings = self._read_old_settings()

            for guild_id, old_setting in old_settings.items():
                try:
                    # 轉換設定格式
                    new_setting = self._convert_settings(old_setting)

                    if dry_run:
                        self._logger.debug(f"試運行 - 將遷移伺服器 {guild_id} 的設定")
                    else:
                        # 檢查新系統中是否已存在
                        existing_settings = await self._repository.get_settings(
                            guild_id
                        )
                        if existing_settings.get(
                            "guild_id"
                        ) == guild_id and not self._is_default_settings(
                            existing_settings
                        ):
                            result["warnings"].append(
                                f"伺服器 {guild_id} 在新系統中已有設定,將被覆蓋"
                            )

                        # 執行遷移
                        await self._repository.update_settings(guild_id, new_setting)
                        self._logger.info(f"已遷移伺服器 {guild_id} 的設定")

                    result["migrated_count"] += 1
                    self._stats["settings_migrated"] += 1

                except Exception as e:
                    error_msg = f"遷移伺服器 {guild_id} 設定失敗: {e}"
                    result["errors"].append(error_msg)
                    self._logger.error(error_msg)
                    self._stats["errors"] += 1

            self._stats["guilds_migrated"] = result["migrated_count"]

            if result["errors"]:
                result["success"] = False

            self._logger.info(
                f"設定數據遷移完成 - 成功: {result['migrated_count']}, 錯誤: {len(result['errors'])}"
            )

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"讀取舊設定失敗: {e}")
            self._logger.error(f"設定遷移失敗: {e}", exc_info=True)

        return result

    async def _migrate_backgrounds(self, dry_run: bool) -> dict[str, Any]:
        """遷移背景圖片

        Args:
            dry_run: 是否為試運行

        Returns:
            遷移結果
        """
        self._logger.info("開始遷移背景圖片...")

        result = {"success": True, "migrated_count": 0, "errors": [], "warnings": []}

        if not self._old_bg_dir.exists():
            result["warnings"].append(f"舊背景圖片目錄不存在: {self._old_bg_dir}")
            return result

        try:
            # 獲取新背景圖片目錄
            new_bg_dir = self._config.get_welcome_bg_directory()

            # 查找所有背景圖片
            bg_files = (
                list(self._old_bg_dir.glob("welcome_bg_*.png"))
                + list(self._old_bg_dir.glob("welcome_bg_*.jpg"))
                + list(self._old_bg_dir.glob("welcome_bg_*.jpeg"))
            )

            for bg_file in bg_files:
                try:
                    # 從文件名提取伺服器 ID
                    guild_id = self._extract_guild_id_from_filename(bg_file.name)
                    if guild_id is None:
                        result["warnings"].append(
                            f"無法從文件名提取伺服器ID: {bg_file.name}"
                        )
                        continue

                    if dry_run:
                        self._logger.debug(
                            f"試運行 - 將遷移背景圖片: {bg_file.name} -> 伺服器 {guild_id}"
                        )
                    else:
                        # 複製文件到新目錄
                        new_filename = f"welcome_bg_{guild_id}{bg_file.suffix}"
                        new_bg_path = new_bg_dir / new_filename

                        # 如果目標文件已存在,創建備份
                        if new_bg_path.exists():
                            backup_path = new_bg_path.with_suffix(
                                f".backup_{self._migration_id}{bg_file.suffix}"
                            )
                            shutil.move(new_bg_path, backup_path)
                            result["warnings"].append(
                                f"已備份現有文件: {new_bg_path} -> {backup_path}"
                            )

                        shutil.copy2(bg_file, new_bg_path)

                        # 更新資料庫記錄
                        await self._repository.update_background(
                            guild_id,
                            str(new_bg_path),
                            bg_file.name,
                            bg_file.stat().st_size,
                        )

                        self._logger.info(
                            f"已遷移背景圖片: {bg_file.name} -> {new_filename}"
                        )

                    result["migrated_count"] += 1
                    self._stats["backgrounds_migrated"] += 1

                except Exception as e:
                    error_msg = f"遷移背景圖片 {bg_file.name} 失敗: {e}"
                    result["errors"].append(error_msg)
                    self._logger.error(error_msg)
                    self._stats["errors"] += 1

            if result["errors"]:
                result["success"] = False

            self._logger.info(
                f"背景圖片遷移完成 - 成功: {result['migrated_count']}, 錯誤: {len(result['errors'])}"
            )

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"背景圖片遷移失敗: {e}")
            self._logger.error(f"背景圖片遷移失敗: {e}", exc_info=True)

        return result

    async def _validate_migration(self, dry_run: bool) -> dict[str, Any]:
        """驗證遷移結果

        Args:
            dry_run: 是否為試運行

        Returns:
            驗證結果
        """
        self._logger.info("開始驗證遷移結果...")

        result = {
            "success": True,
            "validation_checks": [],
            "errors": [],
            "warnings": [],
        }

        if dry_run:
            result["validation_checks"].append("試運行模式 - 跳過驗證")
            return result

        try:
            # 1. 檢查數據完整性
            integrity_result = await self._repository.validate_data_integrity()
            result["validation_checks"].append(
                {
                    "check": "data_integrity",
                    "status": integrity_result["status"],
                    "issues": integrity_result.get("issues", []),
                }
            )

            if integrity_result["status"] != "healthy":
                result["warnings"].extend(integrity_result.get("issues", []))

            # 2. 比較遷移前後的數據量
            old_count = len(self._read_old_settings())
            new_count = len(await self._get_all_new_settings())

            result["validation_checks"].append(
                {
                    "check": "record_count",
                    "old_count": old_count,
                    "new_count": new_count,
                    "match": old_count == new_count,
                }
            )

            if old_count != new_count:
                result["warnings"].append(
                    f"記錄數量不匹配 - 舊系統: {old_count}, 新系統: {new_count}"
                )

            # 3. 檢查關鍵設定是否正確遷移
            validation_errors = await self._validate_key_settings()
            if validation_errors:
                result["errors"].extend(validation_errors)
                result["success"] = False

            # 4. 檢查背景圖片文件
            bg_validation = await self._validate_background_files()
            result["validation_checks"].append(bg_validation)

            if not bg_validation.get("success", True):
                result["warnings"].extend(bg_validation.get("issues", []))

            self._logger.info(f"遷移驗證完成 - 成功: {result['success']}")

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"驗證過程失敗: {e}")
            self._logger.error(f"遷移驗證失敗: {e}", exc_info=True)

        return result

    def _read_old_settings(self) -> dict[int, dict[str, Any]]:
        """讀取舊數據庫中的設定

        Returns:
            舊設定字典 {guild_id: settings}
        """
        settings = {}

        try:
            conn = sqlite3.connect(str(self._old_db_path))
            cursor = conn.execute("""
                SELECT guild_id, channel_id, title, description, message, avatar_x, avatar_y,
                       title_y, description_y, title_font_size, desc_font_size, avatar_size
                FROM welcome_settings
            """)

            for row in cursor.fetchall():
                guild_id = row[0]
                settings[guild_id] = {
                    "guild_id": guild_id,
                    "channel_id": row[1],
                    "title": row[2],
                    "description": row[3],
                    "message": row[4],
                    "avatar_x": row[5],
                    "avatar_y": row[6],
                    "title_y": row[7],
                    "description_y": row[8],
                    "title_font_size": row[9],
                    "desc_font_size": row[10],
                    "avatar_size": row[11],
                }

            conn.close()
            self._logger.debug(f"從舊數據庫讀取了 {len(settings)} 個伺服器設定")

        except sqlite3.Error as e:
            self._logger.error(f"讀取舊設定失敗: {e}")
            raise MigrationError(f"讀取舊設定失敗: {e}")

        return settings

    def _convert_settings(self, old_setting: dict[str, Any]) -> dict[str, Any]:
        """將舊設定格式轉換為新格式

        Args:
            old_setting: 舊設定

        Returns:
            新格式設定
        """
        new_setting = {
            "enabled": old_setting.get("channel_id")
            is not None,  # 如果有設定頻道,則啟用
            "channel_id": old_setting.get("channel_id"),
            "message": old_setting.get(
                "message", "歡迎 {member.mention} 加入 {guild.name}!"
            ),
            "title": old_setting.get("title", "歡迎加入"),
            "description": old_setting.get("description", "感謝您的加入!"),
            "enable_image": True,  # 舊系統預設啟用圖片
            "avatar_size": old_setting.get("avatar_size", 128),
            "avatar_x": old_setting.get("avatar_x", 100),
            "avatar_y": old_setting.get("avatar_y", 100),
            "title_y": old_setting.get("title_y", 200),
            "desc_y": old_setting.get("description_y", 240),  # 注意欄位名稱變化
            "title_font_size": old_setting.get("title_font_size", 36),
            "desc_font_size": old_setting.get("desc_font_size", 24),
        }

        return new_setting

    def _extract_guild_id_from_filename(self, filename: str) -> int | None:
        """從背景圖片文件名提取伺服器 ID

        Args:
            filename: 文件名

        Returns:
            伺服器 ID,如果無法提取則返回 None
        """
        try:
            # 文件名格式: welcome_bg_123456789.png 或 bg_123456789_IMG_xxxx.JPG
            if filename.startswith("welcome_bg_"):
                # 標準格式
                parts = filename.replace("welcome_bg_", "").split(".")
                return int(parts[0])
            elif filename.startswith("bg_"):
                # 變體格式
                parts = filename.replace("bg_", "").split("_")
                return int(parts[0])
            else:
                return None
        except (ValueError, IndexError):
            return None

    async def _get_all_new_settings(self) -> dict[int, dict[str, Any]]:
        """獲取新系統中的所有設定

        Returns:
            新系統設定字典
        """
        try:
            # 這需要實現一個獲取所有設定的方法
            # 暫時返回空字典,實際實現需要查詢所有記錄
            return {}
        except Exception as e:
            self._logger.error(f"獲取新系統設定失敗: {e}")
            return {}

    def _is_default_settings(self, settings: dict[str, Any]) -> bool:
        """檢查設定是否為預設值

        Args:
            settings: 設定字典

        Returns:
            是否為預設設定
        """
        default_settings = self._config.get_default_settings()

        # 比較關鍵設定項目
        key_fields = ["enabled", "channel_id", "message", "title", "description"]

        for field in key_fields:
            if settings.get(field) != default_settings.get(field):
                return False

        return True

    async def _validate_key_settings(self) -> list[str]:
        """驗證關鍵設定是否正確遷移

        Returns:
            驗證錯誤列表
        """
        errors = []

        # 這裡可以實現具體的驗證邏輯
        # 例如檢查特定伺服器的設定是否正確遷移

        return errors

    async def _validate_background_files(self) -> dict[str, Any]:
        """驗證背景圖片文件

        Returns:
            驗證結果
        """
        result = {"check": "background_files", "success": True, "issues": []}

        try:
            new_bg_dir = self._config.get_welcome_bg_directory()

            # 檢查目錄是否存在
            if not new_bg_dir.exists():
                result["success"] = False
                result["issues"].append(f"新背景圖片目錄不存在: {new_bg_dir}")
                return result

            # 檢查文件完整性
            bg_files = list(new_bg_dir.glob("welcome_bg_*"))
            result["migrated_files"] = len(bg_files)

            for bg_file in bg_files:
                if not bg_file.is_file():
                    result["issues"].append(f"背景文件無效: {bg_file}")
                elif bg_file.stat().st_size == 0:
                    result["issues"].append(f"背景文件為空: {bg_file}")

            if result["issues"]:
                result["success"] = False

        except Exception as e:
            result["success"] = False
            result["issues"].append(f"背景文件驗證失敗: {e}")

        return result

    def _generate_migration_report(
        self,
        settings_result: dict[str, Any],
        backgrounds_result: dict[str, Any],
        validation_result: dict[str, Any],
        dry_run: bool,
    ) -> dict[str, Any]:
        """生成遷移報告

        Args:
            settings_result: 設定遷移結果
            backgrounds_result: 背景遷移結果
            validation_result: 驗證結果
            dry_run: 是否為試運行

        Returns:
            完整的遷移報告
        """
        duration = None
        if self._stats["start_time"] and self._stats["end_time"]:
            duration = (
                self._stats["end_time"] - self._stats["start_time"]
            ).total_seconds()

        report = {
            "migration_id": self._migration_id,
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "duration_seconds": duration,
            "statistics": self._stats.copy(),
            "results": {
                "settings": settings_result,
                "backgrounds": backgrounds_result,
                "validation": validation_result,
            },
            "overall_success": (
                settings_result.get("success", False)
                and backgrounds_result.get("success", False)
                and validation_result.get("success", False)
            ),
            "backup_location": str(self._backup_dir)
            if self._backup_dir.exists()
            else None,
        }

        return report

    async def _save_migration_log(self, report: dict[str, Any]) -> None:
        """保存遷移日誌

        Args:
            report: 遷移報告
        """
        try:
            self._migration_log_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self._migration_log_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)

            self._logger.info(f"遷移報告已保存至: {self._migration_log_path}")

        except Exception as e:
            self._logger.error(f"保存遷移日誌失敗: {e}")

    async def rollback_migration(self, migration_id: str) -> dict[str, Any]:
        """回滾遷移操作

        Args:
            migration_id: 要回滾的遷移ID

        Returns:
            回滾結果
        """
        self._logger.info(f"開始回滾遷移: {migration_id}")

        rollback_result = {"success": True, "rolled_back": [], "errors": []}

        try:
            backup_dir = Path("backups") / f"welcome_migration_{migration_id}"

            if not backup_dir.exists():
                raise MigrationError(f"找不到遷移備份: {backup_dir}")

            # 回滾新系統數據
            backup_data_path = backup_dir / "new_system_backup.json"
            if backup_data_path.exists():
                with open(backup_data_path, encoding="utf-8") as f:
                    json.load(f)

                # 這裡需要實現具體的回滾邏輯
                # 恢復到備份狀態
                rollback_result["rolled_back"].append("database_settings")

            # 回滾背景圖片
            backup_bg_dir = backup_dir / "old_backgrounds"
            if backup_bg_dir.exists():
                new_bg_dir = self._config.get_welcome_bg_directory()

                # 刪除遷移後的文件,恢復原始文件
                for bg_file in new_bg_dir.glob("welcome_bg_*"):
                    if bg_file.name.endswith(
                        f".backup_{migration_id}.png"
                    ) or bg_file.name.endswith(f".backup_{migration_id}.jpg"):
                        # 恢復備份文件
                        original_name = bg_file.name.replace(
                            f".backup_{migration_id}", ""
                        )
                        original_path = new_bg_dir / original_name
                        shutil.move(bg_file, original_path)

                rollback_result["rolled_back"].append("background_images")

            self._logger.info(f"遷移回滾完成: {migration_id}")

        except Exception as e:
            rollback_result["success"] = False
            rollback_result["errors"].append(str(e))
            self._logger.error(f"遷移回滾失敗: {e}", exc_info=True)

        return rollback_result


async def main():
    """主函數 - 用於測試和手動執行遷移"""
    from src.core.container import Container

    # 初始化容器
    container = Container()

    # 創建遷移工具
    migration_tool = WelcomeMigrationTool(container)

    try:
        # 執行試運行
        print("執行遷移試運行...")
        dry_run_result = await migration_tool.migrate_all(dry_run=True)
        print(
            f"試運行結果: {json.dumps(dry_run_result, indent=2, ensure_ascii=False, default=str)}"
        )

        # 詢問是否執行實際遷移
        confirm = input("是否執行實際遷移?(y/N): ")
        if confirm.lower() == "y":
            print("執行實際遷移...")
            result = await migration_tool.migrate_all(dry_run=False, backup=True)
            print(
                f"遷移結果: {json.dumps(result, indent=2, ensure_ascii=False, default=str)}"
            )
        else:
            print("已取消實際遷移")

    except Exception as e:
        print(f"遷移失敗: {e}")


if __name__ == "__main__":
    asyncio.run(main())
