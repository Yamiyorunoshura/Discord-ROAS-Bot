"""資料庫備份與驗證工具 for Discord ROAS Bot v2.0.

此模組提供資料庫的備份和驗證功能:
- PostgreSQL 資料庫備份
- 遷移前後的資料完整性驗證
- 備份文件管理
- 資料比對工具
"""

from __future__ import annotations

import asyncio
import gzip
import logging
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

# 常數定義
URL_PARTS_COUNT = 2

class DatabaseBackupManager:
    """資料庫備份管理器."""

    def __init__(
        self,
        database_url: str,
        backup_dir: str | Path = "backups",
        compression: bool = True,
    ):
        """初始化備份管理器.

        Args:
            database_url: 資料庫連接 URL
            backup_dir: 備份目錄
            compression: 是否壓縮備份文件
        """
        self.database_url = database_url
        self.backup_dir = Path(backup_dir)
        self.compression = compression
        self.backup_dir.mkdir(exist_ok=True)

        # 解析資料庫 URL
        self._parse_database_url()

    def _parse_database_url(self) -> None:
        """解析資料庫連接 URL."""
        # 簡化的 URL 解析(實際應使用 urllib.parse)
        if self.database_url.startswith("postgresql://"):
            url_parts = self.database_url.replace("postgresql://", "").split("@")
            if len(url_parts) == URL_PARTS_COUNT:
                user_pass, host_db = url_parts
                if ":" in user_pass:
                    self.db_user, self.db_password = user_pass.split(":", 1)
                else:
                    self.db_user = user_pass
                    self.db_password = ""

                if "/" in host_db:
                    host_port, self.db_name = host_db.split("/", 1)
                else:
                    host_port = host_db
                    self.db_name = "postgres"

                if ":" in host_port:
                    self.db_host, port_str = host_port.split(":", 1)
                    self.db_port = int(port_str)
                else:
                    self.db_host = host_port
                    self.db_port = 5432
            else:
                raise ValueError(f"Invalid database URL format: {self.database_url}")
        else:
            raise ValueError(f"Unsupported database URL: {self.database_url}")

    async def create_backup(self, backup_name: str | None = None) -> Path:
        """建立資料庫備份.

        Args:
            backup_name: 備份名稱, 預設使用時間戳

        Returns:
            備份文件路徑

        Raises:
            Exception: 當備份失敗時
        """
        if backup_name is None:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            backup_name = f"discord_roas_bot_backup_{timestamp}"

        backup_file = self.backup_dir / f"{backup_name}.sql"

        try:
            # 使用 pg_dump 建立備份
            cmd = [
                "pg_dump",
                "-h",
                self.db_host,
                "-p",
                str(self.db_port),
                "-U",
                self.db_user,
                "-d",
                self.db_name,
                "--no-password",
                "--verbose",
                "--clean",
                "--if-exists",
                "--create",
                "-f",
                str(backup_file),
            ]

            env = {"PGPASSWORD": self.db_password} if self.db_password else {}

            logger.info(f"建立資料庫備份: {backup_file}")
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, check=True
            )

            if result.stderr:
                logger.warning(f"pg_dump warnings: {result.stderr}")

            # 壓縮備份文件
            if self.compression:
                compressed_file = backup_file.with_suffix(".sql.gz")
                with backup_file.open("rb") as f_in, gzip.open(compressed_file, "wb") as f_out:
                    f_out.writelines(f_in)

                backup_file.unlink()  # 刪除未壓縮的文件
                backup_file = compressed_file

            logger.info(f"備份建立成功: {backup_file}")
            return backup_file

        except subprocess.CalledProcessError as e:
            logger.error(f"pg_dump failed: {e.stderr}")
            raise Exception(f"Database backup failed: {e}") from e
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise

    async def restore_backup(self, backup_file: Path) -> bool:
        """還原資料庫備份.

        Args:
            backup_file: 備份文件路徑

        Returns:
            是否成功還原

        Raises:
            Exception: 當還原失敗時
        """
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        try:
            # 處理壓縮文件
            if backup_file.suffix == ".gz":
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".sql", delete=False
                ) as temp_file:
                    with gzip.open(backup_file, "rt") as f_in:
                        temp_file.write(f_in.read())
                    temp_backup_file = Path(temp_file.name)
            else:
                temp_backup_file = backup_file

            # 使用 psql 還原備份
            cmd = [
                "psql",
                "-h",
                self.db_host,
                "-p",
                str(self.db_port),
                "-U",
                self.db_user,
                "-d",
                self.db_name,
                "--no-password",
                "-f",
                str(temp_backup_file),
            ]

            env = {"PGPASSWORD": self.db_password} if self.db_password else {}

            logger.info(f"還原資料庫備份: {backup_file}")
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, check=True
            )

            if result.stderr:
                logger.warning(f"psql warnings: {result.stderr}")

            # 清理臨時文件
            if temp_backup_file != backup_file:
                temp_backup_file.unlink()

            logger.info(f"備份還原成功: {backup_file}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"psql failed: {e.stderr}")
            raise Exception(f"Database restore failed: {e}") from e
        except Exception as e:
            logger.error(f"Backup restore failed: {e}")
            raise

    def list_backups(self) -> list[Path]:
        """列出所有備份文件.

        Returns:
            備份文件路徑列表, 按時間排序
        """
        backup_files: list[Path] = []
        for pattern in ["*.sql", "*.sql.gz"]:
            backup_files.extend(self.backup_dir.glob(pattern))

        # 按修改時間排序
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return backup_files

    def cleanup_old_backups(self, retention_days: int = 30) -> int:
        """清理舊備份文件.

        Args:
            retention_days: 保留天數

        Returns:
            刪除的文件數量
        """
        if retention_days <= 0:
            return 0

        cutoff_time = datetime.now().timestamp() - (retention_days * 24 * 3600)
        deleted_count = 0

        for backup_file in self.list_backups():
            if backup_file.stat().st_mtime < cutoff_time:
                logger.info(f"刪除舊備份: {backup_file}")
                backup_file.unlink()
                deleted_count += 1

        return deleted_count

class DataIntegrityValidator:
    """資料完整性驗證器."""

    def __init__(self, database_url: str):
        """初始化驗證器.

        Args:
            database_url: 資料庫連接 URL
        """
        self.database_url = database_url
        self.engine: AsyncEngine | None = None

    async def __aenter__(self):
        """異步上下文管理器進入."""
        self.engine = create_async_engine(self.database_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器退出."""
        if self.engine:
            await self.engine.dispose()

    async def get_table_counts(self) -> dict[str, int]:
        """取得所有表格的記錄數量.

        Returns:
            表格名稱到記錄數量的映射
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized. Use async context manager.")

        table_counts = {}

        async with self.engine.begin() as conn:
            # 取得所有用戶表格
            result = await conn.execute(
                text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                AND table_name != 'alembic_version'
            """)
            )

            tables = [row[0] for row in result.fetchall()]

            # 計算每個表格的記錄數
            for table in tables:
                count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                table_counts[table] = count_result.scalar() or 0

        return table_counts

    async def get_table_checksums(self) -> dict[str, str]:
        """計算所有表格的資料校驗和.

        Returns:
            表格名稱到校驗和的映射
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized. Use async context manager.")

        checksums = {}

        async with self.engine.begin() as conn:
            # 取得所有用戶表格
            result = await conn.execute(
                text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                AND table_name != 'alembic_version'
            """)
            )

            tables = [row[0] for row in result.fetchall()]

            # 計算每個表格的校驗和
            for table in tables:
                checksum_result = await conn.execute(
                    text(f"""
                    SELECT md5(array_agg(md5((t.*)::text) ORDER BY (t.*))::text)
                    FROM {table} t
                """)
                )
                checksums[table] = checksum_result.scalar() or "empty_table"

        return checksums

    async def validate_foreign_keys(self) -> list[str]:
        """驗證外鍵約束.

        Returns:
            違反外鍵約束的錯誤列表
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized. Use async context manager.")

        errors = []

        async with self.engine.begin() as conn:
            # 檢查所有外鍵約束
            result = await conn.execute(
                text("""
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name,
                    tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
            """)
            )

            foreign_keys = result.fetchall()

            for fk in foreign_keys:
                table, column, ref_table, ref_column, constraint = fk

                # 檢查是否有孤立記錄
                orphan_result = await conn.execute(
                    text(f"""
                    SELECT COUNT(*)
                    FROM {table} t
                    LEFT JOIN {ref_table} r ON t.{column} = r.{ref_column}
                    WHERE t.{column} IS NOT NULL AND r.{ref_column} IS NULL
                """)
                )

                orphan_count = orphan_result.scalar() or 0
                if orphan_count > 0:
                    errors.append(
                        f"Foreign key violation in {table}.{column} -> {ref_table}.{ref_column}: "
                        f"{orphan_count} orphaned records"
                    )

        return errors

    async def compare_with_snapshot(
        self, snapshot: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """與之前的資料快照比較.

        Args:
            snapshot: 之前的資料快照

        Returns:
            (是否一致, 差異列表)
        """
        current_counts = await self.get_table_counts()
        current_checksums = await self.get_table_checksums()

        is_consistent = True
        differences = []

        # 比較記錄數量
        prev_counts = snapshot.get("table_counts", {})
        for table, current_count in current_counts.items():
            prev_count = prev_counts.get(table, 0)
            if current_count != prev_count:
                is_consistent = False
                differences.append(
                    f"Table {table} count changed: {prev_count} -> {current_count}"
                )

        # 比較校驗和
        prev_checksums = snapshot.get("table_checksums", {})
        for table, current_checksum in current_checksums.items():
            prev_checksum = prev_checksums.get(table, "")
            if current_checksum != prev_checksum:
                is_consistent = False
                differences.append(f"Table {table} data changed (checksum mismatch)")

        return is_consistent, differences

    async def create_snapshot(self) -> dict[str, Any]:
        """建立當前資料庫狀態的快照.

        Returns:
            資料庫快照
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "table_counts": await self.get_table_counts(),
            "table_checksums": await self.get_table_checksums(),
        }

async def backup_and_validate_migration(
    database_url: str, backup_dir: str = "backups", retention_days: int = 30
) -> tuple[Path, dict[str, Any]]:
    """執行遷移前的備份和驗證.

    Args:
        database_url: 資料庫連接 URL
        backup_dir: 備份目錄
        retention_days: 備份保留天數

    Returns:
        (備份文件路徑, 資料快照)

    Raises:
        Exception: 當備份或驗證失敗時
    """
    # 建立備份
    backup_manager = DatabaseBackupManager(database_url, backup_dir)
    backup_file = await backup_manager.create_backup()

    # 清理舊備份
    deleted_count = backup_manager.cleanup_old_backups(retention_days)
    if deleted_count > 0:
        logger.info(f"清理了 {deleted_count} 個舊備份文件")

    # 建立資料快照
    async with DataIntegrityValidator(database_url) as validator:
        # 驗證外鍵約束
        fk_errors = await validator.validate_foreign_keys()
        if fk_errors:
            logger.warning(f"發現外鍵約束問題: {fk_errors}")

        # 建立快照
        snapshot = await validator.create_snapshot()
        logger.info(f"建立資料快照: {len(snapshot['table_counts'])} 個表格")

    return backup_file, snapshot

async def validate_migration_success(
    database_url: str,
    pre_migration_snapshot: dict[str, Any],
    expected_changes: dict[str, int] | None = None,
) -> bool:
    """驗證遷移是否成功.

    Args:
        database_url: 資料庫連接 URL
        pre_migration_snapshot: 遷移前的資料快照
        expected_changes: 預期的資料變更

    Returns:
        是否遷移成功

    Raises:
        Exception: 當驗證失敗時
    """
    async with DataIntegrityValidator(database_url) as validator:
        # 驗證外鍵約束
        fk_errors = await validator.validate_foreign_keys()
        if fk_errors:
            logger.error(f"遷移後發現外鍵約束問題: {fk_errors}")
            return False

        # 比較資料變更
        is_consistent, differences = await validator.compare_with_snapshot(
            pre_migration_snapshot
        )

        if expected_changes:
            # 檢查預期的變更
            current_counts = await validator.get_table_counts()
            prev_counts = pre_migration_snapshot.get("table_counts", {})

            for table, expected_change in expected_changes.items():
                prev_count = prev_counts.get(table, 0)
                current_count = current_counts.get(table, 0)
                actual_change = current_count - prev_count

                if actual_change != expected_change:
                    logger.error(
                        f"Table {table}: expected change {expected_change}, "
                        f"actual change {actual_change}"
                    )
                    return False
        # 沒有預期變更, 資料應該保持一致
        elif not is_consistent:
            logger.error(f"資料不一致: {differences}")
            return False

        logger.info("遷移驗證成功")
        return True

if __name__ == "__main__":
    # 測試腳本
    async def main():
        database_url = "postgresql+asyncpg://postgres:@localhost/discord_roas_bot"

        try:
            # 建立備份和快照
            backup_file, snapshot = await backup_and_validate_migration(database_url)
            print(f"✅ 備份建立成功: {backup_file}")
            print(f"✅ 快照建立成功: {len(snapshot['table_counts'])} 個表格")

            # 執行遷移驗證 - 假設沒有資料變更
            success = await validate_migration_success(database_url, snapshot)
            print(f"✅ 遷移驗證: {'成功' if success else '失敗'}")

        except Exception as e:
            print(f"❌ 錯誤: {e}")

    asyncio.run(main())
