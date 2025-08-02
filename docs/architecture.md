# Discord ROAS Bot Full-Stack 架構設計

## 概述

Discord ROAS Bot 是一個全端(full-stack) Discord 機器人系統，旨在提供社群管理功能，包括成就系統、活躍度追蹤、安全防護、資料同步等。本架構設計涵蓋前端（Discord 介面與潛在 web 面板）、後端邏輯、資料儲存、基礎設施和部署。重點在於模組化、可擴展性、高效能，以及用戶導向的設計。系統採用 Python 為核心，強調跨端優化（Discord 客戶端與伺服器端），並考慮成本與開發者體驗。

### 核心原則
- **整體系統思維**：每個組件皆為更大系統的一部分。
- **用戶體驗驅動**：從用戶旅程（e.g., 互動面板）反推架構。
- **務實技術選擇**：優先穩定技術（如 Discord.py），僅在必要時引入創新。
- **漸進式複雜度**：從簡單 bot 開始，可擴展到 web 應用。
- **跨端效能焦點**：優化 Discord API 呼叫與資料庫查詢。
- **開發者體驗優先**：使用 pyproject.toml、ruff 等工具提升生產力。
- **每層安全**：深度防禦，包括 API 驗證與資料加密。
- **資料導向設計**：資料需求驅動架構（e.g., PostgreSQL 為中心）。
- **成本意識**：平衡技術理想與資源消耗。
- **活化架構**：設計易於變更與適應。

## 高層架構

- **前端層**：
  - **主要介面**：Discord 嵌入式面板（embeds）、視圖（views）、按鈕（buttons）、模態（modals）和選擇器（selectors）。例如，成就面板使用 `AchievementPanel` 類別動態生成 UI。
  - **潛在擴展**：Web 儀表板（使用 React 或 Streamlit），透過 REST API 連接到後端，提供管理員遠端監控。
  - **技術**：Discord.py UI 組件；web 前端可使用 JavaScript/TypeScript 與 Bootstrap 確保響應式設計。
  - **用戶旅程**：用戶透過 slash 指令（如 /achievement）觸發面板，系統即時回應互動。

- **後端層**：
  - **核心邏輯**：Python 應用，使用 discord.py 處理事件（如 on_message、on_member_join）和指令。模組化為 cogs（e.g., achievement, activity_meter, protection）。
  - **服務層**：獨立服務類別（如 AchievementAwarder、ActivityMonitor）處理業務邏輯，確保可重用。
  - **API**：內部 RESTful API 使用 FastAPI，提供資料同步與外部整合（e.g., /api/activity/stats）。
  - **事件處理**：異步事件匯流排（EventBus）管理跨模組通訊。
  - **技術**：Python 3.12+、discord.py、SQLAlchemy（ORM）、structlog（日誌）。

- **資料層**：
  - **資料庫**：PostgreSQL 作為主要儲存，用於用戶資料、成就進度、活躍度記錄等。表格如 users、achievements、activity_logs。
  - **快取**：Redis 或內建 dict 快取（如在 cogs 中的 cache.py），減少資料庫負載。
  - **配置**：JSON 檔案（如 config.py、departments.json）儲存可自訂設定。
  - **關係**：用戶關聯成就、部門關聯貨幣賬戶，使用外鍵確保資料完整性。

- **基礎設施層**：
  - **部署**：Docker 容器化，Kubernetes 管理水平擴展。支援雲端（如 AWS ECS）或本地伺服器。
  - **監控**：Prometheus 指標、Sentry 錯誤追蹤（雖然 v2.2 移除部分面板，但保留核心監控）。
  - **安全性**：SSL 加密 API、Discord OAuth、速率限制防範濫用。
  - **效能優化**：異步 I/O、非阻塞資料庫查詢、負載平衡。

## 模組分解

### 1. 前端模組
- **組件**：UI 管理器（如 UIManager in activity_meter）、嵌入生成器（e.g., SettingsEmbed）。
- **資料流**：用戶互動 → Discord API 回調 → 後端服務 → 更新嵌入。
- **依賴**：discord.ui 模組；web 擴展使用 Axios 呼叫 API。
- **效能考量**：限制嵌入大小 &lt; 6000 字元，使用分頁處理長列表。

### 2. 後端模組
- **Cogs 結構**：每個功能為獨立 cog（e.g., AchievementCog 處理成就邏輯）。
- **服務**：抽象服務層（如 SyncService）處理複雜操作，支援事務（TransactionCoordinator）。
- **資料流**：事件觸發（e.g., on_message）→ 服務處理 → 資料庫更新 → UI 刷新。
- **依賴**：discord.py、FastAPI、asyncio。

### 3. 資料模型
- **主要實體**：User (id, balance, activity_score)、Achievement (id, criteria)、Department (id, roles_json)。
- **關係**：一對多（用戶到成就）、多對多（部門到用戶）。
- **遷移**：使用 Alembic 管理 schema 變化。

### 4. API 設計
- **端點**：
  - GET /api/users/{id}/achievements：取得用戶成就。
  - POST /api/sync：觸發資料同步。
  - **安全性**：JWT 認證、角色基礎存取控制。
- **Discord 指令**：/activity、/protect 等，使用 app_commands 註冊。

## 技術選擇與權衡
- **為何 Python/Discord.py**：成熟生態、易開發；替代如 JavaScript (discord.js) 但 Python 更適合資料處理。
- **資料庫選擇**：PostgreSQL 優於 SQLite（更好擴展）；權衡：簡單查詢使用快取減少負載。
- **前端權衡**：Discord UI 簡單但受限；添加 web 前端增加複雜度，但提升管理員體驗。
- **假設**：伺服器規模中等（&lt;1000 用戶），若成長需添加消息佇列（如 RabbitMQ）。
- **成本**：本地部署零成本；雲端使用 AWS Free Tier。

## 部署與維護
- **CI/CD**：GitHub Actions 測試與部署。
- **擴展**：水平擴展後端實例，資料庫使用讀寫分離。
- **監控**：整合 Grafana 視覺化指標。