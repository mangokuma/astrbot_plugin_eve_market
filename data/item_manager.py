"""物品数据管理器 — 下载、解析、更新"""

import asyncio
import io
from datetime import datetime
from typing import List, Optional

import aiohttp
import pandas as pd

from .db import Database
from .models import Item
from ..utils.constants import ITEM_DUMP_URL, DEFAULT_AUTO_UPDATE_INTERVAL


class ItemManager:
    """物品数据管理器"""

    def __init__(self, db: Database, auto_update_interval: int = DEFAULT_AUTO_UPDATE_INTERVAL):
        self.db = db
        self.auto_update_interval = auto_update_interval
        self._update_task: Optional[asyncio.Task] = None

    async def update_items(self) -> tuple[bool, str]:
        """下载并更新物品数据

        Returns:
            (是否成功, 提示信息)
        """
        try:
            # 下载 xlsx
            async with aiohttp.ClientSession() as session:
                async with session.get(ITEM_DUMP_URL, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    response.raise_for_status()
                    data = await response.read()

            # 解析 xlsx
            df = pd.read_excel(io.BytesIO(data), engine="openpyxl")

            # 映射列名（根据实际 xlsx 结构调整）
            # 假设列名：type_id, name, group_id, category_id, market_group_id, volume, mass
            items = []
            for _, row in df.iterrows():
                try:
                    item = Item(
                        type_id=int(row.get("type_id", 0)),
                        name=str(row.get("name", "")).strip(),
                        group_id=int(row.get("group_id")) if pd.notna(row.get("group_id")) else None,
                        category_id=int(row.get("category_id")) if pd.notna(row.get("category_id")) else None,
                        market_group_id=int(row.get("market_group_id")) if pd.notna(row.get("market_group_id")) else None,
                        volume=float(row.get("volume")) if pd.notna(row.get("volume")) else None,
                        mass=float(row.get("mass")) if pd.notna(row.get("mass")) else None,
                    )
                    if item.type_id > 0 and item.name:
                        items.append(item)
                except (ValueError, TypeError):
                    continue

            # 写入数据库
            self.db.insert_items(items)
            self.db.set_meta("last_update", datetime.now().isoformat())

            return True, f"✅ 物品数据更新成功！共导入 {len(items)} 条记录"

        except Exception as e:
            return False, f"❌ 更新失败：{str(e)}"

    async def auto_update_scheduler(self):
        """后台定时更新调度器

        按照配置的间隔自动更新物品数据
        """
        if self.auto_update_interval <= 0:
            return  # 间隔为 0 表示禁用自动更新
        while True:
            await asyncio.sleep(self.auto_update_interval)
            success, msg = await self.update_items()
            # 这里可以添加日志记录
            print(f"[AutoUpdate] {msg}")

    def search_item(
        self,
        keyword: str,
        fuzzy: bool = True,
        max_results: int = 6,
    ) -> List[Item]:
        """搜索物品（供指令层调用）

        默认使用 contains 模式，支持非连续子串搜索，可信度≥50%
        """
        return self.db.search_items(keyword, fuzzy=fuzzy, max_results=max_results)

    def get_item_count(self) -> int:
        """获取物品总数"""
        return self.db.get_item_count()

    def get_last_update_time(self) -> Optional[datetime]:
        """获取上次更新时间"""
        return self.db.get_last_update_time()
