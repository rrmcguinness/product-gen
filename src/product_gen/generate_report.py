import json
import os
from pathlib import Path
import sys
from typing import Dict, Any, List

# Add project root to path
sys.path.append("/Users/rmcguinness/Projects/customers/walmart/product-gen/src")

from product_gen.report import generate_pdf_report

def run_report(output_dir: Path) -> None:
    """
    Scans the output directory for product_detail.json files and generates a summary PDF report.
    """
    stats: Dict[str, Any] = {
        "total_processed": 0,
        "success_count": 0,
        "fail_count": 0,
        "total_retries": 0,
        "errors": [],
        "product_details": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_time": 0.0,
        "total_input_cost": 0.0,
        "total_output_cost": 0.0,
        "total_cost": 0.0,
        "total_http_errors": {},
        "retries_to_pass_list": [],
        "try_buckets": {
            "try_1": 0,
            "try_2": 0,
            "try_3": 0,
            "try_4": 0,
            "try_5": 0,
            "failed": 0
        }
    }
    
    # Assumed rates (Gemini 1.5 Pro)
    INPUT_RATE = 0.000007
    OUTPUT_RATE = 0.000021
    
    # Scan output directory
    for item in output_dir.iterdir():
        if item.is_dir():
            detail_path = item / "product_detail.json"
            if detail_path.exists():
                try:
                    with open(detail_path, "r") as f:
                        data = json.load(f)
                        
                    stats["total_processed"] += 1
                    
                    prod_success = 0
                    prod_fail = 0
                    prod_retries = 0
                    
                    reviews = data.get("image_reviews", [])
                    best_score = 0.0
                    threshold = float(os.environ.get("PASS_THRESHOLD", "0.9"))
                    if reviews:
                        best_score = max((r.get("score", 0.0) for r in reviews), default=0.0)
                        for review in reviews:
                            score = review.get("score", 0.0)
                            retries = review.get("retry_count", 0)
                            
                            if score >= threshold:
                                prod_success += 1
                            else:
                                prod_fail += 1
                                
                            prod_retries += retries
                            
                        if prod_success > 0:
                            stats["success_count"] += 1
                        else:
                            stats["fail_count"] += 1
                    else:
                        # No reviews (likely no reference images to judge against).
                        # Fallback to checking if images were generated and saved.
                        images = list(item.glob("image_*.jpeg"))
                        if images:
                            stats["success_count"] += 1
                            prod_success = len(images)
                            best_score = 1.0
                        else:
                            stats["fail_count"] += 1
                            prod_fail = 1
                        
                    category_data = data.get("category", {})
                    category_str = "Unknown"
                    if isinstance(category_data, dict):
                        category_str = f"{category_data.get('level_1', 'Unknown')} > {category_data.get('level_2', 'Unknown')}"
                        
                    metrics = data.get("metrics", {})
                    prod_tokens = 0
                    prod_time = 0.0
                    prod_cost = 0.0
                    
                    if metrics:
                        prod_time = metrics.get("total_time", 0.0)
                        
                        # Use total_retries from metrics if available
                        stats["total_retries"] += metrics.get("total_retries", 0)
                        
                        # Collect HTTP errors
                        prod_http_errors = metrics.get("http_errors", {})
                        for code, count in prod_http_errors.items():
                            code_str = str(code)
                            stats["total_http_errors"][code_str] = stats["total_http_errors"].get(code_str, 0) + count
                            
                        # Collect retries to pass
                        retries_to_pass = metrics.get("retries_to_pass")
                        if retries_to_pass is not None:
                            stats["retries_to_pass_list"].append(retries_to_pass)
                            
                        if prod_success > 0:
                            r = retries_to_pass if retries_to_pass is not None else 0
                            if r == 0:
                                stats["try_buckets"]["try_1"] += 1
                            elif r == 1:
                                stats["try_buckets"]["try_2"] += 1
                            elif r == 2:
                                stats["try_buckets"]["try_3"] += 1
                            elif r == 3:
                                stats["try_buckets"]["try_4"] += 1
                            elif r >= 4:
                                stats["try_buckets"]["try_5"] += 1
                        else:
                            stats["try_buckets"]["failed"] += 1
                        
                        prod_input_tokens = 0
                        prod_output_tokens = 0
                        
                        enrich_tokens = 0
                        desc_tokens = 0
                        img1_tokens = 0
                        judge_tokens = 0
                        
                        base_cost = 0.0
                        base_input_cost = 0.0
                        base_output_cost = 0.0
                        for step in metrics.get("steps", []):
                            step_name = step.get("step_name", "")
                            tokens = step.get("total_tokens", 0) or 0
                            input_tokens = step.get("input_tokens", 0) or 0
                            output_tokens = step.get("output_tokens", 0) or 0
                            
                            prod_input_tokens += input_tokens
                            prod_output_tokens += output_tokens
                            
                            # Gemini 2.5 Pro rates
                            if input_tokens <= 200000:
                                input_rate = 0.00000125
                                output_rate = 0.000010
                            else:
                                input_rate = 0.0000025
                                output_rate = 0.000015
                                
                            base_cost += (input_tokens * input_rate) + (output_tokens * output_rate)
                            base_input_cost += input_tokens * input_rate
                            base_output_cost += output_tokens * output_rate
                            
                            if "Enrich" in step_name:
                                enrich_tokens += tokens
                            elif "Describe" in step_name:
                                desc_tokens += tokens
                            elif "Generate Image 1" in step_name:
                                img1_tokens += tokens
                            elif "Judge" in step_name:
                                judge_tokens += tokens
                            
                        prod_input_cost = base_input_cost * 0.9
                        prod_output_cost = base_output_cost * 0.9
                        prod_cost = base_cost * 0.9
                        prod_tokens = prod_input_tokens + prod_output_tokens # Recalculate to be sure
                        
                        stats["total_input_tokens"] += prod_input_tokens
                        stats["total_output_tokens"] += prod_output_tokens
                        stats["total_tokens"] += prod_tokens
                        stats["total_time"] += prod_time
                        stats["total_input_cost"] += prod_input_cost
                        stats["total_output_cost"] += prod_output_cost
                        stats["total_cost"] += prod_cost
                        
                    stats["product_details"].append({
                        "id": item.name,
                        "category": category_str,
                        "success": prod_success,
                        "fail": prod_fail,
                        "retries": prod_retries,
                        "tokens": prod_tokens,
                        "time": prod_time,
                        "cost": prod_cost,
                        "enrich_tokens": enrich_tokens,
                        "desc_tokens": desc_tokens,
                        "img1_tokens": img1_tokens,
                        "judge_tokens": judge_tokens,
                        "best_score": best_score
                    })
                    
                except Exception as e:
                    stats["errors"].append(f"Error reading {detail_path}: {e}")
                    
    # Calculate median retries to pass
    retries_list = stats.pop("retries_to_pass_list", [])
    median_retries = 0.0
    if retries_list:
        s_list = sorted(retries_list)
        n = len(s_list)
        if n % 2 != 0:
            median_retries = float(s_list[n//2])
        else:
            median_retries = (s_list[n//2 - 1] + s_list[n//2]) / 2.0
    stats["median_retries"] = median_retries
                    
    # Calculate time stats
    times = [prod["time"] for prod in stats["product_details"] if prod["time"] > 0]
    stats["min_time"] = min(times) if times else 0.0
    stats["max_time"] = max(times) if times else 0.0
    stats["avg_time"] = sum(times) / len(times) if times else 0.0
                    
    # Calculate score distribution
    score_buckets = [0] * 10
    for prod in stats["product_details"]:
        score = int(prod.get("best_score", 0.0) * 100)
        bucket = min(score // 10, 9)
        score_buckets[bucket] += 1
        
    # Calculate category stats
    category_stats = {}
    for prod in stats["product_details"]:
        cat = prod["category"]
        top_cat = cat.split(" > ")[0] if " > " in cat else cat
        status = "Pass" if prod["success"] > 0 else "Review"
        
        if top_cat not in category_stats:
            category_stats[top_cat] = {"pass": 0, "review": 0}
            
        if status == "Pass":
            category_stats[top_cat]["pass"] += 1
        else:
            category_stats[top_cat]["review"] += 1
            
    cat_labels = list(category_stats.keys())
    cat_pass_data = [category_stats[c]["pass"] for c in cat_labels]
    cat_review_data = [category_stats[c]["review"] for c in cat_labels]

    # Generate HTML Report
    threshold = float(os.environ.get("PASS_THRESHOLD", "0.9"))
    grid_items_html = ""
    for prod in stats["product_details"]:
        status = "Pass" if prod["success"] > 0 else "Review"
        status_class = "status-pass" if status == "Pass" else "status-review"
        top_cat = prod["category"].split(" > ")[0] if " > " in prod["category"] else prod["category"]
        
        grid_items_html += f"""
        <a href="{prod['id']}/index.html" class="product-card" data-score="{int(prod['best_score'] * 100)}" data-category="{top_cat}">
            <div class="status-tag {status_class}">{status}</div>
            <div class="product-id">{prod['id']}</div>
            <div class="product-category">{prod['category']}</div>
            <div style="margin-top: 10px; font-size: 12px; color: var(--text-sub);">
                Score: {int(prod['best_score'] * 100)} / {int(threshold * 100)} | Time: {prod['time']:.2f}s
            </div>
        </a>
        """
        
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pipeline Execution Report</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            :root {{
                --bg-dark: #0b0f19;
                --bg-card: #151c2c;
                --bg-card-hover: #1e2638;
                --text-main: #f3f4f6;
                --text-sub: #9ca3af;
                --accent-blue: #60a5fa;
                --accent-cyan: #22d3ee;
                --accent-green: #059669;
                --accent-red: #dc2626;
                --border-color: #262f45;
                --card-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.5);
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
            body {{ background-color: var(--bg-dark); color: var(--text-main); padding: 20px; }}
            header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid var(--border-color); padding: 30px; margin-bottom: 30px; border-radius: 12px; position: relative; box-shadow: var(--card-shadow); }}
            header h1 {{ font-size: 28px; margin-bottom: 10px; background: linear-gradient(to right, #60a5fa, #22d3ee); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
            .summary-cards {{ display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
            .summary-card {{ background: var(--bg-card); padding: 20px; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: var(--card-shadow); text-align: center; flex: 1; min-width: 200px; transition: transform 0.3s; }}
            .summary-card:hover {{ transform: translateY(-5px); }}
            .summary-value {{ font-size: 32px; font-weight: bold; color: var(--accent-cyan); margin-bottom: 5px; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; }}
            .product-card {{ background: var(--bg-card); padding: 25px; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: var(--card-shadow); position: relative; text-decoration: none; color: inherit; display: flex; flex-direction: column; justify-content: space-between; transition: all 0.3s ease; }}
            .product-card:hover {{ transform: translateY(-5px); background: var(--bg-card-hover); border-color: var(--accent-blue); box-shadow: 0 10px 25px -5px rgba(59, 130, 246, 0.3); }}
            .status-tag {{ position: absolute; top: 15px; right: 15px; padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; color: #fff; }}
            .status-pass {{ background-color: var(--accent-green); box-shadow: 0 0 10px rgba(52, 211, 153, 0.3); }}
            .status-review {{ background-color: var(--accent-red); box-shadow: 0 0 10px rgba(248, 113, 113, 0.3); }}
            .product-id {{ font-size: 18px; font-weight: bold; margin-bottom: 8px; color: var(--accent-blue); }}
            .product-category {{ font-size: 13px; color: var(--text-sub); }}
            .chart-card {{ background: var(--bg-card); padding: 25px; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: var(--card-shadow); margin-bottom: 30px; }}
            .charts-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 30px; }}
            @media (max-width: 768px) {{
                .charts-container {{ grid-template-columns: 1fr; }}
            }}
            .reset-btn {{
                position: absolute;
                top: 30px;
                right: 30px;
                padding: 10px 20px;
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                cursor: pointer;
                display: none;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                transition: all 0.2s;
            }}
            .reset-btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
                opacity: 0.9;
            }}
        </style>
    </head>
    <body>
        <header>
            <h1>Pipeline Execution Report</h1>
            <div>Total Processed: {stats['total_processed']}</div>
            <button id="resetBtn" class="reset-btn">Remove Filters</button>
        </header>
        
        <div class="summary-cards">
            <div class="summary-card"><div class="summary-value">{stats['success_count']}</div><div>Total Success</div></div>
            <div class="summary-card"><div class="summary-value">{stats['fail_count']}</div><div>Total Failure</div></div>
            <div class="summary-card"><div class="summary-value">{stats['try_buckets']['try_1']}</div><div>Success Try 1</div></div>
            <div class="summary-card"><div class="summary-value">{stats['try_buckets']['try_2']}</div><div>Success Try 2</div></div>
            <div class="summary-card"><div class="summary-value">{stats['try_buckets']['try_3']}</div><div>Success Try 3</div></div>
            <div class="summary-card"><div class="summary-value">{stats['try_buckets']['try_4']}</div><div>Success Try 4</div></div>
            <div class="summary-card"><div class="summary-value">{stats['try_buckets']['try_5']}</div><div>Success Try 5</div></div>
        </div>
        
        <div class="summary-cards">
            <div class="summary-card">
                <div class="summary-value">{stats['total_tokens']}</div>
                <div>Tokens Used</div>
                <div style="font-size: 12px; color: var(--text-sub); margin-top: 5px;">
                    In: {stats['total_input_tokens']} | Out: {stats['total_output_tokens']}
                </div>
            </div>
            <div class="summary-card"><div class="summary-value">${stats['total_cost']:.4f}</div><div>Estimated Cost</div></div>
        </div>
        
        <div class="summary-cards">
            <div class="summary-card"><div class="summary-value">{stats['total_retries']}</div><div>Total Retries</div></div>
            <div class="summary-card"><div class="summary-value">{stats['median_retries']:.1f}</div><div>Median Retries to Pass</div></div>
            <div class="summary-card">
                <div class="summary-value">{sum(stats['total_http_errors'].values())}</div>
                <div>Total HTTP Errors</div>
                <div style="font-size: 12px; color: var(--text-sub); margin-top: 5px;">
                    {', '.join([f"Code {k}: {v}" for k, v in stats['total_http_errors'].items()]) or "None"}
                </div>
            </div>
            <div class="summary-card">
                <div class="summary-value">{stats['avg_time']:.1f}s</div>
                <div>Avg Process Time</div>
                <div style="font-size: 12px; color: var(--text-sub); margin-top: 5px;">
                    Min: {stats['min_time']:.1f}s | Max: {stats['max_time']:.1f}s
                </div>
            </div>
        </div>
        
        <div class="charts-container">
            <!-- Score Chart -->
            <div class="chart-card">
                <h2 style="font-size: 18px; color: var(--accent-blue); margin-bottom: 15px;">Score Distribution</h2>
                <canvas id="scoreChart" style="max-height: 250px;"></canvas>
            </div>
            
            <!-- Category Chart -->
            <div class="chart-card">
                <h2 style="font-size: 18px; color: var(--accent-blue); margin-bottom: 15px;">Status by Category</h2>
                <canvas id="categoryChart" style="max-height: 250px;"></canvas>
            </div>
        </div>
        
        <!-- Filter Title -->
        <div id="filterTitle" style="font-size: 16px; font-weight: bold; margin-bottom: 15px; color: var(--accent-blue); display: none;"></div>

        <div class="grid">
            {grid_items_html}
        </div>

        <script>
            let scoreChart, categoryChart;

            // Set default font color for Chart.js
            Chart.defaults.color = '#9ca3af';
            Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';

            // Score Chart
            const ctx = document.getElementById('scoreChart').getContext('2d');
            scoreChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80-89", "90-100"],
                    datasets: [{{
                        label: 'Number of Products',
                        data: {score_buckets},
                        borderColor: '#60a5fa',
                        backgroundColor: 'rgba(96, 165, 250, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#22d3ee',
                        pointBorderColor: '#fff'
                    }}]
                }},
                options: {{
                    onClick: (e) => {{
                        const points = scoreChart.getElementsAtEventForMode(e, 'nearest', {{ intersect: true }}, true);
                        if (points.length) {{
                            const firstPoint = points[0];
                            const label = scoreChart.data.labels[firstPoint.index];
                            const parts = label.split("-");
                            const lower = parseInt(parts[0]);
                            const upper = parseInt(parts[1]);
                            filterByScoreBand(lower, upper);
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{
                                stepSize: 1,
                                color: '#9ca3af'
                            }}
                        }},
                        x: {{
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{ color: '#9ca3af' }}
                        }}
                    }},
                    plugins: {{
                        legend: {{
                            labels: {{ color: '#9ca3af' }}
                        }}
                    }}
                }}
            }});

            // Category Chart
            const catCtx = document.getElementById('categoryChart').getContext('2d');
            categoryChart = new Chart(catCtx, {{
                type: 'bar',
                data: {{
                    labels: {cat_labels},
                    datasets: [
                        {{
                            label: 'Passed',
                            data: {cat_pass_data},
                            backgroundColor: 'rgba(5, 150, 105, 0.8)',
                            borderColor: 'rgba(5, 150, 105, 1)',
                            borderWidth: 1
                        }},
                        {{
                            label: 'Need Review',
                            data: {cat_review_data},
                            backgroundColor: 'rgba(220, 38, 38, 0.8)',
                            borderColor: 'rgba(220, 38, 38, 1)',
                            borderWidth: 1
                        }}
                    ]
                }},
                options: {{
                    onClick: (e) => {{
                        const points = categoryChart.getElementsAtEventForMode(e, 'nearest', {{ intersect: true }}, true);
                        if (points.length) {{
                            const firstPoint = points[0];
                            const label = categoryChart.data.labels[firstPoint.index];
                            filterByCategory(label);
                        }}
                    }},
                    scales: {{
                        x: {{ 
                            stacked: true,
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{ color: '#9ca3af' }}
                        }},
                        y: {{ 
                            stacked: true, 
                            beginAtZero: true,
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{ color: '#9ca3af' }}
                        }}
                    }},
                    plugins: {{
                        legend: {{
                            labels: {{ color: '#9ca3af' }}
                        }}
                    }}
                }}
            }});

            function filterByScoreBand(lower, upper) {{
                const cards = document.querySelectorAll('.product-card');
                cards.forEach(card => {{
                    const score = parseInt(card.getAttribute('data-score'));
                    if (score >= lower && score <= upper) {{
                        card.style.display = 'flex';
                    }} else {{
                        card.style.display = 'none';
                    }}
                }});
                document.getElementById('resetBtn').style.display = 'inline-block';
                const filterTitle = document.getElementById('filterTitle');
                filterTitle.innerText = `Filter: Score between ${{lower}} and ${{upper}}`;
                filterTitle.style.display = 'block';
            }}

            function filterByCategory(category) {{
                const cards = document.querySelectorAll('.product-card');
                cards.forEach(card => {{
                    const cat = card.getAttribute('data-category');
                    if (cat === category) {{
                        card.style.display = 'flex';
                    }} else {{
                        card.style.display = 'none';
                    }}
                }});
                document.getElementById('resetBtn').style.display = 'inline-block';
                const filterTitle = document.getElementById('filterTitle');
                filterTitle.innerText = `Filter: Category is "${{category}}"`;
                filterTitle.style.display = 'block';
            }}

            document.getElementById('resetBtn').onclick = function() {{
                const cards = document.querySelectorAll('.product-card');
                cards.forEach(card => card.style.display = 'flex');
                this.style.display = 'none';
                document.getElementById('filterTitle').style.display = 'none';
            }};
        </script>
    </body>
    </html>
    """
    
    report_path = output_dir / "index.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  -> Generated HTML Report: {report_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate PDF report from output data.")
    parser.add_argument(
        "--dir", "-d",
        type=str,
        default="output",
        help="Directory containing product output folders"
    )
    args = parser.parse_args()
    
    output_dir = Path(args.dir)
    if not output_dir.exists():
        print(f"Output directory {output_dir} does not exist.")
        sys.exit(1)
    run_report(output_dir)
