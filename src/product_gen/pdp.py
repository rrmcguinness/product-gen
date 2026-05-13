import textwrap
from pathlib import Path
import html
from .model import DetailedProduct, ProductLongDescriptionDetail
from dotenv import load_dotenv
import json

load_dotenv()

def generate_pdp_html(product: DetailedProduct, output_dir: Path):
    """
    Generates a comparative report showing before and after with cards and flow.
    """
    import os
    threshold = float(os.environ.get("PASS_THRESHOLD", "0.9"))
    threshold_display = int(threshold * 100)
    
    # Discover images
    ref_images = []
    
    ref_dir = output_dir / "reference_images"
    if ref_dir.exists():
        for ref_img in sorted(ref_dir.glob("ref_*.*")):
            if ref_img.is_file():
                ref_images.append(f"reference_images/{ref_img.name}")
                
    # Fallbacks
    if not ref_images:
        ref_images.append("https://placehold.co/300x300/f3f4f6/a1a1aa?text=No+Reference+Image")
        
    # Build Generated Images HTML
    gen_images_html = ""
    if product.image_reviews:
        for review in product.image_reviews:
            # Use path relative to the current output_dir to handle moved folders
            filename = Path(review.uri).name
            img_src = f"generated/{filename}"
                
            score = review.score
            reasoning = html.escape(review.reasoning)
            prompt_text = html.escape(review.prompt) if hasattr(review, "prompt") and review.prompt else "N/A"
            
            color = "var(--accent-green)" if score >= threshold else "var(--accent-red)"
            
            gen_images_html += f"""
            <div class="image-item" style="display: flex; flex-direction: column; align-items: center; gap: 5px;">
                <img src="{img_src}" alt="Generated" 
                     data-reasoning="{reasoning}" 
                     data-prompt="{prompt_text}" 
                     data-ref-images='{json.dumps(ref_images)}'
                     data-type="generated"
                     onclick="openModal(this)" 
                     style="border: 3px solid {color}; width: 120px; height: 120px; object-fit: cover; border-radius: 6px; cursor: pointer;">
                <span style="color: {color}; font-weight: bold; font-size: 14px;">{int(score * 100)} / {threshold_display}</span>
            </div>
            """
    else:
        gen_images_html = '<img src="https://placehold.co/300x300/f3f4f6/a1a1aa?text=No+Generated+Image" alt="No Generated Image">'
        
    # Extract original details
    orig_name = product.product_name or "Unknown Product"
    orig_short_desc = product.product_short_description or "No short description available."
    orig_long_desc = "No long description available."
    orig_url = product.main_image_url or "#"
    
    if isinstance(product.product_long_description, ProductLongDescriptionDetail):
        orig_long_desc = product.product_long_description.product_long_description or orig_long_desc
        orig_url = product.product_long_description.url or orig_url
    elif isinstance(product.product_long_description, str):
        pld_str = product.product_long_description
        if pld_str.strip().startswith("{"):
            import re
            try:
                pld_dict = json.loads(pld_str)
                orig_long_desc = pld_dict.get("product_long_description") or pld_dict.get("product_short_description") or pld_str
            except json.JSONDecodeError:
                # Fallback to regex extraction if JSON is malformed
                match = re.search(r'"product_long_description"\s*:\s*"(.*?)(?<!\\\\)"', pld_str, re.DOTALL)
                if match:
                    orig_long_desc = match.group(1).replace('\\\\"', '"').replace('\\\\\\\\', '\\\\')
                else:
                    orig_long_desc = pld_str
        else:
            orig_long_desc = pld_str
        
    # Extract generated details
    gen_name = product.product_name
    
    # Extract reviews
    score_html = "N/A"
    reasoning_html = "No review available."
    score_color = "var(--success-green)"
    status_text = "Review"
    status_class = "status-review"
    if product.image_reviews:
        # Check if ANY review passed
        if any(r.score >= threshold for r in product.image_reviews):
            status_text = "Pass"
            status_class = "status-pass"
            
        # Use the best review for the main badge
        best_review = max(product.image_reviews, key=lambda r: r.score)
        score_html = f"{int(best_review.score * 100)} / {threshold_display}"
        reasoning_html = best_review.reasoning
        if best_review.score < threshold:
            score_color = "red"
        
    # Build Process Flow HTML
    flow_html = ""
    if product.metrics and product.metrics.steps:
        flow_html = '<div class="flow-container">'
        for idx, step in enumerate(product.metrics.steps):
            badge_html = ""
            if getattr(step, "images_passed", None) is not None:
                if step.images_passed:
                    badge_html = '<div class="badge badge-image">Image + Prompt</div>'
                else:
                    badge_html = '<div class="badge badge-prompt">Prompt Only</div>'
            
            flow_html += f"""
            <div class="flow-node">
                <div class="node-name">{step.step_name}</div>
                <div class="node-model">{step.model_used or "N/A"}</div>
                <div class="node-time">{step.time_taken:.2f}s</div>
                <div class="node-tokens">In: {step.input_tokens or 0} | Out: {step.output_tokens or 0}</div>
                {badge_html}
            </div>
            """
            if idx < len(product.metrics.steps) - 1:
                flow_html += '<div class="flow-arrow">→</div>'
        flow_html += '</div>'
    else:
        flow_html = "<div>No metrics available.</div>"
        
    total_seconds = product.metrics.total_time if product.metrics else 0.0
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    time_str = f"{minutes:02d}:{seconds:02d}"
        
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
            .status-tab {{
                position: absolute;
                top: 20px;
                right: 20px;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                color: white;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            .status-pass {{ background-color: var(--accent-green); box-shadow: 0 0 10px rgba(52, 211, 153, 0.3); }}
            .status-review {{ background-color: var(--accent-red); box-shadow: 0 0 10px rgba(248, 113, 113, 0.3); }}
            .badge {{
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                text-transform: uppercase;
                color: white;
                margin-top: 4px;
            }}
            .badge-image {{ background-color: var(--accent-green); }}
            .badge-prompt {{ background-color: var(--accent-blue); }}
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Inter', sans-serif;
            }}
            body {{
                background-color: var(--bg-dark);
                color: var(--text-main);
                line-height: 1.5;
                padding: 20px;
            }}
            header {{
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                color: white;
                padding: 30px;
                margin-bottom: 30px;
                border-radius: 12px;
                box-shadow: var(--card-shadow);
                position: relative;
                border: 1px solid var(--border-color);
            }}
            h1 {{
                font-size: 24px;
                margin-bottom: 5px;
                background: linear-gradient(to right, #60a5fa, #22d3ee);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .container {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
            }}
            .card {{
                background-color: var(--bg-card);
                border-radius: 12px;
                padding: 25px;
                box-shadow: var(--card-shadow);
                border: 1px solid var(--border-color);
                margin-bottom: 30px;
            }}
            .section-title {{
                font-size: 20px;
                font-weight: 700;
                color: var(--accent-blue);
                margin-bottom: 20px;
                border-bottom: 1px solid var(--border-color);
                padding-bottom: 10px;
            }}
            .image-gallery {{
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
                margin-bottom: 20px;
            }}
            .image-gallery img {{
                width: 120px;
                height: 120px;
                object-fit: cover;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
            }}
            .image-gallery img:hover {{
                transform: scale(1.05);
                box-shadow: 0 8px 16px rgba(0,0,0,0.3);
                border-color: var(--accent-blue);
            }}
            .details-block {{
                margin-bottom: 20px;
            }}
            .details-label {{
                font-weight: 600;
                color: var(--accent-cyan);
                font-size: 14px;
                margin-bottom: 6px;
            }}
            .details-value {{
                font-size: 15px;
                color: var(--text-main);
            }}
            .attributes-list {{
                list-style: none;
            }}
            .attributes-list li {{
                margin-bottom: 8px;
                font-size: 14px;
                display: flex;
                gap: 5px;
            }}
            .attributes-list strong {{
                color: var(--text-sub);
                min-width: 120px;
                display: inline-block;
            }}
            
            /* Expandable Section */
            details {{
                background-color: var(--bg-card-hover);
                padding: 15px;
                border-radius: 8px;
                border: 1px solid var(--border-color);
                margin-top: 15px;
            }}
            summary {{
                font-weight: 600;
                cursor: pointer;
                color: var(--accent-blue);
                outline: none;
            }}
            details[open] summary {{
                margin-bottom: 15px;
                border-bottom: 1px solid var(--border-color);
                padding-bottom: 5px;
            }}
            
            /* Score Badge */
            .score-badge {{
                display: inline-block;
                background-color: var(--accent-green);
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 700;
                font-size: 14px;
                margin-left: 10px;
                box-shadow: 0 0 10px rgba(52, 211, 153, 0.3);
            }}
            
            /* Flow Visualization */
            .flow-container {{
                display: flex;
                align-items: center;
                gap: 15px;
                overflow-x: auto;
                padding: 15px 0;
            }}
            .flow-node {{
                background-color: var(--bg-card-hover);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 15px;
                min-width: 160px;
                box-shadow: var(--card-shadow);
                font-size: 12px;
                text-align: center;
                transition: border-color 0.2s;
            }}
            .flow-node:hover {{
                border-color: var(--accent-blue);
            }}
            .node-name {{
                font-weight: 700;
                color: var(--accent-blue);
                margin-bottom: 6px;
            }}
            .node-model {{
                color: var(--text-sub);
                font-size: 11px;
                margin-bottom: 6px;
            }}
            .node-time {{
                color: var(--text-main);
                font-weight: 500;
                margin-bottom: 4px;
            }}
            .node-tokens {{
                color: var(--text-sub);
                font-size: 10px;
            }}
            .flow-arrow {{
                font-size: 24px;
                color: var(--accent-cyan);
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
                background-color: rgba(11, 15, 25, 0.9);
            }}
            .modal-content {{
                margin: auto;
                display: block;
                max-width: 90%;
                max-height: 80%;
                border-radius: 12px;
                border: 1px solid var(--border-color);
            }}
            .close {{
                position: absolute;
                top: 20px;
                right: 35px;
                color: var(--text-sub);
                font-size: 40px;
                font-weight: bold;
                transition: 0.3s;
                cursor: pointer;
            }}
            .close:hover,
            .close:focus {{
                color: var(--text-main);
                text-decoration: none;
                cursor: pointer;
            }}
            
            /* Origin Link */
            .origin-link {{
                display: inline-block;
                margin-top: 10px;
                color: var(--accent-blue);
                text-decoration: none;
                font-size: 14px;
                border-bottom: 1px solid transparent;
                transition: border-color 0.2s;
            }}
            .origin-link:hover {{
                border-color: var(--accent-blue);
            }}
        </style>
    </head>
    <body>
        <header>
            <h1>Product Generation Pipeline: Before & After Report</h1>
            <div>Product ID: {product.wpid or "N/A"}</div>
            <div class="status-tab {status_class}">{status_text}</div>
        </header>
        
        <!-- Metrics Flow Section -->
        <div class="card">
            <div class="section-title">Generation Process Flow [ {time_str} ]</div>
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
                            {"".join([f'<img src="{img}" alt="Reference" data-type="reference" onclick="openModal(this)">' for img in ref_images])}
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
                            {gen_images_html}
                        </div>
                    </div>
                    
                    <div class="details-block">
                        <div class="details-label">
                            Quality Score
                            <span class="score-badge" style="background-color: {score_color};">{score_html}</span>
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
            
            <!-- Images Container -->
            <div style="display: flex; justify-content: center; gap: 30px; max-width: 90%; margin: auto; align-items: center;">
                <!-- Reference Images (Gallery) -->
                <div id="ref-container" style="text-align: center; flex: 1; max-width: 600px;">
                    <div id="ref-title" style="color: white; margin-bottom: 10px; font-weight: bold; font-size: 16px;">Reference Images</div>
                    <div style="height: 60vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden;">
                        <img id="img_ref" style="max-width: 100%; max-height: 80%; object-fit: contain;">
                        <div id="ref-gallery" class="image-gallery" style="margin-top: 10px; justify-content: center; display: flex; gap: 5px; overflow-x: auto; width: 100%; padding: 5px;"></div>
                    </div>
                </div>
                
                <!-- Generated Image -->
                <div id="gen-container" style="text-align: center; flex: 1; max-width: 600px;">
                    <div style="color: white; margin-bottom: 10px; font-weight: bold; font-size: 16px;">Generated Image</div>
                    <div style="height: 60vh; display: flex; justify-content: center; align-items: center; background: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden;">
                        <img id="img01" style="max-width: 100%; max-height: 100%; object-fit: contain;">
                    </div>
                </div>
            </div>
            
            <!-- Reasoning Card -->
            <div id="cards-container" style="max-width: 90%; margin: 20px auto; background: var(--bg-card); border-radius: 12px; padding: 25px; box-shadow: var(--card-shadow); border: 1px solid var(--border-color);">
                <h3 style="color: var(--accent-blue); margin-bottom: 15px; font-size: 18px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">Judge's Reasoning</h3>
                <div id="modal-reasoning" style="color: var(--text-main); text-align: left; font-size: 14px; white-space: pre-wrap; margin-bottom: 20px;"></div>
                
                <h3 style="color: var(--accent-blue); margin-bottom: 15px; font-size: 18px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px;">Prompt Used</h3>
                <div id="modal-prompt" style="color: var(--text-sub); text-align: left; font-size: 12px; white-space: pre-wrap; font-family: monospace; background: var(--bg-card-hover); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color);"></div>
            </div>
        </div>

        <script>
            function openModal(img) {{
                document.getElementById('myModal').style.display = "block";
                
                let type = img.getAttribute('data-type');
                
                if (type === 'reference') {{
                    // Isolation view for reference image
                    document.getElementById('img_ref').src = img.src;
                    document.getElementById('ref-gallery').style.display = "none";
                    document.getElementById('gen-container').style.display = "none";
                    document.getElementById('cards-container').style.display = "none";
                    document.getElementById('ref-title').innerText = "Reference Image";
                }} else {{
                    // Comparison view for generated image
                    document.getElementById('gen-container').style.display = "block";
                    document.getElementById('cards-container').style.display = "block";
                    document.getElementById('ref-gallery').style.display = "flex";
                    document.getElementById('ref-title').innerText = "Reference Images";
                    
                    document.getElementById('img01').src = img.src;
                    
                    let refImagesStr = img.getAttribute('data-ref-images');
                    let refImages = [];
                    try {{
                        refImages = JSON.parse(refImagesStr) || [];
                    }} catch(e) {{
                        console.error("Failed to parse ref images", e);
                    }}
                    
                    let galleryDiv = document.getElementById('ref-gallery');
                    galleryDiv.innerHTML = '';
                    
                    if (refImages.length > 0) {{
                        document.getElementById('img_ref').src = refImages[0];
                        refImages.forEach(src => {{
                            let thumb = document.createElement('img');
                            thumb.src = src;
                            thumb.style.width = '40px';
                            thumb.style.height = '40px';
                            thumb.style.objectFit = 'cover';
                            thumb.style.cursor = 'pointer';
                            thumb.style.border = '1px solid var(--border-color)';
                            thumb.style.borderRadius = '4px';
                            thumb.onclick = function() {{
                                document.getElementById('img_ref').src = src;
                            }};
                            galleryDiv.appendChild(thumb);
                        }});
                    }} else {{
                        document.getElementById('img_ref').src = 'https://placehold.co/300x300/f3f4f6/a1a1aa?text=No+Reference+Image';
                    }}
                    
                    document.getElementById('modal-reasoning').innerText = img.getAttribute('data-reasoning');
                    document.getElementById('modal-prompt').innerText = img.getAttribute('data-prompt') || 'No prompt recorded.';
                }}
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
