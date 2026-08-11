import json
import urllib.request
from pathlib import Path
from typing import List

from google import genai
from google.genai import types

from .model import ProductImageGenerationData, StepMetrics
from .utils import call_gemini, LLMError


class ImageFinder:
    """
    Enterprise-grade utility to locate, extract, and download reference images 
    from raw product payloads to be used in image generation conditioning.
    Focus on manufacturer provided images and royalty free images.
    """
    
    def __init__(self, client: genai.Client, output_base_dir: Path | str = "output"):
        self.client = client
        self.output_base_dir = Path(output_base_dir)

    def extract_image_urls(self, product: ProductImageGenerationData) -> List[str]:
        """
        Parses the product payload to discover reference image URLs.
        First checks 'main_image_url', then drills into 'product_long_description'.
        Focus on manufacturer provided images and royalty free images.
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
                
        # Fallback to regex if no URLs found and pld is a string
        if not urls and isinstance(product.product_long_description, str):
            import re
            found_urls = re.findall(r'https?://[^\s"]+\.(?:jpg|jpeg|png|webp)', product.product_long_description)
            urls.extend(found_urls)
            
        # Deduplicate while preserving order
        return list(dict.fromkeys(urls))

    def search_image_urls(self, product: ProductImageGenerationData) -> tuple[List[str], StepMetrics]:
        """
        Searches for image URLs for the product using Gemini with Google Search.
        Focuses on manufacturer provided images and royalty free images.
        """
        search_term = product.product_name or f"product {product.wpid}" if product.wpid else "product"
        import os
        prompt_template = os.environ.get(
            "SEARCH_PROMPT",
            "Find official high-quality product image URLs for the product: '{search_term}'. Focus on images provided by the manufacturer or official sources. Prioritize royalty-free images. The images MUST contain the actual physical product, not just a brand logo or text. If manufacturer images are not found, images from walmart.com are acceptable. Do NOT return URLs from other e-commerce platforms such as amazon.com, ebay.com, target.com, or shopify.com. Only return URLs from the brand's official domain, official media hosting services, or walmart.com. Return ONLY a JSON list of valid image URLs (strings starting with http or https). Do not include any other text or markdown formatting."
        )
        prompt = prompt_template.format(search_term=search_term)
        
        search_model = os.environ.get("SEARCH_MODEL", "gemini-3.1-flash-lite")
        temp = float(os.environ.get("SEARCH_TEMP", "0.2"))
        top_p = os.environ.get("SEARCH_TOP_P")
        top_k = os.environ.get("SEARCH_TOP_K")
        top_p = float(top_p) if top_p else None
        top_k = int(top_k) if top_k else None
        
        try:
            response, metrics = call_gemini(
                client=self.client,
                model=search_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=temp,
                    top_p=top_p,
                    top_k=top_k,
                    response_mime_type="application/json",
                    system_instruction=os.environ.get("SEARCH_INSTRUCTIONS", "")
                ),
                step_name="Search Image URLs",
                max_retries=3
            )
            
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
                
            import json
            urls = json.loads(text.strip())
            if isinstance(urls, list):
                return [u for u in urls if isinstance(u, str) and u.startswith("http")], metrics
        except LLMError as e:
            print(f"    [Warning] Failed to search for image URLs: {e.original_error}")
            return [], e.metrics
        except Exception as e:
            print(f"    [Warning] Failed to parse image URLs: {e}")
            return [], metrics
            
        return [], metrics

    def verify_reference_image(self, image_path: Path, product_name: str) -> bool:
        """
        Verifies if the downloaded image actually contains the product.
        Returns True if it does, False otherwise.
        """
        import os
        instructions = os.environ.get(
            "VERIFY_INSTRUCTIONS",
            "You are an expert product catalog auditor. Your task is to determine if an image contains the actual physical product or if it is just a logo, text label, or unrelated content."
        )
        prompt = os.environ.get(
            "VERIFY_PROMPT",
            "Analyze this image. Does it contain the actual physical product described as '{product_name}'? Or is it just a logo, text label, or unrelated content? Return JSON with 'contains_product' (boolean) and 'reasoning' (string)."
        )
        prompt = prompt.format(product_name=product_name)
        
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        
        mime = "image/jpeg"
        if image_path.suffix.lower() == ".png": mime = "image/png"
        elif image_path.suffix.lower() == ".webp": mime = "image/webp"
        
        contents = [
            types.Part.from_bytes(data=img_bytes, mime_type=mime),
            prompt
        ]
        
        verify_model = os.environ.get("VERIFY_MODEL", "gemini-3.1-flash-lite")
        temp = float(os.environ.get("VERIFY_TEMP", "0.0"))
        top_p = os.environ.get("VERIFY_TOP_P")
        top_k = os.environ.get("VERIFY_TOP_K")
        top_p = float(top_p) if top_p else None
        top_k = int(top_k) if top_k else None
        
        try:
            response, metrics = call_gemini(
                client=self.client,
                model=verify_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temp,
                    top_p=top_p,
                    top_k=top_k,
                    response_mime_type="application/json",
                    system_instruction=instructions
                ),
                step_name="Verify Reference Image",
                max_retries=3
            )
            
            text = response.text.strip()
            import json
            result = json.loads(text)
            print(f"    Verification result: {result.get('contains_product')}")
            print(f"    Verification reasoning: {result.get('reasoning')}")
            return result.get("contains_product", False)
        except Exception as e:
            print(f"    [Warning] Failed to verify image {image_path}: {e}")
            return False

    def download_reference_images(self, product: ProductImageGenerationData) -> tuple[List[Path], StepMetrics]:
        """
        Finds and downloads all available reference images for the product.
        Returns a list of local file paths indicating where they were saved.
        """
        print(f"  -> Attempting to search for manufacturer images...")
        urls, metrics = self.search_image_urls(product)
        
        if not urls:
            print(f"  -> No manufacturer images found via search. Falling back to payload URLs...")
            urls = self.extract_image_urls(product)
            
        if not urls:
            print(f"  -> No images found in payload. Attempting fallback broad search...")
            import os
            search_term = product.product_name or f"product {product.wpid}" if product.wpid else "product"
            prompt = f"Find any high-quality product image URLs for the product: '{search_term}'. Return ONLY a JSON list of valid image URLs (strings starting with http or https). Do not include any other text or markdown formatting."
            
            search_model = os.environ.get("SEARCH_MODEL", "gemini-3.1-flash-lite")
            try:
                response, fallback_metrics = call_gemini(
                    client=self.client,
                    model=search_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}],
                        temperature=0.2,
                        response_mime_type="application/json"
                    ),
                    step_name="Search Image URLs (Fallback)",
                    max_retries=3
                )
                metrics = fallback_metrics
                
                text = response.text.strip()
                if text.startswith("```json"): text = text[7:]
                elif text.startswith("```"): text = text[3:]
                if text.endswith("```"): text = text[:-3]
                
                import json
                fallback_urls = json.loads(text.strip())
                if isinstance(fallback_urls, list):
                    urls = [u for u in fallback_urls if isinstance(u, str) and u.startswith("http")]
            except Exception as e:
                print(f"    [Warning] Fallback search failed: {e}")
                
        if not urls:
            return [], metrics
            
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
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Referer': 'https://www.google.com/'
                        } # Spoofing to avoid 403s
                    )
                    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
                        out_file.write(response.read())
                        
                # Verify the image
                print(f"    Verifying image {dest_path.name}...")
                if self.verify_reference_image(dest_path, product.product_name):
                    saved_paths.append(dest_path)
                else:
                    print(f"    [Warning] Image {dest_path.name} does not contain the product. Deleting.")
                    dest_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"    [Warning] Failed to download reference image {url}: {e}")
                
        return saved_paths, metrics

