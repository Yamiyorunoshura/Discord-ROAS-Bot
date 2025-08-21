# 資料庫遷移系統操作指南

## 概述

本指南介紹如何使用Discord機器人模組化系統的資料庫遷移工具。我們的遷移系統包含四個核心腳本：

- `migration_validator.py` - 遷移驗證和完整性檢查
- `migration_manager.py` - 遷移執行和狀態管理  
- `backup_manager.py` - 資料庫備份和恢復
- 四個SQL遷移腳本（001-004）

## 遷移腳本結構

### 001_create_economy_tables.sql
建立經濟系統核心表格：
- economy_accounts - 經濟帳戶
- economy_transactions - 交易記錄  
- currency_settings - 貨幣設定
- economy_audit_log - 經濟系統審計日誌

### 002_create_core_system_tables.sql  
建立核心系統基礎表格：
- schema_migrations - 遷移管理
- system_config - 系統配置
- system_logs - 系統日誌
- user_sessions - 使用者會話
- permissions - 權限管理
- role_permissions - 角色權限映射
- system_statistics - 系統統計

### 003_create_government_tables.sql
建立政府系統相關表格：
- government_departments - 政府部門
- government_members - 政府成員
- government_resolutions - 政府決議
- government_votes - 政府投票記錄
- government_audit_log - 政府系統審計日誌

### 004_create_achievement_tables.sql
建立成就系統表格：
- achievements - 成就定義
- user_achievement_progress - 使用者成就進度
- achievement_rewards_log - 獎勵發放記錄
- user_badges - 使用者徽章
- achievement_audit_log - 成就系統審計日誌

## 工具使用指南

### 1. 遷移驗證工具

```bash
# 執行完整的遷移驗證
python scripts/migration_validator.py

# 功能包括：
# - SQL語法檢查
# - 遷移序列完整性驗證
# - 資料庫結構檢查  
# - 索引和約束驗證
# - 外鍵關係測試
# - 觸發器和視圖檢查
```

### 2. 遷移管理工具

```bash
# 查看遷移狀態
python scripts/migration_manager.py status

# 應用所有待處理遷移
python scripts/migration_manager.py apply

# 應用特定版本遷移
python scripts/migration_manager.py apply 002

# 回滾遷移（標記為已回滾）
python scripts/migration_manager.py rollback 002

# 驗證遷移完整性
python scripts/migration_manager.py verify
```

### 3. 備份管理工具

```bash
# 建立壓縮備份
python scripts/backup_manager.py backup --name backup_before_migration

# 建立非壓縮備份
python scripts/backup_manager.py backup --name backup_test --no-compress

# 列出所有備份
python scripts/backup_manager.py list

# 恢復備份
python scripts/backup_manager.py restore backup_before_migration

# 刪除指定備份
python scripts/backup_manager.py delete old_backup

# 清理舊備份（保留30天內或最近10個）
python scripts/backup_manager.py cleanup --keep-days 30 --keep-count 10
```

## 標準操作流程

### 初次部署

1. **驗證遷移腳本**
   ```bash
   python scripts/migration_validator.py
   ```

2. **建立備份（如果有現有資料庫）**  
   ```bash
   python scripts/backup_manager.py backup --name pre_migration_backup
   ```

3. **應用所有遷移**
   ```bash
   python scripts/migration_manager.py apply
   ```

4. **檢查遷移狀態**
   ```bash
   python scripts/migration_manager.py status
   ```

### 系統升級

1. **建立當前資料庫備份**
   ```bash
   python scripts/backup_manager.py backup --name upgrade_backup_$(date +%Y%m%d_%H%M%S)
   ```

2. **驗證新的遷移腳本**
   ```bash  
   python scripts/migration_validator.py
   ```

3. **應用新遷移**
   ```bash
   python scripts/migration_manager.py apply
   ```

4. **驗證升級結果**
   ```bash
   python scripts/migration_manager.py verify
   ```

### 故障恢復

1. **查看備份清單**
   ```bash
   python scripts/backup_manager.py list
   ```

2. **選擇合適的備份進行恢復**
   ```bash
   python scripts/backup_manager.py restore [backup_name]
   ```

3. **驗證恢復結果**
   ```bash
   python scripts/migration_manager.py status
   ```

## 資料庫檔案位置

- **主資料庫**: `dbs/main.db`
- **備份檔案**: `backups/`
- **遷移腳本**: `scripts/migrations/`
- **日誌檔案**: `logs/`

## 安全注意事項

1. **備份策略**：執行任何遷移操作前都應建立備份
2. **測試環境**：在生產環境前先在測試環境執行
3. **權限控制**：確保適當的檔案系統權限
4. **監控**：定期檢查遷移狀態和資料完整性

## 故障排除

### 常見問題

1. **遷移失敗**
   - 檢查遷移日誌中的錯誤訊息
   - 使用 `migration_validator.py` 檢查SQL語法
   - 確認資料庫檔案權限

2. **備份恢復失敗**  
   - 檢查備份檔案是否存在且完整
   - 確認目標資料庫檔案權限
   - 檢查磁碟空間是否充足

3. **效能問題**
   - 檢查資料庫索引是否正確建立
   - 使用 `ANALYZE` 指令更新統計資訊
   - 考慮在大型資料上執行 `VACUUM`

### 緊急恢復程序

如果系統完全故障：

1. 停止所有應用程序
2. 從最近的備份恢復資料庫
3. 檢查資料完整性  
4. 重新啟動應用程序
5. 監控系統狀態

## 維護建議

- 定期執行 `migration_validator.py` 檢查系統健康度
- 每週清理舊備份檔案
- 監控資料庫大小和效能指標
- 保持遷移腳本的版本控制

## 支援聯繫

如遇到技術問題，請提供：
- 錯誤訊息截圖
- 遷移驗證報告
- 系統環境資訊
- 操作步驟記錄