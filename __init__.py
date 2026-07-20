"""EVE Market 插件入口"""

try:
    from .main import EVEMarketPlugin
    __all__ = ["EVEMarketPlugin"]
except ImportError:
    # AstrBot 未安装时（如独立测试环境），不导出主类
    __all__ = []
