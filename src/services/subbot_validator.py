"""
子機器人輸入驗證和安全模組
Task ID: 3 - 子機器人聊天功能和管理系統開發

提供完整的輸入驗證、參數檢查和安全防護：
- Discord Token格式驗證
- 頻道ID和用戶ID驗證
- 內容安全過濾和XSS防護
- 輸入清理和規範化
- 並發安全控制
- 內容安全策略(CSP)支持
"""

import re
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, Set
from datetime import datetime
from threading import Lock
from dataclasses import dataclass

from src.core.errors import ValidationError, SecurityError, SubBotError

logger = logging.getLogger('subbot.validator')


@dataclass
class ContentSecurityPolicy:
    """內容安全策略配置"""
    allow_html: bool = False
    allow_javascript: bool = False
    allow_inline_styles: bool = False
    allow_external_links: bool = True
    allowed_domains: Set[str] = None
    blocked_domains: Set[str] = None
    max_url_length: int = 2048
    enable_xss_protection: bool = True
    enable_csrf_protection: bool = True
    
    def __post_init__(self):
        if self.allowed_domains is None:
            self.allowed_domains = set()
        if self.blocked_domains is None:
            self.blocked_domains = set()


@dataclass
class ValidationRule:
    """驗證規則定義"""
    field_name: str
    rule_type: str
    parameters: Dict[str, Any]
    error_message: str


class SecurityPolicy:
    """安全策略定義"""
    
    def __init__(self):
        # 內容過濾規則
        self.forbidden_patterns = [
            r'(?i)(discord\.gg|discordapp\.com/invite)/[a-zA-Z0-9]+',  # Discord邀請連結
            r'(?i)https?://[^\s]+\.(exe|bat|cmd|scr|com|pif)',  # 可執行文件連結
            r'(?i)(fuck|shit|damn|hell|bitch)',  # 不當語言（示例）
        ]
        
        # 允許的文件擴展名
        self.allowed_file_extensions = {'.txt', '.jpg', '.jpeg', '.png', '.gif', '.pdf'}
        
        # 最大長度限制
        self.max_content_length = 2000  # Discord訊息最大長度
        self.max_name_length = 100
        self.max_channel_count = 50
        
        # 速率限制
        self.max_operations_per_minute = 60
        self.max_bots_per_user = 5


