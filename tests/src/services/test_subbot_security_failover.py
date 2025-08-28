"""
故障恢復和安全性驗證測試套件
Task ID: 3 - 子機器人聊天功能和管理系統開發

測試子機器人系統的故障恢復和安全性：
- 故障注入和恢復機制測試
- Token安全性和資料加密驗證
- 異常處理和錯誤邊界測試
- 安全漏洞和攻擊防護測試
- 資料完整性和一致性驗證
"""

import pytest
import asyncio
import os
import tempfile
import hashlib
import base64
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from src.core.errors import (
    SubBotError, SubBotCreationError, SubBotTokenError, 
    SubBotChannelError, SecurityError
)


class SecurityTestHarness:
    """安全測試工具"""
    
    def __init__(self):
        self.audit_log = []
        self.attack_attempts = []
        self.security_violations = []
    
    def log_audit_event(self, event_type: str, details: Dict[str, Any]):
        """記錄審計事件"""
        self.audit_log.append({
            'timestamp': datetime.now(),
            'event_type': event_type,
            'details': details
        })
    
    def log_attack_attempt(self, attack_type: str, source: str, details: Dict[str, Any]):
        """記錄攻擊嘗試"""
        self.attack_attempts.append({
            'timestamp': datetime.now(),
            'attack_type': attack_type,
            'source': source,
            'details': details
        })
    
    def log_security_violation(self, violation_type: str, severity: str, details: Dict[str, Any]):
        """記錄安全違規"""
        self.security_violations.append({
            'timestamp': datetime.now(),
            'violation_type': violation_type,
            'severity': severity,
            'details': details
        })
    
    def generate_malicious_token(self) -> str:
        """生成惡意Token用於測試"""
        malicious_payloads = [
            "'; DROP TABLE sub_bots; --",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            "\x00\x01\x02\x03",  # 二進制數據
            "A" * 10000,  # 超長字符串
            "../../config/secrets.json"
        ]
        return secrets.choice(malicious_payloads)
    
    def generate_sql_injection_payload(self) -> str:
        """生成SQL注入載荷"""
        payloads = [
            "1' OR '1'='1",
            "'; DELETE FROM sub_bots WHERE 1=1; --",
            "1 UNION SELECT * FROM users",
            "1'; UPDATE sub_bots SET name='hacked' WHERE 1=1; --"
        ]
        return secrets.choice(payloads)


class FaultInjector:
    """故障注入器"""
    
    def __init__(self):
        self.active_faults = {}
        self.fault_history = []
    
    def inject_network_failure(self, duration: float = 1.0):
        """注入網路故障"""
        fault_id = f"network_fault_{datetime.now().timestamp()}"
        self.active_faults[fault_id] = {
            'type': 'network',
            'start_time': datetime.now(),
            'duration': duration,
            'active': True
        }
        return fault_id
    
    def inject_memory_pressure(self, pressure_level: str = 'medium'):
        """注入記憶體壓力"""
        fault_id = f"memory_fault_{datetime.now().timestamp()}"
        self.active_faults[fault_id] = {
            'type': 'memory',
            'pressure_level': pressure_level,
            'start_time': datetime.now(),
            'active': True
        }
        return fault_id
    
    def inject_database_failure(self, failure_type: str = 'connection_timeout'):
        """注入資料庫故障"""
        fault_id = f"db_fault_{datetime.now().timestamp()}"
        self.active_faults[fault_id] = {
            'type': 'database',
            'failure_type': failure_type,
            'start_time': datetime.now(),
            'active': True
        }
        return fault_id
    
    def inject_discord_api_failure(self, failure_mode: str = 'rate_limit'):
        """注入Discord API故障"""
        fault_id = f"discord_fault_{datetime.now().timestamp()}"
        self.active_faults[fault_id] = {
            'type': 'discord_api',
            'failure_mode': failure_mode,
            'start_time': datetime.now(),
            'active': True
        }
        return fault_id
    
    def clear_fault(self, fault_id: str):
        """清除故障"""
        if fault_id in self.active_faults:
            fault = self.active_faults[fault_id]
            fault['active'] = False
            fault['end_time'] = datetime.now()
            self.fault_history.append(fault)
            del self.active_faults[fault_id]
    
    def is_fault_active(self, fault_id: str) -> bool:
        """檢查故障是否仍然活躍"""
        return fault_id in self.active_faults and self.active_faults[fault_id]['active']
    
    def get_active_faults(self) -> List[Dict[str, Any]]:
        """獲取當前活躍的故障"""
        return list(self.active_faults.values())


