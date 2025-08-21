#!/bin/bash
# 資料庫備份腳本
# Task ID: 11 - 建立文件和部署準備

set -euo pipefail

# 配置
DATA_DIR="/app/data"
BACKUP_DIR="/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 日誌函數
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# 創建備份
backup_database() {
    local db_file="$1"
    local backup_name="$2"
    
    if [[ -f "$DATA_DIR/$db_file" ]]; then
        log "備份 $db_file..."
        
        # 使用SQLite備份命令
        sqlite3 "$DATA_DIR/$db_file" ".backup $BACKUP_DIR/${backup_name}_${TIMESTAMP}.db"
        
        # 壓縮備份
        gzip "$BACKUP_DIR/${backup_name}_${TIMESTAMP}.db"
        
        log "備份完成: ${backup_name}_${TIMESTAMP}.db.gz"
    else
        log "警告: 找不到資料庫文件 $db_file"
    fi
}

# 清理舊備份
cleanup_old_backups() {
    log "清理 $RETENTION_DAYS 天前的備份..."
    
    find "$BACKUP_DIR" -name "*.db.gz" -mtime +$RETENTION_DAYS -delete
    
    log "舊備份清理完成"
}

# 驗證備份
verify_backup() {
    local backup_file="$1"
    
    log "驗證備份文件: $backup_file"
    
    # 解壓到臨時位置
    local temp_file="/tmp/verify_backup.db"
    gunzip -c "$backup_file" > "$temp_file"
    
    # 檢查資料庫完整性
    if sqlite3 "$temp_file" "PRAGMA integrity_check;" | grep -q "ok"; then
        log "備份驗證成功"
        rm "$temp_file"
        return 0
    else
        log "錯誤: 備份驗證失敗"
        rm "$temp_file"
        return 1
    fi
}

# 主函數
main() {
    log "開始資料庫備份..."
    
    # 創建備份目錄
    mkdir -p "$BACKUP_DIR"
    
    # 備份主資料庫
    backup_database "discord_data.db" "main"
    
    # 備份訊息資料庫
    backup_database "message.db" "message"
    
    # 驗證備份
    for backup in "$BACKUP_DIR"/*_${TIMESTAMP}.db.gz; do
        if [[ -f "$backup" ]]; then
            verify_backup "$backup"
        fi
    done
    
    # 清理舊備份
    cleanup_old_backups
    
    log "備份流程完成"
}

# 執行備份
main "$@"