class InputValidator:
    """輸入驗證器"""
    
    def __init__(self, 
                 security_policy: Optional[SecurityPolicy] = None,
                 content_security_policy: Optional[ContentSecurityPolicy] = None):
        self.security_policy = security_policy or SecurityPolicy()
        self.content_security_policy = content_security_policy or ContentSecurityPolicy()
        self.logger = logging.getLogger(f'{__name__}.InputValidator')
        
        # 並發控制
        self._validation_lock = asyncio.Lock()
        self._operation_counts = {}  # 用戶操作計數
        self._lock = Lock()  # 用於操作計數的線程鎖
    
    async def validate_bot_creation_input(self, 
                                        name: str, 
                                        token: str, 
                                        owner_id: int,
                                        channel_restrictions: Optional[List[int]] = None,
                                        ai_model: Optional[str] = None,
                                        personality: Optional[str] = None) -> Dict[str, Any]:
        """驗證子機器人創建輸入"""
        async with self._validation_lock:
            errors = []
            warnings = []
            
            # 驗證名稱
            try:
                self._validate_bot_name(name)
            except ValidationError as e:
                errors.append(f"名稱驗證失敗: {e.message}")
            
            # 驗證Token
            try:
                self._validate_discord_token(token)
            except ValidationError as e:
                errors.append(f"Token驗證失敗: {e.message}")
            
            # 驗證擁有者ID
            try:
                self._validate_user_id(owner_id, "owner_id")
            except ValidationError as e:
                errors.append(f"擁有者ID驗證失敗: {e.message}")
            
            # 驗證頻道限制
            if channel_restrictions:
                try:
                    self._validate_channel_list(channel_restrictions)
                except ValidationError as e:
                    errors.append(f"頻道限制驗證失敗: {e.message}")
            
            # 驗證AI模型
            if ai_model:
                try:
                    self._validate_ai_model(ai_model)
                except ValidationError as e:
                    warnings.append(f"AI模型驗證警告: {e.message}")
            
            # 驗證個性設定
            if personality:
                try:
                    self._validate_personality_content(personality)
                except ValidationError as e:
                    errors.append(f"個性設定驗證失敗: {e.message}")
            
            # 檢查操作頻率
            try:
                self._check_rate_limit(owner_id, "create_bot")
            except SecurityError as e:
                errors.append(f"速率限制: {e.message}")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'timestamp': datetime.now().isoformat()
            }
    
    def _validate_bot_name(self, name: str) -> None:
        """驗證機器人名稱"""
        if not name or not isinstance(name, str):
            raise ValidationError(
                field="name",
                value=name,
                validation_rule="非空字符串",
                message="機器人名稱不能為空"
            )
        
        name = name.strip()
        if len(name) < 2:
            raise ValidationError(
                field="name",
                value=name,
                validation_rule="最小長度2",
                message="機器人名稱至少需要2個字符"
            )
        
        if len(name) > self.security_policy.max_name_length:
            raise ValidationError(
                field="name",
                value=name,
                validation_rule=f"最大長度{self.security_policy.max_name_length}",
                message=f"機器人名稱不能超過{self.security_policy.max_name_length}個字符"
            )
        
        # 檢查不當內容
        for pattern in self.security_policy.forbidden_patterns:
            if re.search(pattern, name):
                raise ValidationError(
                    field="name",
                    value=name,
                    validation_rule="內容安全檢查",
                    message="機器人名稱包含不允許的內容"
                )
        
        # 檢查特殊字符
        if not re.match(r'^[a-zA-Z0-9\u4e00-\u9fff\s_-]+$', name):
            raise ValidationError(
                field="name",
                value=name,
                validation_rule="字符集檢查",
                message="機器人名稱只能包含字母、數字、中文字符、空格、下劃線和連字符"
            )
    
    def _validate_discord_token(self, token: str) -> None:
        """驗證Discord Token格式"""
        if not token or not isinstance(token, str):
            raise ValidationError(
                field="token",
                value="[隱藏]",
                validation_rule="非空字符串",
                message="Discord Token不能為空"
            )
        
        token = token.strip()
        
        # 基本長度檢查
        if len(token) < 50:
            raise ValidationError(
                field="token",
                value="[隱藏]",
                validation_rule="最小長度50",
                message="Discord Token長度不足"
            )
        
        # 檢查是否包含Bot前綴（舊格式）
        if token.startswith('Bot '):
            token = token[4:]  # 移除Bot前綴
        
        # Discord Bot Token格式檢查
        token_parts = token.split('.')
        if len(token_parts) != 3:
            raise ValidationError(
                field="token",
                value="[隱藏]",
                validation_rule="三段式格式",
                message="Discord Token格式不正確"
            )
        
        # 檢查第一部分是否為有效的Base64
        try:
            import base64
            # 嘗試解碼第一部分（Bot ID）
            first_part = token_parts[0]
            # 添加必要的填充
            missing_padding = len(first_part) % 4
            if missing_padding:
                first_part += '=' * (4 - missing_padding)
            base64.b64decode(first_part)
        except Exception:
            raise ValidationError(
                field="token",
                value="[隱藏]",
                validation_rule="Base64編碼檢查",
                message="Discord Token第一部分不是有效的Base64編碼"
            )
        
        # 檢查是否為測試Token或明顯無效的Token
        invalid_patterns = [
            'your_bot_token_here',
            'insert_token_here',
            'fake_token',
            'test_token'
        ]
        
        for pattern in invalid_patterns:
            if pattern.lower() in token.lower():
                raise ValidationError(
                    field="token",
                    value="[隱藏]",
                    validation_rule="有效性檢查",
                    message="提供的Token似乎不是有效的Discord Bot Token"
                )
    
    def _validate_user_id(self, user_id: Union[int, str], field_name: str = "user_id") -> None:
        """驗證Discord用戶ID"""
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            raise ValidationError(
                field=field_name,
                value=str(user_id),
                validation_rule="整數格式",
                message=f"{field_name}必須為有效的整數"
            )
        
        # Discord Snowflake ID的基本檢查
        if user_id <= 0:
            raise ValidationError(
                field=field_name,
                value=str(user_id),
                validation_rule="正整數",
                message=f"{field_name}必須為正整數"
            )
        
        # Discord ID通常是17-19位數字
        if len(str(user_id)) < 15 or len(str(user_id)) > 20:
            raise ValidationError(
                field=field_name,
                value=str(user_id),
                validation_rule="長度檢查",
                message=f"{field_name}長度不符合Discord ID格式"
            )
    
    def _validate_channel_list(self, channel_ids: List[int]) -> None:
        """驗證頻道ID列表"""
        if not isinstance(channel_ids, list):
            raise ValidationError(
                field="channel_restrictions",
                value=str(type(channel_ids)),
                validation_rule="列表類型",
                message="頻道限制必須為列表"
            )
        
        if len(channel_ids) > self.security_policy.max_channel_count:
            raise ValidationError(
                field="channel_restrictions",
                value=str(len(channel_ids)),
                validation_rule=f"最大數量{self.security_policy.max_channel_count}",
                message=f"頻道數量不能超過{self.security_policy.max_channel_count}個"
            )
        
        for i, channel_id in enumerate(channel_ids):
            try:
                self._validate_user_id(channel_id, f"channel_restrictions[{i}]")
            except ValidationError as e:
                raise ValidationError(
                    field=f"channel_restrictions[{i}]",
                    value=str(channel_id),
                    validation_rule=e.validation_rule,
                    message=f"第{i+1}個頻道ID無效: {e.message}"
                )
        
        # 檢查重複
        if len(set(channel_ids)) != len(channel_ids):
            raise ValidationError(
                field="channel_restrictions",
                value="存在重複",
                validation_rule="唯一性檢查",
                message="頻道ID列表中存在重複項"
            )
    
    def _validate_ai_model(self, ai_model: str) -> None:
        """驗證AI模型名稱"""
        if not isinstance(ai_model, str):
            raise ValidationError(
                field="ai_model",
                value=str(type(ai_model)),
                validation_rule="字符串類型",
                message="AI模型名稱必須為字符串"
            )
        
        ai_model = ai_model.strip()
        if not ai_model:
            raise ValidationError(
                field="ai_model",
                value="空字符串",
                validation_rule="非空檢查",
                message="AI模型名稱不能為空"
            )
        
        # 支持的AI模型列表（示例）
        supported_models = {
            'gpt-3.5-turbo', 'gpt-4', 'claude-3-sonnet', 
            'claude-3-haiku', 'gemini-pro', 'llama-2-70b'
        }
        
        if ai_model not in supported_models:
            # 這裡只是警告，不會阻止創建
            raise ValidationError(
                field="ai_model",
                value=ai_model,
                validation_rule="支持的模型檢查",
                message=f"AI模型 '{ai_model}' 可能不被支持。支持的模型：{', '.join(supported_models)}"
            )
    
    def _validate_personality_content(self, personality: str) -> None:
        """驗證個性設定內容"""
        if not isinstance(personality, str):
            raise ValidationError(
                field="personality",
                value=str(type(personality)),
                validation_rule="字符串類型",
                message="個性設定必須為字符串"
            )
        
        personality = personality.strip()
        if len(personality) > self.security_policy.max_content_length:
            raise ValidationError(
                field="personality",
                value=f"長度:{len(personality)}",
                validation_rule=f"最大長度{self.security_policy.max_content_length}",
                message=f"個性設定不能超過{self.security_policy.max_content_length}個字符"
            )
        
        # 檢查不當內容
        for pattern in self.security_policy.forbidden_patterns:
            if re.search(pattern, personality):
                raise ValidationError(
                    field="personality",
                    value="包含不當內容",
                    validation_rule="內容安全檢查",
                    message="個性設定包含不允許的內容"
                )
    
    def _check_rate_limit(self, user_id: int, operation: str) -> None:
        """檢查操作速率限制"""
        with self._lock:
            now = datetime.now()
            key = f"{user_id}:{operation}"
            
            if key not in self._operation_counts:
                self._operation_counts[key] = []
            
            # 清理過期的操作記錄（1分鐘前）
            self._operation_counts[key] = [
                timestamp for timestamp in self._operation_counts[key]
                if (now - timestamp).total_seconds() < 60
            ]
            
            # 檢查是否超過限制
            if len(self._operation_counts[key]) >= self.security_policy.max_operations_per_minute:
                raise SecurityError(
                    message=f"操作頻率過高，請稍後再試。限制：每分鐘{self.security_policy.max_operations_per_minute}次操作",
                    security_context="rate_limit"
                )
            
            # 記錄這次操作
            self._operation_counts[key].append(now)
    
    def sanitize_content(self, content: str) -> str:
        """
        高級內容清理和XSS防護
        
        實施多層防護機制：
        1. HTML標籤移除和編碼
        2. 危險字符過濾
        3. 腳本注入防護
        4. URL和連結驗證
        """
        if not isinstance(content, str):
            return ""
        
        # 第一層：移除和編碼HTML標籤
        content = self._remove_html_tags(content)
        content = self._html_encode_special_chars(content)
        
        # 第二層：移除危險字符和控制字符
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
        
        # 第三層：腳本注入防護
        content = self._prevent_script_injection(content)
        
        # 第四層：URL和連結安全檢查
        content = self._sanitize_urls(content)
        
        # 第五層：移除多餘空白字符
        content = re.sub(r'\s+', ' ', content.strip())
        
        # 最終長度限制
        if len(content) > self.security_policy.max_content_length:
            content = content[:self.security_policy.max_content_length-3] + "..."
        
        return content
    
    def _remove_html_tags(self, content: str) -> str:
        """移除所有HTML標籤"""
        import html
        
        # 移除HTML標籤
        clean_content = re.sub(r'<[^>]*>', '', content)
        
        # 解碼HTML實體
        clean_content = html.unescape(clean_content)
        
        return clean_content
    
    def _html_encode_special_chars(self, content: str) -> str:
        """編碼特殊HTML字符"""
        import html
        
        # 編碼危險字符
        dangerous_chars = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '&': '&amp;'
        }
        
        for char, encoded in dangerous_chars.items():
            content = content.replace(char, encoded)
        
        return content
    
    def _prevent_script_injection(self, content: str) -> str:
        """防止腳本注入攻擊"""
        
        # 危險的腳本關鍵詞
        dangerous_patterns = [
            r'(?i)javascript:',
            r'(?i)data:text/html',
            r'(?i)vbscript:',
            r'(?i)on\w+\s*=',  # onclick, onload等事件
            r'(?i)<script[^>]*>',
            r'(?i)</script>',
            r'(?i)expression\s*\(',
            r'(?i)url\s*\(',
            r'(?i)@import',
            r'(?i)document\.',
            r'(?i)window\.',
            r'(?i)eval\s*\(',
            r'(?i)function\s*\(',
        ]
        
        for pattern in dangerous_patterns:
            content = re.sub(pattern, '[FILTERED]', content)
        
        return content
    
    def _sanitize_urls(self, content: str) -> str:
        """清理和驗證URL"""
        
        # URL模式匹配
        url_pattern = r'https?://[^\s<>"\'&;]+'
        
        def validate_url(match):
            url = match.group(0)
            
            # 檢查是否為安全的URL
            if self._is_safe_url(url):
                return url
            else:
                return '[FILTERED_URL]'
        
        # 替換URL
        content = re.sub(url_pattern, validate_url, content)
        
        return content
    
    def _is_safe_url(self, url: str) -> bool:
        """檢查URL是否安全（使用CSP策略）"""
        
        # 如果不允許外部連結
        if not self.content_security_policy.allow_external_links:
            return False
        
        # URL長度檢查
        if len(url) > self.content_security_policy.max_url_length:
            return False
        
        # 危險的URL模式
        dangerous_url_patterns = [
            r'(?i)javascript:',
            r'(?i)data:',
            r'(?i)vbscript:',
            r'(?i)file:',
            r'(?i)ftp:',
        ]
        
        for pattern in dangerous_url_patterns:
            if re.search(pattern, url):
                return False
        
        # 檢查被阻止的域名
        if self.content_security_policy.blocked_domains:
            for domain in self.content_security_policy.blocked_domains:
                if domain.lower() in url.lower():
                    logger.warning(f"阻止的域名檢測到: {domain} 在URL中: {url}")
                    return False
        
        # 如果設定了允許的域名列表，檢查是否在列表中
        if self.content_security_policy.allowed_domains:
            url_is_allowed = False
            for domain in self.content_security_policy.allowed_domains:
                if domain.lower() in url.lower():
                    url_is_allowed = True
                    break
            
            if not url_is_allowed:
                logger.warning(f"URL不在允許列表中: {url}")
                return False
        
        return True
    
    async def validate_message_content(self, content: str, user_id: int) -> Dict[str, Any]:
        """驗證訊息內容"""
        errors = []
        warnings = []
        
        # 檢查內容長度
        if len(content) > self.security_policy.max_content_length:
            errors.append(f"訊息內容過長，最大長度為{self.security_policy.max_content_length}字符")
        
        # 內容安全檢查
        for pattern in self.security_policy.forbidden_patterns:
            if re.search(pattern, content):
                warnings.append("訊息內容可能包含不適當的內容")
                break
        
        # 檢查訊息發送頻率
        try:
            self._check_rate_limit(user_id, "send_message")
        except SecurityError as e:
            errors.append(str(e))
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'sanitized_content': self.sanitize_content(content)
        }


