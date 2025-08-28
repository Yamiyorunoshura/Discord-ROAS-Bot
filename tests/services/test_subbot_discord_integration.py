"""
SubBot服務集成測試 - Discord Token連線驗證
Task ID: 1 - 核心架構和基礎設施建置

驗證子機器人服務可以使用真實的Discord Token建立連線
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.services.subbot_service import SubBotService
from src.core.errors import SubBotCreationError, SubBotTokenError, SubBotChannelError


@pytest.fixture
def subbot_service():
    """創建SubBot服務實例用於測試"""
    return SubBotService(encryption_key="test_integration_key_32bytes_123456")


@pytest.fixture
def mock_discord_client():
    """模擬Discord客戶端"""
    mock_client = Mock()
    mock_client.is_ready.return_value = True
    mock_client.is_closed.return_value = False
    mock_client.latency = 0.05  # 50ms延遲
    mock_client.guilds = [Mock(name="Test Guild", id=123456789)]
    
    # 模擬連線方法
    mock_client.start = AsyncMock()
    mock_client.close = AsyncMock()
    mock_client.wait_until_ready = AsyncMock()
    
    return mock_client


@pytest.fixture
def valid_discord_token():
    """有效的Discord Token格式（測試用假Token）"""
    # Discord Bot Token格式：base64編碼的Bot ID + . + timestamp + . + HMAC
    return "MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.dQw4w9WgXcQ-_example_test_token"


class TestDiscordTokenIntegration:
    """Discord Token集成測試"""
    
    @pytest.mark.asyncio
    async def test_create_subbot_with_valid_token(self, subbot_service, valid_discord_token):
        """測試使用有效Token創建子機器人"""
        
        with patch('src.services.subbot_service.discord') as mock_discord:
            # 模擬Discord.py客戶端
            mock_client = Mock()
            mock_client.is_ready.return_value = False
            mock_client.start = AsyncMock()
            mock_client.wait_until_ready = AsyncMock()
            mock_discord.Client.return_value = mock_client
            
            # 創建子機器人
            result = await subbot_service.create_subbot(
                name="TestBot",
                token=valid_discord_token,
                owner_id=123456789,
                channel_restrictions=[]
            )
            
            assert result["success"] is True, "創建子機器人應該成功"
            assert "bot_id" in result, "結果應該包含bot_id"
            assert result["bot_id"] in subbot_service.registered_bots, "子機器人應該被註冊"
            
            # 驗證Token已正確加密存儲
            bot_config = subbot_service.registered_bots[result["bot_id"]]
            assert "token_hash" in bot_config, "Token應該以加密形式存儲"
            assert bot_config["token_hash"] != valid_discord_token, "存儲的Token不應該是明文"
    
    @pytest.mark.asyncio
    async def test_connect_subbot_with_encrypted_token(self, subbot_service, valid_discord_token):
        """測試使用加密Token連線子機器人"""
        
        with patch('src.services.subbot_service.discord') as mock_discord:
            mock_client = Mock()
            mock_client.is_ready.return_value = False
            mock_client.start = AsyncMock()
            mock_client.wait_until_ready = AsyncMock()
            mock_discord.Client.return_value = mock_client
            
            # 首先創建子機器人
            create_result = await subbot_service.create_subbot(
                name="TestBot",
                token=valid_discord_token,
                owner_id=123456789,
                channel_restrictions=[]
            )
            
            bot_id = create_result["bot_id"]
            
            # 測試連線
            connect_result = await subbot_service.connect_subbot(bot_id)
            
            assert connect_result["success"] is True, "連線子機器人應該成功"
            assert bot_id in subbot_service.active_connections, "子機器人應該在活躍連線中"
            
            # 驗證Discord客戶端使用了解密後的真實Token
            mock_client.start.assert_called_once()
            # 檢查start方法的調用參數（解密後的Token）
            args, kwargs = mock_client.start.call_args
            decrypted_token = args[0] if args else None
            assert decrypted_token == valid_discord_token, "應該使用解密後的真實Token連線"
    
    @pytest.mark.asyncio
    async def test_token_decryption_in_connect_flow(self, subbot_service, valid_discord_token):
        """測試連線流程中的Token解密"""
        
        # 直接測試加密-解密循環
        encrypted_token = subbot_service._encrypt_token(valid_discord_token)
        decrypted_token = subbot_service._decrypt_token(encrypted_token)
        
        assert decrypted_token == valid_discord_token, "Token解密應該得到原始Token"
        
        # 模擬存儲和檢索流程
        bot_config = {
            'name': 'TestBot',
            'token_hash': encrypted_token,
            'owner_id': 123456789,
            'status': 'offline'
        }
        
        # 模擬從存儲中檢索Token並解密
        retrieved_token = subbot_service._decrypt_token(bot_config['token_hash'])
        assert retrieved_token == valid_discord_token, "從存儲檢索的Token應該正確解密"
    
    @pytest.mark.asyncio
    async def test_invalid_token_connection_failure(self, subbot_service):
        """測試無效Token的連線失敗處理"""
        invalid_token = "invalid.token.format"
        
        with patch('src.services.subbot_service.discord') as mock_discord:
            mock_client = Mock()
            # 模擬Discord連線失敗
            mock_client.start = AsyncMock(side_effect=Exception("Invalid token"))
            mock_discord.Client.return_value = mock_client
            
            # 嘗試創建子機器人（應該在連線階段失敗）
            with pytest.raises((SubBotCreationError, SubBotTokenError)):
                await subbot_service.create_subbot(
                    name="InvalidBot",
                    token=invalid_token,
                    owner_id=123456789,
                    channel_restrictions=[]
                )
    
    @pytest.mark.asyncio
    async def test_token_validation_format(self, subbot_service):
        """測試Discord Token格式驗證"""
        
        # 測試各種Token格式
        test_cases = [
            ("valid.token.format", True),  # 基本格式
            ("MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.dQw4w9WgXcQ", True),  # 標準格式
            ("", False),  # 空Token
            ("invalid", False),  # 無效格式
            ("too.short", False),  # 太短
            ("no.dots.in.wrong.places", False),  # 錯誤的點數量
        ]
        
        for token, should_be_valid in test_cases:
            result = subbot_service._validate_token(token)
            if should_be_valid:
                assert result is True, f"Token {token} 應該通過驗證"
            else:
                assert result is False, f"Token {token} 應該驗證失敗"
    
    @pytest.mark.asyncio
    async def test_disconnect_subbot_cleanup(self, subbot_service, valid_discord_token):
        """測試斷開連線時的清理工作"""
        
        with patch('src.services.subbot_service.discord') as mock_discord:
            mock_client = Mock()
            mock_client.is_ready.return_value = True
            mock_client.start = AsyncMock()
            mock_client.close = AsyncMock()
            mock_client.wait_until_ready = AsyncMock()
            mock_discord.Client.return_value = mock_client
            
            # 創建並連線子機器人
            create_result = await subbot_service.create_subbot(
                name="TestBot",
                token=valid_discord_token,
                owner_id=123456789,
                channel_restrictions=[]
            )
            
            bot_id = create_result["bot_id"]
            await subbot_service.connect_subbot(bot_id)
            
            # 驗證連線已建立
            assert bot_id in subbot_service.active_connections
            
            # 斷開連線
            disconnect_result = await subbot_service.disconnect_subbot(bot_id)
            
            assert disconnect_result["success"] is True, "斷開連線應該成功"
            assert bot_id not in subbot_service.active_connections, "應該從活躍連線中移除"
            
            # 驗證Discord客戶端已關閉
            mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multiple_subbots_independent_tokens(self, subbot_service):
        """測試多個子機器人使用獨立的Token"""
        tokens = [
            "MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.token1",
            "MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.token2",
            "MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.token3"
        ]
        
        bot_ids = []
        
        with patch('src.services.subbot_service.discord') as mock_discord:
            mock_clients = []
            
            def create_mock_client():
                client = Mock()
                client.is_ready.return_value = False
                client.start = AsyncMock()
                client.wait_until_ready = AsyncMock()
                mock_clients.append(client)
                return client
            
            mock_discord.Client.side_effect = create_mock_client
            
            # 創建多個子機器人
            for i, token in enumerate(tokens):
                result = await subbot_service.create_subbot(
                    name=f"TestBot{i}",
                    token=token,
                    owner_id=123456789,
                    channel_restrictions=[]
                )
                bot_ids.append(result["bot_id"])
            
            # 驗證每個子機器人都有獨立的加密Token
            encrypted_tokens = []
            for bot_id in bot_ids:
                bot_config = subbot_service.registered_bots[bot_id]
                encrypted_tokens.append(bot_config["token_hash"])
            
            # 所有加密後的Token都應該不同
            assert len(set(encrypted_tokens)) == len(encrypted_tokens), \
                "每個子機器人的加密Token都應該是唯一的"
            
            # 連線所有子機器人
            for bot_id in bot_ids:
                connect_result = await subbot_service.connect_subbot(bot_id)
                assert connect_result["success"] is True, f"子機器人 {bot_id} 連線應該成功"
            
            # 驗證所有客戶端都被正確調用
            assert len(mock_clients) == len(tokens), "應該為每個子機器人創建客戶端"
            
            for i, client in enumerate(mock_clients):
                client.start.assert_called_once()
                # 驗證使用了正確的Token
                args, kwargs = client.start.call_args
                decrypted_token = args[0] if args else None
                assert decrypted_token == tokens[i], f"客戶端 {i} 應該使用對應的Token"


class TestErrorHandling:
    """錯誤處理測試"""
    
    @pytest.mark.asyncio
    async def test_connection_failure_recovery(self, subbot_service, valid_discord_token):
        """測試連線失敗的恢復機制"""
        
        with patch('src.services.subbot_service.discord') as mock_discord:
            mock_client = Mock()
            # 第一次連線失敗，第二次成功
            mock_client.start = AsyncMock(side_effect=[
                Exception("Connection failed"), 
                None  # 成功
            ])
            mock_client.wait_until_ready = AsyncMock()
            mock_discord.Client.return_value = mock_client
            
            # 創建子機器人
            create_result = await subbot_service.create_subbot(
                name="TestBot",
                token=valid_discord_token,
                owner_id=123456789,
                channel_restrictions=[]
            )
            
            bot_id = create_result["bot_id"]
            
            # 第一次連線應該失敗
            with pytest.raises(Exception):
                await subbot_service.connect_subbot(bot_id)
            
            # 第二次連線應該成功
            connect_result = await subbot_service.connect_subbot(bot_id)
            assert connect_result["success"] is True
    
    @pytest.mark.asyncio
    async def test_token_decryption_error_handling(self, subbot_service):
        """測試Token解密錯誤處理"""
        
        # 創建一個損壞的Token記錄
        corrupted_bot_config = {
            'name': 'CorruptedBot',
            'token_hash': 'corrupted_encrypted_data',
            'owner_id': 123456789,
            'status': 'offline'
        }
        
        bot_id = "corrupted_bot_123"
        subbot_service.registered_bots[bot_id] = corrupted_bot_config
        
        # 嘗試連線應該失敗並產生適當的錯誤
        with pytest.raises(SubBotTokenError, match="Token解密失敗"):
            await subbot_service.connect_subbot(bot_id)


class TestSecurityIntegration:
    """安全集成測試"""
    
    @pytest.mark.asyncio
    async def test_no_plaintext_token_in_memory(self, subbot_service, valid_discord_token):
        """測試記憶體中不存在明文Token"""
        
        with patch('src.services.subbot_service.discord') as mock_discord:
            mock_client = Mock()
            mock_client.start = AsyncMock()
            mock_client.wait_until_ready = AsyncMock()
            mock_discord.Client.return_value = mock_client
            
            # 創建子機器人
            create_result = await subbot_service.create_subbot(
                name="SecureBot",
                token=valid_discord_token,
                owner_id=123456789,
                channel_restrictions=[]
            )
            
            bot_id = create_result["bot_id"]
            
            # 檢查服務物件中是否包含明文Token
            service_dict = subbot_service.__dict__
            service_str = str(service_dict)
            
            # 明文Token不應該出現在服務物件的字符串表示中
            assert valid_discord_token not in service_str, \
                "明文Token不應該存在於服務物件中"
            
            # 檢查註冊表中的Token是加密的
            bot_config = subbot_service.registered_bots[bot_id]
            assert bot_config["token_hash"] != valid_discord_token, \
                "存儲的Token應該是加密的，不是明文"
    
    def test_encryption_key_not_logged(self, subbot_service, caplog):
        """測試加密密鑰不會被記錄到日誌中"""
        import logging
        
        # 觸發一些日誌記錄
        with caplog.at_level(logging.INFO):
            subbot_service.get_encryption_info()
        
        # 檢查日誌中不包含加密密鑰
        log_output = caplog.text
        if len(subbot_service._encryption_key) > 10:
            assert subbot_service._encryption_key not in log_output, \
                "加密密鑰不應該出現在日誌中"


if __name__ == "__main__":
    pytest.main([__file__])