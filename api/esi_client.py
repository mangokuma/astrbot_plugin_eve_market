"""EVE ESI 服务器状态查询客户端"""

import aiohttp
from typing import Dict, Any

from ..data.models import ServerStatus
from ..utils.constants import ESI_URLS, SERVER_NAMES


class ESIClient:
    """ESI API 客户端 — 只负责 HTTP 请求与响应解析，无业务逻辑"""

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

    async def fetch_server_status(self, server_key: str) -> ServerStatus:
        """查询服务器状态并解析为 ServerStatus 对象

        ESI 返回格式：{"players": 12345, "server_version": "1234567",
                      "start_time": "2026-07-20T03:00:00Z", "vip": false}
        如果服务器在线，返回包含 players 的 JSON；如果离线，通常返回 503（抛异常）
        """
        data = await self.get_server_status(server_key)

        players = data.get("players", 0)
        version = data.get("server_version", "")
        is_online = players > 0 or bool(version)

        return ServerStatus(
            server_key=server_key,
            server_name=SERVER_NAMES.get(server_key, server_key),
            is_online=is_online,
            players=players,
            server_version=version,
            start_time=data.get("start_time"),
            vip=data.get("vip"),
        )
