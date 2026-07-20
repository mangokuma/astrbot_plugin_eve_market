"""SQLite 数据库封装"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Item, Alias, ItemGroup
from ..utils.constants import DEFAULT_MAX_RESULTS, FUZZY_PATTERNS, DEFAULT_FUZZY_PATTERN, DEFAULT_MIN_CONFIDENCE


def _fuzzy_match_score(query: str, target: str) -> float:
    """计算非连续子串匹配可信度（百分比）

    算法：将 query 拆分为字符，在 target 中按顺序查找每个字符，
    计算匹配到的字符数占总字符数的比例。

    例如:
        query="三钛", target="三钛合金" → 100%
        query="三钛", target="三氧化钛" → 100%
        query="abc", target="aXbYc" → 100%
        query="abc", target="ac" → 33% (b 未匹配)
    """
    if not query:
        return 100.0

    query_chars = list(query.lower())
    target_lower = target.lower()
    matched = 0
    target_idx = 0

    for qc in query_chars:
        found_pos = target_lower.find(qc, target_idx)
        if found_pos != -1:
            matched += 1
            target_idx = found_pos + 1
        else:
            break

    return (matched / len(query_chars)) * 100.0


class Database:
    """SQLite 数据库管理器"""

    def __init__(self, db_path: str = "./data/eve_items.db"):
        self.db_path = db_path
        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """初始化数据库表结构"""
        with self._connect() as conn:
            cursor = conn.cursor()

            # 物品表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    type_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    group_id INTEGER,
                    category_id INTEGER,
                    market_group_id INTEGER,
                    volume REAL,
                    mass REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_items_name ON items(name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_items_name_nocase ON items(name COLLATE NOCASE)
            """)

            # 别名表（独立存储）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    target_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_aliases_name ON aliases(alias_name)
            """)

            # 物品组表（独立存储）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS item_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    prefix TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 元数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    # ==================== 物品操作 ====================

    def insert_items(self, items: List[Item]):
        """批量插入或替换物品数据"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items")
            cursor.executemany(
                """
                INSERT INTO items (type_id, name, group_id, category_id, market_group_id, volume, mass)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (i.type_id, i.name, i.group_id, i.category_id, i.market_group_id, i.volume, i.mass)
                    for i in items
                ]
            )
            conn.commit()

    def search_items(
        self,
        keyword: str,
        fuzzy: bool = True,
        max_results: int = DEFAULT_MAX_RESULTS,
        fuzzy_pattern: str = DEFAULT_FUZZY_PATTERN,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> List[Item]:
        """搜索物品（支持非连续子串模糊搜索）

        Args:
            keyword: 搜索关键词（默认中文名称）
            fuzzy: 是否启用模糊搜索
            max_results: 最大返回数量
            fuzzy_pattern: 模糊模式 (contains / starts_with / ends_with)
            min_confidence: 模糊搜索可信度最低阈值（百分比）

        Returns:
            按可信度排序的物品列表
        """
        with self._connect() as conn:
            cursor = conn.cursor()

            if fuzzy:
                # 第一步：使用 SQLite LIKE 做初步过滤（减少数据量）
                # 非连续子串的 LIKE 模式：将每个字符用 % 隔开
                # 例如 "三钛" → "%三%钛%"
                like_pattern = "%" + "%".join(list(keyword)) + "%"

                cursor.execute(
                    """
                    SELECT type_id, name, group_id, category_id, market_group_id, volume, mass
                    FROM items
                    WHERE name COLLATE NOCASE LIKE ?
                    ORDER BY name
                    LIMIT 100
                    """,
                    (like_pattern,)
                )
            else:
                cursor.execute(
                    """
                    SELECT type_id, name, group_id, category_id, market_group_id, volume, mass
                    FROM items
                    WHERE name COLLATE NOCASE = ?
                    LIMIT ?
                    """,
                    (keyword, max_results)
                )
                rows = cursor.fetchall()
                return [Item(**dict(row)) for row in rows]

            rows = cursor.fetchall()
            items = [Item(**dict(row)) for row in rows]

            # 第二步：计算非连续子串匹配可信度
            scored_items = []
            for item in items:
                score = _fuzzy_match_score(keyword, item.name)
                if score >= min_confidence:
                    scored_items.append((score, item))

            # 按可信度降序排序，取前 max_results 个
            scored_items.sort(key=lambda x: x[0], reverse=True)
            return [item for _, item in scored_items[:max_results]]

    def get_item_by_name(self, name: str) -> Optional[Item]:
        """精确匹配物品名称"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT type_id, name, group_id, category_id, market_group_id, volume, mass
                FROM items
                WHERE name COLLATE NOCASE = ?
                LIMIT 1
                """,
                (name,)
            )
            row = cursor.fetchone()
            return Item(**dict(row)) if row else None

    def get_item_count(self) -> int:
        """获取物品总数"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM items")
            return cursor.fetchone()[0]

    # ==================== 元数据操作 ====================

    def set_meta(self, key: str, value: str):
        """设置元数据"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO meta (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, datetime.now().isoformat())
            )
            conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        """获取元数据"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM meta WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_last_update_time(self) -> Optional[datetime]:
        """获取上次物品更新时间"""
        value = self.get_meta("last_update")
        if value:
            return datetime.fromisoformat(value)
        return None

    # ==================== 别名操作 ====================

    def add_alias(self, alias_name: str, target_name: str) -> bool:
        """添加别名"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO aliases (alias_name, target_name)
                    VALUES (?, ?)
                    """,
                    (alias_name, target_name)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def remove_alias(self, alias_name: str) -> bool:
        """删除别名"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM aliases WHERE alias_name COLLATE NOCASE = ?", (alias_name,))
            conn.commit()
            return cursor.rowcount > 0

    def get_alias(self, alias_name: str) -> Optional[str]:
        """查询别名指向的目标名称"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT target_name FROM aliases WHERE alias_name COLLATE NOCASE = ?",
                (alias_name,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def list_aliases(self) -> List[Alias]:
        """列出所有别名"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, alias_name, target_name, created_at
                FROM aliases
                ORDER BY alias_name
                """
            )
            rows = cursor.fetchall()
            return [
                Alias(
                    id=row["id"],
                    alias_name=row["alias_name"],
                    target_name=row["target_name"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

    def alias_exists(self, alias_name: str) -> bool:
        """检查别名是否存在"""
        return self.get_alias(alias_name) is not None

    # ==================== 物品组操作 ====================

    def get_items_by_prefix(self, prefix: str, max_results: int = 20) -> List[Item]:
        """按名称前缀获取物品（用于物品组展开）"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT type_id, name, group_id, category_id, market_group_id, volume, mass
                FROM items
                WHERE name COLLATE NOCASE LIKE ?
                ORDER BY name
                LIMIT ?
                """,
                (f"{prefix}%", max_results)
            )
            rows = cursor.fetchall()
            return [Item(**dict(row)) for row in rows]

    def add_group(self, group_name: str, prefix: str) -> bool:
        """添加物品组"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO item_groups (group_name, prefix)
                    VALUES (?, ?)
                    """,
                    (group_name, prefix)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def remove_group(self, group_name: str) -> bool:
        """删除物品组"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM item_groups WHERE group_name COLLATE NOCASE = ?",
                (group_name,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_group(self, group_name: str) -> Optional[ItemGroup]:
        """精确匹配物品组名"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, group_name, prefix, created_at
                FROM item_groups
                WHERE group_name COLLATE NOCASE = ?
                LIMIT 1
                """,
                (group_name,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ItemGroup(
                id=row["id"],
                group_name=row["group_name"],
                prefix=row["prefix"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def list_groups(self) -> List[ItemGroup]:
        """列出所有物品组"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, group_name, prefix, created_at
                FROM item_groups
                ORDER BY group_name
                """
            )
            rows = cursor.fetchall()
            return [
                ItemGroup(
                    id=row["id"],
                    group_name=row["group_name"],
                    prefix=row["prefix"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]
