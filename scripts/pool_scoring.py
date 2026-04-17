#!/usr/bin/env python3
"""初选池评分模块。

实现 A/B/C/E 加分与 D 扣分规则，并输出统一评分字典。
"""

from __future__ import annotations

from typing import Any


def _score_a(yang_vol_pct: float, breakout_vol_type: str, sum_turnover: float) -> float:
    # A1
    if yang_vol_pct >= 65:
        a1 = 10.0
    elif yang_vol_pct >= 55:
        a1 = 7.0
    elif yang_vol_pct >= 50:
        a1 = 4.0
    else:
        a1 = 0.0

    # A2
    if breakout_vol_type == "递增放量":
        a2 = 8.0
    elif breakout_vol_type == "中间萎缩":
        a2 = 5.0
    else:
        a2 = 0.0

    # A3
    if sum_turnover < 25:
        a3 = 12.0
    elif sum_turnover < 35:
        a3 = 9.0
    elif sum_turnover < 45:
        a3 = 6.0
    else:
        a3 = 0.0

    return a1 + a2 + a3


def _score_b(max_down_vol: float, avg_up_vol: float, end_down_vol: float, max_up_vol: float, c_above_a_pct: float) -> float:
    ratio_b1 = max_down_vol / avg_up_vol if avg_up_vol > 0 else 999.0
    if ratio_b1 < 0.5:
        b1 = 12.0
    elif ratio_b1 < 0.8:
        b1 = 8.0
    elif ratio_b1 < 1.0:
        b1 = 4.0
    else:
        b1 = 0.0

    ratio_b2 = end_down_vol / max_up_vol if max_up_vol > 0 else 999.0
    if ratio_b2 < 0.3:
        b2 = 12.0
    elif ratio_b2 < 0.5:
        b2 = 8.0
    elif ratio_b2 < 0.7:
        b2 = 4.0
    else:
        b2 = 0.0

    if c_above_a_pct > 3:
        b3 = 11.0
    elif c_above_a_pct > 1:
        b3 = 7.0
    elif c_above_a_pct > 0:
        b3 = 3.0
    else:
        b3 = 0.0

    return b1 + b2 + b3


def _score_c(kdj_j: float, kline_type: str, close: float, ma11: float, ma32: float) -> float:
    if kdj_j < 0:
        c1 = 5.0
    elif kdj_j < 10:
        c1 = 3.0
    elif kdj_j < 15:
        c1 = 1.0
    else:
        c1 = 0.0

    if any(x in kline_type for x in ["下影阳", "阳线下影", "带下影小阳线"]):
        c2 = 5.0
    elif kline_type == "十字星":
        c2 = 3.0
    elif kline_type == "小阴线":
        c2 = 1.0
    else:
        c2 = 0.0

    if close >= ma11:
        c3 = 5.0
    elif close >= ma32:
        c3 = 3.0
    else:
        c3 = 1.0

    return c1 + c2 + c3


def _score_e(
    long_shadow_down_pct: float,
    price_c: float,
    price_a: float,
    end_down_vol: float,
    max_up_vol: float,
    c_above_a_pct: float,
    long_shadow_kline: str,
    long_shadow_vol: float | None,
) -> float:
    # 触发前提
    if not (long_shadow_down_pct <= -5.0 and price_c > price_a):
        return 0.0

    ref_vol = long_shadow_vol if long_shadow_vol is not None else end_down_vol
    ratio = ref_vol / max_up_vol if max_up_vol > 0 else 999.0

    if ratio <= 0.2:
        e1 = 9.0
    elif ratio <= 0.3:
        e1 = 7.0
    elif ratio <= 0.5:
        e1 = 5.0
    elif ratio <= 0.7:
        e1 = 3.0
    elif ratio <= 0.85:
        e1 = 1.0
    else:
        e1 = 0.0

    drop_abs = abs(long_shadow_down_pct)
    if drop_abs >= 10:
        e2 = 5.0
    elif drop_abs >= 8:
        e2 = 4.0
    elif drop_abs >= 6:
        e2 = 3.0
    elif drop_abs >= 5:
        e2 = 2.0
    else:
        e2 = 0.0

    if c_above_a_pct > 5:
        e3 = 3.0
    elif c_above_a_pct > 3:
        e3 = 2.0
    elif c_above_a_pct > 1:
        e3 = 1.0
    else:
        e3 = 0.0

    if long_shadow_kline == "带下影线":
        e4 = 3.0
    elif long_shadow_kline == "光头光脚":
        e4 = 1.5
    else:
        e4 = 0.0

    return e1 + e2 + e3 + e4


