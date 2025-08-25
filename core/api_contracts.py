#!/usr/bin/env python3
"""
API契約定義模組 - 定義服務間的API介面和資料契約
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組定義了Discord Bot、Redis、監控系統等服務間的API契約，
確保服務間的介面一致性和資料流的標準化。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Protocol
import json


class APIVersion(Enum):
    """API版本"""
    V1 = "v1"
    V2 = "v2"


class DataFormat(Enum):
    """資料格式"""
    JSON = "application/json"
    TEXT = "text/plain" 
    BINARY = "application/octet-stream"


class ResponseStatus(Enum):
    """回應狀態"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


@dataclass
class APIEndpoint:
    """API端點定義"""
    path: str
    method: str  # GET, POST, PUT, DELETE
    description: str
    request_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    authentication_required: bool = False
    timeout_seconds: int = 30
    retry_policy: Optional[Dict[str, Any]] = None


@dataclass
class APIResponse:
    """標準API回應格式"""
    status: ResponseStatus
    message: str
    data: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResponse:
    """健康檢查回應"""
    service_name: str
    status: str  # healthy, unhealthy, degraded
    version: str
    uptime_seconds: float
    checks: Dict[str, bool]
    dependencies: Dict[str, str]
    timestamp: datetime = field(default_factory=datetime.now)


class ServiceAPIContract(ABC):
    """服務API契約基底類別"""
    
    def __init__(self, service_name: str, version: APIVersion):
        self.service_name = service_name
        self.version = version
        self.endpoints: Dict[str, APIEndpoint] = {}
        self._define_endpoints()
    
    @abstractmethod
    def _define_endpoints(self) -> None:
        """定義API端點"""
        pass
    
    def get_endpoint(self, name: str) -> Optional[APIEndpoint]:
        """獲取API端點"""
        return self.endpoints.get(name)
    
    def list_endpoints(self) -> List[str]:
        """列出所有端點"""
        return list(self.endpoints.keys())
    
    def validate_request(self, endpoint_name: str, data: Any) -> tuple[bool, List[str]]:
        """驗證請求資料"""
        endpoint = self.get_endpoint(endpoint_name)
        if not endpoint:
            return False, [f"端點 {endpoint_name} 不存在"]
        
        # 簡化的驗證邏輯
        if endpoint.request_schema and not data:
            return False, ["請求資料不能為空"]
        
        return True, []
    
    def format_response(self, status: ResponseStatus, message: str, 
                       data: Any = None, errors: List[str] = None) -> APIResponse:
        """格式化回應"""
        return APIResponse(
            status=status,
            message=message,
            data=data,
            errors=errors or [],
            metadata={
                'service': self.service_name,
                'version': self.version.value
            }
        )


class DiscordBotAPIContract(ServiceAPIContract):
    """Discord Bot API契約"""
    
    def __init__(self):
        super().__init__("discord-bot", APIVersion.V1)
    
    def _define_endpoints(self) -> None:
        """定義Discord Bot API端點"""
        
        # 健康檢查端點
        self.endpoints['health'] = APIEndpoint(
            path="/health",
            method="GET",
            description="健康檢查端點",
            response_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["healthy", "unhealthy", "degraded"]},
                    "uptime": {"type": "number"},
                    "version": {"type": "string"},
                    "discord_connection": {"type": "boolean"},
                    "redis_connection": {"type": "boolean"}
                }
            }
        )
        
        # 機器人狀態端點
        self.endpoints['status'] = APIEndpoint(
            path="/api/v1/bot/status",
            method="GET", 
            description="獲取機器人狀態資訊",
            response_schema={
                "type": "object",
                "properties": {
                    "is_ready": {"type": "boolean"},
                    "latency": {"type": "number"},
                    "guild_count": {"type": "integer"},
                    "user_count": {"type": "integer"},
                    "uptime": {"type": "number"}
                }
            }
        )
        
        # 指標端點（供Prometheus抓取）
        self.endpoints['metrics'] = APIEndpoint(
            path="/metrics",
            method="GET",
            description="Prometheus指標端點",
            response_schema={"type": "string", "format": "prometheus-metrics"}
        )
        
        # 重啟端點
        self.endpoints['restart'] = APIEndpoint(
            path="/api/v1/admin/restart",
            method="POST",
            description="重啟機器人服務",
            authentication_required=True,
            request_schema={
                "type": "object",
                "properties": {
                    "graceful": {"type": "boolean", "default": True},
                    "reason": {"type": "string"}
                }
            }
        )


