"""
遷移管理器 - 統一管理數據遷移流程

此模組提供完整的遷移管理功能,包括:
- 遷移規劃和執行
- 進度監控
- 錯誤處理和回滾
- 報告生成

符合 TASK-004: 數據遷移工具實現的要求
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.container import Container
from src.core.logger import BotLogger

from .migration_validator import MigrationValidator
from .welcome_migration import WelcomeMigrationTool


class MigrationManager:
    """遷移管理器

    統一管理所有遷移相關操作,包括:
    - 遷移執行
    - 驗證檢查
    - 進度追蹤
    - 報告管理
    """

    def __init__(self, container: Container):
        """初始化遷移管理器

        Args:
            container: 依賴注入容器
        """
        self._container = container
        self._logger = container.get(BotLogger)

        # 創建工具實例
        self._migration_tool = WelcomeMigrationTool(container)
        self._validator = MigrationValidator(container)

        self._logger.info("遷移管理器已初始化")

    async def execute_migration_plan(
        self,
        dry_run: bool = False,
        backup: bool = True,
        validate: bool = True,
        auto_rollback: bool = False,
    ) -> dict[str, Any]:
        """執行完整的遷移計劃

        Args:
            dry_run: 是否為試運行
            backup: 是否創建備份
            validate: 是否執行驗證
            auto_rollback: 是否在失敗時自動回滾

        Returns:
            完整的遷移結果
        """
        plan_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._logger.info(f"開始執行遷移計劃 - ID: {plan_id}")

        plan_result = {
            "plan_id": plan_id,
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "dry_run": dry_run,
                "backup": backup,
                "validate": validate,
                "auto_rollback": auto_rollback,
            },
            "phases": {},
            "overall_success": False,
            "duration": None,
        }

        start_time = datetime.now()

        try:
            # 階段 1: 執行遷移
            self._logger.info("階段 1: 執行數據遷移")
            migration_result = await self._migration_tool.migrate_all(
                dry_run=dry_run, backup=backup
            )
            phases_dict = plan_result["phases"]
            if isinstance(phases_dict, dict):
                phases_dict["migration"] = migration_result

            if not migration_result.get("overall_success", False) and not dry_run:
                self._logger.error("遷移失敗,停止後續階段")

                if auto_rollback and migration_result.get("migration_id"):
                    self._logger.info("執行自動回滾...")
                    rollback_result = await self._migration_tool.rollback_migration(
                        migration_result["migration_id"]
                    )
                    phases_dict = plan_result["phases"]
                    if isinstance(phases_dict, dict):
                        phases_dict["rollback"] = rollback_result

                return plan_result

            # 階段 2: 驗證遷移(如果不是試運行且要求驗證)
            if validate and not dry_run:
                self._logger.info("階段 2: 驗證遷移結果")
                validation_result = await self._validator.validate_full_migration()
                phases_dict = plan_result["phases"]
                if isinstance(phases_dict, dict):
                    phases_dict["validation"] = validation_result

                if validation_result.get("overall_status") == "failed":
                    self._logger.error("驗證失敗")

                    if auto_rollback and migration_result.get("migration_id"):
                        self._logger.info("執行自動回滾...")
                        rollback_result = await self._migration_tool.rollback_migration(
                            migration_result["migration_id"]
                        )
                        phases_dict = plan_result["phases"]
                        if isinstance(phases_dict, dict):
                            phases_dict["rollback"] = rollback_result

                    return plan_result

            # 計算整體成功狀態
            phases = plan_result["phases"]
            if isinstance(phases, dict):
                plan_result["overall_success"] = self._calculate_plan_success(phases)
            else:
                plan_result["overall_success"] = False

            end_time = datetime.now()
            plan_result["duration"] = (end_time - start_time).total_seconds()

            self._logger.info(f"遷移計劃完成 - 成功: {plan_result['overall_success']}")

            return plan_result

        except Exception as e:
            self._logger.error(f"遷移計劃執行失敗: {e}", exc_info=True)

            phases_dict = plan_result["phases"]
            if isinstance(phases_dict, dict):
                phases_dict["error"] = {
                    "type": "execution_error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                }

            return plan_result

    async def validate_migration_only(self) -> dict[str, Any]:
        """僅執行遷移驗證

        Returns:
            驗證結果
        """
        self._logger.info("執行獨立遷移驗證")

        try:
            validation_result = await self._validator.validate_full_migration()

            self._logger.info(
                f"驗證完成 - 狀態: {validation_result.get('overall_status')}"
            )

            return validation_result

        except Exception as e:
            self._logger.error(f"驗證執行失敗: {e}", exc_info=True)
            raise

    async def rollback_migration(self, migration_id: str) -> dict[str, Any]:
        """回滾指定的遷移

        Args:
            migration_id: 遷移 ID

        Returns:
            回滾結果
        """
        self._logger.info(f"執行遷移回滾 - ID: {migration_id}")

        try:
            rollback_result = await self._migration_tool.rollback_migration(
                migration_id
            )

            self._logger.info(f"回滾完成 - 成功: {rollback_result.get('success')}")

            return rollback_result

        except Exception as e:
            self._logger.error(f"回滾執行失敗: {e}", exc_info=True)
            raise

    def _calculate_plan_success(self, phases: dict[str, Any]) -> bool:
        """計算遷移計劃的整體成功狀態

        Args:
            phases: 各階段結果

        Returns:
            是否整體成功
        """
        # 遷移階段必須成功
        migration_success = phases.get("migration", {}).get("overall_success", False)

        # 如果有驗證階段,也必須成功
        if "validation" in phases:
            validation_success = phases["validation"].get("overall_status") in [
                "passed",
                "warning",
            ]
            return migration_success and validation_success

        return bool(migration_success)

    def _generate_report_header(self, plan_result: dict[str, Any]) -> list[str]:
        """生成報告標題部分"""
        report_lines: list[str] = []
        report_lines.append("=" * 60)
        report_lines.append("數據遷移執行報告")
        report_lines.append("=" * 60)
        report_lines.append("")

        # 基本信息
        report_lines.append(f"遷移 ID: {plan_result.get('plan_id')}")
        report_lines.append(f"執行時間: {plan_result.get('timestamp')}")
        report_lines.append(f"持續時間: {plan_result.get('duration', 0):.2f} 秒")
        report_lines.append(
            f"整體狀態: {'✅ 成功' if plan_result.get('overall_success') else '❌ 失敗'}"
        )
        report_lines.append("")

        # 參數設定
        params = plan_result.get("parameters", {})
        report_lines.append("執行參數:")
        report_lines.append(f"  - 試運行: {params.get('dry_run')}")
        report_lines.append(f"  - 創建備份: {params.get('backup')}")
        report_lines.append(f"  - 執行驗證: {params.get('validate')}")
        report_lines.append(f"  - 自動回滾: {params.get('auto_rollback')}")
        report_lines.append("")

        return report_lines

    def _generate_migration_phase_report(self, phases: dict[str, Any]) -> list[str]:
        """生成遷移階段報告部分"""
        report_lines: list[str] = []

        if "migration" not in phases:
            return report_lines

        migration = phases["migration"]
        report_lines.append("遷移階段結果:")
        report_lines.append(
            f"  - 狀態: {'✅ 成功' if migration.get('overall_success') else '❌ 失敗'}"
        )

        stats = migration.get("statistics", {})
        report_lines.append(f"  - 遷移伺服器數: {stats.get('guilds_migrated', 0)}")
        report_lines.append(f"  - 遷移設定數: {stats.get('settings_migrated', 0)}")
        report_lines.append(
            f"  - 遷移背景圖片數: {stats.get('backgrounds_migrated', 0)}"
        )
        report_lines.append(f"  - 錯誤數: {stats.get('errors', 0)}")
        report_lines.append("")

        # 詳細結果
        results = migration.get("results", {})
        if "settings" in results:
            settings_result = results["settings"]
            report_lines.append("  設定遷移:")
            report_lines.append(
                f"    - 成功: {settings_result.get('migrated_count', 0)}"
            )
            report_lines.append(f"    - 錯誤: {len(settings_result.get('errors', []))}")
            report_lines.append(
                f"    - 警告: {len(settings_result.get('warnings', []))}"
            )

        if "backgrounds" in results:
            bg_result = results["backgrounds"]
            report_lines.append("  背景圖片遷移:")
            report_lines.append(f"    - 成功: {bg_result.get('migrated_count', 0)}")
            report_lines.append(f"    - 錯誤: {len(bg_result.get('errors', []))}")
            report_lines.append(f"    - 警告: {len(bg_result.get('warnings', []))}")

        report_lines.append("")
        return report_lines

    def _generate_validation_phase_report(self, phases: dict[str, Any]) -> list[str]:
        """生成驗證階段報告部分"""
        report_lines: list[str] = []

        if "validation" not in phases:
            return report_lines

        validation = phases["validation"]
        report_lines.append("驗證階段結果:")
        report_lines.append(f"  - 狀態: {validation.get('overall_status', 'unknown')}")

        stats = validation.get("statistics", {})
        report_lines.append(f"  - 總檢查數: {stats.get('total_checks', 0)}")
        report_lines.append(f"  - 通過檢查: {stats.get('passed_checks', 0)}")
        report_lines.append(f"  - 失敗檢查: {stats.get('failed_checks', 0)}")
        report_lines.append(f"  - 警告數: {stats.get('warnings', 0)}")
        report_lines.append("")

        # 建議
        recommendations = validation.get("recommendations", [])
        if recommendations:
            report_lines.append("改進建議:")
            for i, rec in enumerate(recommendations, 1):
                report_lines.append(f"  {i}. {rec}")
            report_lines.append("")

        return report_lines

    def _generate_rollback_phase_report(self, phases: dict[str, Any]) -> list[str]:
        """生成回滾階段報告部分"""
        report_lines: list[str] = []

        if "rollback" not in phases:
            return report_lines

        rollback = phases["rollback"]
        report_lines.append("回滾階段結果:")
        report_lines.append(
            f"  - 狀態: {'✅ 成功' if rollback.get('success') else '❌ 失敗'}"
        )
        report_lines.append(
            f"  - 回滾項目: {', '.join(rollback.get('rolled_back', []))}"
        )

        if rollback.get("errors"):
            report_lines.append("  - 錯誤:")
            for error in rollback["errors"]:
                report_lines.append(f"    • {error}")

        report_lines.append("")
        return report_lines

    def _generate_error_phase_report(self, phases: dict[str, Any]) -> list[str]:
        """生成錯誤階段報告部分"""
        report_lines: list[str] = []

        if "error" not in phases:
            return report_lines

        error = phases["error"]
        report_lines.append("執行錯誤:")
        report_lines.append(f"  - 類型: {error.get('type')}")
        report_lines.append(f"  - 訊息: {error.get('message')}")
        report_lines.append(f"  - 時間: {error.get('timestamp')}")
        report_lines.append("")

        return report_lines

    def _generate_report_footer(self) -> list[str]:
        """生成報告結尾部分"""
        report_lines: list[str] = []
        report_lines.append("=" * 60)
        report_lines.append(f"報告生成時間: {datetime.now().isoformat()}")
        report_lines.append("=" * 60)
        return report_lines

    async def generate_migration_report(self, plan_result: dict[str, Any]) -> str:
        """生成遷移報告

        Args:
            plan_result: 遷移計劃結果

        Returns:
            報告文本
        """
        report_lines: list[str] = []
        phases = plan_result.get("phases", {})

        # 生成各個部分
        report_lines.extend(self._generate_report_header(plan_result))
        report_lines.extend(self._generate_migration_phase_report(phases))
        report_lines.extend(self._generate_validation_phase_report(phases))
        report_lines.extend(self._generate_rollback_phase_report(phases))
        report_lines.extend(self._generate_error_phase_report(phases))
        report_lines.extend(self._generate_report_footer())

        return "\n".join(report_lines)

def _create_argument_parser() -> argparse.ArgumentParser:
    """創建命令行參數解析器"""
    parser = argparse.ArgumentParser(description="Discord ROAS Bot 數據遷移管理器")

    parser.add_argument(
        "action",
        choices=["migrate", "validate", "rollback", "plan"],
        help="要執行的操作",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="試運行模式(不實際執行遷移)"
    )

    parser.add_argument("--no-backup", action="store_true", help="不創建備份")

    parser.add_argument("--no-validate", action="store_true", help="不執行驗證")

    parser.add_argument("--auto-rollback", action="store_true", help="失敗時自動回滾")

    parser.add_argument("--migration-id", type=str, help="要回滾的遷移 ID")

    parser.add_argument("--output", type=str, help="輸出報告文件路徑")

    return parser

def _save_output(
    data: str | dict[str, Any], output_path: str | None, success_msg: str
) -> None:
    """保存輸出結果到檔案或列印到控制台"""
    if output_path:
        path = Path(output_path)
        with path.open("w", encoding="utf-8") as f:
            if isinstance(data, str):
                f.write(data)
            else:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        print(success_msg)
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))

async def _handle_migrate_action(
    manager: MigrationManager, args: argparse.Namespace
) -> None:
    """處理遷移操作"""
    print("執行數據遷移...")
    result = await manager.execute_migration_plan(
        dry_run=args.dry_run,
        backup=not args.no_backup,
        validate=not args.no_validate,
        auto_rollback=args.auto_rollback,
    )

    # 生成報告
    report = await manager.generate_migration_report(result)
    _save_output(report, args.output, f"報告已保存至: {args.output}")

async def _handle_validate_action(
    manager: MigrationManager, args: argparse.Namespace
) -> None:
    """處理驗證操作"""
    print("執行遷移驗證...")
    result = await manager.validate_migration_only()
    _save_output(result, args.output, f"驗證結果已保存至: {args.output}")

async def _handle_rollback_action(
    manager: MigrationManager, args: argparse.Namespace
) -> None:
    """處理回滾操作"""
    if not args.migration_id:
        print("錯誤: 回滾操作需要指定 --migration-id")
        sys.exit(1)

    print(f"執行遷移回滾 - ID: {args.migration_id}")
    result = await manager.rollback_migration(args.migration_id)
    _save_output(result, args.output, f"回滾結果已保存至: {args.output}")

def _handle_plan_action(args: argparse.Namespace) -> None:
    """處理計劃顯示操作"""
    print("顯示遷移計劃...")
    print("遷移將執行以下步驟:")
    print("1. 檢查舊系統數據")
    print("2. 創建備份(如果啟用)")
    print("3. 遷移設定數據")
    print("4. 遷移背景圖片")
    print("5. 驗證遷移結果(如果啟用)")
    print("6. 生成遷移報告")
    print("")
    print("參數設定:")
    print(f"  - 試運行: {args.dry_run}")
    print(f"  - 創建備份: {not args.no_backup}")
    print(f"  - 執行驗證: {not args.no_validate}")
    print(f"  - 自動回滾: {args.auto_rollback}")

async def main() -> None:
    """主函數 - 命令行界面"""
    parser = _create_argument_parser()
    args = parser.parse_args()

    try:
        # 初始化容器
        container = Container()
        manager = MigrationManager(container)

        # 執行指定操作
        if args.action == "migrate":
            await _handle_migrate_action(manager, args)
        elif args.action == "validate":
            await _handle_validate_action(manager, args)
        elif args.action == "rollback":
            await _handle_rollback_action(manager, args)
        elif args.action == "plan":
            _handle_plan_action(args)

    except Exception as e:
        print(f"執行失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
