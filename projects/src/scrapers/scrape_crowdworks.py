"""
CrowdWorks案件情報スクレイピング実行スクリプト

【使用方法】
python scrape_crowdworks.py

【処理内容】
1. CrowdWorksの案件一覧ページにアクセス
2. 案件情報を1件取得
3. 取得したデータを表示して確認を求める
4. CSVファイルに出力
"""

import sys
from pathlib import Path

# モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).parent))

from crowdworks_scraper import CrowdWorksScraper


def main():
    """メイン処理"""
    url = "https://crowdworks.jp/public/jobs/group/ec"
    output_csv = Path(__file__).parent.parent / "10_raw" / "crowdworks_jobs.csv"
    
    print("="*60)
    print("CrowdWorks案件情報スクレイピング開始")
    print("="*60)
    print(f"対象URL: {url}")
    print(f"出力先: {output_csv}")
    print()

    # スクレイパーを作成（headless=Falseでブラウザを表示）
    scraper = CrowdWorksScraper(headless=False)

    try:
        with scraper:
            # 案件情報を取得（1件取得後に停止）
            jobs_data = scraper.scrape_jobs(
                url=url,
                max_jobs=1,
                stop_after_first=True,
                wait_time=3000
            )

            if jobs_data:
                print("\n" + "="*60)
                print("取得した案件情報")
                print("="*60)
                for idx, job in enumerate(jobs_data, 1):
                    print(f"\n【案件 {idx}】")
                    print(f"URL: {job.get('url', 'N/A')}")
                    print(f"タイトル: {job.get('title', 'N/A')}")
                    print(f"価格: {job.get('price', 'N/A')}")
                    print(f"説明: {job.get('description', 'N/A')[:200]}...")
                    print(f"期限: {job.get('deadline', 'N/A')}")
                    print(f"カテゴリー: {job.get('category', 'N/A')}")
                    print(f"スキル: {job.get('skills', 'N/A')}")

                # CSVに保存
                scraper.save_to_csv(jobs_data, str(output_csv))
                print(f"\nCSVファイルに保存しました: {output_csv}")
            else:
                print("案件情報を取得できませんでした。")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

