"""图片管理器 — 安全地图、势力图下载与缓存"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import aiohttp

from ..utils.constants import (
    SAFEMAP_URLS,
    INFLUENCE_URLS,
    DEFAULT_IMAGE_CACHE_DIR,
    SAFEMAP_UPDATE_CRON,
    INFLUENCE_UPDATE_CRON,
)


class ImageManager:
    """图片管理器 — 负责安全地图和势力图的下载、缓存与定时更新"""

    def __init__(self, cache_dir: str = DEFAULT_IMAGE_CACHE_DIR):
        self.cache_dir = cache_dir
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        # 图片缓存路径映射
        self._safemap_paths: Dict[str, str] = {}
        self._influence_paths: Dict[str, str] = {}

        # 初始化缓存路径
        for server in ["serenity", "infinity"]:
            self._safemap_paths[server] = os.path.join(cache_dir, f"safemap_{server}.png")
            self._influence_paths[server] = os.path.join(cache_dir, f"influence_{server}.png")

    async def download_image(self, url: str, save_path: str) -> bool:
        """下载图片并保存到本地

        Args:
            url: 图片 URL
            save_path: 本地保存路径

        Returns:
            是否下载成功
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        data = await response.read()
                        with open(save_path, "wb") as f:
                            f.write(data)
                        return True
                    else:
                        return False
        except Exception:
            return False

    async def update_safemap(self, server: str) -> bool:
        """更新指定服务器的安全地图

        Args:
            server: "serenity" / "infinity"

        Returns:
            是否更新成功
        """
        url = SAFEMAP_URLS.get(server)
        if not url:
            return False

        save_path = self._safemap_paths[server]
        return await self.download_image(url, save_path)

    async def update_influence(self, server: str) -> bool:
        """更新指定服务器的势力图

        Args:
            server: "serenity" / "infinity"

        Returns:
            是否更新成功
        """
        url = INFLUENCE_URLS.get(server)
        if not url:
            return False

        save_path = self._influence_paths[server]
        return await self.download_image(url, save_path)

    async def update_all_safemaps(self) -> Dict[str, bool]:
        """更新所有安全地图"""
        results = {}
        for server in ["serenity", "infinity"]:
            results[server] = await self.update_safemap(server)
        return results

    async def update_all_influences(self) -> Dict[str, bool]:
        """更新所有势力图"""
        results = {}
        for server in ["serenity", "infinity"]:
            results[server] = await self.update_influence(server)
        return results

    def get_safemap_path(self, server: str) -> Optional[str]:
        """获取安全地图本地路径

        Returns:
            本地路径，如果不存在则返回 None
        """
        path = self._safemap_paths.get(server)
        if path and os.path.exists(path):
            return path
        return None

    def get_influence_path(self, server: str) -> Optional[str]:
        """获取势力图本地路径

        Returns:
            本地路径，如果不存在则返回 None
        """
        path = self._influence_paths.get(server)
        if path and os.path.exists(path):
            return path
        return None

    def is_safemap_exists(self, server: str) -> bool:
        """检查安全地图是否存在"""
        path = self._safemap_paths.get(server)
        return path is not None and os.path.exists(path)

    def is_influence_exists(self, server: str) -> bool:
        """检查势力图是否存在"""
        path = self._influence_paths.get(server)
        return path is not None and os.path.exists(path)

    @staticmethod
    def _seconds_until(cron: str) -> float:
        """计算到下一个定时点的等待秒数

        Args:
            cron: "分 时" 格式，如 "31 0" 表示每天 00:31
        """
        minute, hour = map(int, cron.split())
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    async def safemap_scheduler(self):
        """安全地图定时更新调度器 — 每天 00:31"""
        while True:
            await asyncio.sleep(self._seconds_until(SAFEMAP_UPDATE_CRON))
            await self.update_all_safemaps()

    async def influence_scheduler(self):
        """势力图定时更新调度器 — 每天 12:41"""
        while True:
            await asyncio.sleep(self._seconds_until(INFLUENCE_UPDATE_CRON))
            await self.update_all_influences()
