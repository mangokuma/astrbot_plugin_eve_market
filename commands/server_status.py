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
        tasks = [self.esi_client.fetch_server_status(key) for key in SERVER_KEYS]
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
