<!-- BEGIN:DOC(design) v1 -->

## 1. 系統概覽 (Overview)

本設計文件定義 `v2.4.1` 版本的技術架構、模組切分與關鍵流程，對齊需求（R1–R9）與任務（T1–T11），目標提升：
- 穩定性：修復成就系統啟動（R1）、併發鎖定（R2）、資料完整性（R3）
- 可測試性：dpytest 與隨機交互（R4）
- 可維運性：統一錯誤代碼（R5）、日誌與設定（多處）
- 可重現建置：uv + pyproject（R6）、Python 3.13（R7）
- 部署便捷性：跨平台 Docker 一鍵啟動（R8）
- 操作體驗：終端互動管理模式（R9）

設計原則：
- 明確分層：Core（設定/日誌/錯誤）、Services（業務邏輯）、Panels（交互層）、App（啟動流程）、DB（基礎存取）
- 可觀測：一致化日誌、錯誤代碼、健康檢查
- 預防性穩定：資料庫重試退避、UPSERT、測試資料隔離

## 2. 目錄與模組切分 (Architecture & Modules)

目錄約定（關鍵路徑）：
- `src/app/bootstrap.py`：應用啟動序、依賴注入與生命週期管理（R1）
- `src/core/config.py`、`src/core/logging.py`、`src/core/errors.py`、`src/core/error_codes.py`（R5）
- `src/services/achievement_service.py`、`src/services/activity_meter_service.py`、`src/services/economy_service.py`、`src/services/government_service.py`、`src/services/test_orchestrator_service.py`
- `src/panels/achievement_panel.py`、`src/panels/terminal_panel.py`（R9）
- `src/db/sqlite.py`、`src/db/retry.py`（R2/R3）
- `migrations/*.sql`、`scripts/migrate.py`（R3）
- 測試：`tests/unit/*`、`tests/integration/*`、`tests/dpytest/*`、`tests/random/*`（R4）
- 部署：`docker/Dockerfile`、`docker/compose.yaml`、`scripts/start.*`（R8）

## 3. 啟動流程與依賴注入 (R1)

抽象生命週期：prepare → init → wire → start → ready。
- prepare：載入 `config`、初始化 `logging`
- init：DB 層（`sqlite` 模式、WAL、busy_timeout）、核心服務（economy、government、activity_meter）
- wire：`AchievementService` 注入其依賴（economy/government/activity_meter）
- start：Discord bot / Panels / 終端互動面板
- ready：健康檢查 OK，對外服務可用

啟動序（示意）：
```python
# src/app/bootstrap.py（示意）
from core.config import AppConfig
from core.logging import setup_logging
from db.sqlite import create_sqlite_engine
from services import (
    EconomyService, GovernmentService, ActivityMeterService, AchievementService
)

async def bootstrap() -> None:
    config = AppConfig.from_env()
    setup_logging(config.logging)

    engine = create_sqlite_engine(config.database)

    economy = EconomyService(engine)
    government = GovernmentService(engine)
    activity_meter = ActivityMeterService(engine)

    achievement = AchievementService(
        economy_service=economy,
        government_service=government,
        activity_meter_service=activity_meter,
    )
    await achievement.initialize()

    # register panels / commands
    # start bot & terminal panel (optional)
```

要求：
- `AchievementService.initialize()` 應為冪等，重入不影響狀態
- 面板註冊需在服務可用後進行（避免空指標/依賴缺失）

## 4. 成就系統 (R1)

職責邊界：
- `AchievementService`：決策授予條件、狀態查詢、發放流程協調
- 整合：
  - `EconomyService.adjust_balance(user, amount)`（經濟獎勵）
  - `GovernmentService.assign_role(user, role_id)`（身分組）
  - `ActivityMeterService` 提供活動指標（如訊息數、活躍度）

關鍵設計：
- 授予冪等：同一成就僅授與一次；使用唯一鍵（user_id, achievement_id）
- 發放原子性：失敗時回滾或補償（記錄 `ErrorCode`、重試策略）
- 可測試性：以介面注入依賴，允許在單元測試中替身（stub/mocks）

## 5. 併發與資料庫 (R2/R3)

SQLite 策略：
- 模式：WAL（提升併發讀寫）、`busy_timeout`（如 5000ms）、`synchronous=NORMAL`（可視風險調整）
- 連線：集中化建立引擎/連線工廠，避免失控的多連線
- 重試：`retry_locked` 指數退避與抖動（僅對 `locked`/`busy` 類別錯誤）

寫入設計：
- 熱點鍵採 `UPSERT`（`INSERT ... ON CONFLICT DO UPDATE`）
- 交易邊界明確、盡量縮小臨界區
- 批次提交：聚合後減少提交次數（視功能適用）

