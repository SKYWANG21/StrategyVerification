"""
MA20趋势跟踪策略 - 核心模块包（src 包入口）

【面向初学者】
从本包可以导入策略用到的主要类，便于在其他脚本中写：
  from src import DataFetcher, DataProcessor, SignalGenerator, RiskManager, PerformanceAnalyzer

各模块职责简要说明：
- DataFetcher:    从 Tushare / Akshare 获取期货日 K 线
- DataProcessor:   合成 2 日 K 线、计算 MA 与 K 线特征
- SignalGenerator: 根据 MA20 与 K 线颜色生成做多/做空/观望信号
- RiskManager:     计算止损价、仓位手数、移动止损
- PerformanceAnalyzer: 计算绩效指标、生成绩效报告与图表
"""

__all__ = [
    'DataFetcher',
    'DataProcessor', 
    'SignalGenerator',
    'RiskManager',
    'PerformanceAnalyzer'
]