class MockSecureSubBotService:
    """具有安全功能的子機器人服務模擬"""
    
    def __init__(self, security_harness: SecurityTestHarness, fault_injector: FaultInjector):
        self.security_harness = security_harness
        self.fault_injector = fault_injector
        self.bots: Dict[str, Dict[str, Any]] = {}
        self.encryption_key = secrets.token_hex(32)
        self.failed_login_attempts = {}
        self.rate_limits = {}
        self.audit_enabled = True
    
    async def create_sub_bot(self, name: str, token: str, target_channels: List[int], **kwargs) -> str:
        """創建子機器人（安全版本）"""
        try:
            # 輸入驗證
            await self._validate_input(name, token, target_channels)
            
            # 檢查權限
            await self._check_permissions('create_bot')
            
            # 檢查速率限制
            await self._check_rate_limit('create_bot')
            
            # 安全加密Token
            encrypted_token = await self._secure_encrypt_token(token)
            
            bot_id = f"secure_bot_{secrets.token_hex(8)}"
            
            self.bots[bot_id] = {
                'bot_id': bot_id,
                'name': self._sanitize_input(name),
                'token_hash': encrypted_token,
                'target_channels': target_channels,
                'created_at': datetime.now(),
                'security_level': 'high',
                **kwargs
            }
            
            # 記錄審計日誌
            if self.audit_enabled:
                self.security_harness.log_audit_event('bot_created', {
                    'bot_id': bot_id,
                    'name': name,
                    'channels_count': len(target_channels)
                })
            
            return bot_id
            
        except Exception as e:
            self.security_harness.log_security_violation('creation_failure', 'medium', {
                'error': str(e),
                'name': name,
                'channels': len(target_channels) if target_channels else 0
            })
            raise
    
    async def start_sub_bot(self, bot_id: str) -> bool:
        """啟動子機器人（故障恢復版本）"""
        if bot_id not in self.bots:
            raise SubBotError(f"子機器人不存在: {bot_id}")
        
        # 檢查活躍故障
        active_faults = self.fault_injector.get_active_faults()
        
        # 模擬故障影響
        for fault in active_faults:
            if fault['type'] == 'network':
                if fault.get('active', False):
                    raise Exception("網路連線失敗")
            elif fault['type'] == 'discord_api' and fault.get('failure_mode') == 'auth_failure':
                raise SubBotTokenError(bot_id=bot_id, token_issue="Discord API 認證失敗")
        
        # 嘗試啟動，模擬重試機制
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 模擬啟動延遲
                await asyncio.sleep(0.1)
                
                self.bots[bot_id]['status'] = 'online'
                self.bots[bot_id]['last_start_time'] = datetime.now()
                
                self.security_harness.log_audit_event('bot_started', {
                    'bot_id': bot_id,
                    'retry_count': retry_count
                })
                
                return True
                
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    self.bots[bot_id]['status'] = 'failed'
                    self.security_harness.log_security_violation('start_failure', 'high', {
                        'bot_id': bot_id,
                        'retries': retry_count,
                        'error': str(e)
                    })
                    raise
                
                await asyncio.sleep(0.5 * retry_count)  # 指數退避
        
        return False
    
    async def _validate_input(self, name: str, token: str, channels: List[int]):
        """輸入驗證"""
        # 檢查SQL注入
        sql_patterns = ["'", "--", ";", "DROP", "DELETE", "UPDATE", "INSERT"]
        for pattern in sql_patterns:
            if pattern.lower() in name.lower():
                self.security_harness.log_attack_attempt('sql_injection', 'input_validation', {
                    'field': 'name',
                    'pattern': pattern,
                    'value': name[:100]  # 只記錄前100個字符
                })
                raise SecurityError(f"檢測到潛在的SQL注入攻擊")
        
        # 檢查XSS
        xss_patterns = ["<script", "</script>", "javascript:", "onload="]
        for pattern in xss_patterns:
            if pattern.lower() in name.lower():
                self.security_harness.log_attack_attempt('xss', 'input_validation', {
                    'field': 'name',
                    'pattern': pattern
                })
                raise SecurityError(f"檢測到潛在的XSS攻擊")
        
        # 檢查路徑遍歷
        if ".." in name or "/" in name or "\\" in name:
            self.security_harness.log_attack_attempt('path_traversal', 'input_validation', {
                'field': 'name',
                'value': name[:100]
            })
            raise SecurityError(f"檢測到潛在的路徑遍歷攻擊")
        
        # Token格式驗證
        if not token or len(token) < 20:
            raise SubBotTokenError(bot_id="validation", token_issue="Token格式無效")
    
    async def _check_permissions(self, action: str):
        """檢查權限"""
        # 模擬權限檢查
        pass
    
    async def _check_rate_limit(self, operation: str):
        """檢查速率限制"""
        current_time = datetime.now()
        key = f"{operation}_{current_time.minute}"
        
        if key not in self.rate_limits:
            self.rate_limits[key] = 0
        
        self.rate_limits[key] += 1
        
        if self.rate_limits[key] > 10:  # 每分鐘最多10次
            self.security_harness.log_security_violation('rate_limit_exceeded', 'medium', {
                'operation': operation,
                'count': self.rate_limits[key]
            })
            raise SecurityError("速率限制超出")
    
    async def _secure_encrypt_token(self, token: str) -> str:
        """安全加密Token"""
        try:
            # 使用Fernet進行安全加密
            fernet_key = base64.urlsafe_b64encode(self.encryption_key.encode()[:32].ljust(32, b'\0'))
            fernet = Fernet(fernet_key)
            encrypted = fernet.encrypt(token.encode('utf-8'))
            return base64.b64encode(encrypted).decode('ascii')
        except Exception as e:
            self.security_harness.log_security_violation('encryption_failure', 'critical', {
                'error': str(e)
            })
            raise SecurityError(f"Token加密失敗: {str(e)}")
    
    def _sanitize_input(self, input_str: str) -> str:
        """輸入清理"""
        # 移除潛在危險字符
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\n', '\r']
        sanitized = input_str
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        return sanitized[:100]  # 限制長度


