"""
MA20趋势跟踪策略 - 数据处理器模块

【面向初学者】
本模块在“原始日 K 线”之上做两件事：
1. 合成 2 日 K 线：Open=第一根 Open，High=两日最高，Low=两日最低，Close=最后一根 Close，Volume=两日之和
2. 计算策略所需特征：MA（移动平均）、K 线阴阳与实体比例、价格相对 MA 的位置等

核心方法：
- create_2day_kline(df)：日 K -> 2 日 K
- calculate_ma(df, period)：计算 MA
- calculate_kline_features(df)：阴阳线、实体、影线等
- prepare_strategy_data(df, ma_period)：一次性完成 MA + 特征 + 价格位置，并去掉前 period-1 行 NaN
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, Any, Tuple
from config import get_config, RESAMPLE_CONFIG

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    数据处理器：负责 2 日 K 线合成、MA 计算、K 线特征与价格位置计算，
    为信号生成和回测提供统一格式的“策略数据”。
    """

    def __init__(self):
        self.config = get_config()
        self.resample_config = RESAMPLE_CONFIG

    def create_2day_kline(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        将日 K 线合成为 2 日 K 线。

        合成规则（与 ARCHITECTURE 中一致）：
        - Open: 两日中第一根的开盘价 (first)
        - High: 两日中的最高价 (max)
        - Low: 两日中的最低价 (min)
        - Close: 两日中最后一根的收盘价 (last)
        - Volume/Amount: 两日之和 (sum)

        使用 pandas 的 resample('2D').agg(...) 实现，并会删掉因节假日等产生的空行。
        """
        logger.info("开始合成2日K线数据...")

        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"输入数据必须包含列: {required_columns}")

        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        df_indexed = df.set_index('date')
        aggregation_rules = self.resample_config['aggregation_rules'].copy()
        available_columns = [col for col in aggregation_rules.keys() if col in df_indexed.columns]
        aggregation_rules = {col: aggregation_rules[col] for col in available_columns}

        resampled = df_indexed.resample('2D').agg(aggregation_rules)
        resampled = resampled.dropna()
        resampled = resampled.reset_index()

        self._validate_resampled_data(df, resampled)

        logger.info(f"2日K线合成完成: {len(resampled)} 条记录")
        return resampled

    def calculate_ma(self, df: pd.DataFrame, period: int = 20, price_col: str = 'close') -> pd.DataFrame:
        """
        计算简单移动平均线。新增列名为 ma{period}，例如 ma20。
        前 period-1 行为 NaN（需要至少 period 个点才有一条均线值）。
        """
        logger.info(f"计算MA{period}...")

        if price_col not in df.columns:
            raise ValueError(f"数据中不存在列: {price_col}")

        ma_col = f'ma{period}'
        df[ma_col] = df[price_col].rolling(window=period, min_periods=period).mean()

        logger.info(f"MA{period}计算完成")
        return df

    def calculate_kline_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算 K 线特征：阴阳线、十字星、实体大小、影线等，
        供信号过滤或后续分析使用。
        """
        logger.info("计算K线特征...")

        df['is_red'] = df['close'] > df['open']   # 阳线
        df['is_green'] = df['close'] < df['open'] # 阴线
        df['is_doji'] = df['close'] == df['open'] # 十字星

        df['body_size'] = abs(df['close'] - df['open'])
        df['total_range'] = df['high'] - df['low']
        df['body_ratio'] = df['body_size'] / df['total_range']

        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']

        logger.info("K线特征计算完成")
        return df

    def calculate_price_position(self, df: pd.DataFrame, ma_period: int = 20) -> pd.DataFrame:
        """计算价格相对 MA 的位置：是否在均线上方/下方、以及距离均线的百分比。"""
        logger.info("计算价格相对位置...")

        ma_col = f'ma{ma_period}'
        if ma_col not in df.columns:
            df = self.calculate_ma(df, ma_period)

        df['above_ma'] = df['close'] > df[ma_col]
        df['below_ma'] = df['close'] < df[ma_col]
        df['distance_to_ma'] = (df['close'] - df[ma_col]) / df[ma_col]

        logger.info("价格相对位置计算完成")
        return df

    def prepare_strategy_data(self, df: pd.DataFrame, ma_period: int = 20) -> pd.DataFrame:
        """
        一站式准备策略数据：先算 MA，再算 K 线特征和价格位置，
        最后 dropna 去掉前 ma_period-1 行（无 MA 的行）。
        返回的 DataFrame 可直接交给 SignalGenerator.generate_signals()。
        """
        logger.info("准备策略数据...")

        df = self.calculate_ma(df, ma_period)
        df = self.calculate_kline_features(df)
        df = self.calculate_price_position(df, ma_period)
        df = df.dropna()

        logger.info(f"策略数据准备完成: {len(df)} 条有效记录")
        return df

    def _validate_resampled_data(self, original_df: pd.DataFrame, resampled_df: pd.DataFrame) -> None:
        """
        校验 2 日 K 线结果：条数约为原来一半、high/low 与 open/close 逻辑正确、
        时间间隔大致为 2 天。若有异常会打日志。
        """
        logger.info("验证2日K线合成结果...")

        expected_ratio = len(resampled_df) / len(original_df)
        if not (0.4 <= expected_ratio <= 0.6):
            logger.warning(f"数据量比例异常: {expected_ratio:.2f} (期望约0.5)")

        invalid_high = resampled_df['high'] < resampled_df[['open', 'close']].max(axis=1)
        invalid_low = resampled_df['low'] > resampled_df[['open', 'close']].min(axis=1)

        if invalid_high.any():
            logger.error(f"发现 {invalid_high.sum()} 条high价格异常")

        if invalid_low.any():
            logger.error(f"发现 {invalid_low.sum()} 条low价格异常")

        if len(resampled_df) > 1:
            date_diffs = resampled_df['date'].diff().dropna()
            expected_diff = pd.Timedelta(days=2)
            abnormal_diffs = date_diffs[date_diffs != expected_diff]
            if len(abnormal_diffs) > len(resampled_df) * 0.1:
                logger.warning(f"时间间隔异常的数据占比: {len(abnormal_diffs)/len(resampled_df):.2%}")

        if len(resampled_df) >= 2:
            logger.info("抽样验证前几条2日K线数据:")
            for i in range(min(3, len(resampled_df))):
                row = resampled_df.iloc[i]
                logger.info(f"日期: {row['date']}, O: {row['open']:.2f}, H: {row['high']:.2f}, "
                          f"L: {row['low']:.2f}, C: {row['close']:.2f}, V: {row['volume']:.0f}")

    def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """返回数据摘要：记录数、日期范围、价格/成交量统计、若含 K 线特征则包含阴阳比例等。"""
        summary = {
            'total_records': len(df),
            'date_range': {
                'start': df['date'].min().strftime('%Y-%m-%d'),
                'end': df['date'].max().strftime('%Y-%m-%d'),
                'trading_days': len(df)
            },
            'price_stats': {
                'highest': df['high'].max(),
                'lowest': df['low'].min(),
                'avg_close': df['close'].mean(),
                'price_range': df['high'].max() - df['low'].min()
            },
            'volume_stats': {
                'total_volume': df['volume'].sum(),
                'avg_volume': df['volume'].mean(),
                'max_volume': df['volume'].max()
            }
        }

        if 'is_red' in df.columns:
            red_ratio = df['is_red'].sum() / len(df)
            summary['kline_stats'] = {
                'red_ratio': red_ratio,
                'green_ratio': 1 - red_ratio - (df['is_doji'].sum() / len(df) if 'is_doji' in df.columns else 0),
                'doji_ratio': df['is_doji'].sum() / len(df) if 'doji' in df.columns else 0
            }

        return summary


def test_data_processor():
    """测试数据处理器"""
    print("测试数据处理器...")
    
    # 创建测试数据
    dates = pd.date_range(start='2023-01-01', end='2023-01-31', freq='D')
    np.random.seed(42)
    
    # 生成模拟价格数据
    base_price = 4000
    prices = [base_price]
    
    for i in range(1, len(dates)):
        # 随机价格变动 -2% 到 +2%
        change = np.random.uniform(-0.02, 0.02)
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)
    
    # 创建测试DataFrame
    test_data = pd.DataFrame({
        'date': dates,
        'open': [p * np.random.uniform(0.99, 1.01) for p in prices],
        'high': [p * np.random.uniform(1.00, 1.02) for p in prices],
        'low': [p * np.random.uniform(0.98, 1.00) for p in prices],
        'close': prices,
        'volume': np.random.randint(10000, 100000, len(dates))
    })
    
    # 确保价格逻辑正确
    for i in range(len(test_data)):
        row = test_data.iloc[i]
        test_data.loc[i, 'high'] = max(row['high'], row['open'], row['close'])
        test_data.loc[i, 'low'] = min(row['low'], row['open'], row['close'])
    
    processor = DataProcessor()
    
    # 测试2日K线合成
    print("\n1. 测试2日K线合成:")
    resampled = processor.create_2day_kline(test_data)
    print(f"原始数据: {len(test_data)} 条")
    print(f"合成后: {len(resampled)} 条")
    print(resampled.head())
    
    # 测试MA计算
    print("\n2. 测试MA20计算:")
    with_ma = processor.calculate_ma(resampled, 20)
    print(with_ma[['date', 'close', 'ma20']].head())
    
    # 测试K线特征
    print("\n3. 测试K线特征计算:")
    with_features = processor.calculate_kline_features(resampled)
    print(with_features[['date', 'close', 'is_red', 'body_ratio']].head())
    
    # 测试完整数据准备
    print("\n4. 测试完整数据准备:")
    strategy_data = processor.prepare_strategy_data(test_data, 20)
    print(f"策略数据列: {list(strategy_data.columns)}")
    print(strategy_data.head())
    
    # 测试数据摘要
    print("\n5. 测试数据摘要:")
    summary = processor.get_data_summary(strategy_data)
    print(f"数据摘要: {summary}")
    
    print("\n数据处理器测试完成!")


if __name__ == "__main__":
    test_data_processor()