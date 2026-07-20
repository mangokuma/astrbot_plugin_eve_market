"""ss 指令 — 查询 EVE 三服服务器状态"""

import asyncio
from typing import List

from ..api.esi_client import ESIClient
from ..data.models import ServerStatus
from ..utils.constants import SERVER_KEYS, SERVER_NAMES
from ..utils.formatters import format_server_status


class ServerStatusCommand:
    """服务器状态查询指令处理器"""

    def __init__(self):
        self.esi_client = ESIClient()

    async def handle(self) -> str:
        """处理 ss 指令

        Returns:
            格式化后的回复文本
        """
        # 并发请求三个服务器状态
        tasks = [self._fetch_single_status(key) for key in SERVER_KEYS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        statuses: List[ServerStatus] = []
        for key, result in zip(SERVER_KEYS, results):
            if isinstance(result, Exception):
                statuses.append(ServerStatus(
                    server_key=key,
                    server_name=SERVER_NAMES[key],
                    is_online=False,
                    players=0,
                    server_version=None,
                ))
            else:
                statuses.append(result)

        return format_server_status(statuses)

    async def _fetch_single_status(self, server_key: str) -> ServerStatus:
        """获取单个服务器状态"""
        data = await self.esi_client.get_server_status(server_key)

        # ESI 返回格式：{"players": 12345, "server_version": "1234567", "start_time": "..."}
        # 如果服务器在线，返回包含 players 的 JSON；如果离线，可能返回 503 或空数据
        players = data.get("players", 0)
        version = data.get("server_version", "")
        is_online = players > 0 or bool(version)

        return ServerStatus(
            server_key=server_key,
            server_name=SERVER_NAMES[server_key],
            is_online=is_online,
            players=players,
            server_version=version,
        )
