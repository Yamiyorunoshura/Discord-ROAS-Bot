"""
測試安全管理器功能
驗證加密、解密、哈希和安全存儲機制
"""

import os
import sys
import pytest
import tempfile

# 將專案根目錄加入路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.security_manager import SecurityManager, get_security_manager


class TestSecurityManager:
    """安全管理器測試"""
    
    def setup_method(self):
        """測試設定"""
        self.security_manager = SecurityManager("test-encryption-key-123")
    
    def test_encrypt_decrypt_data(self):
        """測試資料加密解密"""
        original_data = "這是一個測試用的敏感資料"
        
        # 加密
        encrypted_data = self.security_manager.encrypt_data(original_data)
        assert encrypted_data != original_data
        assert len(encrypted_data) > 0
        
        # 解密
        decrypted_data = self.security_manager.decrypt_data(encrypted_data)
        assert decrypted_data == original_data
    
    def test_password_hashing(self):
        """測試密碼哈希和驗證"""
        password = "test_password_123"
        
        # 哈希密碼
        hashed = self.security_manager.hash_password(password)
        assert hashed != password
        assert len(hashed) > 0
        
        # 驗證正確密碼
        assert self.security_manager.verify_password(password, hashed)
        
        # 驗證錯誤密碼
        assert not self.security_manager.verify_password("wrong_password", hashed)
    
    def test_token_hashing(self):
        """測試 Token 哈希"""
        token = "MTk0NzY5OTI4NjA2NDI1NjAwMA.GH1Y3D.example_token_hash"
        
        # 哈希 Token
        hashed_token = self.security_manager.hash_token(token)
        assert hashed_token != token
        assert len(hashed_token) == 64  # SHA256 十六進制長度
        
        # 相同 Token 應該產生相同哈希（在同一小時內）
        hashed_token2 = self.security_manager.hash_token(token)
        assert hashed_token == hashed_token2
    
    def test_discord_token_encryption(self):
        """測試 Discord Token 加密"""
        discord_token = "Bot MTk0NzY5OTI4NjA2NDI1NjAwMA.GH1Y3D.example_token_hash"
        
        # 加密 Discord Token
        encrypted_token = self.security_manager.encrypt_discord_token(discord_token)
        assert encrypted_token != discord_token
        
        # 解密 Discord Token
        decrypted_token = self.security_manager.decrypt_discord_token(encrypted_token)
        assert decrypted_token == discord_token
    
    def test_invalid_discord_token(self):
        """測試無效的 Discord Token"""
        invalid_token = "invalid_token_format"
        
        # 應該拋出 ValueError
        with pytest.raises(ValueError):
            self.security_manager.encrypt_discord_token(invalid_token)
    
    def test_api_key_encryption(self):
        """測試 API 金鑰加密"""
        # OpenAI API 金鑰
        openai_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
        encrypted_key = self.security_manager.encrypt_api_key(openai_key, "openai")
        decrypted_key = self.security_manager.decrypt_api_key(encrypted_key)
        assert decrypted_key == openai_key
        
        # Anthropic API 金鑰
        anthropic_key = "sk-ant-api03-1234567890abcdefghijklmnopqrstuvwxyz"
        encrypted_key = self.security_manager.encrypt_api_key(anthropic_key, "anthropic")
        decrypted_key = self.security_manager.decrypt_api_key(encrypted_key)
        assert decrypted_key == anthropic_key
    
    def test_checksum_generation(self):
        """測試校驗和生成和驗證"""
        data = "test data for checksum"
        
        # 生成校驗和
        checksum = self.security_manager.generate_checksum(data)
        assert len(checksum) == 64  # SHA256 十六進制長度
        
        # 驗證正確的校驗和
        assert self.security_manager.verify_checksum(data, checksum)
        
        # 驗證錯誤的校驗和
        assert not self.security_manager.verify_checksum(data, "wrong_checksum")
        
        # 驗證不同資料的校驗和
        assert not self.security_manager.verify_checksum("different data", checksum)
    
    def test_logging_sanitization(self):
        """測試記錄清理功能"""
        sensitive_data = "sk-1234567890abcdefghijklmnopqrstuvwxyz123456"
        
        # 預設設定（顯示前4個字元）
        sanitized = self.security_manager.sanitize_for_logging(sensitive_data)
        assert sanitized.startswith("sk-1")
        assert "*" in sanitized
        assert len(sanitized) == len(sensitive_data)
        
        # 自定義設定
        sanitized_custom = self.security_manager.sanitize_for_logging(
            sensitive_data, show_length=8, mask_char="X"
        )
        assert sanitized_custom.startswith("sk-12345")
        assert "X" in sanitized_custom
    
    def test_global_security_manager(self):
        """測試全域安全管理器"""
        # 獲取全域實例
        global_manager1 = get_security_manager()
        global_manager2 = get_security_manager()
        
        # 應該是同一個實例
        assert global_manager1 is global_manager2
    
    def test_encryption_consistency(self):
        """測試加密一致性"""
        data = "consistency test data"
        
        # 多次加密同樣資料應該產生不同的結果（因為有隨機元素）
        encrypted1 = self.security_manager.encrypt_data(data)
        encrypted2 = self.security_manager.encrypt_data(data)
        assert encrypted1 != encrypted2
        
        # 但都應該能正確解密
        assert self.security_manager.decrypt_data(encrypted1) == data
        assert self.security_manager.decrypt_data(encrypted2) == data
    
    def test_error_handling(self):
        """測試錯誤處理"""
        # 解密無效資料
        with pytest.raises(ValueError):
            self.security_manager.decrypt_data("invalid_encrypted_data")
        
        # 空 API 金鑰
        with pytest.raises(ValueError):
            self.security_manager.encrypt_api_key("", "openai")


def main():
    """執行安全管理器測試"""
    print("🔒 開始測試安全管理器...")
    
    # 執行測試
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    main()