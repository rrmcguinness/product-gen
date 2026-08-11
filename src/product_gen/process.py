import os
import argparse
from pathlib import Path
import shutil
import concurrent.futures
import time
from functools import wraps
import threading
import logging

from google import genai
from google.genai import types
from google.genai.errors import APIError

from .product_reader import read_product_data
from .model import DetailedProduct, ProductLikenessReview, ImageReview, ProductEnrichment, StepMetrics, PipelineMetrics, ProductImageGenerationData, CategoryHierarchy, ProductLongDescriptionDetail
from pydantic import ValidationError
from .image_finder import ImageFinder
from .pdp import generate_pdp_html
from dotenv import load_dotenv
from .utils import call_gemini, LLMError, check_rate_limit

logger = logging.getLogger(__name__)



def retry_with_backoff(max_retries=5, base_delay=2, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    logger.warning(f"  -> API Error: {e}. Retrying in {delay}s (Attempt {i+1}/{max_retries})...")
                    if i == max_retries - 1:
                        raise
                    time.sleep(delay)
                    delay *= backoff_factor
                except Exception as e:
                    logger.warning(f"  -> Unexpected error: {e}. Retrying in {delay}s (Attempt {i+1}/{max_retries})...")
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
    if not prompt_template:
        prompt_template = "Provide the output strictly conforming to the following JSON schema:\n{schema}\n\nProduct Info:\n{product_json}"
    prompt = prompt_template.format(schema=ProductEnrichment.model_json_schema(), product_json=product_json)
    
    primary_model = os.environ.get("ENRICH_MODEL_PRIMARY", "gemini-3.1-pro-preview")
    fallback_model = os.environ.get("ENRICH_MODEL_FALLBACK", "gemini-3-flash-preview")
    used_model = primary_model
    
    primary_retries = int(os.environ.get("PRIMARY_MODEL_RETRIES", "3"))
    timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
    temp = float(os.environ.get("ENRICH_TEMP", "0.4"))
    top_p = os.environ.get("ENRICH_TOP_P")
    top_k = os.environ.get("ENRICH_TOP_K")
    top_p = float(top_p) if top_p else None
    top_k = int(top_k) if top_k else None
    start_time = time.time()
    response = None
    
    used_model = primary_model
    try:
        response, metrics = call_gemini(
            client=client,
            model=primary_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=temp,
                top_p=top_p,
                top_k=top_k,
                http_options={'timeout': timeout},
                system_instruction=os.environ.get("ENRICH_INSTRUCTIONS", ""),
                response_mime_type="application/json",
                response_schema=ProductEnrichment,
            ),
            step_name="Enrich Product (Primary)",
            max_retries=primary_retries
        )
    except LLMError as e:
        logger.warning(f"    Primary model failed. Trying fallback {fallback_model}...")
        try:
            response, fallback_metrics = call_gemini(
                client=client,
                model=fallback_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],
                    temperature=temp,
                    top_p=top_p,
                    top_k=top_k,
                    http_options={'timeout': timeout},
                    system_instruction=os.environ.get("ENRICH_INSTRUCTIONS", ""),
                    response_mime_type="application/json",
                    response_schema=ProductEnrichment,
                ),
                step_name="Enrich Product (Fallback)",
                max_retries=0
            )
            used_model = fallback_model
            metrics = fallback_metrics
            for code, count in e.metrics.http_errors.items():
                metrics.http_errors[code] = metrics.http_errors.get(code, 0) + count
            metrics.retries += e.metrics.retries
        except LLMError as e2:
            e2.metrics.http_errors.update(e.metrics.http_errors)
            e2.metrics.retries += e.metrics.retries
            raise e2
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
    
    # Metrics are already collected by the wrapper
    metrics.step_name = "Enrich Product"
    
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
    used_model = primary_model
    primary_retries = int(os.environ.get("PRIMARY_MODEL_RETRIES", "3"))
    timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
    start_time = time.time()
    temp = float(os.environ.get("DESCRIBE_TEMP", "0.4"))
    top_p = os.environ.get("DESCRIBE_TOP_P")
    top_k = os.environ.get("DESCRIBE_TOP_K")
    top_p = float(top_p) if top_p else None
    top_k = int(top_k) if top_k else None
    response = None
    
    try:
        response, metrics = call_gemini(
            client=client,
            model=primary_model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=temp,
                top_p=top_p,
                top_k=top_k,
                http_options={'timeout': timeout},
                system_instruction=os.environ.get("DESCRIBE_INSTRUCTIONS", "")
            ),
            step_name="Describe Product from Images (Primary)",
            max_retries=primary_retries
        )
    except LLMError as e:
        logger.warning(f"    Primary model failed. Trying fallback {fallback_model}...")
        try:
            response, fallback_metrics = call_gemini(
                client=client,
                model=fallback_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temp,
                    top_p=top_p,
                    top_k=top_k,
                    http_options={'timeout': timeout},
                    system_instruction=os.environ.get("DESCRIBE_INSTRUCTIONS", "")
                ),
                step_name="Describe Product from Images (Fallback)",
                max_retries=0
            )
            used_model = fallback_model
            metrics = fallback_metrics
            for code, count in e.metrics.http_errors.items():
                metrics.http_errors[code] = metrics.http_errors.get(code, 0) + count
            metrics.retries += e.metrics.retries
        except LLMError as e2:
            e2.metrics.http_errors.update(e.metrics.http_errors)
            e2.metrics.retries += e.metrics.retries
            raise e2
    # Metrics are already collected by the wrapper
    metrics.step_name = "Describe Product from Images"
        
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
    
    temp = float(os.environ.get("JUDGE_TEMP", "0.0"))
    top_p = os.environ.get("JUDGE_TOP_P")
    top_k = os.environ.get("JUDGE_TOP_K")
    top_p = float(top_p) if top_p else 0.7
    top_k = int(top_k) if top_k else 60
    
    model_name = os.environ.get("JUDGE_MODEL", "gemini-2.5-pro")
    timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
    try:
        response, metrics = call_gemini(
            client=client,
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=temp,
                top_p=top_p,
                top_k=top_k,   
                system_instruction=instructions,
                response_mime_type="application/json",
                response_schema=ProductLikenessReview,
                http_options={'timeout': timeout}
            ),
            step_name="Judge Product Likeness",
            max_retries=0
        )
        return ProductLikenessReview.model_validate_json(response.text.strip()), metrics
    except LLMError as e:
        logger.error(f"    Judge failed: {e.original_error}")
        return ProductLikenessReview(score=0.0, reasoning=f"Judge failed with error: {e.original_error}"), e.metrics
    except ValidationError as e:
        logger.error(f"    Validation failed on judge response: {e}")
        return ProductLikenessReview(score=0.0, reasoning=f"Validation failed on judge response: {e}"), metrics


