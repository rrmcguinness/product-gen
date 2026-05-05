from typing import Optional, List, Union
from pydantic import BaseModel, ConfigDict, Field

class ProductLongDescriptionDetail(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        extra='allow',
    )
    retailer_id: Optional[str] = None
    competitor_name: Optional[str] = None
    url: Optional[str] = None
    brand: Optional[str] = None
    model_num: Optional[str] = None
    title: Optional[str] = None
    product_short_description: Optional[str] = None
    product_long_description: Optional[str] = None
    product_description_bullet_points: Optional[str] = None
    category_hierarchy: Optional[str] = None
    category_level0: Optional[str] = None
    category_level1: Optional[str] = None
    category_level2: Optional[str] = None
    category_level3: Optional[str] = None
    category_level4: Optional[str] = None
    product_additional_urls: Optional[dict] = None

class ProductImageGenerationData(BaseModel):
    """
    Enterprise-grade Pydantic model representing the data structure 
    from the Google 50 SKUs image generation Excel file.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    wpid: Optional[str] = None
    gtin: Optional[int] = None
    upc: Optional[int] = None
    ean: Optional[int] = None
    reqmt_lvl_desc: Optional[str] = None
    product_type: Optional[str] = None
    ptg: Optional[float] = None
    product_name: Optional[str] = None
    product_long_description: Optional[Union[str, ProductLongDescriptionDetail]] = None
    product_short_description: Optional[str] = None
    main_image_url: Optional[str] = None
    attribute_key: Optional[str] = None
    value: Optional[str] = None
    model: Optional[str] = None
    data_source: Optional[str] = None


class CategoryHierarchy(BaseModel):
    level_1: str = Field(description="Top level category")
    level_2: str = Field(description="Second level category")
    level_3: str = Field(description="Third level category")
    level_4: str = Field(description="Fourth level category")
    level_5: Optional[str] = Field(default=None, description="Optional fifth level category")

class ProductAttributes(BaseModel):
    color: Optional[str] = Field(default=None, description="The color of the product (Schema.org: color)")
    material: Optional[str] = Field(default=None, description="The material the product is made of (Schema.org: material)")
    height: Optional[str] = Field(default=None, description="The height of the product (Schema.org: height)")
    width: Optional[str] = Field(default=None, description="The width of the product (Schema.org: width)")
    depth: Optional[str] = Field(default=None, description="The depth of the product (Schema.org: depth)")
    weight: Optional[str] = Field(default=None, description="The weight of the product (Schema.org: weight)")
    brand: Optional[str] = Field(default=None, description="The brand of the product")
    target_audience: Optional[str] = Field(default=None, description="Target audience")
    key_features: List[str] = Field(default_factory=list, description="Key features")
    price_range: Optional[str] = Field(default=None, description="Price range")
    origin_country: Optional[str] = Field(default=None, description="Country of origin")
    packaging_type: Optional[str] = Field(default=None, description="Type of packaging")


class ImageReview(BaseModel):
    uri: str = Field(description="URI or path to the generated image")
    score: float = Field(description="Likeness score between 0.0 and 1.0")
    reasoning: str = Field(description="Reasoning for the score")
    retry_count: int = Field(default=0, description="Number of retries for this image")
    image_size_bytes: Optional[int] = Field(default=None, description="Size of the generated image in bytes")

class SchemaProductAttributes(BaseModel):
    color: Optional[str] = Field(default=None, description="The color of the product (Schema.org: color)")
    material: Optional[str] = Field(default=None, description="The material the product is made of (Schema.org: material)")
    height: Optional[str] = Field(default=None, description="The height of the product (Schema.org: height)")
    width: Optional[str] = Field(default=None, description="The width of the product (Schema.org: width)")
    depth: Optional[str] = Field(default=None, description="The depth of the product (Schema.org: depth)")
    weight: Optional[str] = Field(default=None, description="The weight of the product (Schema.org: weight)")


class ProductEnrichment(BaseModel):
    product_name: str = Field(description="The formal, descriptive name of the product")
    category: CategoryHierarchy = Field(description="Deep 4+ level category relationship for PDP")
    attributes: ProductAttributes = Field(description="Product attributes aligned with Schema.org where applicable")
    suggested_natural_environments: List[str] = Field(description="2 or 3 distinct, highly visual dynamic settings appropriate for photographing this product in real life")
    detailed_description: str = Field(description="A deep, rich description of the product based on all available data")

class StepMetrics(BaseModel):
    step_name: str = Field(description="Name of the step")
    time_taken: float = Field(description="Time taken in seconds")
    input_tokens: Optional[int] = Field(default=None, description="Number of input tokens")
    output_tokens: Optional[int] = Field(default=None, description="Number of output tokens")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens used")
    model_used: Optional[str] = Field(default=None, description="Model used for this step")

class PipelineMetrics(BaseModel):
    total_time: float = Field(default=0.0, description="Total time taken for the pipeline")
    steps: List[StepMetrics] = Field(default_factory=list, description="Metrics for each step")
    total_tokens: int = Field(default=0, description="Total tokens used across all steps")
    average_tokens_per_step: float = Field(default=0.0, description="Average tokens per step")

class DetailedProduct(ProductImageGenerationData):
    """
    Enriched product detail model populated by GenAI.
    Follows an OpenSchema-like structure with deep categorizations, 
    while preserving all original ProductImageGenerationData attributes.
    """
    product_name: str = Field(description="The formal, descriptive name of the product")
    category: CategoryHierarchy = Field(description="Deep 4+ level category relationship for PDP")
    attributes: ProductAttributes = Field(description="Product attributes aligned with Schema.org where applicable")
    suggested_natural_environments: List[str] = Field(description="2 or 3 distinct, highly visual dynamic settings appropriate for photographing this product in real life")
    detailed_description: str = Field(description="A deep, rich description of the product based on all available data")
    image_based_description: Optional[str] = Field(default=None, description="A highly detailed description of the product generated from reference images")
    generation_model: Optional[str] = Field(default=None, description="The model used to generate the content")
    image_description_model: Optional[str] = Field(default=None, description="The model used to generate the image description")
    image_reviews: List[ImageReview] = Field(default_factory=list, description="Reviews for generated images")
    metrics: Optional[PipelineMetrics] = Field(default=None, description="Pipeline metrics for this product")


class ProductLikenessReview(BaseModel):
    score: float = Field(description="Likeness score between 0.0 and 1.0 representing how well the generated image matches the original product.")
    reasoning: str = Field(description="Detailed reasoning for the score, comparing the generated image with the original reference image(s).")



