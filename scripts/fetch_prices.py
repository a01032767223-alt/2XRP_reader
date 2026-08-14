#!/usr/bin/env python3
"""
현물(BTC/ETH/SOL/XRP)과 대응 2배 레버리지 ETF(BITX/ETHU/SOLT/XXRP) 종가 수집.

  python scripts/fetch_prices.py              # 매일: 최신 1건 추가
  python scripts/fetch_prices.py --backfill   # 최초 1회: 2년치 실측으로 전면 교체

백필을 한 번 돌리면 seed(보간) 데이터는 전부 실제 종가로 대체된다.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST_PATH = os.path.join(ROOT, "data", "history.json")
LATEST_PATH = os.path.join(ROOT, "data", "latest.json")
KST = timezone(timedelta(hours=9))


def load_hist():
    with open(HIST_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_hist(hist):
    hist["updated"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    with open(HIST_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)


def closes(ticker, period, interval="1d"):
    """{날짜: 종가} 딕셔너리."""
    df = yf.Ticker(ticker).history(period=period, interval=interval)
    if df is None or df.empty:
        raise RuntimeError(f"{ticker}: 데이터 없음")
    df = df.dropna(subset=["Close"])
    return {ix.date().isoformat(): float(v) for ix, v in zip(df.index, df["Close"])}


def backfill(hist):
    """ETF 거래일 기준으로 현물과 짝지어 2년치를 새로 만든다."""
    for key, cfg in hist["assets"].items():
        spot = closes(cfg["spot"], "2y")
        lev = closes(cfg["lev"], "2y")

        rows = []
        for date in sorted(lev):
            if date in spot:  # ETF 거래일 중 현물 시세도 있는 날만
                rows.append({
                    "date": date,
                    "spot": round(spot[date], 6),
                    "lev": round(lev[date], 4),
                    "src": "auto",
                })
        if not rows:
            raise RuntimeError(f"{key}: 겹치는 거래일이 없습니다")
        hist["rows"][key] = rows
        print(f"  {key:4s} {cfg['lev']:5s} {len(rows):4d}건  "
              f"{rows[0]['date']} ~ {rows[-1]['date']}")
    hist["note"] = "전 종목 실측 데이터(yfinance 종가 기준)."
    return hist


def daily(hist):
    """최신 1건씩 추가/갱신."""
    for key, cfg in hist["assets"].items():
        spot = closes(cfg["spot"], "10d")
        lev = closes(cfg["lev"], "10d")
        if not lev:
            print(f"  {key}: ETF 시세 없음, 건너뜀")
            continue

        date = max(lev)
        if date not in spot:  # 현물은 365일 거래이므로 보통 있음
            near = [d for d in sorted(spot) if d <= date]
            if not near:
                print(f"  {key}: 짝 맞는 현물 시세 없음, 건너뜀")
                continue
            date_spot = near[-1]
        else:
            date_spot = date

        entry = {
            "date": date,
            "spot": round(spot[date_spot], 6),
            "lev": round(lev[date], 4),
            "src": "auto",
        }

        rows = hist["rows"].setdefault(key, [])
        # seed 데이터만 있으면 첫 실측 시 정리
        rows = [r for r in rows if r["date"] != date]
        rows.append(entry)
        rows.sort(key=lambda r: r["date"])
        hist["rows"][key] = rows
        print(f"  {key:4s} {date}  현물 {entry['spot']}  ETF {entry['lev']}")
    return hist


def write_latest(hist):
    snap = {"updated": hist["updated"], "assets": {}}
    for key in hist["assets"]:
        rows = hist["rows"].get(key, [])
        if not rows:
            continue
        last = rows[-1]
        prev = rows[-2] if len(rows) >= 2 else last
        snap["assets"][key] = {
            "date": last["date"],
            "spot": last["spot"],
            "lev": last["lev"],
            "spot_chg": round((last["spot"] / prev["spot"] - 1) * 100, 2) if prev["spot"] else 0,
            "lev_chg": round((last["lev"] / prev["lev"] - 1) * 100, 2) if prev["lev"] else 0,
            "count": len(rows),
        }
    with open(LATEST_PATH, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true",
                    help="2년치 실측 데이터로 전면 교체")
    args = ap.parse_args()

    hist = load_hist()
    print("백필 시작" if args.backfill else "일간 수집 시작")
    hist = backfill(hist) if args.backfill else daily(hist)
    save_hist(hist)
    write_latest(hist)
    print("완료:", hist["updated"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"수집 실패: {exc}", file=sys.stderr)
        sys.exit(1)
