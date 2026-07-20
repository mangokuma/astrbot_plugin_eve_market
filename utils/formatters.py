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


def format_price_result(prices: List[PriceInfo], item_name: str) -> str:
    """格式化价格查询结果"""
    if not prices:
        return f"❌ 未找到物品「{item_name}」的价格信息"

    price = prices[0]
    server_name = price.server_name

    # 无订单时显示"无订单"
    buy_max = format_isk(price.buy_max) if price.buy_max is not None else "无订单"
    sell_min = format_isk(price.sell_min) if price.sell_min is not None else "无订单"

    lines = [
        f"💰 {server_name} — {item_name}",
        "─" * 30,
        f"📥 最高收单：{buy_max:>15}",
        f"📤 最低卖单：{sell_min:>15}",
    ]

    if price.volume is not None:
        lines.append(f"📊 日成交量：{price.volume:>15,}")

    lines.append("")
    lines.append("💡 提示：价格数据来自 CEVE Market，可能存在延迟")

    return "\n".join(lines)


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
    """格式化 ISK 金额，自动适配单位"""
    if value is None:
        return "N/A"

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.2f} M"
    elif value >= 1_000:
        return f"{value / 1_000:.2f} K"
    else:
        return f"{value:.2f}"