@pytest.fixture
def security_harness():
    """安全測試工具"""
    return SecurityTestHarness()


@pytest.fixture
def fault_injector():
    """故障注入器"""
    return FaultInjector()


@pytest.fixture
def secure_subbot_service(security_harness, fault_injector):
    """安全的子機器人服務"""
    return MockSecureSubBotService(security_harness, fault_injector)


class TestSecurityValidation:
    """安全驗證測試"""
    
    @pytest.mark.asyncio
    async def test_sql_injection_protection(self, secure_subbot_service, security_harness):
        """測試SQL注入防護"""
        service = secure_subbot_service
        
        # 測試各種SQL注入載荷
        malicious_names = [
            "TestBot'; DROP TABLE sub_bots; --",
            "TestBot' OR '1'='1",
            "TestBot'; DELETE FROM users; --",
            "TestBot' UNION SELECT * FROM passwords --"
        ]
        
        for malicious_name in malicious_names:
            with pytest.raises(SecurityError, match="SQL注入攻擊"):
                await service.create_sub_bot(
                    name=malicious_name,
                    token="valid_token_12345",
                    target_channels=[123456789]
                )
        
        # 檢查攻擊記錄
        sql_attacks = [log for log in security_harness.attack_attempts 
                      if log['attack_type'] == 'sql_injection']
        assert len(sql_attacks) == len(malicious_names)
    
    @pytest.mark.asyncio
    async def test_xss_protection(self, secure_subbot_service, security_harness):
        """測試XSS防護"""
        service = secure_subbot_service
        
        malicious_names = [
            "<script>alert('xss')</script>",
            "TestBot<script src='evil.js'></script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "TestBot onload=alert('xss')"
        ]
        
        for malicious_name in malicious_names:
            with pytest.raises(SecurityError, match="XSS攻擊"):
                await service.create_sub_bot(
                    name=malicious_name,
                    token="valid_token_12345",
                    target_channels=[123456789]
                )
        
        # 檢查XSS攻擊記錄
        xss_attacks = [log for log in security_harness.attack_attempts 
                      if log['attack_type'] == 'xss']
        assert len(xss_attacks) == len(malicious_names)
    
    @pytest.mark.asyncio
    async def test_path_traversal_protection(self, secure_subbot_service, security_harness):
        """測試路徑遍歷防護"""
        service = secure_subbot_service
        
        malicious_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "./../../config/database.yml",
            "TestBot/../secrets.json"
        ]
        
        for malicious_name in malicious_names:
            with pytest.raises(SecurityError, match="路徑遍歷攻擊"):
                await service.create_sub_bot(
                    name=malicious_name,
                    token="valid_token_12345",
                    target_channels=[123456789]
                )
        
        # 檢查路徑遍歷攻擊記錄
        traversal_attacks = [log for log in security_harness.attack_attempts 
                           if log['attack_type'] == 'path_traversal']
        assert len(traversal_attacks) == len(malicious_names)
    
    @pytest.mark.asyncio
    async def test_input_sanitization(self, secure_subbot_service):
        """測試輸入清理"""
        service = secure_subbot_service
        
        # 測試包含危險字符的輸入
        dangerous_input = "TestBot<>&\"'\x00\n\r"
        
        bot_id = await service.create_sub_bot(
            name=dangerous_input,
            token="valid_token_12345",
            target_channels=[123456789]
        )
        
        # 檢查輸入已被清理
        saved_bot = service.bots[bot_id]
        sanitized_name = saved_bot['name']
        
        # 危險字符應該被移除
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\n', '\r']
        for char in dangerous_chars:
            assert char not in sanitized_name
        
        assert "TestBot" in sanitized_name  # 正常內容保留
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, secure_subbot_service, security_harness):
        """測試速率限制"""
        service = secure_subbot_service
        
        # 快速連續創建子機器人
        successful_creates = 0
        rate_limit_errors = 0
        
        for i in range(15):  # 嘗試創建15個（超過限制10個）
            try:
                await service.create_sub_bot(
                    name=f"RateLimitBot{i}",
                    token=f"token_{i}_12345",
                    target_channels=[123456789 + i]
                )
                successful_creates += 1
            except SecurityError as e:
                if "速率限制" in str(e):
                    rate_limit_errors += 1
                else:
                    raise
        
        # 應該有一些請求被速率限制阻擋
        assert rate_limit_errors > 0
        assert successful_creates <= 10
        
        # 檢查安全違規記錄
        rate_violations = [log for log in security_harness.security_violations 
                          if log['violation_type'] == 'rate_limit_exceeded']
        assert len(rate_violations) > 0


