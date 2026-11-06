"""每日维护监控 — 晨曦/曙光每天 11:00 例行维护，恢复后推送开服消息"""

import asyncio
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Dict, List, Optional

from astrbot.api import logger

from ..api.esi_client import ESIClient
from ..data.models import ServerStatus
from ..utils.constants import (
    SERVER_NAMES,
    MAINTENANCE_MONITOR_SERVERS,
    DEFAULT_MAINTENANCE_CHECK_START,
    DEFAULT_MAINTENANCE_CHECK_END,
    DEFAULT_MAINTENANCE_CHECK_INTERVAL,
)

# 推送回调：接收一条文本消息，负责发送到群聊等平台
PushCallback = Callable[[str], Awaitable[None]]


class ServerMonitor:
    """服务器维护监控器

    每天固定窗口内周期性检查指定服务器状态：
    - 服务器在窗口内出现过离线（进入维护），之后恢复在线时推送开服消息
    - 每服每天只推送一次；到窗口结束仍未恢复则静默结束
    - 服务器一直在线（维护延期/取消）时不推送
    """

    def __init__(
        self,
        esi_client: ESIClient,
        push_callback: PushCallback,
        server_keys: Optional[List[str]] = None,
        check_start: str = DEFAULT_MAINTENANCE_CHECK_START,
        check_end: str = DEFAULT_MAINTENANCE_CHECK_END,
        interval_minutes: int = DEFAULT_MAINTENANCE_CHECK_INTERVAL,
    ):
        self.esi_client = esi_client
        self.push_callback = push_callback
        self.server_keys = list(server_keys) if server_keys else list(MAINTENANCE_MONITOR_SERVERS)
        self.check_start = check_start
        self.check_end = check_end
        try:
            self.interval_minutes = max(1, int(interval_minutes))
        except (ValueError, TypeError):
            self.interval_minutes = DEFAULT_MAINTENANCE_CHECK_INTERVAL

        # 每日状态追踪
        self._seen_offline: Dict[str, bool] = {}
        self._notified: Dict[str, bool] = {}
        self._last_online: Dict[str, Optional[bool]] = {}
        self._last_players: Dict[str, int] = {}
        self._last_check_time: Optional[datetime] = None
        self._push_log: List[str] = []
        self._reset_daily()

    def _reset_daily(self):
        """重置每日追踪状态（每个监控窗口开始时调用）"""
        self._seen_offline = {k: False for k in self.server_keys}
        self._notified = {k: False for k in self.server_keys}
        self._last_online = {k: None for k in self.server_keys}
        self._last_players = {k: 0 for k in self.server_keys}
        self._last_check_time = None
        self._push_log = []

    # ==================== 主循环 ====================

    async def run(self):
        """主循环：窗口外休眠，窗口内监控，每天重复"""
        while True:
            wait = self._seconds_until(self.check_start)
            next_start = datetime.now() + timedelta(seconds=wait)
            servers = "、".join(SERVER_NAMES.get(k, k) for k in self.server_keys)
            logger.info(
                f"[EVE Market] 维护监控将在 {next_start.strftime('%Y-%m-%d %H:%M')} 启动"
                f"（窗口 {self.check_start}–{self.check_end}，每 {self.interval_minutes} 分钟"
                f"检查 {servers}）"
            )
            await asyncio.sleep(wait)
            self._reset_daily()
            await self._monitor_window()

    async def _monitor_window(self):
        """窗口内循环检查，直到窗口结束"""
        interval = self.interval_minutes * 60
        while not self._window_ended():
            await self._check_once()
            await asyncio.sleep(interval)
        logger.info(
            f"[EVE Market] 维护监控窗口结束（{self.check_end}），"
            f"今日推送 {len(self._push_log)} 条开服消息"
        )

    def _window_ended(self) -> bool:
        """当前是否已过窗口结束时刻（结束时刻配置非法时视为已结束）"""
        end = self._parse_hm(self.check_end)
        if end is None:
            return True
        now = datetime.now()
        end_dt = now.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
        return now >= end_dt

    # ==================== 检查与推送 ====================

    async def _check_once(self):
        """检查一轮所有被监控服务器"""
        self._last_check_time = datetime.now()
        tasks = [self._fetch_status(k) for k in self.server_keys]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for key, result in zip(self.server_keys, results):
            if isinstance(result, Exception):
                logger.warning(
                    f"[EVE Market] 维护监控查询 {SERVER_NAMES.get(key, key)} 失败：{result}"
                )
                continue
            await self._handle_status(key, result)

    async def _fetch_status(self, server_key: str) -> ServerStatus:
        return await self.esi_client.fetch_server_status(server_key)

    async def _handle_status(self, key: str, status: ServerStatus):
        """处理单服状态：记录离线，并在离线恢复时推送"""
        self._last_online[key] = status.is_online
        self._last_players[key] = status.players
        if not status.is_online:
            self._seen_offline[key] = True
        elif self._seen_offline[key] and not self._notified[key]:
            await self._notify(key, status)

    async def _notify(self, key: str, status: ServerStatus):
        """推送开服消息（每服每天至多一次）"""
        self._notified[key] = True
        name = SERVER_NAMES.get(key, key)
        lines = [
            f"🟢 {name}服维护结束，已开服！",
            f"当前在线玩家：{status.players:,} 人",
        ]
        if status.server_version:
            lines.append(f"服务器版本：{status.server_version}")
        try:
            await self.push_callback("\n".join(lines))
            self._push_log.append(f"{datetime.now().strftime('%H:%M')} {name}")
            logger.info(f"[EVE Market] 已推送{name}服开服消息")
        except Exception as e:
            logger.error(f"[EVE Market] {name}服开服推送失败：{e}")

    # ==================== 状态查询（供「维护监控」指令） ====================

    def get_status_text(self) -> str:
        """生成监控状态文本"""
        servers = "、".join(SERVER_NAMES.get(k, k) for k in self.server_keys)
        lines = [
            "🛠️ 维护监控状态",
            f"监控服务器：{servers}",
            f"监控窗口：{self.check_start} – {self.check_end}，每 {self.interval_minutes} 分钟检查",
        ]

        now = datetime.now()
        start = self._parse_hm(self.check_start)
        end = self._parse_hm(self.check_end)
        if start and end:
            cur = (now.hour, now.minute)
            in_window = start <= cur < end
        else:
            in_window = False
        lines.append(f"运行状态：{'窗口监控中' if in_window else '窗口外（休眠中）'}")

        if self._last_check_time:
            lines.append(f"上次检查：{self._last_check_time.strftime('%H:%M:%S')}")

        for key in self.server_keys:
            name = SERVER_NAMES.get(key, key)
            online = self._last_online[key]
            if online is None:
                state = "状态未知"
            elif online:
                state = f"🟢 在线（{self._last_players[key]:,} 人）"
            else:
                state = "🔴 离线/维护中"
            if self._notified[key]:
                progress = "已推送开服消息 ✅"
            elif self._seen_offline[key]:
                progress = "维护中，等待恢复"
            else:
                progress = "未进入维护"
            lines.append(f"{name}：{state}｜{progress}")

        if self._push_log:
            lines.append("今日推送：" + "、".join(self._push_log))

        return "\n".join(lines)

    # ==================== 工具 ====================

    @staticmethod
    def _parse_hm(time_str: str) -> Optional[tuple]:
        """解析 "HH:MM"，返回 (hour, minute)，失败返回 None"""
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

    def _seconds_until(self, time_str: str) -> float:
        """距离指定时刻的秒数（今天已过则算明天）"""
        parsed = self._parse_hm(time_str)
        if not parsed:
            return 3600.0
        now = datetime.now()
        target = now.replace(hour=parsed[0], minute=parsed[1], second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()
