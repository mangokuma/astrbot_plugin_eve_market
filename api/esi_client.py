"""EVE ESI 服务器状态查询客户端"""

import aiohttp
from typing import Dict, Any

from ..utils.constants import ESI_URLS


class ESIClient:
    """ESI API 客户端 — 只负责 HTTP 请求，无业务逻辑"""

    def __init__(self, timeout: int = 10):
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def get_server_status(self, server_key: str) -> Dict[str, Any]:
        """查询指定服务器状态

        Args:
            server_key: "tranquility" / "serenity" / "infinity"

        Returns:
            ESI 返回的原始 JSON 数据

        Raises:
            ValueError: 未知服务器 key
            aiohttp.ClientError: 请求失败
        """
        url = ESI_URLS.get(server_key)
        if not url:
            raise ValueError(f"未知服务器 key: {server_key}")

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
