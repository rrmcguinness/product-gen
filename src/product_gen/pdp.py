import textwrap
from pathlib import Path
from .model import DetailedProduct, ProductLongDescriptionDetail

def generate_pdp_html(product: DetailedProduct, output_dir: Path):
    """
    Generates a comparative report showing before and after with cards and flow.
    """
    # Discover images
    ref_images = []
    gen_images = []
    
    ref_dir = output_dir / "reference_images"
    if ref_dir.exists():
        for ref_img in sorted(ref_dir.glob("ref_*.*")):
            if ref_img.is_file():
                ref_images.append(f"reference_images/{ref_img.name}")
                
    for i in range(1, 5):
        gen_img = output_dir / f"image_{i}.jpeg"
        if gen_img.exists():
            gen_images.append(gen_img.name)
            
    # Fallbacks
    if not ref_images:
        ref_images.append("https://placehold.co/300x300/f3f4f6/a1a1aa?text=No+Reference+Image")
    if not gen_images:
        gen_images.append("https://placehold.co/300x300/f3f4f6/a1a1aa?text=No+Generated+Image")
        
    # Extract original details
    orig_name = product.product_name or "Unknown Product"
    orig_short_desc = product.product_short_description or "No short description available."
    orig_long_desc = "No long description available."
    orig_url = product.main_image_url or "#"
    
    if isinstance(product.product_long_description, ProductLongDescriptionDetail):
        orig_long_desc = product.product_long_description.product_long_description or orig_long_desc
        orig_url = product.product_long_description.url or orig_url
    elif isinstance(product.product_long_description, str):
        orig_long_desc = product.product_long_description
        
    # Extract generated details
    gen_name = product.product_name
    
    # Extract reviews
    score_html = "N/A"
    reasoning_html = "No review available."
    if product.image_reviews:
        # Use the first review
        review = product.image_reviews[0]
        score_html = f"{review.score:.2f}"
        reasoning_html = review.reasoning
        
    # Build Process Flow HTML
    flow_html = ""
    if product.metrics and product.metrics.steps:
        flow_html = '<div class="flow-container">'
        for idx, step in enumerate(product.metrics.steps):
            flow_html += f"""
            <div class="flow-node">
                <div class="node-name">{step.step_name}</div>
                <div class="node-model">{step.model_used or "N/A"}</div>
                <div class="node-time">{step.time_taken:.2f}s</div>
                <div class="node-tokens">In: {step.input_tokens or 0} | Out: {step.output_tokens or 0}</div>
            </div>
            """
            if idx < len(product.metrics.steps) - 1:
                flow_html += '<div class="flow-arrow">→</div>'
        flow_html += '</div>'
    else:
        flow_html = "<div>No metrics available.</div>"
        
    html_content = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Product Generation Report - {product.product_name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --wm-blue: #0071dc;
                --wm-dark-blue: #004f9a;
                --text-main: #2e2f32;
                --text-sub: #5f6368;
                --bg-light: #f2f8fd;
                --border-color: #e3e4e5;
                --hover-bg: #e1e7ec;
                --success-green: #2a8703;
                --card-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }}
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Inter', sans-serif;
            }}
            body {{
                background-color: #f9f9f9;
                color: var(--text-main);
                line-height: 1.5;
                padding: 20px;
            }}
            header {{
                background-color: var(--wm-blue);
                color: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 8px;
                box-shadow: var(--card-shadow);
            }}
            h1 {{
                font-size: 24px;
                margin-bottom: 5px;
            }}
            .container {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
            }}
            .card {{
                background-color: #ffffff;
                border-radius: 8px;
                padding: 20px;
                box-shadow: var(--card-shadow);
                border: 1px solid var(--border-color);
                margin-bottom: 20px;
            }}
            .section-title {{
                font-size: 20px;
                font-weight: 700;
                color: var(--wm-blue);
                margin-bottom: 15px;
                border-bottom: 2px solid var(--wm-blue);
                padding-bottom: 5px;
            }}
            .image-gallery {{
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-bottom: 15px;
            }}
            .image-gallery img {{
                width: 120px;
                height: 120px;
                object-fit: cover;
                border: 1px solid var(--border-color);
                border-radius: 6px;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .image-gallery img:hover {{
                transform: scale(1.05);
                box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            }}
            .details-block {{
                margin-bottom: 15px;
            }}
            .details-label {{
                font-weight: 600;
                color: var(--text-sub);
                font-size: 14px;
                margin-bottom: 4px;
            }}
            .details-value {{
                font-size: 15px;
                color: var(--text-main);
            }}
            .attributes-list {{
                list-style: none;
            }}
            .attributes-list li {{
                margin-bottom: 5px;
                font-size: 14px;
            }}
            .attributes-list strong {{
                color: var(--text-sub);
            }}
            
            /* Expandable Section */
            details {{
                background-color: var(--bg-light);
                padding: 10px;
                border-radius: 6px;
                border: 1px solid var(--border-color);
                margin-top: 10px;
            }}
            summary {{
                font-weight: 600;
                cursor: pointer;
                color: var(--wm-blue);
                outline: none;
            }}
            details[open] summary {{
                margin-bottom: 10px;
            }}
            
            /* Score Badge */
            .score-badge {{
                display: inline-block;
                background-color: var(--success-green);
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 700;
                font-size: 14px;
                margin-left: 10px;
            }}
            
            /* Flow Visualization */
            .flow-container {{
                display: flex;
                align-items: center;
                gap: 15px;
                overflow-x: auto;
                padding: 10px 0;
            }}
            .flow-node {{
                background-color: #ffffff;
                border: 2px solid var(--wm-blue);
                border-radius: 6px;
                padding: 10px;
                min-width: 150px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.05);
                font-size: 12px;
                text-align: center;
            }}
            .node-name {{
                font-weight: 700;
                color: var(--wm-blue);
                margin-bottom: 4px;
            }}
            .node-model {{
                color: var(--text-sub);
                font-size: 11px;
                margin-bottom: 4px;
            }}
            .node-time {{
                color: var(--text-main);
                font-weight: 500;
            }}
            .node-tokens {{
                color: var(--text-sub);
                font-size: 10px;
            }}
            .flow-arrow {{
                font-size: 24px;
                color: var(--wm-blue);
                font-weight: 700;
            }}
            
            /* Modal for full res view */
            .modal {{
                display: none;
                position: fixed;
                z-index: 1000;
                padding-top: 50px;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                overflow: auto;
                background-color: rgba(0,0,0,0.9);
            }}
            .modal-content {{
                margin: auto;
                display: block;
                max-width: 90%;
                max-height: 80%;
                border-radius: 8px;
            }}
            .close {{
                position: absolute;
                top: 15px;
                right: 35px;
                color: #f1f1f1;
                font-size: 40px;
                font-weight: bold;
                transition: 0.3s;
                cursor: pointer;
            }}
            .close:hover,
            .close:focus {{
                color: #bbb;
                text-decoration: none;
                cursor: pointer;
            }}
            
            /* Origin Link */
            .origin-link {{
                display: inline-block;
                margin-top: 10px;
                color: var(--wm-blue);
                text-decoration: underline;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <header>
            <h1>Product Generation Pipeline: Before & After Report</h1>
            <div>Product ID: {product.wpid or "N/A"}</div>
        </header>
        
        <!-- Metrics Flow Section -->
        <div class="card">
            <div class="section-title">Generation Process Flow</div>
            {flow_html}
        </div>
        
        <div class="container">
            <!-- Left Side: Before -->
            <div>
                <div class="card">
                    <div class="section-title">Before: Original Product</div>
                    
                    <div class="details-block">
                        <div class="details-label">Reference Images</div>
                        <div class="image-gallery">
                            {"".join([f'<img src="{img}" alt="Reference" onclick="openModal(this.src)">' for img in ref_images])}
                        </div>
                        <a href="{orig_url}" class="origin-link" target="_blank">View Origin Product</a>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">Original Product Name</div>
                        <div class="details-value">{orig_name}</div>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">Original Short Description</div>
                        <div class="details-value">{orig_short_desc}</div>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">Original Long Description</div>
                        <div class="details-value">{orig_long_desc}</div>
                    </div>
                </div>
            </div>
            
            <!-- Right Side: After -->
            <div>
                <div class="card">
                    <div class="section-title">After: Generated Product</div>
                    
                    <div class="details-block">
                        <div class="details-label">Generated Images (Click to view full resolution)</div>
                        <div class="image-gallery">
                            {"".join([f'<img src="{img}" alt="Generated" onclick="openModal(this.src)">' for img in gen_images])}
                        </div>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">
                            Quality Score
                            <span class="score-badge">{score_html}</span>
                        </div>
                        <div class="details-value" style="margin-top: 5px;">
                            <strong>Reasoning:</strong> {reasoning_html}
                        </div>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">Generated Product Name</div>
                        <div class="details-value">{gen_name}</div>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">Enriched Detailed Description</div>
                        <div class="details-value">{product.detailed_description or "N/A"}</div>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">Attributes</div>
                        <ul class="attributes-list">
                            <li><strong>Brand:</strong> {product.attributes.brand if product.attributes else "N/A"}</li>
                            <li><strong>Color:</strong> {product.attributes.color if product.attributes else "N/A"}</li>
                            <li><strong>Material:</strong> {product.attributes.material if product.attributes else "N/A"}</li>
                            <li><strong>Target Audience:</strong> {product.attributes.target_audience if product.attributes else "N/A"}</li>
                        </ul>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">Key Features</div>
                        <ul class="attributes-list">
                            {"".join([f"<li>• {feat}</li>" for feat in (product.attributes.key_features if product.attributes else [])])}
                        </ul>
                    </div>
                    
                    {f'''
                    <details>
                        <summary>How Gemini Described the Image</summary>
                        <div style="padding-top: 10px;">
                            {product.image_based_description}
                        </div>
                    </details>
                    ''' if product.image_based_description else ""}
                </div>
            </div>
        </div>
        
        <!-- The Modal -->
        <div id="myModal" class="modal">
            <span class="close" onclick="closeModal()">&times;</span>
            <img class="modal-content" id="img01">
        </div>

        <script>
            function openModal(src) {{
                document.getElementById('myModal').style.display = "block";
                document.getElementById('img01').src = src;
            }}

            function closeModal() {{
                document.getElementById('myModal').style.display = "none";
            }}
            
            window.onclick = function(event) {{
                let modal = document.getElementById('myModal');
                if (event.target == modal) {{
                    modal.style.display = "none";
                }}
            }}
        </script>
    </body>
    </html>
    """)

    html_path = output_dir / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"  -> Generated Report HTML: {html_path}")
    return html_path
