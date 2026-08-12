# main.py

import json
import os
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

from src.daily_reporter import FXDailyReporter
from src.system_logger import SystemLogger
from src.visualizer import BacktestVisualizer

# Webhook URL (環境変数等から取得)
REPORT_WEBHOOK_URL = os.getenv("DISCORD_REPORT_WEBHOOK_URL")  # #daily-summary
LOG_WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")  # #system-logs

# 対象の9通貨ペア定義
PAIRS = {
    "米ドル/円": "JPY=X",
    "ユーロ/円": "EURJPY=X",
    "英ポンド/円": "GBPJPY=X",
    "スイスフラン/円": "CHFJPY=X",
    "カナダドル/円": "CADJPY=X",
    "豪ドル/円": "AUDJPY=X",
    "NZドル/円": "NZDJPY=X",
    "人民元/円": "CNYJPY=X",
    "インドルピー/円": "INRJPY=X",
}

BASE_DATA_DIR = "data"


def save_split_data_to_json(bulk_df: pd.DataFrame, base_dir: str = BASE_DATA_DIR):
    """一括取得データを data/{symbol}/data.json に振り分け保存"""
    for pair_name, symbol in PAIRS.items():
        try:
            if isinstance(bulk_df.columns, pd.MultiIndex) and symbol in bulk_df.columns.levels[0]:
                df_pair = bulk_df[symbol].copy().dropna(subset=["Close"])
            elif not isinstance(bulk_df.columns, pd.MultiIndex):
                df_pair = bulk_df.copy().dropna(subset=["Close"])
            else:
                continue

            records = []
            for idx, row in df_pair.iterrows():
                records.append({
                    "timestamp": idx.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]) if "Volume" in row else 0,
                })

            pair_dir = os.path.join(base_dir, symbol)
            os.makedirs(pair_dir, exist_ok=True)

            json_path = os.path.join(pair_dir, "data.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"個別JSON保存エラー ({symbol}): {e}")


def load_pair_data_from_json(symbol: str, base_dir: str = BASE_DATA_DIR) -> pd.DataFrame:
    """data/{symbol}/data.json からデータを読み込み DataFrame 化"""
    json_path = os.path.join(base_dir, symbol, "data.json")

    if not os.path.exists(json_path):
        return pd.DataFrame()

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["Datetime"] = pd.to_datetime(df["timestamp"])
    df.set_index("Datetime", inplace=True)
    df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
    return df


def main():
    logger = SystemLogger(webhook_url=LOG_WEBHOOK_URL)
    target_date = (datetime.now() - timedelta(days=1)).date()

    # Step 1: 一括取得 ➔ ディレクトリ振り分け保存
    logger.info("一括取得開始", f"対象日 [{target_date}] の9通貨ペアのデータを取得し、`{BASE_DATA_DIR}/{{symbol}}/data.json` へ保存します。")

    ticker_symbols = list(PAIRS.values())
    try:
        bulk_df = yf.download(
            tickers=ticker_symbols,
            period="5d",
            interval="5m",
            group_by="ticker",
            progress=False,
        )

        save_split_data_to_json(bulk_df, base_dir=BASE_DATA_DIR)
        logger.info("保存完了", f"全9通貨ペアの個別 `{BASE_DATA_DIR}/{{symbol}}/data.json` への保存が完了しました。")

    except Exception as e:
        logger.error("取得・保存エラー", f"データの一括取得または個別JSON書き出し中に例外が発生しました:\n{e}")
        return

    # Step 2: 個別読み込み ➔ 検証 ➔ レポート作成・送信
    for pair_name, symbol in PAIRS.items():
        logger.info("個別処理開始", f"=== 【{pair_name}】({symbol}) のデータ検証・出力処理を開始 ===")

        try:
            df_pair = load_pair_data_from_json(symbol, base_dir=BASE_DATA_DIR)

            if df_pair.empty:
                logger.warning("データ未存在", f"[{pair_name}] の JSON ファイル ({BASE_DATA_DIR}/{symbol}/data.json) が読み込めませんでした。")
                continue

            reporter = FXDailyReporter(pips_value=0.01, logger=logger)
            df_day = reporter.extract_verified_full_day_with_logging(df_pair, target_date=target_date, pair_label=pair_name)

            if df_day.empty:
                logger.warning("処理スキップ", f"[{pair_name}] は288本完全データが不揃いのため出力を保留します。")
                continue

            chart_filename = f"chart_{symbol.replace('=X', '')}.png"
            BacktestVisualizer.plot_daily_line_chart(
                df_day, pair_title=f"{pair_name} ({symbol})", target_date=target_date, save_path=chart_filename
            )

            report = reporter.generate_report(df_day, pair_name=pair_name)
            success = reporter.send_discord_webhook(report, REPORT_WEBHOOK_URL, image_path=chart_filename)

            if success:
                logger.info("送信完了", f"[{pair_name}] のレポート・画像を正常送信しました。")

            if os.path.exists(chart_filename):
                os.remove(chart_filename)

        except Exception as e:
            logger.error("個別例外エラー", f"[{pair_name}] 処理中に予期せぬ例外が発生しました:\n{e}")

    logger.info("全処理完了", "全9通貨ペアの個別データ読み込み・検証・配信が完了しました。")


if __name__ == "__main__":
    main()
