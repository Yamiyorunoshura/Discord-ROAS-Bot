"""
SubBot服務Token加密測試
Task ID: 1 - 核心架構和基礎設施建置

測試SubBot服務的Token加密、解密功能和安全性
"""

import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock

from src.services.subbot_service import SubBotService, CRYPTOGRAPHY_AVAILABLE, FERNET_AVAILABLE
from src.core.errors import SubBotTokenError, SecurityError
from src.core.config import SecurityConfig


@pytest.fixture
def encryption_key():
    """提供測試用的加密密鑰"""
    return "test_key_32_bytes_for_encryption_123456789abcdef"


@pytest.fixture
def subbot_service(encryption_key):
    """創建SubBot服務實例用於測試"""
    return SubBotService(encryption_key=encryption_key)


@pytest.fixture
def sample_discord_token():
    """提供測試用的Discord Token"""
    return "MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.dQw4w9WgXcQ"


class TestTokenEncryption:
    """Token加密功能測試"""
    
    def test_encryption_library_availability(self):
        """測試加密庫可用性檢查"""
        # 至少要有一個加密庫可用
        assert CRYPTOGRAPHY_AVAILABLE or FERNET_AVAILABLE, \
            "必須安裝 cryptography 庫才能進行Token加密"
    
    def test_service_initialization_with_key(self, encryption_key):
        """測試服務使用指定密鑰初始化"""
        service = SubBotService(encryption_key=encryption_key)
        
        assert service._encryption_key == encryption_key
        assert service._cipher_type in ["AES-GCM", "Fernet"]
        assert service._key_version == 1
    
    def test_service_initialization_without_key(self):
        """測試服務自動生成密鑰初始化"""
        service = SubBotService()
        
        # 應該自動生成密鑰
        assert service._encryption_key is not None
        assert len(service._encryption_key) > 0
        assert service._cipher_type in ["AES-GCM", "Fernet"]
    
    def test_service_initialization_no_crypto_library(self):
        """測試沒有加密庫時的錯誤處理"""
        with patch('src.services.subbot_service.CRYPTOGRAPHY_AVAILABLE', False):
            with patch('src.services.subbot_service.FERNET_AVAILABLE', False):
                with pytest.raises(SecurityError, match="缺少加密庫"):
                    SubBotService()
    
    def test_token_encryption_decryption_roundtrip(self, subbot_service, sample_discord_token):
        """測試Token加密-解密循環"""
        # 加密Token
        encrypted_token = subbot_service._encrypt_token(sample_discord_token)
        
        # 驗證加密結果
        assert encrypted_token != sample_discord_token, "加密後的Token應該與原始Token不同"
        assert len(encrypted_token) > len(sample_discord_token), "加密後的Token通常會更長"
        
        # 解密Token
        decrypted_token = subbot_service._decrypt_token(encrypted_token)
        
        # 驗證解密結果
        assert decrypted_token == sample_discord_token, "解密後的Token應該與原始Token相同"
    
    def test_token_encryption_uniqueness(self, subbot_service, sample_discord_token):
        """測試每次加密結果的唯一性（防重放攻擊）"""
        encrypted1 = subbot_service._encrypt_token(sample_discord_token)
        encrypted2 = subbot_service._encrypt_token(sample_discord_token)
        
        # 由於使用隨機IV，每次加密結果應該不同
        assert encrypted1 != encrypted2, "相同Token的多次加密結果應該不同（防重放攻擊）"
        
        # 但解密後應該都是原始Token
        assert subbot_service._decrypt_token(encrypted1) == sample_discord_token
        assert subbot_service._decrypt_token(encrypted2) == sample_discord_token
    
    def test_invalid_token_decryption(self, subbot_service):
        """測試無效Token解密的錯誤處理"""
        with pytest.raises(SubBotTokenError):
            subbot_service._decrypt_token("invalid_encrypted_token")
        
        with pytest.raises(SubBotTokenError):
            subbot_service._decrypt_token("")
        
        with pytest.raises(SubBotTokenError):
            subbot_service._decrypt_token("not_base64_encoded")
    
    def test_corrupted_token_decryption(self, subbot_service, sample_discord_token):
        """測試損壞Token解密的錯誤處理"""
        # 加密正常Token
        encrypted_token = subbot_service._encrypt_token(sample_discord_token)
        
        # 損壞加密數據
        corrupted_token = encrypted_token[:-10] + "corrupted"
        
        with pytest.raises(SubBotTokenError, match="Token解密失敗"):
            subbot_service._decrypt_token(corrupted_token)
    
    @pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="需要cryptography庫")
    def test_aes_gcm_encryption_format(self, subbot_service, sample_discord_token):
        """測試AES-GCM加密格式"""
        if subbot_service._cipher_type != "AES-GCM":
            pytest.skip("此測試需要AES-GCM加密")
        
        encrypted_token = subbot_service._encrypt_token(sample_discord_token)
        
        # Base64解碼檢查格式
        import base64
        encrypted_data = base64.b64decode(encrypted_token.encode('ascii'))
        
        # AES-GCM格式：12字節IV + 16字節認證標籤 + 密文
        assert len(encrypted_data) >= 28, "AES-GCM加密數據至少28字節（IV+標籤）"
        
        iv = encrypted_data[:12]
        auth_tag = encrypted_data[12:28]
        ciphertext = encrypted_data[28:]
        
        assert len(iv) == 12, "IV應該是12字節"
        assert len(auth_tag) == 16, "認證標籤應該是16字節"
        assert len(ciphertext) > 0, "密文不能為空"
    
    def test_encryption_with_unicode_token(self, subbot_service):
        """測試包含Unicode字符的Token加密"""
        unicode_token = "test_token_中文_🤖_特殊字符"
        
        encrypted_token = subbot_service._encrypt_token(unicode_token)
        decrypted_token = subbot_service._decrypt_token(encrypted_token)
        
        assert decrypted_token == unicode_token, "Unicode Token應該正確加密解密"
    
    def test_empty_token_encryption(self, subbot_service):
        """測試空Token的處理"""
        empty_token = ""
        
        encrypted_token = subbot_service._encrypt_token(empty_token)
        decrypted_token = subbot_service._decrypt_token(encrypted_token)
        
        assert decrypted_token == empty_token, "空Token應該正確處理"