class RedisAPIContract(ServiceAPIContract):
    """Redis API契約"""
    
    def __init__(self):
        super().__init__("redis", APIVersion.V1)
    
    def _define_endpoints(self) -> None:
        """定義Redis API操作"""
        
        # Redis PING命令
        self.endpoints['ping'] = APIEndpoint(
            path="PING",
            method="REDIS_CMD",
            description="Redis PING命令",
            response_schema={"type": "string", "enum": ["PONG"]}
        )
        
        # 獲取鍵值
        self.endpoints['get'] = APIEndpoint(
            path="GET",
            method="REDIS_CMD",
            description="獲取鍵值",
            request_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string"}
                },
                "required": ["key"]
            }
        )
        
        # 設置鍵值
        self.endpoints['set'] = APIEndpoint(
            path="SET",
            method="REDIS_CMD", 
            description="設置鍵值",
            request_schema={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "ttl": {"type": "integer", "minimum": 1}
                },
                "required": ["key", "value"]
            }
        )
        
        # 獲取資料庫資訊
        self.endpoints['info'] = APIEndpoint(
            path="INFO",
            method="REDIS_CMD",
            description="獲取Redis資訊"
        )


class MonitoringAPIContract(ServiceAPIContract):
    """監控系統API契約"""
    
    def __init__(self, service_name: str):
        super().__init__(service_name, APIVersion.V1)
        self.service_type = service_name  # prometheus, grafana
    
    def _define_endpoints(self) -> None:
        """定義監控API端點"""
        
        if self.service_type == "prometheus":
            self._define_prometheus_endpoints()
        elif self.service_type == "grafana":
            self._define_grafana_endpoints()
    
    def _define_prometheus_endpoints(self) -> None:
        """定義Prometheus端點"""
        
        # 健康檢查
        self.endpoints['health'] = APIEndpoint(
            path="/-/healthy",
            method="GET",
            description="Prometheus健康檢查"
        )
        
        # 準備狀態檢查
        self.endpoints['ready'] = APIEndpoint(
            path="/-/ready", 
            method="GET",
            description="Prometheus準備狀態檢查"
        )
        
        # 查詢API
        self.endpoints['query'] = APIEndpoint(
            path="/api/v1/query",
            method="GET",
            description="PromQL查詢",
            request_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "time": {"type": "string", "format": "rfc3339"},
                    "timeout": {"type": "string"}
                },
                "required": ["query"]
            }
        )
        
        # 範圍查詢API
        self.endpoints['query_range'] = APIEndpoint(
            path="/api/v1/query_range",
            method="GET", 
            description="PromQL範圍查詢",
            request_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "start": {"type": "string", "format": "rfc3339"},
                    "end": {"type": "string", "format": "rfc3339"},
                    "step": {"type": "string"}
                },
                "required": ["query", "start", "end", "step"]
            }
        )
    
    def _define_grafana_endpoints(self) -> None:
        """定義Grafana端點"""
        
        # 健康檢查
        self.endpoints['health'] = APIEndpoint(
            path="/api/health",
            method="GET",
            description="Grafana健康檢查"
        )
        
        # 資料源測試
        self.endpoints['test_datasource'] = APIEndpoint(
            path="/api/datasources/proxy/{id}/api/v1/query",
            method="POST",
            description="測試資料源連接"
        )
        
        # 儀表板API
        self.endpoints['dashboards'] = APIEndpoint(
            path="/api/search",
            method="GET",
            description="搜索儀表板"
        )


