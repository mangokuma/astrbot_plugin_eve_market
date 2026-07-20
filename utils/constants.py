"""全局常量配置"""

# ============================================
# EVE ESI 服务器状态 API
# ============================================
ESI_URLS = {
    "tranquility": "https://esi.evetech.net/status",
    "serenity": "https://ali-esi.evepc.163.com/latest/status/?datasource=serenity",
    "infinity": "https://ali-esi.evepc.163.com/latest/status/?datasource=infinity",
}

# ============================================
# CEVE Market 价格查询 API
# ============================================
CEVE_API_URLS = {
    "tranquility": "https://www.ceve-market.org/tqapi/",
    "serenity": "https://www.ceve-market.org/api/",
    "infinity": "https://www.ceve-market.org/infapi/",
}

# ============================================
# 默认交易星域 Region ID
# ============================================
DEFAULT_REGION_IDS = {
    "tranquility": 10000002,   # 吉他
    "serenity": 10000002,      # 吉他
    "infinity": 10000016,      # 长征 (索巴色基所在星域)
}

# ============================================
# 服务器名称映射
# ============================================
SERVER_NAMES = {
    "tranquility": "宁静",
    "serenity": "晨曦",
    "infinity": "曙光",
}

SERVER_KEYS = ["tranquility", "serenity", "infinity"]

# ============================================
# 物品数据下载
# ============================================
ITEM_DUMP_URL = "https://www.ceve-market.org/dumps/evedata.xlsx"

# ============================================
# 安全地图图片 URL
# ============================================
SAFEMAP_URLS = {
    "serenity": "https://www.ceve-market.org/dumps/safemap/last.png",
    "infinity": "https://www.ceve-market.org/dumps/safemap_inf/last.png",
}

# ============================================
# 势力图图片 URL
# ============================================
INFLUENCE_URLS = {
    "serenity": "https://www.ceve-market.org/dumps/safemap/last.png",
    "infinity": "https://www.ceve-market.org/dumps/archive_inf/influence.png",
}

# ============================================
# 图片缓存目录
# ============================================
DEFAULT_IMAGE_CACHE_DIR = "./data/images"

# ============================================
# 定时任务配置（cron 格式：分 时）
# ============================================
SAFEMAP_UPDATE_CRON = "31 0"      # 每天 00:31
INFLUENCE_UPDATE_CRON = "41 12"  # 每天 12:41

# ============================================
# 搜索配置
# ============================================
DEFAULT_MAX_RESULTS = 6
DEFAULT_FUZZY_MATCH = True

# 模糊匹配模式
FUZZY_PATTERNS = {
    "contains": lambda kw: f"%{kw}%",
    "starts_with": lambda kw: f"{kw}%",
    "ends_with": lambda kw: f"%{kw}",
}

# 默认模糊模式
DEFAULT_FUZZY_PATTERN = "contains"

# 模糊搜索可信度最低阈值（百分比）
DEFAULT_MIN_CONFIDENCE = 50

# ============================================
# 数据库配置
# ============================================
DEFAULT_DB_PATH = "./data/eve_items.db"

# ============================================
# 自动更新配置
# ============================================
DEFAULT_AUTO_UPDATE_INTERVAL = 86400  # 秒，默认每天
