# MA20 趋势跟踪策略 - 项目架构说明（面向 Python 初学者）

本文档帮助初学者理解项目的整体架构、各模块的职责以及数据如何从“原始行情”流向“回测结果”。

---

## 一、项目是做什么的？

这是一个**期货量化策略**项目：

- **策略名称**：MA20 趋势跟踪（用 20 周期均线判断趋势方向）
- **交易标的**：期货主连（如螺纹钢 RB0、铜 CU0、沪深300 IF0）
- **时间周期**：2 日 K 线（由日 K 线合成）
- **主要功能**：获取数据 → 合成 K 线 → 计算均线 → 产生买卖信号 → 计算止损与仓位 → 回测 → 绩效分析与图表

---

## 二、目录结构一览

```
TrendFollowingStrategy/
├── config.py              # 全局配置（参数、品种、路径等）
├── ARCHITECTURE.md        # 本文件：架构说明
├── PROJECT_SUMMARY.md     # 项目总结与完成状态
├── README.md              # 使用说明与快速开始
├── requirements.txt      # Python 依赖
│
├── src/                   # 核心策略与工具代码
│   ├── __init__.py        # 包入口，导出主要类
│   ├── data_fetcher.py    # 数据获取（Tushare / Akshare）
│   ├── data_processor.py  # 2日K线合成、MA、K线特征
│   ├── signal_generator.py # 交易信号生成（多/空/观望）
│   ├── risk_manager.py   # 止损、仓位、移动止损
│   ├── backtest_engine.py # Backtrader 回测引擎
│   ├── performance_analyzer.py # 绩效指标与图表
│   └── visualization.py   # 综合图表与 HTML 报告
│
├── scripts/               # 可执行脚本
│   ├── main_simple.py     # 主入口：一键运行策略（推荐）
│   ├── simple_test.py    # 基础功能测试
│   ├── simple_backtest.py # 简化回测验证
│   ├── multibacktest.py  # 多品种回测
│   └── ...
│
├── tests/                 # 单元测试
│   ├── test_strategy.py
│   ├── test_backtest.py
│   └── test_simple.py
│
├── results/               # 回测报告、交易明细、图表（运行后生成）
├── logs/                  # 日志文件
└── data/                  # 数据缓存（可选，可在上级目录）
```

---

## 三、数据流与模块关系（重要）

整体流程可以概括为：

```
[数据源] → DataFetcher → 日K线
                ↓
         DataProcessor：合成2日K线、算MA、K线特征
                ↓
         SignalGenerator：根据 MA20 + K线颜色 生成 做多/做空/观望
                ↓
         RiskManager：每笔开仓的止损价、手数（仓位）
                ↓
         BacktestEngine / 简化回测：模拟买卖、手续费、滑点
                ↓
         PerformanceAnalyzer + Visualization：指标、曲线、图表、报告
```

### 1. 配置层：`config.py`

- 定义项目根目录、`src`、`scripts`、`results`、`logs`、`data` 等路径
- 定义数据源（tushare / akshare）、MA 周期、止损比例、品种参数（手续费、保证金、合约乘数等）
- 提供 `get_config()`、`get_instrument_config(symbol)`、`validate_config()` 等函数供其他模块使用

### 2. 数据层

| 模块     | 文件                | 职责（一句话）                                                                                                |
| -------- | ------------------- | ------------------------------------------------------------------------------------------------------------- |
| 数据获取 | `data_fetcher.py`   | 从 Tushare 或 Akshare 拉取期货日 K 线，统一成 `date, open, high, low, close, volume` 等列，并做基本校验与缓存 |
| 数据处理 | `data_processor.py` | 把日 K 线合成 2 日 K 线，计算 MA、K 线阴阳与特征，为策略提供“策略数据”                                        |

### 3. 策略层

| 模块     | 文件                  | 职责（一句话）                                                                                       |
| -------- | --------------------- | ---------------------------------------------------------------------------------------------------- |
| 信号生成 | `signal_generator.py` | 根据「收盘价 vs MA20」和「K 线颜色」产生做多(1)、做空(-1)、观望(0)，可加过滤器（实体比例、成交量等） |
| 风险管理 | `risk_manager.py`     | 计算单笔止损价（前 K 极值 vs 强制止损）、基于资金与风险的手数、移动止损（保本/跟踪）                 |

### 4. 回测与绩效层

| 模块     | 文件                      | 职责（一句话）                                                                               |
| -------- | ------------------------- | -------------------------------------------------------------------------------------------- |
| 回测引擎 | `backtest_engine.py`      | 使用 Backtrader 框架，按策略规则逐 K 线模拟开平仓、手续费、滑点，输出资金曲线与交易记录      |
| 绩效分析 | `performance_analyzer.py` | 根据交易记录和权益曲线计算胜率、盈亏比、回撤、夏普等指标，并绘制权益曲线、回撤图、交易分布等 |
| 可视化   | `visualization.py`        | 综合多张图（权益、价格+信号、交易分布、月度热力图、回撤分析等），并生成 HTML 仪表盘          |

### 5. 入口脚本

- **`scripts/main_simple.py`**：主入口。内部会依次调用：DataFetcher → DataProcessor → SignalGenerator → 简化回测（或可接 Backtrader）→ 报告与可视化。  
  命令行可指定品种、数据源、起止日期、初始资金等。

---

## 四、核心概念速查（给初学者的解释）

- **2 日 K 线**：把连续 2 个交易日的 K 线合成一根。Open=第 1 日 Open，High=两日最高，Low=两日最低，Close=第 2 日 Close，Volume=两日成交量之和。这样周期更长，噪音更少。
- **MA20**：20 根 K 线收盘价的简单平均，用来代表“近期趋势方向”。
- **做多信号**：收盘价 > MA20 且 当前 K 线收阳（Close > Open）。
- **做空信号**：收盘价 < MA20 且 当前 K 线收阴（Close < Open）。
- **止损**：做多时用前一根 K 线最低价作基础止损；若距离超过 6% 则改用“进场价 × (1 - 3%)”的强制止损。做空对称。
- **移动止损**：有浮盈后把止损移到成本价（保本），K 线颜色反转时平仓。

---

## 五、如何运行（快速上手）

1. 安装依赖：`pip install -r requirements.txt`
2. 在项目根目录下运行主程序（示例）：
   ```bash
   python scripts/main_simple.py --symbol RB0 --start-date 2024-01-01 --end-date 2025-12-31
   ```
3. 查看 `results/` 下的报告、交易 CSV 和图表；日志在 `logs/`。

---

## 六、学习建议（按模块阅读顺序）

1. 先看 **config.py**：了解有哪些可调参数和路径。
2. 再看 **data_fetcher.py** → **data_processor.py**：理解“原始数据 → 策略用数据”的转换。
3. 然后 **signal_generator.py** 和 **risk_manager.py**：理解“什么时候买卖、止损和仓位怎么算”。
4. 接着 **backtest_engine.py**（或 main_simple 里的简化回测）：理解“如何按时间顺序模拟交易”。
5. 最后 **performance_analyzer.py** 和 **visualization.py**：理解“如何从交易结果得到指标和图表”。

每个模块在代码里都补充了注释，建议结合本架构说明和注释一起阅读。

---

_文档版本与项目代码保持一致，如有疑问可参考 README.md 与 PROJECT_SUMMARY.md。_
