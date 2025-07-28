# 數據遷移工具

此工具包提供完整的數據遷移功能，用於將舊歡迎系統的數據遷移到新的企業級架構。

## 功能特點

- **完整遷移**: 支援設定數據和背景圖片的完整遷移
- **數據驗證**: 提供多層次的遷移驗證機制
- **回滾支援**: 支援遷移失敗時的自動或手動回滾
- **進度追蹤**: 詳細的遷移進度和統計信息
- **報告生成**: 自動生成詳細的遷移報告

## 主要組件

### 1. WelcomeMigrationTool
主要的遷移執行工具，負責：
- 讀取舊系統數據
- 轉換數據格式
- 執行實際遷移
- 創建備份和回滾

### 2. MigrationValidator  
遷移驗證工具，負責：
- 數據完整性檢查
- 功能完整性測試
- 性能基準測試
- 檔案系統驗證

### 3. MigrationManager
統一管理介面，負責：
- 遷移流程管控
- 錯誤處理
- 報告生成
- 命令行介面

## 使用方法

### 命令行使用

```bash
# 執行完整遷移（試運行）
python -m src.tools.migration.migration_manager migrate --dry-run

# 執行實際遷移
python -m src.tools.migration.migration_manager migrate --auto-rollback

# 僅驗證遷移結果
python -m src.tools.migration.migration_manager validate

# 回滾指定遷移
python -m src.tools.migration.migration_manager rollback --migration-id 20250127_143000

# 查看遷移計劃
python -m src.tools.migration.migration_manager plan
```

### 程序化使用

```python
from src.core.container import Container
from src.tools.migration import MigrationManager

# 初始化
container = Container()
manager = MigrationManager(container)

# 執行遷移
result = await manager.execute_migration_plan(
    dry_run=False,
    backup=True,
    validate=True,
    auto_rollback=True
)

# 生成報告
report = await manager.generate_migration_report(result)
print(report)
```

## 遷移流程

1. **預檢查**: 檢查舊數據庫和新系統狀態
2. **備份創建**: 創建舊數據和新數據的備份
3. **設定遷移**: 遷移歡迎設定數據
4. **圖片遷移**: 遷移背景圖片文件
5. **驗證檢查**: 驗證遷移的完整性和正確性
6. **報告生成**: 生成詳細的遷移報告

## 數據映射

### 設定欄位映射

| 舊系統欄位 | 新系統欄位 | 說明 |
|-----------|-----------|------|
| channel_id | channel_id | 歡迎頻道 ID |
| title | title | 圖片標題 |
| description | description | 圖片描述 |
| message | message | 歡迎訊息模板 |
| avatar_x | avatar_x | 頭像 X 坐標 |
| avatar_y | avatar_y | 頭像 Y 坐標 |
| title_y | title_y | 標題 Y 坐標 |
| description_y | desc_y | 描述 Y 坐標 |
| title_font_size | title_font_size | 標題字體大小 |
| desc_font_size | desc_font_size | 描述字體大小 |
| avatar_size | avatar_size | 頭像大小 |

### 新增欄位

新系統增加了以下欄位：
- `enabled`: 是否啟用歡迎功能
- `enable_image`: 是否啟用歡迎圖片

## 驗證檢查

遷移驗證包括以下檢查：

### 數據庫結構驗證
- 檢查必要表是否存在
- 驗證表結構完整性
- 檢查索引和約束

### 數據內容驗證
- 對比新舊數據一致性
- 檢查數據完整性
- 驗證數據類型正確性

### 功能驗證
- CRUD 操作測試
- 配置驗證測試
- 背景圖片操作測試

### 性能驗證
- 讀取操作基準測試
- 寫入操作基準測試
- 性能指標評估

### 檔案系統驗證
- 背景圖片目錄檢查
- 檔案權限驗證
- 字體文件檢查

## 錯誤處理

### 常見錯誤

1. **舊數據庫不存在**
   - 檢查 `dbs/welcome.db` 是否存在
   - 確認路徑配置正確

2. **新系統未初始化**
   - 確保新系統已正確安裝
   - 運行依賴注入容器初始化

3. **權限問題**
   - 檢查文件讀寫權限
   - 確認目錄創建權限

4. **數據格式錯誤**
   - 檢查舊數據庫結構
   - 驗證數據完整性

### 自動回滾

當啟用自動回滾時，系統會在遷移失敗時自動恢復：
- 恢復備份的新系統數據
- 還原背景圖片文件
- 記錄回滾操作日誌

## 備份和恢復

### 備份位置

- 舊數據庫備份: `backups/welcome_migration_{id}/old_welcome.db`
- 舊背景圖片: `backups/welcome_migration_{id}/old_backgrounds/`
- 新系統備份: `backups/welcome_migration_{id}/new_system_backup.json`

### 手動恢復

如需手動恢復，可以：
1. 使用 `rollback` 命令
2. 手動還原備份文件
3. 重新初始化新系統

## 日誌和報告

### 日誌位置
- 遷移日誌: `logs/welcome_migration.log`
- 驗證日誌: `logs/migration_validation.json`

### 報告內容
- 遷移統計信息
- 各階段執行結果
- 錯誤和警告詳情
- 性能基準數據
- 改進建議

## 注意事項

1. **數據安全**: 建議在遷移前手動備份重要數據
2. **測試環境**: 建議先在測試環境執行試運行
3. **服務停機**: 遷移期間建議停止機器人服務
4. **磁盤空間**: 確保有足夠空間存放備份文件
5. **權限設定**: 確認文件和目錄權限正確設定

## 故障排除

### 如果遷移失敗

1. 檢查日誌文件中的錯誤信息
2. 使用驗證工具檢查數據狀態
3. 如有必要，執行回滾操作
4. 修復問題後重新執行遷移

### 如果驗證失敗

1. 檢查驗證報告中的詳細信息
2. 手動檢查數據一致性
3. 修復發現的問題
4. 重新執行驗證

### 獲取支援

如遇到問題，請：
1. 收集相關日誌文件
2. 記錄詳細的錯誤信息
3. 提供系統環境信息
4. 聯繫技術支援團隊