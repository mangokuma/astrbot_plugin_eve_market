"""CEVE Market 价格查询客户端"""

import aiohttp
from typing import Dict, Any

from ..utils.constants import CEVE_API_URLS, DEFAULT_REGION_IDS


class CEVEClient:
    """CEVE Market API 客户端 — 只负责 HTTP 请求，无业务逻辑"""

    def __init__(self, timeout: int = 15):
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def query_price(
        self,
        server_key: str,
        type_id: int,
    ) -> Dict[str, Any]:
        """查询指定服务器的物品价格

        调用 market 接口: {base_url}market/region/{region_id}/type/{type_id}.json

        宁静/晨曦默认使用吉他 Region (10000002)
        曙光默认使用长征 Region (10000016，索巴色基所在星域)

        Args:
            server_key: "tranquility" / "serenity" / "infinity"
            type_id: 物品 type_id

        Returns:
            CEVE API 返回的原始 JSON 数据
            格式:
            {
                "all": {"max": 384900, "min": 0.01, "volume": 110610128051},
                "buy": {"max": 6, "min": 0.01, "volume": 74302852844},
                "sell": {"max": 384900, "min": 2.05, "volume": 36307275207}
            }

        Raises:
            ValueError: 未知服务器 key
            aiohttp.ClientError: 请求失败
        """
        base_url = CEVE_API_URLS.get(server_key)
        if not base_url:
            raise ValueError(f"未知服务器 key: {server_key}")

        region_id = DEFAULT_REGION_IDS.get(server_key, 10000002)
        url = f"{base_url}market/region/{region_id}/type/{type_id}.json"

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
