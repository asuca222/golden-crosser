"""日本株のゴールデンクロスを検出して ntfy にプッシュ通知する。"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
import yfinance as yf

SHORT = 5    # 短期移動平均(日)
LONG = 25    # 長期移動平均(日)
JST = timezone(timedelta(hours=9))


def detect_golden_cross(close):
    """最新の足でゴールデンクロスしたかを返す。

    前日: 短期 <= 長期 かつ 当日: 短期 > 長期 のときだけ True。
    """
    if len(close) < LONG + 1:
        return False
    short = close.rolling(SHORT).mean()
    long_ = close.rolling(LONG).mean()
    prev_s, prev_l = short.iloc[-2], long_.iloc[-2]
    now_s, now_l = short.iloc[-1], long_.iloc[-1]
    if any(v != v for v in (prev_s, prev_l, now_s, now_l)):  # NaN チェック
        return False
    return prev_s <= prev_l and now_s > now_l


def notify(topic, title, message):
    r = requests.post(
        "https://ntfy.sh/",
        json={
            "topic": topic,
            "title": title,
            "message": message,
            "tags": ["chart_with_upwards_trend"],
        },
        timeout=30,
    )
    r.raise_for_status()


def main():
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        sys.exit("NTFY_TOPIC が設定されていません")

    # テスト通知(手動実行時に動作確認したいとき)
    if os.environ.get("TEST_NOTIFY") == "true":
        notify(topic, "テスト通知", "ゴールデンクロス通知アプリが動いています")
        print("テスト通知を送信しました")
        return

    with open("stocks.json", encoding="utf-8") as f:
        stocks = json.load(f)

    today = datetime.now(JST).date()
    hits = []

    for s in stocks:
        symbol = f"{s['code']}.T"
        try:
            close = yf.Ticker(symbol).history(period="6mo")["Close"].dropna()
        except Exception as e:
            print(f"{symbol}: 取得失敗 {e}")
            continue
        if close.empty:
            print(f"{symbol}: データなし")
            continue

        last_date = close.index[-1].date()
        # 休場日に前営業日のクロスを再通知しないよう、当日の足だけ対象にする
        if last_date != today:
            print(f"{symbol}: 最新の足が {last_date}(本日ではない)のためスキップ")
            continue

        if detect_golden_cross(close):
            hits.append(f"{s['name']}({s['code']}) 終値 {close.iloc[-1]:,.0f}円")
            print(f"{symbol}: ゴールデンクロス!")
        else:
            print(f"{symbol}: クロスなし")

    if hits:
        notify(topic, "ゴールデンクロス検出", "\n".join(hits))


if __name__ == "__main__":
    main()