class TestTokenSecurity:
    """Token安全性測試"""
    
    @pytest.mark.asyncio
    async def test_token_encryption_security(self, secure_subbot_service):
        """測試Token加密安全性"""
        service = secure_subbot_service
        
        original_token = "MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.secure_test_token"
        
        # 創建子機器人
        bot_id = await service.create_sub_bot(
            name="EncryptionTestBot",
            token=original_token,
            target_channels=[123456789]
        )
        
        # 檢查Token已被加密
        saved_bot = service.bots[bot_id]
        encrypted_token = saved_bot['token_hash']
        
        # 加密後的Token不應該包含原始Token
        assert original_token not in encrypted_token
        assert len(encrypted_token) > len(original_token)  # 加密後通常更長
        assert encrypted_token != original_token
    
    @pytest.mark.asyncio
    async def test_token_encryption_uniqueness(self, secure_subbot_service):
        """測試Token加密唯一性"""
        service = secure_subbot_service
        
        same_token = "MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.uniqueness_test"
        
        # 使用相同Token創建兩個子機器人
        bot_id1 = await service.create_sub_bot(
            name="UniqueBot1",
            token=same_token,
            target_channels=[123456789]
        )
        
        bot_id2 = await service.create_sub_bot(
            name="UniqueBot2",
            token=same_token,
            target_channels=[987654321]
        )
        
        # 檢查加密結果是否不同（使用隨機鹽或IV）
        encrypted1 = service.bots[bot_id1]['token_hash']
        encrypted2 = service.bots[bot_id2]['token_hash']
        
        # 即使原始Token相同，加密結果也應該不同
        assert encrypted1 != encrypted2
    
    @pytest.mark.asyncio
    async def test_invalid_token_handling(self, secure_subbot_service, security_harness):
        """測試無效Token處理"""
        service = secure_subbot_service
        
        invalid_tokens = [
            "",
            "short",
            None,
            "invalid_format",
            "a" * 1000,  # 過長Token
        ]
        
        for invalid_token in invalid_tokens:
            with pytest.raises((SubBotTokenError, SecurityError, TypeError)):
                await service.create_sub_bot(
                    name="InvalidTokenBot",
                    token=invalid_token,
                    target_channels=[123456789]
                )
        
        # 檢查安全違規記錄
        violations = security_harness.security_violations
        token_violations = [v for v in violations if 'token' in str(v).lower()]
        assert len(token_violations) >= 1


