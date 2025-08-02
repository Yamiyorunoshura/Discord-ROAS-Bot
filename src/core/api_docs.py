"""API 文件生成系統.

此模組提供完整的 API 文件生成功能，包含：
- OpenAPI 3.0 規範生成
- 自動化文件註解提取
- 互動式 Swagger UI 支援
- 成就系統 API 端點文檔
- 文件驗證和一致性檢查

遵循 OpenAPI 3.0 標準，確保文件與實際 API 實作保持同步。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OpenAPIGenerator:
    """OpenAPI 3.0 文件生成器.
    
    提供成就系統 API 的完整文件生成功能。
    """

    def __init__(self, title: str = "Discord ROAS Bot API", version: str = "2.0.0"):
        """初始化 OpenAPI 生成器.
        
        Args:
            title: API 標題
            version: API 版本
        """
        self.title = title
        self.version = version

        # 基礎 OpenAPI 規範結構
        self.spec = {
            "openapi": "3.0.3",
            "info": {
                "title": title,
                "version": version,
                "description": "Discord ROAS Bot API 文档 - 成就系統核心 API",
                "contact": {
                    "name": "ADR Bot Team",
                    "email": "admin@adrbot.dev",
                    "url": "https://github.com/adr-bot/discord-adr-bot"
                },
                "license": {
                    "name": "MIT",
                    "url": "https://github.com/adr-bot/discord-adr-bot/blob/main/LICENSE"
                }
            },
            "servers": [
                {
                    "url": "http://localhost:8080/api/v1",
                    "description": "開發環境"
                },
                {
                    "url": "https://api.adrbot.dev/v1",
                    "description": "生產環境"
                }
            ],
            "paths": {},
            "components": {
                "schemas": {},
                "responses": {},
                "parameters": {},
                "examples": {},
                "requestBodies": {},
                "headers": {},
                "securitySchemes": {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key"
                    },
                    "BearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT"
                    }
                }
            },
            "security": [
                {"ApiKeyAuth": []},
                {"BearerAuth": []}
            ],
            "tags": [
                {
                    "name": "achievements",
                    "description": "成就管理相關操作"
                },
                {
                    "name": "categories",
                    "description": "成就分類管理"
                },
                {
                    "name": "user-achievements",
                    "description": "用戶成就操作"
                },
                {
                    "name": "progress",
                    "description": "成就進度追蹤"
                },
                {
                    "name": "statistics",
                    "description": "統計和報表"
                },
                {
                    "name": "leaderboard",
                    "description": "排行榜功能"
                }
            ]
        }

        logger.info(f"OpenAPI 生成器初始化完成: {title} v{version}")

    def add_achievement_schemas(self) -> None:
        """添加成就系統相關的 Schema 定義."""

        # 成就類型枚舉
        self.spec["components"]["schemas"]["AchievementType"] = {
            "type": "string",
            "enum": ["COUNT", "THRESHOLD", "ACCUMULATION", "STREAK", "TIME_BASED"],
            "description": "成就類型",
            "example": "COUNT"
        }

        # 成就分類 Schema
        self.spec["components"]["schemas"]["AchievementCategory"] = {
            "type": "object",
            "required": ["name", "description"],
            "properties": {
                "id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "分類 ID",
                    "example": 1
                },
                "name": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "分類名稱",
                    "example": "活躍度成就"
                },
                "description": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "分類描述",
                    "example": "與用戶活躍度相關的成就"
                },
                "display_order": {
                    "type": "integer",
                    "description": "顯示順序",
                    "default": 0,
                    "example": 1
                },
                "icon_emoji": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "分類圖示表情符號",
                    "example": "🏆"
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "創建時間",
                    "readOnly": True
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "更新時間",
                    "readOnly": True
                }
            },
            "example": {
                "id": 1,
                "name": "活躍度成就",
                "description": "與用戶活躍度相關的成就",
                "display_order": 1,
                "icon_emoji": "🏆",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }

        # 成就 Schema
        self.spec["components"]["schemas"]["Achievement"] = {
            "type": "object",
            "required": ["name", "description", "category_id", "type", "criteria", "points"],
            "properties": {
                "id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "成就 ID",
                    "readOnly": True,
                    "example": 1
                },
                "name": {
                    "type": "string",
                    "maxLength": 100,
                    "description": "成就名稱",
                    "example": "活躍會員"
                },
                "description": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "成就描述",
                    "example": "連續30天在伺服器中發言"
                },
                "category_id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "所屬分類 ID",
                    "example": 1
                },
                "type": {
                    "$ref": "#/components/schemas/AchievementType"
                },
                "criteria": {
                    "type": "object",
                    "description": "成就達成條件",
                    "properties": {
                        "target_value": {
                            "type": "number",
                            "description": "目標數值",
                            "example": 30
                        }
                    },
                    "example": {
                        "target_value": 30,
                        "event_type": "message_sent",
                        "consecutive_days": True
                    }
                },
                "points": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "成就點數",
                    "example": 100
                },
                "badge_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "成就徽章圖片 URL",
                    "example": "https://example.com/badge.png"
                },
                "is_active": {
                    "type": "boolean",
                    "description": "是否啟用",
                    "default": True,
                    "example": True
                },
                "created_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "創建時間",
                    "readOnly": True
                },
                "updated_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "更新時間",
                    "readOnly": True
                }
            }
        }

        # 用戶成就 Schema
        self.spec["components"]["schemas"]["UserAchievement"] = {
            "type": "object",
            "required": ["user_id", "achievement_id"],
            "properties": {
                "id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "記錄 ID",
                    "readOnly": True,
                    "example": 1
                },
                "user_id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "用戶 Discord ID",
                    "example": 123456789012345678
                },
                "achievement_id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "成就 ID",
                    "example": 1
                },
                "earned_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "獲得時間",
                    "example": "2024-01-01T00:00:00Z"
                },
                "notified": {
                    "type": "boolean",
                    "description": "是否已通知",
                    "default": False,
                    "example": True
                }
            }
        }

        # 成就進度 Schema
        self.spec["components"]["schemas"]["AchievementProgress"] = {
            "type": "object",
            "required": ["user_id", "achievement_id", "current_value", "target_value"],
            "properties": {
                "id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "進度 ID",
                    "readOnly": True,
                    "example": 1
                },
                "user_id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "用戶 Discord ID",
                    "example": 123456789012345678
                },
                "achievement_id": {
                    "type": "integer",
                    "format": "int64",
                    "description": "成就 ID",
                    "example": 1
                },
                "current_value": {
                    "type": "number",
                    "description": "當前進度值",
                    "minimum": 0,
                    "example": 15.5
                },
                "target_value": {
                    "type": "number",
                    "description": "目標值",
                    "minimum": 0,
                    "example": 30
                },
                "progress_data": {
                    "type": "object",
                    "description": "額外進度資料",
                    "example": {
                        "daily_counts": [1, 2, 1, 3, 0, 2, 1],
                        "streak_count": 5
                    }
                },
                "last_updated": {
                    "type": "string",
                    "format": "date-time",
                    "description": "最後更新時間",
                    "example": "2024-01-01T12:00:00Z"
                }
            }
        }

        # 錯誤回應 Schema
        self.spec["components"]["schemas"]["Error"] = {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {
                    "type": "integer",
                    "description": "錯誤代碼",
                    "example": 400
                },
                "message": {
                    "type": "string",
                    "description": "錯誤訊息",
                    "example": "請求參數無效"
                },
                "details": {
                    "type": "object",
                    "description": "詳細錯誤資訊",
                    "example": {
                        "field": "name",
                        "issue": "不能為空"
                    }
                }
            }
        }

        # 分頁回應 Schema
        self.spec["components"]["schemas"]["PaginationMeta"] = {
            "type": "object",
            "properties": {
                "total": {
                    "type": "integer",
                    "description": "總記錄數",
                    "example": 100
                },
                "page": {
                    "type": "integer",
                    "description": "當前頁碼",
                    "example": 1
                },
                "per_page": {
                    "type": "integer",
                    "description": "每頁記錄數",
                    "example": 20
                },
                "pages": {
                    "type": "integer",
                    "description": "總頁數",
                    "example": 5
                }
            }
        }

        logger.info("成就系統 Schema 定義已添加")

    def add_achievement_paths(self) -> None:
        """添加成就系統相關的 API 路徑定義."""

        # 成就分類 API
        self.spec["paths"]["/categories"] = {
            "get": {
                "tags": ["categories"],
                "summary": "取得成就分類列表",
                "description": "取得所有成就分類，支援篩選和排序",
                "parameters": [
                    {
                        "name": "active_only",
                        "in": "query",
                        "description": "是否只取得啟用的分類",
                        "required": False,
                        "schema": {
                            "type": "boolean",
                            "default": True
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "成功取得分類列表",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/components/schemas/AchievementCategory"
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "伺服器內部錯誤",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error"
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "tags": ["categories"],
                "summary": "建立新的成就分類",
                "description": "建立一個新的成就分類",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/AchievementCategory"
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "成功建立分類",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/AchievementCategory"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "請求資料無效",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error"
                                }
                            }
                        }
                    }
                }
            }
        }

        # 單一分類操作 API
        self.spec["paths"]["/categories/{category_id}"] = {
            "get": {
                "tags": ["categories"],
                "summary": "取得特定成就分類",
                "description": "根據 ID 取得特定成就分類的詳細資訊",
                "parameters": [
                    {
                        "name": "category_id",
                        "in": "path",
                        "required": True,
                        "description": "分類 ID",
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "成功取得分類",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/AchievementCategory"
                                }
                            }
                        }
                    },
                    "404": {
                        "description": "分類不存在",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error"
                                }
                            }
                        }
                    }
                }
            },
            "put": {
                "tags": ["categories"],
                "summary": "更新成就分類",
                "description": "更新特定成就分類的資訊",
                "parameters": [
                    {
                        "name": "category_id",
                        "in": "path",
                        "required": True,
                        "description": "分類 ID",
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/AchievementCategory"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "成功更新分類",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/AchievementCategory"
                                }
                            }
                        }
                    },
                    "404": {
                        "description": "分類不存在"
                    }
                }
            },
            "delete": {
                "tags": ["categories"],
                "summary": "刪除成就分類",
                "description": "刪除特定的成就分類（需要確保分類下沒有成就）",
                "parameters": [
                    {
                        "name": "category_id",
                        "in": "path",
                        "required": True,
                        "description": "分類 ID",
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    }
                ],
                "responses": {
                    "204": {
                        "description": "成功刪除分類"
                    },
                    "400": {
                        "description": "分類下還有成就，無法刪除"
                    },
                    "404": {
                        "description": "分類不存在"
                    }
                }
            }
        }

        # 成就 API
        self.spec["paths"]["/achievements"] = {
            "get": {
                "tags": ["achievements"],
                "summary": "取得成就列表",
                "description": "取得成就列表，支援多種篩選和分頁",
                "parameters": [
                    {
                        "name": "category_id",
                        "in": "query",
                        "description": "篩選特定分類",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    },
                    {
                        "name": "type",
                        "in": "query",
                        "description": "篩選特定類型",
                        "required": False,
                        "schema": {
                            "$ref": "#/components/schemas/AchievementType"
                        }
                    },
                    {
                        "name": "active_only",
                        "in": "query",
                        "description": "是否只取得啟用的成就",
                        "required": False,
                        "schema": {
                            "type": "boolean",
                            "default": True
                        }
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "description": "最大返回數量",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20
                        }
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "description": "跳過的記錄數",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "minimum": 0,
                            "default": 0
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "成功取得成就列表",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "$ref": "#/components/schemas/Achievement"
                                            }
                                        },
                                        "meta": {
                                            "$ref": "#/components/schemas/PaginationMeta"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "tags": ["achievements"],
                "summary": "建立新成就",
                "description": "建立一個新的成就",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/Achievement"
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "成功建立成就",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Achievement"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "請求資料無效"
                    }
                }
            }
        }

        # 用戶成就 API
        self.spec["paths"]["/users/{user_id}/achievements"] = {
            "get": {
                "tags": ["user-achievements"],
                "summary": "取得用戶成就列表",
                "description": "取得特定用戶的所有成就",
                "parameters": [
                    {
                        "name": "user_id",
                        "in": "path",
                        "required": True,
                        "description": "用戶 Discord ID",
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    },
                    {
                        "name": "category_id",
                        "in": "query",
                        "description": "篩選特定分類",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "成功取得用戶成就列表",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "user_achievement": {
                                                "$ref": "#/components/schemas/UserAchievement"
                                            },
                                            "achievement": {
                                                "$ref": "#/components/schemas/Achievement"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "tags": ["user-achievements"],
                "summary": "頒發成就給用戶",
                "description": "為特定用戶頒發成就",
                "parameters": [
                    {
                        "name": "user_id",
                        "in": "path",
                        "required": True,
                        "description": "用戶 Discord ID",
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["achievement_id"],
                                "properties": {
                                    "achievement_id": {
                                        "type": "integer",
                                        "format": "int64",
                                        "description": "成就 ID"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "成功頒發成就",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/UserAchievement"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "用戶已獲得此成就或成就不存在"
                    }
                }
            }
        }

        # 成就進度 API
        self.spec["paths"]["/users/{user_id}/progress"] = {
            "get": {
                "tags": ["progress"],
                "summary": "取得用戶成就進度",
                "description": "取得特定用戶的所有成就進度",
                "parameters": [
                    {
                        "name": "user_id",
                        "in": "path",
                        "required": True,
                        "description": "用戶 Discord ID",
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "成功取得用戶進度",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/components/schemas/AchievementProgress"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        # 統計 API
        self.spec["paths"]["/statistics/global"] = {
            "get": {
                "tags": ["statistics"],
                "summary": "取得全域統計資料",
                "description": "取得成就系統的全域統計資料",
                "responses": {
                    "200": {
                        "description": "成功取得統計資料",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "total_achievements": {
                                            "type": "integer",
                                            "description": "總成就數量"
                                        },
                                        "active_achievements": {
                                            "type": "integer",
                                            "description": "啟用的成就數量"
                                        },
                                        "total_user_achievements": {
                                            "type": "integer",
                                            "description": "用戶獲得的總成就數"
                                        },
                                        "unique_users": {
                                            "type": "integer",
                                            "description": "有成就的獨特用戶數"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        logger.info("成就系統 API 路徑定義已添加")

    def generate_spec(self) -> dict[str, Any]:
        """生成完整的 OpenAPI 規格.
        
        Returns:
            完整的 OpenAPI 3.0 規格字典
        """
        # 添加所有組件
        self.add_achievement_schemas()
        self.add_achievement_paths()

        # 添加生成時間戳記
        self.spec["info"]["x-generated-at"] = datetime.now().isoformat()

        logger.info("OpenAPI 規格生成完成")
        return self.spec

    def save_spec_to_file(self, output_path: Path) -> None:
        """將 OpenAPI 規格保存到文件.
        
        Args:
            output_path: 輸出文件路徑
        """
        spec = self.generate_spec()

        # 確保輸出目錄存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 寫入 JSON 文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)

        logger.info(f"OpenAPI 規格已保存至: {output_path}")

    def generate_swagger_html(self, spec_url: str = "/api/openapi.json") -> str:
        """生成 Swagger UI HTML 頁面.
        
        Args:
            spec_url: OpenAPI 規格文件的 URL
            
        Returns:
            Swagger UI HTML 內容
        """
        html_template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title} - API 文档</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.10.5/swagger-ui.css" />
    <style>
        .swagger-ui .topbar {{ display: none; }}
        .swagger-ui .info .title {{ color: #3b4151; }}
        .swagger-ui .scheme-container {{ background: #fafafa; padding: 10px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.10.5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5.10.5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            const ui = SwaggerUIBundle({{
                url: '{spec_url}',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                tryItOutEnabled: true,
                supportedSubmitMethods: ['get', 'post', 'put', 'delete', 'patch'],
                docExpansion: 'list',
                defaultModelsExpandDepth: 2,
                defaultModelExpandDepth: 2,
                displayRequestDuration: true,
                showExtensions: true,
                showCommonExtensions: true,
                requestInterceptor: function(request) {{
                    // 添加 API Key 如果需要
                    if (localStorage.getItem('api_key')) {{
                        request.headers['X-API-Key'] = localStorage.getItem('api_key');
                    }}
                    return request;
                }}
            }});
            
            // 添加自定義樣式
            setTimeout(function() {{
                const style = document.createElement('style');
                style.textContent = `
                    .swagger-ui .info .title {{ 
                        font-size: 2.5em; 
                        font-weight: bold; 
                        color: #5865F2; 
                    }}
                    .swagger-ui .info .description {{ 
                        font-size: 1.2em; 
                        line-height: 1.6; 
                    }}
                    .swagger-ui .scheme-container .schemes > label {{ 
                        font-weight: bold; 
                    }}
                `;
                document.head.appendChild(style);
            }}, 100);
        }};
    </script>
</body>
</html>"""

        logger.info("Swagger UI HTML 已生成")
        return html_template


