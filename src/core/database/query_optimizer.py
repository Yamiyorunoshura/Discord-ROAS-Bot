"""
子機器人資料庫查詢優化器
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供專門的查詢優化功能：
- 智能索引策略管理
- 查詢效能分析和優化建議
- 自適應查詢計劃選擇
- 慢查詢檢測和記錄
- 查詢統計和效能監控
- 動態索引建議系統
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import json
import sqlite3

# 核心依賴
from core.base_service import BaseService
from core.database_manager import DatabaseManager

logger = logging.getLogger('core.database.query_optimizer')


class QueryType(Enum):
    """查詢類型"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    COUNT = "COUNT"
    JOIN = "JOIN"


class QueryPriority(Enum):
    """查詢優先級"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class IndexType(Enum):
    """索引類型"""
    BTREE = "btree"
    HASH = "hash"
    PARTIAL = "partial"
    UNIQUE = "unique"
    COMPOSITE = "composite"


@dataclass
class QueryMetrics:
    """查詢指標"""
    query_hash: str
    sql_template: str
    query_type: QueryType
    execution_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    last_executed: Optional[datetime] = None
    slow_query_count: int = 0
    error_count: int = 0
    rows_affected: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    
    def update_timing(self, execution_time: float, rows: int = 0, cached: bool = False):
        """更新執行時間統計"""
        self.execution_count += 1
        self.total_time += execution_time
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)
        self.avg_time = self.total_time / self.execution_count
        self.last_executed = datetime.now()
        self.rows_affected += rows
        
        if cached:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def mark_slow_query(self):
        """標記為慢查詢"""
        self.slow_query_count += 1
    
    def mark_error(self):
        """標記查詢錯誤"""
        self.error_count += 1


@dataclass
class IndexRecommendation:
    """索引建議"""
    table_name: str
    columns: List[str]
    index_type: IndexType
    reason: str
    expected_improvement: float  # 預期效能提升百分比
    creation_sql: str
    drop_sql: str
    priority: QueryPriority
    estimated_size: int = 0  # 預估索引大小（KB）
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'table_name': self.table_name,
            'columns': self.columns,
            'index_type': self.index_type.value,
            'reason': self.reason,
            'expected_improvement': self.expected_improvement,
            'creation_sql': self.creation_sql,
            'drop_sql': self.drop_sql,
            'priority': self.priority.value,
            'estimated_size': self.estimated_size
        }


@dataclass
class QueryPlan:
    """查詢計劃"""
    query_hash: str
    original_sql: str
    optimized_sql: str
    explain_plan: str
    cost_estimate: float
    rows_estimate: int
    indexes_used: List[str]
    optimization_applied: List[str]
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'query_hash': self.query_hash,
            'original_sql': self.original_sql,
            'optimized_sql': self.optimized_sql,
            'explain_plan': self.explain_plan,
            'cost_estimate': self.cost_estimate,
            'rows_estimate': self.rows_estimate,
            'indexes_used': self.indexes_used,
            'optimization_applied': self.optimization_applied,
            'created_at': self.created_at.isoformat()
        }


class QueryPatternAnalyzer:
    """查詢模式分析器"""
    
    def __init__(self):
        self.patterns = defaultdict(int)
        self.frequent_columns = defaultdict(int)
        self.join_patterns = defaultdict(int)
        self.where_conditions = defaultdict(int)
        
    def analyze_query(self, sql: str) -> Dict[str, Any]:
        """
        分析查詢模式
        
        Args:
            sql: SQL查詢語句
            
        Returns:
            分析結果
        """
        sql_upper = sql.upper().strip()
        
        # 基本查詢類型檢測
        query_type = self._detect_query_type(sql_upper)
        
        # 提取表名
        tables = self._extract_tables(sql_upper)
        
        # 提取列名
        columns = self._extract_columns(sql_upper)
        
        # 提取WHERE條件
        where_conditions = self._extract_where_conditions(sql_upper)
        
        # 檢測JOIN模式
        joins = self._extract_joins(sql_upper)
        
        # 檢測ORDER BY
        order_by = self._extract_order_by(sql_upper)
        
        # 檢測GROUP BY
        group_by = self._extract_group_by(sql_upper)
        
        return {
            'query_type': query_type,
            'tables': tables,
            'columns': columns,
            'where_conditions': where_conditions,
            'joins': joins,
            'order_by': order_by,
            'group_by': group_by
        }
    
    def _detect_query_type(self, sql: str) -> QueryType:
        """檢測查詢類型"""
        if sql.startswith('SELECT'):
            if 'COUNT(' in sql:
                return QueryType.COUNT
            elif 'JOIN' in sql:
                return QueryType.JOIN
            else:
                return QueryType.SELECT
        elif sql.startswith('INSERT'):
            return QueryType.INSERT
        elif sql.startswith('UPDATE'):
            return QueryType.UPDATE
        elif sql.startswith('DELETE'):
            return QueryType.DELETE
        else:
            return QueryType.SELECT
    
    def _extract_tables(self, sql: str) -> List[str]:
        """提取表名"""
        tables = []
        
        # FROM子句
        if ' FROM ' in sql:
            from_part = sql.split(' FROM ')[1]
            from_part = from_part.split(' WHERE ')[0].split(' ORDER BY ')[0].split(' GROUP BY ')[0]
            
            # 處理JOIN
            parts = from_part.split(' JOIN ')
            for part in parts:
                table_name = part.split(' ')[0].strip()
                if table_name and not table_name.upper() in ['INNER', 'LEFT', 'RIGHT', 'FULL', 'ON']:
                    tables.append(table_name.lower())
        
        return tables
    
    def _extract_columns(self, sql: str) -> List[str]:
        """提取列名"""
        columns = []
        
        # SELECT子句
        if sql.startswith('SELECT'):
            select_part = sql.split('SELECT')[1].split(' FROM ')[0]
            if select_part.strip() != '*':
                # 簡單解析，實際實現需要更複雜的解析邏輯
                col_parts = select_part.split(',')
                for col in col_parts:
                    col = col.strip()
                    if ' AS ' in col:
                        col = col.split(' AS ')[0].strip()
                    columns.append(col.lower())
        
        return columns
    
    def _extract_where_conditions(self, sql: str) -> List[str]:
        """提取WHERE條件"""
        conditions = []
        
        if ' WHERE ' in sql:
            where_part = sql.split(' WHERE ')[1]
            where_part = where_part.split(' ORDER BY ')[0].split(' GROUP BY ')[0]
            
            # 簡單解析WHERE條件
            # 實際實現需要更複雜的解析邏輯來處理AND/OR/括號等
            parts = where_part.replace(' AND ', '|||').replace(' OR ', '|||').split('|||')
            for part in parts:
                condition = part.strip()
                if '=' in condition:
                    column = condition.split('=')[0].strip()
                    conditions.append(f"{column} = ?")
                elif ' IN ' in condition:
                    column = condition.split(' IN ')[0].strip()
                    conditions.append(f"{column} IN (?)")
                elif ' LIKE ' in condition:
                    column = condition.split(' LIKE ')[0].strip()
                    conditions.append(f"{column} LIKE ?")
        
        return conditions
    
    def _extract_joins(self, sql: str) -> List[str]:
        """提取JOIN模式"""
        joins = []
        
        join_keywords = [' INNER JOIN ', ' LEFT JOIN ', ' RIGHT JOIN ', ' FULL JOIN ', ' JOIN ']
        for keyword in join_keywords:
            if keyword in sql:
                parts = sql.split(keyword)
                for i in range(1, len(parts)):
                    join_info = parts[i].split(' ON ')[0].strip()
                    joins.append(f"{keyword.strip()} {join_info}")
        
        return joins
    
    def _extract_order_by(self, sql: str) -> List[str]:
        """提取ORDER BY"""
        if ' ORDER BY ' in sql:
            order_part = sql.split(' ORDER BY ')[1]
            order_part = order_part.split(' LIMIT ')[0].split(' OFFSET ')[0]
            
            columns = []
            for col in order_part.split(','):
                col = col.strip()
                columns.append(col.lower())
            
            return columns
        
        return []
    
    def _extract_group_by(self, sql: str) -> List[str]:
        """提取GROUP BY"""
        if ' GROUP BY ' in sql:
            group_part = sql.split(' GROUP BY ')[1]
            group_part = group_part.split(' HAVING ')[0].split(' ORDER BY ')[0]
            
            columns = []
            for col in group_part.split(','):
                col = col.strip()
                columns.append(col.lower())
            
            return columns
        
        return []


class QueryOptimizer(BaseService):
    """
    查詢優化器
    
    提供智能查詢分析、索引建議、效能監控等功能
    """
    
    def __init__(
        self,
        slow_query_threshold: float = 1.0,  # 慢查詢閾值（秒）
        enable_auto_index: bool = False,     # 是否啟用自動索引創建
        max_query_history: int = 10000       # 最大查詢歷史記錄數
    ):
        """
        初始化查詢優化器
        
        Args:
            slow_query_threshold: 慢查詢閾值（秒）
            enable_auto_index: 是否啟用自動索引創建
            max_query_history: 最大查詢歷史記錄數
        """
        super().__init__("QueryOptimizer")
        
        self.slow_query_threshold = slow_query_threshold
        self.enable_auto_index = enable_auto_index
        self.max_query_history = max_query_history
        
        # 查詢統計
        self.query_metrics: Dict[str, QueryMetrics] = {}
        
        # 查詢計劃快取
        self.query_plans: Dict[str, QueryPlan] = {}
        
        # 模式分析器
        self.pattern_analyzer = QueryPatternAnalyzer()
        
        # 索引建議
        self.index_recommendations: List[IndexRecommendation] = []
        
        # 慢查詢記錄
        self.slow_queries: deque = deque(maxlen=1000)
        
        # 現有索引追蹤
        self.existing_indexes: Dict[str, List[str]] = {}
        
        # 效能統計
        self._performance_stats = {
            'total_queries': 0,
            'slow_queries': 0,
            'optimization_applied': 0,
            'index_recommendations': 0,
            'avg_response_time': 0.0,
            'cache_hit_rate': 0.0
        }
    
    async def _initialize(self) -> bool:
        """初始化查詢優化器"""
        try:
            self.logger.info("查詢優化器初始化中...")
            
            # 掃描現有索引
            await self._scan_existing_indexes()
            
            # 載入歷史查詢統計
            await self._load_query_statistics()
            
            self.logger.info("查詢優化器初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"查詢優化器初始化失敗: {e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            # 保存查詢統計
            await self._save_query_statistics()
            
            self.logger.info("查詢優化器清理完成")
        except Exception as e:
            self.logger.error(f"清理查詢優化器時發生錯誤: {e}")
    
    async def _validate_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """驗證權限"""
        return True  # 查詢優化通常不需要特殊權限
    
    async def analyze_query(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        execution_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        分析查詢並提供優化建議
        
        Args:
            sql: SQL查詢語句
            params: 查詢參數
            execution_time: 執行時間（秒）
            
        Returns:
            分析結果和優化建議
        """
        try:
            # 生成查詢哈希
            query_hash = self._generate_query_hash(sql)
            
            # 分析查詢模式
            pattern_analysis = self.pattern_analyzer.analyze_query(sql)
            
            # 更新或創建查詢指標
            if query_hash not in self.query_metrics:
                self.query_metrics[query_hash] = QueryMetrics(
                    query_hash=query_hash,
                    sql_template=self._normalize_sql(sql),
                    query_type=pattern_analysis['query_type']
                )
            
            metrics = self.query_metrics[query_hash]
            
            # 更新執行統計
            if execution_time is not None:
                metrics.update_timing(execution_time)
                
                # 檢查是否為慢查詢
                if execution_time > self.slow_query_threshold:
                    metrics.mark_slow_query()
                    await self._record_slow_query(sql, execution_time, pattern_analysis)
            
            # 生成優化建議
            optimization_suggestions = await self._generate_optimization_suggestions(
                sql, pattern_analysis, metrics
            )
            
            # 檢查索引建議
            index_suggestions = await self._generate_index_suggestions(pattern_analysis)
            
            # 更新統計
            self._performance_stats['total_queries'] += 1
            
            return {
                'query_hash': query_hash,
                'pattern_analysis': pattern_analysis,
                'metrics': asdict(metrics),
                'optimization_suggestions': optimization_suggestions,
                'index_suggestions': [suggestion.to_dict() for suggestion in index_suggestions],
                'is_slow_query': execution_time and execution_time > self.slow_query_threshold,
                'performance_impact': self._calculate_performance_impact(metrics)
            }
            
        except Exception as e:
            self.logger.error(f"查詢分析失敗: {e}")
            return {'error': str(e)}
    
    async def optimize_query(self, sql: str) -> Dict[str, Any]:
        """
        優化查詢語句
        
        Args:
            sql: 原始SQL查詢
            
        Returns:
            優化結果
        """
        try:
            query_hash = self._generate_query_hash(sql)
            
            # 檢查是否已有優化計劃
            if query_hash in self.query_plans:
                plan = self.query_plans[query_hash]
                return {
                    'optimized': True,
                    'original_sql': sql,
                    'optimized_sql': plan.optimized_sql,
                    'optimization_applied': plan.optimization_applied,
                    'from_cache': True
                }
            
            # 分析查詢
            pattern_analysis = self.pattern_analyzer.analyze_query(sql)
            
            # 應用優化規則
            optimized_sql, optimizations = await self._apply_optimization_rules(sql, pattern_analysis)
            
            # 獲取執行計劃
            explain_plan = await self._get_explain_plan(optimized_sql)
            
            # 創建查詢計劃
            plan = QueryPlan(
                query_hash=query_hash,
                original_sql=sql,
                optimized_sql=optimized_sql,
                explain_plan=explain_plan,
                cost_estimate=0.0,  # SQLite不提供成本估算
                rows_estimate=0,
                indexes_used=self._extract_indexes_from_plan(explain_plan),
                optimization_applied=optimizations,
                created_at=datetime.now()
            )
            
            # 快取查詢計劃
            self.query_plans[query_hash] = plan
            
            # 更新統計
            self._performance_stats['optimization_applied'] += 1
            
            return {
                'optimized': len(optimizations) > 0,
                'original_sql': sql,
                'optimized_sql': optimized_sql,
                'optimization_applied': optimizations,
                'explain_plan': explain_plan,
                'from_cache': False
            }
            
        except Exception as e:
            self.logger.error(f"查詢優化失敗: {e}")
            return {
                'optimized': False,
                'error': str(e),
                'original_sql': sql,
                'optimized_sql': sql
            }
    
    async def create_recommended_indexes(self, max_indexes: int = 5) -> Dict[str, Any]:
        """
        創建推薦的索引
        
        Args:
            max_indexes: 最大創建索引數量
            
        Returns:
            索引創建結果
        """
        try:
            if not self.enable_auto_index:
                return {
                    'success': False,
                    'error': '自動索引創建未啟用'
                }
            
            # 獲取高優先級索引建議
            high_priority_indexes = [
                rec for rec in self.index_recommendations
                if rec.priority in [QueryPriority.HIGH, QueryPriority.CRITICAL]
            ][:max_indexes]
            
            results = []
            db_manager = self.get_dependency("database_manager")
            
            for recommendation in high_priority_indexes:
                try:
                    # 檢查索引是否已存在
                    if self._index_exists(recommendation.table_name, recommendation.columns):
                        results.append({
                            'table': recommendation.table_name,
                            'columns': recommendation.columns,
                            'status': 'already_exists',
                            'sql': recommendation.creation_sql
                        })
                        continue
                    
                    # 創建索引
                    await db_manager.execute(recommendation.creation_sql)
                    
                    # 更新現有索引記錄
                    if recommendation.table_name not in self.existing_indexes:
                        self.existing_indexes[recommendation.table_name] = []
                    self.existing_indexes[recommendation.table_name].append(
                        f"idx_{'_'.join(recommendation.columns)}"
                    )
                    
                    results.append({
                        'table': recommendation.table_name,
                        'columns': recommendation.columns,
                        'status': 'created',
                        'sql': recommendation.creation_sql,
                        'expected_improvement': recommendation.expected_improvement
                    })
                    
                    self.logger.info(f"創建索引: {recommendation.creation_sql}")
                    
                except Exception as e:
                    results.append({
                        'table': recommendation.table_name,
                        'columns': recommendation.columns,
                        'status': 'failed',
                        'error': str(e),
                        'sql': recommendation.creation_sql
                    })
            
            return {
                'success': True,
                'indexes_processed': len(results),
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"創建推薦索引失敗: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_slow_queries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        獲取慢查詢記錄
        
        Args:
            limit: 返回記錄數量限制
            
        Returns:
            慢查詢列表
        """
        return list(self.slow_queries)[-limit:]
    
    def get_query_statistics(self) -> Dict[str, Any]:
        """獲取查詢統計資訊"""
        # 計算統計數據
        total_queries = len(self.query_metrics)
        slow_queries = sum(1 for m in self.query_metrics.values() if m.slow_query_count > 0)
        
        if total_queries > 0:
            avg_response_time = sum(m.avg_time for m in self.query_metrics.values()) / total_queries
            total_cache_hits = sum(m.cache_hits for m in self.query_metrics.values())
            total_cache_attempts = sum(m.cache_hits + m.cache_misses for m in self.query_metrics.values())
            cache_hit_rate = total_cache_hits / max(total_cache_attempts, 1) * 100
        else:
            avg_response_time = 0.0
            cache_hit_rate = 0.0
        
        return {
            'total_unique_queries': total_queries,
            'slow_queries_count': slow_queries,
            'avg_response_time': avg_response_time,
            'cache_hit_rate': cache_hit_rate,
            'index_recommendations': len(self.index_recommendations),
            'query_plans_cached': len(self.query_plans),
            'existing_indexes': dict(self.existing_indexes),
            'performance_stats': self._performance_stats.copy()
        }
    
    def get_index_recommendations(self, priority: Optional[QueryPriority] = None) -> List[Dict[str, Any]]:
        """
        獲取索引建議
        
        Args:
            priority: 優先級過濾
            
        Returns:
            索引建議列表
        """
        recommendations = self.index_recommendations
        
        if priority:
            recommendations = [r for r in recommendations if r.priority == priority]
        
        return [r.to_dict() for r in recommendations]
    
    # 私有方法
    
    def _generate_query_hash(self, sql: str) -> str:
        """生成查詢哈希"""
        import hashlib
        normalized_sql = self._normalize_sql(sql)
        return hashlib.md5(normalized_sql.encode()).hexdigest()[:16]
    
    def _normalize_sql(self, sql: str) -> str:
        """正規化SQL語句（移除參數值等）"""
        # 簡單的正規化，實際實現需要更複雜的邏輯
        normalized = sql.strip().upper()
        
        # 替換數字和字符串字面值
        import re
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        normalized = re.sub(r'"[^"]*"', '"?"', normalized)
        
        return normalized
    
    async def _scan_existing_indexes(self):
        """掃描現有索引"""
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                return
            
            # 獲取所有索引
            indexes = await db_manager.fetchall(
                "SELECT name, sql, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
            
            for index in indexes:
                table_name = index['tbl_name']
                index_name = index['name']
                
                if table_name not in self.existing_indexes:
                    self.existing_indexes[table_name] = []
                
                self.existing_indexes[table_name].append(index_name)
            
            self.logger.debug(f"掃描到現有索引: {dict(self.existing_indexes)}")
            
        except Exception as e:
            self.logger.warning(f"掃描現有索引失敗: {e}")
    
    async def _load_query_statistics(self):
        """載入查詢統計資料"""
        # 這裡可以實現從持久化存儲載入統計資料
        pass
    
    async def _save_query_statistics(self):
        """保存查詢統計資料"""
        # 這裡可以實現保存統計資料到持久化存儲
        pass
    
    async def _record_slow_query(self, sql: str, execution_time: float, pattern_analysis: Dict[str, Any]):
        """記錄慢查詢"""
        slow_query_record = {
            'sql': sql,
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
            'pattern_analysis': pattern_analysis,
            'threshold': self.slow_query_threshold
        }
        
        self.slow_queries.append(slow_query_record)
        self._performance_stats['slow_queries'] += 1
        
        self.logger.warning(f"慢查詢記錄: {execution_time:.3f}s - {sql[:100]}...")
    
    async def _generate_optimization_suggestions(
        self,
        sql: str,
        pattern_analysis: Dict[str, Any],
        metrics: QueryMetrics
    ) -> List[str]:
        """生成優化建議"""
        suggestions = []
        
        # 基於查詢模式的建議
        if pattern_analysis['query_type'] == QueryType.SELECT:
            if not pattern_analysis['columns'] or '*' in sql:
                suggestions.append("避免使用 SELECT *，明確指定需要的欄位")
        
        # 基於WHERE條件的建議
        if pattern_analysis['where_conditions']:
            for condition in pattern_analysis['where_conditions']:
                if 'LIKE' in condition and condition.endswith('LIKE ?'):
                    suggestions.append(f"考慮為 {condition} 創建全文索引")
        
        # 基於JOIN的建議
        if pattern_analysis['joins']:
            suggestions.append("檢查JOIN條件是否有適當的索引")
        
        # 基於效能指標的建議
        if metrics.avg_time > self.slow_query_threshold:
            suggestions.append("查詢平均執行時間過長，考慮優化或添加索引")
        
        if metrics.cache_misses > metrics.cache_hits * 2:
            suggestions.append("快取命中率偏低，檢查查詢是否可以優化")
        
        return suggestions
    
    async def _generate_index_suggestions(self, pattern_analysis: Dict[str, Any]) -> List[IndexRecommendation]:
        """生成索引建議"""
        suggestions = []
        
        # 基於WHERE條件生成索引建議
        for table in pattern_analysis['tables']:
            for condition in pattern_analysis['where_conditions']:
                # 簡單解析條件獲取欄位名
                column = condition.split(' ')[0].lower()
                
                # 檢查是否已有此索引
                if not self._index_exists(table, [column]):
                    suggestion = IndexRecommendation(
                        table_name=table,
                        columns=[column],
                        index_type=IndexType.BTREE,
                        reason=f"WHERE條件頻繁使用 {column}",
                        expected_improvement=25.0,  # 預期25%效能提升
                        creation_sql=f"CREATE INDEX idx_{table}_{column} ON {table}({column})",
                        drop_sql=f"DROP INDEX idx_{table}_{column}",
                        priority=QueryPriority.NORMAL
                    )
                    suggestions.append(suggestion)
        
        # 基於ORDER BY生成索引建議
        for table in pattern_analysis['tables']:
            if pattern_analysis['order_by']:
                order_columns = [col.split(' ')[0].lower() for col in pattern_analysis['order_by']]
                if not self._index_exists(table, order_columns):
                    suggestion = IndexRecommendation(
                        table_name=table,
                        columns=order_columns,
                        index_type=IndexType.BTREE,
                        reason=f"ORDER BY頻繁使用 {', '.join(order_columns)}",
                        expected_improvement=30.0,
                        creation_sql=f"CREATE INDEX idx_{table}_{'_'.join(order_columns)} ON {table}({', '.join(order_columns)})",
                        drop_sql=f"DROP INDEX idx_{table}_{'_'.join(order_columns)}",
                        priority=QueryPriority.HIGH
                    )
                    suggestions.append(suggestion)
        
        # 將新建議加入到建議列表中
        for suggestion in suggestions:
            if not any(
                existing.table_name == suggestion.table_name and
                existing.columns == suggestion.columns
                for existing in self.index_recommendations
            ):
                self.index_recommendations.append(suggestion)
                self._performance_stats['index_recommendations'] += 1
        
        return suggestions
    
    def _index_exists(self, table_name: str, columns: List[str]) -> bool:
        """檢查索引是否存在"""
        if table_name not in self.existing_indexes:
            return False
        
        # 簡單檢查，實際實現需要更精確的比對
        index_name_pattern = f"idx_{table_name}_{'_'.join(columns)}"
        return any(index_name_pattern in idx_name for idx_name in self.existing_indexes[table_name])
    
    async def _apply_optimization_rules(self, sql: str, pattern_analysis: Dict[str, Any]) -> Tuple[str, List[str]]:
        """應用優化規則"""
        optimized_sql = sql
        optimizations = []
        
        # 規則1: 移除不必要的子查詢
        # 這裡是簡化的示例，實際實現需要複雜的SQL解析
        
        # 規則2: 優化JOIN順序
        # 實際實現需要基於表大小和統計資訊
        
        # 規則3: 添加LIMIT子句（如果適用）
        if pattern_analysis['query_type'] == QueryType.SELECT and 'LIMIT' not in sql.upper():
            if self._should_add_limit(pattern_analysis):
                optimized_sql += " LIMIT 1000"
                optimizations.append("添加LIMIT子句防止大量結果集")
        
        return optimized_sql, optimizations
    
    def _should_add_limit(self, pattern_analysis: Dict[str, Any]) -> bool:
        """判斷是否應該添加LIMIT"""
        # 簡單規則：如果沒有WHERE條件且沒有聚合函數，建議添加LIMIT
        return (not pattern_analysis['where_conditions'] and 
                not pattern_analysis['group_by'] and
                pattern_analysis['query_type'] == QueryType.SELECT)
    
    async def _get_explain_plan(self, sql: str) -> str:
        """獲取查詢執行計劃"""
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                return "無法獲取執行計劃"
            
            explain_sql = f"EXPLAIN QUERY PLAN {sql}"
            results = await db_manager.fetchall(explain_sql)
            
            plan_lines = []
            for row in results:
                plan_lines.append(f"{row.get('id', '')}: {row.get('detail', '')}")
            
            return "\n".join(plan_lines)
            
        except Exception as e:
            return f"獲取執行計劃失敗: {str(e)}"
    
    def _extract_indexes_from_plan(self, explain_plan: str) -> List[str]:
        """從執行計劃中提取使用的索引"""
        indexes = []
        
        # 簡單解析執行計劃中的索引資訊
        for line in explain_plan.split('\n'):
            if 'USING INDEX' in line.upper():
                parts = line.split('USING INDEX')
                if len(parts) > 1:
                    index_name = parts[1].strip().split(' ')[0]
                    indexes.append(index_name)
        
        return indexes
    
    def _calculate_performance_impact(self, metrics: QueryMetrics) -> Dict[str, Any]:
        """計算效能影響"""
        return {
            'frequency_score': min(metrics.execution_count / 100, 10),  # 頻率分數
            'latency_score': min(metrics.avg_time / self.slow_query_threshold, 10),  # 延遲分數
            'overall_impact': (metrics.execution_count * metrics.avg_time) / 1000,  # 總體影響
            'optimization_priority': (
                QueryPriority.CRITICAL if metrics.avg_time > self.slow_query_threshold * 3
                else QueryPriority.HIGH if metrics.avg_time > self.slow_query_threshold * 2
                else QueryPriority.NORMAL if metrics.avg_time > self.slow_query_threshold
                else QueryPriority.LOW
            ).value
        }


# 全域實例
_query_optimizer: Optional[QueryOptimizer] = None


async def get_query_optimizer() -> QueryOptimizer:
    """
    獲取全域查詢優化器實例
    
    Returns:
        查詢優化器實例
    """
    global _query_optimizer
    if _query_optimizer is None:
        _query_optimizer = QueryOptimizer()
        await _query_optimizer.initialize()
    return _query_optimizer