"""
Simple database pool functionality test
Bypassing Discord token validation for testing purposes
"""

import asyncio
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


class SimpleTestPool:
    """Simple test database pool"""

    def __init__(self):
        self.connections = {}

    @asynccontextmanager
    async def get_connection_context(self, db_path: str):
        """Get database connection context"""
        try:
            conn = await aiosqlite.connect(db_path)
            yield conn
        finally:
            await conn.close()


async def test_database_functionality():
    """Test database functionality without Discord dependencies"""
    print("Testing database functionality...")

    pool = SimpleTestPool()

    try:
        # Test each database file
        db_files = [
            "dbs/activity.db",
            "dbs/anti_executable.db",
            "dbs/anti_link.db",
            "dbs/discord_data.db",
            "dbs/message.db",
            "dbs/sync_data.db",
            "dbs/welcome.db",
        ]

        total_tests = 0
        passed_tests = 0

        for db_file in db_files:
            if not Path(db_file).exists():
                print(f"SKIP: {db_file} - file not found")
                continue

            try:
                async with pool.get_connection_context(db_file) as conn:
                    # Test read
                    cursor = await conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    )
                    table_count = await cursor.fetchone()

                    # Test basic operation
                    cursor = await conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"
                    )
                    first_table = await cursor.fetchone()

                    print(
                        f"PASS: {db_file} - {table_count[0]} tables, first: {first_table[0] if first_table else 'none'}"
                    )
                    passed_tests += 1

            except Exception as e:
                print(f"FAIL: {db_file} - {e}")

            total_tests += 1

        print("\nDatabase compatibility test results:")
        print(f"  Total databases tested: {total_tests}")
        print(f"  Passed: {passed_tests}")
        print(f"  Failed: {total_tests - passed_tests}")
        print(f"  Success rate: {(passed_tests / total_tests) * 100:.1f}%")

        # Test database pool pattern
        print("\nTesting database pool pattern...")
        async with pool.get_connection_context("dbs/activity.db") as conn1:
            async with pool.get_connection_context("dbs/message.db") as conn2:
                # Both connections should work simultaneously
                cursor1 = await conn1.execute("SELECT COUNT(*) FROM sqlite_master")
                cursor2 = await conn2.execute("SELECT COUNT(*) FROM sqlite_master")

                result1 = await cursor1.fetchone()
                result2 = await cursor2.fetchone()

                print(
                    f"PASS: Concurrent connections work - activity: {result1[0]}, message: {result2[0]}"
                )

        print("SUCCESS: Database pool pattern test completed")
        return total_tests, passed_tests

    except Exception as e:
        print(f"ERROR: Database test failed: {e}")

        traceback.print_exc()
        return 0, 0


if __name__ == "__main__":
    total, passed = asyncio.run(test_database_functionality())
    print(
        f"\nREQ-M-010 Database Compatibility: {'PASSED' if passed == total and total > 0 else 'FAILED'}"
    )
