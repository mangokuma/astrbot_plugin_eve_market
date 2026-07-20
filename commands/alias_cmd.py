"""简称 指令 — 物品别名管理"""

from typing import List

from ..data.alias_manager import AliasManager
from ..utils.formatters import (
    format_alias_list,
    format_alias_added,
    format_alias_removed,
    format_alias_resolved,
)


class AliasCommand:
    """别名管理指令处理器"""

    def __init__(self, alias_manager: AliasManager):
        self.alias_manager = alias_manager

    async def handle(self, args: str) -> str:
        """处理 简称 指令

        Args:
            args: 指令参数，如 "add 三钛 三钛合金" / "del 三钛" / "list" / "三钛"

        Returns:
            格式化后的回复文本
        """
        parts = args.strip().split(maxsplit=2)
        if not parts or not parts[0]:
            return self._help_text()

        sub_cmd = parts[0].lower()

        if sub_cmd == "add":
            return await self._handle_add(parts)
        elif sub_cmd == "del":
            return await self._handle_del(parts)
        elif sub_cmd == "list":
            return await self._handle_list()
        else:
            # 查询单个别名
            return await self._handle_query(sub_cmd)

    async def _handle_add(self, parts: List[str]) -> str:
        """处理添加别名"""
        if len(parts) < 3:
            return "❌ 用法：简称 add <别名> <目标物品名>"

        alias_name = parts[1]
        target_name = parts[2]

        success, msg = self.alias_manager.add_alias(alias_name, target_name)
        if success:
            return format_alias_added(alias_name, target_name)
        return msg

    async def _handle_del(self, parts: List[str]) -> str:
        """处理删除别名"""
        if len(parts) < 2:
            return "❌ 用法：简称 del <别名>"

        alias_name = parts[1]
        success, msg = self.alias_manager.remove_alias(alias_name)
        if success:
            return format_alias_removed(alias_name)
        return msg

    async def _handle_list(self) -> str:
        """处理列出别名"""
        aliases = self.alias_manager.list_aliases()
        return format_alias_list(aliases)

    async def _handle_query(self, alias_name: str) -> str:
        """处理查询别名"""
        target = self.alias_manager.resolve_alias(alias_name)
        if target:
            return format_alias_resolved(alias_name, target)
        return f"❌ 别名「{alias_name}」不存在"

    def _help_text(self) -> str:
        """帮助文本"""
        return (
            "📖 别名管理指令：\n"
            "─" * 30 + "\n"
            "• 简称 add <别名> <目标物品名> — 添加别名\n"
            "• 简称 del <别名> — 删除别名\n"
            "• 简称 list — 列出所有别名\n"
            "• 简称 <别名> — 查询别名指向\n"
        )
