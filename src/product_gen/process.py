import os
import argparse
from pathlib import Path
import shutil
import concurrent.futures
import time
from functools import wraps

from google import genai
from google.genai import types
from google.genai.errors import APIError

from .product_reader import read_product_data
from .model import DetailedProduct, ProductLikenessReview, ImageReview, ProductEnrichment, StepMetrics, PipelineMetrics, ProductImageGenerationData, CategoryHierarchy, ProductLongDescriptionDetail
from pydantic import ValidationError
from .image_finder import ImageFinder
from .pdp import generate_pdp_html


def retry_with_backoff(max_retries=5, base_delay=2, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    print(f"  -> API Error: {e}. Retrying in {delay}s (Attempt {i+1}/{max_retries})...")
                    if i == max_retries - 1:
                        raise
                    time.sleep(delay)
                    delay *= backoff_factor
                except Exception as e:
                    print(f"  -> Unexpected error: {e}. Retrying in {delay}s (Attempt {i+1}/{max_retries})...")
                    if i == max_retries - 1:
                        raise
                    time.sleep(delay)
                    delay *= backoff_factor
            return func(*args, **kwargs)
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3)
def enrich_product(client: genai.Client, product_json: str) -> tuple[DetailedProduct, StepMetrics]:
    prompt_template = os.environ.get("ENRICH_PROMPT", "")
    prompt = prompt_template.format(schema=ProductEnrichment.model_json_schema(), product_json=product_json)
    
    primary_model = os.environ.get("ENRICH_MODEL_PRIMARY", "gemini-3.1-pro-preview")
    fallback_model = os.environ.get("ENRICH_MODEL_FALLBACK", "gemini-3-flash-preview")
    used_model = primary_model
    
    primary_retries = int(os.environ.get("PRIMARY_MODEL_RETRIES", "3"))
    timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
    start_time = time.time()
    response = None
    
    for attempt in range(primary_retries + 1):
        try:
            if attempt > 0:
                print(f"  -> Retrying primary model {primary_model} (Attempt {attempt}/{primary_retries})...")
            response = client.models.generate_content(
                model=primary_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=0.4,
                    http_options={'timeout': timeout}
                )
            )
            break
        except Exception as e:
            print(f"  -> Primary model {primary_model} failed: {e}.")
            if attempt < primary_retries:
                delay = 2 ** attempt
                print(f"    Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                print(f"    Max retries reached for primary model. Trying fallback {fallback_model}...")
                used_model = fallback_model
                response = client.models.generate_content(
                    model=fallback_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}],
                        temperature=0.4,
                        http_options={'timeout': timeout}
                    )
                )
    end_time = time.time()
        
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
        
    enrichment = ProductEnrichment.model_validate_json(text.strip())
    obj = DetailedProduct(
        product_name=enrichment.product_name,
        category=enrichment.category,
        attributes=enrichment.attributes,
        suggested_natural_environments=enrichment.suggested_natural_environments,
        detailed_description=enrichment.detailed_description,
    )
    obj.generation_model = used_model
    
    # Extract tokens
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage and usage.prompt_token_count is not None else 0
    output_tokens = usage.candidates_token_count if usage and usage.candidates_token_count is not None else 0
    total_tokens = input_tokens + output_tokens
    
    metrics = StepMetrics(
        step_name="Enrich Product",
        time_taken=end_time - start_time,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model_used=used_model
    )
    
    return obj, metrics


