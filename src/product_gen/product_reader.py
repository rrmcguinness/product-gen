from pathlib import Path
from typing import List, Union
import json

import pandas as pd

from .model import ProductImageGenerationData


def read_product_data(file_path: Union[Path, str]) -> List[ProductImageGenerationData]:
    """
    Reads an Excel file containing product information and returns a list 
    of enterprise-grade ProductImageGenerationData models.
    Supports multiple formats by normalizing column names and parsing JSON fields.
    """
    # Load data using pandas
    df = pd.read_excel(file_path)
    
    # Normalize column names: lowercase and replace spaces with underscores
    df.columns = [str(c).lower().replace(' ', '_') for c in df.columns]
    
    # If there are duplicate columns after normalization, merge them by taking the first non-null value
    if df.columns.duplicated().any():
        df = df.T.groupby(level=0).first().T
        
    # Clean up pandas NaN, converting to Python None for Pydantic
    df = df.astype(object).where(pd.notna(df), None)
    
    # Deduplicate based on wpid to ensure we process unique products
    if "wpid" in df.columns:
        df.drop_duplicates(subset=["wpid"], keep="first", inplace=True)
    
    # Convert records to dicts
    records = df.to_dict(orient="records")
    
    # Parse JSON in product_long_description if present and handle mapping
    for record in records:
        # Map product_category to product_type if missing
        if "product_category" in record and not record.get("product_type"):
            record["product_type"] = record["product_category"]
            
        pld = record.get("product_long_description")
        if isinstance(pld, str) and pld.strip().startswith("{"):
            try:
                record["product_long_description"] = json.loads(pld)
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON for {record.get('wpid')}: {e}")
                pass
                
    return [ProductImageGenerationData.model_validate(record) for record in records]