def _deduct_d(gap_type: str, shadow_ratio: float, b_candle_type: str, first_down_ratio: float) -> float:
    # D1
    if gap_type == "中期跳空":
        d1 = 6.0
    elif gap_type == "末期跳空":
        d1 = 12.0
    else:
        d1 = 0.0

    # D2
    if shadow_ratio <= 1.5:
        d2 = 0.0
    elif shadow_ratio <= 2.5:
        d2 = 5.0 if b_candle_type == "阴线" else 2.0
    elif shadow_ratio <= 4:
        d2 = 10.0 if b_candle_type == "阴线" else 5.0
    else:
        d2 = 15.0 if b_candle_type == "阴线" else 8.0

    # D3
    if first_down_ratio > 1.0:
        d3 = 0.0  # 已淘汰场景，不在此重复扣分
    elif first_down_ratio >= 0.8:
        d3 = 8.0
    elif first_down_ratio >= 0.5:
        d3 = 3.0
    else:
        d3 = 0.0

    return min(20.0, d1 + d2 + d3)


def _rating(final_score: float) -> str:
    if final_score >= 90:
        return "S级（钻石买点）"
    if final_score >= 80:
        return "A级（优质买点）"
    if final_score >= 70:
        return "B级（观察买点）"
    if final_score >= 60:
        return "C级（鸡肋）"
    return "D级（不合格）"


def score_stock_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    """按规则计算单只股票评分。

    payload 关键字段：
      stock_code, date,
      is_qualified, reject_reason,
      yang_vol_pct, breakout_vol_type, sum_turnover,
      max_down_vol, avg_up_vol, end_down_vol, max_up_vol,
      price_A, price_C,
      kdj_j, kline_type, close, ma11, ma32,
      long_shadow_down_pct, long_shadow_kline, long_shadow_vol(optional),
      gap_type, shadow_ratio, b_candle_type, first_down_ratio
    """
    stock_code = str(payload.get("stock_code", ""))
    date = str(payload.get("date", ""))

    is_qualified = bool(payload.get("is_qualified", True))
    reject_reason = str(payload.get("reject_reason", ""))

    if not is_qualified:
        return {
            "stock_code": stock_code,
            "date": date,
            "final_score": 0.0,
            "rating": "D级（不合格）",
            "is_qualified": False,
            "reject_reason": reject_reason or "未通过硬性否决条件",
            "module_scores": {"A": 0.0, "B": 0.0, "C": 0.0, "E": 0.0, "D_deduct": 0.0},
        }

    price_a = float(payload.get("price_A", 0.0))
    price_c = float(payload.get("price_C", 0.0))
    c_above_a_pct = ((price_c - price_a) / price_a * 100) if price_a > 0 else 0.0

    a = _score_a(
        float(payload.get("yang_vol_pct", 0.0)),
        str(payload.get("breakout_vol_type", "")),
        float(payload.get("sum_turnover", 0.0)),
    )
    b = _score_b(
        float(payload.get("max_down_vol", 0.0)),
        float(payload.get("avg_up_vol", 0.0)),
        float(payload.get("end_down_vol", 0.0)),
        float(payload.get("max_up_vol", 0.0)),
        c_above_a_pct,
    )
    c = _score_c(
        float(payload.get("kdj_j", 0.0)),
        str(payload.get("kline_type", "")),
        float(payload.get("close", 0.0)),
        float(payload.get("ma11", 0.0)),
        float(payload.get("ma32", 0.0)),
    )
    e = _score_e(
        float(payload.get("long_shadow_down_pct", 0.0)),
        price_c,
        price_a,
        float(payload.get("end_down_vol", 0.0)),
        float(payload.get("max_up_vol", 0.0)),
        c_above_a_pct,
        str(payload.get("long_shadow_kline", "")),
        None if payload.get("long_shadow_vol") is None else float(payload.get("long_shadow_vol")),
    )
    d_deduct = _deduct_d(
        str(payload.get("gap_type", "无跳空")),
        float(payload.get("shadow_ratio", 0.0)),
        str(payload.get("b_candle_type", "")),
        float(payload.get("first_down_ratio", 0.0)),
    )

    middle_score = a + b + c + e
    final_score = max(0.0, min(100.0, middle_score - d_deduct))
    final_score = round(final_score, 1)

    return {
        "stock_code": stock_code,
        "date": date,
        "final_score": final_score,
        "rating": _rating(final_score),
        "is_qualified": True,
        "reject_reason": "",
        "module_scores": {
            "A": round(a, 1),
            "B": round(b, 1),
            "C": round(c, 1),
            "E": round(e, 1),
            "D_deduct": round(d_deduct, 1),
        },
    }
