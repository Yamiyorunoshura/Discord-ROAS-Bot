# Discord ADR Bot 版本管理指南

## 📋 分支管理策略

### 分支類型
- **`master`** - 主分支，僅用於穩定版本
- **`develop`** - 開發分支，用於日常開發
- **`feature/*`** - 功能分支，用於新功能開發
- **`hotfix/*`** - 修復分支，用於緊急修復
- **`release/*`** - 發布分支，用於版本準備

### 分支管理命令
```bash
# 創建開發分支
git checkout -b develop

# 創建功能分支
git checkout -b feature/new-function develop

# 創建修復分支
git checkout -b hotfix/fix-bug master

# 創建發布分支
git checkout -b release/v1.65 develop
```

## 🔄 版本回退方法

### 1. 軟回退（推薦）- 使用 git revert
```bash
# 撤銷最新提交
git revert HEAD

# 撤銷特定提交
git revert <commit-hash>

# 撤銷多個提交
git revert HEAD~3..HEAD

# 推送到遠程
git push origin master
```

### 2. 硬回退（危險）- 使用 git reset
```bash
# 回退到上一個提交（保留修改）
git reset --soft HEAD~1

# 回退到上一個提交（撤銷暫存）
git reset --mixed HEAD~1

# 完全回退（丟失修改）
git reset --hard HEAD~1

# 強制推送到遠程（危險）
git push --force-with-lease origin master
```

### 3. 回退到特定版本標籤
```bash
# 查看所有標籤
git tag -l

# 基於標籤創建新分支
git checkout -b rollback-v1.63 v1.63

# 或直接回退到標籤
git reset --hard v1.63
```

## 🏷️ 版本標籤管理

### 創建標籤
```bash
# 創建輕量標籤
git tag v1.65

# 創建帶註釋的標籤（推薦）
git tag -a v1.65 -m "Release version 1.65 - 新增功能描述"

# 對特定提交打標籤
git tag -a v1.65 9fceb02 -m "Release version 1.65"
```

### 管理標籤
```bash
# 查看標籤列表
git tag -l

# 查看標籤詳細信息
git show v1.65

# 刪除本地標籤
git tag -d v1.65

# 刪除遠程標籤
git push origin --delete v1.65

# 推送標籤到遠程
git push origin v1.65
git push --tags
```

## 📦 版本發布流程

### 準備發布
1. 從 develop 創建 release 分支
2. 在 release 分支上進行最終測試和修復
3. 合併到 master 並打標籤
4. 合併回 develop

```bash
# 1. 創建發布分支
git checkout -b release/v1.65 develop

# 2. 進行最終修改和測試
# ... 修改代碼 ...

# 3. 合併到 master
git checkout master
git merge --no-ff release/v1.65

# 4. 打標籤
git tag -a v1.65 -m "Release version 1.65"

# 5. 合併回 develop
git checkout develop
git merge --no-ff release/v1.65

# 6. 刪除發布分支
git branch -d release/v1.65

# 7. 推送到遠程
git push origin master
git push origin develop
git push --tags
```

## 🚨 緊急修復流程

```bash
# 1. 從 master 創建修復分支
git checkout -b hotfix/critical-fix master

# 2. 修復問題
# ... 修改代碼 ...

# 3. 合併到 master
git checkout master
git merge --no-ff hotfix/critical-fix

# 4. 打標籤
git tag -a v1.64.1 -m "Hotfix version 1.64.1"

# 5. 合併回 develop
git checkout develop
git merge --no-ff hotfix/critical-fix

# 6. 刪除修復分支
git branch -d hotfix/critical-fix

# 7. 推送到遠程
git push origin master
git push origin develop
git push --tags
```

## 📋 版本號規則

採用語義化版本號：`MAJOR.MINOR.PATCH`

- **MAJOR** - 重大變更，不向後兼容
- **MINOR** - 新功能，向後兼容
- **PATCH** - 錯誤修復，向後兼容

### 範例：
- `v1.64.0` - 主版本
- `v1.64.1` - 修復版本
- `v1.65.0` - 新功能版本
- `v2.0.0` - 重大更新版本

## 🔍 查看版本信息

```bash
# 查看當前版本
git describe --tags

# 查看提交歷史
git log --oneline --graph --all

# 查看特定版本的變更
git show v1.64

# 比較兩個版本
git diff v1.63..v1.64

# 查看版本之間的提交
git log v1.63..v1.64 --oneline
```

## ⚠️ 注意事項

1. **永遠不要強制推送到主分支**
2. **在執行 reset 操作前先備份**
3. **使用 revert 而非 reset 來撤銷已推送的提交**
4. **定期備份重要分支**
5. **在合併前進行充分測試**

## 🆘 緊急恢復

如果意外丟失了提交：

```bash
# 查看所有操作歷史
git reflog

# 恢復到特定操作
git reset --hard HEAD@{n}

# 創建備份分支
git branch backup-recovery HEAD@{n}
``` 