@retry_with_backoff(max_retries=3)
def describe_product_from_images(client: genai.Client, ref_paths: list[Path]) -> tuple[str, str, StepMetrics]:
    prompt = os.environ.get("DESCRIBE_PROMPT", "")
    
    contents = []
    for rp in ref_paths:
        with open(rp, "rb") as f:
            img_bytes = f.read()
        mime = "image/jpeg"
        if rp.suffix.lower() == ".png": mime = "image/png"
        elif rp.suffix.lower() == ".webp": mime = "image/webp"
        
        contents.append(
            types.Part.from_bytes(data=img_bytes, mime_type=mime)
        )
        
    contents.append(prompt)
    
    primary_model = os.environ.get("DESCRIBE_MODEL_PRIMARY", "gemini-3.1-pro-preview")
    fallback_model = os.environ.get("DESCRIBE_MODEL_FALLBACK", "gemini-3.1-flash-preview")
    primary_retries = int(os.environ.get("PRIMARY_MODEL_RETRIES", "3"))
    timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
    start_time = time.time()
    response = None
    
    for attempt in range(primary_retries + 1):
        try:
            if attempt > 0:
                print(f"  -> Retrying primary model {primary_model} (Attempt {attempt}/{primary_retries})...")
            response = client.models.generate_content(
                model=primary_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    http_options={'timeout': timeout}
                )
            )
            break
        except Exception as e:
            print(f"  -> Primary model {primary_model} failed: {e}.")
            if attempt < primary_retries:
                delay = 2 ** attempt
                print(f"    Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                print(f"    Max retries reached for primary model. Trying fallback {fallback_model}...")
                used_model = fallback_model
                response = client.models.generate_content(
                    model=fallback_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        http_options={'timeout': timeout}
                    )
                )
    end_time = time.time()
        
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage and usage.prompt_token_count is not None else 0
    output_tokens = usage.candidates_token_count if usage and usage.candidates_token_count is not None else 0
    total_tokens = input_tokens + output_tokens
    
    metrics = StepMetrics(
        step_name="Describe Product from Images",
        time_taken=end_time - start_time,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model_used=used_model
    )
        
    return response.text.strip(), used_model, metrics


@retry_with_backoff(max_retries=3)
def judge_product_likeness(client: genai.Client, original_paths: list[Path], generated_path: Path, description: str) -> tuple[ProductLikenessReview, StepMetrics]:
    """
    Judges the likeness of a generated image against original reference images.
    """
    instructions = os.environ.get("JUDGE_INSTRUCTIONS", "")
    prompt = os.environ.get("JUDGE_PROMPT", "")
    
    contents = []
    # Add original images
    for rp in original_paths:
        with open(rp, "rb") as f:
            img_bytes = f.read()
        mime = "image/jpeg"
        if rp.suffix.lower() == ".png": mime = "image/png"
        elif rp.suffix.lower() == ".webp": mime = "image/webp"
        
        contents.append(
            types.Part.from_bytes(data=img_bytes, mime_type=mime)
        )
        
    # Add generated image
    with open(generated_path, "rb") as f:
        img_bytes = f.read()
    mime = "image/jpeg"
    if generated_path.suffix.lower() == ".png": mime = "image/png"
    elif generated_path.suffix.lower() == ".webp": mime = "image/webp"
    
    contents.append(
        types.Part.from_bytes(data=img_bytes, mime_type=mime)
    )
    
    # Add prompt and description
    contents.append(f"{prompt}\n\nProduct Description:\n{description}")
    
    model_name = os.environ.get("JUDGE_MODEL", "gemini-2.5-pro")
    timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
    start_time = time.time()
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                top_p=0.7,
                top_k=60,   
                system_instruction=instructions,
                response_mime_type="application/json",
                response_schema=ProductLikenessReview,
                http_options={'timeout': timeout}
            )
        )
        end_time = time.time()
        
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage and usage.prompt_token_count is not None else 0
        output_tokens = usage.candidates_token_count if usage and usage.candidates_token_count is not None else 0
        total_tokens = input_tokens + output_tokens
        
        metrics = StepMetrics(
            step_name="Judge Product Likeness",
            time_taken=end_time - start_time,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model_used=model_name
        )
        
        return ProductLikenessReview.model_validate_json(response.text.strip()), metrics
    except (APIError, ValidationError) as e:
        end_time = time.time()
        print(f"    Judge failed: {e}")
        metrics = StepMetrics(
            step_name="Judge Product Likeness (Failed)",
            time_taken=end_time - start_time,
            model_used=model_name
        )
        return ProductLikenessReview(score=0.0, reasoning=f"Judge failed with error: {e}"), metrics


