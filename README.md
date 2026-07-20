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
| `aqdt` / `aqdt_sg` | 晨曦 / 曙光安全地图 |
| `slt` / `slt_sg` | 晨曦 / 曙光势力图 |

## 特性

- 物品数据每日自动更新（CEVE Market evedata.xlsx）
- 非连续子串模糊搜索，可信度阈值可配置（默认 ≥50%），最多展示 6 个结果
- 别名独立存储于 SQLite，物品数据更新不丢失
- 安全地图每天 00:31、势力图每天 12:41 自动更新
- 全链路异步 IO

## 安装

将本目录放入 AstrBot 的 `data/plugins/` 下，并在 AstrBot 配置中添加（参见 `config.yaml` 示例）。

## 依赖

`aiohttp` / `pandas` / `openpyxl`

## 数据来源

- ESI：https://esi.evetech.net
- 网易 ESI：https://ali-esi.evepc.163.com
- CEVE Market：https://www.ceve-market.org
