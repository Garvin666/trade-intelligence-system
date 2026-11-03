"""SQLite 存储与读取清洗后的市场数据。"""

from __future__ import annotations

import sqlite3

import pandas as pd

from src.config import DB_PATH


def save_processed_data(df: pd.DataFrame, table_name: str = "market_data") -> None:
    """将清洗后的数据写入 SQLite。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql(table_name, conn, if_exists="replace", index=False)


def load_processed_data(table_name: str = "market_data") -> pd.DataFrame:
    """从 SQLite 读取数据；库不存在或表为空时返回空 DataFrame。"""
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
        except sqlite3.DatabaseError:
            return pd.DataFrame()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df