class DataFlowContract:
    """資料流契約"""
    
    def __init__(self):
        self.flows: Dict[str, Dict[str, Any]] = {}
        self._define_data_flows()
    
    def _define_data_flows(self) -> None:
        """定義資料流"""
        
        # Discord Bot -> Redis 資料流
        self.flows['bot_to_redis'] = {
            'source': 'discord-bot',
            'destination': 'redis',
            'data_types': [
                'user_session',
                'command_cache', 
                'rate_limit_state',
                'guild_configuration'
            ],
            'flow_direction': 'bidirectional',
            'serialization': 'json',
            'compression': False,
            'encryption': False
        }
        
        # Discord Bot -> Prometheus 資料流
        self.flows['bot_to_prometheus'] = {
            'source': 'discord-bot',
            'destination': 'prometheus',
            'data_types': [
                'command_metrics',
                'response_time_metrics',
                'error_count_metrics',
                'user_activity_metrics'
            ],
            'flow_direction': 'unidirectional',
            'protocol': 'http_pull',
            'format': 'prometheus_exposition'
        }
        
        # Prometheus -> Grafana 資料流
        self.flows['prometheus_to_grafana'] = {
            'source': 'prometheus',
            'destination': 'grafana',
            'data_types': [
                'time_series_metrics',
                'alert_rules',
                'recording_rules'
            ],
            'flow_direction': 'unidirectional', 
            'protocol': 'http_promql',
            'query_language': 'promql'
        }


class IntegrationContractValidator:
    """整合契約驗證器"""
    
    def __init__(self):
        self.discord_contract = DiscordBotAPIContract()
        self.redis_contract = RedisAPIContract()
        self.prometheus_contract = MonitoringAPIContract("prometheus")
        self.grafana_contract = MonitoringAPIContract("grafana")
        self.data_flow_contract = DataFlowContract()
    
    def validate_all_contracts(self) -> Dict[str, Dict[str, Any]]:
        """驗證所有契約"""
        results = {}
        
        # 驗證各服務契約
        results['discord-bot'] = self._validate_service_contract(self.discord_contract)
        results['redis'] = self._validate_service_contract(self.redis_contract)
        results['prometheus'] = self._validate_service_contract(self.prometheus_contract)
        results['grafana'] = self._validate_service_contract(self.grafana_contract)
        
        # 驗證資料流契約
        results['data_flows'] = self._validate_data_flows()
        
        # 驗證服務間相容性
        results['compatibility'] = self._validate_cross_service_compatibility()
        
        return results
    
    def _validate_service_contract(self, contract: ServiceAPIContract) -> Dict[str, Any]:
        """驗證服務契約"""
        validation_result = {
            'service': contract.service_name,
            'version': contract.version.value,
            'endpoint_count': len(contract.endpoints),
            'endpoints_valid': True,
            'issues': []
        }
        
        # 檢查必要端點
        required_endpoints = ['health']
        for endpoint_name in required_endpoints:
            if endpoint_name not in contract.endpoints:
                validation_result['endpoints_valid'] = False
                validation_result['issues'].append(f"缺少必要端點: {endpoint_name}")
        
        # 檢查端點定義完整性
        for name, endpoint in contract.endpoints.items():
            if not endpoint.path:
                validation_result['endpoints_valid'] = False
                validation_result['issues'].append(f"端點 {name} 缺少路徑定義")
            
            if not endpoint.description:
                validation_result['issues'].append(f"端點 {name} 缺少描述")
        
        return validation_result
    
    def _validate_data_flows(self) -> Dict[str, Any]:
        """驗證資料流"""
        validation_result = {
            'flow_count': len(self.data_flow_contract.flows),
            'flows_valid': True,
            'issues': []
        }
        
        for flow_name, flow_config in self.data_flow_contract.flows.items():
            # 檢查必要欄位
            required_fields = ['source', 'destination', 'data_types', 'flow_direction']
            for field in required_fields:
                if field not in flow_config:
                    validation_result['flows_valid'] = False
                    validation_result['issues'].append(f"資料流 {flow_name} 缺少 {field} 定義")
            
            # 檢查服務存在性
            source = flow_config.get('source')
            destination = flow_config.get('destination')
            
            valid_services = ['discord-bot', 'redis', 'prometheus', 'grafana']
            if source not in valid_services:
                validation_result['issues'].append(f"資料流 {flow_name} 的來源服務 {source} 不存在")
            
            if destination not in valid_services:
                validation_result['issues'].append(f"資料流 {flow_name} 的目標服務 {destination} 不存在")
        
        return validation_result
    
    def _validate_cross_service_compatibility(self) -> Dict[str, Any]:
        """驗證服務間相容性"""
        compatibility_result = {
            'compatible': True,
            'checks': {},
            'issues': []
        }
        
        # 檢查Discord Bot和Redis的相容性
        compatibility_result['checks']['discord_bot_redis'] = self._check_discord_redis_compatibility()
        
        # 檢查Discord Bot和Prometheus的相容性  
        compatibility_result['checks']['discord_bot_prometheus'] = self._check_discord_prometheus_compatibility()
        
        # 檢查Prometheus和Grafana的相容性
        compatibility_result['checks']['prometheus_grafana'] = self._check_prometheus_grafana_compatibility()
        
        # 統計結果
        failed_checks = [name for name, result in compatibility_result['checks'].items() if not result['compatible']]
        if failed_checks:
            compatibility_result['compatible'] = False
            compatibility_result['issues'] = [f"相容性檢查失敗: {', '.join(failed_checks)}"]
        
        return compatibility_result
    
    def _check_discord_redis_compatibility(self) -> Dict[str, Any]:
        """檢查Discord Bot和Redis相容性"""
        return {
            'compatible': True,
            'protocol_match': 'redis_protocol',
            'data_format_match': 'key_value',
            'issues': []
        }
    
    def _check_discord_prometheus_compatibility(self) -> Dict[str, Any]:
        """檢查Discord Bot和Prometheus相容性"""
        # 檢查Discord Bot是否提供metrics端點
        metrics_endpoint = self.discord_contract.get_endpoint('metrics')
        
        return {
            'compatible': metrics_endpoint is not None,
            'metrics_endpoint_available': metrics_endpoint is not None,
            'protocol_match': 'http',
            'format_match': 'prometheus_exposition',
            'issues': [] if metrics_endpoint else ['Discord Bot缺少metrics端點']
        }
    
    def _check_prometheus_grafana_compatibility(self) -> Dict[str, Any]:
        """檢查Prometheus和Grafana相容性"""
        # 檢查Prometheus查詢API是否可用
        query_endpoint = self.prometheus_contract.get_endpoint('query')
        
        return {
            'compatible': query_endpoint is not None,
            'query_api_available': query_endpoint is not None,
            'protocol_match': 'http',
            'query_language': 'promql',
            'issues': [] if query_endpoint else ['Prometheus缺少查詢API']
        }


