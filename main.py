"""EVE Market 插件主入口（适配 AstrBot v4.x 新 API）"""

import asyncio
import re

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api import logger
import astrbot.api.message_components as Comp
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

from .data.db import Database
from .data.item_manager import ItemManager
from .data.alias_manager import AliasManager
from .data.image_manager import ImageManager
from .data.group_manager import GroupManager
from .data.server_monitor import ServerMonitor
from .commands.server_status import ServerStatusCommand
from .commands.price_query import PriceQueryCommand
from .commands.alias_cmd import AliasCommand
from .commands.map_cmd import MapCommand
from .commands.group_cmd import GroupCommand
from .commands.update_cmd import UpdateCommand
from .utils.constants import (
    DEFAULT_AUTO_UPDATE_TIME,
    DEFAULT_UPDATE_RETRY_MINUTES,
    MAINTENANCE_MONITOR_SERVERS,
    DEFAULT_MAINTENANCE_CHECK_START,
    DEFAULT_MAINTENANCE_CHECK_END,
    DEFAULT_MAINTENANCE_CHECK_INTERVAL,
)


class EVEMarketPlugin(Star):
    """EVE 三服市场查询插件"""

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)

        # 读取插件配置
        # 优先使用 AstrBot 插件配置管理（_conf_schema.json，可在 WebUI 可视化配置）；
        # 兼容旧版：未提供 _conf_schema.json 时回退到全局配置的 plugins.eve_market 段
        if config is not None:
            self.config = dict(config)
        else:
            self.config = {}
            try:
                legacy = context.get_config() or {}
                if isinstance(legacy, dict):
                    plugins_conf = legacy.get("plugins") or {}
                    self.config = (
                        plugins_conf.get("eve_market")
                        or legacy.get("eve_market")
                        or {}
                    )
            except Exception:
                self.config = {}

        # 配置项：每天自动更新时刻（HH:MM），空字符串表示禁用
        self.auto_update_time = self.config.get(
            "auto_update_time",
            DEFAULT_AUTO_UPDATE_TIME
        )
        # 兼容旧配置：auto_update_interval 设为 0 表示禁用自动更新
        if self.config.get("auto_update_interval") == 0:
            self.auto_update_time = ""

        # 配置项：自动更新失败后的重试间隔（分钟）
        self.update_retry_minutes = self.config.get(
            "update_retry_minutes",
            DEFAULT_UPDATE_RETRY_MINUTES
        )

        # 配置项：每日维护监控（晨曦/曙光 11:00 例行维护，恢复后推送开服消息）
        self.maintenance_monitor_enabled = bool(
            self.config.get("maintenance_monitor_enabled", True)
        )
        notify_groups = self.config.get("maintenance_notify_groups", [])
        if isinstance(notify_groups, (str, int)):
            notify_groups = [notify_groups]
        self.maintenance_notify_groups = [
            str(g).strip() for g in notify_groups if str(g).strip()
        ]
        self.maintenance_check_start = self.config.get(
            "maintenance_check_start", DEFAULT_MAINTENANCE_CHECK_START
        )
        self.maintenance_check_end = self.config.get(
            "maintenance_check_end", DEFAULT_MAINTENANCE_CHECK_END
        )
        self.maintenance_check_interval = self.config.get(
            "maintenance_check_interval", DEFAULT_MAINTENANCE_CHECK_INTERVAL
        )

        # 配置项：模糊搜索
        self.fuzzy_match = bool(self.config.get("fuzzy_match", True))
        self.max_search_results = self.config.get("max_search_results", 6)
        self.fuzzy_pattern = self.config.get("fuzzy_pattern", "contains")
        self.min_confidence = self.config.get("min_confidence", 50)

        # 插件数据目录：AstrBot data/plugin_data/eve_market
        # 数据库与图片缓存统一存放于此，可通过 config 覆盖数据库路径
        self.plugin_data_dir = StarTools.get_data_dir("eve_market")
        db_path = self.config.get("db_path") or str(self.plugin_data_dir / "eve_items.db")
        image_cache_dir = str(self.plugin_data_dir / "images")

        # 初始化数据层
        self.db = Database(db_path=db_path)
        self.item_manager = ItemManager(
            self.db,
            auto_update_time=self.auto_update_time,
            retry_minutes=self.update_retry_minutes
        )
        self.alias_manager = AliasManager(self.db)
        self.group_manager = GroupManager(self.db)
        self.image_manager = ImageManager(cache_dir=image_cache_dir)

        # 初始化指令层
        self.server_status_cmd = ServerStatusCommand()
        self.price_query_cmd = PriceQueryCommand(
            self.item_manager,
            self.alias_manager,
            self.group_manager,
            fuzzy_match=self.fuzzy_match,
            max_results=self.max_search_results,
            fuzzy_pattern=self.fuzzy_pattern,
            min_confidence=self.min_confidence,
        )
        self.alias_cmd = AliasCommand(self.alias_manager)
        self.group_cmd = GroupCommand(self.group_manager)
        self.update_cmd = UpdateCommand(self.item_manager)
        self.map_cmd = MapCommand(self.image_manager)

        # 每日维护监控：恢复在线后推送开服消息到指定群聊
        self.server_monitor = None
        if self.maintenance_monitor_enabled:
            if self.maintenance_notify_groups:
                self.server_monitor = ServerMonitor(
                    esi_client=self.server_status_cmd.esi_client,
                    push_callback=self._make_push_callback(),
                    server_keys=list(MAINTENANCE_MONITOR_SERVERS),
                    check_start=self.maintenance_check_start,
                    check_end=self.maintenance_check_end,
                    interval_minutes=self.maintenance_check_interval,
                )
            else:
                logger.warning(
                    "[EVE Market] 维护监控已启用但未配置 maintenance_notify_groups，"
                    "开服消息将无法推送"
                )

        # 后台任务
        self._auto_update_task = None
        self._safemap_task = None
        self._influence_task = None
        self._monitor_task = None

        logger.info("[EVE Market] 插件初始化完成")

    def _make_push_callback(self):
        """构造开服推送回调：向所有配置的群聊发送消息"""
        async def _push(msg: str):
            for gid in self.maintenance_notify_groups:
                try:
                    await self.context.send_message(
                        f"aiocqhttp:GroupMessage:{gid}",
                        [Comp.Plain(msg)],
                    )
                except Exception as e:
                    logger.error(f"[EVE Market] 推送开服消息到群 {gid} 失败：{e}")
        return _push

    async def initialize(self):
        """插件初始化（AstrBot 调用）"""
        # 首次启动时检查并更新物品数据
        item_count = self.item_manager.get_item_count()
        if item_count == 0:
            logger.info("[EVE Market] 首次启动，正在下载物品数据...")
            success, msg = await self.item_manager.update_items(trigger="init")
            logger.info(f"[EVE Market] {msg}")
        else:
            last_update = self.item_manager.get_last_update_time()
            logger.info(f"[EVE Market] 物品数据已存在，共 {item_count} 条，上次更新：{last_update}")

        # 启动物品数据自动更新（每天固定时刻）
        self._auto_update_task = asyncio.create_task(
            self.item_manager.auto_update_scheduler()
        )

        # 首次启动时下载安全地图和势力图
        logger.info("[EVE Market] 正在下载安全地图...")
        await self.image_manager.update_all_safemaps()
        logger.info("[EVE Market] 正在下载势力图...")
        await self.image_manager.update_all_influences()

        # 启动安全地图定时更新（每天 00:31）
        self._safemap_task = asyncio.create_task(
            self.image_manager.safemap_scheduler()
        )

        # 启动势力图定时更新（每天 12:41）
        self._influence_task = asyncio.create_task(
            self.image_manager.influence_scheduler()
        )

        # 启动每日维护监控（晨曦/曙光 11:00 例行维护）
        if self.server_monitor:
            self._monitor_task = asyncio.create_task(self.server_monitor.run())

        logger.info("[EVE Market] 所有后台任务已启动")

    async def terminate(self):
        """插件卸载（AstrBot 调用）"""
        tasks = [
            ("auto_update", self._auto_update_task),
            ("safemap", self._safemap_task),
            ("influence", self._influence_task),
            ("maintenance_monitor", self._monitor_task),
        ]

        for name, task in tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info(f"[EVE Market] {name} 任务已取消")

        logger.info("[EVE Market] 插件已卸载")

    # ==================== 工具方法 ====================

    # 适配器可能附加的尾部标记，如 " [MSG_ID:1462389253]"
    _MSG_TAIL_RE = re.compile(r"\s*\[MSG_ID:\d+\]\s*$")

    @classmethod
    def _extract_args(cls, event: AstrMessageEvent, cmd: str) -> str:
        """从消息中提取指令参数

        message_str 形如 "nj 三钛合金"（不含指令前缀），去掉首个指令词，
        并剥离适配器附加的 [MSG_ID:xxx] 等尾部标记
        """
        text = (event.message_str or "").strip()
        # 剥离 [MSG_ID:xxx] 尾部标记（引用消息时由适配器附加）
        text = cls._MSG_TAIL_RE.sub("", text).strip()
        parts = text.split(maxsplit=1)
        if not parts:
            return ""
        # 如果首词就是指令本身，去掉它
        if parts[0].lstrip("/").lower() == cmd.lower():
            return parts[1].strip() if len(parts) > 1 else ""
        # 否则整体视为参数
        return text

    async def _check_admin(self, event: AstrMessageEvent) -> tuple[bool, str]:
        """校验管理权限：群聊中仅群主/管理员可用，私聊放行

        Returns:
            (是否允许, 拒绝提示文本)
        """
        group_id = event.get_group_id()
        if not group_id:
            return True, ""
        if not isinstance(event, AiocqhttpMessageEvent):
            return False, "❌ 当前平台不支持权限校验，请在私聊中使用"
        sender_id = event.get_sender_id()
        try:
            members = await event.bot.get_group_member_list(group_id=group_id)
        except Exception as e:
            return False, f"❌ 获取群成员信息失败：{e}"
        for m in members:
            if str(m.get("user_id")) == sender_id and m.get("role") in ("owner", "admin"):
                return True, ""
        return False, "❌ 仅群主/管理员可使用此指令"

    # ==================== 指令注册 ====================

    @filter.command("ss")
    async def cmd_server_status(self, event: AstrMessageEvent):
        """查询 EVE 三服服务器状态"""
        result = await self.server_status_cmd.handle()
        yield event.plain_result(result)

    @filter.command("nj")
    async def cmd_tranquility_price(self, event: AstrMessageEvent):
        """查询宁静服物品价格"""
        args = self._extract_args(event, "nj")
        if not args:
            yield event.plain_result("❌ 用法：nj <物品名>")
            return
        result = await self.price_query_cmd.handle("tranquility", args)
        yield event.plain_result(result)

    @filter.command("cx")
    async def cmd_serenity_price(self, event: AstrMessageEvent):
        """查询晨曦服物品价格"""
        args = self._extract_args(event, "cx")
        if not args:
            yield event.plain_result("❌ 用法：cx <物品名>")
            return
        result = await self.price_query_cmd.handle("serenity", args)
        yield event.plain_result(result)

    @filter.command("sg")
    async def cmd_infinity_price(self, event: AstrMessageEvent):
        """查询曙光服物品价格"""
        args = self._extract_args(event, "sg")
        if not args:
            yield event.plain_result("❌ 用法：sg <物品名>")
            return
        result = await self.price_query_cmd.handle("infinity", args)
        yield event.plain_result(result)

    @filter.command("简称")
    async def cmd_alias(self, event: AstrMessageEvent):
        """物品别名管理"""
        args = self._extract_args(event, "简称")
        result = await self.alias_cmd.handle(args)
        yield event.plain_result(result)

    @filter.command("物品组")
    async def cmd_group(self, event: AstrMessageEvent):
        """物品组管理"""
        args = self._extract_args(event, "物品组")
        result = await self.group_cmd.handle(args)
        yield event.plain_result(result)

    @filter.command("更新物品")
    async def cmd_update_items(self, event: AstrMessageEvent):
        """手动更新物品数据（仅群主/管理员）"""
        allowed, deny_msg = await self._check_admin(event)
        if not allowed:
            yield event.plain_result(deny_msg)
            return
        yield event.plain_result("📥 开始更新物品数据，请稍候...")
        result = await self.update_cmd.handle_update()
        yield event.plain_result(result)

    @filter.command("更新状态")
    async def cmd_update_status(self, event: AstrMessageEvent):
        """查询物品数据更新状态"""
        result = self.update_cmd.handle_status()
        yield event.plain_result(result)

    @filter.command("维护监控")
    async def cmd_maintenance_monitor(self, event: AstrMessageEvent):
        """查询每日维护监控状态"""
        if not self.server_monitor:
            yield event.plain_result(
                "⚠️ 维护监控未启用（已禁用或未配置 maintenance_notify_groups）"
            )
            return
        yield event.plain_result(self.server_monitor.get_status_text())

    # ==================== 地图指令 ====================

    @filter.command("aqdt")
    async def cmd_serenity_safemap(self, event: AstrMessageEvent):
        """晨曦安全地图"""
        result = await self.map_cmd.handle_safemap("serenity")
        if result["type"] == "image":
            yield event.plain_result("📍 晨曦安全地图")
            yield event.image_result(result["path"])
        else:
            yield event.plain_result(result["message"])

    @filter.command("aqdt_sg")
    async def cmd_infinity_safemap(self, event: AstrMessageEvent):
        """曙光安全地图"""
        result = await self.map_cmd.handle_safemap("infinity")
        if result["type"] == "image":
            yield event.plain_result("📍 曙光安全地图")
            yield event.image_result(result["path"])
        else:
            yield event.plain_result(result["message"])

    @filter.command("slt")
    async def cmd_serenity_influence(self, event: AstrMessageEvent):
        """晨曦势力图"""
        result = await self.map_cmd.handle_influence("serenity")
        if result["type"] == "image":
            yield event.plain_result("⚔️ 晨曦势力图")
            yield event.image_result(result["path"])
        else:
            yield event.plain_result(result["message"])

    @filter.command("slt_sg")
    async def cmd_infinity_influence(self, event: AstrMessageEvent):
        """曙光势力图"""
        result = await self.map_cmd.handle_influence("infinity")
        if result["type"] == "image":
            yield event.plain_result("⚔️ 曙光势力图")
            yield event.image_result(result["path"])
        else:
            yield event.plain_result(result["message"])
