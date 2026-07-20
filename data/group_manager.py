"""物品组管理器"""

from typing import List, Optional, Tuple

from .db import Database
from .models import ItemGroup


class GroupManager:
    """物品组管理器 — 处理物品组的增删查

    物品组：将「名称以指定前缀开头」的多个物品聚合为一个组，
    查询组名时展示组内所有物品的价格。
    """

    def __init__(self, db: Database):
        self.db = db

    def add_group(self, group_name: str, prefix: str) -> Tuple[bool, str]:
        """添加物品组

        Args:
            group_name: 组名（查询时精确匹配）
            prefix: 物品名称前缀，如「三钛」匹配所有以三钛开头的物品

        Returns:
            (是否成功, 提示信息)
        """
        if not group_name or not group_name.strip():
            return False, "❌ 组名不能为空"
        if not prefix or not prefix.strip():
            return False, "❌ 前缀不能为空"

        # 验证前缀能匹配到至少一个物品
        matched = self.db.get_items_by_prefix(prefix.strip(), max_results=1)
        if not matched:
            return False, f"❌ 没有名称以「{prefix}」开头的物品，请确认前缀正确"

        success = self.db.add_group(group_name.strip(), prefix.strip())
        if success:
            return True, f"✅ 物品组添加成功：{group_name}（前缀：{prefix}）"
        return False, f"❌ 物品组「{group_name}」已存在"

    def remove_group(self, group_name: str) -> Tuple[bool, str]:
        """删除物品组"""
        success = self.db.remove_group(group_name)
        if success:
            return True, f"✅ 物品组「{group_name}」已删除"
        return False, f"❌ 物品组「{group_name}」不存在"

    def get_group(self, group_name: str) -> Optional[ItemGroup]:
        """精确匹配物品组名"""
        return self.db.get_group(group_name)

    def list_groups(self) -> List[ItemGroup]:
        """列出所有物品组"""
        return self.db.list_groups()