# 工具函數
def create_standard_health_response(service_name: str, status: str, **kwargs) -> HealthCheckResponse:
    """創建標準健康檢查回應"""
    return HealthCheckResponse(
        service_name=service_name,
        status=status,
        version=kwargs.get('version', '1.0.0'),
        uptime_seconds=kwargs.get('uptime_seconds', 0.0),
        checks=kwargs.get('checks', {}),
        dependencies=kwargs.get('dependencies', {})
    )


def validate_api_response(response: APIResponse) -> tuple[bool, List[str]]:
    """驗證API回應格式"""
    issues = []
    
    if not isinstance(response.status, ResponseStatus):
        issues.append("回應狀態必須是ResponseStatus枚舉值")
    
    if not response.message:
        issues.append("回應訊息不能為空")
    
    if response.status == ResponseStatus.ERROR and not response.errors:
        issues.append("錯誤狀態必須包含錯誤詳情")
    
    return len(issues) == 0, issues


# 使用範例
if __name__ == '__main__':
    # 創建契約驗證器
    validator = IntegrationContractValidator()
    
    # 驗證所有契約
    results = validator.validate_all_contracts()
    
    # 輸出驗證結果
    print("=== API契約驗證結果 ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    # 示例：創建標準健康檢查回應
    health_response = create_standard_health_response(
        service_name="discord-bot",
        status="healthy",
        version="2.4.3",
        uptime_seconds=3600.0,
        checks={
            'database': True,
            'redis': True,
            'discord_api': True
        },
        dependencies={
            'redis': 'healthy',
            'postgres': 'healthy'
        }
    )
    
    print(f"\n=== 健康檢查回應範例 ===")
    print(json.dumps(health_response.__dict__, indent=2, ensure_ascii=False, default=str))