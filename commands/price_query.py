"""nj / cx / sg 指令 — 查询物品价格"""

from typing import List, Optional

from ..api.ceve_client import CEVEClient
from ..data.alias_manager import AliasManager
from ..data.item_manager import ItemManager
from ..data.models import Item, PriceInfo
from ..utils.constants import SERVER_NAMES
from ..utils.formatters import (
    format_price_result,
    format_item_candidates,
)


class PriceQueryCommand:
    """价格查询指令处理器"""

    def __init__(self, item_manager: ItemManager, alias_manager: AliasManager):
        self.item_manager = item_manager
        self.alias_manager = alias_manager
        self.ceve_client = CEVEClient()

    async def handle(self, server_key: str, keyword: str) -> str:
        """处理价格查询指令

        Args:
            server_key: "tranquility" / "serenity" / "infinity"
            keyword: 物品名称或别名

        Returns:
            格式化后的回复文本
        """
        # Step 1: 解析别名
        resolved_name = self.alias_manager.resolve_with_fallback(keyword)

        # Step 2: 搜索物品（模糊搜索，最多6个结果，可信度>=50%）
        items = self.item_manager.search_item(resolved_name, fuzzy=True, max_results=6)

        if not items:
            return f"❌ 未找到与「{keyword}」相关的物品（可信度>=50%）"

        # Step 3: 如果结果唯一，直接查询价格
        if len(items) == 1:
            return await self._query_single_price(server_key, items[0])

        # Step 4: 如果结果不唯一，检查是否有精确匹配
        exact_match = next(
            (item for item in items if item.name.lower() == resolved_name.lower()),
            None
        )
        if exact_match:
            return await self._query_single_price(server_key, exact_match)

        # 展示候选列表
        return format_item_candidates(items, keyword)

    async def _query_single_price(self, server_key: str, item: Item) -> str:
        """查询单个物品的价格

        使用 CEVE market 接口: /market/region/{region_id}/type/{type_id}.json
        返回格式:
        {
            "all": {"max": 384900, "min": 0.01, "volume": 110610128051},
            "buy": {"max": 6, "min": 0.01, "volume": 74302852844},
            "sell": {"max": 384900, "min": 2.05, "volume": 36307275207}
        }

        无订单时返回:
        {
            "all": {"max": 0, "min": 0, "volume": 0},
            "buy": {"max": 0, "min": 0, "volume": 0},
            "sell": {"max": 0, "min": 0, "volume": 0}
        }
        """
        try:
            data = await self.ceve_client.query_price(server_key, item.type_id)

            # 解析 market 接口 JSON
            buy_data = data.get("buy", {})
            sell_data = data.get("sell", {})
            all_data = data.get("all", {})

            # 处理无订单情况：buy.max=0 或 sell.min=0 视为无订单
            buy_max = buy_data.get("max")
            sell_min = sell_data.get("min")

            if buy_max == 0:
                buy_max = None
            if sell_min == 0:
                sell_min = None

            price_info = PriceInfo(
                server_key=server_key,
                server_name=SERVER_NAMES[server_key],
                item_name=item.name,
                buy_max=buy_max,
                sell_min=sell_min,
                volume=all_data.get("volume"),
            )

            return format_price_result([price_info], item.name)

        except Exception as e:
            return f"❌ 查询「{item.name}」价格失败：{str(e)}"