import os

load_dotenv()

def load_constraints() -> str:
    constraints_path = Path(__file__).parent / "image_constraints.md"
    if constraints_path.exists():
        with open(constraints_path, "r") as f:
            return f.read().strip()
    return ""

def rewrite_prompt_with_feedback(client: genai.Client, original_prompt: str, reasoning: str, retry: int) -> tuple[str, StepMetrics]:
    """
    Uses Gemini 3.1 Pro to rewrite the image generation prompt based on the judge's critique.
    """
    prompt_template = os.environ.get(
        "REWRITE_PROMPT",
        "You are an expert prompt engineer for text-to-image models. Your task is to improve an image generation prompt based on feedback from a quality judge.\\n\\nOriginal Prompt:\\n{original_prompt}\\n\\nJudge's Feedback/Reasoning for Failure:\\n{reasoning}\\n\\nGenerate a new, optimized prompt that incorporates the feedback to fix the issues. Make the instructions specific, actionable, and clear for the image generator. Output ONLY the new prompt text, nothing else."
    )
    prompt = prompt_template.replace("\\n", "\n").format(original_prompt=original_prompt, reasoning=reasoning)
    
    model_name = os.environ.get("ENRICH_MODEL_PRIMARY", "gemini-3.1-pro-preview")
    timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
    try:
        response, metrics = call_gemini(
            client=client,
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                http_options={'timeout': timeout}
            ),
            step_name=f"Rewrite Prompt (Attempt {retry})",
            max_retries=0
        )
        return response.text.strip(), metrics
    except LLMError as e:
        logger.warning(f"    [Warning] Failed to rewrite prompt: {e.original_error}. Using original prompt.")
        return original_prompt, e.metrics