class TestKeyRotation:
    """密鑰輪換功能測試"""
    
    @pytest.mark.asyncio
    async def test_key_rotation_basic(self, subbot_service, sample_discord_token):
        """測試基本密鑰輪換功能"""
        # 記錄初始狀態
        original_key = subbot_service._encryption_key
        original_version = subbot_service._key_version
        
        # 加密一個Token
        encrypted_token = subbot_service._encrypt_token(sample_discord_token)
        
        # 執行密鑰輪換
        success = await subbot_service._rotate_encryption_key()
        
        assert success, "密鑰輪換應該成功"
        assert subbot_service._encryption_key != original_key, "新密鑰應該與舊密鑰不同"
        assert subbot_service._key_version == original_version + 1, "密鑰版本應該遞增"
        assert original_key in subbot_service._legacy_keys.values(), "舊密鑰應該保存在legacy_keys中"
    
    @pytest.mark.asyncio
    async def test_legacy_key_cleanup(self, subbot_service):
        """測試舊密鑰清理機制"""
        # 設置較小的備份數量以便測試
        subbot_service.config['key_backup_count'] = 2
        
        # 模擬多次密鑰輪換
        for i in range(5):
            await subbot_service._rotate_encryption_key()
        
        # 檢查舊密鑰數量不超過配置
        assert len(subbot_service._legacy_keys) <= subbot_service.config['key_backup_count'], \
            "舊密鑰數量應該不超過配置的最大值"
    
    def test_encryption_info(self, subbot_service):
        """測試加密資訊獲取"""
        info = subbot_service.get_encryption_info()
        
        expected_keys = {
            'algorithm', 'key_version', 'legacy_key_count', 
            'rotation_enabled', 'rotation_interval'
        }
        
        assert set(info.keys()) == expected_keys, "加密資訊應該包含所有必要欄位"
        assert info['algorithm'] in ["AES-GCM", "Fernet"], "算法應該是支援的類型"
        assert info['key_version'] >= 1, "密鑰版本應該從1開始"
        assert isinstance(info['legacy_key_count'], int), "舊密鑰數量應該是整數"