class ConcurrencyManager:
    """並發安全管理器"""
    
    def __init__(self, max_concurrent_operations: int = 10):
        self.max_concurrent_operations = max_concurrent_operations
        self._operation_semaphore = asyncio.Semaphore(max_concurrent_operations)
        self._active_operations: Dict[str, Set[str]] = {}
        self._operation_lock = asyncio.Lock()
        
        self.logger = logging.getLogger(f'{__name__}.ConcurrencyManager')
    
    async def acquire_operation_lock(self, operation_type: str, resource_id: str) -> None:
        """獲取操作鎖"""
        await self._operation_semaphore.acquire()
        
        async with self._operation_lock:
            if operation_type not in self._active_operations:
                self._active_operations[operation_type] = set()
            
            if resource_id in self._active_operations[operation_type]:
                self._operation_semaphore.release()
                raise SubBotError(
                    f"資源 {resource_id} 正在執行 {operation_type} 操作，請稍後再試"
                )
            
            self._active_operations[operation_type].add(resource_id)
            self.logger.debug(f"獲得操作鎖: {operation_type}:{resource_id}")
    
    async def release_operation_lock(self, operation_type: str, resource_id: str) -> None:
        """釋放操作鎖"""
        async with self._operation_lock:
            if (operation_type in self._active_operations and 
                resource_id in self._active_operations[operation_type]):
                self._active_operations[operation_type].remove(resource_id)
                self.logger.debug(f"釋放操作鎖: {operation_type}:{resource_id}")
        
        self._operation_semaphore.release()
    
    async def safe_operation(self, operation_type: str, resource_id: str, coro_func):
        """安全執行操作"""
        await self.acquire_operation_lock(operation_type, resource_id)
        
        try:
            result = await coro_func()
            return result
        finally:
            await self.release_operation_lock(operation_type, resource_id)


# 全局實例
default_validator = InputValidator()
default_concurrency_manager = ConcurrencyManager()