def generate_and_judge_images(client: genai.Client, detailed_product: DetailedProduct, output_dir: Path, ref_paths: list[Path] | None = None, image_description: str = "", use_reference_text: bool = True, use_ref_images_in_gen: bool = False, stop_event: threading.Event = None) -> None:
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
        if stop_event and stop_event.is_set():
            logger.info(f"  -> Cancellation requested. Stopping image generation.")
            return
        prompt_base = os.environ.get("GENERATE_PROMPT_BASE", "")
        prompt = (
            f"{constraints}\n\n"
            f"{prompt_base.format(product_name=detailed_product.product_name, level_1=detailed_product.category.level_1, level_2=detailed_product.category.level_2)}\n"
        )
        
        if ref_paths and use_ref_images_in_gen:
            ref_refs = ", ".join([f"[{i}]" for i in range(1, len(ref_paths) + 1)])
            prompt += f"Using the provided reference images {ref_refs} as the absolute ground truth for the product's physical appearance, generate a new high-fidelity photograph. Maintain strict visual consistency with the shape, colors, materials, and branding shown in those references.\n"
            
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
        current_prompt = prompt
        
        while retry <= max_retries and not passed:
            if stop_event and stop_event.is_set():
                logger.info(f"  -> Cancellation requested. Stopping retry loop.")
                return
            try:
                logger.info(f"  -> Generating image {i}/{len(all_scenes)} (Attempt {retry})...")
                contents = []
                if ref_paths and use_ref_images_in_gen:
                    for rp in ref_paths:
                        with open(rp, "rb") as f:
                            img_bytes = f.read()
                        mime = "image/jpeg"
                        if rp.suffix.lower() == ".png": mime = "image/png"
                        elif rp.suffix.lower() == ".webp": mime = "image/webp"
                        
                        contents.append(
                            types.Part.from_bytes(data=img_bytes, mime_type=mime)
                        )
                        
                contents.append(current_prompt)
                
                model_name = os.environ.get("GENERATE_MODEL", "gemini-3-pro-image-preview")
                timeout = int(os.environ.get("API_CALL_TIMEOUT", "60")) * 1000
                start_time = time.time()
                
                check_rate_limit()
                
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
                    model_used=model_name,
                    images_passed=bool(ref_paths and use_ref_images_in_gen)
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
                            logger.info(f"    Saved attempt: {image_path} ({image_size} bytes)")
                            found_image = True
                            break
                            
                if not found_image:
                    logger.warning(f"    Warning: No inline image data returned by the model.")
                    retry += 1
                    continue
                    
                if ref_paths:
                    logger.info(f"    Judging image {i} (Attempt {retry}) against {len(ref_paths)} reference images...")
                    review, judge_metrics = judge_product_likeness(client, ref_paths, image_path, image_description or detailed_product.detailed_description)
                    detailed_product.metrics.steps.append(judge_metrics)
                    logger.info(f"    Score: {review.score}")
                    
                    image_review = ImageReview(
                        uri=str(image_path),
                        score=review.score,
                        reasoning=review.reasoning,
                        retry_count=retry,
                        image_size_bytes=image_size,
                        prompt=current_prompt
                    )
                    detailed_product.image_reviews.append(image_review)
                    
                    threshold = float(os.environ.get("PASS_THRESHOLD", "0.9"))
                    if review.score >= threshold:
                        passed = True
                        detailed_product.metrics.retries_to_pass = retry
                        logger.info(f"    Image {i} passed with score {review.score}")
                    else:
                        logger.info(f"    Image {i} failed with score {review.score}")
                        retry += 1
                        if retry <= max_retries:
                            logger.info(f"    Retrying with improved prompt...")
                            current_prompt, rewrite_metrics = rewrite_prompt_with_feedback(client, current_prompt, review.reasoning, retry)
                            detailed_product.metrics.steps.append(rewrite_metrics)
                            continue
                        else:
                            logger.info(f"    Max retries reached.")
                            
                    # Point URI to the generated attempt directly
                    image_review.uri = str(image_path)
                else:
                    logger.info("    No reference images to judge likeness. Flagging for review.")
                    image_review = ImageReview(
                        uri=str(image_path),
                        score=0.0,
                        reasoning="No reference images provided for likeness evaluation. Automatically flagged for manual review.",
                        retry_count=retry,
                        image_size_bytes=image_size,
                        prompt=current_prompt
                    )
                    detailed_product.image_reviews.append(image_review)
                    passed = True
                    detailed_product.metrics.retries_to_pass = 0
                    
            except APIError as e:
                code = getattr(e, 'code', None) or getattr(e, 'status_code', None) or 0
                detailed_product.metrics.http_errors[code] = detailed_product.metrics.http_errors.get(code, 0) + 1
                logger.error(f"    Failed to generate image {i} (API Error {code}): {e}")
                retry += 1
                time.sleep(2 ** retry)
            except Exception as e:
                detailed_product.metrics.http_errors[0] = detailed_product.metrics.http_errors.get(0, 0) + 1
                logger.error(f"    Unexpected error during image generation {i}: {e}")
                retry += 1
        
        detailed_product.metrics.total_retries += retry