class APIDocumentationValidator:
    """API 文件驗證器.
    
    驗證 API 文件的完整性和準確性。
    """

    def __init__(self, spec: dict[str, Any]):
        """初始化驗證器.
        
        Args:
            spec: OpenAPI 規格字典
        """
        self.spec = spec
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_spec(self) -> dict[str, Any]:
        """驗證 OpenAPI 規格.
        
        Returns:
            驗證結果字典
        """
        self._validate_basic_structure()
        self._validate_schemas()
        self._validate_paths()
        self._validate_responses()

        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings)
        }

    def _validate_basic_structure(self) -> None:
        """驗證基本結構."""
        required_fields = ["openapi", "info", "paths"]

        for field in required_fields:
            if field not in self.spec:
                self.errors.append(f"缺少必要欄位: {field}")

        # 驗證 OpenAPI 版本
        if self.spec.get("openapi", "").startswith("3."):
            logger.debug("OpenAPI 版本驗證通過")
        else:
            self.errors.append("不支援的 OpenAPI 版本")

    def _validate_schemas(self) -> None:
        """驗證 Schema 定義."""
        schemas = self.spec.get("components", {}).get("schemas", {})

        if not schemas:
            self.warnings.append("沒有定義任何 Schema")
            return

        # 檢查必要的成就系統 Schema
        required_schemas = [
            "Achievement",
            "AchievementCategory",
            "UserAchievement",
            "AchievementProgress"
        ]

        for schema_name in required_schemas:
            if schema_name not in schemas:
                self.errors.append(f"缺少必要 Schema: {schema_name}")

    def _validate_paths(self) -> None:
        """驗證 API 路徑定義."""
        paths = self.spec.get("paths", {})

        if not paths:
            self.errors.append("沒有定義任何 API 路徑")
            return

        # 檢查必要的 API 端點
        required_paths = [
            "/categories",
            "/achievements",
            "/users/{user_id}/achievements"
        ]

        for path in required_paths:
            if path not in paths:
                self.warnings.append(f"建議添加 API 路徑: {path}")

    def _validate_responses(self) -> None:
        """驗證回應定義."""
        paths = self.spec.get("paths", {})

        for path, methods in paths.items():
            for method, operation in methods.items():
                if isinstance(operation, dict) and "responses" in operation:
                    responses = operation["responses"]

                    # 檢查是否有成功回應
                    success_codes = [code for code in responses.keys()
                                   if code.startswith("2")]

                    if not success_codes:
                        self.warnings.append(
                            f"路徑 {path} 方法 {method} 缺少成功回應"
                        )


