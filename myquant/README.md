# myquant - 量化策略开发框架

模块化、可扩展的本地量化研发平台，覆盖 A股、美股、加密货币与期货主连，支持数据获取、
回测、绩效报告，并为实盘模拟交易预留接口。

## 目录结构

```
myquant/
├── config/          # YAML 配置与加载器
│   ├── settings.yaml       # 资金、手续费、市场与品种参数
│   └── data_sources.yaml   # 数据源、Token、接口名映射
├── data/            # 数据获取与清洗
│   ├── base_datafeed.py    # BaseDataFeed 抽象基类 + Market 枚举
│   ├── akshare_feed.py     # AKShare 实现（四市场）
│   ├── tushare_feed.py     # Tushare Pro 实现（A股/期货）
│   └── cleaner.py          # 列名统一、缺失值、重采样、多品种对齐
├── strategies/      # 可插拔策略库（一策略一文件夹）
│   ├── base_strategy.py    # 策略基类：日志、交易记录、仓位计算
│   ├── ma20_trend/         # MA20 趋势跟踪（signals.py / risk.py / strategy.py）
│   └── ma_cross/           # 双均线交叉示例
├── backtest/        # 回测引擎与报告
│   ├── engine.py           # 封装 Backtrader Cerebro
│   ├── analyzer.py         # 指标汇总与结果结构
│   └── visualizer.py       # 图表 + quantstats HTML 报告
├── live/            # 实盘模拟交易（当前仅接口骨架）
├── results/         # 运行产物（已 gitignore）
├── tests/           # pytest 单元测试与端到端冒烟
└── run.py           # 统一命令行入口
```

## 安装

```bash
pip install -r myquant/requirements.txt
# Tushare 数据源需要配置 Token
setx TUSHARE_TOKEN "your_token"     # Windows
export TUSHARE_TOKEN=your_token     # Linux / macOS
```

## 使用

### 单策略回测

```bash
# 期货主连，2 日 K 线（MA20 趋势跟踪的原始设定）
python myquant/run.py --mode backtest --strategy ma20_trend --symbol RB0 \
    --market futures --start 2024-01-01 --end 2025-12-31 --resample 2D

# A 股日线
python myquant/run.py --mode backtest --strategy ma_cross --symbol 000001 \
    --market cn_stock --start 2022-01-01 --end 2023-01-01

# 美股 / 加密货币
python myquant/run.py --mode backtest --strategy ma_cross --symbol AAPL --market us_stock
python myquant/run.py --mode backtest --strategy ma_cross --symbol BTC --market crypto
```

产出归档到 `results/backtest/<策略>_<品种>_<起>_<止>/`，含 `report.html`、
`equity_curve.png`、`drawdown.png`、`trade_distribution.png`、`trades.csv`、`summary.json`。

### 多策略对比

```bash
python myquant/run.py --mode compare --symbol RB0 --market futures --resample 2D
```

自动发现 `strategies/` 下所有策略，逐个回测并输出对比表到
`results/backtest/compare_<品种>_<起>_<止>/comparison.csv`。

### 覆盖策略参数

```bash
python myquant/run.py --mode backtest --strategy ma20_trend --symbol RB0 \
    --market futures --param ma_period=10 --param force_stop_pct=0.02
```

### 实盘模拟

`--mode live` 当前仅有接口骨架，执行会提示未实现并返回退出码 3。

## 扩展

**新增数据源**：实现 `BaseDataFeed` 的 `get_daily` 与 `get_realtime`，在
`data/__init__.py` 中 `register_feed("name", YourFeed)`，并在 `data_sources.yaml` 添加配置。

**新增策略**：在 `strategies/` 下新建文件夹，`strategy.py` 继承 `BaseStrategy`，
`__init__.py` 通过 `STRATEGY` 导出策略类，即可被自动发现，无需注册。

**新增品种/市场**：在 `settings.yaml` 的 `instruments` 增加条目；新市场需同时在
`markets` 段补默认参数，并在 `data_sources.yaml` 的 `interfaces` 声明对应接口名。

## 测试

```bash
pytest myquant/tests
```

## 与旧项目的关系

`TrendFollowingStrategy/` 是本框架的前身，MA20 策略逻辑已迁移至
`strategies/ma20_trend/`，回测统一走 Backtrader，旧目录仅作历史参考。