import os

def load_env() -> None:
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.strip().split("=", 1)
                    val = val.strip(''' '"''')
                    if key.startswith("export "):
                        key = key[7:]
                    os.environ[key] = val

load_env()

def load_constraints() -> str:
    constraints_path = Path(__file__).parent / "image_constraints.md"
    if constraints_path.exists():
        with open(constraints_path, "r") as f:
            return f.read().strip()
    return ""

def generate_and_judge_images(client: genai.Client, detailed_product: DetailedProduct, output_dir: Path, ref_paths: list[Path] | None = None, image_description: str = "", use_reference_text: bool = True) -> None:
    environments = detailed_product.suggested_natural_environments[:2]
    if not environments:
        environments = ["A beautiful, well-lit studio environment", "In a natural lifestyle setting"]
    elif len(environments) == 1:
        environments.append(f"{environments[0]}, but from a different aesthetic angle")
        
    all_scenes = ["Seamless pure white background"]  # + environments
    
    if not detailed_product.metrics:
        detailed_product.metrics = PipelineMetrics()
        
    constraints = load_constraints()
        
    for i, env in enumerate(all_scenes, 1):
        prompt_base = os.environ.get("GENERATE_PROMPT_BASE", "")
        prompt = (
            f"{constraints}\n\n"
            f"{prompt_base.format(product_name=detailed_product.product_name, level_1=detailed_product.category.level_1, level_2=detailed_product.category.level_2)}\n"
        )
        
        if use_reference_text:
            if image_description:
                prompt += f"Product Description (from image): {image_description}\n"
                prompt += "Ensure the generated image uses the exact sRGB colors specified in the description.\n"
            else:
                prompt += f"Description: {detailed_product.detailed_description[:200]}.\n"
            
        prompt += (
            f"Environment: {env}. "
            f"Style: Professional, photorealistic, 2k resolution, highly detailed."
        )
        
        retry = 0
        max_retries = 3
        passed = False
        
        while retry <= max_retries and not passed:
            try:
                print(f"  -> Generating image {i}/{len(all_scenes)} (Attempt {retry})...")
                contents = []
                if ref_paths:
                    for rp in ref_paths:
                        with open(rp, "rb") as f:
                            img_bytes = f.read()
                        mime = "image/jpeg"
                        if rp.suffix.lower() == ".png": mime = "image/png"
                        elif rp.suffix.lower() == ".webp": mime = "image/webp"
                        
                        contents.append(
                            types.Part.from_bytes(data=img_bytes, mime_type=mime)
                        )
                        
                contents.append(prompt)
                
                model_name = os.environ.get("GENERATE_MODEL", "gemini-3-pro-image-preview")
                timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
                start_time = time.time()
                img_response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        http_options={'timeout': timeout}
                    )
                )
                end_time = time.time()
                
                usage = img_response.usage_metadata
                input_tokens = usage.prompt_token_count if usage and usage.prompt_token_count is not None else 0
                output_tokens = usage.candidates_token_count if usage and usage.candidates_token_count is not None else 0
                total_tokens = input_tokens + output_tokens
                
                gen_metrics = StepMetrics(
                    step_name=f"Generate Image {i} (Attempt {retry})",
                    time_taken=end_time - start_time,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    model_used=model_name
                )
                detailed_product.metrics.steps.append(gen_metrics)
                
                found_image = False
                generated_dir = output_dir / "generated"
                generated_dir.mkdir(parents=True, exist_ok=True)
                image_path = generated_dir / f"image_{i}_attempt_{retry}.jpeg"
                image_size = 0
                
                if img_response.candidates and img_response.candidates[0].content.parts:
                    for part in img_response.candidates[0].content.parts:
                        if part.inline_data:
                            image_bytes = part.inline_data.data
                            with open(image_path, "wb") as f:
                                f.write(image_bytes)
                            image_size = len(image_bytes)
                            print(f"    Saved attempt: {image_path} ({image_size} bytes)")
                            found_image = True
                            break
                            
                if not found_image:
                    print(f"    Warning: No inline image data returned by the model.")
                    retry += 1
                    continue
                    
                # Judge the image
                if ref_paths:
                    print(f"    Judging image {i} (Attempt {retry})...")
                    review, judge_metrics = judge_product_likeness(client, ref_paths, image_path, image_description or detailed_product.detailed_description)
                    detailed_product.metrics.steps.append(judge_metrics)
                    print(f"    Score: {review.score}")
                    
                    image_review = ImageReview(
                        uri=str(image_path),
                        score=review.score,
                        reasoning=review.reasoning,
                        retry_count=retry,
                        image_size_bytes=image_size
                    )
                    detailed_product.image_reviews.append(image_review)
                    
                    if review.score >= 0.9:
                        passed = True
                        print(f"    Image {i} passed with score {review.score}")
                    else:
                        print(f"    Image {i} failed with score {review.score}")
                        retry += 1
                        if retry <= max_retries:
                            print(f"    Retrying...")
                            continue
                        else:
                            print(f"    Max retries reached.")
                            
                    # Save final image to product level
                    dest_image_path = output_dir / f"image_{i}.jpeg"
                    shutil.copy(image_path, dest_image_path)
                    image_review.uri = str(dest_image_path)
                else:
                    print("    No reference images to judge likeness.")
                    standard_path = output_dir / f"image_{i}.jpeg"
                    shutil.copy(image_path, standard_path)
                    passed = True
                    
            except APIError as e:
                print(f"    Failed to generate image {i} (API Error): {e}")
                retry += 1
                time.sleep(2 ** retry)
            except Exception as e:
                print(f"    Unexpected error during image generation {i}: {e}")
                retry += 1