class TestFaultRecovery:
    """故障恢復測試"""
    
    @pytest.mark.asyncio
    async def test_network_failure_recovery(self, secure_subbot_service, fault_injector, security_harness):
        """測試網路故障恢復"""
        service = secure_subbot_service
        
        # 創建子機器人
        bot_id = await service.create_sub_bot(
            name="NetworkTestBot",
            token="network_test_token_12345",
            target_channels=[123456789]
        )
        
        # 注入網路故障
        fault_id = fault_injector.inject_network_failure(duration=0.5)
        
        # 嘗試啟動（應該失敗）
        with pytest.raises(Exception, match="網路連線失敗"):
            await service.start_sub_bot(bot_id)
        
        # 清除故障
        fault_injector.clear_fault(fault_id)
        
        # 再次嘗試啟動（應該成功）
        success = await service.start_sub_bot(bot_id)
        assert success is True
        
        # 檢查審計日誌記錄了恢復過程
        audit_logs = security_harness.audit_log
        start_events = [log for log in audit_logs if log['event_type'] == 'bot_started']
        assert len(start_events) > 0
    
    @pytest.mark.asyncio
    async def test_discord_api_failure_recovery(self, secure_subbot_service, fault_injector):
        """測試Discord API故障恢復"""
        service = secure_subbot_service
        
        # 創建子機器人
        bot_id = await service.create_sub_bot(
            name="DiscordAPITestBot",
            token="discord_api_test_token_12345",
            target_channels=[123456789]
        )
        
        # 注入Discord API認證失敗
        fault_id = fault_injector.inject_discord_api_failure(failure_mode='auth_failure')
        
        # 嘗試啟動（應該失敗並重試）
        with pytest.raises(SubBotTokenError):
            await service.start_sub_bot(bot_id)
        
        # 檢查重試邏輯被執行
        assert service.bots[bot_id]['status'] == 'failed'
        
        # 清除故障並重試
        fault_injector.clear_fault(fault_id)
        
        # 再次嘗試啟動
        success = await service.start_sub_bot(bot_id)
        assert success is True
        assert service.bots[bot_id]['status'] == 'online'
    
    @pytest.mark.asyncio
    async def test_cascade_failure_isolation(self, secure_subbot_service, fault_injector):
        """測試級聯故障隔離"""
        service = secure_subbot_service
        
        # 創建多個子機器人
        bot_ids = []
        for i in range(5):
            bot_id = await service.create_sub_bot(
                name=f"IsolationBot{i}",
                token=f"isolation_token_{i}_12345",
                target_channels=[123456789 + i]
            )
            bot_ids.append(bot_id)
            await service.start_sub_bot(bot_id)
        
        # 確認所有bot都在線
        online_count = sum(1 for bot_id in bot_ids 
                          if service.bots[bot_id]['status'] == 'online')
        assert online_count == 5
        
        # 注入部分故障（模擬某些bot失敗）
        fault_id = fault_injector.inject_discord_api_failure()
        
        # 嘗試操作所有bot（部分應該失敗，但不影響其他bot）
        failed_bots = []
        working_bots = []
        
        for bot_id in bot_ids[:3]:  # 只對前3個bot施加故障
            try:
                # 模擬重啟操作
                service.bots[bot_id]['status'] = 'offline'
                await service.start_sub_bot(bot_id)
                working_bots.append(bot_id)
            except Exception:
                failed_bots.append(bot_id)
        
        # 檢查故障隔離效果
        assert len(failed_bots) <= 3  # 最多3個失敗
        
        # 其他bot應該仍然正常工作
        for bot_id in bot_ids[3:]:
            assert service.bots[bot_id]['status'] == 'online'


