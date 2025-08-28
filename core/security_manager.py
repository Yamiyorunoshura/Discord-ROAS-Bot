"""
Security Manager - 資料庫安全與加密管理
Task ID: 1 - 核心架構和基礎設施建置

提供統一的敏感資料加密、解密和安全存儲機制，
配合安全代理的 Token 加密改進，確保資料庫中敏感資料的安全性。
"""

import os
import base64
import hashlib
import secrets
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import bcrypt
import logging

logger = logging.getLogger('core.security_manager')


class SecurityManager:
    """
    統一的安全管理器
    
    處理敏感資料的加密、解密、哈希和安全存儲
    與資料庫管理器整合，確保所有敏感資料都經過適當處理
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        初始化安全管理器
        
        參數：
            master_key: 主加密密鑰，如果不提供則從環境變數讀取
        """
        self.master_key = master_key or self._get_master_key()
        self._fernet = self._initialize_fernet(self.master_key)
        self._salt = self._generate_or_load_salt()
    
    def _get_master_key(self) -> str:
        """獲取主加密密鑰"""
        key = os.environ.get('ROAS_ENCRYPTION_KEY')
        if not key:
            logger.critical("未設置 ROAS_ENCRYPTION_KEY 環境變數，這是必要的安全要求")
            raise ValueError(
                "ROAS_ENCRYPTION_KEY 環境變數未設置。\n"
                "為確保安全，必須設置此環境變數。\n"
                "請生成一個強密鑰：python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # 驗證密鑰強度
        self._validate_key_strength(key)
        return key
    
    def _validate_key_strength(self, key: str) -> None:
        """
        驗證密鑰強度
        
        參數：
            key: 要驗證的密鑰
            
        拋出：
            ValueError: 如果密鑰不符合安全要求
        """
        if len(key) < 32:
            raise ValueError("加密密鑰長度至少需要32個字元")
        
        # 檢查複雜度要求
        has_lower = any(c.islower() for c in key)
        has_upper = any(c.isupper() for c in key)
        has_digit = any(c.isdigit() for c in key)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in key)
        
        complexity_count = sum([has_lower, has_upper, has_digit, has_special])
        
        if complexity_count < 3:
            raise ValueError(
                "加密密鑰必須包含至少3種類型的字元："
                "小寫字母、大寫字母、數字、特殊字元"
            )
        
        # 檢查是否包含預設或常見的不安全密鑰
        unsafe_patterns = [
            "password", "123456", "qwerty", "admin", "secret",
            "default", "change", "dev-", "test-", "demo-"
        ]
        
        key_lower = key.lower()
        for pattern in unsafe_patterns:
            if pattern in key_lower:
                raise ValueError(f"密鑰包含不安全的模式：{pattern}")
        
        logger.info("密鑰強度驗證通過")
    
    def _initialize_fernet(self, master_key: str) -> Fernet:
        """初始化 Fernet 加密器"""
        # 使用 PBKDF2 從主密鑰衍生加密密鑰
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'roas-bot-salt-2024',  # 固定鹽值用於密鑰衍生
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return Fernet(key)
    
    def _generate_or_load_salt(self) -> bytes:
        """生成或載入隨機鹽值"""
        salt_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'security.salt')
        
        try:
            # 嘗試載入現有鹽值
            if os.path.exists(salt_file):
                with open(salt_file, 'rb') as f:
                    return f.read()
        except Exception:
            pass
        
        # 生成新鹽值
        salt = secrets.token_bytes(32)
        
        try:
            # 儲存鹽值
            os.makedirs(os.path.dirname(salt_file), exist_ok=True)
            with open(salt_file, 'wb') as f:
                f.write(salt)
        except Exception as e:
            logger.warning(f"無法儲存安全鹽值：{e}")
        
        return salt
    
    # ========== 對稱加密方法 ==========
    
    def encrypt_data(self, plaintext: str) -> str:
        """
        加密敏感資料
        
        參數：
            plaintext: 明文資料
            
        返回：
            Base64 編碼的加密資料
        """
        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"資料加密失敗：{e}")
            raise ValueError(f"加密失敗：{str(e)}")
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        解密敏感資料
        
        參數：
            encrypted_data: Base64 編碼的加密資料
            
        返回：
            解密後的明文資料
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"資料解密失敗：{e}")
            raise ValueError(f"解密失敗：{str(e)}")
    
    # ========== 哈希方法 ==========
    
    def hash_password(self, password: str, rounds: int = 12) -> str:
        """
        使用 bcrypt 哈希密碼
        
        參數：
            password: 明文密碼
            rounds: bcrypt 輪數（預設 12）
            
        返回：
            bcrypt 哈希值
        """
        try:
            salt = bcrypt.gensalt(rounds=rounds)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        except Exception as e:
            logger.error(f"密碼哈希失敗：{e}")
            raise ValueError(f"密碼哈希失敗：{str(e)}")
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """
        驗證密碼哈希
        
        參數：
            password: 明文密碼
            hashed: bcrypt 哈希值
            
        返回：
            驗證結果
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.error(f"密碼驗證失敗：{e}")
            return False
    
    def hash_token(self, token: str, include_timestamp: bool = True) -> str:
        """
        安全哈希 Token
        
        參數：
            token: 原始 Token
            include_timestamp: 是否包含時間戳（增加安全性）
            
        返回：
            SHA256 哈希值（十六進制）
        """
        try:
            # 結合 Token、鹽值和可選時間戳
            data_to_hash = token.encode('utf-8') + self._salt
            if include_timestamp:
                import time
                timestamp = str(int(time.time() // 3600))  # 小時級時間戳
                data_to_hash += timestamp.encode('utf-8')
            
            hash_obj = hashlib.sha256(data_to_hash)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Token 哈希失敗：{e}")
            raise ValueError(f"Token 哈希失敗：{str(e)}")
    
    # ========== 專用的資料庫安全方法 ==========
    
    def encrypt_discord_token(self, token: str) -> str:
        """
        加密 Discord Bot Token
        
        專門處理 Discord Bot Token 的加密，使用高強度加密
        
        參數：
            token: Discord Bot Token
            
        返回：
            加密後的 Token
        """
        if not token or not token.startswith(('Bot ', 'MTk')):
            raise ValueError("無效的 Discord Token 格式")
        
        return self.encrypt_data(token)
    
    def decrypt_discord_token(self, encrypted_token: str) -> str:
        """
        解密 Discord Bot Token
        
        參數：
            encrypted_token: 加密後的 Token
            
        返回：
            原始 Discord Token
        """
        decrypted = self.decrypt_data(encrypted_token)
        
        # 驗證 Token 格式
        if not decrypted.startswith(('Bot ', 'MTk')):
            raise ValueError("解密的 Token 格式無效")
        
        return decrypted
    
    def encrypt_api_key(self, api_key: str, provider: str) -> str:
        """
        加密 API 金鑰
        
        參數：
            api_key: API 金鑰
            provider: 提供商名稱（用於驗證格式）
            
        返回：
            加密後的 API 金鑰
        """
        if not api_key:
            raise ValueError("API 金鑰不能為空")
        
        # 簡單格式驗證
        provider_prefixes = {
            'openai': 'sk-',
            'anthropic': 'sk-ant-',
            'google': 'AIza'
        }
        
        expected_prefix = provider_prefixes.get(provider.lower())
        if expected_prefix and not api_key.startswith(expected_prefix):
            logger.warning(f"API 金鑰格式可能不正確 (provider: {provider})")
        
        return self.encrypt_data(api_key)
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """
        解密 API 金鑰
        
        參數：
            encrypted_key: 加密後的 API 金鑰
            
        返回：
            原始 API 金鑰
        """
        return self.decrypt_data(encrypted_key)
    
    # ========== 資料完整性和審計 ==========
    
    def generate_checksum(self, data: str) -> str:
        """
        生成資料校驗和
        
        參數：
            data: 需要校驗的資料
            
        返回：
            SHA256 校驗和
        """
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    def verify_checksum(self, data: str, expected_checksum: str) -> bool:
        """
        驗證資料校驗和
        
        參數：
            data: 資料
            expected_checksum: 預期校驗和
            
        返回：
            驗證結果
        """
        actual_checksum = self.generate_checksum(data)
        return actual_checksum == expected_checksum
    
    def sanitize_for_logging(self, sensitive_data: str, 
                           show_length: int = 4, mask_char: str = '*') -> str:
        """
        為記錄清理敏感資料
        
        參數：
            sensitive_data: 敏感資料
            show_length: 顯示的字元數量
            mask_char: 遮罩字元
            
        返回：
            安全的記錄字串
        """
        if not sensitive_data or len(sensitive_data) <= show_length:
            return mask_char * 8
        
        visible_part = sensitive_data[:show_length]
        masked_part = mask_char * (len(sensitive_data) - show_length)
        return f"{visible_part}{masked_part}"


# 全域安全管理器實例
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """
    獲取全域安全管理器實例
    
    返回：
        安全管理器實例
    """
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


# 便利函數
def encrypt_sensitive_data(data: str) -> str:
    """加密敏感資料的便利函數"""
    return get_security_manager().encrypt_data(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """解密敏感資料的便利函數"""
    return get_security_manager().decrypt_data(encrypted_data)


def hash_token_secure(token: str) -> str:
    """安全哈希 Token 的便利函數"""
    return get_security_manager().hash_token(token)