資料模型（示例 `activity_meter`）：
- 主鍵/唯一鍵：`(guild_id, user_id)`
- 欄位：`score`（或分欄位統計）、`updated_at`
- 遷移：`migrations/0001_create_activity_meter.sql` 建置與必要索引

測試資料完整性：
- 測試級隔離：每案例使用臨時 DB 或記憶體 DB
- 清理工具：`tests/helpers/db_utils.py` 重建 schema、避免 UNIQUE 汙染

## 6. 測試策略與 dpytest/隨機交互 (R4)

測試分層：
- 單元：服務邏輯、錯誤映射、退避重試
- 整合：啟動序、DB UPSERT、遷移雙態（空白/既有 DB）
- e2e：dpytest 模擬 Discord 事件與指令，覆蓋成功路徑/錯誤處理
- 隨機交互：可指定 `--seed`、`--max-steps`，失敗輸出重現報告（包含種子與操作序列）

穩定性：
- 重複執行策略（CI 中 rerun）偵測 flaky
- 隨機測試預設超時，避免掛起

## 7. 錯誤代碼系統 (R5)

命名與分類（示例）：
- `CORE-XXXX` 核心（設定/日誌）
- `DB-LOCKED-XXXX` 資料庫鎖定/重試
- `SRV-ACH-XXXX` 成就模組
- `SRV-ACT-XXXX` 活躍度模組
- `SRV-ECO-XXXX` 經濟模組
- `SRV-GOV-XXXX` 政府模組
- `CLI-XXXX` 終端互動

原則：
- 唯一性與版本化；文件化對照表 `docs/error-codes.md`
- 使用者訊息與日誌均含錯誤代碼；錯誤轉譯集中於 `core/error_codes.py`

## 8. 依賴與環境 (R6/R7)

- 依賴：`pyproject.toml` 管理、`uv` 安裝與鎖定（`uv.lock`）
- Python：3.13（本地與容器一致），在 `pyproject.toml` 宣告 `requires-python`
- CI：使用 `uv sync` 與快取，提高速度與可重現

## 9. Docker 與一鍵啟動 (R8)

- 基底映像：`python:3.13-slim`
- 內容：系統依賴、`uv`、建立應用使用者、掛載 `logs/`、`.env`
- Compose：服務宣告、環境變數、卷、健康檢查
- 一鍵腳本：`scripts/start.sh`、`scripts/start.ps1`，含前置檢查與錯誤代碼回傳

## 10. 終端互動管理模式 (R9)

- 互動主迴圈：`src/cli/interactive.py`，支援 `help`、未知指令提示、超時/非互動關閉
- 指令派發：`src/panels/terminal_panel.py` 定義命令與授權邏輯
- 審計：日誌通道區分、遮罩敏感資訊

## 11. 設定、日誌與安全 (Cross-cutting)

- 設定：`core/config.py` 支援環境變數、預設值、型別檢查
- 日誌：`core/logging.py` 統一格式、檔案路徑、滾動策略，避免敏感資訊
- 憑證：僅透過環境變數/秘密管理器提供，不落地於版本庫

## 12. CI/CD 與觀測 (Ops)

- CI：lint/測試（含 dpytest）、可選壓測工作流（輸出 p50/p95/p99 與錯誤率）
- 觀測：啟動與致命錯誤字串掃描、健康檢查腳本 `scripts/verify_container_health.sh`

## 13. 風險、相容性與回滾 (Risk)

- SQLite 併發：以 WAL+退避緩解，若仍不足，規劃 PostgreSQL 遷移路線（未納入本版）
- 依賴相容：升級至 Python 3.13 後，針對 `discord.py` 等關鍵套件建立相容性檢查清單
- 回滾：保留 `requires-python` 調降與 Docker tag 回退流程

## 14. 對應矩陣 (Traceability)

- R1 ↔ T1、T2.1：啟動序與成就整合
- R2 ↔ T3：SQLite 併發、退避、UPSERT
- R3 ↔ T4：遷移雙態、測試隔離、完整性回歸
- R4 ↔ T5：dpytest、隨機交互、重現報告
- R5 ↔ T2.2、T8：錯誤代碼規範、落地與一致日誌
- R6 ↔ T7：uv + pyproject、CI 切換
- R7 ↔ T9：Python 3.13 升級與相容
- R8 ↔ T6：Docker 與啟動腳本
- R9 ↔ T11：終端互動模式

## 15. 變更摘要 (Changelog)
- 新增：分層架構骨架、啟動序、併發策略（WAL/退避/UPSERT）、錯誤代碼系統、dpytest 與隨機交互、uv + pyproject、Docker 一鍵啟動、終端互動模式。

<!-- FORMAT_CHECK
doc_type: design
schema_version: 1
source_of_truth: ["docs/specs/requirement.md","docs/specs/task.md"]
references_requirements: ["R1","R2","R3","R4","R5","R6","R7","R8","R9"]
references_tasks: ["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11"]
-->

<!-- END:DOC -->