def generate_api_documentation(
    output_dir: Path,
    title: str = "Discord ROAS Bot API",
    version: str = "2.0.0"
) -> dict[str, Any]:
    """生成完整的 API 文件.
    
    Args:
        output_dir: 輸出目錄
        title: API 標題
        version: API 版本
        
    Returns:
        生成結果字典
    """
    try:
        # 建立輸出目錄
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成 OpenAPI 規格
        generator = OpenAPIGenerator(title, version)
        spec = generator.generate_spec()

        # 保存 OpenAPI JSON 文件
        json_path = output_dir / "openapi.json"
        generator.save_spec_to_file(json_path)

        # 生成 Swagger UI HTML
        html_content = generator.generate_swagger_html("/api/openapi.json")
        html_path = output_dir / "index.html"

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # 驗證文件
        validator = APIDocumentationValidator(spec)
        validation_result = validator.validate_spec()

        # 保存驗證報告
        report_path = output_dir / "validation_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(validation_result, f, ensure_ascii=False, indent=2)

        result = {
            "success": True,
            "files_generated": [
                str(json_path),
                str(html_path),
                str(report_path)
            ],
            "validation": validation_result,
            "message": f"API 文件已成功生成至 {output_dir}"
        }

        logger.info(f"API 文件生成完成: {output_dir}")
        return result

    except Exception as e:
        logger.error(f"API 文件生成失敗: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "API 文件生成失敗"
        }


__all__ = [
    "APIDocumentationValidator",
    "OpenAPIGenerator",
    "generate_api_documentation"
]
