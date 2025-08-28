#!/usr/bin/env python3
"""
ROAS Discord Bot v2.4.4 資料庫遷移驗證腳本
==================================================

這個腳本用於驗證v2.4.4核心架構資料庫遷移的正確性。
它會執行以下檢查：
1. 資料表結構驗證
2. 索引完整性檢查  
3. 觸發器功能測試
4. 外鍵約束驗證
5. 初始資料檢查
6. 效能基準測試

使用方式:
    python validate_v2_4_4_migration.py [database_path]
"""

import os
import sys
import sqlite3
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """驗證結果數據類"""
    test_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None


class DatabaseMigrationValidator:
    """資料庫遷移驗證器"""
    
    def __init__(self, db_path: str):
        """
        初始化驗證器
        
        Args:
            db_path: 資料庫檔案路徑
        """
        self.db_path = db_path
        self.results: List[ValidationResult] = []
        
    def run_all_validations(self) -> bool:
        """
        執行所有驗證檢查
        
        Returns:
            bool: 所有測試是否通過
        """
        print(f"🔍 開始驗證資料庫遷移: {self.db_path}")
        print("=" * 60)
        
        # 執行各項驗證
        validations = [
            self.validate_database_connection,
            self.validate_table_structure,
            self.validate_indexes,
            self.validate_triggers,
            self.validate_foreign_keys,
            self.validate_initial_data,
            self.validate_data_integrity,
            self.run_performance_tests,
        ]
        
        for validation in validations:
            try:
                start_time = time.time()
                validation()
                execution_time = (time.time() - start_time) * 1000
                
                # 更新最後一個結果的執行時間
                if self.results:
                    self.results[-1].execution_time_ms = execution_time
                    
            except Exception as e:
                self.results.append(ValidationResult(
                    test_name=validation.__name__,
                    passed=False,
                    message=f"驗證過程中發生異常: {str(e)}",
                    execution_time_ms=(time.time() - start_time) * 1000 if 'start_time' in locals() else None
                ))
        
        # 輸出結果
        self.print_results()
        return self.generate_report()
    
    def validate_database_connection(self):
        """驗證資料庫連接"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
            self.results.append(ValidationResult(
                test_name="資料庫連接測試",
                passed=result is not None,
                message="資料庫連接成功" if result else "資料庫連接失敗"
            ))
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="資料庫連接測試", 
                passed=False,
                message=f"無法連接資料庫: {str(e)}"
            ))
    
    def validate_table_structure(self):
        """驗證資料表結構"""
        required_tables = {
            'sub_bots': [
                'id', 'bot_id', 'name', 'token_hash', 'target_channels',
                'ai_enabled', 'ai_model', 'personality', 'rate_limit', 'status',
                'created_at', 'updated_at', 'last_active_at', 'message_count'
            ],
            'sub_bot_channels': [
                'id', 'sub_bot_id', 'channel_id', 'channel_type',
                'permissions', 'created_at'
            ],
            'ai_conversations': [
                'id', 'user_id', 'sub_bot_id', 'provider', 'model',
                'user_message', 'ai_response', 'tokens_used', 'cost',
                'response_time', 'created_at'
            ],
            'ai_usage_quotas': [
                'id', 'user_id', 'daily_limit', 'weekly_limit', 'monthly_limit',
                'daily_used', 'weekly_used', 'monthly_used', 'total_cost_limit',
                'total_cost_used', 'last_reset_daily', 'last_reset_weekly',
                'last_reset_monthly', 'created_at', 'updated_at'
            ],
            'ai_providers': [
                'id', 'provider_name', 'api_key_hash', 'base_url', 'is_active',
                'priority', 'rate_limit_per_minute', 'cost_per_token',
                'created_at', 'updated_at'
            ],
            'deployment_logs': [
                'id', 'deployment_id', 'mode', 'status', 'environment_info',
                'error_message', 'start_time', 'end_time', 'duration_seconds',
                'created_at'
            ]
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                missing_tables = []
                incomplete_tables = {}
                
                for table_name, required_columns in required_tables.items():
                    # 檢查表是否存在
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,)
                    )
                    if not cursor.fetchone():
                        missing_tables.append(table_name)
                        continue
                    
                    # 檢查列是否完整
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    existing_columns = [row[1] for row in cursor.fetchall()]
                    
                    missing_columns = set(required_columns) - set(existing_columns)
                    if missing_columns:
                        incomplete_tables[table_name] = list(missing_columns)
                
                # 生成驗證結果
                if missing_tables or incomplete_tables:
                    details = {
                        'missing_tables': missing_tables,
                        'incomplete_tables': incomplete_tables
                    }
                    self.results.append(ValidationResult(
                        test_name="資料表結構驗證",
                        passed=False,
                        message=f"發現 {len(missing_tables)} 個缺失表格，{len(incomplete_tables)} 個不完整表格",
                        details=details
                    ))
                else:
                    self.results.append(ValidationResult(
                        test_name="資料表結構驗證",
                        passed=True,
                        message="所有必要的資料表和欄位都已正確建立"
                    ))
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="資料表結構驗證",
                passed=False,
                message=f"結構驗證失敗: {str(e)}"
            ))
    
    def validate_indexes(self):
        """驗證索引"""
        required_indexes = [
            'idx_sub_bots_bot_id', 'idx_sub_bots_status', 'idx_sub_bots_ai_enabled',
            'idx_sub_bot_channels_sub_bot_id', 'idx_sub_bot_channels_channel_id',
            'idx_ai_conversations_user_id', 'idx_ai_conversations_provider',
            'idx_ai_usage_quotas_user_id', 'idx_ai_providers_name',
            'idx_deployment_logs_deployment_id', 'idx_deployment_logs_status'
        ]
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
                existing_indexes = [row[0] for row in cursor.fetchall()]
                
                missing_indexes = []
                for index_name in required_indexes:
                    if index_name not in existing_indexes:
                        missing_indexes.append(index_name)
                
                if missing_indexes:
                    self.results.append(ValidationResult(
                        test_name="索引驗證",
                        passed=False,
                        message=f"缺少 {len(missing_indexes)} 個索引",
                        details={'missing_indexes': missing_indexes}
                    ))
                else:
                    self.results.append(ValidationResult(
                        test_name="索引驗證",
                        passed=True,
                        message="所有必要的索引都已建立"
                    ))
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="索引驗證",
                passed=False,
                message=f"索引驗證失敗: {str(e)}"
            ))
    
    def validate_triggers(self):
        """驗證觸發器功能"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 檢查觸發器是否存在
                required_triggers = [
                    'trg_sub_bots_updated_at',
                    'trg_ai_usage_quotas_updated_at', 
                    'trg_ai_providers_updated_at',
                    'trg_deployment_logs_duration'
                ]
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
                existing_triggers = [row[0] for row in cursor.fetchall()]
                
                missing_triggers = [t for t in required_triggers if t not in existing_triggers]
                
                if missing_triggers:
                    self.results.append(ValidationResult(
                        test_name="觸發器驗證",
                        passed=False,
                        message=f"缺少 {len(missing_triggers)} 個觸發器",
                        details={'missing_triggers': missing_triggers}
                    ))
                    return
                
                # 測試更新時間觸發器 - 使用更可靠的測試方法
                test_bot_id = f"test_bot_{int(time.time())}"
                cursor.execute(
                    "INSERT INTO sub_bots (bot_id, name, token_hash, target_channels) VALUES (?, ?, ?, ?)",
                    (test_bot_id, "測試機器人", "test_hash", "[]")
                )
                
                # 獲取初始時間戳
                cursor.execute(
                    "SELECT created_at, updated_at FROM sub_bots WHERE bot_id = ?",
                    (test_bot_id,)
                )
                initial_result = cursor.fetchone()
                
                # 等待足夠的時間確保時間戳會不同
                time.sleep(1.1)
                
                # 手動設置一個不同的updated_at來測試觸發器
                cursor.execute(
                    "UPDATE sub_bots SET name = ?, updated_at = ? WHERE bot_id = ?",
                    ("更新後的測試機器人", "2020-01-01 00:00:00", test_bot_id)
                )
                
                # 檢查觸發器是否覆蓋了手動設置的時間戳
                cursor.execute(
                    "SELECT created_at, updated_at FROM sub_bots WHERE bot_id = ?",
                    (test_bot_id,)
                )
                final_result = cursor.fetchone()
                
                # 清理測試資料
                cursor.execute("DELETE FROM sub_bots WHERE bot_id = ?", (test_bot_id,))
                conn.commit()
                
                # 檢查觸發器是否正常工作：
                # 1. updated_at應該不等於我們手動設置的"2020-01-01 00:00:00"
                # 2. updated_at應該是最新的時間戳
                trigger_working = (
                    final_result and 
                    final_result[1] != "2020-01-01 00:00:00" and
                    final_result[1] >= initial_result[1]
                )
                
                if trigger_working:
                    self.results.append(ValidationResult(
                        test_name="觸發器驗證",
                        passed=True,
                        message="所有觸發器正常工作",
                        details={
                            'initial_timestamps': initial_result,
                            'final_timestamps': final_result
                        }
                    ))
                else:
                    self.results.append(ValidationResult(
                        test_name="觸發器驗證", 
                        passed=False,
                        message="更新時間觸發器未正確工作",
                        details={
                            'initial_timestamps': initial_result,
                            'final_timestamps': final_result,
                            'expected_not_equal_to': "2020-01-01 00:00:00"
                        }
                    ))
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="觸發器驗證",
                passed=False,
                message=f"觸發器驗證失敗: {str(e)}"
            ))
    
    def validate_foreign_keys(self):
        """驗證外鍵約束"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # 測試sub_bot_channels的外鍵約束
                test_bot_id = f"test_bot_{int(time.time())}"
                
                # 插入測試子機器人
                cursor.execute(
                    "INSERT INTO sub_bots (bot_id, name, token_hash, target_channels) VALUES (?, ?, ?, ?)",
                    (test_bot_id, "測試機器人", "test_hash", "[]")
                )
                
                cursor.execute("SELECT id FROM sub_bots WHERE bot_id = ?", (test_bot_id,))
                sub_bot_id = cursor.fetchone()[0]
                
                # 測試有效的外鍵引用
                cursor.execute(
                    "INSERT INTO sub_bot_channels (sub_bot_id, channel_id) VALUES (?, ?)",
                    (sub_bot_id, 123456789)
                )
                
                # 測試無效的外鍵引用（應該失敗）
                try:
                    cursor.execute(
                        "INSERT INTO sub_bot_channels (sub_bot_id, channel_id) VALUES (?, ?)",
                        (99999, 987654321)  # 不存在的sub_bot_id
                    )
                    # 如果能執行到這裡，說明外鍵約束沒有生效
                    foreign_key_working = False
                except sqlite3.IntegrityError:
                    # 這是期望的結果，外鍵約束正常工作
                    foreign_key_working = True
                
                # 清理測試資料
                cursor.execute("DELETE FROM sub_bot_channels WHERE sub_bot_id = ?", (sub_bot_id,))
                cursor.execute("DELETE FROM sub_bots WHERE id = ?", (sub_bot_id,))
                conn.commit()
                
                self.results.append(ValidationResult(
                    test_name="外鍵約束驗證",
                    passed=foreign_key_working,
                    message="外鍵約束正常工作" if foreign_key_working else "外鍵約束未生效"
                ))
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="外鍵約束驗證",
                passed=False,
                message=f"外鍵約束驗證失敗: {str(e)}"
            ))
    
    def validate_initial_data(self):
        """驗證初始資料"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 檢查預設AI提供商是否已插入
                cursor.execute("SELECT COUNT(*) FROM ai_providers")
                provider_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT provider_name FROM ai_providers ORDER BY priority")
                providers = [row[0] for row in cursor.fetchall()]
                
                expected_providers = ['openai', 'anthropic', 'google']
                missing_providers = [p for p in expected_providers if p not in providers]
                
                if provider_count >= 3 and not missing_providers:
                    self.results.append(ValidationResult(
                        test_name="初始資料驗證",
                        passed=True,
                        message=f"成功插入 {provider_count} 個預設AI提供商",
                        details={'providers': providers}
                    ))
                else:
                    self.results.append(ValidationResult(
                        test_name="初始資料驗證",
                        passed=False,
                        message=f"初始資料不完整，缺少提供商: {missing_providers}",
                        details={'expected': expected_providers, 'actual': providers}
                    ))
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="初始資料驗證",
                passed=False,
                message=f"初始資料驗證失敗: {str(e)}"
            ))
    
    def validate_data_integrity(self):
        """驗證資料完整性約束"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                integrity_tests = []
                
                # 測試UNIQUE約束
                test_bot_id = f"unique_test_{int(time.time())}"
                
                # 第一次插入應該成功
                cursor.execute(
                    "INSERT INTO sub_bots (bot_id, name, token_hash, target_channels) VALUES (?, ?, ?, ?)",
                    (test_bot_id, "唯一性測試", "test_hash", "[]")
                )
                
                # 第二次插入相同bot_id應該失敗
                try:
                    cursor.execute(
                        "INSERT INTO sub_bots (bot_id, name, token_hash, target_channels) VALUES (?, ?, ?, ?)",
                        (test_bot_id, "重複機器人", "test_hash2", "[]")
                    )
                    integrity_tests.append(("UNIQUE約束", False, "允許了重複的bot_id"))
                except sqlite3.IntegrityError:
                    integrity_tests.append(("UNIQUE約束", True, "UNIQUE約束正常工作"))
                
                # 清理測試資料
                cursor.execute("DELETE FROM sub_bots WHERE bot_id = ?", (test_bot_id,))
                
                # 測試NOT NULL約束
                try:
                    cursor.execute(
                        "INSERT INTO sub_bots (bot_id, name, token_hash) VALUES (?, ?, ?)",
                        (None, "空ID測試", "test_hash")  # bot_id不能為NULL
                    )
                    integrity_tests.append(("NOT NULL約束", False, "允許了NULL值"))
                except sqlite3.IntegrityError:
                    integrity_tests.append(("NOT NULL約束", True, "NOT NULL約束正常工作"))
                
                conn.commit()
                
                # 評估整體完整性
                failed_tests = [test for test in integrity_tests if not test[1]]
                
                if not failed_tests:
                    self.results.append(ValidationResult(
                        test_name="資料完整性驗證",
                        passed=True,
                        message="所有資料完整性約束正常工作",
                        details={'tests': integrity_tests}
                    ))
                else:
                    self.results.append(ValidationResult(
                        test_name="資料完整性驗證",
                        passed=False,
                        message=f"{len(failed_tests)} 個完整性約束失敗",
                        details={'failed_tests': failed_tests, 'all_tests': integrity_tests}
                    ))
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="資料完整性驗證",
                passed=False,
                message=f"完整性驗證失敗: {str(e)}"
            ))
    
    def run_performance_tests(self):
        """執行效能基準測試"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                performance_results = {}
                
                # 測試基本查詢效能
                queries_to_test = [
                    ("子機器人ID查詢", "SELECT * FROM sub_bots WHERE bot_id = 'test_bot'"),
                    ("AI對話用戶查詢", "SELECT COUNT(*) FROM ai_conversations WHERE user_id = 123456"),
                    ("AI提供商列表", "SELECT * FROM ai_providers WHERE is_active = 1 ORDER BY priority"),
                    ("部署狀態統計", "SELECT status, COUNT(*) FROM deployment_logs GROUP BY status"),
                ]
                
                for test_name, query in queries_to_test:
                    start_time = time.time()
                    cursor.execute(query)
                    cursor.fetchall()
                    execution_time = (time.time() - start_time) * 1000
                    
                    performance_results[test_name] = {
                        'query': query,
                        'execution_time_ms': round(execution_time, 3)
                    }
                
                # 檢查是否所有查詢都在合理時間內完成（< 100ms）
                slow_queries = {name: data for name, data in performance_results.items() 
                               if data['execution_time_ms'] > 100}
                
                if not slow_queries:
                    self.results.append(ValidationResult(
                        test_name="效能基準測試",
                        passed=True,
                        message="所有查詢都在100ms內完成",
                        details=performance_results
                    ))
                else:
                    self.results.append(ValidationResult(
                        test_name="效能基準測試",
                        passed=False,
                        message=f"{len(slow_queries)} 個查詢超過100ms閾值",
                        details={'slow_queries': slow_queries, 'all_results': performance_results}
                    ))
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="效能基準測試",
                passed=False,
                message=f"效能測試失敗: {str(e)}"
            ))
    
    def print_results(self):
        """輸出驗證結果"""
        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)
        
        print(f"\n📊 驗證結果摘要:")
        print(f"   通過: {passed_count}/{total_count}")
        print(f"   失敗: {total_count - passed_count}/{total_count}")
        print(f"   成功率: {(passed_count/total_count)*100:.1f}%")
        print("\n" + "=" * 60)
        
        for result in self.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            time_info = f"({result.execution_time_ms:.1f}ms)" if result.execution_time_ms else ""
            print(f"{status} {result.test_name} {time_info}")
            print(f"      {result.message}")
            
            if result.details and not result.passed:
                print(f"      詳細信息: {json.dumps(result.details, ensure_ascii=False, indent=6)}")
            print()
    
    def generate_report(self) -> bool:
        """生成驗證報告"""
        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)
        success_rate = (passed_count / total_count) * 100 if total_count > 0 else 0
        
        report = {
            'database_path': self.db_path,
            'validation_time': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_count,
                'passed_tests': passed_count,
                'failed_tests': total_count - passed_count,
                'success_rate': success_rate
            },
            'detailed_results': [
                {
                    'test_name': r.test_name,
                    'passed': r.passed,
                    'message': r.message,
                    'execution_time_ms': r.execution_time_ms,
                    'details': r.details
                }
                for r in self.results
            ]
        }
        
        # 儲存報告到檔案
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"migration_validation_{timestamp}.json"
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"📄 驗證報告已儲存至: {report_path}")
        except Exception as e:
            print(f"⚠️  無法儲存報告: {e}")
        
        return success_rate >= 90  # 90%以上成功率視為通過


def main():
    """主函數"""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # 預設使用主資料庫
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        db_path = os.path.join(project_root, "dbs", "welcome.db")
    
    if not os.path.exists(db_path):
        print(f"❌ 資料庫檔案不存在: {db_path}")
        sys.exit(1)
    
    validator = DatabaseMigrationValidator(db_path)
    success = validator.run_all_validations()
    
    if success:
        print("🎉 資料庫遷移驗證完全成功！")
        sys.exit(0)
    else:
        print("💥 資料庫遷移驗證失敗！")
        sys.exit(1)


if __name__ == "__main__":
    main()