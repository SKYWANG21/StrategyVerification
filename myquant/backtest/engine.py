"""回测引擎：封装 Backtrader Cerebro 的装配与执行。

引擎不关心具体策略与数据源，只负责：按配置设置资金/手续费/滑点/保证金，
注入数据与策略类，运行后把结果交给 :mod:`myquant.backtest.analyzer` 整理。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

import backtrader as bt
import pandas as pd

from myquant.backtest.analyzer import (
    BacktestResult,
    build_equity_curve,
    collect_metrics,
    extract_returns,
    extract_trades,
)
from myquant.config import get_instrument_config, get_settings
from myquant.data.base_datafeed import Market
from myquant.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class BacktestEngine:
    """单品种、单策略的回测引擎。

    Attributes:
        symbol: 品种代码。
        market: 市场类型。
        instrument: 合并后的品种交易参数。
        initial_capital: 初始资金。
    """

    def __init__(
        self,
        symbol: str,
        market: Market = Market.CN_STOCK,
        initial_capital: Optional[float] = None,
    ) -> None:
        """初始化引擎并载入品种参数。

        Args:
            symbol: 品种代码。
            market: 市场类型。
            initial_capital: 初始资金；为 None 时取 ``settings.yaml`` 的默认值。
        """
        backtest_settings = get_settings("backtest")
        self.symbol = symbol
        self.market = market
        self.instrument: Dict[str, Any] = get_instrument_config(symbol, market.value)
        self.initial_capital = float(
            initial_capital or backtest_settings.get("initial_capital", 100000)
        )
        self._backtest_settings = backtest_settings
        self.cerebro: Optional[bt.Cerebro] = None

    def run(
        self,
        df: pd.DataFrame,
        strategy_cls: Type[BaseStrategy],
        strategy_name: str,
        strategy_params: Optional[Dict[str, Any]] = None,
    ) -> BacktestResult:
        """执行回测。

        Args:
            df: 标准格式的 OHLCV DataFrame。
            strategy_cls: 策略类。
            strategy_name: 策略目录名，用于结果归档。
            strategy_params: 覆盖策略默认参数的键值对。

        Returns:
            回测结果。

        Raises:
            ValueError: 行情数据为空。
        """
        if df.empty:
            raise ValueError("行情数据为空，无法回测")

        self.cerebro = self._build_cerebro(df, strategy_cls, strategy_params or {})
        strategies = self.cerebro.run()
        strategy = strategies[0]

        final_value = float(self.cerebro.broker.getvalue())
        returns = extract_returns(strategy, self.initial_capital)

        return BacktestResult(
            strategy=strategy_name,
            symbol=self.symbol,
            market=self.market.value,
            start=str(pd.to_datetime(df["date"].min()).date()),
            end=str(pd.to_datetime(df["date"].max()).date()),
            initial_capital=self.initial_capital,
            final_value=final_value,
            metrics=collect_metrics(strategy, self.initial_capital, final_value),
            trades=extract_trades(strategy),
            equity_curve=build_equity_curve(returns, self.initial_capital),
            returns=returns,
        )

    def _build_cerebro(
        self,
        df: pd.DataFrame,
        strategy_cls: Type[BaseStrategy],
        strategy_params: Dict[str, Any],
    ) -> bt.Cerebro:
        """装配 Cerebro：数据、策略、经纪商参数与分析器。

        Args:
            df: 标准格式的 OHLCV DataFrame。
            strategy_cls: 策略类。
            strategy_params: 策略参数覆盖值。

        Returns:
            已装配完成的 Cerebro 实例。
        """
        cerebro = bt.Cerebro(stdstats=False)
        cerebro.adddata(self._to_bt_feed(df))
        cerebro.addstrategy(strategy_cls, **self._resolve_params(strategy_cls, strategy_params))

        cerebro.broker.setcash(self.initial_capital)
        self._setup_broker(cerebro, float(df["close"].iloc[0]))
        self._add_analyzers(cerebro)
        return cerebro

    @staticmethod
    def _to_bt_feed(df: pd.DataFrame) -> bt.feeds.PandasData:
        """把标准 DataFrame 转成 Backtrader 数据源。

        Args:
            df: 标准格式的 OHLCV DataFrame。

        Returns:
            Backtrader PandasData 数据源。
        """
        indexed = df.copy()
        indexed["date"] = pd.to_datetime(indexed["date"])
        indexed = indexed.set_index("date").sort_index()

        return bt.feeds.PandasData(
            dataname=indexed,
            datetime=None,
            open="open",
            high="high",
            low="low",
            close="close",
            volume="volume",
            openinterest=-1,
        )

    def _resolve_params(
        self,
        strategy_cls: Type[BaseStrategy],
        overrides: Dict[str, Any],
    ) -> Dict[str, Any]:
        """合成策略参数：配置中的风控参数 + 品种参数 + 命令行覆盖。

        只保留策略实际声明过的参数，避免把无关配置传进 Backtrader 导致报错。

        Args:
            strategy_cls: 策略类。
            overrides: 调用方指定的参数覆盖值。

        Returns:
            可直接传给 ``cerebro.addstrategy`` 的参数字典。
        """
        candidates: Dict[str, Any] = {
            "risk_per_trade": self._backtest_settings.get("risk_per_trade", 0.02),
            "max_position_pct": self._backtest_settings.get("max_position_pct", 0.8),
            "min_position_size": self._backtest_settings.get("min_position_size", 1),
            "margin_rate": self.instrument.get("margin_rate", 1.0),
            "contract_multiplier": self.instrument.get("contract_multiplier", 1),
        }
        candidates.update(overrides)

        accepted = set(strategy_cls.params._getkeys())
        unknown = sorted(set(overrides) - accepted)
        if unknown:
            logger.warning("策略 %s 不支持参数 %s，已忽略", strategy_cls.__name__, unknown)

        return {key: value for key, value in candidates.items() if key in accepted}

    def _setup_broker(self, cerebro: bt.Cerebro, reference_price: float) -> None:
        """设置手续费、保证金与滑点。

        股票/现货按比例手续费、全额资金占用；期货按合约乘数与保证金比例折算
        每手保证金现金额（以首根 K 线收盘价为参考价）。

        Args:
            cerebro: Cerebro 实例。
            reference_price: 用于折算保证金的参考价格。
        """
        commission = float(self.instrument.get("commission", 0.0))
        slippage = float(self.instrument.get("slippage", 0.0))
        multiplier = float(self.instrument.get("contract_multiplier", 1))
        margin_rate = float(self.instrument.get("margin_rate", 1.0))

        if self.market is Market.FUTURES:
            cerebro.broker.setcommission(
                commission=commission,
                margin=reference_price * multiplier * margin_rate,
                mult=multiplier,
                commtype=bt.CommInfoBase.COMM_PERC,
                percabs=True,
            )
        else:
            cerebro.broker.setcommission(commission=commission, mult=multiplier)

        if slippage > 0:
            cerebro.broker.set_slippage_perc(perc=slippage)

    @staticmethod
    def _add_analyzers(cerebro: bt.Cerebro) -> None:
        """注册绩效分析器。

        Args:
            cerebro: Cerebro 实例。
        """
        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")
        cerebro.addanalyzer(
            bt.analyzers.TimeReturn, _name="timereturn", timeframe=bt.TimeFrame.Days
        )
