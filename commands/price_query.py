"""nj / cx / sg 指令 — 查询物品价格"""

import asyncio
from typing import List, Optional, Tuple

from ..api.ceve_client import CEVEClient
from ..data.alias_manager import AliasManager
from ..data.group_manager import GroupManager
from ..data.item_manager import ItemManager
from ..data.models import Item, PriceInfo
from ..utils.constants import SERVER_NAMES
from ..utils.formatters import (
    format_price_result,
    format_multi_price_results,
    format_group_price_result,
)


class PriceQueryCommand:
    """价格查询指令处理器"""

    def __init__(
        self,
        item_manager: ItemManager,
        alias_manager: AliasManager,
        group_manager: GroupManager,
    ):
        self.item_manager = item_manager
        self.alias_manager = alias_manager
        self.group_manager = group_manager
        self.ceve_client = CEVEClient()

    async def handle(self, server_key: str, keyword: str) -> str:
        """处理价格查询指令

        流程：
        1. 解析别名
        2. 精确匹配物品组 → 展示组内所有物品价格
        3. 模糊搜索物品：
           - 唯一结果 / 有精确匹配 → 展示单个物品价格
           - 多个结果 → 展示所有结果的价格 + 别名/物品组提示

        Args:
            server_key: "tranquility" / "serenity" / "infinity"
            keyword: 物品名称、别名或物品组名

        Returns:
            格式化后的回复文本
        """
        server_name = SERVER_NAMES[server_key]

        # Step 1: 解析别名
        resolved_name = self.alias_manager.resolve_with_fallback(keyword)

        # Step 2: 精确匹配物品组
        group = self.group_manager.get_group(resolved_name)
        if group:
            items = self.item_manager.get_items_by_prefix(group.prefix, max_results=20)
            if not items:
                return f"❌ 物品组「{group.group_name}」（前缀：{group.prefix}）未匹配到任何物品"
            entries = await self._query_prices(server_key, items)
            return format_group_price_result(group.group_name, group.prefix, entries, server_name)

        # Step 3: 搜索物品（模糊搜索，最多6个结果，可信度>=50%）
        items = self.item_manager.search_item(resolved_name, fuzzy=True, max_results=6)

        if not items:
            return f"❌ 未找到与「{keyword}」相关的物品（可信度>=50%）"

        # 结果唯一 → 直接展示价格
        if len(items) == 1:
            return await self._query_single_price(server_key, items[0])

        # 多个结果中存在精确匹配 → 展示精确匹配的价格
        exact_match = next(
            (item for item in items if item.name.lower() == resolved_name.lower()),
            None
        )
        if exact_match:
            return await self._query_single_price(server_key, exact_match)

        # 多个模糊结果 → 展示所有结果的价格
        entries = await self._query_prices(server_key, items)
        return format_multi_price_results(entries, keyword, server_name)

    async def _fetch_price(self, server_key: str, item: Item) -> Optional[PriceInfo]:
        """获取单个物品价格，失败返回 None"""
        try:
            data = await self.ceve_client.query_price(server_key, item.type_id)

            buy_data = data.get("buy", {})
            sell_data = data.get("sell", {})

            # 处理无订单情况：buy.max=0 或 sell.min=0 视为无订单
            buy_max = buy_data.get("max")
            sell_min = sell_data.get("min")
            if buy_max == 0:
                buy_max = None
            if sell_min == 0:
                sell_min = None

            return PriceInfo(
                server_key=server_key,
                server_name=SERVER_NAMES[server_key],
                item_name=item.name,
                buy_max=buy_max,
                sell_min=sell_min,
            )
        except Exception:
            return None

    async def _query_prices(
        self, server_key: str, items: List[Item]
    ) -> List[Tuple[Item, Optional[PriceInfo]]]:
        """并发查询多个物品价格"""
        results = await asyncio.gather(
            *[self._fetch_price(server_key, item) for item in items]
        )
        return list(zip(items, results))

    async def _query_single_price(self, server_key: str, item: Item) -> str:
        """查询单个物品的价格（只展示最高收单与最低卖单）"""
        price_info = await self._fetch_price(server_key, item)
        if price_info is None:
            return f"❌ 查询「{item.name}」价格失败，请稍后重试"
        return format_price_result([price_info], item.name)
