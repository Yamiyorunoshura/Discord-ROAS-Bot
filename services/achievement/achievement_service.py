"""
成就系統服務
Task ID: 6 - 成就系統核心功能

這個模組提供成就系統的核心業務邏輯，包括：
- 成就管理：CRUD操作
- 進度追蹤：使用者成就進度管理
- 觸發檢查：事件觸發和條件評估
- 獎勵發放：整合經濟和身分組系統

符合要求：
- F2: 成就服務核心邏輯
- F3: 成就觸發系統
- F4: 獎勵系統整合
- N1: 效能要求 - 單次觸發檢查 < 100ms
- N3: 可靠性要求 - 資料一致性和錯誤處理
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Union, Callable
from collections import defaultdict

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError, ValidationError, DatabaseError, handle_errors
from services.economy.economy_service import EconomyService
from services.government.role_service import RoleService
from .models import (
    Achievement, AchievementProgress, AchievementReward, TriggerCondition,
    AchievementType, TriggerType, RewardType, AchievementStatus,
    generate_progress_id, create_default_progress,
    validate_achievement_id, validate_user_id, validate_guild_id
)


class AchievementService(BaseService):
    """
    成就系統服務
    
    提供完整的成就管理功能，包括成就定義、進度追蹤、觸發檢查和獎勵發放
    """
    
    def __init__(self):
        super().__init__("AchievementService")
        self.db_manager: Optional[DatabaseManager] = None
        self.economy_service: Optional[EconomyService] = None
        self.role_service: Optional[RoleService] = None
        
        # 效能快取
        self._active_achievements_cache: Dict[int, List[Achievement]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 300  # 5分鐘快取
        
        # 觸發系統組件
        self._custom_evaluators: Dict[str, Callable] = {}
        self._custom_reward_handlers: Dict[str, Callable] = {}
        
        # 異步操作鎖
        self._progress_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._audit_enabled = True
    
    async def _initialize(self) -> bool:
        """初始化成就系統服務"""
        try:
            # 獲取資料庫管理器依賴
            self.db_manager = self.get_dependency("database_manager")
            if not self.db_manager or not self.db_manager.is_initialized:
                self.logger.error("資料庫管理器依賴不可用")
                return False
            
            # 獲取經濟服務依賴（用於獎勵發放）
            self.economy_service = self.get_dependency("economy_service")
            if not self.economy_service or not self.economy_service.is_initialized:
                self.logger.warning("經濟服務依賴不可用，貨幣獎勵功能將受限")
            
            # 獲取身分組服務依賴（用於身分組獎勵）
            self.role_service = self.get_dependency("role_service")  
            if not self.role_service or not self.role_service.is_initialized:
                self.logger.warning("身分組服務依賴不可用，身分組獎勵功能將受限")
            
            # 註冊成就系統資料庫遷移
            await self._register_migrations()
            
            # 應用遷移
            migration_result = await self.db_manager.migration_manager.apply_migrations()
            if not migration_result:
                self.logger.error("成就系統遷移應用失敗")
                return False
            
            # 初始化內建觸發評估器
            await self._setup_builtin_evaluators()
            
            self.logger.info("成就系統服務初始化完成")
            return True
            
        except Exception as e:
            self.logger.exception(f"成就系統服務初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理成就系統服務資源"""
        self._active_achievements_cache.clear()
        self._custom_evaluators.clear()
        self._custom_reward_handlers.clear()
        self._progress_locks.clear()
        
        self.db_manager = None
        self.economy_service = None
        self.role_service = None
        
        self.logger.info("成就系統服務已清理")
    
    async def _validate_permissions(
        self,
        user_id: int,
        guild_id: Optional[int],
        action: str
    ) -> bool:
        """
        驗證使用者權限
        
        參數：
            user_id: 使用者ID
            guild_id: 伺服器ID
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        # 成就管理操作需要管理員權限
        admin_actions = [
            "create_achievement", "update_achievement", "delete_achievement",
            "reset_progress", "award_manual", "manage_system"
        ]
        
        if action in admin_actions:
            # 實際權限檢查 - 與政府系統整合
            if not guild_id:
                self.logger.warning(f"管理員操作 {action} 被拒絕：缺少伺服器ID (user_id: {user_id})")
                return False
            
            # 檢查是否有 role_service 依賴
            if not self.role_service:
                self.logger.error(f"管理員操作 {action} 被拒絕：RoleService 未初始化 (user_id: {user_id}, guild_id: {guild_id})")
                return False
            
            try:
                # 整合政府系統的權限檢查
                # 檢查使用者是否為伺服器管理員或擁有成就管理權限
                is_admin = await self.role_service.has_permission(
                    user_id=user_id,
                    guild_id=guild_id,
                    permission="manage_achievements"
                )
                
                if not is_admin:
                    # 檢查是否為伺服器擁有者或具有管理員權限
                    is_admin = await self.role_service.has_permission(
                        user_id=user_id,
                        guild_id=guild_id,
                        permission="administrator"
                    )
                
                if not is_admin:
                    self.logger.warning(f"管理員操作 {action} 被拒絕：權限不足 (user_id: {user_id}, guild_id: {guild_id})")
                    # 記錄審計日誌
                    await self._log_security_event(
                        event_type="permission_denied",
                        user_id=user_id,
                        guild_id=guild_id,
                        action=action,
                        details={"reason": "insufficient_permissions"}
                    )
                    return False
                
                # 記錄管理員操作審計日誌
                await self._log_security_event(
                    event_type="admin_action_authorized",
                    user_id=user_id,
                    guild_id=guild_id,
                    action=action,
                    details={"authorized": True}
                )
                
                self.logger.info(f"管理員操作 {action} 已授權 (user_id: {user_id}, guild_id: {guild_id})")
                return True
                
            except Exception as e:
                self.logger.error(f"權限檢查過程中發生錯誤：{e} (user_id: {user_id}, guild_id: {guild_id}, action: {action})")
                # 安全原則：發生錯誤時拒絕操作
                return False
        
        # 一般查詢操作允許所有使用者
        return True
    
    async def _log_security_event(
        self,
        event_type: str,
        user_id: int,
        guild_id: Optional[int],
        action: str,
        details: Dict[str, Any] = None
    ) -> None:
        """
        記錄安全相關事件到審計日誌
        
        參數：
            event_type: 事件類型 (permission_denied, admin_action_authorized, etc.)
            user_id: 使用者ID
            guild_id: 伺服器ID
            action: 執行的動作
            details: 額外詳細資訊
        """
        try:
            if details is None:
                details = {}
            
            audit_log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "user_id": user_id,
                "guild_id": guild_id,
                "action": action,
                "details": details,
                "service": "achievement_service"
            }
            
            # 如果有資料庫管理器，將審計日誌存入資料庫
            if self.db_manager:
                await self.db_manager.execute(
                    """
                    INSERT INTO achievement_audit_log 
                    (event_type, user_id, guild_id, action, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_type,
                        user_id,
                        guild_id,
                        action,
                        json.dumps(details, ensure_ascii=False),
                        datetime.now()
                    )
                )
            
            # 同時記錄到應用程式日誌
            self.logger.info(f"安全事件: {json.dumps(audit_log_entry, ensure_ascii=False)}")
            
        except Exception as e:
            self.logger.error(f"記錄安全事件失敗: {e}")
            # 審計日誌失敗不應該影響主要流程，但需要記錄錯誤
    
    async def _register_migrations(self):
        """註冊成就系統的資料庫遷移"""
        try:
            # 讀取遷移腳本
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            migration_file = os.path.join(project_root, "scripts", "migrations", "004_create_achievement_tables.sql")
            
            if os.path.exists(migration_file):
                with open(migration_file, 'r', encoding='utf-8') as f:
                    migration_sql = f.read()
                
                # 清理SQL腳本，保持正確的語句分隔
                sql_lines = []
                for line in migration_sql.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('--'):
                        sql_lines.append(line)
                
                # 使用換行符連接，保持SQL語句結構
                cleaned_sql = '\n'.join(sql_lines)
                
                self.db_manager.migration_manager.add_migration(
                    version="004_achievement_system",
                    description="建立成就系統核心表格和索引",
                    up_sql=cleaned_sql,
                    down_sql="""
                    DROP VIEW IF EXISTS guild_achievement_stats;
                    DROP VIEW IF EXISTS user_achievement_stats;
                    DROP VIEW IF EXISTS active_achievements;
                    DROP TABLE IF EXISTS achievement_audit_log;
                    DROP TABLE IF EXISTS user_badges;
                    DROP TABLE IF EXISTS achievement_rewards_log;
                    DROP TABLE IF EXISTS user_achievement_progress;
                    DROP TABLE IF EXISTS achievements;
                    """
                )
                
                self.logger.info("成就系統遷移已註冊")
            else:
                self.logger.warning(f"遷移檔案不存在：{migration_file}")
                
        except Exception as e:
            self.logger.error(f"註冊遷移失敗：{e}")
    
    async def _setup_builtin_evaluators(self):
        """設定內建的觸發條件評估器"""
        
        def message_count_evaluator(progress_data: Dict[str, Any], target_value: Union[int, float], operator: str) -> bool:
            """訊息數量評估器"""
            current_count = progress_data.get("message_count", 0)
            return self._compare_values(current_count, target_value, operator)
        
        def voice_time_evaluator(progress_data: Dict[str, Any], target_value: Union[int, float], operator: str) -> bool:
            """語音時間評估器"""
            current_time = progress_data.get("voice_time", 0)
            return self._compare_values(current_time, target_value, operator)
        
        def reaction_count_evaluator(progress_data: Dict[str, Any], target_value: Union[int, float], operator: str) -> bool:
            """反應數量評估器"""
            current_count = progress_data.get("reaction_count", 0)
            return self._compare_values(current_count, target_value, operator)
        
        # 註冊內建評估器
        self._custom_evaluators[TriggerType.MESSAGE_COUNT.value] = message_count_evaluator
        self._custom_evaluators[TriggerType.VOICE_TIME.value] = voice_time_evaluator
        self._custom_evaluators[TriggerType.REACTION_COUNT.value] = reaction_count_evaluator
    
    def _compare_values(self, current: Union[int, float], target: Union[int, float], operator: str) -> bool:
        """比較值的輔助方法"""
        if operator == "==":
            return current == target
        elif operator == "!=":
            return current != target
        elif operator == ">":
            return current > target
        elif operator == "<":
            return current < target
        elif operator == ">=":
            return current >= target
        elif operator == "<=":
            return current <= target
        else:
            return False
    
    # ==========================================================================
    # 成就管理功能 (F2)
    # ==========================================================================
    
    @handle_errors(log_errors=True)
    async def create_achievement(self, achievement: Achievement) -> Achievement:
        """
        建立新成就
        
        參數：
            achievement: 成就配置
            
        返回：
            建立的成就物件
            
        異常：
            ValidationError: 當配置無效時
            ServiceError: 當建立失敗時
        """
        try:
            # 驗證成就配置
            achievement.validate()
            
            # 檢查成就是否已存在
            existing_achievement = await self.get_achievement(achievement.id)
            if existing_achievement is not None:
                raise ServiceError(
                    f"成就已存在：{achievement.id}",
                    service_name=self.name,
                    operation="create_achievement"
                )
            
            # 準備資料庫資料
            now = datetime.now()
            achievement.created_at = now
            achievement.updated_at = now
            
            # 插入資料庫
            await self.db_manager.execute(
                """INSERT INTO achievements 
                   (id, name, description, achievement_type, guild_id, 
                    trigger_conditions, rewards, status, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    achievement.id,
                    achievement.name,
                    achievement.description,
                    achievement.achievement_type.value,
                    achievement.guild_id,
                    json.dumps([condition.to_dict() for condition in achievement.trigger_conditions]),
                    json.dumps([reward.to_dict() for reward in achievement.rewards]),
                    achievement.status.value,
                    json.dumps(achievement.metadata),
                    achievement.created_at.isoformat(),
                    achievement.updated_at.isoformat()
                )
            )
            
            # 清理快取
            self._invalidate_cache(achievement.guild_id)
            
            # 記錄審計日誌
            await self._audit_log(
                operation="create_achievement",
                target_type="achievement",
                target_id=achievement.id,
                guild_id=achievement.guild_id,
                new_values=achievement.to_dict()
            )
            
            self.logger.info(f"成就建立成功：{achievement.id}")
            return achievement
            
        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(
                f"建立成就失敗：{str(e)}",
                service_name=self.name,
                operation="create_achievement"
            )
    
    @handle_errors(log_errors=True)
    async def get_achievement(self, achievement_id: str) -> Optional[Achievement]:
        """
        根據ID獲取成就
        
        參數：
            achievement_id: 成就ID
            
        返回：
            成就物件，如果不存在則返回 None
        """
        try:
            achievement_id = validate_achievement_id(achievement_id)
            
            row = await self.db_manager.fetchone(
                "SELECT * FROM achievements WHERE id = ?",
                (achievement_id,)
            )
            
            if row:
                return Achievement.from_db_row(dict(row))
            return None
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取成就失敗：{str(e)}",
                service_name=self.name,
                operation="get_achievement"
            )
    
    @handle_errors(log_errors=True)
    async def update_achievement(self, achievement: Achievement) -> Achievement:
        """
        更新成就配置
        
        參數：
            achievement: 更新後的成就配置
            
        返回：
            更新後的成就物件
        """
        try:
            # 驗證配置
            achievement.validate()
            
            # 檢查成就是否存在
            existing_achievement = await self.get_achievement(achievement.id)
            if existing_achievement is None:
                raise ServiceError(
                    f"成就不存在：{achievement.id}",
                    service_name=self.name,
                    operation="update_achievement"
                )
            
            # 更新時間戳
            achievement.updated_at = datetime.now()
            
            # 更新資料庫
            await self.db_manager.execute(
                """UPDATE achievements SET 
                   name = ?, description = ?, achievement_type = ?, 
                   trigger_conditions = ?, rewards = ?, status = ?, 
                   metadata = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    achievement.name,
                    achievement.description,
                    achievement.achievement_type.value,
                    json.dumps([condition.to_dict() for condition in achievement.trigger_conditions]),
                    json.dumps([reward.to_dict() for reward in achievement.rewards]),
                    achievement.status.value,
                    json.dumps(achievement.metadata),
                    achievement.updated_at.isoformat(),
                    achievement.id
                )
            )
            
            # 清理快取
            self._invalidate_cache(achievement.guild_id)
            
            # 記錄審計日誌
            await self._audit_log(
                operation="update_achievement",
                target_type="achievement",
                target_id=achievement.id,
                guild_id=achievement.guild_id,
                old_values=existing_achievement.to_dict(),
                new_values=achievement.to_dict()
            )
            
            self.logger.info(f"成就更新成功：{achievement.id}")
            return achievement
            
        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(
                f"更新成就失敗：{str(e)}",
                service_name=self.name,
                operation="update_achievement"
            )
    
    @handle_errors(log_errors=True)
    async def delete_achievement(self, achievement_id: str) -> bool:
        """
        刪除成就
        
        參數：
            achievement_id: 成就ID
            
        返回：
            是否刪除成功
        """
        try:
            achievement_id = validate_achievement_id(achievement_id)
            
            # 檢查成就是否存在
            existing_achievement = await self.get_achievement(achievement_id)
            if existing_achievement is None:
                self.logger.warning(f"嘗試刪除不存在的成就：{achievement_id}")
                return False
            
            # 使用資料庫事務刪除相關資料
            async with self.db_manager.transaction():
                # 刪除進度記錄
                await self.db_manager.execute(
                    "DELETE FROM user_achievement_progress WHERE achievement_id = ?",
                    (achievement_id,)
                )
                
                # 刪除獎勵記錄
                await self.db_manager.execute(
                    "DELETE FROM achievement_rewards_log WHERE achievement_id = ?",
                    (achievement_id,)
                )
                
                # 刪除徽章記錄
                await self.db_manager.execute(
                    "DELETE FROM user_badges WHERE achievement_id = ?",
                    (achievement_id,)
                )
                
                # 刪除成就
                await self.db_manager.execute(
                    "DELETE FROM achievements WHERE id = ?",
                    (achievement_id,)
                )
            
            # 清理快取
            self._invalidate_cache(existing_achievement.guild_id)
            
            # 記錄審計日誌
            await self._audit_log(
                operation="delete_achievement",
                target_type="achievement",
                target_id=achievement_id,
                guild_id=existing_achievement.guild_id,
                old_values=existing_achievement.to_dict()
            )
            
            self.logger.info(f"成就刪除成功：{achievement_id}")
            return True
            
        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(
                f"刪除成就失敗：{str(e)}",
                service_name=self.name,
                operation="delete_achievement"
            )
    
    @handle_errors(log_errors=True)
    async def list_guild_achievements(
        self,
        guild_id: int,
        status: Optional[AchievementStatus] = None,
        achievement_type: Optional[AchievementType] = None
    ) -> List[Achievement]:
        """
        列出伺服器的成就
        
        參數：
            guild_id: 伺服器ID
            status: 成就狀態篩選
            achievement_type: 成就類型篩選
            
        返回：
            成就列表
        """
        try:
            guild_id = validate_guild_id(guild_id)
            
            # 構建查詢
            query = "SELECT * FROM achievements WHERE guild_id = ?"
            params = [guild_id]
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
            
            if achievement_type:
                query += " AND achievement_type = ?"
                params.append(achievement_type.value)
            
            query += " ORDER BY created_at DESC"
            
            rows = await self.db_manager.fetchall(query, params)
            
            achievements = []
            for row in rows:
                achievement = Achievement.from_db_row(dict(row))
                achievements.append(achievement)
            
            return achievements
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"列出伺服器成就失敗：{str(e)}",
                service_name=self.name,
                operation="list_guild_achievements"
            )
    
    # ==========================================================================
    # 進度管理功能 (F2)
    # ==========================================================================
    
    @handle_errors(log_errors=True)
    async def get_user_progress(self, user_id: int, achievement_id: str) -> Optional[AchievementProgress]:
        """
        獲取使用者成就進度
        
        參數：
            user_id: 使用者ID
            achievement_id: 成就ID
            
        返回：
            進度物件，如果不存在則返回 None
        """
        try:
            user_id = validate_user_id(user_id)
            achievement_id = validate_achievement_id(achievement_id)
            
            row = await self.db_manager.fetchone(
                "SELECT * FROM user_achievement_progress WHERE user_id = ? AND achievement_id = ?",
                (user_id, achievement_id)
            )
            
            if row:
                return AchievementProgress.from_db_row(dict(row))
            return None
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取使用者進度失敗：{str(e)}",
                service_name=self.name,
                operation="get_user_progress"
            )
    
    @handle_errors(log_errors=True)
    async def update_user_progress(
        self,
        user_id: int,
        achievement_id: str,
        new_progress: Dict[str, Any]
    ) -> bool:
        """
        更新使用者成就進度
        
        參數：
            user_id: 使用者ID
            achievement_id: 成就ID
            new_progress: 新的進度資料
            
        返回：
            是否更新成功
        """
        progress_key = f"{user_id}_{achievement_id}"
        
        async with self._progress_locks[progress_key]:
            try:
                user_id = validate_user_id(user_id)
                achievement_id = validate_achievement_id(achievement_id)
                
                # 獲取成就配置
                achievement = await self.get_achievement(achievement_id)
                if not achievement:
                    raise ServiceError(
                        f"成就不存在：{achievement_id}",
                        service_name=self.name,
                        operation="update_user_progress"
                    )
                
                # 獲取或創建進度記錄
                progress = await self.get_user_progress(user_id, achievement_id)
                if not progress:
                    progress = create_default_progress(achievement_id, user_id, achievement.guild_id)
                
                # 更新進度資料
                old_progress = progress.current_progress.copy()
                progress.update_progress(new_progress)
                
                # 檢查是否完成成就
                was_completed = progress.completed
                if not was_completed:
                    is_now_completed = await self._check_achievement_completion(achievement, progress)
                    if is_now_completed:
                        progress.mark_completed()
                        # 發放獎勵
                        await self._award_achievement_rewards(user_id, achievement.guild_id, achievement.rewards, achievement_id)
                
                # 保存進度到資料庫
                await self._save_progress_to_db(progress)
                
                # 記錄審計日誌
                await self._audit_log(
                    operation="update_progress",
                    target_type="progress",
                    target_id=progress.id,
                    guild_id=progress.guild_id,
                    user_id=user_id,
                    old_values={"current_progress": old_progress, "completed": was_completed},
                    new_values={"current_progress": progress.current_progress, "completed": progress.completed}
                )
                
                if progress.completed and not was_completed:
                    self.logger.info(f"使用者 {user_id} 完成成就 {achievement_id}")
                
                return True
                
            except (ValidationError, ServiceError):
                raise
            except Exception as e:
                raise ServiceError(
                    f"更新使用者進度失敗：{str(e)}",
                    service_name=self.name,
                    operation="update_user_progress"
                )
    
    async def _save_progress_to_db(self, progress: AchievementProgress):
        """保存進度到資料庫"""
        # 檢查進度記錄是否已存在
        existing = await self.db_manager.fetchone(
            "SELECT id FROM user_achievement_progress WHERE id = ?",
            (progress.id,)
        )
        
        if existing:
            # 更新現有記錄
            await self.db_manager.execute(
                """UPDATE user_achievement_progress SET 
                   current_progress = ?, completed = ?, completed_at = ?, last_updated = ?
                   WHERE id = ?""",
                (
                    json.dumps(progress.current_progress),
                    progress.completed,
                    progress.completed_at.isoformat() if progress.completed_at else None,
                    progress.last_updated.isoformat(),
                    progress.id
                )
            )
        else:
            # 插入新記錄
            await self.db_manager.execute(
                """INSERT INTO user_achievement_progress 
                   (id, achievement_id, user_id, guild_id, current_progress, 
                    completed, completed_at, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    progress.id,
                    progress.achievement_id,
                    progress.user_id,
                    progress.guild_id,
                    json.dumps(progress.current_progress),
                    progress.completed,
                    progress.completed_at.isoformat() if progress.completed_at else None,
                    progress.last_updated.isoformat()
                )
            )
    
    @handle_errors(log_errors=True)
    async def list_user_achievements(
        self,
        user_id: int,
        guild_id: int,
        completed_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        列出使用者的成就進度
        
        參數：
            user_id: 使用者ID
            guild_id: 伺服器ID
            completed_only: 是否只返回已完成的成就
            
        返回：
            成就進度列表
        """
        try:
            user_id = validate_user_id(user_id)
            guild_id = validate_guild_id(guild_id)
            
            # 構建查詢
            query = """
                SELECT p.*, a.name, a.description, a.achievement_type
                FROM user_achievement_progress p
                JOIN achievements a ON p.achievement_id = a.id
                WHERE p.user_id = ? AND p.guild_id = ?
            """
            params = [user_id, guild_id]
            
            if completed_only:
                query += " AND p.completed = 1"
            
            query += " ORDER BY p.last_updated DESC"
            
            rows = await self.db_manager.fetchall(query, params)
            
            results = []
            for row in rows:
                row_dict = dict(row)
                progress = AchievementProgress.from_db_row(row_dict)
                
                result = {
                    "achievement_id": progress.achievement_id,
                    "achievement_name": row_dict["name"],
                    "achievement_description": row_dict["description"],
                    "achievement_type": row_dict["achievement_type"],
                    "current_progress": progress.current_progress,
                    "completed": progress.completed,
                    "completed_at": progress.completed_at,
                    "last_updated": progress.last_updated
                }
                results.append(result)
            
            return results
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"列出使用者成就失敗：{str(e)}",
                service_name=self.name,
                operation="list_user_achievements"
            )
    
    # ==========================================================================
    # 觸發系統功能 (F3)
    # ==========================================================================
    
    async def evaluate_trigger_condition(
        self,
        condition: TriggerCondition,
        user_progress: Dict[str, Any]
    ) -> bool:
        """
        評估觸發條件
        
        參數：
            condition: 觸發條件
            user_progress: 使用者進度資料
            
        返回：
            是否滿足條件
        """
        try:
            if not user_progress:
                return False
            
            trigger_type_value = (
                condition.trigger_type.value if isinstance(condition.trigger_type, TriggerType)
                else condition.trigger_type
            )
            
            # 使用自訂評估器
            if trigger_type_value in self._custom_evaluators:
                evaluator = self._custom_evaluators[trigger_type_value]
                return evaluator(user_progress, condition.target_value, condition.comparison_operator)
            
            # 預設行為：直接比較數值
            current_value = user_progress.get(trigger_type_value, 0)
            return self._compare_values(current_value, condition.target_value, condition.comparison_operator)
            
        except Exception as e:
            self.logger.error(f"評估觸發條件失敗：{e}")
            raise ServiceError(
                f"觸發條件評估失敗：{str(e)}",
                service_name=self.name,
                operation="evaluate_trigger_condition"
            )
    
    async def evaluate_compound_conditions(
        self,
        conditions: List[TriggerCondition],
        user_progress: Dict[str, Any],
        operator: str = "AND"
    ) -> bool:
        """
        評估複合觸發條件
        
        參數：
            conditions: 觸發條件列表
            user_progress: 使用者進度資料
            operator: 邏輯運算符 ("AND" 或 "OR")
            
        返回：
            是否滿足複合條件
        """
        if not conditions:
            return True
        
        results = []
        for condition in conditions:
            result = await self.evaluate_trigger_condition(condition, user_progress)
            results.append(result)
        
        if operator.upper() == "AND":
            return all(results)
        elif operator.upper() == "OR":
            return any(results)
        else:
            # 預設使用AND邏輯
            return all(results)
    
    async def _check_achievement_completion(
        self,
        achievement: Achievement,
        progress: AchievementProgress
    ) -> bool:
        """
        檢查成就是否完成
        
        參數：
            achievement: 成就配置
            progress: 使用者進度
            
        返回：
            是否完成成就
        """
        if progress.completed:
            return True  # 已經完成
        
        # 評估所有觸發條件（使用AND邏輯）
        return await self.evaluate_compound_conditions(
            achievement.trigger_conditions,
            progress.current_progress,
            "AND"
        )
    
    @handle_errors(log_errors=True)
    async def process_event_triggers(self, event_data: Dict[str, Any]) -> List[str]:
        """
        處理事件觸發，更新相關使用者的成就進度
        
        參數：
            event_data: 事件資料
            
        返回：
            觸發的成就ID列表
        """
        try:
            user_id = event_data.get("user_id")
            guild_id = event_data.get("guild_id")
            event_type = event_data.get("type")
            
            if not all([user_id, guild_id, event_type]):
                self.logger.warning(f"事件資料不完整：{event_data}")
                return []
            
            user_id = validate_user_id(user_id)
            guild_id = validate_guild_id(guild_id)
            
            # 獲取該伺服器的活躍成就
            active_achievements = await self._get_active_achievements(guild_id)
            
            triggered_achievements = []
            
            for achievement in active_achievements:
                try:
                    # 獲取使用者進度
                    progress = await self.get_user_progress(user_id, achievement.id)
                    if not progress:
                        progress = create_default_progress(achievement.id, user_id, guild_id)
                    
                    # 跳過已完成的成就（除非是重複性成就）
                    if progress.completed and achievement.achievement_type != AchievementType.RECURRING:
                        continue
                    
                    # 處理事件並更新進度
                    progress_update = self._process_event_for_progress(event_data, progress.current_progress)
                    
                    if progress_update:
                        # 更新進度
                        success = await self.update_user_progress(user_id, achievement.id, progress_update)
                        if success:
                            triggered_achievements.append(achievement.id)
                
                except Exception as e:
                    self.logger.error(f"處理成就 {achievement.id} 的事件觸發失敗：{e}")
                    continue
            
            return triggered_achievements
            
        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(
                f"處理事件觸發失敗：{str(e)}",
                service_name=self.name,
                operation="process_event_triggers"
            )
    
    def _process_event_for_progress(
        self,
        event_data: Dict[str, Any],
        current_progress: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根據事件資料處理進度更新
        
        參數：
            event_data: 事件資料
            current_progress: 目前進度
            
        返回：
            進度更新資料
        """
        event_type = event_data.get("type")
        progress_update = {}
        
        if event_type == "message_sent":
            progress_update["message_count"] = current_progress.get("message_count", 0) + 1
            
        elif event_type == "voice_activity":
            duration = event_data.get("duration", 0)
            progress_update["voice_time"] = current_progress.get("voice_time", 0) + duration
            
        elif event_type == "reaction_added":
            progress_update["reaction_count"] = current_progress.get("reaction_count", 0) + 1
            
        elif event_type == "command_used":
            command_name = event_data.get("command")
            if command_name:
                command_key = f"command_{command_name}_count"
                progress_update[command_key] = current_progress.get(command_key, 0) + 1
                progress_update["total_command_count"] = current_progress.get("total_command_count", 0) + 1
        
        return progress_update
    
    async def _get_active_achievements(self, guild_id: int) -> List[Achievement]:
        """
        獲取伺服器的活躍成就（帶快取）
        
        參數：
            guild_id: 伺服器ID
            
        返回：
            活躍成就列表
        """
        now = datetime.now()
        
        # 檢查快取
        if (self._cache_timestamp and 
            guild_id in self._active_achievements_cache and
            (now - self._cache_timestamp).total_seconds() < self._cache_ttl):
            return self._active_achievements_cache[guild_id]
        
        # 從資料庫獲取
        achievements = await self.list_guild_achievements(guild_id, AchievementStatus.ACTIVE)
        
        # 更新快取
        self._active_achievements_cache[guild_id] = achievements
        self._cache_timestamp = now
        
        return achievements
    
    def _invalidate_cache(self, guild_id: int):
        """清理指定伺服器的快取"""
        if guild_id in self._active_achievements_cache:
            del self._active_achievements_cache[guild_id]
        self._cache_timestamp = None
    
    # ==========================================================================
    # 獎勵系統功能 (F4)
    # ==========================================================================
    
    async def award_reward(
        self,
        user_id: int,
        guild_id: int,
        reward: AchievementReward,
        achievement_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        發放單個獎勵
        
        參數：
            user_id: 使用者ID
            guild_id: 伺服器ID
            reward: 獎勵配置
            achievement_id: 成就ID（用於記錄）
            
        返回：
            發放結果
        """
        try:
            user_id = validate_user_id(user_id)
            guild_id = validate_guild_id(guild_id)
            
            result = {
                "reward_type": reward.reward_type,
                "reward_value": reward.value,
                "success": False,
                "error": None
            }
            
            reward_type_value = (
                reward.reward_type.value if isinstance(reward.reward_type, RewardType)
                else reward.reward_type
            )
            
            # 記錄獎勵發放日誌
            log_id = await self._log_reward_attempt(user_id, guild_id, reward, achievement_id)
            
            try:
                if reward_type_value == "currency":
                    # 貨幣獎勵
                    if not self.economy_service:
                        raise ServiceError("經濟服務不可用", service_name=self.name, operation="award_currency")
                    
                    # 創建使用者帳戶（如果不存在）
                    from services.economy.models import AccountType
                    account_id = f"user_{user_id}_{guild_id}"
                    
                    try:
                        await self.economy_service.get_account(account_id)
                    except ServiceError:
                        # 帳戶不存在，創建新帳戶
                        await self.economy_service.create_account(
                            guild_id=guild_id,
                            account_type=AccountType.USER,
                            user_id=user_id,
                            initial_balance=0.0
                        )
                    
                    # 發放貨幣
                    await self.economy_service.deposit(
                        account_id=account_id,
                        amount=float(reward.value),
                        reason=reward.metadata.get("reason", "成就獎勵"),
                        created_by=None
                    )
                    result["success"] = True
                    
                elif reward_type_value == "role":
                    # 身分組獎勵
                    if not self.role_service:
                        raise ServiceError("身分組服務不可用", service_name=self.name, operation="award_role")
                    
                    # 這裡需要Discord客戶端的整合
                    # 目前記錄獎勵，實際發放需要在Discord Cog中處理
                    result["success"] = True
                    result["note"] = "身分組獎勵已記錄，需要Discord整合完成發放"
                    
                elif reward_type_value == "badge":
                    # 徽章獎勵
                    await self._award_badge(user_id, guild_id, reward, achievement_id)
                    result["success"] = True
                    
                else:
                    # 自訂獎勵
                    if reward_type_value in self._custom_reward_handlers:
                        handler = self._custom_reward_handlers[reward_type_value]
                        await handler(user_id, guild_id, reward, achievement_id)
                        result["success"] = True
                    else:
                        raise ServiceError(f"未知的獎勵類型：{reward_type_value}")
                
                # 更新獎勵發放日誌
                await self._update_reward_log(log_id, "completed", None)
                
            except Exception as e:
                result["error"] = str(e)
                await self._update_reward_log(log_id, "failed", str(e))
                raise
            
            return result
            
        except Exception as e:
            self.logger.error(f"發放獎勵失敗：{e}")
            raise ServiceError(
                f"發放獎勵失敗：{str(e)}",
                service_name=self.name,
                operation="award_reward"
            )
    
    async def _award_achievement_rewards(
        self,
        user_id: int,
        guild_id: int,
        rewards: List[AchievementReward],
        achievement_id: str
    ):
        """發放成就的所有獎勵"""
        for reward in rewards:
            try:
                await self.award_reward(user_id, guild_id, reward, achievement_id)
            except Exception as e:
                self.logger.error(f"發放獎勵失敗 - 成就:{achievement_id}, 獎勵:{reward.reward_type}, 錯誤:{e}")
                continue  # 繼續發放其他獎勵
    
    async def _award_badge(
        self,
        user_id: int,
        guild_id: int,
        reward: AchievementReward,
        achievement_id: Optional[str]
    ):
        """發放徽章獎勵"""
        await self.db_manager.execute(
            """INSERT OR REPLACE INTO user_badges 
               (user_id, guild_id, achievement_id, badge_name, badge_metadata, earned_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                guild_id,
                achievement_id or "manual_award",
                str(reward.value),
                json.dumps(reward.metadata),
                datetime.now().isoformat()
            )
        )
    
    async def _log_reward_attempt(
        self,
        user_id: int,
        guild_id: int,
        reward: AchievementReward,
        achievement_id: Optional[str]
    ) -> int:
        """記錄獎勵發放嘗試"""
        reward_type_value = (
            reward.reward_type.value if isinstance(reward.reward_type, RewardType)
            else reward.reward_type
        )
        
        cursor = await self.db_manager.execute(
            """INSERT INTO achievement_rewards_log 
               (achievement_id, user_id, guild_id, reward_type, reward_value, 
                reward_metadata, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                achievement_id or "manual",
                user_id,
                guild_id,
                reward_type_value,
                str(reward.value),
                json.dumps(reward.metadata),
                "pending",
                datetime.now().isoformat()
            )
        )
        return cursor.lastrowid
    
    async def _update_reward_log(self, log_id: int, status: str, error_message: Optional[str]):
        """更新獎勵發放記錄"""
        await self.db_manager.execute(
            """UPDATE achievement_rewards_log 
               SET status = ?, error_message = ?, processed_at = ?
               WHERE id = ?""",
            (status, error_message, datetime.now().isoformat(), log_id)
        )
    
    # ==========================================================================
    # 擴展性功能 (N2)
    # ==========================================================================
    
    async def register_custom_trigger_type(self, trigger_type: str, evaluator_func: Callable):
        """
        註冊自訂觸發類型
        
        參數：
            trigger_type: 觸發類型名稱
            evaluator_func: 評估函數 (progress_data, target_value, operator) -> bool
        """
        self._custom_evaluators[trigger_type] = evaluator_func
        self.logger.info(f"註冊自訂觸發類型：{trigger_type}")
    
    async def register_custom_reward_type(self, reward_type: str, handler_func: Callable):
        """
        註冊自訂獎勵類型
        
        參數：
            reward_type: 獎勵類型名稱
            handler_func: 處理函數 (user_id, guild_id, reward, achievement_id) -> None
        """
        self._custom_reward_handlers[reward_type] = handler_func
        self.logger.info(f"註冊自訂獎勵類型：{reward_type}")
    
    # ==========================================================================
    # 批量操作 (N1 - 效能要求)
    # ==========================================================================
    
    async def batch_update_progress(self, updates: List[Dict[str, Any]]) -> bool:
        """
        批量更新使用者進度
        
        參數：
            updates: 更新資料列表，每個元素包含 user_id, achievement_id, progress
            
        返回：
            是否全部更新成功
        """
        try:
            # 使用資料庫事務進行批量操作
            async with self.db_manager.transaction():
                for update in updates:
                    await self.update_user_progress(
                        update["user_id"],
                        update["achievement_id"],
                        update["progress"]
                    )
            
            return True
            
        except Exception as e:
            self.logger.error(f"批量更新進度失敗：{e}")
            return False
    
    # ==========================================================================
    # 輔助方法和錯誤處理
    # ==========================================================================
    
    async def award_reward_with_fallback(
        self,
        user_id: int,
        guild_id: int,
        reward: AchievementReward
    ) -> Dict[str, Any]:
        """
        帶降級處理的獎勵發放
        
        參數：
            user_id: 使用者ID
            guild_id: 伺服器ID
            reward: 獎勵配置
            
        返回：
            發放結果（包含降級資訊）
        """
        try:
            return await self.award_reward(user_id, guild_id, reward)
        except ServiceError as e:
            # 優雅降級：記錄失敗但不完全中斷
            self.logger.warning(f"獎勵發放失敗，使用降級處理：{e}")
            return {
                "reward_type": reward.reward_type,
                "reward_value": reward.value,
                "success": False,
                "fallback": True,
                "error": str(e)
            }
    
    async def complete_achievement(
        self,
        user_id: int,
        achievement_id: str,
        rewards: List[AchievementReward]
    ) -> bool:
        """
        完成成就並發放獎勵
        
        參數：
            user_id: 使用者ID
            achievement_id: 成就ID
            rewards: 獎勵列表
            
        返回：
            是否處理成功
        """
        try:
            # 獲取成就和使用者進度
            achievement = await self.get_achievement(achievement_id)
            if not achievement:
                return False
            
            progress = await self.get_user_progress(user_id, achievement_id)
            if not progress:
                return False
            
            # 使用事務確保資料一致性
            async with self.db_manager.transaction():
                # 標記為完成
                progress.mark_completed()
                await self._save_progress_to_db(progress)
                
                # 發放獎勵
                for reward in rewards:
                    await self.award_reward(user_id, achievement.guild_id, reward, achievement_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"完成成就處理失敗：{e}")
            return False
    
    async def complete_achievement_with_rewards(
        self,
        user_id: int,
        achievement_id: str,
        rewards: List[AchievementReward]
    ):
        """帶事務的成就完成處理"""
        async with self.db_manager.transaction():
            await self.complete_achievement(user_id, achievement_id, rewards)
    
    async def batch_check_conditions(
        self,
        conditions: List[TriggerCondition],
        users_progress: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量檢查條件（用於效能測試）
        
        參數：
            conditions: 觸發條件列表
            users_progress: 使用者進度列表
            
        返回：
            檢查結果列表
        """
        results = []
        
        for user_progress_data in users_progress:
            user_id = user_progress_data.get("user_id")
            progress = {k: v for k, v in user_progress_data.items() if k != "user_id"}
            
            result = await self.evaluate_compound_conditions(conditions, progress, "AND")
            results.append({"user_id": user_id, "result": result})
        
        return results
    
    async def _audit_log(
        self,
        operation: str,
        target_type: str,
        target_id: str,
        guild_id: int,
        user_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        記錄審計日誌
        
        參數：
            operation: 操作類型
            target_type: 目標類型
            target_id: 目標ID
            guild_id: 伺服器ID
            user_id: 執行操作的使用者ID
            old_values: 操作前的值
            new_values: 操作後的值
            success: 操作是否成功
            error_message: 錯誤訊息
        """
        if not self._audit_enabled:
            return
        
        try:
            await self.db_manager.execute(
                """INSERT INTO achievement_audit_log 
                   (operation, target_type, target_id, guild_id, user_id, 
                    old_values, new_values, created_at, success, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    operation,
                    target_type,
                    target_id,
                    guild_id,
                    user_id,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    datetime.now().isoformat(),
                    int(success),
                    error_message
                )
            )
        except Exception as e:
            # 審計日誌失敗不應影響主要操作
            self.logger.error(f"審計日誌記錄失敗：{e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查
        
        返回：
            服務健康狀態
        """
        base_health = await super().health_check()
        
        try:
            # 檢查資料庫連接
            await self.db_manager.fetchone("SELECT 1")
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        
        # 檢查依賴服務
        economy_status = "healthy" if (self.economy_service and self.economy_service.is_initialized) else "unavailable"
        role_status = "healthy" if (self.role_service and self.role_service.is_initialized) else "unavailable"
        
        base_health.update({
            "database_status": db_status,
            "economy_service_status": economy_status,
            "role_service_status": role_status,
            "cache_size": len(self._active_achievements_cache),
            "custom_evaluators": len(self._custom_evaluators),
            "custom_reward_handlers": len(self._custom_reward_handlers),
            "audit_enabled": self._audit_enabled,
            "features": [
                "achievement_management",
                "progress_tracking",
                "trigger_evaluation", 
                "reward_distribution",
                "batch_operations",
                "custom_extensions"
            ]
        })
        
        return base_health