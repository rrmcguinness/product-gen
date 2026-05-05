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
        "total_cost": 0.0
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
                    if reviews:
                        for review in reviews:
                            score = review.get("score", 0.0)
                            retries = review.get("retry_count", 0)
                            
                            if score >= 0.9:
                                stats["success_count"] += 1
                                prod_success += 1
                            else:
                                stats["fail_count"] += 1
                                prod_fail += 1
                                
                            stats["total_retries"] += retries
                            prod_retries += retries
                    else:
                        # No reviews (likely no reference images to judge against).
                        # Fallback to checking if images were generated and saved.
                        images = list(item.glob("image_*.jpeg"))
                        if images:
                            stats["success_count"] += 1
                            prod_success = len(images)
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
                        "judge_tokens": judge_tokens
                    })
                    
                except Exception as e:
                    stats["errors"].append(f"Error reading {detail_path}: {e}")
                    
    # Generate PDF
    report_path = output_dir / "pipeline_report.pdf"
    generate_pdf_report(report_path, stats)

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
