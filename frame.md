以下是根据我们全部讨论内容整理而成的 **需求与架构文档**。它系统性地描述了量化策略开发框架的目标、功能与设计，可作为后续开发或团队协作的直接参考。

---

# 量化策略开发框架 - 需求与架构文档

> **版本**：v1.0  
> **状态**：设计阶段  
> **核心目标**：构建一个模块化、可扩展、覆盖中美及加密货币的量化策略研发平台，支持数据获取、回测、可视化分析以及实盘模拟交易。

---

## 目录

1. [项目背景与目标](#1-项目背景与目标)
2. [核心需求](#2-核心需求)
3. [架构设计概览](#3-架构设计概览)
4. [目录结构](#4-目录结构)
5. [模块详细设计](#5-模块详细设计)
   - 5.1 数据获取与清洗
   - 5.2 策略库（可插拔）
   - 5.3 回测引擎
   - 5.4 可视化与报告
   - 5.5 实盘模拟交易
   - 5.6 结果管理
6. [技术选型](#6-技术选型)
7. [使用流程示例](#7-使用流程示例)
8. [扩展性设计](#8-扩展性设计)

---

## 1. 项目背景与目标

- **背景**：在量化交易研究过程中，需要一个整合数据获取、策略开发、回测验证、可视分析及模拟交易的端到端本地平台。
- **目标**：
  - 利用开源数据接口（**AKShare** 为主、**Tushare** 为辅）统一获取 A 股、美股、加密货币等市场数据。
  - 基于 **Backtrader** 构建回测引擎，策略以插件形式组织，支持批量对比。
  - 自动生成资金曲线、绩效报告等可视化产物。
  - 提供实时行情驱动的虚拟资金测试环境，无缝衔接回测与实盘。

---

## 2. 核心需求

| 编号 | 需求                                                       | 优先级 |
| ---- | ---------------------------------------------------------- | ------ |
| R1   | 支持 AKShare 和 Tushare 作为主数据源，并预留扩展接口       | 高     |
| R2   | 数据清洗模块提供缺失值处理、复权、对齐等通用功能           | 高     |
| R3   | 策略以独立文件夹形式存放，内部可拆分信号、风控、过滤等逻辑 | 高     |
| R4   | 回测引擎封装 Backtrader，支持多品种、多策略同时回测        | 高     |
| R5   | 可视化模块输出资金曲线、回撤、绩效指标及 HTML 完整报告     | 高     |
| R6   | 基于实时行情的虚拟资金测试（模拟撮合），无需真实券商账户   | 高     |
| R7   | 数据覆盖 A 股、美股、加密货币三大市场                      | 高     |
| R8   | 回测与模拟交易结果集中管理，按策略和日期归档               | 中     |
| R9   | 命令行统一入口，支持指定模式（回测/模拟/对比）和参数       | 中     |

---

## 3. 架构设计概览

框架采用**分层、模块化**设计，各层之间通过抽象接口降低耦合：

```text
┌─────────────────────────────────┐
│        CLI / run.py              │  ← 用户交互
├─────────────────────────────────┤
│        Live Simulation           │  ← 实时模拟交易
├─────────────────────────────────┤
│       Backtest Engine            │  ← 回测引擎
├───────────────┬─────────────────┤
│   Strategies  │   Visualization  │  ← 策略库 & 可视化
├───────────────┴─────────────────┤
│         Data Layer               │  ← 数据获取与清洗
├─────────────────────────────────┤
│   AKShare / Tushare / ...       │  ← 外部数据源
└─────────────────────────────────┘
```

- **数据层**：通过抽象基类统一接口，可灵活切换数据来源。
- **策略层**：每个策略为独立文件夹，继承基础策略类，内部可按功能拆分。
- **引擎层**：负责回测/模拟交易的调度与生命周期管理。
- **表现层**：生成可视化图表、绩效报告，结果集中输出到 `results/`。

---

## 4. 目录结构

```
myquant/
├── config/                     # 配置文件
│   ├── settings.yaml           # 全局参数（资金、手续费、数据源等）
│   └── data_sources.yaml       # 数据源详细配置（Token等）
├── data/                       # 数据获取与清洗模块
│   ├── __init__.py
│   ├── base_datafeed.py        # 数据源抽象基类
│   ├── akshare_feed.py         # AKShare 实现（A股/美股/加密/期货）
│   ├── tushare_feed.py         # Tushare Pro 实现（需Token）
│   └── cleaner.py              # 通用数据清洗工具
├── strategies/                 # 策略库（可插拔，一策略一文件夹）
│   ├── __init__.py
│   ├── base_strategy.py        # 策略基类（继承 backtrader.Strategy）
│   ├── ma_cross/               # 示例：双均线策略
│   │   ├── __init__.py         # 导出策略类
│   │   ├── strategy.py         # 主策略逻辑
│   │   ├── signals.py          # 信号计算
│   │   └── risk.py             # 止盈止损逻辑
│   ├── momentum_breakout/      # 示例：动量突破策略
│   │   ├── __init__.py
│   │   ├── strategy.py
│   │   ├── signals.py
│   │   └── filters.py          # 过滤条件
│   └── ...                     # 后续新增策略按此模式
├── backtest/                   # 回测引擎与可视化
│   ├── __init__.py
│   ├── engine.py               # 封装 Backtrader Cerebro，提供回测接口
│   ├── analyzer.py             # 绩效分析（夏普、回撤、年化收益等）
│   └── visualizer.py           # 可视化与报告生成（matplotlib/quantstats）
├── live/                       # 实盘模拟交易模块
│   ├── __init__.py
│   ├── virtual_broker.py       # 虚拟券商（撮合、资金管理）
│   ├── data_stream.py          # 实时行情流（AKShare轮询/WebSocket）
│   ├── live_engine.py          # 模拟交易引擎（继承自回测引擎）
│   └── monitor.py              # 可选实时监控面板（Streamlit）
├── results/                    # 结果存放（统一管理）
│   ├── backtest/               # 回测结果
│   │   └── <strategy>_<symbol>_<start>_<end>/
│   │       ├── report.html
│   │       ├── equity_curve.png
│   │       ├── trades.csv
│   │       └── summary.json
│   └── live/                   # 模拟交易结果
│       └── <strategy>_<symbol>_live_<date>/
│           ├── performance.csv
│           ├── log.txt
│           └── daily_positions.csv
├── tests/                      # 单元测试
├── requirements.txt
└── run.py                      # 统一入口（支持回测、模拟、策略对比）
```

---

## 5. 模块详细设计

### 5.1 数据获取与清洗

- **抽象基类 `BaseDataFeed`**  
  定义三个必须实现的方法：
  - `get_daily(symbol, start, end) -> DataFrame`：获取历史日线数据，返回统一格式的 OHLCV DataFrame。
  - `get_realtime(symbol) -> dict`：获取实时快照。
  - `stream_ticks(symbol) -> generator`：实时行情推送。

- **`akshare_feed.py`**  
  通过 AKShare 实现上述接口，覆盖：
  - A 股：`stock_zh_a_hist`
  - 美股：`stock_us_hist`
  - 加密货币：`crypto_spot_hist`
    自动转换列名、时区处理等。

- **`tushare_feed.py`**  
  使用 Tushare Pro 获取高质量结构化数据，需要配置 Token。

- **`cleaner.py`**  
  工具函数：缺失值填充、复权方式统一、异常值过滤、多品种时间对齐。

### 5.2 策略库（可插拔）

- **基类 `BaseStrategy`**  
  继承 `backtrader.Strategy`，统一管理：
  - `notify_order` / `notify_trade` 日志记录。
  - 提供 `self.buy()` / `self.sell()` 等交易方法。

- **策略文件夹规范**  
  每个策略占一个文件夹，必须包含 `__init__.py` 并暴露策略类。内部文件可按功能命名（如 `signals.py`、`risk.py`、`filters.py` 等），由 `strategy.py` 组装调用。

- **示例：双均线策略**

  ```python
  # strategies/ma_cross/strategy.py
  from strategies.base_strategy import BaseStrategy
  from .signals import get_signal
  from .risk import apply_risk_management

  class MACrossStrategy(BaseStrategy):
      params = dict(fast=5, slow=20)
      def next(self):
          signal = get_signal(self.data, self.params)
          if signal == 'buy':
              self.buy()
          elif signal == 'sell':
              self.sell()
          apply_risk_management(self)
  ```

### 5.3 回测引擎

- **`engine.py`**  
  封装 `backtrader.Cerebro`：
  - 从 `settings.yaml` 读取初始资金、手续费、滑点。
  - 根据参数加载数据馈送（DataFeed）和策略类。
  - 运行回测并返回结果 Cerebro 对象。

- **`analyzer.py`**  
  添加 Backtrader 内置分析器（夏普比率、回撤、收益等），并汇总为易用字典。

- **支持多策略对比**  
  `run.py` 中实现 `--mode compare`，自动扫描 `strategies/` 下所有文件夹，依次回测并汇总结果。

### 5.4 可视化与报告

- **`visualizer.py`**  
  结合 `matplotlib` 和 `quantstats` 库：
  - 绘制资金曲线、回撤图。
  - 生成完整 HTML 报告（`quantstats.reports.html`），包含年化收益、夏普、最大回撤、月度热力图等。
  - 交易明细导出为 `trades.csv`。

- **结果自动保存**  
  所有图表和报告输出到 `results/backtest/<策略名>_<标的>_<时间区间>/`。

### 5.5 实盘模拟交易

- **`virtual_broker.py`**  
  实现一个简易的虚拟券商，包含：
  - 虚拟现金与持仓管理。
  - 撮合规则（按当前价成交，可配置 T+0/T+1）。
  - 佣金、印花税、滑点模拟。

- **`data_stream.py`**  
  使用 AKShare 的实时行情接口（轮询或 Websocket）推送数据到策略。

- **`live_engine.py`**  
  基于 Backtrader 的实时运行模式（`exactbars=True`），将虚拟券商与实时数据源注入，策略的 `next()` 在每根新 Bar 或 Tick 时自动触发。

- **监控面板**（可选）  
  `monitor.py` 基于 Streamlit 实现，实时显示持仓、资金曲线、交易日志。

- **模拟交易结果**  
  全部写入 `results/live/<策略名>_<标的>_live_<日期>/`。

### 5.6 结果管理

- 所有产出文件集中存储于项目根目录下的 `results/` 文件夹。
- 命名规范：`{策略名}_{标的}_{开始日期}_{结束日期}`（回测）或 `{策略名}_{标的}_live_{日期}`（模拟）。
- 便于历史对比、参数调优和报告分享。

---

## 6. 技术选型

| 组件         | 技术/库                                         | 说明                 |
| ------------ | ----------------------------------------------- | -------------------- |
| 数据获取     | **AKShare**, **Tushare**                        | A股/美股/加密全覆盖  |
| 回测引擎     | **Backtrader**                                  | 成熟、功能全面       |
| 数据清洗     | **pandas**, **numpy**                           | 数据处理基础         |
| 可视化       | **matplotlib**, **quantstats**                  | 资金曲线与专业报告   |
| 实时行情处理 | **AKShare** (轮询), **websocket-client** (可选) | 模拟交易实时数据驱动 |
| 配置管理     | **PyYAML**                                      | 读取 `settings.yaml` |
| CLI 入口     | **argparse** 或 **click**                       | 命令行参数解析       |
| 可选面板     | **Streamlit**                                   | 实时监控界面         |
| 加密数据源   | AKShare 内置（`crypto_spot_hist` 等）           | 无需额外引入 CCXT    |

---

## 7. 使用流程示例

### 7.1 回测

```bash
python run.py --mode backtest \
              --strategy ma_cross \
              --symbol 000001 \
              --start 2022-01-01 \
              --end 2023-01-01 \
              --source akshare
```

输出：

- 控制台打印绩效摘要。
- `results/backtest/ma_cross_000001_20220101_20230101/` 下生成 `report.html`、图表及 `trades.csv`。

### 7.2 批量策略对比

```bash
python run.py --mode compare \
              --symbol 000001 \
              --start 2021-01-01 \
              --end 2023-01-01
```

自动遍历 `strategies/` 下所有策略，对比结果保存到 `results/backtest/compare_...`。

### 7.3 实盘模拟交易

```bash
python run.py --mode live \
              --strategy ma_cross \
              --symbol 000001
```

- 实时行情驱动，虚拟资金 100 万（可配置）。
- 日志和持仓记录持续写入 `results/live/ma_cross_000001_live_20240101/`。

### 7.4 覆盖美股与加密货币

```bash
# 美股（使用 AKShare 内部接口）
python run.py --mode backtest --strategy ma_cross --symbol AAPL --source akshare

# 加密货币
python run.py --mode live --strategy ma_cross --symbol BTC/USDT --source akshare
```

---

## 8. 扩展性设计

- **新增数据源**  
  只需实现 `data/base_datafeed.py` 的抽象方法，然后注册到工厂函数，所有上层模块无需改动。

- **新增策略**  
  在 `strategies/` 下新建文件夹，遵循导出规范，即可被 `run.py` 自动发现和调用。

- **新增市场/品种**  
  AKShare 已内置丰富接口，框架只负责调用；若有特殊品种，可在 `akshare_feed.py` 中增加映射。

- **第三方模拟交易对接**  
  `live/` 模块与核心引擎解耦，未来可替换为 vnpy、Alpaca Paper Trading 等官方模拟环境。

---
