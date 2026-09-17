#!/usr/bin/env python3
"""Learn real duration from extensions, not from what a person guessed.

Asked 45 minutes, then "+20" three times → actual 105. After a few
samples, suggest the median actual instead of the asked number.
"""
from __future__ import annotations

import re
from statistics import median


def key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def suggested(entry: dict, asked: int) -> int:
    actuals = [int(x) for x in entry.get("actual") or [] if int(x) > 0]
    if len(actuals) >= 2:
        return max(5, int(median(actuals)))
    if actuals:
        return max(asked, actuals[-1])
    return asked


def record(entry: dict, asked: int, actual: int) -> dict:
    asked_list = list(entry.get("asked") or [])
    actual_list = list(entry.get("actual") or [])
    asked_list.append(int(asked))
    actual_list.append(int(actual))
    out = {
        "asked": asked_list[-20:],
        "actual": actual_list[-20:],
    }
    out["suggested_minutes"] = suggested(out, int(asked))
    return out
