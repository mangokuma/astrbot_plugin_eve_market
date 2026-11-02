"""更新相关指令：手动更新物品数据、查询更新状态"""

from ..data.item_manager import ItemManager


class UpdateCommand:
    """物品数据更新指令"""

    def __init__(self, item_manager: ItemManager):
        self.item_manager = item_manager

    async def handle_update(self) -> str:
        """手动更新物品数据

        Returns:
            更新结果提示文本
        """
        _, msg = await self.item_manager.update_items(trigger="manual")
        return msg

    def handle_status(self) -> str:
        """查询物品数据更新状态

        Returns:
            状态信息文本
        """
        s = self.item_manager.get_update_status()
        lines = ["📦 物品数据状态", f"物品总数：{s['item_count']}"]

        if s["last_update"]:
            status_text = {
                "success": "成功",
                "failed": "失败",
                "never": "从未更新",
            }.get(s["status"], s["status"])
            lines.append(
                f"上次更新：{s['last_update'].strftime('%Y-%m-%d %H:%M:%S')}（{status_text}）"
            )
        else:
            lines.append("上次更新：从未更新")

        if s["status"] == "failed" and s["error"]:
            lines.append(f"失败原因：{s['error'][:100]}")

        if s["next_update"]:
            lines.append(f"下次自动更新：{s['next_update'].strftime('%Y-%m-%d %H:%M')}")
        else:
            lines.append("下次自动更新：已禁用")

        return "\n".join(lines)
