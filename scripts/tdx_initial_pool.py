#!/usr/bin/env python3
"""通达信本地数据初选池脚本。

根据给定公式对通达信 `vipdoc` 目录中的日线数据进行初筛。

选股条件：
- VOL > 0
- J <= 13
- DIFF > 0
- 当日振幅 ∈ [0.5, 7.1]
- 当日涨跌幅 ∈ [-2.3, 1.95]
- FINANCE(39) / 1e8 >= 10（通过外部 CSV 提供）

示例：
    python scripts/tdx_initial_pool.py \
        --vipdoc "F:/newVer/vipdoc" \
        --finance39-csv "F:/newVer/finance39.csv" \
        --output output/initial_pool.csv
"""

from __future__ import annotations

import argparse
import csv
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass
class Candle:
    date: int
    open: float
    high: float
    low: float
    close: float
    amount: float
    volume: int


def parse_day_file(path: Path) -> pd.DataFrame:
    """解析通达信 .day 文件为 DataFrame。"""
    record_size = 32
    rows: list[Candle] = []

    with path.open("rb") as f:
        data = f.read()

    if len(data) % record_size != 0:
        raise ValueError(f"文件大小异常（非32字节倍数）: {path}")

    for i in range(0, len(data), record_size):
        chunk = data[i : i + record_size]
        date, open_, high, low, close, amount, volume, _ = struct.unpack("<IIIIIfII", chunk)
        rows.append(
            Candle(
                date=date,
                open=open_ / 100.0,
                high=high / 100.0,
                low=low / 100.0,
                close=close / 100.0,
                amount=float(amount),
                volume=int(volume),
            )
        )

    df = pd.DataFrame([r.__dict__ for r in rows])
    if df.empty:
        return df

    df["trade_date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    return df


def tdx_sma(series: pd.Series, n: int, m: int = 1) -> pd.Series:
    """通达信 SMA(X,N,M) 递推实现。"""
    if series.empty:
        return series

    values = series.astype(float).tolist()
    out = [values[0]]
    for i in range(1, len(values)):
        out.append((m * values[i] + (n - m) * out[i - 1]) / n)
    return pd.Series(out, index=series.index)


def compute_indicators(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """计算 KDJ、MACD、涨跌幅、振幅。"""
    if df.empty:
        return df

    high_n = df["high"].rolling(n, min_periods=1).max()
    low_n = df["low"].rolling(n, min_periods=1).min()
    denom = (high_n - low_n).replace(0, pd.NA)
    rsv = ((df["close"] - low_n) / denom * 100).fillna(0)

    k = tdx_sma(rsv, m1, 1)
    d = tdx_sma(k, m2, 1)
    j = 3 * k - 2 * d

    diff = df["close"].ewm(span=12, adjust=False).mean() - df["close"].ewm(span=26, adjust=False).mean()
    dea = diff.ewm(span=9, adjust=False).mean()
    macd = 2 * (diff - dea)

    pct_chg = (df["close"] / df["close"].shift(1) - 1) * 100
    amplitude = (df["high"] - df["low"]) / df["close"].shift(1) * 100

    out = df.copy()
    out["K"] = k
    out["D"] = d
    out["J"] = j
    out["DIFF"] = diff
    out["DEA"] = dea
    out["MACD"] = macd
    out["当日涨跌幅"] = pct_chg
    out["当日振幅"] = amplitude
    return out


def iter_day_files(vipdoc_path: Path, markets: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for m in markets:
        market_dir = vipdoc_path / m / "lday"
        if market_dir.exists():
            files.extend(sorted(market_dir.glob("*.day")))
    return files


def load_finance39(csv_path: Path | None) -> dict[str, float]:
    """读取 FINANCE(39) 映射：code,finance39。"""
    if csv_path is None:
        return {}

    mapping: dict[str, float] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"code", "finance39"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("finance39 CSV 必须包含列: code, finance39")
        for row in reader:
            code = (row.get("code") or "").strip()
            if not code:
                continue
            mapping[code] = float(row.get("finance39") or 0)
    return mapping


def evaluate_stock(code: str, df: pd.DataFrame, finance39: float | None = None) -> dict | None:
    """基于最后一个交易日执行条件判断。"""
    if df.empty:
        return None

    latest = df.iloc[-1]
    finance39_value = float(finance39 or 0)

    passed = (
        latest["volume"] > 0
        and latest["J"] <= 13
        and latest["DIFF"] > 0
        and 0.5 <= latest["当日振幅"] <= 7.1
        and -2.3 <= latest["当日涨跌幅"] <= 1.95
        and finance39_value / 100000000 >= 10
    )

    if not passed:
        return None

    return {
        "code": code,
        "trade_date": latest["trade_date"].strftime("%Y-%m-%d"),
        "close": round(float(latest["close"]), 3),
        "volume": int(latest["volume"]),
        "J": round(float(latest["J"]), 3),
        "DIFF": round(float(latest["DIFF"]), 4),
        "当日振幅": round(float(latest["当日振幅"]), 3),
        "当日涨跌幅": round(float(latest["当日涨跌幅"]), 3),
        "FINANCE39": finance39_value,
        "FINANCE39_亿": round(finance39_value / 100000000, 3),
    }


def build_initial_pool(vipdoc: Path, finance39_map: dict[str, float], markets: list[str]) -> pd.DataFrame:
    """扫描通达信数据并构建初选池。"""
    results: list[dict] = []
    day_files = iter_day_files(vipdoc, markets)

    for day_file in day_files:
        code = day_file.stem
        try:
            raw = parse_day_file(day_file)
            if raw.empty:
                continue
            enriched = compute_indicators(raw)
            result = evaluate_stock(code, enriched, finance39_map.get(code))
            if result:
                results.append(result)
        except Exception as exc:
            print(f"[WARN] 处理失败 {day_file.name}: {exc}")

    if not results:
        return pd.DataFrame(columns=[
            "code", "trade_date", "close", "volume", "J", "DIFF", "当日振幅", "当日涨跌幅", "FINANCE39", "FINANCE39_亿"
        ])

    return pd.DataFrame(results).sort_values(["trade_date", "code"], ascending=[False, True]).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="通达信初选池生成工具")
    parser.add_argument("--vipdoc", type=Path, required=True, help="通达信 vipdoc 目录，例如 F:/newVer/vipdoc")
    parser.add_argument("--finance39-csv", type=Path, default=None, help="含 code,finance39 列的 CSV 文件")
    parser.add_argument("--markets", nargs="+", default=["sh", "sz"], help="市场目录，默认: sh sz")
    parser.add_argument("--output", type=Path, default=Path("output/initial_pool.csv"), help="输出 CSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.vipdoc.exists():
        raise FileNotFoundError(f"vipdoc 路径不存在: {args.vipdoc}")

    finance39_map = load_finance39(args.finance39_csv)
    pool = build_initial_pool(args.vipdoc, finance39_map, args.markets)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pool.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"扫描完成，命中 {len(pool)} 只股票")
    print(f"输出文件: {args.output}")


if __name__ == "__main__":
    main()
