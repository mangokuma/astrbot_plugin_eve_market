"""消息格式化工具"""

from typing import List, Optional
from ..data.models import ServerStatus, Item, PriceInfo, Alias


def _format_start_time(iso_time: Optional[str]) -> str:
    """将 ESI 的 ISO 启动时间转为易读格式（UTC+8）"""
    if not iso_time:
        return "未知"
    try:
        from datetime import datetime, timezone, timedelta
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        dt_cn = dt.astimezone(timezone(timedelta(hours=8)))
        return dt_cn.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_time


def format_server_status(statuses: List[ServerStatus]) -> str:
    """格式化三服状态查询结果"""
    lines = ["📡 EVE 服务器状态", "─" * 30]

    for status in statuses:
        # VIP 标识：ESI 返回 vip=true 时显示
        vip_badge = " 💎VIP" if status.vip else ""

        if status.is_online:
            icon = "🟢"
            state_text = "在线"
        else:
            icon = "🔴"
            state_text = "离线"

        lines.append(f"{icon} {status.server_name}{vip_badge}：{state_text}")
        if status.is_online:
            lines.append(f"   👥 在线人数：{status.players:,}")
            lines.append(f"   🕐 启动时间：{_format_start_time(status.start_time)}")
            if status.server_version:
                lines.append(f"   📦 版本：{status.server_version}")
        lines.append("")

    return "\n".join(lines)


def _price_line(name: str, price: Optional[PriceInfo]) -> str:
    """单个物品的一行价格：📥 最高收单 / 📤 最低卖单"""
    if price is None:
        return f"• {name}：查询失败"
    buy_max = format_isk(price.buy_max) if price.buy_max is not None else "无订单"
    sell_min = format_isk(price.sell_min) if price.sell_min is not None else "无订单"
    return f"• {name}：📥{buy_max} / 📤{sell_min}"


def format_price_result(prices: List[PriceInfo], item_name: str) -> str:
    """格式化单个物品价格查询结果（只展示最高收单与最低卖单）"""
    if not prices:
        return f"❌ 未找到物品「{item_name}」的价格信息"

    price = prices[0]

    # 无订单时显示"无订单"
    buy_max = format_isk(price.buy_max) if price.buy_max is not None else "无订单"
    sell_min = format_isk(price.sell_min) if price.sell_min is not None else "无订单"

    lines = [
        f"💰 {price.server_name} — {item_name}",
        "─" * 30,
        f"📥 最高收单：{buy_max}",
        f"📤 最低卖单：{sell_min}",
    ]

    return "\n".join(lines)


def format_multi_price_results(entries: List[tuple], keyword: str, server_name: str) -> str:
    """格式化多个物品的价格列表（模糊搜索多结果）

    Args:
        entries: [(Item, Optional[PriceInfo]), ...]
        keyword: 搜索关键词
        server_name: 服务器名称
    """
    lines = [
        f"🔍 「{keyword}」匹配到 {len(entries)} 个物品（{server_name}）：",
        "─" * 30,
    ]

    for item, price in entries:
        lines.append(_price_line(item.name, price))

    lines.append("")
    lines.append("💡 可使用别名简化查询：")
    lines.append(f'   简称 add <别名> "{entries[0][0].name}"')
    lines.append("💡 或将同前缀物品设为物品组：")
    lines.append("   物品组 add <组名> <名称前缀>")

    return "\n".join(lines)


def format_group_price_result(group_name: str, prefix: str, entries: List[tuple], server_name: str) -> str:
    """格式化物品组价格列表

    Args:
        group_name: 组名
        prefix: 名称前缀
        entries: [(Item, Optional[PriceInfo]), ...]
        server_name: 服务器名称
    """
    lines = [
        f"📦 物品组「{group_name}」（{server_name}，前缀：{prefix}）",
        "─" * 30,
    ]

    for item, price in entries:
        lines.append(_price_line(item.name, price))

    return "\n".join(lines)


def format_group_list(groups) -> str:
    """格式化物品组列表"""
    if not groups:
        return "📭 暂无自定义物品组"

    lines = [
        f"📋 共 {len(groups)} 个物品组：",
        "─" * 30,
    ]

    for g in groups:
        lines.append(f"• {g.group_name}（前缀：{g.prefix}）")

    lines.append("")
    lines.append("💡 使用「物品组 del <组名>」删除物品组")

    return "\n".join(lines)


def format_group_added(group_name: str, prefix: str) -> str:
    """格式化添加物品组成功消息"""
    return (
        f"✅ 物品组添加成功！\n"
        f"   {group_name}（前缀：{prefix}）\n"
        f"\n"
        f"💡 现在可以使用「nj {group_name}」查看组内所有物品价格"
    )


def format_group_removed(group_name: str) -> str:
    """格式化删除物品组成功消息"""
    return f"✅ 物品组「{group_name}」已删除"


def format_item_candidates(items: List[Item], keyword: str) -> str:
    """格式化候选物品列表（模糊搜索结果）"""
    if not items:
        return f"❌ 未找到包含「{keyword}」的物品"

    lines = [
        f"🔍 找到 {len(items)} 个包含「{keyword}」的物品：",
        "─" * 30,
    ]

    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item.name}")

    lines.append("")
    lines.append("💡 请使用更精确的名称重新查询，或添加别名：")
    lines.append(f'   简称 add <别名> "{items[0].name}"')

    return "\n".join(lines)


def format_alias_list(aliases: List[Alias]) -> str:
    """格式化别名列表"""
    if not aliases:
        return "📭 暂无自定义别名"

    lines = [
        f"📋 共 {len(aliases)} 个别名：",
        "─" * 30,
    ]

    for alias in aliases:
        lines.append(f"• {alias.alias_name} → {alias.target_name}")

    lines.append("")
    lines.append("💡 使用「简称 del <别名>」删除别名")

    return "\n".join(lines)


def format_alias_added(alias_name: str, target_name: str) -> str:
    """格式化添加别名成功消息"""
    return (
        f"✅ 别名添加成功！\n"
        f"   {alias_name} → {target_name}\n"
        f"\n"
        f"💡 现在可以直接使用「nj {alias_name}」查询价格"
    )


def format_alias_removed(alias_name: str) -> str:
    """格式化删除别名成功消息"""
    return f"✅ 别名「{alias_name}」已删除"


def format_alias_resolved(alias_name: str, target_name: str) -> str:
    """格式化别名查询结果"""
    return f"📎 {alias_name} → {target_name}"


def format_isk(value: Optional[float]) -> str:
    """格式化 ISK 金额，使用千分位分隔符"""
    if value is None:
        return "N/A"

    return f"{value:,.2f}"