def process_single_product(idx: int, product: ProductImageGenerationData, client: genai.Client, output_base: Path, use_reference_images: bool, force: bool, use_image_description: bool, use_reference_text: bool) -> None:
    wpid = product.wpid or f"unknown_{idx}"
    output_dir = output_base / wpid
    
    # Resume logic: Skip if already completely processed
    if not force and (output_dir / "index.html").exists():
        return
        
    print(f"\nProcessing: {product.product_name or wpid or 'Unknown'}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / "product_detail.json"
    
    # Step 1: Enrich Product
    try:
        print("  -> Enriching product details...")
        product_json = product.model_dump_json(exclude_none=True)
        detailed, enrich_metrics = enrich_product(client, product_json)
        
        detailed.metrics = PipelineMetrics(steps=[enrich_metrics])
        
        # Forward the original product properties
        for field in product.model_fields_set:
            setattr(detailed, field, getattr(product, field))
            
        # Override category if available in product_long_description (user noted it doesn't need category extraction)
        if isinstance(product.product_long_description, ProductLongDescriptionDetail):
            pld = product.product_long_description
            if pld.category_level1:
                detailed.category = CategoryHierarchy(
                    level_1=pld.category_level1,
                    level_2=pld.category_level2 or "Unknown",
                    level_3=pld.category_level3 or "Unknown",
                    level_4=pld.category_level4 or "Unknown",
                )
        
        with open(detail_path, "w") as f:
            f.write(detailed.model_dump_json(indent=2))
        print(f"    Saved: {detail_path}")
        
    except Exception as e:
        print(f"  -> Failed to enrich product {wpid}: {e}")
        return
        
    # Step 2: Extract & Download Reference Images
    ref_paths = []
    if use_reference_images or use_image_description:
        print("  -> Locating reference images...")
        finder = ImageFinder(output_base_dir=output_base)
        ref_paths = finder.download_reference_images(product)
        if ref_paths:
            for p in ref_paths:
                print(f"    Saved Reference: {p}")
        else:
            print("    No reference URLs detected.")
    else:
        print("    Skipping reference images as requested.")
        
    # Step 2.5: Describe product from images if requested
    image_description = ""
    if use_image_description and ref_paths:
        print("  -> Describing product from reference images...")
        image_description, desc_model, desc_metrics = describe_product_from_images(client, ref_paths)
        detailed.image_based_description = image_description
        detailed.image_description_model = desc_model
        
        detailed.metrics.steps.append(desc_metrics)
        
        # Resave detail json with the new description
        with open(detail_path, "w") as f:
            f.write(detailed.model_dump_json(indent=2))
        print(f"    Description generated and saved.")
        
    # Step 3: Generate and Judge Images with Retries
    gen_ref_paths = ref_paths if use_reference_images else []
    generate_and_judge_images(client, detailed, output_dir, ref_paths=gen_ref_paths, image_description=image_description, use_reference_text=use_reference_text)
    
    # Calculate totals
    if detailed.metrics:
        detailed.metrics.total_time = sum(s.time_taken for s in detailed.metrics.steps)
        detailed.metrics.total_tokens = sum(s.total_tokens for s in detailed.metrics.steps if s.total_tokens)
        if detailed.metrics.steps:
            detailed.metrics.average_tokens_per_step = detailed.metrics.total_tokens / len(detailed.metrics.steps)
    
    # Resave detail json with the new reviews and metrics
    with open(detail_path, "w") as f:
        f.write(detailed.model_dump_json(indent=2))
    print(f"    Reviews and metrics saved to product_detail.json")
    
    # Step 4: Generate HTML PDP UI
    generate_pdp_html(detailed, output_dir)


def run_pipeline(file_path: str | Path, max_records: int | None = None, use_reference_images: bool = True, force: bool = False, use_image_description: bool = False, use_reference_text: bool = True) -> list[ProductImageGenerationData]:
    print(f"Loading data from: {file_path}")
    products = read_product_data(file_path)
    
    print(f"Successfully loaded {len(products)} products into memory.")
    
    file_stem = Path(file_path).stem
    output_base = Path("output") / file_stem
    
    # Initialize the GenAI client using the Developer API with the key from .env
    client = genai.Client()
    
    if max_records:
        products = products[:max_records]
        print(f"Limited to {len(products)} products as requested.")
        
    thread_pool_size = int(os.environ.get("THREAD_POOL_SIZE", 5))
    print(f"Using thread pool size: {thread_pool_size}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_pool_size) as executor:
        futures = [
            executor.submit(
                process_single_product, 
                idx, product, client, output_base, use_reference_images, force, use_image_description, use_reference_text
            ) 
            for idx, product in enumerate(products, 1)
        ]
        # Wait for all to complete
        concurrent.futures.wait(futures)
        
    # Generate PDF Report using standalone script
    from product_gen.generate_report import run_report
    run_report(output_base)

    return products


def main() -> None:
    parser = argparse.ArgumentParser(description="Process product generation data.")
    parser.add_argument(
        "--max-records", 
        "-n",
        type=int, 
        default=None, 
        help="Strict limit on records to process. Less than 1 or omitted means all records."
    )
    parser.add_argument(
        "--useReferenceImages", "--useRefernceImages",
        type=str,
        default="True",
        choices=["True", "False"],
        help="Use reference images for generation (True/False)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of products even if they already exist."
    )
    parser.add_argument(
        "--useImageDescription",
        type=str,
        default="False",
        choices=["True", "False"],
        help="Generate detailed description from reference images and use for generation (True/False)"
    )
    parser.add_argument(
        "--no-refs",
        action="store_true",
        help="Do not use reference images or reference text for generation."
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        default="data/Google_50_skus_image_generation.xlsx",
        help="Path to the product Excel file"
    )
    args = parser.parse_args()
    
    use_ref = args.useReferenceImages == "True"
    use_desc = args.useImageDescription == "True"
    use_text = True
    
    if args.no_refs:
        use_ref = False
        use_desc = False
        use_text = False
        
    file_path = Path(args.file)
    run_pipeline(file_path, max_records=args.max_records, use_reference_images=use_ref, force=args.force, use_image_description=use_desc, use_reference_text=use_text)


if __name__ == "__main__":
    main()