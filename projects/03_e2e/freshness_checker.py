import csv
import os
import shutil
from datetime import datetime
from e2e_test_runner import E2ETestRunner
from dom_xpath_handler import DomXPathHandler

def generate_custom_report(results, output_dir):
    """
    Generate a custom HTML report including extracted text/dates.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"site_freshness_report_{timestamp}.html")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Site Freshness Check Report</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background-color: #f9f9f9; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #3498db; color: white; }}
            tr:nth-child(even) {{ background-color: #f8f9fa; }}
            tr:hover {{ background-color: #e9ecef; }}
            .status-pass {{ color: #27ae60; font-weight: bold; }}
            .status-fail {{ color: #c0392b; font-weight: bold; }}
            .status-error {{ color: #e67e22; font-weight: bold; }}
            .screenshot-img {{ max-width: 150px; border: 1px solid #ddd; padding: 2px; }}
            .diff-info {{ color: #e74c3c; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <h1>Site Freshness Check Report</h1>
        <p>Generated at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <table>
            <thead>
                <tr>
                    <th>Site Name</th>
                    <th>URL</th>
                    <th>Status</th>
                    <th>Extracted Data</th>
                    <th>Visual Diff</th>
                    <th>Screenshot</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for res in results:
        status = res.get('status', 'unknown')
        status_class = f"status-{status}"
        
        # Screenshot Link
        screenshot_path = res.get('screenshot_path') or ""
        screenshot_html = ""
        if screenshot_path:
            # Make path relative for the report if possible, or just use name
            filename = os.path.basename(screenshot_path)
            screenshot_html = f'<a href="{filename}" target="_blank"><img src="{filename}" class="screenshot-img"></a>'
        
        # Diff Info
        diff_html = "-"
        if res.get('comparison'):
            comp = res['comparison']
            if not comp.get('identical', True):
                diff_pct = comp.get('difference_percentage', 0)
                diff_html = f"<span class='diff-info'>Diff: {diff_pct}%</span>"
                if comp.get('diff_image_path'):
                     diff_filename = os.path.basename(comp['diff_image_path'])
                     diff_html += f"<br><a href='{diff_filename}' target='_blank'>View Diff</a>"
            else:
                diff_html = "<span style='color: #ccc;'>No Change</span>"
        if res.get('warning'):
             diff_html += f"<br><small>{res['warning']}</small>"

        
        html += f"""
                <tr>
                    <td>{res.get('test_name')}</td>
                    <td><a href="{res.get('url')}">{res.get('url')}</a></td>
                    <td class="{status_class}">{status.upper()}</td>
                    <td>{res.get('extracted_date', 'N/A')}</td>
                    <td>{diff_html}</td>
                    <td>{screenshot_html}</td>
                </tr>
        """
        
    html += """
            </tbody>
        </table>
    </body>
    </html>
    """
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
        
    return report_path

def run_freshness_check():
    # 1. Setup
    print("Initializing Freshness Checker...")
    sites_csv = 'sites.csv'
    
    runner = E2ETestRunner(
        output_dir="./test_results",
        baseline_dir="./baseline",
        compare_baseline=True,
        headless=True
    )
    
    handler = DomXPathHandler(headless=True)
    
    # 2. Read CSV
    if not os.path.exists(sites_csv):
        print("sites.csv not found!")
        return
        
    with open(sites_csv, 'r', encoding='utf-8') as f:
        sites = list(csv.DictReader(f))
        
    print(f"Loaded {len(sites)} sites from CSV.")
    
    # 3. Execution (Separated to avoid Playwright nesting)
    results = []
    visual_results_map = {}
    
    # Phase A: Visual Checks (using Runner)
    print("\n--- Phase A: Visual Checks ---")
    for site in sites:
        name = site['site_name']
        url = site['url']
        print(f"[{name}] Visual Check...")
        
        # Explicitly pass baseline path to enable comparison/creation
        baseline_path = os.path.join("./baseline", f"{name}_baseline.png")
        
        test_result = runner.run_test(
            test_name=name,
            url=url,
            baseline_path=baseline_path
        )
        visual_results_map[name] = test_result

    # Phase B: Content Checks (using Handler)
    print("\n--- Phase B: Content Checks ---")
    content_results_map = {}
    with handler:
        for site in sites:
            name = site['site_name']
            url = site['url']
            xpath = site['date_xpath']
            print(f"[{name}] Content Check...")
            
            extracted_text = "N/A"
            if xpath:
                try:
                    texts = handler.get_text_by_xpath(url, xpath)
                    if texts:
                        extracted_text = texts[0]
                    else:
                        extracted_text = "(Not Found)"
                except Exception as e:
                    extracted_text = f"Error: {str(e)}"
            
            content_results_map[name] = extracted_text

    # Merge Results
    for site in sites:
        name = site['site_name']
        res = visual_results_map.get(name)
        res['extracted_date'] = content_results_map.get(name, "N/A")
        results.append(res)
        print(f"[{name}] Final Status: {res['status']}, Extracted: {res['extracted_date']}")
        if res.get('error'):
            print(f"  Error details: {res['error']}")

    # 4. Reporting
    report_file = generate_custom_report(results, "./test_results")
    print(f"\nCompleted! Report saved to: {report_file}")

if __name__ == "__main__":
    run_freshness_check()
