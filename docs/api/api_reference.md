# API 參考文檔

本文檔包含所有服務層API的詳細說明。

**生成時間：** 2025-08-21 17:46:57
**API數量：** 84

## 目錄

- [AchievementService](#achievementservice)
- [ActivityService](#activityservice)
- [DocumentationService](#documentationservice)
- [EconomyService](#economyservice)
- [GovernmentService](#governmentservice)
- [MessageService](#messageservice)
- [MonitoringService](#monitoringservice)
- [RoleService](#roleservice)
- [WelcomeService](#welcomeservice)

## AchievementService

### 方法列表

#### `award_reward()`

發放單個獎勵

**參數：**

- `user_id` ('int, 必需): 使用者ID
- `guild_id` ('int, 必需): 伺服器ID
- `reward` (AchievementReward, 必需): 獎勵配置
- `achievement_id` (Optional[str], 可選)（預設：None）: 成就ID（用於記錄）

**返回：** Dict[str, Any]

發放結果

**範例：**

*使用 award_reward 方法*

```python
# 呼叫 award_reward 方法
result = await service.award_reward(
    user_id=...,
    guild_id=...,
    reward=...
)
print(f"操作成功：{result}")
```

---

#### `award_reward_with_fallback()`

帶降級處理的獎勵發放

**參數：**

- `user_id` ('int, 必需): 使用者ID
- `guild_id` ('int, 必需): 伺服器ID
- `reward` (AchievementReward, 必需): 獎勵配置

**返回：** Dict[str, Any]

發放結果（包含降級資訊）

**範例：**

*使用 award_reward_with_fallback 方法*

```python
# 呼叫 award_reward_with_fallback 方法
result = await service.award_reward_with_fallback(
    user_id=...,
    guild_id=...,
    reward=...
)
print(f"操作成功：{result}")
```

---

#### `batch_check_conditions()`

批量檢查條件（用於效能測試）

**參數：**

- `conditions` (List[services.achievement.models.TriggerCondition], 必需): 觸發條件列表
- `users_progress` (List[Dict[str, Any]], 必需): 使用者進度列表

**返回：** List[Dict[str, Any]]

檢查結果列表

**範例：**

*使用 batch_check_conditions 方法*

```python
# 呼叫 batch_check_conditions 方法
result = await service.batch_check_conditions(
    conditions=...,
    users_progress=...
)
print(f"操作成功：{result}")
```

---

#### `batch_update_progress()`

批量更新使用者進度

**參數：**

- `updates` (List[Dict[str, Any]], 必需): 更新資料列表，每個元素包含 user_id, achievement_id, progress

**返回：** 'bool

是否全部更新成功

**範例：**

*使用 batch_update_progress 方法*

```python
# 呼叫 batch_update_progress 方法
result = await service.batch_update_progress(
    updates=...
)
print(f"操作成功：{result}")
```

---

#### `complete_achievement()`

完成成就並發放獎勵

**參數：**

- `user_id` ('int, 必需): 使用者ID
- `achievement_id` ('str, 必需): 成就ID
- `rewards` (List[services.achievement.models.AchievementReward], 必需): 獎勵列表

**返回：** 'bool

是否處理成功

**範例：**

*使用 complete_achievement 方法*

```python
# 呼叫 complete_achievement 方法
result = await service.complete_achievement(
    user_id=...,
    achievement_id=...,
    rewards=...
)
print(f"操作成功：{result}")
```

---

#### `complete_achievement_with_rewards()`

帶事務的成就完成處理

**參數：**

- `user_id` ('int, 必需): 
- `achievement_id` ('str, 必需): 
- `rewards` (List[services.achievement.models.AchievementReward], 必需): 

**返回：** Any

返回 complete_achievement_with_rewards 的執行結果

**範例：**

*使用 complete_achievement_with_rewards 方法*

```python
# 呼叫 complete_achievement_with_rewards 方法
result = await service.complete_achievement_with_rewards(
    user_id=...,
    achievement_id=...,
    rewards=...
)
print(f"操作成功：{result}")
```

---

#### `create_achievement()`

建立新成就

**參數：**

- `achievement` (Achievement, 必需): 成就配置

**返回：** Achievement

建立的成就物件

**異常：**

- `ValidationError`: 當配置無效時
- `ServiceError`: 當建立失敗時

**範例：**

*使用 create_achievement 方法*

```python
# 呼叫 create_achievement 方法
result = await service.create_achievement(
    achievement=...
)
print(f"操作成功：{result}")
```

---

#### `delete_achievement()`

刪除成就

**參數：**

- `achievement_id` ('str, 必需): 成就ID

**返回：** 'bool

是否刪除成功

**範例：**

*使用 delete_achievement 方法*

```python
# 呼叫 delete_achievement 方法
result = await service.delete_achievement(
    achievement_id=...
)
print(f"操作成功：{result}")
```

---

#### `evaluate_compound_conditions()`

評估複合觸發條件

**參數：**

- `conditions` (List[services.achievement.models.TriggerCondition], 必需): 觸發條件列表
- `user_progress` (Dict[str, Any], 必需): 使用者進度資料
- `operator` ('str, 可選)（預設：AND）: 邏輯運算符 ("AND" 或 "OR")

**返回：** 'bool

是否滿足複合條件

**範例：**

*使用 evaluate_compound_conditions 方法*

```python
# 呼叫 evaluate_compound_conditions 方法
result = await service.evaluate_compound_conditions(
    conditions=...,
    user_progress=...
)
print(f"操作成功：{result}")
```

---

#### `evaluate_trigger_condition()`

評估觸發條件

**參數：**

- `condition` (TriggerCondition, 必需): 觸發條件
- `user_progress` (Dict[str, Any], 必需): 使用者進度資料

**返回：** 'bool

是否滿足條件

**範例：**

*使用 evaluate_trigger_condition 方法*

```python
# 呼叫 evaluate_trigger_condition 方法
result = await service.evaluate_trigger_condition(
    condition=...,
    user_progress=...
)
print(f"操作成功：{result}")
```

---

#### `get_achievement()`

根據ID獲取成就

**參數：**

- `achievement_id` ('str, 必需): 成就ID

**返回：** Optional[services.achievement.models.Achievement]

成就物件，如果不存在則返回 None

**範例：**

*使用 get_achievement 方法*

```python
# 呼叫 get_achievement 方法
result = await service.get_achievement(
    achievement_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_user_progress()`

獲取使用者成就進度

**參數：**

- `user_id` ('int, 必需): 使用者ID
- `achievement_id` ('str, 必需): 成就ID

**返回：** Optional[services.achievement.models.AchievementProgress]

進度物件，如果不存在則返回 None

**範例：**

*使用 get_user_progress 方法*

```python
# 呼叫 get_user_progress 方法
result = await service.get_user_progress(
    user_id=...,
    achievement_id=...
)
print(f"操作成功：{result}")
```

---

#### `list_guild_achievements()`

列出伺服器的成就

**參數：**

- `guild_id` ('int, 必需): 伺服器ID
- `status` (Optional[services.achievement.models.AchievementStatus], 可選)（預設：None）: 成就狀態篩選
- `achievement_type` (Optional[services.achievement.models.AchievementType], 可選)（預設：None）: 成就類型篩選

**返回：** List[services.achievement.models.Achievement]

成就列表

**範例：**

*使用 list_guild_achievements 方法*

```python
# 呼叫 list_guild_achievements 方法
result = await service.list_guild_achievements(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `list_user_achievements()`

列出使用者的成就進度

**參數：**

- `user_id` ('int, 必需): 使用者ID
- `guild_id` ('int, 必需): 伺服器ID
- `completed_only` ('bool, 可選)（預設：False）: 是否只返回已完成的成就

**返回：** List[Dict[str, Any]]

成就進度列表

**範例：**

*使用 list_user_achievements 方法*

```python
# 呼叫 list_user_achievements 方法
result = await service.list_user_achievements(
    user_id=...,
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `process_event_triggers()`

處理事件觸發，更新相關使用者的成就進度

**參數：**

- `event_data` (Dict[str, Any], 必需): 事件資料

**返回：** List[str]

觸發的成就ID列表

**範例：**

*使用 process_event_triggers 方法*

```python
# 呼叫 process_event_triggers 方法
result = await service.process_event_triggers(
    event_data=...
)
print(f"操作成功：{result}")
```

---

#### `register_custom_reward_type()`

註冊自訂獎勵類型

**參數：**

- `reward_type` ('str, 必需): 獎勵類型名稱
- `handler_func` (Callable, 必需): 處理函數 (user_id, guild_id, reward, achievement_id) -> None

**返回：** Any

返回 register_custom_reward_type 的執行結果

**範例：**

*使用 register_custom_reward_type 方法*

```python
# 呼叫 register_custom_reward_type 方法
result = await service.register_custom_reward_type(
    reward_type=...,
    handler_func=...
)
print(f"操作成功：{result}")
```

---

#### `register_custom_trigger_type()`

註冊自訂觸發類型

**參數：**

- `trigger_type` ('str, 必需): 觸發類型名稱
- `evaluator_func` (Callable, 必需): 評估函數 (progress_data, target_value, operator) -> bool

**返回：** Any

返回 register_custom_trigger_type 的執行結果

**範例：**

*使用 register_custom_trigger_type 方法*

```python
# 呼叫 register_custom_trigger_type 方法
result = await service.register_custom_trigger_type(
    trigger_type=...,
    evaluator_func=...
)
print(f"操作成功：{result}")
```

---

#### `update_achievement()`

更新成就配置

**參數：**

- `achievement` (Achievement, 必需): 更新後的成就配置

**返回：** Achievement

更新後的成就物件

**範例：**

*使用 update_achievement 方法*

```python
# 呼叫 update_achievement 方法
result = await service.update_achievement(
    achievement=...
)
print(f"操作成功：{result}")
```

---

#### `update_user_progress()`

更新使用者成就進度

**參數：**

- `user_id` ('int, 必需): 使用者ID
- `achievement_id` ('str, 必需): 成就ID
- `new_progress` (Dict[str, Any], 必需): 新的進度資料

**返回：** 'bool

是否更新成功

**範例：**

*使用 update_user_progress 方法*

```python
# 呼叫 update_user_progress 方法
result = await service.update_user_progress(
    user_id=...,
    achievement_id=...,
    new_progress=...
)
print(f"操作成功：{result}")
```

---

## ActivityService

### 方法列表

#### `generate_activity_image()`

生成活躍度進度條圖片

**參數：**

- `user_id` ('int, 必需): 用戶 ID
- `guild_id` ('int, 必需): 伺服器 ID
- `member` (Optional[discord.member.Member], 可選)（預設：None）: Discord 成員物件（用於顯示名稱）

**返回：** ActivityImage

活躍度圖片

**範例：**

*使用 generate_activity_image 方法*

```python
# 呼叫 generate_activity_image 方法
result = await service.generate_activity_image(
    user_id=...,
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `generate_daily_report()`

生成每日活躍度報告

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID

**返回：** Optional[services.activity.models.ActivityReport]

活躍度報告，如果沒有數據則返回 None

**範例：**

*使用 generate_daily_report 方法*

```python
# 呼叫 generate_daily_report 方法
result = await service.generate_daily_report(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_activity_score()`

獲取用戶當前活躍度分數

**參數：**

- `user_id` ('int, 必需): 用戶 ID
- `guild_id` ('int, 必需): 伺服器 ID

**返回：** 'float

當前活躍度分數

**範例：**

*使用 get_activity_score 方法*

```python
# 呼叫 get_activity_score 方法
result = await service.get_activity_score(
    user_id=...,
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_daily_leaderboard()`

獲取每日排行榜

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID
- `limit` ('int, 可選)（預設：10）: 限制數量

**返回：** List[services.activity.models.LeaderboardEntry]

排行榜列表

**範例：**

*使用 get_daily_leaderboard 方法*

```python
# 呼叫 get_daily_leaderboard 方法
result = await service.get_daily_leaderboard(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_monthly_stats()`

獲取月度統計

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID

**返回：** MonthlyStats

月度統計資料

**範例：**

*使用 get_monthly_stats 方法*

```python
# 呼叫 get_monthly_stats 方法
result = await service.get_monthly_stats(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_settings()`

獲取伺服器的活躍度設定

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID

**返回：** ActivitySettings

活躍度設定

**範例：**

*使用 get_settings 方法*

```python
# 呼叫 get_settings 方法
result = await service.get_settings(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `set_report_channel()`

設定自動播報頻道

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID
- `channel_id` ('int, 必需): 頻道 ID

**返回：** 'bool

是否設定成功

**範例：**

*使用 set_report_channel 方法*

```python
# 呼叫 set_report_channel 方法
result = await service.set_report_channel(
    guild_id=...,
    channel_id=...
)
print(f"操作成功：{result}")
```

---

#### `update_activity()`

更新用戶活躍度

**參數：**

- `user_id` ('int, 必需): 用戶 ID
- `guild_id` ('int, 必需): 伺服器 ID
- `message` (Optional[discord.message.Message], 可選)（預設：None）: Discord 訊息物件（可選）

**返回：** 'float

更新後的活躍度分數

**範例：**

*使用 update_activity 方法*

```python
# 呼叫 update_activity 方法
result = await service.update_activity(
    user_id=...,
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `update_setting()`

更新單一活躍度設定

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID
- `key` ('str, 必需): 設定鍵
- `value` (Any, 必需): 設定值

**返回：** 'bool

是否更新成功

**範例：**

*使用 update_setting 方法*

```python
# 呼叫 update_setting 方法
result = await service.update_setting(
    guild_id=...,
    key=...,
    value=...
)
print(f"操作成功：{result}")
```

---

## DocumentationService

### 方法列表

#### `generate_api_docs()`

生成API文檔

**參數：**

- `service_classes` (List[Type], 可選)（預設：None）: 要生成文檔的服務類別列表，None表示掃描所有服務

**返回：** 'bool

是否生成成功

---

#### `get_documentation_metrics()`

獲取文檔系統指標

**返回：** DocumentationMetrics

返回 get_documentation_metrics 的執行結果

---

#### `validate_api_documentation_quality()`

專門驗證API文檔品質

**參數：**

- `content` ('str, 必需): 

**返回：** Dict[str, Any]

品質評估結果，包含分數、問題清單和改善建議

**範例：**

*使用 validate_api_documentation_quality 方法*

```python
# 呼叫 validate_api_documentation_quality 方法
result = await service.validate_api_documentation_quality(
    content=...
)
print(f"操作成功：{result}")
```

---

#### `validate_documents()`

驗證文檔品質

**參數：**

- `document_ids` (List[str], 可選)（預設：None）: 要驗證的文檔ID列表，None表示驗證所有文檔

**返回：** List[services.documentation.models.DocumentValidationResult]

驗證結果列表

---

## EconomyService

### 方法列表

#### `create_account()`

建立新帳戶

**參數：**

- `guild_id` ('int, 必需): Discord伺服器ID
- `account_type` ('AccountType, 必需): 帳戶類型
- `user_id` (Optional[int], 可選)（預設：None）: 使用者ID（僅用於使用者帳戶）
- `initial_balance` ('float, 可選)（預設：0.0）: 初始餘額

**返回：** Account

建立的帳戶物件

**異常：**

- `ValidationError`: 當參數無效時
- `ServiceError`: 當帳戶已存在或建立失敗時

**範例：**

*建立使用者帳戶*

```python
# 為使用者建立個人帳戶
account = await economy_service.create_account(
    guild_id=123456789,
    account_type=AccountType.USER,
    user_id=987654321,
    initial_balance=100.0
)
print(f"帳戶建立成功：{account.id}")
```

---

#### `deposit()`

向帳戶存款（系統增加餘額）

**參數：**

- `account_id` ('str, 必需): 目標帳戶ID
- `amount` ('float, 必需): 存款金額
- `reason` (Optional[str], 可選)（預設：None）: 存款原因
- `created_by` (Optional[int], 可選)（預設：None）: 執行存款的使用者ID

**返回：** Transaction

交易記錄

**範例：**

*向帳戶存款*

```python
# 向指定帳戶存入資金
result = await economy_service.deposit(
    account_id="acc_123456789_987654321",
    amount=50.0,
    description="每日簽到獎勵"
)
print(f"存款成功，新餘額：{result.new_balance}")
```

---

#### `enable_audit()`

啟用或停用審計記錄

**參數：**

- `enabled` ('bool, 可選)（預設：True）: 

**返回：** Any

返回 enable_audit 的執行結果

---

#### `get_account()`

獲取帳戶資訊

**參數：**

- `account_id` ('str, 必需): 帳戶ID

**返回：** Optional[services.economy.models.Account]

帳戶物件，如果不存在則返回 None

**範例：**

*使用 get_account 方法*

```python
# 呼叫 get_account 方法
result = await service.get_account(
    account_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_audit_log()`

獲取審計日誌

**參數：**

- `guild_id` ('int, 必需): 伺服器ID
- `limit` ('int, 可選)（預設：100）: 記錄數量限制
- `operation` (Optional[str], 可選)（預設：None）: 操作類型篩選
- `user_id` (Optional[int], 可選)（預設：None）: 使用者ID篩選

**返回：** List[Dict[str, Any]]

審計日誌列表

**範例：**

*使用 get_audit_log 方法*

```python
# 呼叫 get_audit_log 方法
result = await service.get_audit_log(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_balance()`

獲取帳戶餘額

**參數：**

- `account_id` ('str, 必需): 帳戶ID

**返回：** 'float

帳戶餘額

**異常：**

- `ServiceError`: 當帳戶不存在時

**範例：**

*使用 get_balance 方法*

```python
# 呼叫 get_balance 方法
result = await service.get_balance(
    account_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_currency_config()`

獲取伺服器的貨幣配置

**參數：**

- `guild_id` ('int, 必需): Discord伺服器ID

**返回：** CurrencyConfig

貨幣配置物件

**範例：**

*使用 get_currency_config 方法*

```python
# 呼叫 get_currency_config 方法
result = await service.get_currency_config(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_economy_statistics()`

獲取經濟系統統計資料

**參數：**

- `guild_id` ('int, 必需): Discord伺服器ID

**返回：** Dict[str, Any]

統計資料字典

**範例：**

*使用 get_economy_statistics 方法*

```python
# 呼叫 get_economy_statistics 方法
result = await service.get_economy_statistics(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_guild_accounts()`

獲取伺服器的所有帳戶

**參數：**

- `guild_id` ('int, 必需): Discord伺服器ID
- `account_type` (Optional[services.economy.models.AccountType], 可選)（預設：None）: 帳戶類型篩選
- `include_inactive` ('bool, 可選)（預設：False）: 是否包含停用的帳戶

**返回：** List[services.economy.models.Account]

帳戶列表

**範例：**

*使用 get_guild_accounts 方法*

```python
# 呼叫 get_guild_accounts 方法
result = await service.get_guild_accounts(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_transaction_history()`

獲取帳戶交易記錄

**參數：**

- `account_id` ('str, 必需): 帳戶ID
- `limit` ('int, 可選)（預設：50）: 記錄數量限制
- `transaction_type` (Optional[services.economy.models.TransactionType], 可選)（預設：None）: 交易類型篩選

**返回：** List[services.economy.models.Transaction]

交易記錄列表

**範例：**

*使用 get_transaction_history 方法*

```python
# 呼叫 get_transaction_history 方法
result = await service.get_transaction_history(
    account_id=...
)
print(f"操作成功：{result}")
```

---

#### `set_currency_config()`

設定伺服器的貨幣配置

**參數：**

- `guild_id` ('int, 必需): Discord伺服器ID
- `currency_name` (Optional[str], 可選)（預設：None）: 貨幣名稱
- `currency_symbol` (Optional[str], 可選)（預設：None）: 貨幣符號
- `decimal_places` (Optional[int], 可選)（預設：None）: 小數位數
- `min_transfer_amount` (Optional[float], 可選)（預設：None）: 最小轉帳金額
- `max_transfer_amount` (Optional[float], 可選)（預設：None）: 最大轉帳金額
- `daily_transfer_limit` (Optional[float], 可選)（預設：None）: 每日轉帳限額
- `enable_negative_balance` (Optional[bool], 可選)（預設：None）: 是否允許負餘額
- `updated_by` (Optional[int], 可選)（預設：None）: 更新者使用者ID

**返回：** CurrencyConfig

更新後的貨幣配置

**範例：**

*使用 set_currency_config 方法*

```python
# 呼叫 set_currency_config 方法
result = await service.set_currency_config(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `transfer()`

執行帳戶間轉帳

**參數：**

- `from_account_id` ('str, 必需): 來源帳戶ID
- `to_account_id` ('str, 必需): 目標帳戶ID
- `amount` ('float, 必需): 轉帳金額
- `reason` (Optional[str], 可選)（預設：None）: 轉帳原因
- `created_by` (Optional[int], 可選)（預設：None）: 執行轉帳的使用者ID

**返回：** Transaction

交易記錄

**異常：**

- `ValidationError`: 當參數無效時
- `ServiceError`: 當轉帳失敗時

**範例：**

*帳戶間轉帳*

```python
# 在兩個帳戶間進行轉帳
transaction = await economy_service.transfer(
    from_account_id="acc_123456789_111111",
    to_account_id="acc_123456789_222222", 
    amount=25.0,
    description="轉帳給朋友"
)
print(f"轉帳成功，交易ID：{transaction.id}")
```

---

#### `withdraw()`

從帳戶提款（系統減少餘額）

**參數：**

- `account_id` ('str, 必需): 來源帳戶ID
- `amount` ('float, 必需): 提款金額
- `reason` (Optional[str], 可選)（預設：None）: 提款原因
- `created_by` (Optional[int], 可選)（預設：None）: 執行提款的使用者ID

**返回：** Transaction

交易記錄

**範例：**

*使用 withdraw 方法*

```python
# 呼叫 withdraw 方法
result = await service.withdraw(
    account_id=...,
    amount=...
)
print(f"操作成功：{result}")
```

---

## GovernmentService

### 方法列表

#### `create_department()`

建立新部門

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `department_data` (Dict[str, Any], 必需): 部門資料

**返回：** 'int

ValidationError: 資料無效時

**範例：**

*使用 create_department 方法*

```python
# 呼叫 create_department 方法
result = await service.create_department(
    guild=...,
    department_data=...
)
print(f"操作成功：{result}")
```

---

#### `delete_department()`

刪除部門

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `department_id` ('int, 必需): 部門ID

**返回：** 'bool

是否成功

**範例：**

*使用 delete_department 方法*

```python
# 呼叫 delete_department 方法
result = await service.delete_department(
    guild=...,
    department_id=...
)
print(f"操作成功：{result}")
```

---

#### `ensure_council_infrastructure()`

確保常任理事會基礎設施存在

**參數：**

- `guild` (Guild, 必需): Discord伺服器

**返回：** 'bool

是否成功

**範例：**

*使用 ensure_council_infrastructure 方法*

```python
# 呼叫 ensure_council_infrastructure 方法
result = await service.ensure_council_infrastructure(
    guild=...
)
print(f"操作成功：{result}")
```

---

#### `get_department_by_id()`

根據ID獲取部門資訊

**參數：**

- `department_id` ('int, 必需): 部門ID

**返回：** Optional[Dict[str, Any]]

部門資訊或None

**範例：**

*使用 get_department_by_id 方法*

```python
# 呼叫 get_department_by_id 方法
result = await service.get_department_by_id(
    department_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_department_registry()`

獲取伺服器的部門註冊表

**參數：**

- `guild_id` ('int, 必需): 伺服器ID

**返回：** List[Dict[str, Any]]

部門列表

**範例：**

*使用 get_department_registry 方法*

```python
# 呼叫 get_department_registry 方法
result = await service.get_department_registry(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `update_department()`

更新部門資訊

**參數：**

- `department_id` ('int, 必需): 部門ID
- `updates` (Dict[str, Any], 必需): 要更新的欄位

**返回：** 'bool

是否成功

**範例：**

*使用 update_department 方法*

```python
# 呼叫 update_department 方法
result = await service.update_department(
    department_id=...,
    updates=...
)
print(f"操作成功：{result}")
```

---

## MessageService

### 方法列表

#### `add_monitored_channel()`

添加監聽頻道

**參數：**

- `channel_id` ('int, 必需): 頻道 ID

**返回：** 'bool

是否添加成功

**範例：**

*使用 add_monitored_channel 方法*

```python
# 呼叫 add_monitored_channel 方法
result = await service.add_monitored_channel(
    channel_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_settings()`

獲取監聽設定

**返回：** MonitorSettings

監聽設定物件

---

#### `is_channel_monitored()`

檢查頻道是否被監聽

**參數：**

- `channel_id` ('int, 必需): 

**返回：** 'bool

返回 is_channel_monitored 的執行結果

**範例：**

*使用 is_channel_monitored 方法*

```python
# 呼叫 is_channel_monitored 方法
result = await service.is_channel_monitored(
    channel_id=...
)
print(f"操作成功：{result}")
```

---

#### `purge_old_messages()`

清理舊訊息

**參數：**

- `days` (Optional[int], 可選)（預設：None）: 保留天數，如果不提供則使用設定中的值

**返回：** 'int

清理的訊息數量

---

#### `refresh_monitored_channels()`

重新載入監聽頻道快取

**返回：** Any

返回 refresh_monitored_channels 的執行結果

---

#### `refresh_settings()`

重新載入設定快取

**返回：** Any

返回 refresh_settings 的執行結果

---

#### `remove_monitored_channel()`

移除監聽頻道

**參數：**

- `channel_id` ('int, 必需): 頻道 ID

**返回：** 'bool

是否移除成功

**範例：**

*使用 remove_monitored_channel 方法*

```python
# 呼叫 remove_monitored_channel 方法
result = await service.remove_monitored_channel(
    channel_id=...
)
print(f"操作成功：{result}")
```

---

#### `save_message()`

儲存訊息記錄

**參數：**

- `message` (Any, 必需): Discord 訊息物件

**返回：** 'bool

是否儲存成功

**範例：**

*使用 save_message 方法*

```python
# 呼叫 save_message 方法
result = await service.save_message(
    message=...
)
print(f"操作成功：{result}")
```

---

#### `search_messages()`

搜尋訊息

**參數：**

- `query` (SearchQuery, 必需): 搜尋查詢參數

**返回：** SearchResult

搜尋結果

**範例：**

*使用 search_messages 方法*

```python
# 呼叫 search_messages 方法
result = await service.search_messages(
    query=...
)
print(f"操作成功：{result}")
```

---

#### `update_setting()`

更新單一設定

**參數：**

- `key` ('str, 必需): 設定鍵
- `value` ('str, 必需): 設定值

**返回：** 'bool

是否更新成功

**範例：**

*使用 update_setting 方法*

```python
# 呼叫 update_setting 方法
result = await service.update_setting(
    key=...,
    value=...
)
print(f"操作成功：{result}")
```

---

## MonitoringService

### 方法列表

#### `cleanup_old_data()`

清理過期的監控數據

**返回：** Dict[str, Any]

返回 cleanup_old_data 的執行結果

---

#### `collect_all_performance_metrics()`

收集所有效能指標

**返回：** List[services.monitoring.models.PerformanceMetric]

返回 collect_all_performance_metrics 的執行結果

---

#### `get_health_history()`

獲取健康檢查歷史

**參數：**

- `component` (Optional[str], 可選)（預設：None）: 
- `hours` ('int, 可選)（預設：24）: 

**返回：** List[services.monitoring.models.HealthCheckResult]

返回 get_health_history 的執行結果

---

#### `get_performance_report()`

生成效能報告

**參數：**

- `start_date` (datetime, 必需): 
- `end_date` (datetime, 必需): 

**返回：** PerformanceReport

返回 get_performance_report 的執行結果

**範例：**

*使用 get_performance_report 方法*

```python
# 呼叫 get_performance_report 方法
result = await service.get_performance_report(
    start_date=...,
    end_date=...
)
print(f"操作成功：{result}")
```

---

#### `perform_full_health_check()`

執行完整的系統健康檢查

**返回：** SystemHealth

返回 perform_full_health_check 的執行結果

---

#### `start_monitoring()`

開始監控

**返回：** Any

返回 start_monitoring 的執行結果

---

#### `stop_monitoring()`

停止監控

**返回：** Any

返回 stop_monitoring 的執行結果

---

#### `update_config()`

更新監控配置

**參數：**

- `config` (MonitoringConfig, 必需): 

**返回：** Any

返回 update_config 的執行結果

**範例：**

*使用 update_config 方法*

```python
# 呼叫 update_config 方法
result = await service.update_config(
    config=...
)
print(f"操作成功：{result}")
```

---

## RoleService

### 方法列表

#### `assign_role_to_user()`

為使用者指派身分組

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `user` (Member, 必需): 使用者
- `role` (Role, 必需): 身分組
- `reason` (Optional[str], 可選)（預設：None）: 指派原因

**返回：** 'bool

是否成功

**範例：**

*使用 assign_role_to_user 方法*

```python
# 呼叫 assign_role_to_user 方法
result = await service.assign_role_to_user(
    guild=...,
    user=...,
    role=...
)
print(f"操作成功：{result}")
```

---

#### `cleanup_department_roles()`

清理部門相關身分組

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `department_name` ('str, 必需): 部門名稱

**返回：** 'bool

是否成功

**範例：**

*使用 cleanup_department_roles 方法*

```python
# 呼叫 cleanup_department_roles 方法
result = await service.cleanup_department_roles(
    guild=...,
    department_name=...
)
print(f"操作成功：{result}")
```

---

#### `create_department_roles()`

建立部門相關身分組

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `department_data` (Dict[str, Any], 必需): 部門資料

**返回：** Dict[str, discord.role.Role]

包含部門身分組的字典

**範例：**

*使用 create_department_roles 方法*

```python
# 呼叫 create_department_roles 方法
result = await service.create_department_roles(
    guild=...,
    department_data=...
)
print(f"操作成功：{result}")
```

---

#### `create_role_if_not_exists()`

建立身分組（如果不存在）

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `name` ('str, 必需): 身分組名稱
- `kwargs` (Any, 必需): 

**返回：** Role

ServiceError: 建立失敗時

**範例：**

*使用 create_role_if_not_exists 方法*

```python
# 呼叫 create_role_if_not_exists 方法
result = await service.create_role_if_not_exists(
    guild=...,
    name=...,
    kwargs=...
)
print(f"操作成功：{result}")
```

---

#### `delete_role()`

刪除身分組

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `role` (Role, 必需): 要刪除的身分組
- `reason` (Optional[str], 可選)（預設：None）: 刪除原因

**返回：** 'bool

是否成功

**範例：**

*使用 delete_role 方法*

```python
# 呼叫 delete_role 方法
result = await service.delete_role(
    guild=...,
    role=...
)
print(f"操作成功：{result}")
```

---

#### `ensure_council_role()`

確保常任理事身分組存在

**參數：**

- `guild` (Guild, 必需): Discord伺服器

**返回：** Role

常任理事身分組

**範例：**

*使用 ensure_council_role 方法*

```python
# 呼叫 ensure_council_role 方法
result = await service.ensure_council_role(
    guild=...
)
print(f"操作成功：{result}")
```

---

#### `get_role_by_name()`

根據名稱獲取身分組

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `name` ('str, 必需): 身分組名稱

**返回：** Optional[discord.role.Role]

身分組物件或None

**範例：**

*使用 get_role_by_name 方法*

```python
# 呼叫 get_role_by_name 方法
result = await service.get_role_by_name(
    guild=...,
    name=...
)
print(f"操作成功：{result}")
```

---

#### `list_department_roles()`

獲取部門相關的所有身分組

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `department_name` ('str, 必需): 部門名稱

**返回：** List[discord.role.Role]

部門身分組列表

**範例：**

*使用 list_department_roles 方法*

```python
# 呼叫 list_department_roles 方法
result = await service.list_department_roles(
    guild=...,
    department_name=...
)
print(f"操作成功：{result}")
```

---

#### `remove_role_from_user()`

移除使用者的身分組

**參數：**

- `guild` (Guild, 必需): Discord伺服器
- `user` (Member, 必需): 使用者
- `role` (Role, 必需): 身分組
- `reason` (Optional[str], 可選)（預設：None）: 移除原因

**返回：** 'bool

是否成功

**範例：**

*使用 remove_role_from_user 方法*

```python
# 呼叫 remove_role_from_user 方法
result = await service.remove_role_from_user(
    guild=...,
    user=...,
    role=...
)
print(f"操作成功：{result}")
```

---

## WelcomeService

### 方法列表

#### `clear_cache()`

清除快取

**參數：**

- `guild_id` (Optional[int], 可選)（預設：None）: 伺服器 ID，如果為 None 則清除所有快取

**返回：** Any

返回 clear_cache 的執行結果

---

#### `generate_welcome_image()`

生成歡迎圖片

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID
- `member` (Optional[discord.member.Member], 可選)（預設：None）: 成員物件
- `force_refresh` ('bool, 可選)（預設：False）: 強制重新生成

**返回：** WelcomeImage

歡迎圖片

**範例：**

*使用 generate_welcome_image 方法*

```python
# 呼叫 generate_welcome_image 方法
result = await service.generate_welcome_image(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `get_settings()`

獲取伺服器的歡迎設定

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID

**返回：** WelcomeSettings

歡迎設定

**範例：**

*使用 get_settings 方法*

```python
# 呼叫 get_settings 方法
result = await service.get_settings(
    guild_id=...
)
print(f"操作成功：{result}")
```

---

#### `process_member_join()`

處理成員加入事件

**參數：**

- `member` (Member, 必需): 加入的成員

**返回：** 'bool

是否處理成功

**範例：**

*使用 process_member_join 方法*

```python
# 呼叫 process_member_join 方法
result = await service.process_member_join(
    member=...
)
print(f"操作成功：{result}")
```

---

#### `update_background()`

更新歡迎背景圖片

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID
- `image_path` ('str, 必需): 圖片路徑

**返回：** 'bool

是否更新成功

**範例：**

*使用 update_background 方法*

```python
# 呼叫 update_background 方法
result = await service.update_background(
    guild_id=...,
    image_path=...
)
print(f"操作成功：{result}")
```

---

#### `update_setting()`

更新單一歡迎設定

**參數：**

- `guild_id` ('int, 必需): 伺服器 ID
- `key` ('str, 必需): 設定鍵
- `value` (Any, 必需): 設定值

**返回：** 'bool

是否更新成功

**範例：**

*使用 update_setting 方法*

```python
# 呼叫 update_setting 方法
result = await service.update_setting(
    guild_id=...,
    key=...,
    value=...
)
print(f"操作成功：{result}")
```

---