class TestConfigurationIntegration:
    """配置系統整合測試"""
    
    def test_config_preferred_algorithm_aes(self):
        """測試配置首選AES-GCM算法"""
        if not CRYPTOGRAPHY_AVAILABLE:
            pytest.skip("需要cryptography庫")
        
        with patch('src.services.subbot_service.get_config') as mock_config:
            mock_security_config = Mock()
            mock_security_config.encryption_key = "test_key_from_config_32bytes_123456"
            mock_security_config.token_encryption_algorithm = "AES-GCM"
            mock_security_config.key_rotation_enabled = True
            
            mock_config.return_value.security = mock_security_config
            
            service = SubBotService()
            
            assert service._cipher_type == "AES-GCM", "應該使用配置指定的AES-GCM"
            assert service._encryption_key == "test_key_from_config_32bytes_123456"
            assert service._key_rotation_enabled is True
    
    def test_config_fallback_to_fernet(self):
        """測試當AES-GCM不可用時回退到Fernet"""
        if not FERNET_AVAILABLE:
            pytest.skip("需要cryptography庫中的Fernet")
        
        with patch('src.services.subbot_service.CRYPTOGRAPHY_AVAILABLE', False):
            with patch('src.services.subbot_service.get_config') as mock_config:
                mock_security_config = Mock()
                mock_security_config.encryption_key = "test_key_32bytes_for_fernet_test123"
                mock_security_config.token_encryption_algorithm = "AES-GCM"  # 請求AES但不可用
                mock_security_config.key_rotation_enabled = False
                
                mock_config.return_value.security = mock_security_config
                
                service = SubBotService()
                
                assert service._cipher_type == "Fernet", "應該回退到Fernet"
                assert service._key_rotation_enabled is False


class TestSecurityFeatures:
    """安全功能測試"""
    
    def test_key_derivation_different_salts(self, subbot_service):
        """測試密鑰派生使用不同鹽值產生不同結果"""
        if subbot_service._cipher_type != "AES-GCM":
            pytest.skip("此測試需要AES-GCM加密")
        
        salt1 = os.urandom(12)
        salt2 = os.urandom(12)
        
        key1 = subbot_service._derive_key(salt1)
        key2 = subbot_service._derive_key(salt2)
        
        assert key1 != key2, "不同鹽值應該產生不同的派生密鑰"
        assert len(key1) == 32, "派生密鑰應該是32字節（256位）"
        assert len(key2) == 32, "派生密鑰應該是32字節（256位）"
    
    def test_key_derivation_consistency(self, subbot_service):
        """測試密鑰派生的一致性"""
        if subbot_service._cipher_type != "AES-GCM":
            pytest.skip("此測試需要AES-GCM加密")
        
        salt = os.urandom(12)
        
        key1 = subbot_service._derive_key(salt)
        key2 = subbot_service._derive_key(salt)
        
        assert key1 == key2, "相同鹽值應該產生相同的派生密鑰"
    
    def test_sensitive_data_handling(self, subbot_service):
        """測試敏感資料處理"""
        # 確保加密密鑰不會出現在字符串表示中
        service_str = str(subbot_service.__dict__)
        
        # 加密密鑰不應該以明文形式出現
        if len(subbot_service._encryption_key) > 10:
            assert subbot_service._encryption_key not in service_str, \
                "加密密鑰不應該出現在對象的字符串表示中"
    
    @pytest.mark.asyncio 
    async def test_cleanup_clears_sensitive_data(self, subbot_service):
        """測試清理操作會清除敏感資料"""
        # 添加一些舊密鑰
        await subbot_service._rotate_encryption_key()
        
        # 確保有舊密鑰
        assert len(subbot_service._legacy_keys) > 0
        
        # 執行清理
        await subbot_service._cleanup()
        
        # 檢查敏感資料已清理
        assert len(subbot_service._legacy_keys) == 0, "清理後應該清除所有舊密鑰"


class TestPerformance:
    """性能測試"""
    
    def test_encryption_performance(self, subbot_service, sample_discord_token):
        """測試加密性能"""
        import time
        
        # 測試100次加密操作的時間
        start_time = time.time()
        for _ in range(100):
            encrypted = subbot_service._encrypt_token(sample_discord_token)
            decrypted = subbot_service._decrypt_token(encrypted)
            assert decrypted == sample_discord_token
        
        elapsed_time = time.time() - start_time
        
        # 100次操作應該在1秒內完成（很寬鬆的要求）
        assert elapsed_time < 1.0, f"100次加密解密操作耗時 {elapsed_time:.3f}s，性能可能有問題"
        
        # 平均每次操作應該在10ms內
        avg_time = elapsed_time / 100
        assert avg_time < 0.01, f"平均每次加密解密耗時 {avg_time*1000:.2f}ms，可能需要優化"


if __name__ == "__main__":
    pytest.main([__file__])