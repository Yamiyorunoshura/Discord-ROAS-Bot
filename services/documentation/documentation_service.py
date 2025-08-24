"""
文檔生成和管理服務
Task ID: 11 - 建立文件和部署準備

提供自動化文檔生成、版本管理和品質驗證功能
"""

import os
import re
import ast
import json
import hashlib
import inspect
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Type, Set
from datetime import datetime, timedelta
import asyncio

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError, ValidationError

# 匯入新的連結檢查功能
from .link_checker_service import LinkCheckerService
from .api_endpoints import LinkCheckAPI, get_link_check_api
from .link_checker_models import LinkCheckConfig

from .models import (
    DocumentConfig, DocumentVersion, DocumentCategory, 
    DocumentFormat, DocumentStatus, DocumentGenerationRequest,
    DocumentValidationResult, DocumentationMetrics, 
    APIDocumentationInfo
)

logger = logging.getLogger('services.documentation')


class DocumentationService(BaseService):
    """
    文檔生成和管理服務
    
    功能：
    - 自動生成API文檔
    - 管理文檔版本控制
    - 驗證文檔品質和完整性
    - 支援多種文檔格式
    - 提供文檔搜尋和索引
    """
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__("DocumentationService")
        self.db_manager = db_manager
        self.add_dependency(db_manager, "db_manager")
        
        # 配置
        self.docs_root_path = Path("docs")
        self.api_docs_path = self.docs_root_path / "api"
        self.user_docs_path = self.docs_root_path / "user"
        self.technical_docs_path = self.docs_root_path / "technical"
        
        # 文檔模板路徑
        self.templates_path = Path("docs/templates")
        
        # 支援的檔案副檔名
        self.supported_extensions = {'.py', '.md', '.yaml', '.yml', '.json'}
        
        # 文檔配置快取
        self._document_configs: Dict[str, DocumentConfig] = {}
        self._last_cache_update: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=30)
        
        # 新增：連結檢查服務
        self._link_checker_service: Optional[LinkCheckerService] = None
        self._link_check_api: Optional[LinkCheckAPI] = None
    
    async def _initialize(self) -> bool:
        """初始化文檔服務"""
        try:
            # 創建必要的目錄結構
            await self._create_directory_structure()
            
            # 初始化資料庫表
            await self._initialize_database()
            
            # 載入文檔配置
            await self._load_document_configs()
            
            # 初始化連結檢查服務
            await self._initialize_link_checker()
            
            self.logger.info("文檔服務初始化完成")
            return True
            
        except Exception as e:
            self.logger.exception(f"文檔服務初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理文檔服務資源"""
        # 清理連結檢查服務
        if self._link_checker_service:
            await self._link_checker_service.shutdown()
            self._link_checker_service = None
            
        if self._link_check_api:
            await self._link_check_api.shutdown()
            self._link_check_api = None
            
        self._document_configs.clear()
        self.logger.info("文檔服務清理完成")
    
    async def _validate_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """驗證文檔操作權限"""
        # 文檔操作通常需要管理員權限
        if action in ['generate_docs', 'update_config', 'delete_doc']:
            # 這裡應該檢查使用者是否有管理員權限
            # 暫時允許所有操作
            return True
        
        # 查看文檔的權限較寬鬆
        if action in ['view_docs', 'search_docs']:
            return True
        
        return False
    
    async def _create_directory_structure(self):
        """創建文檔目錄結構"""
        directories = [
            self.docs_root_path,
            self.api_docs_path,
            self.user_docs_path,
            self.technical_docs_path,
            self.templates_path,
            self.docs_root_path / "architecture",
            self.docs_root_path / "developer",
            self.docs_root_path / "troubleshooting"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("文檔目錄結構創建完成")
    
    async def _initialize_database(self):
        """初始化文檔相關的資料庫表"""
        create_docs_config_table = """
        CREATE TABLE IF NOT EXISTS doc_config (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            path TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            format TEXT DEFAULT 'markdown',
            status TEXT DEFAULT 'draft',
            template_path TEXT,
            auto_generate BOOLEAN DEFAULT FALSE,
            update_frequency INTEGER,
            dependencies TEXT,
            metadata TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        create_docs_version_table = """
        CREATE TABLE IF NOT EXISTS doc_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            version TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            file_path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            author TEXT NOT NULL,
            commit_message TEXT,
            is_current BOOLEAN DEFAULT FALSE,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES doc_config (id)
        )
        """
        
        await self.db_manager.execute(create_docs_config_table)
        await self.db_manager.execute(create_docs_version_table)
        
        self.logger.info("文檔資料庫表初始化完成")
    
    async def _load_document_configs(self):
        """載入文檔配置"""
        try:
            rows = await self.db_manager.fetchall(
                "SELECT * FROM doc_config ORDER BY created_at"
            )
            
            self._document_configs.clear()
            for row in rows:
                config = DocumentConfig(
                    id=row['id'],
                    category=DocumentCategory(row['category']),
                    path=row['path'],
                    title=row['title'],
                    description=row['description'],
                    format=DocumentFormat(row['format']),
                    status=DocumentStatus(row['status']),
                    template_path=row['template_path'],
                    auto_generate=bool(row['auto_generate']),
                    update_frequency=row['update_frequency'],
                    dependencies=json.loads(row['dependencies']) if row['dependencies'] else [],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    created_at=row['created_at'],
                    updated_at=row['last_updated']
                )
                self._document_configs[config.id] = config
            
            self._last_cache_update = datetime.now()
            self.logger.info(f"載入了 {len(self._document_configs)} 個文檔配置")
            
        except Exception as e:
            self.logger.exception(f"載入文檔配置失敗：{e}")
            raise ServiceError(
                f"載入文檔配置失敗：{e}", 
                service_name=self.name,
                operation="load_document_configs"
            )
    
    async def generate_api_docs(self, service_classes: List[Type] = None) -> bool:
        """
        生成API文檔
        
        參數：
            service_classes: 要生成文檔的服務類別列表，None表示掃描所有服務
            
        返回：
            是否生成成功
        """
        try:
            if service_classes is None:
                service_classes = await self._discover_service_classes()
            
            api_docs = []
            for service_class in service_classes:
                service_docs = await self._extract_service_documentation(service_class)
                api_docs.extend(service_docs)
            
            # 生成API文檔內容
            api_doc_content = await self._generate_api_doc_content(api_docs)
            
            # 儲存API文檔
            api_doc_path = self.api_docs_path / "api_reference.md"
            await self._save_document(
                "api_reference",
                api_doc_content,
                api_doc_path,
                DocumentCategory.API
            )
            
            self.logger.info(f"API文檔生成完成，包含 {len(api_docs)} 個API方法")
            return True
            
        except Exception as e:
            self.logger.exception(f"生成API文檔失敗：{e}")
            return False
    
    async def _discover_service_classes(self) -> List[Type]:
        """自動發現服務類別"""
        service_classes = []
        services_path = Path("services")
        discovered_services = set()  # 防止重複添加
        
        if not services_path.exists():
            return service_classes
        
        for service_dir in services_path.iterdir():
            if service_dir.is_dir() and not service_dir.name.startswith('_'):
                service_module_path = service_dir / f"{service_dir.name}_service.py"
                if service_module_path.exists():
                    # 動態導入模組並提取服務類別
                    try:
                        module_name = f"services.{service_dir.name}.{service_dir.name}_service"
                        module = __import__(module_name, fromlist=[''])
                        
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (inspect.isclass(attr) and 
                                attr_name.endswith('Service') and 
                                attr_name != 'BaseService' and
                                attr_name not in discovered_services):  # 避免重複
                                service_classes.append(attr)
                                discovered_services.add(attr_name)
                                
                    except Exception as e:
                        self.logger.warning(f"無法載入服務模組 {module_name}：{e}")
        
        self.logger.info(f"發現 {len(service_classes)} 個服務類別：{[cls.__name__ for cls in service_classes]}")
        return service_classes
    
    async def _extract_service_documentation(self, service_class: Type) -> List[APIDocumentationInfo]:
        """提取服務類別的文檔信息"""
        docs = []
        
        # 排除BaseService的基礎方法，只提取服務特有的方法
        base_service_methods = set(dir(BaseService))
        
        for method_name in dir(service_class):
            if method_name.startswith('_'):
                continue
                
            # 跳過BaseService的基礎方法
            if method_name in base_service_methods:
                continue
                
            method = getattr(service_class, method_name)
            if not inspect.ismethod(method) and not inspect.isfunction(method):
                continue
            
            # 提取方法文檔
            doc_info = await self._extract_method_documentation(
                service_class.__name__,
                method_name,
                method
            )
            
            if doc_info:
                docs.append(doc_info)
        
        return docs
    
    async def _extract_method_documentation(self, class_name: str, method_name: str, method) -> Optional[APIDocumentationInfo]:
        """提取方法的文檔信息"""
        try:
            # 獲取方法簽名
            sig = inspect.signature(method)
            docstring = inspect.getdoc(method)
            
            # 如果沒有文檔字符串，為常見方法提供預設描述
            if not docstring:
                docstring = self._get_default_method_description(method_name)
            
            if not docstring:
                return None
            
            # 解析完整的文檔字符串
            parsed_doc = await self._parse_docstring(docstring)
            
            # 解析文檔字符串
            doc_info = APIDocumentationInfo(
                service_name=class_name,
                class_name=class_name,
                method_name=method_name,
                description=parsed_doc['description'],
                parameters=[],
                return_type="Any",
                return_description=parsed_doc.get('return_description', ''),
                exceptions=[],
                examples=[]
            )
            
            # 提取參數信息
            param_descriptions = parsed_doc.get('param_descriptions', {})
            for param_name, param in sig.parameters.items():
                if param_name not in ['self', 'cls']:
                    param_type = self._format_type_annotation(param.annotation)
                    param_info = {
                        'name': param_name,
                        'type': param_type,
                        'default': str(param.default) if param.default != param.empty else None,
                        'required': param.default == param.empty,
                        'description': param_descriptions.get(param_name, '')
                    }
                    doc_info.parameters.append(param_info)
            
            # 提取返回類型
            if sig.return_annotation != sig.empty:
                doc_info.return_type = self._format_type_annotation(sig.return_annotation)
            
            # 提取異常信息
            doc_info.exceptions = parsed_doc.get('exceptions', [])
            
            # 生成使用範例
            doc_info.examples = await self._generate_method_examples(class_name, method_name, doc_info.parameters)
            
            return doc_info
            
        except Exception as e:
            self.logger.warning(f"提取方法 {class_name}.{method_name} 文檔失敗：{e}")
            return None
    
    async def _generate_api_doc_content(self, api_docs: List[APIDocumentationInfo]) -> str:
        """生成API文檔內容"""
        content = [
            "# API 參考文檔",
            "",
            "本文檔包含所有服務層API的詳細說明。",
            "",
            f"**生成時間：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**API數量：** {len(api_docs)}",
            "",
            "## 目錄",
            ""
        ]
        
        # 按服務分組
        services = {}
        for doc in api_docs:
            if doc.service_name not in services:
                services[doc.service_name] = []
            services[doc.service_name].append(doc)
        
        # 生成目錄
        for service_name in sorted(services.keys()):
            content.append(f"- [{service_name}](#{service_name.lower()})")
        
        content.append("")
        
        # 生成服務文檔
        for service_name in sorted(services.keys()):
            content.extend([
                f"## {service_name}",
                "",
                f"### 方法列表",
                ""
            ])
            
            for doc in services[service_name]:
                content.extend([
                    f"#### `{doc.method_name}()`",
                    "",
                    doc.description,
                    ""
                ])
                
                if doc.parameters:
                    content.append("**參數：**")
                    content.append("")
                    for param in doc.parameters:
                        required_text = "必需" if param['required'] else "可選"
                        default_text = f"（預設：{param['default']}）" if param['default'] else ""
                        content.append(f"- `{param['name']}` ({param['type']}, {required_text}){default_text}: {param['description']}")
                    content.append("")
                
                content.extend([
                    f"**返回：** {doc.return_type}",
                    "",
                    doc.return_description if doc.return_description else f"返回 {doc.method_name} 的執行結果",
                    ""
                ])
                
                if doc.exceptions:
                    content.append("**異常：**")
                    content.append("")
                    for exc in doc.exceptions:
                        content.append(f"- `{exc['type']}`: {exc['description']}")
                    content.append("")
                
                if doc.examples:
                    content.append("**範例：**")
                    content.append("")
                    for example in doc.examples:
                        if example.get('description'):
                            content.append(f"*{example['description']}*")
                            content.append("")
                        content.extend([
                            f"```{example.get('language', 'python')}",
                            example['code'],
                            "```",
                            ""
                        ])
                
                content.append("---")
                content.append("")
        
        return "\n".join(content)
    
    def _get_default_method_description(self, method_name: str) -> Optional[str]:
        """為常見方法名稱提供預設描述"""
        default_descriptions = {
            'create_account': '建立新的帳戶',
            'get_account': '取得帳戶資訊',
            'update_account': '更新帳戶資訊',
            'delete_account': '刪除帳戶',
            'deposit': '存款到帳戶',
            'withdraw': '從帳戶提款',
            'transfer': '在帳戶間轉帳',
            'get_balance': '取得帳戶餘額',
            'get_transaction_history': '取得交易歷史',
            'create_transaction': '建立新交易',
            'validate_transaction': '驗證交易',
            'get_achievements': '取得成就列表',
            'unlock_achievement': '解鎖成就',
            'check_achievement': '檢查成就達成狀態',
            'create_role': '建立新角色',
            'assign_role': '分配角色給使用者',
            'remove_role': '從使用者移除角色',
            'get_user_roles': '取得使用者角色',
            'send_welcome_message': '發送歡迎訊息',
            'configure_welcome': '設定歡迎訊息配置',
            'track_activity': '追蹤使用者活動',
            'get_activity_stats': '取得活動統計',
            'process_message': '處理訊息',
            'log_message': '記錄訊息',
            'get_messages': '取得訊息記錄',
            'start_election': '開始選舉',
            'vote': '投票',
            'get_election_results': '取得選舉結果',
            'create_proposal': '建立提案',
            'vote_on_proposal': '對提案投票',
        }
        return default_descriptions.get(method_name)
    
    async def _parse_docstring(self, docstring: str) -> Dict[str, Any]:
        """解析docstring並提取結構化信息"""
        lines = docstring.split('\n')
        result = {
            'description': '',
            'param_descriptions': {},
            'return_description': '',
            'exceptions': []
        }
        
        current_section = 'description'
        description_lines = []
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
                
            if line in ['參數：', 'Parameters:', '參数：']:
                current_section = 'parameters'
                continue
            elif line in ['返回：', 'Returns:', '返回值：', 'return:', 'Return:']:
                current_section = 'returns'
                continue
            elif line in ['異常：', 'Raises:', 'Exceptions:', '异常：']:
                current_section = 'exceptions'
                continue
            elif line in ['範例：', 'Examples:', '示例：', 'Example:']:
                current_section = 'examples'
                continue
            
            if current_section == 'description':
                description_lines.append(line)
            elif current_section == 'parameters':
                # 解析參數行，格式如：guild_id: Discord伺服器ID
                if ':' in line:
                    param_parts = line.split(':', 1)
                    param_name = param_parts[0].strip()
                    param_desc = param_parts[1].strip() if len(param_parts) > 1 else ''
                    result['param_descriptions'][param_name] = param_desc
            elif current_section == 'returns':
                result['return_description'] = line
            elif current_section == 'exceptions':
                # 解析異常行，格式如：ValidationError: 當參數無效時
                if ':' in line:
                    exc_parts = line.split(':', 1)
                    exc_type = exc_parts[0].strip()
                    exc_desc = exc_parts[1].strip() if len(exc_parts) > 1 else ''
                    result['exceptions'].append({
                        'type': exc_type,
                        'description': exc_desc
                    })
        
        result['description'] = ' '.join(description_lines) if description_lines else ''
        return result
    
    def _format_type_annotation(self, annotation) -> str:
        """統一格式化類型註解"""
        if annotation is None or annotation == inspect.Parameter.empty:
            return 'Any'
        
        type_str = str(annotation)
        
        # 統一格式化
        if type_str.startswith('<class '):
            # <class 'int'> -> int
            type_name = type_str[7:-2] if type_str.endswith("'>") else type_str[7:-1]
            return type_name.split('.')[-1]  # 只取最後的類型名稱
        elif type_str.startswith('<enum '):
            # <enum 'AccountType'> -> AccountType
            type_name = type_str[6:-2] if type_str.endswith("'>") else type_str[6:-1]
            return type_name.split('.')[-1]
        elif 'typing.' in type_str:
            # 簡化typing類型
            type_str = type_str.replace('typing.', '')
        
        return type_str
    
    async def _generate_method_examples(self, class_name: str, method_name: str, parameters: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """生成方法的使用範例"""
        examples = []
        
        # 根據服務類型和方法名稱生成具體範例
        service_examples = {
            'EconomyService': {
                'create_account': [
                    {
                        'language': 'python',
                        'description': '建立使用者帳戶',
                        'code': '''# 為使用者建立個人帳戶
account = await economy_service.create_account(
    guild_id=123456789,
    account_type=AccountType.USER,
    user_id=987654321,
    initial_balance=100.0
)
print(f"帳戶建立成功：{account.id}")'''
                    }
                ],
                'deposit': [
                    {
                        'language': 'python',
                        'description': '向帳戶存款',
                        'code': '''# 向指定帳戶存入資金
result = await economy_service.deposit(
    account_id="acc_123456789_987654321",
    amount=50.0,
    description="每日簽到獎勵"
)
print(f"存款成功，新餘額：{result.new_balance}")'''
                    }
                ],
                'transfer': [
                    {
                        'language': 'python',
                        'description': '帳戶間轉帳',
                        'code': '''# 在兩個帳戶間進行轉帳
transaction = await economy_service.transfer(
    from_account_id="acc_123456789_111111",
    to_account_id="acc_123456789_222222", 
    amount=25.0,
    description="轉帳給朋友"
)
print(f"轉帳成功，交易ID：{transaction.id}")'''
                    }
                ]
            },
            'AchievementService': {
                'unlock_achievement': [
                    {
                        'language': 'python',
                        'description': '解鎖使用者成就',
                        'code': '''# 為使用者解鎖特定成就
result = await achievement_service.unlock_achievement(
    guild_id=123456789,
    user_id=987654321,
    achievement_id="first_message"
)
print(f"成就解鎖：{result.achievement.title}")'''
                    }
                ],
                'get_user_achievements': [
                    {
                        'language': 'python', 
                        'description': '取得使用者成就列表',
                        'code': '''# 取得使用者所有成就
achievements = await achievement_service.get_user_achievements(
    guild_id=123456789,
    user_id=987654321,
    include_locked=False
)
print(f"使用者共有 {len(achievements)} 個成就")'''
                    }
                ]
            },
            'GovernmentService': {
                'create_proposal': [
                    {
                        'language': 'python',
                        'description': '建立新提案',
                        'code': '''# 建立新的政府提案
proposal = await government_service.create_proposal(
    guild_id=123456789,
    proposer_id=987654321,
    title="增加新的頻道分類",
    description="提議新增遊戲討論頻道分類",
    proposal_type=ProposalType.POLICY
)
print(f"提案建立成功：{proposal.id}")'''
                    }
                ],
                'vote': [
                    {
                        'language': 'python',
                        'description': '對提案投票',
                        'code': '''# 對提案進行投票
vote_result = await government_service.vote(
    proposal_id="prop_123456",
    voter_id=111222333,
    vote_type=VoteType.APPROVE,
    reason="支持這個想法"
)
print(f"投票成功：{vote_result.vote.vote_type}")'''
                    }
                ]
            },
            'WelcomeService': {
                'send_welcome_message': [
                    {
                        'language': 'python',
                        'description': '發送歡迎訊息',
                        'code': '''# 向新成員發送歡迎訊息
result = await welcome_service.send_welcome_message(
    guild_id=123456789,
    user_id=987654321,
    channel_id=555666777
)
print(f"歡迎訊息已發送：{result.message_id}")'''
                    }
                ]
            },
            'ActivityService': {
                'track_activity': [
                    {
                        'language': 'python',
                        'description': '追蹤使用者活動',
                        'code': '''# 記錄使用者活動
activity = await activity_service.track_activity(
    guild_id=123456789,
    user_id=987654321,
    activity_type=ActivityType.MESSAGE,
    channel_id=555666777
)
print(f"活動記錄成功：{activity.id}")'''
                    }
                ]
            }
        }
        
        # 取得對應的範例
        if class_name in service_examples and method_name in service_examples[class_name]:
            examples = service_examples[class_name][method_name]
        else:
            # 生成通用範例
            param_names = [p['name'] for p in parameters if p['required']]
            if param_names:
                param_str = ',\n    '.join([f"{name}=..." for name in param_names[:3]])  # 最多顯示3個參數
                examples = [{
                    'language': 'python',
                    'description': f'使用 {method_name} 方法',
                    'code': f'''# 呼叫 {method_name} 方法
result = await service.{method_name}(
    {param_str}
)
print(f"操作成功：{{result}}")'''
                }]
        
        return examples
    
    async def _save_document(self, doc_id: str, content: str, file_path: Path, category: DocumentCategory) -> bool:
        """儲存文檔"""
        try:
            # 確保目錄存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 寫入檔案
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 計算內容雜湊
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # 獲取檔案大小
            file_size = file_path.stat().st_size
            
            # 保存文檔配置
            await self._save_document_config(doc_id, category, str(file_path))
            
            # 保存版本信息
            await self._save_document_version(
                doc_id=doc_id,
                content_hash=content_hash,
                file_path=str(file_path),
                size_bytes=file_size,
                author="DocumentationService"
            )
            
            self.logger.info(f"文檔 {doc_id} 儲存成功：{file_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"儲存文檔 {doc_id} 失敗：{e}")
            return False
    
    async def _save_document_config(self, doc_id: str, category: DocumentCategory, file_path: str):
        """儲存文檔配置"""
        config = DocumentConfig(
            id=doc_id,
            category=category,
            path=file_path,
            title=doc_id.replace('_', ' ').title(),
            status=DocumentStatus.PUBLISHED,
            auto_generate=True
        )
        
        # 檢查是否已存在
        existing = await self.db_manager.fetchone(
            "SELECT id FROM doc_config WHERE id = ?",
            (doc_id,)
        )
        
        if existing:
            # 更新
            await self.db_manager.execute(
                """UPDATE doc_config SET 
                   category = ?, path = ?, title = ?, status = ?, 
                   last_updated = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (category.value, file_path, config.title, config.status.value, doc_id)
            )
        else:
            # 插入
            await self.db_manager.execute(
                """INSERT INTO doc_config 
                   (id, category, path, title, status, auto_generate, 
                    dependencies, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (doc_id, category.value, file_path, config.title, 
                 config.status.value, config.auto_generate, 
                 json.dumps(config.dependencies), json.dumps(config.metadata))
            )
        
        # 更新快取
        self._document_configs[doc_id] = config
    
    async def _save_document_version(self, doc_id: str, content_hash: str, 
                                   file_path: str, size_bytes: int, author: str):
        """儲存文檔版本"""
        # 設定其他版本為非當前版本
        await self.db_manager.execute(
            "UPDATE doc_versions SET is_current = FALSE WHERE document_id = ?",
            (doc_id,)
        )
        
        # 插入新版本
        version_id = f"{doc_id}_v_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        version = datetime.now().strftime('%Y.%m.%d.%H%M%S')
        
        await self.db_manager.execute(
            """INSERT INTO doc_versions 
               (id, document_id, version, content_hash, file_path, 
                size_bytes, author, is_current, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, TRUE, CURRENT_TIMESTAMP)""",
            (version_id, doc_id, version, content_hash, file_path, 
             size_bytes, author)
        )
    
    async def validate_documents(self, document_ids: List[str] = None) -> List[DocumentValidationResult]:
        """
        驗證文檔品質
        
        參數：
            document_ids: 要驗證的文檔ID列表，None表示驗證所有文檔
            
        返回：
            驗證結果列表
        """
        try:
            if document_ids is None:
                await self._refresh_cache_if_needed()
                document_ids = list(self._document_configs.keys())
            
            results = []
            for doc_id in document_ids:
                result = await self._validate_single_document(doc_id)
                if result:
                    results.append(result)
            
            self.logger.info(f"完成 {len(results)} 個文檔的品質驗證")
            return results
            
        except Exception as e:
            self.logger.exception(f"文檔驗證失敗：{e}")
            raise ServiceError(
                f"文檔驗證失敗：{e}", 
                service_name=self.name,
                operation="validate_documents"
            )
    
    async def _validate_single_document(self, doc_id: str) -> Optional[DocumentValidationResult]:
        """驗證單個文檔"""
        try:
            config = self._document_configs.get(doc_id)
            if not config:
                return None
            
            # 檢查檔案是否存在
            if not Path(config.path).exists():
                return DocumentValidationResult(
                    document_id=doc_id,
                    is_valid=False,
                    completeness_score=0.0,
                    accuracy_score=0.0,
                    readability_score=0.0,
                    issues=[f"文檔檔案不存在：{config.path}"]
                )
            
            # 讀取文檔內容
            with open(config.path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 進行各項驗證
            completeness_score = await self._calculate_completeness_score(content, config)
            accuracy_score = await self._calculate_accuracy_score(content, config)
            readability_score = await self._calculate_readability_score(content)
            
            issues = []
            warnings = []
            suggestions = []
            
            # 檢查基本品質要求
            if len(content.strip()) < 100:
                issues.append("文檔內容過短")
            
            if completeness_score < 0.8:
                warnings.append("文檔完整度不足")
            
            if readability_score < 3.0:
                suggestions.append("建議改善文檔可讀性")
            
            is_valid = len(issues) == 0 and completeness_score >= 0.5
            
            return DocumentValidationResult(
                document_id=doc_id,
                is_valid=is_valid,
                completeness_score=completeness_score,
                accuracy_score=accuracy_score,
                readability_score=readability_score,
                issues=issues,
                warnings=warnings,
                suggestions=suggestions
            )
            
        except Exception as e:
            self.logger.exception(f"驗證文檔 {doc_id} 失敗：{e}")
            return DocumentValidationResult(
                document_id=doc_id,
                is_valid=False,
                completeness_score=0.0,
                accuracy_score=0.0,
                readability_score=0.0,
                issues=[f"驗證過程發生錯誤：{e}"]
            )
    
    async def _calculate_completeness_score(self, content: str, config: DocumentConfig) -> float:
        """計算文檔完整度分數"""
        score = 0.0
        total_checks = 0
        
        # 基本結構檢查（權重：20%）
        if content.strip():
            score += 0.2
        total_checks += 1
        
        # 標題檢查（權重：15%）
        if config.format == DocumentFormat.MARKDOWN:
            if re.search(r'^#\s+', content, re.MULTILINE):
                score += 0.15
        total_checks += 1
        
        # 內容長度檢查（權重：20%）
        content_length = len(content.strip())
        if content_length >= 1000:
            score += 0.2
        elif content_length >= 500:
            score += 0.15
        elif content_length >= 200:
            score += 0.1
        total_checks += 1
        
        # 範例程式碼檢查（權重：25%，對API文檔特別重要）
        if config.category in [DocumentCategory.API, DocumentCategory.DEVELOPER]:
            code_blocks = len(re.findall(r'```[\s\S]*?```', content))
            if code_blocks >= 5:
                score += 0.25
            elif code_blocks >= 3:
                score += 0.2
            elif code_blocks >= 1:
                score += 0.1
        total_checks += 1
        
        # 連結和參考檢查（權重：10%）
        if re.search(r'\[.*?\]\(.*?\)', content):
            score += 0.1
        total_checks += 1
        
        # 結構化內容檢查（權重：10%）
        if re.search(r'^[-*+]\s+', content, re.MULTILINE):  # 列表
            score += 0.05
        if re.search(r'^\|.*\|', content, re.MULTILINE):  # 表格
            score += 0.05
        total_checks += 1
        
        return min(score, 1.0)
    
    async def _calculate_accuracy_score(self, content: str, config: DocumentConfig) -> float:
        """計算文檔準確度分數"""
        score = 1.0  # 從滿分開始扣分
        
        # 檢查是否有明顯的錯誤標記
        error_indicators = ['TODO', 'FIXME', 'XXX', '待完成', '需要修改', '無額外說明', 'TBD']
        for indicator in error_indicators:
            occurrences = content.count(indicator)
            if occurrences > 0:
                score -= min(0.1 * occurrences, 0.3)  # 最多扣0.3分
        
        # 檢查是否有空的程式碼區塊
        empty_code_blocks = len(re.findall(r'```\s*```', content))
        if empty_code_blocks > 0:
            score -= min(0.2 * empty_code_blocks, 0.4)
        
        # 檢查是否有無效的內部連結（以#開頭但找不到對應標題）
        internal_links = re.findall(r'\[.*?\]\(#(.*?)\)', content)
        headers = re.findall(r'^#+\s+(.+)', content, re.MULTILINE)
        header_anchors = [h.lower().replace(' ', '') for h in headers]
        
        broken_links = 0
        for link in internal_links:
            if link.lower() not in header_anchors:
                broken_links += 1
        
        if broken_links > 0:
            score -= min(0.1 * broken_links, 0.2)
        
        # 檢查參數描述的完整性（針對API文檔）
        if config.category == DocumentCategory.API:
            # 查找參數列表中空描述的情況
            empty_param_descriptions = len(re.findall(r'- `\w+`[^:]*:\s*$', content, re.MULTILINE))
            if empty_param_descriptions > 0:
                score -= min(0.05 * empty_param_descriptions, 0.3)
        
        return max(score, 0.0)
    
    async def _calculate_readability_score(self, content: str) -> float:
        """計算文檔可讀性分數（1-5分）"""
        score = 3.0  # 基礎分數
        
        # 段落結構檢查
        paragraphs = content.split('\n\n')
        if len(paragraphs) >= 3:
            score += 0.5
        
        # 列表結構檢查
        if re.search(r'^[-*+]\s+', content, re.MULTILINE):
            score += 0.3
        
        # 標題層次檢查
        headers = re.findall(r'^#+\s+', content, re.MULTILINE)
        if len(headers) >= 2:
            score += 0.2
        
        return min(score, 5.0)
    
    async def validate_api_documentation_quality(self, content: str) -> Dict[str, Any]:
        """
        專門驗證API文檔品質
        
        返回：
            品質評估結果，包含分數、問題清單和改善建議
        """
        quality_result = {
            'overall_score': 0.0,
            'issues': [],
            'warnings': [], 
            'suggestions': [],
            'metrics': {}
        }
        
        # 檢查「無額外說明」問題
        no_description_count = content.count('無額外說明')
        quality_result['metrics']['no_description_count'] = no_description_count
        
        if no_description_count > 0:
            quality_result['issues'].append(f"發現 {no_description_count} 個「無額外說明」，需要提供有意義的描述")
        
        # 檢查範例程式碼
        code_blocks = len(re.findall(r'```[\s\S]*?```', content))
        total_methods = len(re.findall(r'#### `\w+\(\)`', content))
        
        quality_result['metrics']['code_blocks'] = code_blocks
        quality_result['metrics']['total_methods'] = total_methods
        quality_result['metrics']['methods_with_examples_ratio'] = code_blocks / total_methods if total_methods > 0 else 0
        
        if code_blocks == 0:
            quality_result['issues'].append("沒有任何使用範例，所有方法都應該提供實際的程式碼範例")
        elif code_blocks < total_methods * 0.5:
            quality_result['warnings'].append(f"只有 {(code_blocks/total_methods)*100:.1f}% 的方法有範例，建議提高到80%以上")
        
        # 檢查重複內容
        service_headers = re.findall(r'^## (\w+Service)', content, re.MULTILINE)
        duplicate_services = [service for service in set(service_headers) if service_headers.count(service) > 1]
        
        if duplicate_services:
            quality_result['issues'].append(f"發現重複的服務：{', '.join(duplicate_services)}")
        
        # 檢查參數格式一致性
        param_formats = re.findall(r'- `\w+` \(([^)]+)\)', content)
        inconsistent_formats = []
        
        for param_format in set(param_formats):
            if '<class ' in param_format and not param_format.startswith('<class '):
                inconsistent_formats.append(param_format)
        
        if inconsistent_formats:
            quality_result['warnings'].append(f"參數類型格式不一致：{inconsistent_formats[:3]}")
        
        # 檢查方法描述品質
        method_descriptions = re.findall(r'#### `(\w+)\(\)`\n\n([^\n]+)', content)
        short_descriptions = [method for method, desc in method_descriptions if len(desc.strip()) < 10]
        
        if short_descriptions:
            quality_result['suggestions'].append(f"以下方法的描述過於簡短，建議擴充：{short_descriptions[:5]}")
        
        # 計算總體品質分數
        score = 5.0  # 滿分
        
        # 根據問題數量扣分
        score -= len(quality_result['issues']) * 1.0
        score -= len(quality_result['warnings']) * 0.5
        score -= len(quality_result['suggestions']) * 0.2
        
        # 根據範例覆蓋率加分/扣分
        example_ratio = quality_result['metrics']['methods_with_examples_ratio']
        if example_ratio >= 0.8:
            score += 1.0
        elif example_ratio >= 0.5:
            score += 0.5
        else:
            score -= 1.0
        
        quality_result['overall_score'] = max(score, 0.0)
        
        return quality_result
    
    async def _refresh_cache_if_needed(self):
        """必要時重新整理快取"""
        if (self._last_cache_update is None or 
            datetime.now() - self._last_cache_update > self._cache_ttl):
            await self._load_document_configs()
    
    async def get_documentation_metrics(self) -> DocumentationMetrics:
        """獲取文檔系統指標"""
        try:
            await self._refresh_cache_if_needed()
            
            # 統計各類別文檔數量
            documents_by_category = {}
            documents_by_status = {}
            total_size = 0
            
            for config in self._document_configs.values():
                # 按類別統計
                category_key = config.category.value
                documents_by_category[category_key] = documents_by_category.get(category_key, 0) + 1
                
                # 按狀態統計
                status_key = config.status.value
                documents_by_status[status_key] = documents_by_status.get(status_key, 0) + 1
                
                # 計算檔案大小
                if Path(config.path).exists():
                    total_size += Path(config.path).stat().st_size
            
            # 驗證所有文檔以獲取品質指標
            validation_results = await self.validate_documents()
            
            avg_completeness = sum(r.completeness_score for r in validation_results) / len(validation_results) if validation_results else 0.0
            avg_accuracy = sum(r.accuracy_score for r in validation_results) / len(validation_results) if validation_results else 0.0
            avg_readability = sum(r.readability_score for r in validation_results) / len(validation_results) if validation_results else 0.0
            
            # 統計過期文檔
            outdated_count = sum(1 for config in self._document_configs.values() 
                               if config.status == DocumentStatus.OUTDATED)
            
            return DocumentationMetrics(
                total_documents=len(self._document_configs),
                documents_by_category=documents_by_category,
                documents_by_status=documents_by_status,
                total_size_bytes=total_size,
                average_completeness=avg_completeness,
                average_accuracy=avg_accuracy,
                average_readability=avg_readability,
                outdated_documents=outdated_count
            )
            
        except Exception as e:
            self.logger.exception(f"獲取文檔指標失敗：{e}")
            raise ServiceError(
                f"獲取文檔指標失敗：{e}", 
                service_name=self.name,
                operation="get_documentation_metrics"
            )
    
    # === 新增：連結檢查功能 ===
    
    async def _initialize_link_checker(self):
        """初始化連結檢查服務"""
        try:
            # 創建連結檢查服務
            project_root = str(Path.cwd())
            self._link_checker_service = LinkCheckerService(project_root)
            await self._link_checker_service.initialize()
            
            # 創建API服務
            self._link_check_api = LinkCheckAPI(project_root)
            await self._link_check_api.initialize()
            
            self.logger.info("連結檢查服務已初始化")
            
        except Exception as e:
            self.logger.error(f"初始化連結檢查服務失敗: {e}")
            # 不阻斷主服務初始化
    
    async def check_documentation_links(
        self,
        target_paths: Optional[List[str]] = None,
        check_external: bool = False,
        check_anchors: bool = True
    ) -> Dict[str, Any]:
        """
        檢查文檔連結有效性
        
        參數:
            target_paths: 目標路徑列表，預設檢查docs目錄
            check_external: 是否檢查外部連結
            check_anchors: 是否檢查錨點連結
            
        返回:
            檢查結果字典
        """
        if not self._link_check_api:
            raise ServiceError(
                "連結檢查服務未初始化",
                service_name=self.name,
                operation="check_documentation_links"
            )
        
        try:
            if target_paths is None:
                target_paths = [str(self.docs_root_path)]
            
            result = await self._link_check_api.check_links(
                target_paths=target_paths,
                check_external=check_external,
                check_anchors=check_anchors,
                output_format="json"
            )
            
            self.logger.info(f"文檔連結檢查完成: {result}")
            return result
            
        except Exception as e:
            self.logger.exception(f"檢查文檔連結失敗: {e}")
            raise ServiceError(
                f"檢查文檔連結失敗: {e}",
                service_name=self.name,
                operation="check_documentation_links"
            )
    
    async def schedule_periodic_link_check(
        self,
        interval_hours: int = 24,
        name: str = "documentation_check"
    ) -> str:
        """
        排程定期連結檢查
        
        參數:
            interval_hours: 檢查間隔（小時）
            name: 排程名稱
            
        返回:
            排程ID
        """
        if not self._link_checker_service:
            raise ServiceError(
                "連結檢查服務未初始化",
                service_name=self.name,
                operation="schedule_periodic_link_check"
            )
        
        try:
            schedule_id = self._link_checker_service.schedule_periodic_check(
                interval_hours=interval_hours,
                name=name,
                target_directories=[str(self.docs_root_path)]
            )
            
            self.logger.info(f"已創建定期連結檢查排程: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            self.logger.exception(f"創建定期連結檢查失敗: {e}")
            raise ServiceError(
                f"創建定期連結檢查失敗: {e}",
                service_name=self.name,
                operation="schedule_periodic_link_check"
            )
    
    async def get_link_check_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        獲取連結檢查歷史
        
        參數:
            limit: 返回記錄數量限制
            
        返回:
            檢查歷史列表
        """
        if not self._link_check_api:
            raise ServiceError(
                "連結檢查服務未初始化", 
                service_name=self.name,
                operation="get_link_check_history"
            )
        
        try:
            result = await self._link_check_api.list_check_history(limit=limit)
            
            if result["success"]:
                return result["data"]["history"]
            else:
                self.logger.error(f"獲取連結檢查歷史失敗: {result}")
                return []
                
        except Exception as e:
            self.logger.exception(f"獲取連結檢查歷史失敗: {e}")
            raise ServiceError(
                f"獲取連結檢查歷史失敗: {e}",
                service_name=self.name,
                operation="get_link_check_history"
            )
    
    async def export_link_check_report(
        self,
        check_id: str,
        format: str = "markdown"
    ) -> str:
        """
        匯出連結檢查報告
        
        參數:
            check_id: 檢查ID
            format: 報告格式
            
        返回:
            報告檔案路徑
        """
        if not self._link_check_api:
            raise ServiceError(
                "連結檢查服務未初始化",
                service_name=self.name,
                operation="export_link_check_report"
            )
        
        try:
            result = await self._link_check_api.export_report(check_id, format)
            
            if result["success"]:
                return result["data"]["report_path"]
            else:
                raise ServiceError(
                    f"匯出報告失敗: {result['error']}",
                    service_name=self.name,
                    operation="export_link_check_report"
                )
                
        except Exception as e:
            self.logger.exception(f"匯出連結檢查報告失敗: {e}")
            raise ServiceError(
                f"匯出連結檢查報告失敗: {e}",
                service_name=self.name,
                operation="export_link_check_report"
            )
    
    @property
    def link_checker_service(self) -> Optional[LinkCheckerService]:
        """獲取連結檢查服務實例（供外部使用）"""
        return self._link_checker_service
    
    @property  
    def link_check_api(self) -> Optional[LinkCheckAPI]:
        """獲取連結檢查API實例（供外部使用）"""
        return self._link_check_api