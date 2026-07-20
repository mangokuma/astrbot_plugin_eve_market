"""物品组 指令 — 物品组管理"""

from typing import List

from ..data.group_manager import GroupManager
from ..utils.formatters import (
    format_group_list,
    format_group_added,
    format_group_removed,
)


class GroupCommand:
    """物品组管理指令处理器"""

    def __init__(self, group_manager: GroupManager):
        self.group_manager = group_manager

    async def handle(self, args: str) -> str:
        """处理 物品组 指令

        Args:
            args: 指令参数，如 "add 矿物 三钛" / "del 矿物" / "list"

        Returns:
            格式化后的回复文本
        """
        parts = args.strip().split(maxsplit=2)
        if not parts or not parts[0]:
            return self._help_text()

        sub_cmd = parts[0].lower()

        if sub_cmd == "add":
            if len(parts) < 3:
                return "❌ 用法：物品组 add <组名> <名称前缀>"
            success, msg = self.group_manager.add_group(parts[1], parts[2])
            if success:
                return format_group_added(parts[1], parts[2])
            return msg
        elif sub_cmd == "del":
            if len(parts) < 2:
                return "❌ 用法：物品组 del <组名>"
            success, msg = self.group_manager.remove_group(parts[1])
            if success:
                return format_group_removed(parts[1])
            return msg
        elif sub_cmd == "list":
            return format_group_list(self.group_manager.list_groups())
        else:
            return self._help_text()

    def _help_text(self) -> str:
        """帮助文本"""
        return (
            "📖 物品组管理指令：\n"
            "─" * 30 + "\n"
            "• 物品组 add <组名> <名称前缀> — 添加物品组\n"
            "• 物品组 del <组名> — 删除物品组\n"
            "• 物品组 list — 列出所有物品组\n"
            "\n"
            "💡 示例：物品组 add 常用矿物 三钛\n"
            "   之后使用「nj 常用矿物」即可查看所有\n"
            "   以「三钛」开头的物品价格"
        )
