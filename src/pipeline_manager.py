# src/pipeline_manager.py 内の抜粋

def _process_single_pair(self, pair_name: str, symbol: str, target_date: date):
    df_accumulated = self.storage.load_pair_data(symbol)
    if df_accumulated.empty:
        return

    # 前日(target_date)のデータを抽出
    df_day = df_accumulated[df_accumulated.index.date == target_date].sort_index()
    actual_count = len(df_day)

    if actual_count == 0:
        return

    # 曜日判定 (0: 月曜日, 1: 火曜日 ... 6: 日曜日)
    # target_date が月曜日の場合、07:00オープン開始のため本数が少ない(約204本)
    is_monday = (target_date.weekday() == 0)
    
    # 確定条件の閾値設定
    # 月曜日は200本以上、それ以外の営業日は288本で確定とみなす
    required_count = 200 if is_monday else 288

    # 本数チェック ＋ 最終データが23:50以降まで存在するかチェック
    latest_time = df_day.index[-1].time()
    is_day_complete = (actual_count >= required_count) and (latest_time.hour == 23 and latest_time.minute >= 50)

    if is_day_complete:
        self.logger.info(
            "完全データ検知",
            f"[{pair_name}] 前日[{target_date}] (月曜特例: {is_monday}) のデータ確定({actual_count}本)を確認。処理を開始します。",
        )

        df_verified = self.reporter.extract_verified_full_day_with_logging(
            df_accumulated, target_date=target_date, pair_label=pair_name
        )

        if df_verified.empty:
            return

        # --- 以下、スプレッドシート・チャート・AIレポート・Discord送信処理 ---
        # (従来のロジックを実行)
    else:
        self.logger.info(
            "データ蓄積中",
            f"[{pair_name}] 前日[{target_date}] 蓄積本数: {actual_count}/{required_count}本 (最終データ: {latest_time})",
        )
