"""myquant：模块化量化策略研发框架。

分层结构：``config`` 配置 → ``data`` 数据获取与清洗 → ``strategies`` 可插拔策略
→ ``backtest`` 回测与报告 → ``live`` 实盘模拟（骨架）。统一入口为 ``run.py``。
"""

__version__ = "0.1.0"
