"""物品数据管理器 — 下载、解析、更新"""

import asyncio
import io
import json
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import aiohttp
import pandas as pd
from astrbot.api import logger

from .db import Database
from .models import Item
from ..utils.constants import (
    ITEM_DUMP_URL,
    ITEM_DUMP_FALLBACK_URL,
    DEFAULT_AUTO_UPDATE_TIME,
    DEFAULT_UPDATE_RETRY_MINUTES,
)

# 请求头：部分数据源（如 ceve-market）的风控会拦截默认的 aiohttp UA
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


class ItemManager:
    """物品数据管理器"""

    def __init__(
        self,
        db: Database,
        auto_update_time: str = DEFAULT_AUTO_UPDATE_TIME,
        retry_minutes: int = DEFAULT_UPDATE_RETRY_MINUTES,
    ):
        self.db = db
        # 每天自动更新时刻（"HH:MM" 格式），空字符串表示禁用自动更新
        self.auto_update_time = (auto_update_time or "").strip()
        # 自动更新失败后的重试间隔（分钟），至少 1 分钟
        try:
            self.retry_minutes = max(1, int(retry_minutes))
        except (ValueError, TypeError):
            self.retry_minutes = DEFAULT_UPDATE_RETRY_MINUTES
        # 手动更新与自动更新互斥，防止并发写入导致数据被清空
        self._lock = asyncio.Lock()

    # ==================== 更新 ====================

    async def update_items(self, trigger: str = "manual") -> tuple[bool, str]:
        """下载并更新物品数据（手动与自动更新共用，带并发锁）

        Args:
            trigger: 触发来源标识（"manual" 指令触发 / "auto" 定时触发），仅用于日志

        Returns:
            (是否成功, 提示信息)
        """
        if self._lock.locked():
            return False, "⏳ 物品数据正在更新中，请稍候再试"

        async with self._lock:
            try:
                items, source = await self._fetch_items()

                # 写入数据库
                self.db.insert_items(items)
                self.db.set_meta("last_update", datetime.now().isoformat())
                self.db.set_meta("last_update_status", "success")
                self.db.set_meta("last_update_count", str(len(items)))
                self.db.set_meta("last_update_error", "")

                source_note = "" if source == "primary" else f"（备用数据源：{source}）"
                logger.info(f"[EVE Market] 物品数据更新成功（{trigger}），共 {len(items)} 条{source_note}")
                return True, f"✅ 物品数据更新成功！共导入 {len(items)} 条记录{source_note}"

            except Exception as e:
                err = str(e)
                logger.error(f"[EVE Market] 物品数据更新失败（{trigger}）：{err}")
                self.db.set_meta("last_update_status", "failed")
                self.db.set_meta("last_update_error", err)
                return False, f"❌ 更新失败：{err}"

    # ==================== 数据源 ====================

    async def _fetch_items(self) -> Tuple[List[Item], str]:
        """获取物品数据：主数据源失败时自动降级到备用数据源

        Returns:
            (物品列表, 数据源标识："primary" 或备用源名称)

        Raises:
            Exception: 两个数据源均失败时抛出最后合并的错误
        """
        primary_err = None
        try:
            data = await self._download(ITEM_DUMP_URL)
            return self._parse_xlsx(data), "primary"
        except Exception as e:
            primary_err = e
            logger.warning(f"[EVE Market] 主数据源（ceve-market）获取失败：{e}")

        try:
            data = await self._download(ITEM_DUMP_FALLBACK_URL)
            return self._parse_c3q_js(data), "eve.c3q.cc"
        except Exception as e:
            raise ValueError(
                f"主数据源与备用数据源均不可用。"
                f"主数据源：{primary_err}；备用数据源：{e}"
            )

    async def _download(self, url: str) -> bytes:
        """下载数据文件"""
        async with aiohttp.ClientSession(headers=_REQUEST_HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                response.raise_for_status()
                return await response.read()

    def _parse_xlsx(self, data: bytes) -> List[Item]:
        """解析 ceve-market evedata.xlsx

        Raises:
            ValueError: 内容不是有效 xlsx（如被反爬拦截返回 HTML）或解析为空
        """
        # xlsx 本质是 zip，以 PK 魔数开头；HTML 拦截页没有该特征
        if data[:4] != b"PK\x03\x04":
            raise ValueError("主数据源返回的不是有效的数据文件（可能被反爬风控临时拦截）")

        # 实际结构（ceve-market evedata.xlsx）：
        #   sheet「物品列表」，列：typeID / 物品名称 / 描述 / 第一~第七市场分类
        # 兼容英文列名（type_id / name）以防格式变更
        df = pd.read_excel(
            io.BytesIO(data),
            sheet_name="物品列表",
            engine="openpyxl",
        )

        # 列名映射：兼容中英文
        col_map = {}
        for col in df.columns:
            cl = str(col).strip().lower()
            if cl in ("typeid", "type_id"):
                col_map[col] = "type_id"
            elif cl in ("物品名称", "name"):
                col_map[col] = "name"
        df = df.rename(columns=col_map)

        items = []
        for _, row in df.iterrows():
            try:
                item = Item(
                    type_id=int(row.get("type_id", 0)),
                    name=str(row.get("name", "")).strip(),
                )
                if item.type_id > 0 and item.name and item.name.lower() != "nan":
                    items.append(item)
            except (ValueError, TypeError):
                continue

        if not items:
            raise ValueError("主数据源解析结果为空，数据文件格式可能已变更")
        return items

    def _parse_c3q_js(self, data: bytes) -> List[Item]:
        """解析 eve.c3q.cc 静态数据（JS 包装 JSON）

        结构：eve_types={"<typeID>": ["中文名", 体积, ?, marketGroupID, groupID, ...], ...}
        marketGroupID 为 null 的是恒星/行星/星系等非交易物，过滤后与 evedata.xlsx 口径对齐
        """
        try:
            raw = data.decode("utf-8")
            start = raw.index("{")
            end = raw.rindex("}")
            payload = json.loads(raw[start:end + 1])
        except Exception as e:
            raise ValueError(f"备用数据源解析失败：{e}")

        items = []
        for tid, arr in payload.items():
            try:
                type_id = int(tid)
                name = str(arr[0]).strip()
                volume = arr[1] if len(arr) > 1 else None
                market_group_id = arr[3] if len(arr) > 3 else None
                group_id = arr[4] if len(arr) > 4 else None
            except (ValueError, TypeError, IndexError):
                continue
            if type_id > 0 and name and name.lower() != "nan" and market_group_id is not None:
                items.append(Item(
                    type_id=type_id,
                    name=name,
                    group_id=group_id,
                    market_group_id=market_group_id,
                    volume=volume,
                ))

        if not items:
            raise ValueError("备用数据源解析结果为空")
        return items

    # ==================== 自动更新调度 ====================

    async def auto_update_scheduler(self):
        """每天固定时刻自动更新物品数据

        - 到达设定的每日时刻执行一次更新
        - 失败后在 retry_minutes 分钟后重试一次
        - 与手动更新共用锁，不会并发执行
        """
        if not self.auto_update_time:
            logger.info("[EVE Market] 物品数据自动更新已禁用（未配置 auto_update_time）")
            return
        if not self._parse_time(self.auto_update_time):
            logger.warning(
                f"[EVE Market] auto_update_time 格式无效：{self.auto_update_time}"
                "（应为 HH:MM），自动更新已禁用"
            )
            return

        while True:
            wait_seconds = self._seconds_until_next_run()
            next_run = datetime.now() + timedelta(seconds=wait_seconds)
            logger.info(
                f"[EVE Market] 下次物品数据自动更新：{next_run.strftime('%Y-%m-%d %H:%M')}"
            )
            await asyncio.sleep(wait_seconds)

            success, msg = await self.update_items(trigger="auto")
            logger.info(f"[EVE Market] 自动更新结果：{msg}")
            if success:
                continue

            # 失败后延时重试一次，再失败则记录日志等待次日
            logger.info(f"[EVE Market] {self.retry_minutes} 分钟后将重试物品数据更新...")
            await asyncio.sleep(self.retry_minutes * 60)
            success, msg = await self.update_items(trigger="auto-retry")
            logger.info(f"[EVE Market] 自动更新重试结果：{msg}")

    @staticmethod
    def _parse_time(time_str: str) -> Optional[tuple]:
        """解析 "HH:MM" 格式的时刻，返回 (hour, minute)，失败返回 None"""
        try:
            parts = str(time_str).strip().split(":")
            if len(parts) != 2:
                return None
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h, m
        except (ValueError, TypeError):
            pass
        return None

    def _seconds_until_next_run(self) -> float:
        """距离下次自动更新的秒数（默认回退为 24 小时）"""
        parsed = self._parse_time(self.auto_update_time)
        if not parsed:
            return 86400.0
        h, m = parsed
        now = datetime.now()
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    def get_next_update_time(self) -> Optional[datetime]:
        """获取下次自动更新时间，未配置或已禁用返回 None"""
        if not self.auto_update_time or not self._parse_time(self.auto_update_time):
            return None
        return datetime.now() + timedelta(seconds=self._seconds_until_next_run())

    def get_update_status(self) -> dict:
        """获取更新状态（供「更新状态」指令展示）

        Returns:
            包含 item_count / last_update / status / error / next_update 的字典
        """
        last_update = self.db.get_last_update_time()
        status = self.db.get_meta("last_update_status")
        if not status:
            # 兼容旧数据：有更新时间记录但无状态字段
            status = "success" if last_update else "never"
        return {
            "item_count": self.db.get_item_count(),
            "last_update": last_update,
            "status": status,
            "error": self.db.get_meta("last_update_error") or "",
            "next_update": self.get_next_update_time(),
        }

    # ==================== 查询（供指令层调用） ====================

    def search_item(
        self,
        keyword: str,
        fuzzy: bool = True,
        max_results: int = 6,
        fuzzy_pattern: str = "contains",
        min_confidence: float = 50,
    ) -> List[Item]:
        """搜索物品（供指令层调用）

        默认使用 contains 模式，支持非连续子串搜索，可信度≥50%
        """
        return self.db.search_items(
            keyword,
            fuzzy=fuzzy,
            max_results=max_results,
            fuzzy_pattern=fuzzy_pattern,
            min_confidence=min_confidence,
        )

    def get_items_by_prefix(self, prefix: str, max_results: int = 20) -> List[Item]:
        """按名称前缀获取物品（供物品组展开使用）"""
        return self.db.get_items_by_prefix(prefix, max_results=max_results)

    def get_item_count(self) -> int:
        """获取物品总数"""
        return self.db.get_item_count()

    def get_last_update_time(self) -> Optional[datetime]:
        """获取上次更新时间"""
        return self.db.get_last_update_time()
