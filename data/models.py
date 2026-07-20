"""数据模型定义"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ServerStatus:
    """EVE 服务器状态"""
    server_key: str          # "tranquility" / "serenity" / "infinity"
    server_name: str         # "宁静" / "晨曦" / "曙光"
    is_online: bool
    players: int = 0
    server_version: Optional[str] = None
    start_time: Optional[str] = None   # 服务器启动时间（ESI start_time，ISO 格式）
    vip: Optional[bool] = None         # ESI vip 标识（仅部分服务器返回）


@dataclass
class Item:
    """EVE 物品"""
    type_id: int
    name: str
    group_id: Optional[int] = None
    category_id: Optional[int] = None
    market_group_id: Optional[int] = None
    volume: Optional[float] = None
    mass: Optional[float] = None


@dataclass
class PriceInfo:
    """价格信息"""
    server_key: str
    server_name: str
    item_name: str
    buy_max: Optional[float] = None
    sell_min: Optional[float] = None
    volume: Optional[int] = None


@dataclass
class Alias:
    """物品别名"""
    id: int
    alias_name: str
    target_name: str
    created_at: datetime
