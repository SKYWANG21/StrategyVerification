"""
MA20趋势跟踪策略 - 数据获取模块

【面向初学者】
本模块负责从外部数据源拉取期货日 K 线数据，并统一成策略所需的格式。
- 支持两种数据源：Tushare（需 token）、Akshare（免 token，推荐）
- 输出标准列：date, open, high, low, close, volume, open_interest
- 会做基本校验（价格高低点逻辑、缺失值、异常涨跌幅等）
- 支持将数据保存到本地缓存，以及从缓存加载

使用方式示例：
  fetcher = DataFetcher('akshare')
  df = fetcher.fetch_futures_data('RB0', '2024-01-01', '2024-12-31')
"""

import pandas as pd
import numpy as np
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# 尝试导入数据源库，若未安装则对应 AVAILABLE 为 False
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

from config import get_config, get_instrument_config, get_paths

# 使用 config 中的日志配置初始化 logging
log_config = get_config('logging')
logging.basicConfig(
    level=getattr(logging, log_config.get('level', 'INFO')),
    format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger = logging.getLogger(__name__)


class DataFetcher:
    """
    期货数据获取器：按品种、日期范围从指定数据源拉取日 K 线，并做清洗与校验。
    """

    def __init__(self, data_source: str = 'tushare'):
        """
        初始化数据获取器。
        data_source 为 'tushare' 时需已设置环境变量 TUSHARE_TOKEN。
        """
        self.data_source = data_source
        self.config = get_config()

        if data_source == 'tushare' and TUSHARE_AVAILABLE:
            token = self.config['tushare_token']
            if not token:
                raise ValueError("Tushare token未设置，请设置环境变量TUSHARE_TOKEN")
            ts.set_token(token)
            self.pro = ts.pro_api()
            logger.info("Tushare数据源初始化成功")
        elif data_source == 'akshare' and AKSHARE_AVAILABLE:
            logger.info("Akshare数据源初始化成功")
        else:
            raise ValueError(f"数据源 {data_source} 不可用")

    def fetch_futures_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """根据数据源调用对应接口，返回统一格式的日 K 线 DataFrame。"""
        logger.info(f"获取 {symbol} 数据，时间范围: {start_date} 至 {end_date}")

        if self.data_source == 'tushare':
            return self._fetch_from_tushare(symbol, start_date, end_date)
        elif self.data_source == 'akshare':
            return self._fetch_from_akshare(symbol, start_date, end_date)
        else:
            raise ValueError(f"不支持的数据源: {self.data_source}")

    def _fetch_from_tushare(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Tushare 拉取期货日线，先试 SHF，若无数据再试 DCE/CZCE/CFFEX。"""
        try:
            start_date_str = start_date.replace('-', '')
            end_date_str = end_date.replace('-', '')

            instrument_config = get_instrument_config(symbol)
            # 默认按上海期货交易所代码请求
            df = self.pro.fut_daily(
                ts_code=f"{symbol}.SHF",
                start_date=start_date_str,
                end_date=end_date_str,
                fields='ts_code,trade_date,open,high,low,close,vol,oi'
            )

            # 若 SHF 无数据，依次尝试其他交易所
            if df.empty:
                logger.warning(f"Tushare未找到 {symbol} 的数据")
                for exchange in ['DCE', 'CZCE', 'CFFEX']:
                    df = self.pro.fut_daily(
                        ts_code=f"{symbol}.{exchange}",
                        start_date=start_date_str,
                        end_date=end_date_str,
                        fields='ts_code,trade_date,open,high,low,close,vol,oi'
                    )
                    if not df.empty:
                        logger.info(f"在 {exchange} 找到 {symbol} 数据")
                        break

            if df.empty:
                raise ValueError(f"未找到 {symbol} 的数据")

            df = self._process_tushare_data(df)
            logger.info(f"成功获取 {len(df)} 条Tushare数据")
            return df

        except Exception as e:
            logger.error(f"Tushare数据获取失败: {e}")
            raise

    def _fetch_from_akshare(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Akshare 拉取期货日线，再按 start/end 做日期过滤。"""
        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)

            if df.empty:
                raise ValueError(f"Akshare未找到 {symbol} 的数据")

            df = self._process_akshare_data(df)

            df['date'] = pd.to_datetime(df['date'])
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

            logger.info(f"成功获取 {len(df)} 条Akshare数据")
            return df

        except Exception as e:
            logger.error(f"Akshare数据获取失败: {e}")
            raise

    def _process_tushare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """统一 Tushare 列名与类型：trade_date -> date, vol -> volume, 数值列转 float，排序并校验。"""
        df = df.rename(columns={
            'trade_date': 'date',
            'vol': 'volume',
            'oi': 'open_interest'
        })

        df['date'] = pd.to_datetime(df['date'])

        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['open_interest'] = pd.to_numeric(df['open_interest'], errors='coerce').fillna(0)

        df = df.sort_values('date').reset_index(drop=True)
        self._validate_price_data(df)

        return df[['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest']]

    def _process_akshare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """统一 Akshare 列名与类型，缺失的 open_interest 补 0，排序并校验。"""
        df = df.rename(columns={
            'date': 'date',
            'volume': 'volume'
        })

        df['date'] = pd.to_datetime(df['date'])

        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)

        if 'open_interest' not in df.columns:
            df['open_interest'] = 0

        df = df.sort_values('date').reset_index(drop=True)
        self._validate_price_data(df)

        return df[['date', 'open', 'high', 'low', 'close', 'volume', 'open_interest']]

    def _validate_price_data(self, df: pd.DataFrame) -> None:
        """
        校验价格逻辑：high 应 >= open/close，low 应 <= open/close；
        若单日涨跌幅超过 20% 会打警告（期货可能有涨跌停，仅作提示）。
        """
        if df[['open', 'high', 'low', 'close']].isnull().any().any():
            logger.warning("价格数据中存在缺失值")

        invalid_high = df['high'] < df[['open', 'close']].max(axis=1)
        invalid_low = df['low'] > df[['open', 'close']].min(axis=1)

        if invalid_high.any():
            logger.warning(f"发现 {invalid_high.sum()} 条数据high价格异常")

        if invalid_low.any():
            logger.warning(f"发现 {invalid_low.sum()} 条数据low价格异常")

        df['price_change'] = df['close'].pct_change().abs()
        extreme_changes = df['price_change'] > 0.2

        if extreme_changes.any():
            logger.warning(f"发现 {extreme_changes.sum()} 条数据单日涨跌幅超过20%")

    def save_data(self, df: pd.DataFrame, symbol: str, data_dir: Optional[str] = None) -> str:
        """将 DataFrame 保存为 CSV，文件名含品种与日期范围，返回保存路径。"""
        paths = get_paths()
        target_dir = data_dir or paths['data_dir']
        os.makedirs(target_dir, exist_ok=True)

        start_date = df['date'].min().strftime('%Y%m%d')
        end_date = df['date'].max().strftime('%Y%m%d')
        filename = f"{symbol}_{start_date}_{end_date}.csv"
        filepath = os.path.join(target_dir, filename)

        df.to_csv(filepath, index=False)
        logger.info(f"数据已保存到: {filepath}")

        return filepath

    def load_cached_data(self, filepath: str) -> Optional[pd.DataFrame]:
        """从指定 CSV 路径加载数据，若文件不存在返回 None。"""
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            df['date'] = pd.to_datetime(df['date'])
            logger.info(f"从缓存加载数据: {len(df)} 条记录")
            return df
        return None


def test_data_fetcher():
    print("测试数据获取器...")
    
    if TUSHARE_AVAILABLE:
        try:
            fetcher = DataFetcher('tushare')
            df = fetcher.fetch_futures_data('RB0', '2023-01-01', '2023-01-31')
            print(f"Tushare数据获取成功: {len(df)} 条记录")
            print(df.head())
        except Exception as e:
            print(f"Tushare测试失败: {e}")
    
    if AKSHARE_AVAILABLE:
        try:
            fetcher = DataFetcher('akshare')
            df = fetcher.fetch_futures_data('RB0', '2023-01-01', '2023-01-31')
            print(f"Akshare数据获取成功: {len(df)} 条记录")
            print(df.head())
        except Exception as e:
            print(f"Akshare测试失败: {e}")


if __name__ == "__main__":
    test_data_fetcher()