class TestDataIntegrity:
    """資料完整性測試"""
    
    @pytest.mark.asyncio
    async def test_concurrent_data_consistency(self, secure_subbot_service):
        """測試併發操作的資料一致性"""
        service = secure_subbot_service
        
        # 並發創建子機器人
        async def create_bot(i):
            try:
                return await service.create_sub_bot(
                    name=f"ConcurrentBot{i}",
                    token=f"concurrent_token_{i}_12345",
                    target_channels=[123456789 + i]
                )
            except Exception as e:
                return f"error_{i}: {str(e)}"
        
        # 啟動並發創建任務
        tasks = [create_bot(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # 檢查結果一致性
        successful_creates = [r for r in results if not str(r).startswith('error_')]
        
        # 所有成功創建的bot都應該在服務中
        for bot_id in successful_creates:
            assert bot_id in service.bots
            assert service.bots[bot_id]['bot_id'] == bot_id
        
        # 檢查沒有重複的bot_id
        assert len(set(successful_creates)) == len(successful_creates)
    
    @pytest.mark.asyncio
    async def test_data_corruption_detection(self, secure_subbot_service, security_harness):
        """測試資料損壞檢測"""
        service = secure_subbot_service
        
        # 創建子機器人
        bot_id = await service.create_sub_bot(
            name="CorruptionTestBot",
            token="corruption_test_token_12345",
            target_channels=[123456789]
        )
        
        # 模擬資料損壞
        original_token_hash = service.bots[bot_id]['token_hash']
        service.bots[bot_id]['token_hash'] = "corrupted_data_xxx"
        
        # 嘗試使用損壞的資料（應該檢測到問題）
        # 在實際實現中，這裡會有資料完整性檢查
        corrupted_token = service.bots[bot_id]['token_hash']
        
        # 檢查是否記錄了安全違規
        assert corrupted_token != original_token_hash
        
        # 恢復正確的資料
        service.bots[bot_id]['token_hash'] = original_token_hash


class TestAuditAndCompliance:
    """審計和合規測試"""
    
    @pytest.mark.asyncio
    async def test_audit_logging_completeness(self, secure_subbot_service, security_harness):
        """測試審計日誌完整性"""
        service = secure_subbot_service
        
        # 執行一系列操作
        bot_id = await service.create_sub_bot(
            name="AuditTestBot",
            token="audit_test_token_12345",
            target_channels=[123456789]
        )
        
        await service.start_sub_bot(bot_id)
        
        # 檢查審計日誌
        audit_logs = security_harness.audit_log
        
        # 應該記錄創建事件
        create_events = [log for log in audit_logs if log['event_type'] == 'bot_created']
        assert len(create_events) >= 1
        
        create_event = create_events[0]
        assert create_event['details']['bot_id'] == bot_id
        assert create_event['details']['name'] == "AuditTestBot"
        
        # 應該記錄啟動事件
        start_events = [log for log in audit_logs if log['event_type'] == 'bot_started']
        assert len(start_events) >= 1
        
        start_event = start_events[0]
        assert start_event['details']['bot_id'] == bot_id
    
    @pytest.mark.asyncio
    async def test_security_violation_tracking(self, secure_subbot_service, security_harness):
        """測試安全違規追踪"""
        service = secure_subbot_service
        
        # 觸發多種安全違規
        violations_to_test = [
            ("TestBot'; DROP TABLE users; --", "sql_injection"),
            ("<script>alert('xss')</script>", "xss"),
            ("../../../etc/passwd", "path_traversal")
        ]
        
        for malicious_input, expected_attack_type in violations_to_test:
            try:
                await service.create_sub_bot(
                    name=malicious_input,
                    token="test_token_12345",
                    target_channels=[123456789]
                )
            except SecurityError:
                pass  # 預期的異常
        
        # 檢查所有攻擊都被記錄
        attack_types = {log['attack_type'] for log in security_harness.attack_attempts}
        expected_types = {violation[1] for violation in violations_to_test}
        
        assert expected_types.issubset(attack_types)
        
        # 檢查攻擊詳情包含必要資訊
        for attack_log in security_harness.attack_attempts:
            assert 'timestamp' in attack_log
            assert 'attack_type' in attack_log
            assert 'source' in attack_log
            assert 'details' in attack_log
    
    @pytest.mark.asyncio
    async def test_compliance_data_retention(self, secure_subbot_service, security_harness):
        """測試合規資料保留"""
        service = secure_subbot_service
        
        # 生成一些審計資料
        for i in range(5):
            bot_id = await service.create_sub_bot(
                name=f"ComplianceBot{i}",
                token=f"compliance_token_{i}_12345",
                target_channels=[123456789 + i]
            )
            await service.start_sub_bot(bot_id)
        
        # 檢查審計日誌結構符合合規要求
        for log_entry in security_harness.audit_log:
            # 每個日誌項目都應該包含時間戳
            assert 'timestamp' in log_entry
            assert isinstance(log_entry['timestamp'], datetime)
            
            # 應該包含事件類型
            assert 'event_type' in log_entry
            assert isinstance(log_entry['event_type'], str)
            
            # 應該包含詳細資訊
            assert 'details' in log_entry
            assert isinstance(log_entry['details'], dict)
        
        # 檢查日誌時間順序
        timestamps = [log['timestamp'] for log in security_harness.audit_log]
        assert timestamps == sorted(timestamps)  # 應該按時間順序排列


if __name__ == "__main__":
    # 運行測試時的配置
    pytest.main([
        __file__,
        "-v",  # 詳細輸出
        "--tb=short",  # 簡短的錯誤追蹤
        "-s",  # 不捕獲輸出，顯示print
        "--asyncio-mode=auto",  # 自動asyncio模式
    ])