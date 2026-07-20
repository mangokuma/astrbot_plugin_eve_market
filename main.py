"""EVE Market 插件主入口"""

import asyncio
from astrbot.api.all import AstrBotMessage, CommandResult, Context, Star, filter
from astrbot.api import logger

from .data.db import Database
from .data.item_manager import ItemManager
from .data.alias_manager import AliasManager
from .data.image_manager import ImageManager
from .commands.server_status import ServerStatusCommand
from .commands.price_query import PriceQueryCommand
from .commands.alias_cmd import AliasCommand
from .commands.map_cmd import MapCommand
from .utils.constants import SERVER_NAMES, DEFAULT_AUTO_UPDATE_INTERVAL


class EVEMarketPlugin(Star):
    """EVE 三服市场查询插件"""

    def __init__(self, context: Context):
        super().__init__(context)

        # 读取插件配置
        self.config = context.get_config().get("eve_market", {})

        # 配置项：定时更新间隔（秒），默认每天
        self.auto_update_interval = self.config.get(
            "auto_update_interval",
            DEFAULT_AUTO_UPDATE_INTERVAL
        )

        # 配置项：数据库路径
        db_path = self.config.get("db_path", "./data/eve_items.db")

        # 初始化数据层
        self.db = Database(db_path=db_path)
        self.item_manager = ItemManager(
            self.db,
            auto_update_interval=self.auto_update_interval
        )
        self.alias_manager = AliasManager(self.db)
        self.image_manager = ImageManager()

        # 初始化指令层
        self.server_status_cmd = ServerStatusCommand()
        self.price_query_cmd = PriceQueryCommand(self.item_manager, self.alias_manager)
        self.alias_cmd = AliasCommand(self.alias_manager)
        self.map_cmd = MapCommand(self.image_manager)

        # 后台任务
        self._auto_update_task = None
        self._safemap_task = None
        self._influence_task = None

        logger.info("[EVE Market] 插件初始化完成")

    async def initialize(self):
        """插件初始化（AstrBot 调用）"""
        # 首次启动时检查并更新物品数据
        item_count = self.item_manager.get_item_count()
        if item_count == 0:
            logger.info("[EVE Market] 首次启动，正在下载物品数据...")
            success, msg = await self.item_manager.update_items()
            logger.info(f"[EVE Market] {msg}")
        else:
            last_update = self.item_manager.get_last_update_time()
            logger.info(f"[EVE Market] 物品数据已存在，共 {item_count} 条，上次更新：{last_update}")

        # 启动物品数据自动更新
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

        logger.info("[EVE Market] 所有后台任务已启动")

    async def terminate(self):
        """插件卸载（AstrBot 调用）"""
        tasks = [
            ("auto_update", self._auto_update_task),
            ("safemap", self._safemap_task),
            ("influence", self._influence_task),
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

    # ==================== 指令注册 ====================

    @filter.command("ss")
    async def cmd_server_status(self, message: AstrBotMessage) -> CommandResult:
        """查询 EVE 三服服务器状态"""
        result = await self.server_status_cmd.handle()
        return CommandResult().message(result)

    @filter.command("nj")
    async def cmd_tranquility_price(self, message: AstrBotMessage, args: str = "") -> CommandResult:
        """查询宁静服物品价格"""
        if not args.strip():
            return CommandResult().message("❌ 用法：nj <物品名>")
        result = await self.price_query_cmd.handle("tranquility", args.strip())
        return CommandResult().message(result)

    @filter.command("cx")
    async def cmd_serenity_price(self, message: AstrBotMessage, args: str = "") -> CommandResult:
        """查询晨曦服物品价格"""
        if not args.strip():
            return CommandResult().message("❌ 用法：cx <物品名>")
        result = await self.price_query_cmd.handle("serenity", args.strip())
        return CommandResult().message(result)

    @filter.command("sg")
    async def cmd_infinity_price(self, message: AstrBotMessage, args: str = "") -> CommandResult:
        """查询曙光服物品价格"""
        if not args.strip():
            return CommandResult().message("❌ 用法：sg <物品名>")
        result = await self.price_query_cmd.handle("infinity", args.strip())
        return CommandResult().message(result)

    @filter.command("简称")
    async def cmd_alias(self, message: AstrBotMessage, args: str = "") -> CommandResult:
        """物品别名管理"""
        result = await self.alias_cmd.handle(args)
        return CommandResult().message(result)

    # ==================== 地图指令 ====================

    @filter.command("aqdt")
    async def cmd_serenity_safemap(self, message: AstrBotMessage) -> CommandResult:
        """晨曦安全地图"""
        result = await self.map_cmd.handle_safemap("serenity")
        if result["type"] == "image":
            return CommandResult().message("📍 晨曦安全地图").use_image(result["path"])
        return CommandResult().message(result["message"])

    @filter.command("aqdt_sg")
    async def cmd_infinity_safemap(self, message: AstrBotMessage) -> CommandResult:
        """曙光安全地图"""
        result = await self.map_cmd.handle_safemap("infinity")
        if result["type"] == "image":
            return CommandResult().message("📍 曙光安全地图").use_image(result["path"])
        return CommandResult().message(result["message"])

    @filter.command("slt")
    async def cmd_serenity_influence(self, message: AstrBotMessage) -> CommandResult:
        """晨曦势力图"""
        result = await self.map_cmd.handle_influence("serenity")
        if result["type"] == "image":
            return CommandResult().message("⚔️ 晨曦势力图").use_image(result["path"])
        return CommandResult().message(result["message"])

    @filter.command("slt_sg")
    async def cmd_infinity_influence(self, message: AstrBotMessage) -> CommandResult:
        """曙光势力图"""
        result = await self.map_cmd.handle_influence("infinity")
        if result["type"] == "image":
            return CommandResult().message("⚔️ 曙光势力图").use_image(result["path"])
        return CommandResult().message(result["message"])
