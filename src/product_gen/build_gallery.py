import json
import textwrap
from pathlib import Path

def build_gallery(output_dir: Path | str = "output"):
    output_path = Path(output_dir)
    
    products = []
    
    # Scan through output directory
    for item in output_path.iterdir():
        if item.is_dir() and (item / "product_detail.json").exists():
            wpid = item.name
            json_path = item / "product_detail.json"
            
            with open(json_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    continue
                    
            # Find a generated image (not a reference image)
            img_src = None
            for p in ["image_1.jpeg", "image_2.jpeg", "image_1.jpg", "image_2.jpg", "image_1.png"]:
                if (item / p).exists():
                    img_src = f"{wpid}/{p}"
                    break
                    
            if not img_src:
                img_src = "https://placehold.co/400x400/f3f4f6/a1a1aa?text=No+Generated+Image"
                
            title = data.get("product_name") or wpid
            desc = data.get("detailed_description") or ""
            
            # If no detailed_description exists directly, try parsing from sales_attributes or key_features
            if not desc and "sales_attributes" in data:
                features = data["sales_attributes"].get("key_features", [])
                if features:
                    desc = " ".join(features)
                    
            products.append({
                "wpid": wpid,
                "title": title,
                "desc": desc,
                "img": img_src,
                "link": f"{wpid}/index.html"
            })
            
    # Sort for consistent rendering
    products.sort(key=lambda x: x["title"])
    
    cards_html = ""
    for p in products:
        cards_html += f"""
        <div class="card">
            <a href="{p['link']}" class="img-link">
                <img src="{p['img']}" alt="{p['title']}" loading="lazy">
            </a>
            <div class="card-content">
                <h3 class="title" title="{p['title']}">{p['title']}</h3>
                <p class="desc">{p['desc']}</p>
            </div>
        </div>
        """
        
    html_content = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Walmart Generated Product Gallery</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-main: #f4f6f8;
                --text-main: #2e2f32;
                --text-sub: #5f6368;
                --wm-blue: #0071dc;
                --card-bg: rgba(255, 255, 255, 0.95);
            }}
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Inter', sans-serif;
            }}
            body {{
                background-color: var(--bg-main);
                color: var(--text-main);
                padding: 40px 20px;
                background-image: radial-gradient(#e5e7eb 1px, transparent 1px);
                background-size: 24px 24px;
            }}
            .header-container {{
                text-align: center;
                margin-bottom: 50px;
            }}
            .header-container h1 {{
                font-size: 36px;
                font-weight: 700;
                color: var(--text-main);
                letter-spacing: -1px;
                margin-bottom: 8px;
            }}
            .header-container p {{
                font-size: 16px;
                color: var(--text-sub);
            }}
            .gallery-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 28px;
                max-width: 1400px;
                margin: 0 auto;
            }}
            .card {{
                background-color: var(--card-bg);
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 4px 16px rgba(0,0,0,0.04);
                transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
                backdrop-filter: blur(10px);
                display: flex;
                flex-direction: column;
                border: 1px solid rgba(255, 255, 255, 0.5);
            }}
            .card:hover {{
                transform: translateY(-8px);
                box-shadow: 0 12px 24px rgba(0, 113, 220, 0.15);
            }}
            .img-link {{
                display: block;
                aspect-ratio: 1;
                overflow: hidden;
                position: relative;
            }}
            .img-link::after {{
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(180deg, rgba(0,0,0,0) 70%, rgba(0,0,0,0.05) 100%);
                pointer-events: none;
            }}
            .img-link img {{
                width: 100%;
                height: 100%;
                object-fit: cover;
                transition: transform 0.5s ease;
            }}
            .img-link:hover img {{
                transform: scale(1.08);
            }}
            .card-content {{
                padding: 20px;
                flex-grow: 1;
                display: flex;
                flex-direction: column;
            }}
            .title {{
                font-size: 16px;
                font-weight: 600;
                line-height: 1.3;
                margin-bottom: 12px;
                color: var(--text-main);
                
                /* Truncate to 2 lines */
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}
            .desc {{
                font-size: 13px;
                color: var(--text-sub);
                line-height: 1.5;
                
                /* Truncate to 3 lines */
                display: -webkit-box;
                -webkit-line-clamp: 3;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }}
        </style>
    </head>
    <body>
        <div class="header-container">
            <h1>Enterprise GenAI Gallery</h1>
            <p>Showcasing {len(products)} enriched SKUs with synthetically generated lifestyle imaging.</p>
        </div>
        
        <div class="gallery-grid">
            {cards_html}
        </div>
    </body>
    </html>
    """)
    
    out_file = output_path / "index.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Gallery successfully written to {out_file} featuring {len(products)} items.")

if __name__ == "__main__":
    build_gallery()
