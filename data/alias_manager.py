"""物品别名管理器"""

from typing import List, Optional, Tuple

from .db import Database
from .models import Alias, Item


class AliasManager:
    """别名管理器 — 处理别名的增删查"""

    def __init__(self, db: Database):
        self.db = db

    def add_alias(self, alias_name: str, target_name: str) -> Tuple[bool, str]:
        """添加别名

        Args:
            alias_name: 别名
            target_name: 目标物品名称

        Returns:
            (是否成功, 提示信息)
        """
        # 验证别名是否合法
        if not self.is_valid_alias_name(alias_name):
            return False, f"❌ 别名「{alias_name}」不合法，不能与现有物品名称冲突"

        # 检查目标物品是否存在
        target = self.db.get_item_by_name(target_name)
        if not target:
            return False, f"❌ 目标物品「{target_name}」不存在，请确认物品名称正确"

        # 添加别名
        success = self.db.add_alias(alias_name, target_name)
        if success:
            return True, f"✅ 别名添加成功：{alias_name} → {target_name}"
        else:
            return False, f"❌ 别名「{alias_name}」已存在"

    def remove_alias(self, alias_name: str) -> Tuple[bool, str]:
        """删除别名

        Returns:
            (是否成功, 提示信息)
        """
        success = self.db.remove_alias(alias_name)
        if success:
            return True, f"✅ 别名「{alias_name}」已删除"
        else:
            return False, f"❌ 别名「{alias_name}」不存在"

    def resolve_alias(self, alias_name: str) -> Optional[str]:
        """解析别名到目标名称

        Args:
            alias_name: 别名

        Returns:
            目标物品名称，如果别名不存在则返回 None
        """
        return self.db.get_alias(alias_name)

    def list_aliases(self) -> List[Alias]:
        """列出所有别名"""
        return self.db.list_aliases()

    def is_valid_alias_name(self, alias_name: str) -> bool:
        """验证别名是否合法

        规则：
        1. 不能为空
        2. 不能与现有物品名称冲突（避免歧义）
        """
        if not alias_name or not alias_name.strip():
            return False

        # 检查是否与现有物品名冲突
        existing_item = self.db.get_item_by_name(alias_name)
        if existing_item:
            return False

        return True

    def resolve_with_fallback(self, keyword: str) -> Optional[str]:
        """解析关键词：先尝试别名，再返回原关键词

        这是供 price_query 使用的便捷方法
        """
        resolved = self.resolve_alias(keyword)
        return resolved if resolved else keyword