def process_single_product(idx: int, product: ProductImageGenerationData, client: genai.Client, output_base: Path, use_reference_images: bool, force: bool, use_image_description: bool, use_reference_text: bool, stop_event: threading.Event) -> None:
    if stop_event.is_set():
        return
    wpid = product.wpid or f"unknown_{idx}"
    output_dir = output_base / wpid
    
    # Resume logic: Skip if already completely processed
    if not force and (output_dir / "index.html").exists():
        return
        
    logger.info(f"\nProcessing: {product.product_name or wpid or 'Unknown'}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / "product_detail.json"
    
    # Step 1: Enrich Product
    try:
        logger.info("  -> Enriching product details...")
        product_json = product.model_dump_json(exclude_none=True)
        detailed, enrich_metrics = enrich_product(client, product_json)
        
        detailed.metrics = PipelineMetrics(steps=[enrich_metrics])
        detailed.metrics.total_retries += enrich_metrics.retries
        for code, count in enrich_metrics.http_errors.items():
            detailed.metrics.http_errors[code] = detailed.metrics.http_errors.get(code, 0) + count
        
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
        logger.info(f"    Saved: {detail_path}")
        
    except Exception as e:
        logger.error(f"  -> Failed to enrich product {wpid}: {e}")
        return
        
    # Step 2: Extract & Download Reference Images
    ref_paths = []
    if use_reference_images or use_image_description:
        logger.info("  -> Locating reference images...")
        finder = ImageFinder(client=client, output_base_dir=output_base)
        start_time = time.time()
        ref_paths, finder_metrics = finder.download_reference_images(product)
        end_time = time.time()
        
        detailed.metrics.steps.append(finder_metrics)
        
        download_metrics = StepMetrics(
            step_name="Download Reference Images",
            time_taken=end_time - start_time,
            model_used="N/A"
        )
        detailed.metrics.steps.append(download_metrics)
        
        if ref_paths:
            for p in ref_paths:
                logger.info(f"    Saved Reference: {p}")
        else:
            logger.info("    No reference URLs detected.")
            if use_reference_images or use_image_description:
                logger.warning(f"  -> [Warning] No reference images found for {wpid}. Proceeding with text-only generation.")
    else:
        logger.info("    Skipping reference images as requested.")
        
    # Step 2.5: Describe product from images if requested
    image_description = ""
    if use_image_description and ref_paths:
        logger.info(f"  -> Describing product from {len(ref_paths)} reference images...")
        image_description, desc_model, desc_metrics = describe_product_from_images(client, ref_paths)
        detailed.image_based_description = image_description
        detailed.image_description_model = desc_model
        
        detailed.metrics.steps.append(desc_metrics)
        detailed.metrics.total_retries += desc_metrics.retries
        for code, count in desc_metrics.http_errors.items():
            detailed.metrics.http_errors[code] = detailed.metrics.http_errors.get(code, 0) + count
        
        # Resave detail json with the new description
        with open(detail_path, "w") as f:
            f.write(detailed.model_dump_json(indent=2))
        logger.info(f"    Description generated and saved.")
        
    # Step 3: Generate and Judge Images with Retries
    if stop_event.is_set():
        return
    generate_and_judge_images(client, detailed, output_dir, ref_paths=ref_paths, image_description=image_description, use_reference_text=use_reference_text, use_ref_images_in_gen=use_reference_images, stop_event=stop_event)
    
    # Calculate totals
    if detailed.metrics:
        detailed.metrics.total_time = sum(s.time_taken for s in detailed.metrics.steps)
        detailed.metrics.total_tokens = sum(s.total_tokens for s in detailed.metrics.steps if s.total_tokens)
        if detailed.metrics.steps:
            detailed.metrics.average_tokens_per_step = detailed.metrics.total_tokens / len(detailed.metrics.steps)
    
    # Resave detail json with the new reviews and metrics
    with open(detail_path, "w") as f:
        f.write(detailed.model_dump_json(indent=2))
    logger.info(f"    Reviews and metrics saved to product_detail.json")
    
    # Step 4: Generate HTML PDP UI
    generate_pdp_html(detailed, output_dir)


def run_pipeline(file_path: str | Path, max_records: int | None = None, use_reference_images: bool = False, force: bool = False, use_image_description: bool = False, use_reference_text: bool = True, output_dir: str | Path | None = None, thread_pool_size: int | None = None) -> list[ProductImageGenerationData]:
    if use_reference_images:
        logger.warning("\n[!] WARNING: use_reference_images is set to True. This removes image indemnification.\n")
    logger.info(f"Loading data from: {file_path}")
    products = read_product_data(file_path)
    
    logger.info(f"Successfully loaded {len(products)} products into memory.")
    
    if output_dir:
        output_base = Path(output_dir)
    else:
        file_stem = Path(file_path).stem
        output_base = Path("output") / file_stem
        
    output_base.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = output_base / f"pipeline_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True
    )
    logging.info(f"Logging to: {log_file}")
    
    # Initialize the GenAI client using the Developer API with the key from .env
    client = genai.Client()
    
    if max_records:
        products = products[:max_records]
        logger.info(f"Limited to {len(products)} products as requested.")
        
    if thread_pool_size is None:
        thread_pool_size = int(os.environ.get("THREAD_POOL_SIZE", 5))
    logger.info(f"Using thread pool size: {thread_pool_size}")
    
    stop_event = threading.Event()

    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_pool_size) as executor:
        futures = []
        for idx, product in enumerate(products, 1):
            futures.append(
                executor.submit(
                    process_single_product,
                    idx,
                    product,
                    client,
                    output_base,
                    use_reference_images,
                    force,
                    use_image_description,
                    use_reference_text,
                    stop_event
                )
            )
        
        try:
            for future in concurrent.futures.as_completed(futures):
                if stop_event.is_set():
                    break
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Task failed: {e}")
        except KeyboardInterrupt:
            logger.warning("\n[!] KeyboardInterrupt received. Exiting immediately...")
            stop_event.set()
            executor.shutdown(wait=False, cancel_futures=True)
            import sys
            sys.exit(1)
        
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
        "--use-reference-images",
        action="store_true",
        help="Use reference images for generation and likeness judging."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of products even if they already exist."
    )
    parser.add_argument(
        "--use-image-description",
        action="store_true",
        help="Generate detailed description from reference images and use for generation."
    )
    parser.add_argument(
        "--no-product-description",
        action="store_true",
        help="Do not use the product's text description in the prompt."
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        default="data/Google_50_skus_image_generation.xlsx",
        help="Path to the product Excel file"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Custom output directory"
    )
    parser.add_argument(
        "--threads", "-j",
        type=int,
        default=None,
        help="Number of threads to use for processing. Overrides THREAD_POOL_SIZE env var."
    )
    args = parser.parse_args()
    
    use_ref = args.use_reference_images
    use_desc = args.use_image_description
    use_text = not args.no_product_description
        
    file_path = Path(args.file)
    run_pipeline(file_path, max_records=args.max_records, use_reference_images=use_ref, force=args.force, use_image_description=use_desc, use_reference_text=use_text, output_dir=args.output, thread_pool_size=args.threads)


if __name__ == "__main__":
    main()