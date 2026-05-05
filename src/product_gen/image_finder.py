import json
import urllib.request
from pathlib import Path
from typing import List

from .model import ProductImageGenerationData


class ImageFinder:
    """
    Enterprise-grade utility to locate, extract, and download reference images 
    from raw product payloads to be used in image generation conditioning.
    """
    
    def __init__(self, output_base_dir: Path | str = "output"):
        self.output_base_dir = Path(output_base_dir)

    def extract_image_urls(self, product: ProductImageGenerationData) -> List[str]:
        """
        Parses the product payload to discover reference image URLs.
        First checks 'main_image_url', then drills into 'product_long_description'.
        """
        urls = []
        
        if product.main_image_url and isinstance(product.main_image_url, str):
            urls.append(product.main_image_url)
            
        if product.product_long_description:
            try:
                if isinstance(product.product_long_description, str):
                    desc_obj = json.loads(product.product_long_description)
                elif isinstance(product.product_long_description, dict):
                    desc_obj = product.product_long_description
                elif hasattr(product.product_long_description, "model_dump"):
                    desc_obj = product.product_long_description.model_dump()
                else:
                    desc_obj = {}
                    
                additional_urls = desc_obj.get("product_additional_urls", {})
                
                if "image_url" in additional_urls:
                    image_url_data = json.loads(additional_urls["image_url"])
                    
                    if isinstance(image_url_data, list):
                        for item in image_url_data:
                            # It can be a direct url string or an embedded json structure
                            if isinstance(item, str) and item.startswith("http") and "{" not in item:
                                urls.append(item)
            except (json.JSONDecodeError, TypeError):
                pass
                
        # Deduplicate while preserving order
        return list(dict.fromkeys(urls))

    def download_reference_images(self, product: ProductImageGenerationData) -> List[Path]:
        """
        Finds and downloads all available reference images for the product.
        Returns a list of local file paths indicating where they were saved.
        """
        urls = self.extract_image_urls(product)
        if not urls:
            return []
            
        wpid = product.wpid or "unknown"
        target_dir = self.output_base_dir / wpid / "reference_images"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        saved_paths = []
        for i, url in enumerate(urls, 1):
            try:
                # Basic extension extraction (defaulting to .jpg)
                ext = ".jpg"
                if ".png" in url.lower(): ext = ".png"
                elif ".jpeg" in url.lower(): ext = ".jpeg"
                elif ".webp" in url.lower(): ext = ".webp"
                    
                dest_path = target_dir / f"ref_{i}{ext}"
                
                # Fetch image if it doesn't already exist
                if not dest_path.exists():
                    req = urllib.request.Request(
                        url,
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'} # Spoofing to avoid 403s
                    )
                    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
                        out_file.write(response.read())
                        
                saved_paths.append(dest_path)
            except Exception as e:
                print(f"    [Warning] Failed to download reference image {url}: {e}")
                
        return saved_paths

