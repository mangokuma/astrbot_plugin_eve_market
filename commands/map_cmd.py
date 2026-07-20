"""地图指令 — 安全地图(aqdt) / 势力图(slt)"""

from ..data.image_manager import ImageManager
from ..utils.constants import SERVER_NAMES


class MapCommand:
    """地图指令处理器"""

    def __init__(self, image_manager: ImageManager):
        self.image_manager = image_manager

    async def handle_safemap(self, server: str) -> dict:
        """处理安全地图指令

        Args:
            server: "serenity" / "infinity"

        Returns:
            {"type": "image", "path": str} 或 {"type": "text", "message": str}
        """
        # 如果本地没有，先尝试下载
        if not self.image_manager.is_safemap_exists(server):
            success = await self.image_manager.update_safemap(server)
            if not success:
                return {
                    "type": "text",
                    "message": f"❌ 获取{SERVER_NAMES[server]}安全地图失败，请稍后重试"
                }

        path = self.image_manager.get_safemap_path(server)
        if path:
            return {"type": "image", "path": path}

        return {
            "type": "text",
            "message": f"❌ {SERVER_NAMES[server]}安全地图暂不可用"
        }

    async def handle_influence(self, server: str) -> dict:
        """处理势力图指令

        Args:
            server: "serenity" / "infinity"

        Returns:
            {"type": "image", "path": str} 或 {"type": "text", "message": str}
        """
        # 如果本地没有，先尝试下载
        if not self.image_manager.is_influence_exists(server):
            success = await self.image_manager.update_influence(server)
            if not success:
                return {
                    "type": "text",
                    "message": f"❌ 获取{SERVER_NAMES[server]}势力图失败，请稍后重试"
                }

        path = self.image_manager.get_influence_path(server)
        if path:
            return {"type": "image", "path": path}

        return {
            "type": "text",
            "message": f"❌ {SERVER_NAMES[server]}势力图暂不可用"
        }
