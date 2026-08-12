import json
import os
import time
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

from src.daily_reporter import FXDailyReporter
from src.system_logger import SystemLogger
from src.visualizer import BacktestVisualizer

# Webhook URL
REPORT_WEBHOOK_URL = os.getenv("DISCORD_REPORT_WEBHOOK_URL")  # #daily-summary
LOG_WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")  # #system-logs

# 9通貨ペアの定義
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


def fetch_bulk_data_with_retry(
    symbols: list, max_retries: int = 5
) -> pd.DataFrame:
    """429エラー(Rate Limit)対策を入れた一括取得ロジック"""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"データ一括取得試行中... ({attempt}/{max_retries})")
            # 1dで最新データを取得
            bulk_df = yf.download(
                tickers=symbols,
                period="1d",
                interval="5m",
                group_by="ticker",
                progress=False,
            )

            if not bulk_df.empty:
                return bulk_df

        except Exception as e:
            print(f"取得エラー発生 ({attempt}/{max_retries}): {e}")

        wait_time = attempt * 10
        print(f"429回避のため {wait_time} 秒待機して再試行します...")
        time.sleep(wait_time)

    return pd.DataFrame()


def append_latest_data_to_json(
    bulk_df: pd.DataFrame, base_dir: str = BASE_DATA_DIR
) -> bool:
    """最新の1本（実行時間データ）を抽出し、既存の data.json へ追記保存する"""
    if bulk_df.empty:
        return False

    saved_any = False

    for pair_name, symbol in PAIRS.items():
        try:
            # MultiIndex構造からの抽出
            if (
                isinstance(bulk_df.columns, pd.MultiIndex)
                and symbol in bulk_df.columns.levels[0]
            ):
                df_pair = bulk_df[symbol].copy().dropna(subset=["Close"])
            elif not isinstance(bulk_df.columns, pd.MultiIndex):
                df_pair = bulk_df.copy().dropna(subset=["Close"])
            else:
                continue

            if df_pair.empty:
                continue

            # 最新の1行（実行時間のデータ）のみを取得
            latest_row = df_pair.iloc[-1:]
            latest_ts = latest_row.index[0].strftime("%Y-%m-%d %H:%M:%S")

            new_record = {
                "timestamp": latest_ts,
                "open": float(latest_row["Open"].iloc[0]),
                "high": float(latest_row["High"].iloc[0]),
                "low": float(latest_row["Low"].iloc[0]),
                "close": float(latest_row["Close"].iloc[0]),
                "volume": (
                    int(latest_row["Volume"].iloc[0])
                    if "Volume" in latest_row
                    else 0
                ),
            }

            pair_dir = os.path.join(base_dir, symbol)
            os.makedirs(pair_dir, exist_ok=True)
            json_path = os.path.join(pair_dir, "data.json")

            # 既存の JSON があれば読み込み、無ければ空リスト
            existing_records = []
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    try:
                        existing_records = json.load(f)
                    except json.JSONDecodeError:
                        existing_records = []

            # 重複チェック (同じ timestamp が無ければ末尾に追加)
            existing_timestamps = {r["timestamp"] for r in existing_records}
            if new_record["timestamp"] not in existing_timestamps:
                existing_records.append(new_record)

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(existing_records, f, ensure_ascii=False, indent=2)

                print(
                    f"[{symbol}] 最新データを追記完了 ({latest_ts}) / 総本数: {len(existing_records)}"
                )
            else:
                print(
                    f"[{symbol}] 既に同一時刻データ存在のためスキップ ({latest_ts})"
                )

            saved_any = True

        except Exception as e:
            print(f"JSON追記処理エラー ({symbol}): {e}")

    return saved_any


def load_pair_data_from_json(
    symbol: str, base_dir: str = BASE_DATA_DIR
) -> pd.DataFrame:
    """data/{symbol}/data.json からデータを読み込んで DataFrame 化"""
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
    df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        inplace=True,
    )
    return df


def main():
    logger = SystemLogger(webhook_url=LOG_WEBHOOK_URL)

    # 前日確定分をターゲット（日次集計用）
    target_date = (datetime.now() - timedelta(days=1)).date()

    logger.info(
        "パイプライン起動",
        f"実行時刻の最新1本を取得し `data/{{symbol}}/data.json` に追記します。",
    )

    # Step 1: 実行時間の最新1本を取得 ➔ data.json へ追記
    ticker_symbols = list(PAIRS.values())
    bulk_df = fetch_bulk_data_with_retry(ticker_symbols, max_retries=5)

    if bulk_df.empty:
        logger.error(
            "取得失敗",
            "Yahoo Financeからのデータ取得に失敗（またはレートリミット到達）しました。",
        )
        return

    save_success = append_latest_data_to_json(bulk_df, base_dir=BASE_DATA_DIR)
    if not save_success:
        logger.error(
            "JSON追記失敗",
            f"`{BASE_DATA_DIR}/{{symbol}}/data.json` への追記に失敗しました。",
        )
        return

    logger.info(
        "JSON追記完了",
        f"全対象ペアの最新データ追記・保存処理が完了しました。",
    )

    # Step 2: 各通貨の data.json から蓄積されたデータを読み込んで検証・送信判定
    for pair_name, symbol in PAIRS.items():
        try:
            df_pair = load_pair_data_from_json(symbol, base_dir=BASE_DATA_DIR)

            if df_pair.empty:
                continue

            reporter = FXDailyReporter(pips_value=0.01, logger=logger)
            df_day = df_pair[df_pair.index.date == target_date].sort_index()
            actual_count = len(df_day)

            # 対象（前日分）のデータが 288 本揃っていたら正式レポートを送信
            if actual_count == 288:
                logger.info(
                    "完全データ検知",
                    f"[{pair_name}] 前日[{target_date}] の288本蓄積完了を確認。レポートを配信します。",
                )

                df_verified = (
                    reporter.extract_verified_full_day_with_logging(
                        df_pair, target_date=target_date, pair_label=pair_name
                    )
                )
                if not df_verified.empty:
                    chart_filename = f"chart_{symbol.replace('=X', '')}.png"
                    BacktestVisualizer.plot_daily_line_chart(
                        df_verified,
                        pair_title=f"{pair_name} ({symbol})",
                        target_date=target_date,
                        save_path=chart_filename,
                    )

                    report = reporter.generate_report(
                        df_verified, pair_name=pair_name
                    )
                    success = reporter.send_discord_webhook(
                        report, REPORT_WEBHOOK_URL, image_path=chart_filename
                    )

                    if success:
                        logger.info(
                            "送信完了",
                            f"[{pair_name}] の確定日次レポートを送信しました。",
                        )
                    if os.path.exists(chart_filename):
                        os.remove(chart_filename)
            else:
                logger.info(
                    "データ蓄積中",
                    f"[{pair_name}] 前日[{target_date}] の蓄積本数: {actual_count}/288本",
                )

            time.sleep(0.5)

        except Exception as e:
            logger.error(
                "個別例外エラー",
                f"[{pair_name}] 処理中に予期せぬ例外が発生しました:\n{e}",
            )

    logger.info("全処理完了", "パイプラインの実行が正常に終了しました。")


if __name__ == "__main__":
    main()
