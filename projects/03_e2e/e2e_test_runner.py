"""
E2E Test Runner Module

【使用方法】
from e2e_test_runner import E2ETestRunner

# テストランナー作成
runner = E2ETestRunner(
    output_dir="./test_results",
    compare_baseline=True
)

# 単一テスト実行
result = runner.run_test(
    test_name="homepage_test",
    url="https://example.com",
    baseline_path="./baseline/homepage.png"
)

# 複数テスト実行
results = runner.run_test_suite([
    {"name": "homepage", "url": "https://example.com"},
    {"name": "about", "url": "https://example.com/about"}
])

# テストレポート生成
runner.generate_test_report("./test_results/report.json")

【処理内容】
1. Playwrightでスクリーンショット撮影
2. スクリーンショットを解析・処理
3. ベースライン画像と比較（差分検出）
4. テスト結果をレポートとして出力
5. 失敗時は差分画像を保存
"""

from playwright_capture import PlaywrightCapture
from screenshot_processor import ScreenshotProcessor
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import shutil


class E2ETestRunner:
    """
    E2Eテストを実行し、スクリーンショットの撮影・比較を行うクラス
    """

    def __init__(
        self,
        output_dir: str = "./test_results",
        baseline_dir: str = "./baseline",
        compare_baseline: bool = False,
        headless: bool = True,
        threshold: float = 1.0
    ):
        """
        初期化

        Args:
            output_dir: テスト結果の出力ディレクトリ
            baseline_dir: ベースライン画像のディレクトリ
            compare_baseline: ベースライン比較を行うか
            headless: ヘッドレスモードで実行するか
            threshold: 差分許容率（%）
        """
        self.output_dir = Path(output_dir)
        self.baseline_dir = Path(baseline_dir)
        self.compare_baseline = compare_baseline
        self.headless = headless
        self.threshold = threshold

        self.processor = ScreenshotProcessor()
        self.test_results: List[Dict] = []

        # ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.compare_baseline:
            self.baseline_dir.mkdir(parents=True, exist_ok=True)

    def run_test(
        self,
        test_name: str,
        url: str,
        baseline_path: Optional[str] = None,
        interactions: Optional[List[Dict]] = None,
        wait_time: int = 2000,
        viewport_size: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        単一テストを実行

        Input:
            test_name: テスト名
            url: テスト対象URL
            baseline_path: ベースライン画像のパス（比較する場合）
            interactions: ページ操作のリスト
            wait_time: 読み込み待機時間
            viewport_size: ビューポートサイズ
            metadata: 追加メタデータ

        Output:
            Dict: テスト結果
                {
                    "test_name": "...",
                    "url": "...",
                    "status": "pass|fail|error",
                    "screenshot_path": "...",
                    "analyzed_at": "...",
                    "comparison": {...},
                    "error": "..."
                }
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_filename = f"{test_name}_{timestamp}.png"
        screenshot_path = self.output_dir / screenshot_filename

        result = {
            "test_name": test_name,
            "url": url,
            "status": "error",
            "screenshot_path": None,
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "comparison": None,
            "error": None,
            "metadata": metadata or {}
        }

        try:
            # スクリーンショット撮影
            with PlaywrightCapture(headless=self.headless) as capture:
                if interactions:
                    saved_path = capture.capture_with_interaction(
                        url=url,
                        output_path=str(screenshot_path),
                        interactions=interactions,
                        wait_time=wait_time,
                        viewport_size=viewport_size
                    )
                else:
                    saved_path = capture.capture_screenshot(
                        url=url,
                        output_path=str(screenshot_path),
                        wait_time=wait_time,
                        viewport_size=viewport_size
                    )

            result["screenshot_path"] = saved_path

            # 画像解析
            analysis = self.processor.analyze_screenshot(saved_path)
            result["analysis"] = analysis

            # メタデータ付き画像を作成
            if metadata:
                annotated_path = self.output_dir / f"{test_name}_{timestamp}_annotated.png"
                self.processor.add_metadata(
                    image_path=saved_path,
                    output_path=str(annotated_path),
                    metadata=metadata
                )
                result["annotated_path"] = str(annotated_path)

            # ベースライン比較
            if self.compare_baseline and baseline_path:
                baseline = Path(baseline_path)
                if baseline.exists():
                    diff_path = self.output_dir / f"{test_name}_{timestamp}_diff.png"
                    comparison = self.processor.compare_screenshots(
                        image1_path=str(baseline),
                        image2_path=saved_path,
                        output_path=str(diff_path) if not result.get("comparison", {}).get("identical", False) else None
                    )

                    result["comparison"] = comparison

                    # 差分判定
                    if comparison["identical"]:
                        result["status"] = "pass"
                    elif comparison["difference_percentage"] <= self.threshold:
                        result["status"] = "pass"
                        result["warning"] = f"Minor differences detected: {comparison['difference_percentage']}%"
                    else:
                        result["status"] = "fail"
                        result["error"] = f"Screenshot differs by {comparison['difference_percentage']}%"
                else:
                    # ベースラインが存在しない場合は新規作成
                    shutil.copy(saved_path, baseline)
                    result["status"] = "pass"
                    result["warning"] = "Baseline created"
            else:
                # 比較なしの場合は常にpass
                result["status"] = "pass"

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        self.test_results.append(result)
        return result

    def run_test_suite(
        self,
        test_cases: List[Dict],
        create_baseline: bool = False
    ) -> List[Dict]:
        """
        テストスイートを実行

        Input:
            test_cases: テストケースのリスト
                [
                    {
                        "name": "test1",
                        "url": "https://example.com",
                        "interactions": [...],
                        "metadata": {...}
                    }
                ]
            create_baseline: ベースライン画像を作成するか

        Output:
            List[Dict]: テスト結果のリスト
        """
        results = []

        for test_case in test_cases:
            test_name = test_case["name"]
            url = test_case["url"]
            interactions = test_case.get("interactions")
            wait_time = test_case.get("wait_time", 2000)
            viewport_size = test_case.get("viewport_size")
            metadata = test_case.get("metadata", {})

            # ベースラインパス
            baseline_path = None
            if self.compare_baseline or create_baseline:
                baseline_path = self.baseline_dir / f"{test_name}_baseline.png"

            result = self.run_test(
                test_name=test_name,
                url=url,
                baseline_path=str(baseline_path) if baseline_path else None,
                interactions=interactions,
                wait_time=wait_time,
                viewport_size=viewport_size,
                metadata=metadata
            )

            results.append(result)

        return results

    def generate_test_report(
        self,
        output_path: Optional[str] = None,
        format: str = "json"
    ) -> str:
        """
        テストレポートを生成

        Input:
            output_path: レポート出力パス（Noneの場合は自動生成）
            format: レポート形式 ("json", "html")

        Output:
            str: 生成されたレポートのパス
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"test_report_{timestamp}.{format}"
        else:
            output_path = Path(output_path)

        # 統計情報
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["status"] == "pass")
        failed = sum(1 for r in self.test_results if r["status"] == "fail")
        errors = sum(1 for r in self.test_results if r["status"] == "error")

        report = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "pass_rate": round((passed / total * 100) if total > 0 else 0, 2)
            },
            "test_results": self.test_results
        }

        if format == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        elif format == "html":
            html_content = self._generate_html_report(report)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

        return str(output_path.absolute())

    def _generate_html_report(self, report: Dict) -> str:
        """HTMLレポートを生成"""
        summary = report["summary"]
        results = report["test_results"]

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>E2E Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .summary-item {{ display: inline-block; margin-right: 20px; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        .error {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .screenshot {{ max-width: 200px; }}
    </style>
</head>
<body>
    <h1>E2E Test Report</h1>
    <p>Generated at: {report['generated_at']}</p>

    <div class="summary">
        <h2>Summary</h2>
        <div class="summary-item"><strong>Total:</strong> {summary['total']}</div>
        <div class="summary-item pass"><strong>Passed:</strong> {summary['passed']}</div>
        <div class="summary-item fail"><strong>Failed:</strong> {summary['failed']}</div>
        <div class="summary-item error"><strong>Errors:</strong> {summary['errors']}</div>
        <div class="summary-item"><strong>Pass Rate:</strong> {summary['pass_rate']}%</div>
    </div>

    <h2>Test Results</h2>
    <table>
        <tr>
            <th>Test Name</th>
            <th>URL</th>
            <th>Status</th>
            <th>Screenshot</th>
            <th>Details</th>
        </tr>
"""

        for result in results:
            status_class = result['status']
            screenshot_html = ""
            if result.get('screenshot_path'):
                screenshot_html = f'<a href="{result["screenshot_path"]}">View</a>'

            details = result.get('error') or result.get('warning') or '-'

            html += f"""
        <tr>
            <td>{result['test_name']}</td>
            <td>{result['url']}</td>
            <td class="{status_class}">{result['status'].upper()}</td>
            <td>{screenshot_html}</td>
            <td>{details}</td>
        </tr>
"""

        html += """
    </table>
</body>
</html>
"""
        return html

    def clear_results(self):
        """テスト結果をクリア"""
        self.test_results = []


# ユーティリティ関数
def quick_test(url: str, test_name: str = "quick_test", **kwargs) -> Dict:
    """
    クイックテスト実行

    Input:
        url: テスト対象URL
        test_name: テスト名
        **kwargs: run_testに渡す追加引数

    Output:
        Dict: テスト結果
    """
    runner = E2ETestRunner()
    return runner.run_test(test_name=test_name, url=url, **kwargs)
