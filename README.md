# EVE Market — AstrBot 插件

EVE Online 三服（宁静 / 晨曦 / 曙光）市场查询插件，基于 AstrBot Plugin API。

## 功能

| 指令 | 说明 |
|------|------|
| `ss` | 查询三服服务器状态 |
| `nj <物品>` | 查询宁静服物品价格（吉他） |
| `cx <物品>` | 查询晨曦服物品价格（吉他） |
| `sg <物品>` | 查询曙光服物品价格（索巴色基） |
| `简称 add <别名> <目标>` | 添加物品别名 |
| `简称 del <别名>` | 删除别名 |
| `简称 list` | 列出所有别名 |
| `物品组 add <组名> <前缀>` | 添加物品组（按名称前缀聚合） |
| `物品组 del <组名>` | 删除物品组 |
| `物品组 list` | 列出所有物品组 |
| `更新物品` | 手动更新物品数据（仅群主/管理员，私聊不限） |
| `更新状态` | 查询物品数据更新状态 |
| `维护监控` | 查询每日维护监控状态（晨曦/曙光） |
| `aqdt` / `aqdt_sg` | 晨曦 / 曙光安全地图 |
| `slt` / `slt_sg` | 晨曦 / 曙光势力图 |

## 特性

- 物品数据每天固定时刻自动更新（默认 05:07，可配置，CEVE Market evedata.xlsx），失败自动重试
- 每日维护监控：晨曦/曙光每天 11:00 例行维护，监控窗口内（默认 11:01–15:00，每 1 分钟）检测到服务器离线后恢复在线时，自动向指定会话推送开服消息（每服每天一次）
- `更新物品` 指令可随时手动更新，与自动更新互斥（不会并发清空数据）
- 非连续子串模糊搜索，可信度阈值可配置（默认 ≥50%），最多展示 6 个结果
- 模糊多结果直接展示全部物品的最高收单 / 最低卖单
- 物品组：按名称前缀聚合，查询组名即展示组内全部物品价格
- 别名与物品组独立存储于 SQLite，物品数据更新不丢失
- 安全地图每天 00:31、势力图每天 12:41 自动更新
- 全链路异步 IO

## 配置

自 v1.5.0 起，配置统一通过 **AstrBot 内置插件配置管理** 进行：

1. 打开 AstrBot WebUI →「插件管理」→ 找到 `eve_market` → 点击「设置」
2. AstrBot 会自动生成 `data/config/<插件目录名>_config.json`（首次打开时以默认值填充），可视化修改即可，保存后重载插件生效

配置项说明：

- `db_path`：物品数据库路径，留空使用默认（`data/plugin_data/eve_market/eve_items.db`）
- `auto_update_time`：每天自动更新物品数据的时刻（HH:MM），默认 `05:07`，留空禁用
- `update_retry_minutes`：自动更新失败后的重试间隔（分钟），默认 30
- `fuzzy_match`：模糊搜索开关，默认开启
- `max_search_results`：模糊搜索最多展示的结果数，默认 6
- `fuzzy_pattern`：匹配模式（`contains` 包含 / `starts_with` 开头 / `ends_with` 结尾），默认 `contains`
- `min_confidence`：模糊搜索可信度阈值（%），默认 50
- `maintenance_monitor_enabled`：每日维护监控开关，默认开启
- `maintenance_notify_groups`：开服推送会话列表，填写 AstrBot SID（如 `aiocqhttp:GroupMessage:123456789`），**留空则不启用监控推送**；直接填 QQ 群号也可，会自动补 aiocqhttp 群消息前缀
- `maintenance_check_start` / `maintenance_check_end`：监控窗口（HH:MM），默认 `11:01` – `15:00`
- `maintenance_check_interval`：检查间隔（分钟），默认 1

> 兼容说明：若通过旧方式（全局配置 `plugins.eve_market` 段）提供配置，插件仍会读取作为回退；但推荐统一使用 WebUI 插件设置管理。

## 安装

将本目录放入 AstrBot 的 `data/plugins/` 下，重启或重载插件后，在 WebUI「插件管理」中进入 `eve_market` 的「设置」页填写配置（首次打开会自动生成默认配置文件）。

## 依赖

`aiohttp` / `pandas` / `openpyxl`

## 数据来源

- ESI：https://esi.evetech.net
- 网易 ESI：https://ali-esi.evepc.163.com
- CEVE Market：https://www.ceve-market.org
