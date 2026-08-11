# Step 4: Studio Image Generation

The image generation stage synthesizes photorealistic, commercial-grade product assets using Google's multimodal image generation model `gemini-3-pro-image-preview`.

---

## Technical Specifications & Studio Constraints

Generation is governed by strict photography constraints loaded dynamically from [`image_constraints.md`](../configuration/image-constraints.md):

| Constraint | Value | Rationale |
| :--- | :--- | :--- |
| **Pixel Dimensions** | `2200px x 2200px` | High-resolution zoom compatibility for e-commerce PDPs |
| **Aspect Ratio** | `1:1 (Square)` | Uniform catalog grid alignment |
| **Color Format** | `RGB 8-bit per pixel` | Standard web display profile |
| **Background** | `Seamless pure white (255, 255, 255)` | Zero ambient shadows, gradients, or floor occlusions |
| **Framing** | Close crop, front-facing | Centers focus exclusively on the primary subject |

---

## Prompt Assembly Strategy

Prompts are assembled dynamically within [`process.py:generate_and_judge_images`](../api/process.md):

```python
constraints = load_constraints()

prompt = (
    f"{constraints}\n\n"
    f"{prompt_base.format(product_name=detailed_product.product_name, level_1=detailed_product.category.level_1, level_2=detailed_product.category.level_2)}\n"
)

# Optional Conditioning: Reference Images
if ref_paths and use_ref_images_in_gen:
    prompt += "Using the provided reference images [1], [2] as the absolute ground truth..."

# Optional Conditioning: Physical Image Description
if use_reference_text:
    if image_description:
        prompt += f"Product Description (from image): {image_description}\n"
        prompt += "Ensure the generated image uses the exact sRGB colors specified in the description.\n"
    else:
        prompt += f"Description: {detailed_product.detailed_description[:200]}.\n"

prompt += "Environment: Seamless pure white background. Style: Professional, photorealistic, 2k resolution, highly detailed."
```

---

## Model Invocation & Byte Extraction

The pipeline issues a request to `gemini-3-pro-image-preview` and extracts inline image byte arrays:

```python
img_response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=contents, # Image parts + Prompt text
    config=types.GenerateContentConfig(
        http_options={'timeout': timeout}
    )
)

if img_response.candidates and img_response.candidates[0].content.parts:
    for part in img_response.candidates[0].content.parts:
        if part.inline_data:
            image_bytes = part.inline_data.data
            with open(image_path, "wb") as f:
                f.write(image_bytes)
```

Generated attempts are saved sequentially to disk:
`output/{wpid}/generated/image_1_attempt_{retry}.jpeg`
