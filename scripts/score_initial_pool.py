#!/usr/bin/env python3
"""批量执行初选池评分。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from pool_scoring import score_stock_candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="初选池评分工具")
    parser.add_argument("--input", type=Path, required=True, help="输入特征 CSV")
    parser.add_argument("--output", type=Path, default=Path("output/initial_pool_scored.csv"), help="输出评分 CSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)

    records = []
    for row in df.to_dict(orient="records"):
        scored = score_stock_candidate(row)
        flat = {
            "stock_code": scored["stock_code"],
            "date": scored["date"],
            "final_score": scored["final_score"],
            "rating": scored["rating"],
            "is_qualified": scored["is_qualified"],
            "reject_reason": scored["reject_reason"],
            "A": scored["module_scores"]["A"],
            "B": scored["module_scores"]["B"],
            "C": scored["module_scores"]["C"],
            "E": scored["module_scores"]["E"],
            "D_deduct": scored["module_scores"]["D_deduct"],
        }
        records.append(flat)

    out = pd.DataFrame(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"评分完成: {len(out)} 条")
    print(f"输出文件: {args.output}")


if __name__ == "__main__":
    main()
